"""Select platform for writable Heliotherm WebMI controls."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import WebMIError
from .const import CONF_ENABLE_WRITES, DEFAULT_ENABLE_WRITES, DOMAIN
from .descriptions import SELECT_DESCRIPTIONS, number_value
from .entity import HeliothermWebMIEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up writable WebMI selects."""
    if not _writes_enabled(entry):
        return

    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        HeliothermWebMISelect(coordinator, entry, description)
        for description in SELECT_DESCRIPTIONS
    )


class HeliothermWebMISelect(HeliothermWebMIEntity, SelectEntity):
    """Representation of a writable WebMI select."""

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return list(self.entity_description.options_by_value.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        result = self.webmi_result
        if result is None or result.error != 0:
            return None
        value = number_value(result.value)
        if not isinstance(value, int | float):
            return None
        return self.entity_description.options_by_value.get(int(value))

    async def async_select_option(self, option: str) -> None:
        """Write the selected option to WebMI and refresh the readback."""
        value_by_option = {
            label: value
            for value, label in self.entity_description.options_by_value.items()
        }
        if option not in value_by_option:
            raise HomeAssistantError(f"Unsupported option for WebMI select: {option}")

        try:
            await self.coordinator.api.write_address(
                self.entity_description.address,
                value_by_option[option],
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
