"""开关实体平台 - 远大新风肺保 (FF100-Pro).

本模块将远大新风肺保的功能模式开关映射为 Home Assistant Switch 实体：
- 睡眠模式开关 (Sleep Mode Switch, sjx: 5)
- 自动调节模式开关 (Auto Mode Switch, sjx: 18)
- 室内净化/循环模式开关 (Indoor Purification Switch, sjx: 19)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    FIELD_AUTO_MODE,
    FIELD_SLEEP_MODE,
    FIELD_SUPPLY_AIR_CONFIG,
    FIELD_SUPPLY_AIR_MODE,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BroadAirSwitchEntityDescription(SwitchEntityDescription):
    """扩展的开关实体描述结构体，包含状态读取字段与控制回调函数."""

    field: str = ""
    turn_on_fn: Callable[[BroadAirCoordinator, str], Coroutine[Any, Any, Any]] | None = None
    turn_off_fn: Callable[[BroadAirCoordinator, str], Coroutine[Any, Any, Any]] | None = None
    available_fn: Callable[[dict[str, Any]], bool] | None = None


# -----------------------------------------------------------------------------
# 开关实体定义列表
# -----------------------------------------------------------------------------
SWITCH_DESCRIPTIONS: tuple[BroadAirSwitchEntityDescription, ...] = (
    # 1. 睡眠模式开关 (开启后风机以超低静音转速运行)
    BroadAirSwitchEntityDescription(
        key="sleep_mode",
        name="Sleep Mode",
        icon="mdi:sleep",
        device_class=SwitchDeviceClass.SWITCH,
        field=FIELD_SLEEP_MODE,
        turn_on_fn=lambda coord, dev_id: coord.client.set_sleep_mode(dev_id, True),
        turn_off_fn=lambda coord, dev_id: coord.client.set_sleep_mode(dev_id, False),
    ),
    # 2. 自动调节模式开关 (根据粉尘与 CO2 浓度自动切换档位)
    BroadAirSwitchEntityDescription(
        key="auto_mode",
        name="Auto Mode",
        icon="mdi:fan-auto",
        device_class=SwitchDeviceClass.SWITCH,
        field=FIELD_AUTO_MODE,
        turn_on_fn=lambda coord, dev_id: coord.client.set_auto_mode(dev_id, True),
        turn_off_fn=lambda coord, dev_id: coord.client.set_auto_mode(dev_id, False),
    ),
    # 3. 室内净化模式开关 (切换为室内空气循环净化，仅在硬件支持该功能时可用)
    BroadAirSwitchEntityDescription(
        key="indoor_purification",
        name="Indoor Purification",
        icon="mdi:air-filter",
        device_class=SwitchDeviceClass.SWITCH,
        field=FIELD_SUPPLY_AIR_MODE,
        available_fn=lambda data: str(data.get(FIELD_SUPPLY_AIR_CONFIG, "0")) == "1",
        turn_on_fn=lambda coord, dev_id: coord.client.set_indoor_purification(dev_id, True),
        turn_off_fn=lambda coord, dev_id: coord.client.set_indoor_purification(dev_id, False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置列表异步注册 Switch 实体."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BroadAirGenericSwitch(coordinator, entry, description)
        for description in SWITCH_DESCRIPTIONS
    ]

    async_add_entities(entities)


class BroadAirGenericSwitch(CoordinatorEntity[BroadAirCoordinator], SwitchEntity):
    """远大模式控制通用开关实体实现类."""

    _attr_has_entity_name = True
    entity_description: BroadAirSwitchEntityDescription

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
        description: BroadAirSwitchEntityDescription,
    ) -> None:
        """初始化开关实体.

        Args:
            coordinator: 数据更新协调器
            entry: 配置条目
            description: 开关元数据描述
        """
        super().__init__(coordinator)

        self.entity_description = description
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_{description.key}"

        # 关联至主设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    @property
    def available(self) -> bool:
        """判断当前开关实体是否可用 (协调器数据正常且满足可用性条件)."""
        if not super().available or self.coordinator.data is None:
            return False

        if self.entity_description.available_fn:
            return self.entity_description.available_fn(self.coordinator.data)

        return True

    @property
    def is_on(self) -> bool | None:
        """读取当前开关状态 ("1" 为开启，"0" 为关闭)."""
        if self.coordinator.data is None:
            return None
        return str(self.coordinator.data.get(self.entity_description.field, "0")) == "1"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """执行打开开关动作并立即刷新状态."""
        if self.entity_description.turn_on_fn:
            await self.entity_description.turn_on_fn(self.coordinator, self._device_id)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """执行关闭开关动作并立即刷新状态."""
        if self.entity_description.turn_off_fn:
            await self.entity_description.turn_off_fn(self.coordinator, self._device_id)
            await self.coordinator.async_request_refresh()
