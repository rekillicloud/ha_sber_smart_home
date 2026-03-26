"""API client for Sber Smart Home."""
import asyncio
import logging
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
from aiohttp import ClientSession

from .const import (
    COMPANION_TOKEN_URL,
    DEFAULT_SSL_CERT_PATH,
    DEVICE_GROUPS_URL,
    DOMAIN,
    GATEWAY_API,
)

_LOGGER = logging.getLogger(__name__)


class SberSmartHomeApi:
    """Main API client for Sber Smart Home."""

    def __init__(self, session: ClientSession, access_token: str):
        """Initialize API client."""
        self._session = session
        self._access_token = access_token
        self._gateway_token: str | None = None
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_verify_flags = ssl.CERT_NONE
        self._ssl_context.load_verify_locations(str(DEFAULT_SSL_CERT_PATH))

    async def _request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request to Sber API."""
        default_headers = {
            "User-Agent": "Salute+prod%2F24.08.1.15602+(Android+34;Google+sdk_gphone64_arm64)",
        }
        if headers:
            default_headers.update(headers)

        try:
            async with self._session.request(
                method,
                url,
                headers=default_headers,
                json=json,
                params=params,
                ssl=self._ssl_context,
            ) as response:
                if response.status >= 400:
                    text = await response.text()
                    _LOGGER.error("API request failed: %s %s", response.status, text)
                    raise Exception(f"API error: {response.status}")
                
                return await response.json()
        except Exception as e:
            _LOGGER.error("Request error: %s", e)
            raise

    async def get_gateway_token(self) -> str | None:
        """Get gateway token for API access."""
        try:
            async with self._session.get(
                COMPANION_TOKEN_URL,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "User-Agent": "Salute+prod%2F24.08.1.15602+(Android+34;Google+sdk_gphone64_arm64)",
                },
                ssl=self._ssl_context,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._gateway_token = data.get("token")
                    return self._gateway_token
                else:
                    _LOGGER.error("Failed to get gateway token: %s", response.status)
        except Exception as e:
            _LOGGER.error("Gateway token error: %s", e)
        return None

    async def get_devices(self) -> dict[str, Any]:
        """Get all devices from Sber Smart Home."""
        if not self._gateway_token:
            await self.get_gateway_token()

        if not self._gateway_token:
            raise Exception("No gateway token available")

        try:
            async with self._session.get(
                DEVICE_GROUPS_URL,
                headers={
                    "X-AUTH-jwt": self._gateway_token,
                    "User-Agent": "Salute+prod%2F24.08.1.15602+(Android+34;Google+sdk_gphone64_arm64)",
                },
                ssl=self._ssl_context,
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    text = await response.text()
                    _LOGGER.error("Failed to get devices: %s %s", response.status, text)
                    raise Exception(f"Failed to get devices: {response.status}")
        except Exception as e:
            _LOGGER.error("Get devices error: %s", e)
            raise

    async def set_device_state(
        self, device_id: str, state: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Set device state."""
        if not self._gateway_token:
            await self.get_gateway_token()

        if not self._gateway_token:
            raise Exception("No gateway token available")

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        desired_state = []
        for item in state:
            key = item.get("key")
            value = item.get("value")
            attr_type = item.get("attr_type", "BOOL")

            state_item = {"key": key, "type": attr_type}

            if attr_type == "BOOL":
                state_item["bool_value"] = value
            elif attr_type == "INTEGER":
                state_item["integer_value"] = str(value)
            elif attr_type == "STRING":
                state_item["string_value"] = str(value)
            elif attr_type == "ENUM":
                state_item["enum_value"] = str(value)
            elif attr_type == "COLOR":
                state_item["color_value"] = value

            desired_state.append(state_item)

        return await self._request(
            "PUT",
            f"{GATEWAY_API}/devices/{device_id}/state",
            headers={"X-AUTH-jwt": self._gateway_token},
            json={
                "device_id": device_id,
                "desired_state": desired_state,
                "timestamp": timestamp,
            },
        )

    async def set_switch_state(self, device_id: str, is_on: bool) -> dict[str, Any]:
        """Set switch on/off state."""
        return await self.set_device_state(
            device_id, [{"key": "on_off", "value": is_on, "attr_type": "BOOL"}]
        )

    async def set_light_brightness(self, device_id: str, brightness: int) -> dict[str, Any]:
        """Set light brightness."""
        return await self.set_device_state(
            device_id,
            [{"key": "light_brightness", "value": brightness, "attr_type": "INTEGER"}],
        )

    async def set_light_color(self, device_id: str, rgb: list[int]) -> dict[str, Any]:
        """Set light color."""
        return await self.set_device_state(
            device_id,
            [{"key": "light_colour", "value": {"rgb": rgb}, "attr_type": "COLOR"}],
        )

    async def set_light_color_temp(self, device_id: str, color_temp: int) -> dict[str, Any]:
        """Set light color temperature."""
        return await self.set_device_state(
            device_id,
            [{"key": "light_colour_temp", "value": color_temp, "attr_type": "INTEGER"}],
        )
