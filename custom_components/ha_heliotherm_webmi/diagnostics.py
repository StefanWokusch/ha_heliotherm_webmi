"""Diagnostics for Heliotherm WebMI."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .descriptions import DESCRIPTIONS_BY_KEY


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator
    values = {
        DESCRIPTIONS_BY_KEY[key].address: result
        for key, result in (coordinator.data or {}).items()
    }

    return {
        "entry": {
            "title": entry.title,
            CONF_HOST: entry.data.get(CONF_HOST),
            CONF_PORT: entry.data.get(CONF_PORT),
            "options": dict(entry.options),
        },
        "base_url": runtime.api.base_url,
        "source": "coordinator_cache",
        "minimal_monitoring": coordinator.minimal_monitoring,
        "last_update_success": coordinator.last_update_success,
        "session_generation": runtime.api.session_generation,
        "address_count": len(values),
        "ok_count": sum(1 for result in values.values() if result.error == 0),
        "error_count": sum(1 for result in values.values() if result.error != 0),
        "addresses": {
            address: result.as_dict() for address, result in values.items()
        },
    }

