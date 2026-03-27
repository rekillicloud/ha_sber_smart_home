"""Sber Smart Home integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SberSmartHomeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light", "switch", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sber Smart Home from a config entry."""
    print("=" * 60)
    print("SBER_SMART_HOME: Setting up integration")
    _LOGGER.info("Setting up Sber Smart Home integration")

    coordinator = SberSmartHomeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    devices = coordinator.get_devices()
    print(f"SBER_SMART_HOME: Loaded {len(devices)} devices from coordinator")
    _LOGGER.info("Loaded %d devices from coordinator", len(devices))
    for device in devices:
        device_name = device.get("name", {})
        name = (
            device_name.get("name", "Unknown")
            if isinstance(device_name, dict)
            else str(device_name)
        )
        model = device.get("device_info", {}).get("model", "Unknown")
        attrs = [a.get("key") for a in device.get("attributes", [])]
        print(f"SBER_SMART_HOME: Device: {name}, model: {model}, attributes: {attrs}")
        _LOGGER.info("Device: %s, model: %s, attributes: %s", name, model, attrs)

    print(f"SBER_SMART_HOME: Loading platforms: {PLATFORMS}")
    _LOGGER.info("Loading platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    print("SBER_SMART_HOME: Integration set up successfully")
    _LOGGER.info("Sber Smart Home integration set up successfully")
    print("=" * 60)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Sber Smart Home integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    _LOGGER.info("Reloading Sber Smart Home integration")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
