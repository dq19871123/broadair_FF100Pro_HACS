"""数值调节实体平台 - 远大新风肺保 (FF100-Pro).

本模块将远大滤芯寿命周期配置映射为 Home Assistant Number 实体：
- 设定粗效滤芯清洗周期 (Primary Filter Cleaning Cycle, sjx: 7, 168~2160 小时)
- 设定HEPA高效滤芯更换周期 (HEPA Filter Replacement Cycle, sjx: 6, 2000~10000 小时)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DEFAULT_HEPA_FILTER_LIFE,
    DEFAULT_PRIMARY_FILTER_LIFE,
    DOMAIN,
    FIELD_HEPA_LIFE_CYCLE,
    FIELD_PRIMARY_CLEANING_CYCLE,
    MAX_COARSE_FILTER_LIFE,
    MAX_HEPA_FILTER_LIFE,
    MIN_COARSE_FILTER_LIFE,
    MIN_HEPA_FILTER_LIFE,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BroadAirNumberEntityDescription(NumberEntityDescription):
    """扩展的数值实体描述结构体."""

    value_fn: Callable[[dict[str, Any]], float | None] | None = None
    set_value_fn: Callable[[BroadAirCoordinator, str, int], Coroutine[Any, Any, Any]] | None = None
    field: str = ""


def get_coarse_cycle_value(data: dict[str, Any]) -> float:
    """提取粗效滤芯清洗周期 (若无有效值则返回默认 500 小时)."""
    val = data.get(FIELD_PRIMARY_CLEANING_CYCLE)
    if val is not None and val != "":
        try:
            val_int = int(val)
            if MIN_COARSE_FILTER_LIFE <= val_int <= MAX_COARSE_FILTER_LIFE:
                return float(val_int)
        except (ValueError, TypeError):
            pass
    return float(DEFAULT_PRIMARY_FILTER_LIFE)


def get_hepa_cycle_value(data: dict[str, Any]) -> float:
    """提取HEPA高效滤芯更换周期 (若无有效值则返回默认 3000 小时)."""
    val = data.get(FIELD_HEPA_LIFE_CYCLE)
    if val is not None and val != "":
        try:
            val_int = int(val)
            if MIN_HEPA_FILTER_LIFE <= val_int <= MAX_HEPA_FILTER_LIFE:
                return float(val_int)
        except (ValueError, TypeError):
            pass
    return float(DEFAULT_HEPA_FILTER_LIFE)


NUMBER_DESCRIPTIONS: tuple[BroadAirNumberEntityDescription, ...] = (
    # 1. 粗效滤芯清洗周期设置 (168~2160 小时，对应 7~90 天，App 默认 500h/720h)
    BroadAirNumberEntityDescription(
        key="coarse_filter_cycle",
        translation_key="coarse_filter_cycle",
        name="粗效滤芯清洗周期",
        icon="mdi:filter-cog",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=MIN_COARSE_FILTER_LIFE,
        native_max_value=MAX_COARSE_FILTER_LIFE,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field=FIELD_PRIMARY_CLEANING_CYCLE,
        value_fn=get_coarse_cycle_value,
        set_value_fn=lambda coord, dev_id, val: coord.client.set_coarse_filter_cycle(dev_id, val),
    ),
    # 2. HEPA高效滤芯更换周期设置 (2000~10000 小时，App 默认 3000h)
    BroadAirNumberEntityDescription(
        key="hepa_filter_cycle",
        translation_key="hepa_filter_cycle",
        name="HEPA高效滤芯更换周期",
        icon="mdi:filter-cog",
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        native_min_value=MIN_HEPA_FILTER_LIFE,
        native_max_value=MAX_HEPA_FILTER_LIFE,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
        field=FIELD_HEPA_LIFE_CYCLE,
        value_fn=get_hepa_cycle_value,
        set_value_fn=lambda coord, dev_id, val: coord.client.set_hepa_filter_cycle(dev_id, val),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置列表异步注册 Number 实体."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        BroadAirNumberEntity(coordinator, entry, description)
        for description in NUMBER_DESCRIPTIONS
    )


class BroadAirNumberEntity(CoordinatorEntity[BroadAirCoordinator], NumberEntity):
    """远大新风肺保数值配置实体实现类."""

    _attr_has_entity_name = True
    entity_description: BroadAirNumberEntityDescription

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
        description: BroadAirNumberEntityDescription,
    ) -> None:
        """初始化数值调节实体.

        Args:
            coordinator: 数据更新协调器
            entry: 配置条目
            description: 数值实体元数据描述
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
    def native_value(self) -> float | None:
        """获取当前配置数值 (小时)."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator.data)

        return None

    async def async_set_native_value(self, value: float) -> None:
        """设定新数值并同步到云端."""
        int_val = int(round(value))
        _LOGGER.info(
            "正在设置 %s: 设备 ID=%s, 目标值=%d 小时",
            self.entity_description.name,
            self._device_id,
            int_val,
        )
        if self.entity_description.set_value_fn:
            await self.entity_description.set_value_fn(self.coordinator, self._device_id, int_val)
            # 乐观更新本地协调器数据缓存，避免云端同步延迟导致界面跳变
            if self.coordinator.data is not None and self.entity_description.field:
                self.coordinator.data[self.entity_description.field] = int_val
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
