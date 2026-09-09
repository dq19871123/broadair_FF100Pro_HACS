"""按钮实体平台 - 远大新风肺保 (FF100-Pro).

本模块将远大滤网计时重置功能映射为 Home Assistant Button 实体：
- 重置高效 HEPA 滤芯使用时间 (Reset HEPA Filter Button, sjx: 8, cs: "1")
- 重置粗效/初效滤网使用时间 (Reset Primary Filter Button, sjx: 9, cs: "1")
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """初始化并注册滤网清零相关的 Button 实体."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        BroadAirResetHEPAFilterButton(coordinator, entry),
        BroadAirResetCoarseFilterButton(coordinator, entry),
    ])


class BroadAirResetHEPAFilterButton(CoordinatorEntity[BroadAirCoordinator], ButtonEntity):
    """高效 HEPA 滤芯计时清零按钮实体 (用户更换新滤芯后点击)."""

    _attr_has_entity_name = True
    _attr_translation_key = "reset_hepa_filter"
    _attr_name = "重置HEPA高效滤芯计时"
    _attr_icon = "mdi:air-filter"
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """初始化按钮实体."""
        super().__init__(coordinator)

        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_reset_hepa_filter"

        # 关联至主设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    async def async_press(self) -> None:
        """点击按钮事件处理：向云端下发 HEPA 滤网清零指令 (sjx: 8, cs: 1)."""
        _LOGGER.info("正在下发高效 HEPA 滤芯计时清零指令: 设备 ID=%s", self._device_id)
        await self.coordinator.client.reset_hepa_filter(self._device_id)
        await self.coordinator.async_request_refresh()


class BroadAirResetCoarseFilterButton(CoordinatorEntity[BroadAirCoordinator], ButtonEntity):
    """初效/粗效滤网计时清零按钮实体 (用户清洗滤网后点击)."""

    _attr_has_entity_name = True
    _attr_translation_key = "reset_coarse_filter"
    _attr_name = "重置粗效滤网计时"
    _attr_icon = "mdi:air-filter"
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """初始化按钮实体."""
        super().__init__(coordinator)

        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_reset_coarse_filter"

        # 关联至主设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    async def async_press(self) -> None:
        """点击按钮事件处理：向云端下发粗效滤网计时清零指令 (sjx: 9, cs: 1)."""
        _LOGGER.info("正在下发粗效滤网计时清零指令: 设备 ID=%s", self._device_id)
        await self.coordinator.client.reset_coarse_filter(self._device_id)
        await self.coordinator.async_request_refresh()
