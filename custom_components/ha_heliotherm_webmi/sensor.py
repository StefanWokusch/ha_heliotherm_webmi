"""Sensor platform for Heliotherm WebMI."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import SENSOR_DESCRIPTIONS
from .entity import HeliothermWebMIEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WebMI sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        HeliothermWebMISensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class HeliothermWebMISensor(HeliothermWebMIEntity, SensorEntity):
    """Representation of a WebMI sensor."""

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        result = self.webmi_result
        if result is None or result.error != 0:
            return None
        try:
            return self.entity_description.value_fn(result.value)
        except (TypeError, ValueError) as err:
            _LOGGER.debug(
                "Could not convert WebMI value for %s: %s",
                self.entity_description.key,
                err,
            )
            return None

