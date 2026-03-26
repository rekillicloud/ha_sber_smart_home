"""Switch platform for Sber Smart Home."""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SberSmartHomeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sber Smart Home switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    devices = coordinator.get_devices()
    entities = []
    
    for device in devices:
        device_id = device.get("id")
        device_name = device.get("name", {})
        name = device_name.get("name", "Unknown") if isinstance(device_name, dict) else str(device_name)
        
        attributes = device.get("attributes", [])
        
        has_on_off = any(
            a.get("key") == "on_off" for a in attributes
        )
        
        if has_on_off:
            entity_type = "switch"
            attributes_keys = [a.get("key") for a in attributes]
            
            if "light_brightness" in attributes_keys or "light_colour" in attributes_keys:
                continue
            
            entities.append(
                SberSwitch(coordinator, device_id, name, device)
            )
    
    async_add_entities(entities)


class SberSwitch(CoordinatorEntity, SwitchEntity):
    """Sber Smart Home Switch."""

    def __init__(self, coordinator, device_id: str, name: str, device: dict):
        """Initialize switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name
        self._device = device
        self._attr_unique_id = f"sber_switch_{device_id}"

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return True if switch is on."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None
        
        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "on_off":
                return state.get("bool_value", False)
        return None

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return {}
        
        device_info = device.get("device_info", {})
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._name,
            "manufacturer": device_info.get("manufacturer", "Sber"),
            "model": device_info.get("model", "Smart Device"),
            "sw_version": device_info.get("sw_version"),
            "hw_version": device_info.get("hw_version"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        if not self.coordinator.api:
            return
        
        await self.coordinator.api.set_switch_state(self._device_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        if not self.coordinator.api:
            return
        
        await self.coordinator.api.set_switch_state(self._device_id, False)
        await self.coordinator.async_request_refresh()
