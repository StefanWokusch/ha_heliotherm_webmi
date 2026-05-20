"""Number platform for writable Heliotherm WebMI controls."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WebMIError
from .const import CONF_ENABLE_WRITES, DEFAULT_ENABLE_WRITES, DOMAIN
from .descriptions import NUMBER_DESCRIPTIONS
from .entity import HeliothermWebMIEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up writable WebMI number controls."""
    if not _writes_enabled(entry):
        return

    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        HeliothermWebMINumber(coordinator, entry, description)
        for description in NUMBER_DESCRIPTIONS
    )


class HeliothermWebMINumber(HeliothermWebMIEntity, NumberEntity):
    """Representation of a writable WebMI number."""

    @property
    def native_value(self) -> float | int | None:
        """Return the current number value."""
        result = self.webmi_result
        if result is None or result.error != 0:
            return None
        return self.entity_description.value_fn(result.value)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value to WebMI and refresh the readback."""
        try:
            await self.coordinator.api.write_address(
                self.entity_description.address,
                _write_number(value),
            )
        except WebMIError as err:
            raise HomeAssistantError(
                f"Could not write {self.entity_description.translation_key}"
            ) from err
        await self.coordinator.async_request_refresh()


def _writes_enabled(entry: ConfigEntry) -> bool:
    """Return whether write controls are enabled for this entry."""
    return bool(
        entry.options.get(
            CONF_ENABLE_WRITES,
            entry.data.get(CONF_ENABLE_WRITES, DEFAULT_ENABLE_WRITES),
        )
    )


def _write_number(value: float) -> int | float:
    """Render an HA number value for WebMI."""
    if float(value).is_integer():
        return int(value)
    return round(float(value), 1)
