"""数据更新协调器 - 远大新风肺保 (FF100-Pro).

本模块通过 Home Assistant 的 DataUpdateCoordinator 机制，集中管理向远大云端轮询数据的生命周期：
- 周期性调用 API 接口同步设备最新状态 (开关、档位、风量、传感器、耗材)
- 捕获鉴权失败异常并抛出 ConfigEntryAuthFailed 以触发 HA 原生重新认证流程
- 统一分发状态给所有关联的 Fan、Sensor、Switch 和 Button 实体
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BroadAirApiClient, BroadAirApiError, BroadAirAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class BroadAirCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """远大新风肺保数据更新协调器."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: BroadAirApiClient,
        device_id: str,
        device_name: str,
    ) -> None:
        """初始化数据更新协调器.

        Args:
            hass: Home Assistant 核心实例
            client: 远大 API 客户端对象
            device_id: 远大设备唯一标识 GUID (eq_guid)
            device_name: 设备名称 (用于日志标识)
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device_name}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.device_id = device_id
        self.device_name = device_name

    async def _async_update_data(self) -> dict[str, Any]:
        """向远大云端拉取设备最新状态数据.

        Returns:
            包含设备各项实时遥测与配置参数的字典

        Raises:
            ConfigEntryAuthFailed: 当会话失效且自动重新登录失败时抛出，通知 HA 弹出重新认证提示
            UpdateFailed: 当发生网络超时或云端接口异常时抛出
        """
        try:
            data = await self.client.get_status(self.device_id)
            _LOGGER.debug(
                "设备 [%s] 状态同步成功: 开关=%s, 设定档位=%s, 睡眠模式=%s, 出风量=%s m³/h",
                self.device_name,
                data.get("FB_ON"),
                data.get("GEAR_POSITION"),
                data.get("FB_SLEEPMODEL_ON"),
                data.get("AIR_VOLUME"),
            )
            return data
        except BroadAirAuthError as err:
            # 自动刷新 Token 失败后触发 HA 系统级重新认证流程
            raise ConfigEntryAuthFailed(
                f"设备 [{self.device_name}] 云端鉴权失败，请在集成配置中重新输入账号密码。"
            ) from err
        except BroadAirApiError as err:
            raise UpdateFailed(
                f"拉取设备 [{self.device_name}] 状态失败: {err}"
            ) from err
