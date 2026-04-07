"""API client for Broad Fresh Air."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import ssl
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    APP_TOKEN,
    CMD_POLL,
    CMD_POWER_OFF,
    CMD_POWER_ON,
    CMD_RESET_COARSE_FILTER,
    CMD_RESET_HEPA_FILTER,
    CMD_SET_SPEED,
    CMD_SLEEP_MODE,
    ENDPOINT_CONTROL,
    ENDPOINT_DEVICES,
    ENDPOINT_LOGIN,
)

_LOGGER = logging.getLogger(__name__)


class BroadAirApiError(Exception):
    """Base exception for BroadAir API errors."""


class BroadAirAuthError(BroadAirApiError):
    """Authentication error - token invalid or expired."""


class BroadAirConnectionError(BroadAirApiError):
    """Connection error."""


def _md5(s: str) -> str:
    """Calculate MD5 hash of string."""
    return hashlib.md5(s.encode()).hexdigest()


def _generate_nonce() -> str:
    """Generate 6-digit random nonce."""
    return str(random.randint(100000, 999999))


def _generate_sign(nonce: str, timestamp: int) -> str:
    """
    Generate Sign using formula: MD5(AppToken + Nonce + Timestamp)
    """
    data = f"{APP_TOKEN}{nonce}{timestamp}"
    return _md5(data)


def _create_ssl_context() -> ssl.SSLContext:
    """Create SSL context that accepts self-signed certificates."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


async def async_login(
    account: str,
    password: str,
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """
    Login to Broad Fresh Air API.

    Args:
        account: Phone number
        password: Password
        session: Optional aiohttp session

    Returns:
        Login response data including session token

    Raises:
        BroadAirAuthError: If login fails
        BroadAirConnectionError: If connection fails
    """
    timestamp = int(time.time())
    nonce = _generate_nonce()
    sign = _generate_sign(nonce, timestamp)

    headers = {
        "Content-Type": "application/json",
        "language": "cn",
        "token": "1",  # "1" for login requests
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Html5Plus/1.0 uni-app",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    payload = {
        "Token": APP_TOKEN,
        "Timestamp": timestamp,
        "Sign": sign,
        "Nonce": nonce,
        "Account": account,
        "Password": password,
    }

    url = f"{API_BASE_URL}{ENDPOINT_LOGIN}"
    _LOGGER.debug("Login request to %s for account %s", url, account)

    own_session = session is None
    if own_session:
        connector = aiohttp.TCPConnector(ssl=_create_ssl_context())
        session = aiohttp.ClientSession(connector=connector)

    try:
        async with asyncio.timeout(30):
            async with session.post(url, json=payload, headers=headers, ssl=_create_ssl_context()) as resp:
                result = await resp.json()

                _LOGGER.debug("Login response code: %s", result.get("Code"))

                code = result.get("Code")
                if code != 200:
                    msg = result.get("Message", "Unknown error")
                    raise BroadAirAuthError(f"Login failed (code {code}): {msg}")

                return result.get("Data", {})

    except asyncio.TimeoutError as err:
        raise BroadAirConnectionError("Login request timeout") from err
    except aiohttp.ClientError as err:
        raise BroadAirConnectionError(f"Connection error: {err}") from err
    finally:
        if own_session and session:
            await session.close()


class BroadAirApiClient:
    """API client for Broad Fresh Air units."""

    def __init__(
        self,
        token: str,
        session: aiohttp.ClientSession | None = None,
        account: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            token: Session token from Data.Token after login
            session: Optional aiohttp session (recommended to use HA's session)
            account: Optional account for re-authentication
            password: Optional password for re-authentication
        """
        self._token = token
        self._session = session
        self._own_session = session is None
        self._account = account
        self._password = password
        self._ssl_context = _create_ssl_context()

    @property
    def token(self) -> str:
        """Return current token."""
        return self._token

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            connector = aiohttp.TCPConnector(ssl=self._ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        """Close the session if we created it."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    def _headers(self) -> dict[str, str]:
        """Build request headers."""
        return {
            "Content-Type": "application/json",
            "language": "en",
            "token": self._token,
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Connection": "keep-alive",
        }

    async def _request(
        self,
        endpoint: str,
        data: dict[str, Any],
        timeout: int = 30,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        """Make API request.

        Args:
            endpoint: API endpoint path
            data: Request body data
            timeout: Request timeout in seconds
            retry_auth: Whether to retry with token refresh on auth failure

        Returns:
            Response Data field

        Raises:
            BroadAirAuthError: If authentication fails
            BroadAirConnectionError: If connection fails
            BroadAirApiError: For other API errors
        """
        session = await self._get_session()
        url = f"{API_BASE_URL}{endpoint}"

        _LOGGER.debug("API request to %s: %s", endpoint, data)

        try:
            async with asyncio.timeout(timeout):
                async with session.post(
                    url,
                    json=data,
                    headers=self._headers(),
                    ssl=self._ssl_context,
                ) as resp:
                    result = await resp.json()

                    _LOGGER.debug("API response: %s", result)

                    code = result.get("Code")
                    if code != 200:
                        msg = result.get("Message", result.get("Msg", "Unknown error"))
                        
                        # Check if it's an auth error (code 800 = token验证失败)
                        is_auth_error = (
                            code in (401, 403, 800, 10001) or 
                            "token" in msg.lower() or 
                            "验证失败" in msg
                        )
                        
                        if is_auth_error:
                            # Try to refresh token if we have credentials and haven't retried yet
                            if retry_auth and self._account and self._password:
                                _LOGGER.info("Token expired (code %s: %s), attempting to refresh...", code, msg)
                                try:
                                    await self.refresh_token()
                                    _LOGGER.info("Token refreshed successfully, retrying request")
                                    # Retry the request with new token (but don't retry auth again)
                                    return await self._request(endpoint, data, timeout, retry_auth=False)
                                except BroadAirAuthError as refresh_err:
                                    _LOGGER.error("Token refresh failed: %s", refresh_err)
                                    raise BroadAirAuthError(
                                        f"Authentication failed and token refresh failed: {msg}"
                                    ) from refresh_err
                            
                            raise BroadAirAuthError(
                                f"Authentication failed (code {code}): {msg}"
                            )
                        raise BroadAirApiError(f"API error {code}: {msg}")

                    return result.get("Data", {})

        except asyncio.TimeoutError as err:
            raise BroadAirConnectionError(f"Request timeout: {url}") from err
        except aiohttp.ClientError as err:
            raise BroadAirConnectionError(f"Connection error: {err}") from err

    async def refresh_token(self) -> str:
        """Refresh the session token by re-authenticating.

        Returns:
            New session token

        Raises:
            BroadAirAuthError: If credentials are not available or login fails
        """
        if not self._account or not self._password:
            raise BroadAirAuthError("Cannot refresh token: credentials not available")

        _LOGGER.info("Refreshing token for account %s", self._account)

        login_data = await async_login(self._account, self._password, self._session)
        self._token = login_data.get("Token", "")

        if not self._token:
            raise BroadAirAuthError("Login succeeded but no token returned")

        return self._token

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices.

        Returns:
            List of device dictionaries with ID, MAC, Name, EquipmentMode, Online
        """
        result = await self._request(ENDPOINT_DEVICES, {"GroupName": ""})
        if isinstance(result, list):
            return result
        return []

    async def get_status(self, device_id: str) -> dict[str, Any]:
        """Get device status.

        Args:
            device_id: Device GUID (eq_guid)

        Returns:
            Status dictionary with FB_ON, GEAR_POSITION, AIR_VOLUME, etc.
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_POLL, "cs": ""},
        )

    async def set_power(self, device_id: str, on: bool) -> dict[str, Any]:
        """Set device power state.

        Args:
            device_id: Device GUID
            on: True to power on, False to power off

        Returns:
            Updated status dictionary
        """
        cmd = CMD_POWER_ON if on else CMD_POWER_OFF
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": cmd, "cs": ""},
        )

    async def set_speed(self, device_id: str, speed: int) -> dict[str, Any]:
        """Set fan speed.

        Args:
            device_id: Device GUID
            speed: Speed level 1-3

        Returns:
            Updated status dictionary

        Raises:
            ValueError: If speed is not between 1 and 3
        """
        if not 1 <= speed <= 3:
            raise ValueError(f"Speed must be between 1 and 3, got {speed}")
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_SET_SPEED, "cs": str(speed)},
        )

    async def set_sleep_mode(self, device_id: str, on: bool) -> dict[str, Any]:
        """Set sleep mode.

        Args:
            device_id: Device GUID
            on: True to enable sleep mode, False to disable

        Returns:
            Updated status dictionary
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_SLEEP_MODE, "cs": "1" if on else "0"},
        )

    async def reset_hepa_filter(self, device_id: str) -> dict[str, Any]:
        """Reset HEPA filter used time counter.

        Args:
            device_id: Device GUID

        Returns:
            Updated status dictionary
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_RESET_HEPA_FILTER, "cs": "1"},
        )

    async def reset_coarse_filter(self, device_id: str) -> dict[str, Any]:
        """Reset coarse/primary filter used time counter.

        Args:
            device_id: Device GUID

        Returns:
            Updated status dictionary
        """
        return await self._request(
            ENDPOINT_CONTROL,
            {"eq_guid": device_id, "sjx": CMD_RESET_COARSE_FILTER, "cs": "1"},
        )

    async def validate_token(self) -> bool:
        """Validate token by fetching devices.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            await self.get_devices()
            return True
        except BroadAirAuthError:
            return False
        except BroadAirApiError:
            # Other errors don't necessarily mean invalid token
            return True
