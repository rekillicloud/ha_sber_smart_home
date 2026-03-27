"""Light platform for Sber Smart Home."""

import asyncio
import logging
from typing import Any

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import color_hs_to_RGB, color_RGB_to_hs

from .const import DOMAIN
from .coordinator import SberSmartHomeCoordinator

_LOGGER = logging.getLogger(__name__)


LIGHT_TYPES = ("bulb", "ledstrip", "night_lamp", "cat_ledstrip_m", "cat_bulb_m")


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

        image_set_type = device.get("image_set_type", "")

        if any(t in image_set_type for t in LIGHT_TYPES):
            entities.append(SberLight(coordinator, device_id, name, device))

    async_add_entities(entities)


class SberLight(CoordinatorEntity, LightEntity):
    """Sber Smart Home Light."""

    _attr_assumed_state = True

    def __init__(self, coordinator, device_id: str, name: str, device: dict):
        """Initialize light."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name
        self._device = device
        self._attr_unique_id = f"sber_light_{device_id}"
        self._attr_name = name
        self._is_on = None
        self._brightness = None
        self._hs_color = None

        attributes = device.get("attributes", [])
        attribute_keys = [a.get("key") for a in attributes]

        has_color = "light_colour" in attribute_keys
        has_color_temp = "light_colour_temp" in attribute_keys
        has_brightness = "light_brightness" in attribute_keys

        color_modes = set()
        if has_color:
            color_modes.add(ColorMode.HS)
            if has_color_temp:
                color_modes.add(ColorMode.COLOR_TEMP)
        elif has_color_temp:
            color_modes.add(ColorMode.COLOR_TEMP)
        elif has_brightness:
            color_modes.add(ColorMode.BRIGHTNESS)
        else:
            color_modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = color_modes

        self._supports_color = has_color
        self._supports_color_temp = has_color_temp
        self._supports_brightness = has_brightness

        self._attr_icon = "mdi:lightbulb"
        self._has_brightness = has_brightness
        self._has_mode = "light_mode" in attribute_keys

        if ColorMode.COLOR_TEMP in color_modes:
            self._attr_min_mireds = 153
            self._attr_max_mireds = 500

        self._optimistic_state = {}
        self._last_command_time = None

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
        }

    @property
    def is_on(self) -> bool | None:
        """Return True if light is on."""
        if self._is_on is not None:
            return self._is_on

        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        desired = device.get("desired_state", [])
        for state in desired:
            if state.get("key") == "on_off":
                return state.get("bool_value", False)
        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "switch_led":
                return state.get("bool_value", False)
        return None

    @property
    def brightness(self) -> int | None:
        """Return brightness (0-255 for HA, 50-1000 for Sber)."""
        if self._brightness is not None:
            return self._brightness

        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        if self.color_mode == ColorMode.HS:
            desired = device.get("desired_state", [])
            for state in desired:
                if state.get("key") == "light_colour":
                    color_value = state.get("color_value")
                    if color_value and "v" in color_value:
                        v = int(color_value.get("v", 1000))
                        return int((v - 50) * 255 / 950)
            reported = device.get("reported_state", [])
            for state in reported:
                if state.get("key") == "light_colour":
                    color_value = state.get("color_value")
                    if color_value and "v" in color_value:
                        v = int(color_value.get("v", 1000))
                        return int((v - 50) * 255 / 950)

        desired = device.get("desired_state", [])
        for state in desired:
            if state.get("key") == "light_brightness":
                sber_brightness = int(state.get("integer_value", 50))
                ha_brightness = int((sber_brightness - 50) * 255 / 950)
                return max(0, min(255, ha_brightness))

        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "light_brightness":
                sber_brightness = int(state.get("integer_value", 50))
                ha_brightness = int((sber_brightness - 50) * 255 / 950)
                return max(0, min(255, ha_brightness))

        return None

    @property
    def color_temp(self) -> int | None:
        """Return color temperature in mireds."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "light_colour_temp":
                sber_temp = int(state.get("integer_value", 0))
                return int(sber_temp * 347 / 1000 + 153)
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return hue and saturation."""
        if self._hs_color is not None:
            return self._hs_color

        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        desired = device.get("desired_state", [])
        for state in desired:
            if state.get("key") == "light_colour":
                color_value = state.get("color_value")
                if color_value:
                    h = color_value.get("h", 0)
                    s = color_value.get("s", 0)
                    return (float(h), float(s) / 10.0)

        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "light_colour":
                color_value = state.get("color_value")
                if color_value:
                    h = color_value.get("h", 0)
                    s = color_value.get("s", 0)
                    return (float(h), float(s) / 10.0)
        return None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return rgb color."""
        hs = self.hs_color
        if hs is None:
            return None

        return tuple(int(v) for v in color_hs_to_RGB(hs[0], hs[1]))

    @property
    def color_mode(self) -> ColorMode | None:
        """Return current color mode."""
        if self._hs_color is not None:
            return ColorMode.HS

        device = self.coordinator.get_device(self._device_id)
        if device and self._has_mode:
            desired = device.get("desired_state", [])
            for state in desired:
                if state.get("key") == "light_mode":
                    mode = state.get("enum_value", "")
                    if mode == "colour":
                        return ColorMode.HS
                    elif mode == "white":
                        return ColorMode.COLOR_TEMP
            reported = device.get("reported_state", [])
            for state in reported:
                if state.get("key") == "light_mode":
                    mode = state.get("enum_value", "")
                    if mode == "colour":
                        return ColorMode.HS
                    elif mode == "white":
                        return ColorMode.COLOR_TEMP

        if ColorMode.HS in self._attr_supported_color_modes:
            return ColorMode.HS
        elif ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return ColorMode.COLOR_TEMP
        elif ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
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

    def _get_current_light_mode(self) -> str | None:
        """Get current light mode from device state."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None
        desired = device.get("desired_state", [])
        for state in desired:
            if state.get("key") == "light_mode":
                return state.get("enum_value")
        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "light_mode":
                return state.get("enum_value")
        return None

    def _get_current_color(self) -> dict | None:
        """Get current color from device state."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None
        desired = device.get("desired_state", [])
        for state in desired:
            if state.get("key") == "light_colour":
                return state.get("color_value")
        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == "light_colour":
                return state.get("color_value")
        return None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on light."""
        if not self.coordinator.api:
            return

        state_updates = []

        if "brightness" in kwargs:
            ha_brightness = kwargs["brightness"]
            sber_brightness = 50 + (int(ha_brightness) * 950 // 255)
            sber_brightness = max(50, min(1000, sber_brightness))
            _LOGGER.warning(
                f"SBER BRIGHTNESS: ha={ha_brightness}, sber={sber_brightness}, mode={self.color_mode}"
            )

            if self.color_mode == ColorMode.HS:
                current_color = self._get_current_color()
                if current_color:
                    h = current_color.get("h", 0)
                    s = current_color.get("s", 0)
                    v = sber_brightness
                    state_updates = [
                        {"key": "on_off", "bool_value": True},
                        {"key": "light_mode", "enum_value": "colour"},
                        {
                            "key": "light_colour",
                            "color_value": {"h": h, "s": s, "v": v},
                        },
                    ]
                    await self.coordinator.api.set_device_state(
                        self._device_id,
                        state_updates,
                    )
                    self.coordinator.async_patch_device_state(
                        self._device_id, state_updates
                    )
                else:
                    state_updates = [
                        {"key": "on_off", "bool_value": True},
                        {"key": "light_mode", "enum_value": "white"},
                        {
                            "key": "light_brightness",
                            "integer_value": sber_brightness,
                        },
                    ]
                    await self.coordinator.api.set_device_state(
                        self._device_id,
                        state_updates,
                    )
                    self.coordinator.async_patch_device_state(
                        self._device_id, state_updates
                    )
            else:
                state_updates = [
                    {"key": "on_off", "bool_value": True},
                    {"key": "light_mode", "enum_value": "white"},
                    {"key": "light_brightness", "integer_value": sber_brightness},
                ]
                await self.coordinator.api.set_device_state(
                    self._device_id,
                    state_updates,
                )
                self.coordinator.async_patch_device_state(
                    self._device_id, state_updates
                )
            self._brightness = ha_brightness
            self._is_on = True
            self.async_write_ha_state()
            return

        if "color_temp" in kwargs:
            ha_color_temp = kwargs["color_temp"]
            sber_color_temp = int((ha_color_temp - 153) * 1000 / 347)
            sber_color_temp = max(0, min(1000, sber_color_temp))
            state_updates.append(
                {
                    "key": "light_colour_temp",
                    "integer_value": sber_color_temp,
                }
            )
            if self._has_mode:
                state_updates.append({"key": "light_mode", "enum_value": "white"})

        if "hs_color" in kwargs:
            hs = kwargs["hs_color"]
            h, s = hs[0], hs[1]
            state_updates.append(
                {
                    "key": "light_colour",
                    "color_value": {"h": int(h), "s": int(s * 10), "v": 1000},
                }
            )
            self._hs_color = hs
            if self._has_mode:
                state_updates.append({"key": "light_mode", "enum_value": "colour"})

        if "rgb_color" in kwargs:
            rgb = kwargs["rgb_color"]
            h, s = color_RGB_to_hs(rgb[0], rgb[1], rgb[2])
            state_updates.append(
                {
                    "key": "light_colour",
                    "color_value": {"h": int(h), "s": int(s * 10), "v": 1000},
                }
            )
            self._hs_color = (h, s)
            if self._has_mode:
                state_updates.append({"key": "light_mode", "enum_value": "colour"})

        if "on_off" not in [s.get("key") for s in state_updates]:
            state_updates.append({"key": "on_off", "bool_value": True})

        await self.coordinator.api.set_device_state(self._device_id, state_updates)
        self.coordinator.async_patch_device_state(self._device_id, state_updates)

        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off light."""
        if not self.coordinator.api:
            return

        state_updates = [{"key": "on_off", "bool_value": False}]
        await self.coordinator.api.set_device_state(
            self._device_id,
            state_updates,
        )
        self.coordinator.async_patch_device_state(self._device_id, state_updates)

        self._is_on = False
        self._brightness = None
        self._hs_color = None
        self.async_write_ha_state()
