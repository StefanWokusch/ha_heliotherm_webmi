"""Binary sensor platform for Heliotherm WebMI."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import BINARY_SENSOR_DESCRIPTIONS
from .entity import HeliothermWebMIEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WebMI binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        HeliothermWebMIBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class HeliothermWebMIBinarySensor(HeliothermWebMIEntity, BinarySensorEntity):
    """Representation of a WebMI binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        result = self.webmi_result
        if result is None or result.error != 0:
            return None
        return result.value in self.entity_description.on_values

