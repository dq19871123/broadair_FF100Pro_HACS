"""传感器平台 - 远大新风肺保 (FF100-Pro).

本模块负责将远大设备的遥测数据与滤网寿命映射为 Home Assistant Sensor 实体：
- 实时新风风量 (m³/h)
- 运行风速档位 (1~3 档，睡眠模式显示为 0 档)
- 滤网寿命监控 (高效 HEPA 剩余百分比与已用小时数、粗效初效剩余百分比与已用小时数、静电除尘器)
- 环境监测传感器 (PM2.5、CO2、室内温度 - 自动缩放除以 10)
- 设备故障诊断状态 (解析云端下发的 ALLFAULT 详细文本)
- 动态硬件选配件检测 (模块未安装或传感器异常时自动标记实体为不可用)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
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
    FIELD_CO2,
    FIELD_CO2_MODULE,
    FIELD_COARSE_USED_TIME,
    FIELD_DUSTER_CLEANING_CYCLE,
    FIELD_DUSTER_USED_TIME,
    FIELD_DUST_MODULE,
    FIELD_FAULT,
    FIELD_GEAR,
    FIELD_HEPA_LIFE_CYCLE,
    FIELD_HEPA_USED_TIME,
    FIELD_PM_2_5,
    FIELD_PM_2_5_DUST,
    FIELD_PRIMARY_CLEANING_CYCLE,
    FIELD_ROOM_TEMP,
    FIELD_RUNNING_GEAR,
    FIELD_SLEEP_MODE,
    FIELD_TEMP_MODULE,
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


def get_pm25_value(data: dict[str, Any]) -> int | None:
    """提取 PM2.5 浓度数值 (过滤 65535 离线哨兵值与故障状态)."""
    val = get_int_value(data, FIELD_PM_2_5_DUST)
    if val is None or val == 65535:
        val = get_int_value(data, FIELD_PM_2_5)
    if val is None or val == 65535:
        return None

    all_fault = str(data.get(FIELD_ALL_FAULT, ""))
    if "PM2.5故障" in all_fault:
        return None

    return val


def get_temperature_value(data: dict[str, Any]) -> float | None:
    """提取室内温度数值 (远大云端下发原始值为真实值的 10 倍，需除以 10.0)."""
    raw_val = get_int_value(data, FIELD_ROOM_TEMP)
    if raw_val is None:
        return None

    # 温度异常极值哨兵值过滤
    if raw_val in (65535, -9990, 9990):
        return None

    return round(raw_val / 10.0, 1)


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


def is_module_installed(data: dict[str, Any], module_field: str) -> bool:
    """检测设备是否安装了指定硬件传感器选配件 (1 为已安装，0 为未安装)."""
    return str(data.get(module_field, "0")) == "1"


def get_fault_status_text(data: dict[str, Any]) -> str:
    """解析设备当前故障状态文本."""
    all_fault = data.get(FIELD_ALL_FAULT)
    if all_fault and str(all_fault).strip() and str(all_fault) != "00":
        return str(all_fault)

    fault = data.get(FIELD_FAULT)
    if fault and str(fault) not in ("00", "0", ""):
        return f"Fault ({fault})"

    return "Normal"


# -----------------------------------------------------------------------------
# 传感器实体配置元数据定义
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
        attr_fn=lambda data: {
            "min_level": 1,
            "max_level": 3,
            "is_sleep_mode": str(data.get(FIELD_SLEEP_MODE)) == "1",
        },
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
    # 4. 高效 HEPA 滤芯剩余寿命百分比
    BroadAirSensorEntityDescription(
        key="hepa_filter_life",
        translation_key="hepa_filter_life",
        name="HEPA滤芯剩余寿命",
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
    # 5. 高效 HEPA 滤芯累计已用时长 (默认禁用，供高级用户启用)
    BroadAirSensorEntityDescription(
        key="hepa_filter_used",
        translation_key="hepa_filter_used",
        name="HEPA滤芯已用时间",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: get_int_value(data, FIELD_HEPA_USED_TIME),
        entity_registry_enabled_default=False,
    ),
    # 6. 初效/粗效滤网剩余寿命百分比
    BroadAirSensorEntityDescription(
        key="coarse_filter_life",
        translation_key="coarse_filter_life",
        name="粗效滤网剩余寿命",
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
    # 7. 初效/粗效滤网累计已用时长 (默认禁用)
    BroadAirSensorEntityDescription(
        key="coarse_filter_used",
        translation_key="coarse_filter_used",
        name="粗效滤网已用时间",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: get_int_value(data, FIELD_COARSE_USED_TIME),
        entity_registry_enabled_default=False,
    ),
    # 8. 静电除尘器寿命百分比 (若设备配置了除尘器则可用)
    BroadAirSensorEntityDescription(
        key="duster_filter_life",
        translation_key="duster_filter_life",
        name="静电除尘器寿命",
        icon="mdi:air-filter",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_filter_remaining_percentage(
            data, FIELD_DUSTER_USED_TIME, FIELD_DUSTER_CLEANING_CYCLE, 500
        ),
        available_fn=lambda data: bool(get_int_value(data, FIELD_DUSTER_CLEANING_CYCLE)),
        attr_fn=lambda data: {
            "used_hours": get_int_value(data, FIELD_DUSTER_USED_TIME),
            "total_hours": get_int_value(data, FIELD_DUSTER_CLEANING_CYCLE),
        },
        entity_registry_enabled_default=False,
    ),
    # 9. 二氧化碳浓度传感器 (仅在硬件安装了 CO2 模块时可用)
    BroadAirSensorEntityDescription(
        key="co2",
        translation_key="co2",
        name="二氧化碳浓度",
        icon="mdi:molecule-co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_int_value(data, FIELD_CO2),
        available_fn=lambda data: is_module_installed(data, FIELD_CO2_MODULE)
        and get_int_value(data, FIELD_CO2) is not None,
    ),
    # 10. PM2.5 粉尘浓度传感器 (仅在安装了粉尘模块、读数有效且无 PM2.5 故障时可用)
    BroadAirSensorEntityDescription(
        key="pm25",
        translation_key="pm25",
        name="PM2.5浓度",
        icon="mdi:blur",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=get_pm25_value,
        available_fn=lambda data: is_module_installed(data, FIELD_DUST_MODULE)
        and get_pm25_value(data) is not None,
        attr_fn=lambda data: {
            "quality_level": (
                "Good" if (get_pm25_value(data) or 0) <= 20
                else "Moderate" if (get_pm25_value(data) or 0) <= 50
                else "Poor"
            ) if get_pm25_value(data) is not None else "Unknown"
        },
    ),
    # 11. 室内温度传感器 (仅在安装了温度模块时可用，数值已做 0.1 缩放)
    BroadAirSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        name="室内温度",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=get_temperature_value,
        available_fn=lambda data: is_module_installed(data, FIELD_TEMP_MODULE)
        and get_temperature_value(data) is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """根据传感器描述列表批量注册 Sensor 实体.

    仅添加硬件实际支持且已安装的传感器实体；对于硬件未安装或不可用的选配传感器，
    若此前已存在于注册表中，则自动清理移除，避免在界面中显示为“不可用”。
    """
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    ent_reg = er.async_get(hass)

    # 获取当前配置条目下已在 Home Assistant 注册的 sensor 实体
    existing_entries = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.domain == "sensor"
    }

    device_id = entry.data[CONF_DEVICE_ID]
    entities: list[BroadAirSensor] = []

    for description in SENSOR_DESCRIPTIONS:
        unique_id = f"{device_id}_{description.key}"

        # 判断当前硬件是否支持/安装该传感器
        is_supported = True
        if description.available_fn and coordinator.data is not None:
            is_supported = description.available_fn(coordinator.data)

        if not is_supported:
            # 硬件未安装/不支持此传感器：如果之前注册过，自动从实体注册表中彻底移除
            if unique_id in existing_entries:
                entity_id = existing_entries[unique_id]
                _LOGGER.info(
                    "设备未安装或不支持传感器 [%s]，已自动从注册表清理: %s",
                    description.key,
                    entity_id,
                )
                ent_reg.async_remove(entity_id)
            continue

        entities.append(BroadAirSensor(coordinator, entry, description))

    async_add_entities(entities)


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
        """判断当前实体是否可用 (协调器数据正常且通过选配件判断)."""
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
        """提取扩展状态属性 (如空气质量等级、滤网额定总时长等)."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)

        return None

    @property
    def icon(self) -> str | None:
        """根据当前状态动态切换图标 (如故障警告图标、滤网告警图标)."""
        # 故障状态告警图标动态变化
        if self.entity_description.key == "fault_status" and self.coordinator.data:
            fault_text = get_fault_status_text(self.coordinator.data)
            if fault_text != "Normal":
                return "mdi:alert-circle"
            return "mdi:check-circle-outline"

        # 滤网剩余寿命严重偏低时切换为警示图标
        if "filter_life" in self.entity_description.key:
            value = self.native_value
            if isinstance(value, (int, float)):
                if value <= 10:
                    return "mdi:air-filter-off"
                elif value <= 30:
                    return "mdi:air-filter"

        return self.entity_description.icon
