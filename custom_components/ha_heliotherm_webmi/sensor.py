"""Sensor platform for Heliotherm WebMI."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .descriptions import DESCRIPTIONS_BY_KEY, SENSOR_DESCRIPTIONS
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
    def available(self) -> bool:
        """Return if entity is available."""
        if self.entity_description.calculate_fn is None:
            return super().available
        return (
            self.coordinator.last_update_success
            and self._calculated_value() is not None
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.entity_description.calculate_fn is not None:
            return self._calculated_value()

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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes for calculated sensors."""
        if self.entity_description.calculate_fn is None:
            return None
        return {
            **self.entity_description.calculation_attributes,
            "dependencies": list(self.entity_description.dependencies),
        }

    def _calculated_value(self) -> Any:
        """Calculate a derived sensor value from dependency values."""
        if self.coordinator.data is None:
            return None

        dependency_values: dict[str, Any] = {}
        for key in self.entity_description.dependencies:
            result = self.coordinator.data.get(key)
            if result is None or result.error != 0:
                return None
            description = DESCRIPTIONS_BY_KEY.get(key)
            if description is None:
                return None
            try:
                dependency_values[key] = description.value_fn(result.value)
            except (TypeError, ValueError):
                return None

        try:
            return self.entity_description.calculate_fn(dependency_values)
        except (TypeError, ValueError) as err:
            _LOGGER.debug(
                "Could not calculate WebMI value for %s: %s",
                self.entity_description.key,
                err,
            )
            return None
