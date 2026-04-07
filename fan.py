"""Fan platform for Broad Fresh Air."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    DOMAIN,
    FAN_SPEED_COUNT,
    FIELD_GEAR,
    FIELD_POWER,
    FIELD_RUNNING_GEAR,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)

# Preset modes for gear 1-3
PRESET_MODES = ["1", "2", "3"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Broad Fresh Air fan entity from config entry."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BroadAirFan(coordinator, entry)])


class BroadAirFan(CoordinatorEntity[BroadAirCoordinator], FanEntity):
    """Representation of a Broad Fresh Air fan."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name as entity name
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = FAN_SPEED_COUNT
    _attr_preset_modes = PRESET_MODES

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator)

        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_fan"

        # Device info for device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=entry.data.get(CONF_DEVICE_NAME, "Broad Fresh Air"),
            manufacturer="Broad",
            model=entry.data.get(CONF_DEVICE_MODEL, "FE6-Pro"),
        )

        # Add MAC address if available
        mac = entry.data.get(CONF_DEVICE_MAC)
        if mac:
            self._attr_device_info["connections"] = {("mac", mac)}

    @property
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(FIELD_POWER) == "1"

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode (gear 1-3)."""
        if self.coordinator.data is None:
            return None

        gear = self.coordinator.data.get(FIELD_GEAR) or self.coordinator.data.get(
            FIELD_RUNNING_GEAR
        )

        if gear and gear in PRESET_MODES:
            return gear

        return None

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0

        if self.coordinator.data is None:
            return None

        gear = self.coordinator.data.get(FIELD_GEAR) or self.coordinator.data.get(
            FIELD_RUNNING_GEAR
        )

        if gear is None:
            return None

        try:
            gear_int = int(gear)
            # Convert 1-6 to percentage ( 33,  67,  100)
            return round(gear_int * 100 / FAN_SPEED_COUNT)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid gear value: %s", gear)
            return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug(
            "Turning on fan %s (percentage=%s, preset_mode=%s)",
            self._device_id,
            percentage,
            preset_mode,
        )

        # Send power on command
        await self.coordinator.client.set_power(self._device_id, True)

        # If preset_mode specified, set the gear
        if preset_mode is not None and preset_mode in PRESET_MODES:
            speed = int(preset_mode)
            await self.coordinator.client.set_speed(self._device_id, speed)
        # If percentage specified, convert to gear and set
        elif percentage is not None and percentage > 0:
            speed = max(1, min(3, round(percentage * FAN_SPEED_COUNT / 100)))
            await self.coordinator.client.set_speed(self._device_id, speed)
        # Otherwise, device remembers its last gear, no need to set it

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        _LOGGER.debug("Turning off fan %s", self._device_id)

        await self.coordinator.client.set_power(self._device_id, False)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Setting fan %s percentage to %d", self._device_id, percentage)

        if percentage == 0:
            # Turn off when percentage is 0
            await self.async_turn_off()
            return

        # Convert percentage to gear 1-3
        speed = max(1, min(3, round(percentage * FAN_SPEED_COUNT / 100)))

        _LOGGER.debug("Converted percentage %d to gear %d", percentage, speed)

        # If fan is off, turn it on first
        if not self.is_on:
            await self.coordinator.client.set_power(self._device_id, True)

        await self.coordinator.client.set_speed(self._device_id, speed)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode (gear 1-3)."""
        _LOGGER.debug("Setting fan %s preset mode to %s", self._device_id, preset_mode)

        if preset_mode not in PRESET_MODES:
            _LOGGER.error("Invalid preset mode: %s", preset_mode)
            return

        speed = int(preset_mode)

        # If fan is off, turn it on first
        if not self.is_on:
            await self.coordinator.client.set_power(self._device_id, True)

        await self.coordinator.client.set_speed(self._device_id, speed)
        await self.coordinator.async_request_refresh()
