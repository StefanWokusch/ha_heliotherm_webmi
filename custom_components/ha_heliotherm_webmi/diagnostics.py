"""Diagnostics for Heliotherm WebMI."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    addresses = await runtime.api.discover_addresses()
    values = await runtime.api.read_addresses(addresses)

    return {
        "entry": {
            "title": entry.title,
            CONF_HOST: entry.data.get(CONF_HOST),
            CONF_PORT: entry.data.get(CONF_PORT),
            "options": dict(entry.options),
        },
        "base_url": runtime.api.base_url,
        "address_count": len(addresses),
        "ok_count": sum(1 for result in values.values() if result.error == 0),
        "error_count": sum(1 for result in values.values() if result.error != 0),
        "addresses": {
            address: values[address].as_dict()
            for address in addresses
            if address in values
        },
    }

