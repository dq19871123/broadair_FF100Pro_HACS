"""二进制传感器平台 - 远大新风肺保 (FF100-Pro).

本模块将远大设备的布尔状态映射为 Home Assistant Binary Sensor 实体：
- 设备故障告警 (Problem Binary Sensor)
- 设备在线连接状态 (Connectivity Binary Sensor)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    FIELD_ALL_FAULT,
    FIELD_FAULT,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BroadAirBinarySensorEntityDescription(BinarySensorEntityDescription):
    """扩展的二进制传感器描述结构体."""

    is_on_fn: Callable[[dict[str, Any]], bool | None] | None = None
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def has_device_fault(data: dict[str, Any]) -> bool:
    """检测设备是否存在故障."""
    all_fault = data.get(FIELD_ALL_FAULT)
    if all_fault and str(all_fault).strip() and str(all_fault) != "00":
        return True

    fault = data.get(FIELD_FAULT)
    if fault and str(fault) not in ("00", "0", ""):
        return True

    return False


BINARY_SENSOR_DESCRIPTIONS: tuple[BroadAirBinarySensorEntityDescription, ...] = (
    # 1. 设备故障监测实体 (用于自动化告警)
    BroadAirBinarySensorEntityDescription(
        key="problem",
        translation_key="problem",
        name="故障报警",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=has_device_fault,
        attr_fn=lambda data: {
            "fault_detail": str(data.get(FIELD_ALL_FAULT, "")),
            "fault_code": str(data.get(FIELD_FAULT, "00")),
        },
    ),
    # 2. 设备在线状态实体
    BroadAirBinarySensorEntityDescription(
        key="connectivity",
        translation_key="connectivity",
        name="在线状态",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: str(data.get("Online", "1")) == "1",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置列表注册 Binary Sensor 实体."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BroadAirBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class BroadAirBinarySensor(CoordinatorEntity[BroadAirCoordinator], BinarySensorEntity):
    """远大新风肺保二进制传感器实体实现类."""

    _attr_has_entity_name = True
    entity_description: BroadAirBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
        description: BroadAirBinarySensorEntityDescription,
    ) -> None:
        """初始化二进制传感器实体."""
        super().__init__(coordinator)

        self.entity_description = description
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    @property
    def is_on(self) -> bool | None:
        """计算当前二进制状态 (True 为异常/在线)."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.is_on_fn:
            return self.entity_description.is_on_fn(self.coordinator.data)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """提取扩展属性."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)

        return None
