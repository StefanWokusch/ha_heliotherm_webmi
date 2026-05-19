"""The Heliotherm WebMI integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HeliothermWebMIClient
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_USE_SUBSCRIPTIONS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SUBSCRIPTION_FALLBACK_INTERVAL,
    DEFAULT_USE_SUBSCRIPTIONS,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
)
from .coordinator import HeliothermWebMICoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class HeliothermWebMIRuntimeData:
    """Runtime data for one config entry."""

    api: HeliothermWebMIClient
    coordinator: HeliothermWebMICoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heliotherm WebMI from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = int(entry.data.get(CONF_PORT, DEFAULT_PORT))
    scan_interval = _scan_interval(entry)
    use_subscriptions = _use_subscriptions(entry)
    update_interval = scan_interval
    if use_subscriptions:
        update_interval = max(scan_interval, DEFAULT_SUBSCRIPTION_FALLBACK_INTERVAL)

    api = HeliothermWebMIClient(
        async_get_clientsession(hass),
        host=host,
        port=port,
    )
    equivalent_entries = [
        configured_entry
        for configured_entry in hass.config_entries.async_entries(DOMAIN)
        if _entry_base_url(configured_entry) == api.base_url
    ]
    if equivalent_entries:
        primary_entry = min(equivalent_entries, key=_entry_sort_key)
        if entry.entry_id != primary_entry.entry_id:
            _LOGGER.error(
                "Duplicate Heliotherm WebMI entry %s for %s; keeping primary entry %s",
                entry.entry_id,
                api.base_url,
                primary_entry.entry_id,
            )
            return False

    coordinator = HeliothermWebMICoordinator(
        hass,
        api=api,
        update_interval=timedelta(seconds=update_interval),
        use_subscriptions=use_subscriptions,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = HeliothermWebMIRuntimeData(
        api=api,
        coordinator=coordinator,
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.async_start_subscription()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime.coordinator.async_stop_subscription()
        runtime.api.reset_session()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after options changed."""
    await hass.config_entries.async_reload(entry.entry_id)


def _scan_interval(entry: ConfigEntry) -> int:
    value = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = DEFAULT_SCAN_INTERVAL
    return max(seconds, MIN_SCAN_INTERVAL)


def _use_subscriptions(entry: ConfigEntry) -> bool:
    value = entry.options.get(
        CONF_USE_SUBSCRIPTIONS,
        entry.data.get(CONF_USE_SUBSCRIPTIONS, DEFAULT_USE_SUBSCRIPTIONS),
    )
    return bool(value)


def _entry_base_url(entry: ConfigEntry) -> str | None:
    """Return the normalized WebMI base URL for an entry."""
    try:
        return HeliothermWebMIClient._normalize_base_url(
            entry.data[CONF_HOST],
            int(entry.data.get(CONF_PORT, DEFAULT_PORT)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _entry_sort_key(entry: ConfigEntry) -> tuple[float, str]:
    """Return a stable order key for equivalent entries."""
    created_at = getattr(entry, "created_at", None)
    if created_at is None:
        sort_value = float("inf")
    elif hasattr(created_at, "timestamp"):
        sort_value = created_at.timestamp()
    else:
        sort_value = float(created_at)
    return (sort_value, entry.entry_id)
