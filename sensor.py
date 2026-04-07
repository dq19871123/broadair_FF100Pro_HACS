"""Sensor platform for Broad Fresh Air."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    FIELD_AIR_VOLUME,
    FIELD_CO2,
    FIELD_CO2_MODULE,
    FIELD_COARSE_USED_TIME,
    FIELD_DUST_MODULE,
    FIELD_FAULT,
    FIELD_GEAR,
    FIELD_HEPA_LIFE_CYCLE,
    FIELD_HEPA_USED_TIME,
    FIELD_PM_2_5,
    FIELD_PM_10,
    FIELD_ROOM_TEMP,
    FIELD_RUNNING_GEAR,
    FIELD_TEMP_MODULE,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)

# Known fault codes (expand as you discover more)
FAULT_CODES = {
    "00": "No Fault",
    "01": "Filter Replacement Required",
    # Add more fault codes as discovered
}


@dataclass(frozen=True)
class BroadAirSensorEntityDescription(SensorEntityDescription):
    """Describes a Broad Air sensor entity."""

    value_fn: Callable[[dict], str | int | float | None] | None = None
    available_fn: Callable[[dict], bool] | None = None
    attr_fn: Callable[[dict], dict] | None = None


def get_int_value(data: dict, field: str) -> int | None:
    """Get integer value from data."""
    value = data.get(field)
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def get_filter_percentage(data: dict, used_field: str, total_field: str) -> int | None:
    """Calculate filter remaining percentage."""
    used = get_int_value(data, used_field)
    total = get_int_value(data, total_field)
    if used is None or total is None or total == 0:
        return None
    remaining = max(0, 100 - (used * 100 // total))
    return remaining


def is_module_installed(data: dict, module_field: str) -> bool:
    """Check if a module is installed."""
    return data.get(module_field) == "1"


SENSOR_DESCRIPTIONS: tuple[BroadAirSensorEntityDescription, ...] = (
    # Core sensors (always available)
    BroadAirSensorEntityDescription(
        key="air_volume",
        name="Air Volume",
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="m³/h",
        suggested_display_precision=0,
        value_fn=lambda data: get_int_value(data, FIELD_AIR_VOLUME),
    ),
    BroadAirSensorEntityDescription(
        key="speed_level",
        name="Speed Level",
        icon="mdi:speedometer",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_int_value(data, FIELD_GEAR) or get_int_value(data, FIELD_RUNNING_GEAR),
        attr_fn=lambda data: {"min_level": 1, "max_level": 3},
    ),
    BroadAirSensorEntityDescription(
        key="fault_status",
        name="Fault Status",
        icon="mdi:alert-circle-outline",
        value_fn=lambda data: FAULT_CODES.get(data.get(FIELD_FAULT, "00"), f"Unknown ({data.get(FIELD_FAULT)})"),
        attr_fn=lambda data: {
            "fault_code": data.get(FIELD_FAULT, "00"),
            "has_fault": data.get(FIELD_FAULT, "00") != "00",
        },
    ),
    # Filter life sensors
    BroadAirSensorEntityDescription(
        key="hepa_filter_life",
        name="HEPA Filter Life",
        icon="mdi:air-filter",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_filter_percentage(data, FIELD_HEPA_USED_TIME, FIELD_HEPA_LIFE_CYCLE),
        attr_fn=lambda data: {
            "used_hours": get_int_value(data, FIELD_HEPA_USED_TIME),
            "total_hours": get_int_value(data, FIELD_HEPA_LIFE_CYCLE),
        },
    ),
    BroadAirSensorEntityDescription(
        key="hepa_filter_used",
        name="HEPA Filter Used Time",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: get_int_value(data, FIELD_HEPA_USED_TIME),
        entity_registry_enabled_default=False,  # Disabled by default, advanced users can enable
    ),
    BroadAirSensorEntityDescription(
        key="coarse_filter_used",
        name="Coarse Filter Used Time",
        icon="mdi:clock-outline",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: get_int_value(data, FIELD_COARSE_USED_TIME),
        entity_registry_enabled_default=False,
    ),
    # Air quality sensors (only if modules installed)
    BroadAirSensorEntityDescription(
        key="co2",
        name="CO2",
        icon="mdi:molecule-co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_int_value(data, FIELD_CO2),
        available_fn=lambda data: is_module_installed(data, FIELD_CO2_MODULE),
    ),
    BroadAirSensorEntityDescription(
        key="pm25",
        name="PM2.5",
        icon="mdi:blur",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_int_value(data, FIELD_PM_2_5),
        available_fn=lambda data: is_module_installed(data, FIELD_DUST_MODULE),
    ),
    BroadAirSensorEntityDescription(
        key="pm10",
        name="PM10",
        icon="mdi:blur",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement="µg/m³",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_int_value(data, FIELD_PM_10),
        available_fn=lambda data: is_module_installed(data, FIELD_DUST_MODULE),
    ),
    BroadAirSensorEntityDescription(
        key="temperature",
        name="Room Temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: get_int_value(data, FIELD_ROOM_TEMP),
        available_fn=lambda data: is_module_installed(data, FIELD_TEMP_MODULE),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Broad Fresh Air sensor entities from config entry."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        BroadAirSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class BroadAirSensor(CoordinatorEntity[BroadAirCoordinator], SensorEntity):
    """Representation of a Broad Fresh Air sensor."""

    _attr_has_entity_name = True
    entity_description: BroadAirSensorEntityDescription

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
        description: BroadAirSensorEntityDescription,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data update coordinator
            entry: Config entry
            description: Entity description
        """
        super().__init__(coordinator)

        self.entity_description = description
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_{description.key}"

        # Link to the same device as the fan
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False

        # Check module-specific availability
        if self.entity_description.available_fn and self.coordinator.data:
            return self.entity_description.available_fn(self.coordinator.data)

        return True

    @property
    def native_value(self) -> str | int | float | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator.data)

        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional state attributes."""
        if self.coordinator.data is None:
            return None

        if self.entity_description.attr_fn:
            return self.entity_description.attr_fn(self.coordinator.data)

        return None

    @property
    def icon(self) -> str | None:
        """Return dynamic icon based on state."""
        # Special handling for fault status icon
        if self.entity_description.key == "fault_status" and self.coordinator.data:
            fault_code = self.coordinator.data.get(FIELD_FAULT, "00")
            if fault_code != "00":
                return "mdi:alert-circle"
            return "mdi:check-circle-outline"

        # Special handling for filter life icon
        if self.entity_description.key == "hepa_filter_life":
            value = self.native_value
            if value is not None:
                if value <= 10:
                    return "mdi:air-filter-off"
                elif value <= 30:
                    return "mdi:air-filter"

        return self.entity_description.icon
