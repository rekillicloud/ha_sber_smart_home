"""Sensor platform for Sber Smart Home."""

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SberSmartHomeCoordinator

_LOGGER = logging.getLogger(__name__)


SENSOR_ATTRIBUTES = {
    "temperature": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": "°C",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "humidity": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "power": {
        "device_class": SensorDeviceClass.POWER,
        "unit": "W",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "voltage": {
        "device_class": SensorDeviceClass.VOLTAGE,
        "unit": "V",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "current": {
        "device_class": SensorDeviceClass.CURRENT,
        "unit": "A",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "online": {
        "device_class": SensorDeviceClass.ENUM,
        "unit": None,
        "state_class": None,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sber Smart Home sensors."""
    print("=" * 60)
    print("SBER_SENSOR: Starting sensor platform setup")

    coordinator = hass.data[DOMAIN][entry.entry_id]

    devices = coordinator.get_devices()
    print(f"SBER_SENSOR: Found {len(devices)} devices")
    _LOGGER.warning("Sensor platform: found %d devices", len(devices))
    entities = []

    for device in devices:
        device_id = device.get("id")
        device_name = device.get("name", {})
        name = (
            device_name.get("name", "Unknown")
            if isinstance(device_name, dict)
            else str(device_name)
        )

        attributes = device.get("attributes", [])

        sensor_attributes = [
            "temperature",
            "humidity",
            "power",
            "voltage",
            "current",
            "online",
        ]

        for attr_key in sensor_attributes:
            if any(a.get("key") == attr_key for a in attributes):
                print(f"SBER_SENSOR: Creating sensor {attr_key} for device {name}")
                _LOGGER.warning("Creating sensor %s for device %s", attr_key, name)
                entities.append(
                    SberSensor(
                        coordinator, device_id, f"{name} {attr_key}", attr_key, device
                    )
                )

    print(f"SBER_SENSOR: Creating {len(entities)} sensor entities")
    _LOGGER.warning("Creating %d sensor entities", len(entities))
    print("=" * 60)
    async_add_entities(entities)


class SberSensor(CoordinatorEntity, SensorEntity):
    """Sber Smart Home Sensor."""

    def __init__(
        self, coordinator, device_id: str, name: str, attribute_key: str, device: dict
    ):
        """Initialize sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._name = name
        self._attribute_key = attribute_key
        self._device = device
        self._attr_unique_id = f"sber_sensor_{device_id}_{attribute_key}"

        attr_config = SENSOR_ATTRIBUTES.get(attribute_key, {})
        self._attr_device_class = attr_config.get("device_class")
        self._attr_native_unit_of_measurement = attr_config.get("unit")
        self._attr_state_class = attr_config.get("state_class")

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return None

        reported = device.get("reported_state", [])
        for state in reported:
            if state.get("key") == self._attribute_key:
                if self._attribute_key == "online":
                    return "online" if state.get("bool_value") else "offline"
                elif self._attribute_key in [
                    "temperature",
                    "humidity",
                    "power",
                    "voltage",
                    "current",
                ]:
                    return float(state.get("integer_value", 0))
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
        }
