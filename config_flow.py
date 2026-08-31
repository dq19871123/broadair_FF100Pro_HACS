"""配置向导流程 - 远大新风肺保 (FF100-Pro).

本模块实现了 Home Assistant 的 Config Flow 配置向导：
- 用户输入手机号与密码进行云端登录认证
- 查询账号名下的远大设备列表供用户多选/单选绑定
- 防止重复添加相同设备 (基于 device_id 设置 Unique ID)
- 处理 Token 长期失效后的 Reauth 重新认证向导
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .api import async_login, BroadAirApiClient, BroadAirApiError, BroadAirAuthError
from .const import (
    CONF_ACCOUNT,
    CONF_DEVICE_ID,
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    DEVICE_FIELD_ID,
    DEVICE_FIELD_MAC,
    DEVICE_FIELD_MODEL,
    DEVICE_FIELD_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# 第一步：用户账号密码输入表单 Schema
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_credentials(
    hass: HomeAssistant, account: str, password: str
) -> tuple[str, list[dict[str, Any]]]:
    """验证用户凭据并拉取设备列表.

    Args:
        hass: Home Assistant 核心实例
        account: 手机号
        password: 登录密码

    Returns:
        包含 (会话 Token, 设备列表) 的元组

    Raises:
        BroadAirAuthError: 账号密码错误
        BroadAirApiError: 网络异常或无法获取设备
    """
    # 1. 执行登录获取 Token
    login_data = await async_login(account, password)
    token = login_data.get("Token")

    if not token:
        raise BroadAirAuthError("登录成功但返回的 Token 字段为空")

    # 2. 借助新获得的 Token 拉取设备列表
    client = BroadAirApiClient(token, account=account, password=password)
    try:
        devices = await client.get_devices()
    finally:
        await client.close()

    return token, devices


class BroadAirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """远大新风配置流控制器."""

    VERSION = 1

    def __init__(self) -> None:
        """初始化配置流状态变量."""
        self._account: str | None = None
        self._password: str | None = None
        self._token: str | None = None
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """配置向导第一步：接收并验证用户输入的账号与密码."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input[CONF_ACCOUNT].strip()
            password = user_input[CONF_PASSWORD]

            try:
                # 验证账号并拉取设备
                token, devices = await validate_credentials(
                    self.hass, account, password
                )

                if not devices:
                    # 账号下无可用设备
                    errors["base"] = "no_devices"
                else:
                    # 暂存凭据并进入设备选择步骤
                    self._account = account
                    self._password = password
                    self._token = token
                    self._devices = devices
                    return await self.async_step_device()

            except BroadAirAuthError as err:
                _LOGGER.error("远大账号认证失败: %s", err)
                errors["base"] = "invalid_auth"
            except BroadAirApiError as err:
                _LOGGER.error("连接远大云端服务器失败: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("配置向导发生未知异常")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """配置向导第二步：选择需要添加至 Home Assistant 的新风肺保设备."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]

            # 匹配所选设备的对象信息
            device = next(
                (d for d in self._devices if str(d.get(DEVICE_FIELD_ID)) == str(device_id)),
                None,
            )

            if device is None:
                return self.async_abort(reason="device_not_found")

            # 检查唯一 ID，防止同一个物理设备被重复添加
            await self.async_set_unique_id(str(device_id))
            self._abort_if_unique_id_configured()

            device_name = device.get(DEVICE_FIELD_NAME, "Broad Fresh Air")

            # 完成配置创建 ConfigEntry
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_ACCOUNT: self._account,
                    CONF_PASSWORD: self._password,
                    CONF_TOKEN: self._token,
                    CONF_DEVICE_ID: str(device_id),
                    CONF_DEVICE_NAME: device_name,
                    CONF_DEVICE_MAC: device.get(DEVICE_FIELD_MAC, ""),
                    CONF_DEVICE_MODEL: device.get(DEVICE_FIELD_MODEL, "FF100-Pro"),
                },
            )

        # 构造设备下拉选单选项 (名称 + 型号)
        device_options = {
            str(d[DEVICE_FIELD_ID]): (
                f"{d.get(DEVICE_FIELD_NAME, 'Broad Unit')} "
                f"({d.get(DEVICE_FIELD_MODEL, 'FF100-Pro')})"
            )
            for d in self._devices
            if d.get(DEVICE_FIELD_ID) is not None
        }

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): vol.In(device_options),
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """重新认证入口 (由 Coordinator 捕获认证异常后触发)."""
        self._account = entry_data.get(CONF_ACCOUNT)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """重新认证确认步骤：用户输入新密码后更新现有配置条目."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input.get(CONF_ACCOUNT, self._account)
            password = user_input[CONF_PASSWORD]

            try:
                # 重新验证凭据
                token, devices = await validate_credentials(
                    self.hass, account, password
                )

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    # 更新当前 Entry 中的 Token 与凭据信息并重新加载集成
                    existing_entry = self.hass.config_entries.async_get_entry(
                        self.context["entry_id"]
                    )
                    if existing_entry:
                        self.hass.config_entries.async_update_entry(
                            existing_entry,
                            data={
                                **existing_entry.data,
                                CONF_ACCOUNT: account,
                                CONF_PASSWORD: password,
                                CONF_TOKEN: token,
                            },
                        )
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")

            except BroadAirAuthError:
                errors["base"] = "invalid_auth"
            except BroadAirApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("重新认证流程发生异常")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT, default=self._account): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
