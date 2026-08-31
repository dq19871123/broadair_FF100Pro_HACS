"""API 客户端模块 - 负责与远大云端 HTTP 接口通信.

本模块封装了与远大 IoT 云平台的完整交互逻辑：
- 动态签名计算 (MD5(AppToken + Nonce + Timestamp))
- 账号密码登录与会话 Token 获取
- Token 过期自动重新认证与重试机制 (处理 600/700/800 状态码)
- 针对 FF100-Pro 设备的状态查询、档位调节、模式切换与滤网重置
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import ssl
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    APP_TOKEN,
    CMD_AUTO_MODE,
    CMD_INDOOR_PURIFICATION,
    CMD_POLL,
    CMD_POWER_OFF,
    CMD_POWER_ON,
    CMD_RESET_COARSE_FILTER,
    CMD_RESET_HEPA_FILTER,
    CMD_SET_SPEED,
    CMD_SLEEP_MODE,
    ENDPOINT_CACHE,
    ENDPOINT_CONTROL,
    ENDPOINT_DEVICES,
    ENDPOINT_LOGIN,
    FAN_SPEED_COUNT,
)

_LOGGER = logging.getLogger(__name__)


class BroadAirApiError(Exception):
    """远大 API 通信基类异常."""


class BroadAirAuthError(BroadAirApiError):
    """身份认证异常 (Token 失效、过期或账号密码错误)."""


class BroadAirConnectionError(BroadAirApiError):
    """网络连接异常 (超时或无法连接到云端服务器)."""


def _md5(s: str) -> str:
    """计算字符串的 MD5 哈希值 (小写 32 位十六进制)."""
    return hashlib.md5(s.encode()).hexdigest()


def _generate_nonce() -> str:
    """生成 6 位随机数字字符串作为 Nonce."""
    return str(random.randint(100000, 999999))


def _generate_sign(nonce: str, timestamp: int) -> str:
    """计算登录接口的请求签名.

    计算规则来自官方 App 逆向工程：
    Sign = MD5(APP_TOKEN + Nonce + Timestamp)
    """
    data = f"{APP_TOKEN}{nonce}{timestamp}"
    return _md5(data)


def _create_ssl_context() -> ssl.SSLContext:
    """创建自定义 SSL 上下文.

    远大云端服务器 (broadair.remotcon.mobi:8201) 使用的 SSL 证书链在部分 Linux 环境下
    可能无法通过系统 CA 严格校验，因此关闭证书主机名校验以保障通信稳定性。
    """
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


async def async_login(
    account: str,
    password: str,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """通过手机号与密码登录远大云端接口.

    Args:
        account: 注册手机号
        password: 账号密码
        session: 可选的 aiohttp 客户端会话

    Returns:
        包含用户身份 Token 及用户信息的字典对象 (响应体中的 Data 字段)

    Raises:
        BroadAirAuthError: 账号或密码错误
        BroadAirConnectionError: 网络连接超时或失败
    """
    timestamp = int(time.time())
    nonce = _generate_nonce()
    sign = _generate_sign(nonce, timestamp)

    # 模拟官方 uni-app 客户端请求头
    headers = {
        "Content-Type": "application/json",
        "language": "cn",
        "token": "1",  # 登录接口固定传 "1"
        "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) uni-app",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    # 登录请求报文结构
    payload = {
        "Token": APP_TOKEN,
        "Timestamp": timestamp,
        "Sign": sign,
        "Nonce": nonce,
        "Account": account,
        "Password": password,
    }

    url = f"{API_BASE_URL}{ENDPOINT_LOGIN}"
    _LOGGER.debug("向云端发起登录请求: %s (账号: %s)", url, account)

    own_session = session is None
    if own_session:
        connector = aiohttp.TCPConnector(ssl=_create_ssl_context())
        session = aiohttp.ClientSession(connector=connector)

    try:
        async with asyncio.timeout(30):
            async with session.post(url, json=payload, headers=headers, ssl=_create_ssl_context()) as resp:
                try:
                    result = await resp.json()
                except Exception as json_err:
                    text_resp = await resp.text()
                    raise BroadAirConnectionError(
                        f"解析登录响应失败 (HTTP {resp.status}): {text_resp[:100]}"
                    ) from json_err

                _LOGGER.debug("登录响应状态码: %s", result.get("Code"))

                code = result.get("Code")
                if code != 200:
                    msg = result.get("Message", result.get("DetailMessage", "未知错误"))
                    raise BroadAirAuthError(f"登录失败 (Code: {code}): {msg}")

                # 返回登录成功后的 Data 对象 (包含 Token, ID, Account 等)
                data = result.get("Data")
                if isinstance(data, dict):
                    return data
                return {}

    except asyncio.TimeoutError as err:
        raise BroadAirConnectionError("登录请求响应超时") from err
    except (aiohttp.ClientError, BroadAirConnectionError, BroadAirAuthError):
        raise
    except Exception as err:
        raise BroadAirConnectionError(f"登录网络连接异常: {err}") from err
    finally:
        if own_session and session:
            await session.close()


class BroadAirApiClient:
    """远大新风肺保 API 客户端管理器."""

    def __init__(
        self,
        token: str,
        session: aiohttp.ClientSession | None = None,
        account: str | None = None,
        password: str | None = None,
    ) -> None:
        """初始化 API 客户端.

        Args:
            token: 登录成功后获得的会话 Token
            session: 传入的 aiohttp 会话 (若无则内部自建)
            account: 用于 Token 过期时自动重登的账号
            password: 用于 Token 过期时自动重登的密码
        """
        self._token = token
        self._session = session
        self._own_session = session is None
        self._account = account
        self._password = password
        self._ssl_context = _create_ssl_context()

    @property
    def token(self) -> str:
        """获取当前使用的会话 Token."""
        return self._token

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建内部使用的 aiohttp.ClientSession 实例."""
        if self._session is None:
            connector = aiohttp.TCPConnector(ssl=self._ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        """关闭客户端自建的网络会话."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    def _headers(self) -> dict[str, str]:
        """构造常规业务请求头 (携带会话 token)."""
        return {
            "Content-Type": "application/json",
            "language": "cn",
            "token": self._token,
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) uni-app",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Connection": "keep-alive",
        }

    async def _request(
        self,
        endpoint: str,
        data: dict[str, Any],
        timeout: int = 30,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """向云端发送 POST 请求，并处理鉴权失败后的自动刷新重试.

        Args:
            endpoint: API 路径
            data: 请求体参数字典
            timeout: 超时时间 (秒)
            retry_auth: 鉴权失败时是否尝试重登刷新 Token 并重发请求

        Returns:
            响应体中的 Data 字段数据

        Raises:
            BroadAirAuthError: 鉴权失败且无法恢复
            BroadAirConnectionError: 网络超时或中断
            BroadAirApiError: 业务逻辑错误
        """
        session = await self._get_session()
        url = f"{API_BASE_URL}{endpoint}"

        _LOGGER.debug("发送 API 请求 [%s]: %s", endpoint, data)

        try:
            async with asyncio.timeout(timeout):
                async with session.post(
                    url,
                    json=data,
                    headers=self._headers(),
                    ssl=self._ssl_context,
                ) as resp:
                    try:
                        result = await resp.json()
                    except Exception as json_err:
                        text_resp = await resp.text()
                        raise BroadAirConnectionError(
                            f"解析云端响应失败 (HTTP {resp.status}): {text_resp[:100]}"
                        ) from json_err

                    _LOGGER.debug("收到 API 响应 [%s]: %s", endpoint, result)

                    code = result.get("Code")
                    if code != 200:
                        # 兼容部分接口使用 Head.Code 返回状态码的设计
                        head_code = result.get("Head", {}).get("Code") if isinstance(result.get("Head"), dict) else None
                        if head_code == 200:
                            data_resp = result.get("Data")
                            return data_resp if data_resp is not None else {}

                        msg = result.get("Message", result.get("Msg", result.get("DetailMessage", "未知错误")))

                        # 远大接口定义的 Token 失效状态码：401, 403, 600(未登录), 700(Token需更新), 800(其他设备登录)
                        is_auth_error = (
                            code in (401, 403, 600, 700, 800, 10001)
                            or "token" in str(msg).lower()
                            or "验证失败" in str(msg)
                            or "过期" in str(msg)
                        )

                        if is_auth_error:
                            if retry_auth and self._account and self._password:
                                _LOGGER.info("Token 已过期或失效 (Code: %s, Msg: %s)，正在尝试自动重新登录...", code, msg)
                                try:
                                    await self.refresh_token()
                                    _LOGGER.info("Token 刷新成功，正在重试之前的请求...")
                                    return await self._request(endpoint, data, timeout, retry_auth=False)
                                except BroadAirAuthError as refresh_err:
                                    _LOGGER.error("Token 自动刷新失败: %s", refresh_err)
                                    raise BroadAirAuthError(
                                        f"鉴权失败且自动重登无效: {msg}"
                                    ) from refresh_err

                            raise BroadAirAuthError(f"API 鉴权失败 (Code: {code}): {msg}")
                        raise BroadAirApiError(f"API 业务请求失败 (Code: {code}): {msg}")

                    data_resp = result.get("Data")
                    return data_resp if data_resp is not None else {}

        except asyncio.TimeoutError as err:
            raise BroadAirConnectionError(f"请求超时: {url}") from err
        except (aiohttp.ClientError, BroadAirConnectionError, BroadAirAuthError):
            raise
        except Exception as err:
            raise BroadAirConnectionError(f"网络连接异常: {err}") from err

    async def refresh_token(self) -> str:
        """重新执行登录流程以刷新会话 Token."""
        if not self._account or not self._password:
            raise BroadAirAuthError("无法刷新 Token：未提供账号密码凭据")

        _LOGGER.info("正在为账号 %s 重新申请 Token", self._account)

        login_data = await async_login(self._account, self._password, self._session)
        self._token = login_data.get("Token", "")

        if not self._token:
            raise BroadAirAuthError("登录成功但返回的 Token 为空")

        return self._token

    async def get_devices(self) -> list[dict[str, Any]]:
        """获取用户绑定的全部设备列表.

        Returns:
            设备信息列表 (包含 ID, MAC, Name, EquipmentMode, Online 等字段)
        """
        result = await self._request(ENDPOINT_DEVICES, {"GroupName": ""})
        if isinstance(result, list):
            return result
        return []

    async def get_status(self, device_id: str) -> dict[str, Any]:
        """获取设备的实时运行状态与传感器数据.

        在官方 App 机制中：
        1. 优先调用 SetFreshLung (sjx="1", cs="") 向硬件下发实时状态同步指令；
        2. 若下发失败则降级调用 GetFreshLung 获取云端最近一次缓存数据。

        Args:
            device_id: 设备唯一标识 GUID (eq_guid)

        Returns:
            包含设备开关、档位、风量、传感器数值与滤网寿命的状态字典
        """
        try:
            return await self._request(
                ENDPOINT_CONTROL,
                {"eq_guid": device_id, "sjx": CMD_POLL, "cs": ""},
            )
        except BroadAirApiError as err:
            _LOGGER.debug("通过 SetFreshLung 轮询状态失败 (%s)，降级尝试 GetFreshLung 缓存接口", err)
            return await self._request(
                ENDPOINT_CACHE,
                {"eq_guid": device_id},
            )

    async def set_power(self, device_id: str, on: bool) -> dict[str, Any]:
        """控制设备开关机 (sjx: 3=开机, 2=关机).

        Args:
            device_id: 设备唯一标识 GUID
            on: True 为开机，False 为关机
        """
        cmd = CMD_POWER_ON if on else CMD_POWER_OFF
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": cmd, "cs": ""},
        )

    async def set_speed(self, device_id: str, speed: int) -> dict[str, Any]:
        """设定风速档位 (FF100-Pro 支持 1 到 3 档, sjx: 4).

        Args:
            device_id: 设备唯一标识 GUID
            speed: 目标风速 (1, 2, 3)

        Raises:
            ValueError: 当档位超出 1~3 范围时抛出
        """
        if not 1 <= speed <= FAN_SPEED_COUNT:
            raise ValueError(f"FF100-Pro 风速档位必须在 1 到 {FAN_SPEED_COUNT} 之间，传入值为: {speed}")
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_SET_SPEED, "cs": str(speed)},
        )

    async def set_sleep_mode(self, device_id: str, on: bool) -> dict[str, Any]:
        """开启或关闭睡眠模式 (sjx: 5, cs: 1=开启, 0=关闭).

        开启睡眠模式后，设备以极低静音转速运行，风速显示为睡眠档。
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_SLEEP_MODE, "cs": "1" if on else "0"},
        )

    async def set_auto_mode(self, device_id: str, on: bool) -> dict[str, Any]:
        """开启或关闭自动调节模式 (sjx: 18, cs: 1=开启, 0=关闭).

        开启后设备将根据粉尘/CO2 等环境指标自动变档。
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_AUTO_MODE, "cs": "1" if on else "0"},
        )

    async def set_indoor_purification(self, device_id: str, on: bool) -> dict[str, Any]:
        """开启或关闭室内净化/循环模式 (sjx: 19, cs: 1=开启, 0=关闭).

        切换新风肺保的送风阀门，进入室内空气循环净化状态。
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_INDOOR_PURIFICATION, "cs": "1" if on else "0"},
        )

    async def reset_hepa_filter(self, device_id: str) -> dict[str, Any]:
        """重置高效 HEPA 滤芯已用计时 (sjx: 8, cs: "1").

        在用户更换全新 HEPA 滤芯后调用，重置已用小时数为 0。
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_RESET_HEPA_FILTER, "cs": "1"},
        )

    async def reset_coarse_filter(self, device_id: str) -> dict[str, Any]:
        """重置初效/粗效滤网已用计时 (sjx: 9, cs: "1").

        在用户清洗并装回粗效滤网后调用，重置已用小时数为 0。
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_RESET_COARSE_FILTER, "cs": "1"},
        )

    async def validate_token(self) -> bool:
        """测试并验证当前 Token 是否有效 (通过尝试拉取设备列表).

        Returns:
            True 表示凭据有效，False 表示已失效
        """
        try:
            await self.get_devices()
            return True
        except BroadAirAuthError:
            return False
        except BroadAirApiError:
            # 其他非认证异常 (如暂时网络波动) 不视为 Token 失效
            return True
