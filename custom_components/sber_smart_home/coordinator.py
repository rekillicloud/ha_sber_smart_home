"""Data coordinator for Sber Smart Home."""

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import SberSmartHomeApi
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SberSmartHomeCoordinator(DataUpdateCoordinator):
    """Sber Smart Home data coordinator."""

    def __init__(self, hass: HomeAssistant, entry):
        """Initialize coordinator."""
        self._entry = entry
        self._api: SberSmartHomeApi | None = None

        access_token = entry.data.get("access_token", "")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        if access_token:
            import aiohttp

            session = aiohttp.ClientSession()
            self._api = SberSmartHomeApi(session, access_token)

            self._entry.async_on_unload(
                self._entry.add_update_listener(self._async_update_listener)
            )

    async def _async_update_listener(self, hass: HomeAssistant, entry) -> None:
        """Handle config entry update."""
        self._api = None
        access_token = entry.data.get("access_token", "")
        if access_token:
            import aiohttp

            session = aiohttp.ClientSession()
            self._api = SberSmartHomeApi(session, access_token)

    @property
    def api(self) -> SberSmartHomeApi:
        """Return API client."""
        return self._api

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data from Sber Smart Home."""
        if not self._api:
            _LOGGER.error("API not initialized")
            return {"devices": []}

        try:
            devices_data = await self._api.get_devices()
            return devices_data
        except Exception as e:
            _LOGGER.error("Failed to update data: %s", e)
            raise

    def get_devices(self) -> list[dict[str, Any]]:
        """Get list of devices from last update."""
        if self.data and "result" in self.data:
            return self.data.get("result", {}).get("devices", [])
        return []

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        """Get specific device by ID."""
        for device in self.get_devices():
            if device.get("id") == device_id:
                return device
        return None

    def async_patch_device_state(self, device_id: str, states: list[dict]) -> None:
        """Update device state optimistically."""
        if not self.data or "result" not in self.data:
            return
        devices = self.data.get("result", {}).get("devices", [])
        for device in devices:
            if device.get("id") == device_id:
                desired = device.get("desired_state", [])
                for state in states:
                    key = state.get("key")
                    found = False
                    for i, d in enumerate(desired):
                        if d.get("key") == key:
                            desired[i].update(state)
                            found = True
                            break
                    if not found:
                        desired.append(state)
                self.async_set_updated_data(self.data)
                break
