"""Light platform for Sber Smart Home."""

import logging
from typing import Any

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SberSmartHomeCoordinator

_LOGGER = logging.getLogger(__name__)

_DEBUG = True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sber Smart Home lights."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    devices = coordinator.get_devices()
    entities = []

    for device in devices:
        device_id = device.get("id")
        device_name = device.get("name", {})
        name = (
            device_name.get("name", "Unknown")
            if isinstance(device_name, dict)
            else str(device_name)
        )
        device_type = device.get("device_type_name", "")

        attributes = device.get("attributes", [])
        attribute_keys = [a.get("key") for a in attributes]

        has_on_off = any(a.get("key") == "on_off" for a in attributes)
        has_brightness = any(a.get("key") == "light_brightness" for a in attributes)

        if _DEBUG:
            model = device.get("device_info", {}).get("model", "Unknown")
            _LOGGER.debug(
                "Device: %s (model: %s) attributes: %s, has_on_off: %s, has_brightness: %s",
                name,
                model,
                attribute_keys,
                has_on_off,
                has_brightness,
            )

        if has_on_off or has_brightness:
            entities.append(SberLight(coordinator, device_id, name, device))

    _LOGGER.info("Found %d light entities", len(entities))
    async_add_entities(entities)


class SberLight(CoordinatorEntity, LightEntity):
    """Sber Smart Home Light."""

    def __init__(self, coordinator, device_id: str, name: str, device: dict):
        """Initialize light."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name
        self._device = device
        self._attr_unique_id = f"sber_light_{device_id}"

        attributes = device.get("attributes", [])
        attribute_keys = [a.get("key") for a in attributes]

        color_modes = set()
        if "light_brightness" in attribute_keys:
            color_modes.add(ColorMode.BRIGHTNESS)
        if "light_colour" in attribute_keys:
            color_modes.add(ColorMode.COLOR)
        if "light_colour_temp" in attribute_keys:
            color_modes.add(ColorMode.COLOR_TEMP)

        if not color_modes:
            color_modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = color_modes

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return True if light is on."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "on_off":
                return state.get("bool_value", False)
        return None

    @property
    def brightness(self) -> int | None:
        """Return brightness."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "light_brightness":
                return int(state.get("integer_value", 0))
        return None

    @property
    def color_mode(self) -> ColorMode | None:
        """Return color mode."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "light_colour":
                return ColorMode.COLOR
            elif state.get("key") == "light_colour_temp":
                return ColorMode.COLOR_TEMP
            elif state.get("key") == "light_brightness":
                return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device attributes."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return {}

        attrs = {}
        reported = device.get("reported_state", [])

        for state in reported:
            key = state.get("key")
            if key == "light_colour_temp":
                attrs["color_temp"] = int(state.get("integer_value", 0))
            elif key == "light_colour":
                attrs["color"] = state.get("color_value")
            elif key == "light_scene":
                attrs["scene"] = state.get("enum_value")
            elif key == "light_mode":
                attrs["mode"] = state.get("enum_value")

        return attrs

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on light."""
        if not self.coordinator.api:
            return

        state_updates = []

        if "brightness" in kwargs:
            brightness = kwargs["brightness"]
            state_updates.append(
                {"key": "light_brightness", "value": brightness, "attr_type": "INTEGER"}
            )

        if "color_temp" in kwargs:
            color_temp = kwargs["color_temp"]
            state_updates.append(
                {
                    "key": "light_colour_temp",
                    "value": color_temp,
                    "attr_type": "INTEGER",
                }
            )

        if "color" in kwargs:
            color = kwargs["color"]
            state_updates.append(
                {"key": "light_colour", "value": color, "attr_type": "COLOR"}
            )

        state_updates.append({"key": "on_off", "value": True, "attr_type": "BOOL"})

        await self.coordinator.api.set_device_state(self._device_id, state_updates)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off light."""
        if not self.coordinator.api:
            return

        await self.coordinator.api.set_device_state(
            self._device_id, [{"key": "on_off", "value": False, "attr_type": "BOOL"}]
        )
        await self.coordinator.async_request_refresh()
