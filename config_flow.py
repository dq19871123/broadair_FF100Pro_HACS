"""Config flow for Broad Fresh Air integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .api import async_login, BroadAirApiClient, BroadAirApiError, BroadAirAuthError
from .const import (
    CONF_ACCOUNT,
    CONF_DEVICE_ID,
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    DEVICE_FIELD_ID,
    DEVICE_FIELD_MAC,
    DEVICE_FIELD_MODEL,
    DEVICE_FIELD_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCOUNT): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_credentials(
    hass: HomeAssistant, account: str, password: str
) -> tuple[str, list[dict[str, Any]]]:
    """Validate credentials and return token and devices.

    Args:
        hass: Home Assistant instance
        account: Phone number
        password: Password

    Returns:
        Tuple of (session_token, devices_list)

    Raises:
        BroadAirAuthError: If login fails
        BroadAirApiError: If connection fails
    """
    # Login to get token
    login_data = await async_login(account, password)
    token = login_data.get("Token")

    if not token:
        raise BroadAirAuthError("Login succeeded but no token returned")

    # Get devices using the new token
    client = BroadAirApiClient(token, account=account, password=password)
    try:
        devices = await client.get_devices()
    finally:
        await client.close()

    return token, devices


class BroadAirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Broad Fresh Air."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._account: str | None = None
        self._password: str | None = None
        self._token: str | None = None
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - credentials input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input[CONF_ACCOUNT].strip()
            password = user_input[CONF_PASSWORD]

            try:
                token, devices = await validate_credentials(
                    self.hass, account, password
                )

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    self._account = account
                    self._password = password
                    self._token = token
                    self._devices = devices
                    return await self.async_step_device()

            except BroadAirAuthError as err:
                _LOGGER.error("Authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except BroadAirApiError as err:
                _LOGGER.error("Connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during login")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device selection step."""
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]

            # Find selected device
            device = next(
                (d for d in self._devices if d[DEVICE_FIELD_ID] == device_id),
                None,
            )

            if device is None:
                return self.async_abort(reason="device_not_found")

            # Check if already configured
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            device_name = device.get(DEVICE_FIELD_NAME, "Broad Fresh Air")

            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_ACCOUNT: self._account,
                    CONF_PASSWORD: self._password,
                    CONF_TOKEN: self._token,
                    CONF_DEVICE_ID: device_id,
                    CONF_DEVICE_NAME: device_name,
                    CONF_DEVICE_MAC: device.get(DEVICE_FIELD_MAC, ""),
                    CONF_DEVICE_MODEL: device.get(DEVICE_FIELD_MODEL, "FF100-Pro"),
                },
            )

        # Build device options for selection
        device_options = {
            d[DEVICE_FIELD_ID]: (
                f"{d.get(DEVICE_FIELD_NAME, 'Unknown')} "
                f"({d.get(DEVICE_FIELD_MODEL, 'Unknown Model')})"
            )
            for d in self._devices
        }

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): vol.In(device_options),
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication when token expires."""
        self._account = entry_data.get(CONF_ACCOUNT)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            account = user_input.get(CONF_ACCOUNT, self._account)
            password = user_input[CONF_PASSWORD]

            try:
                token, devices = await validate_credentials(
                    self.hass, account, password
                )

                if not devices:
                    errors["base"] = "no_devices"
                else:
                    # Update the existing entry
                    existing_entry = self.hass.config_entries.async_get_entry(
                        self.context["entry_id"]
                    )
                    if existing_entry:
                        self.hass.config_entries.async_update_entry(
                            existing_entry,
                            data={
                                **existing_entry.data,
                                CONF_ACCOUNT: account,
                                CONF_PASSWORD: password,
                                CONF_TOKEN: token,
                            },
                        )
                        await self.hass.config_entries.async_reload(
                            existing_entry.entry_id
                        )
                        return self.async_abort(reason="reauth_successful")

            except BroadAirAuthError:
                errors["base"] = "invalid_auth"
            except BroadAirApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during re-authentication")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT, default=self._account): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
