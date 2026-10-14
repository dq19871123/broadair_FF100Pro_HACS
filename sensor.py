"""传感器平台 - 远大新风肺保 (FF100-Pro).

本模块负责将远大设备的遥测数据与滤芯寿命映射为 Home Assistant Sensor 实体：
- 实时新风风量 (m³/h)
- 运行风速档位 (1~3 档，睡眠模式显示为 0 档)
- 设备故障诊断状态 (解析云端下发的 ALLFAULT 详细文本)
- 滤芯寿命监控 (HEPA高效滤芯剩余百分比与已用小时数、粗效滤芯剩余百分比与已用小时数)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DEFAULT_HEPA_FILTER_LIFE,
    DEFAULT_PRIMARY_FILTER_LIFE,
    DOMAIN,
    FIELD_AIR_VOLUME,
    FIELD_ALL_FAULT,
    FIELD_COARSE_USED_TIME,
    FIELD_FAULT,
    FIELD_GEAR,
    FIELD_HEPA_LIFE_CYCLE,
    FIELD_HEPA_USED_TIME,
    FIELD_POWER,
    FIELD_PRIMARY_CLEANING_CYCLE,
    FIELD_RUNNING_GEAR,
    FIELD_SLEEP_MODE,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BroadAirSensorEntityDescription(SensorEntityDescription):
    """扩展的传感器实体描述结构体."""

    value_fn: Callable[[dict[str, Any]], str | int | float | None] | None = None
    available_fn: Callable[[dict[str, Any]], bool] | None = None
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


# -----------------------------------------------------------------------------
# 数据解析与换算辅助函数
# -----------------------------------------------------------------------------
def get_int_value(data: dict[str, Any], field: str) -> int | None:
    """安全解析整型字段值，若字段缺失或非数字则返回 None."""
    val = data.get(field)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def get_filter_remaining_percentage(
    data: dict[str, Any],
    used_field: str,
    total_field: str,
    default_total: int,
) -> int:
    """计算滤芯剩余寿命百分比 (0~100%)."""
    used = get_int_value(data, used_field) or 0
    total = get_int_value(data, total_field) or default_total

    if default_total == DEFAULT_PRIMARY_FILTER_LIFE and total < 168:
        total = DEFAULT_PRIMARY_FILTER_LIFE
    elif default_total == DEFAULT_HEPA_FILTER_LIFE and total < 2000:
        total = DEFAULT_HEPA_FILTER_LIFE

    used_pct = (used / total) * 100.0
    return max(0, min(100, int(round(100.0 - used_pct))))


def get_fault_status_text(data: dict[str, Any]) -> str:
    """解析设备当前故障状态文本."""
    all_fault = data.get(FIELD_ALL_FAULT)
    if all_fault and str(all_fault).strip() and str(all_fault) != "00":
        return str(all_fault)

    fault = data.get(FIELD_FAULT)
    if fault and str(fault) not in ("00", "0", ""):
        return f"Fault ({fault})"

    return "Normal"


def get_speed_level_attributes(data: dict[str, Any]) -> dict[str, Any]:
    """生成风速档位的扩展属性 (含指示灯颜色、浅绿呼吸标记与色块显示)."""
    is_sleep = str(data.get(FIELD_SLEEP_MODE)) == "1"
    power = str(data.get(FIELD_POWER)) == "1"
    gear = get_int_value(data, FIELD_GEAR) or get_int_value(data, FIELD_RUNNING_GEAR) or 0

    attrs: dict[str, Any] = {
        "min_level": 1,
        "max_level": 3,
        "is_sleep_mode": is_sleep,
    }

    if not power:
        attrs.update({
            "indicator_color": "off",
            "indicator_mode": "off",
            "indicator_color_hex": "#9E9E9E",
            "gear_display": "关机",
        })
        return attrs

    if is_sleep:
        attrs.update({
            "indicator_color": "light_green",
            "indicator_mode": "breathing",
            "indicator_color_hex": "#69F0AE",
            "gear_display": "睡眠档 🟢 (浅绿·呼吸)",
        })
        return attrs

    color_map = {
        1: ("blue", "steady", "#2196F3", "1档 🔵"),
        2: ("green", "steady", "#4CAF50", "2档 🟢"),
        3: ("yellow", "steady", "#FFB300", "3档 🟡"),
    }
    color_info = color_map.get(gear, ("unknown", "unknown", "#9E9E9E", f"{gear}档"))
    attrs.update({
        "indicator_color": color_info[0],
        "indicator_mode": color_info[1],
        "indicator_color_hex": color_info[2],
        "gear_display": color_info[3],
    })
    return attrs


# -----------------------------------------------------------------------------
# 传感器实体配置元数据定义 (针对 FF100-Pro 原生支持的 7 个遥测项目)
# -----------------------------------------------------------------------------
SENSOR_DESCRIPTIONS: tuple[BroadAirSensorEntityDescription, ...] = (
    # 1. 实时新风出风量传感器
    BroadAirSensorEntityDescription(
        key="air_volume",
        translation_key="air_volume",
        name="实时风量",
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m³/h",
        suggested_display_precision=0,
        value_fn=lambda data: get_int_value(data, FIELD_AIR_VOLUME),
    ),
    # 2. 实时风速档位 (1~3 档，睡眠模式时显示为 0 档)
    BroadAirSensorEntityDescription(
        key="speed_level",
        translation_key="speed_level",
        name="风速档位",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: 0 if str(data.get(FIELD_SLEEP_MODE)) == "1" else (
            get_int_value(data, FIELD_GEAR) or get_int_value(data, FIELD_RUNNING_GEAR) or 0
        ),
        attr_fn=get_speed_level_attributes,
    ),
    # 3. 故障自检与诊断状态
    BroadAirSensorEntityDescription(
        key="fault_status",
        translation_key="fault_status",
        name="故障状态",
        icon="mdi:alert-circle-outline",
        value_fn=get_fault_status_text,
        attr_fn=lambda data: {
            "has_fault": get_fault_status_text(data) != "Normal",
            "fault_detail": data.get(FIELD_ALL_FAULT, ""),
        },
    ),
    # 4. HEPA高效滤芯剩余寿命百分比
    BroadAirSensorEntityDescription(
        key="hepa_filter_life",
        translation_key="hepa_filter_life",
        name="HEPA高效滤芯剩余寿命",
        icon="mdi:air-filter",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_filter_remaining_percentage(
            data, FIELD_HEPA_USED_TIME, FIELD_HEPA_LIFE_CYCLE, DEFAULT_HEPA_FILTER_LIFE
        ),
        attr_fn=lambda data: {
            "used_hours": get_int_value(data, FIELD_HEPA_USED_TIME),
            "total_hours": get_int_value(data, FIELD_HEPA_LIFE_CYCLE) or DEFAULT_HEPA_FILTER_LIFE,
        },
    ),
    # 5. HEPA高效滤芯累计已用时长 (默认禁用，供高级用户启用)
    BroadAirSensorEntityDescription(
        key="hepa_filter_used",
        translation_key="hepa_filter_used",
        name="HEPA高效滤芯已用时间",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: get_int_value(data, FIELD_HEPA_USED_TIME),
        entity_registry_enabled_default=False,
    ),
    # 6. 粗效滤芯剩余寿命百分比
    BroadAirSensorEntityDescription(
        key="coarse_filter_life",
        translation_key="coarse_filter_life",
        name="粗效滤芯剩余寿命",
        icon="mdi:air-filter",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_filter_remaining_percentage(
            data, FIELD_COARSE_USED_TIME, FIELD_PRIMARY_CLEANING_CYCLE, DEFAULT_PRIMARY_FILTER_LIFE
        ),
        attr_fn=lambda data: {
            "used_hours": get_int_value(data, FIELD_COARSE_USED_TIME),
            "total_hours": get_int_value(data, FIELD_PRIMARY_CLEANING_CYCLE) or DEFAULT_PRIMARY_FILTER_LIFE,
        },
    ),
    # 7. 粗效滤芯累计已用时长 (默认禁用)
    BroadAirSensorEntityDescription(
        key="coarse_filter_used",
        translation_key="coarse_filter_used",
        name="粗效滤芯已用时间",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: get_int_value(data, FIELD_COARSE_USED_TIME),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """注册 Sensor 实体并自动清理历史不支持的遗留传感器."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    ent_reg = er.async_get(hass)

    # 获取当前配置条目下已在 Home Assistant 注册的 sensor 实体
    existing_entries = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.domain == "sensor"
    }

    device_id = entry.data[CONF_DEVICE_ID]

    # 1. 自动清理此前版本遗留或 FF100-Pro 不支持的幽灵传感器实体 (静电除尘、CO2、PM2.5、温度)
    deprecated_unique_ids = {
        f"{device_id}_duster_filter_life",
        f"{device_id}_co2",
        f"{device_id}_pm25",
        f"{device_id}_temperature",
    }
    for dep_uid in deprecated_unique_ids:
        if dep_uid in existing_entries:
            entity_id = existing_entries[dep_uid]
            _LOGGER.info(
                "已自动从注册表清理 FF100-Pro 不支持的传感器: %s (%s)",
                dep_uid,
                entity_id,
            )
            ent_reg.async_remove(entity_id)

    # 2. 注册 FF100-Pro 实际支持的全部传感器实体
    async_add_entities(
        BroadAirSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class BroadAirSensor(CoordinatorEntity[BroadAirCoordinator], SensorEntity):
    """远大新风肺保传感器实体实现类."""

    _attr_has_entity_name = True
    entity_description: BroadAirSensorEntityDescription

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
        description: BroadAirSensorEntityDescription,
    ) -> None:
        """初始化传感器实体.

        Args:
            coordinator: 数据更新协调器
            entry: 配置条目
            description: 实体元数据描述
        """
        super().__init__(coordinator)

        self.entity_description = description
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_{description.key}"

        # 关联至同一个主设备
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    @property
    def available(self) -> bool:
        """判断当前实体是否可用 (协调器数据正常)."""
        if not super().available or self.coordinator.data is None:
            return False

        if self.entity_description.available_fn:
            return self.entity_description.available_fn(self.coordinator.data)

        return True

    @property
    def native_value(self) -> str | int | float | None:
        """计算并提取当前传感器的原生状态值."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator.data)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """提取扩展状态属性 (如空气质量等级、滤芯额定总时长等)."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)

        return None

    @property
    def icon(self) -> str | None:
        """根据当前状态动态切换图标 (如故障警告图标、滤芯告警图标)."""
        # 故障状态告警图标动态变化
        if self.entity_description.key == "fault_status" and self.coordinator.data:
            fault_text = get_fault_status_text(self.coordinator.data)
            if fault_text != "Normal":
                return "mdi:alert-circle"
            return "mdi:check-circle-outline"

        # 滤芯剩余寿命严重偏低时切换为警示图标
        if "filter_life" in self.entity_description.key:
            value = self.native_value
            if isinstance(value, (int, float)):
                if value <= 10:
                    return "mdi:air-filter-off"
                elif value <= 30:
                    return "mdi:air-filter"

        return self.entity_description.icon
