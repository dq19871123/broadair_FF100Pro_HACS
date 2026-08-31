"""集成入口模块 - 远大新风肺保 (Broad Fresh Air FF100-Pro).

本模块负责在 Home Assistant 启动时加载和初始化远大新风肺保集成：
- 初始化 API 客户端并执行开机 Token 有效性检查与自动续期
- 构建 DataUpdateCoordinator 数据同步协调器
- 派发并加载各平台实体 (Fan, Sensor, Binary Sensor, Switch, Button)
- 管理集成配置的卸载 (Unload) 与热重载 (Reload)
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import BroadAirApiClient, BroadAirAuthError, BroadAirConnectionError
from .const import (
    CONF_ACCOUNT,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    DOMAIN,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)

# 支持并需要初始化的 Home Assistant 实体平台列表
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """初始化并启动配置条目 (ConfigEntry).

    Args:
        hass: Home Assistant 核心实例
        entry: 当前集成的配置条目

    Returns:
        True 表示初始化成功

    Raises:
        ConfigEntryAuthFailed: 当认证彻底失败时触发重新认证向导
        ConfigEntryNotReady: 当网络暂时不通时触发 HA 自动重试
    """
    hass.data.setdefault(DOMAIN, {})

    account = entry.data.get(CONF_ACCOUNT)
    password = entry.data.get(CONF_PASSWORD)
    token = entry.data.get(CONF_TOKEN, "")

    # 1. 实例化 API 通信客户端
    client = BroadAirApiClient(
        token=token,
        session=None,  # 客户端自建 session 并配置专用非严格 SSL 上下文
        account=account,
        password=password,
    )

    # 2. 启动时主动校验一次 Token 连通性 (若失效且有账号密码则自动续期)
    try:
        is_valid = await client.validate_token()
        if not is_valid:
            if account and password:
                _LOGGER.info("启动时 Token 校验失败，尝试自动重新登录获取新 Token...")
                new_token = await client.refresh_token()
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_TOKEN: new_token},
                )
            else:
                raise ConfigEntryAuthFailed("当前会话 Token 已失效且未提供账号密码，请重新配置")
    except BroadAirAuthError as err:
        if account and password:
            try:
                _LOGGER.info("捕获认证异常 (%s)，尝试通过账号密码重新认证...", err)
                new_token = await client.refresh_token()
                hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_TOKEN: new_token},
                )
            except Exception as refresh_err:
                raise ConfigEntryAuthFailed(f"自动重新登录失败: {refresh_err}") from refresh_err
        else:
            raise ConfigEntryAuthFailed(str(err)) from err
    except BroadAirConnectionError as err:
        raise ConfigEntryNotReady(f"无法连接到远大云端服务器: {err}") from err

    # 3. 创建数据更新协调器 (负责周期性轮询与数据分发)
    device_id = entry.data.get(CONF_DEVICE_ID)
    if not device_id:
        raise ConfigEntryAuthFailed("配置条目中缺少 device_id，请删除并重新添加设备")

    device_name = entry.data.get(CONF_DEVICE_NAME, "Broad Fresh Air")

    coordinator = BroadAirCoordinator(
        hass=hass,
        client=client,
        device_id=device_id,
        device_name=device_name,
    )

    # 4. 执行首次数据拉取 (若失败将抛出异常并阻止后续实体初始化)
    await coordinator.async_config_entry_first_refresh()

    # 5. 将协调器存入 hass 运行时数据容器中，供各平台实体消费
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # 6. 向各实体平台派发加载任务 (fan, sensor, binary_sensor, switch, button)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 7. 注册配置项修改监听器 (当用户更改选项时自动重载集成)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info(
        "远大新风肺保集成已成功加载: 设备名称=%s, 设备 ID=%s",
        device_name,
        device_id,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载并清理配置条目.

    Args:
        hass: Home Assistant 核心实例
        entry: 需要卸载的配置条目

    Returns:
        True 表示卸载清理成功
    """
    # 1. 卸载各实体平台
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # 2. 从内存中清理该设备对应的协调器
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator and coordinator.client:
            await coordinator.client.close()
        _LOGGER.info(
            "远大新风肺保集成已卸载: %s",
            entry.data.get(CONF_DEVICE_NAME, entry.data.get(CONF_DEVICE_ID)),
        )

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """配置项变更时的重载回调函数."""
    await hass.config_entries.async_reload(entry.entry_id)
