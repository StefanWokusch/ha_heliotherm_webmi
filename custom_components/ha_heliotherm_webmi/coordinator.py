"""Data update coordinator for Heliotherm WebMI."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeliothermWebMIClient, WebMIError, WebMIReadResult
from .descriptions import DESCRIPTIONS_BY_KEY

_LOGGER = logging.getLogger(__name__)


class HeliothermWebMICoordinator(DataUpdateCoordinator[dict[str, WebMIReadResult]]):
    """Coordinator that batch-reads enabled WebMI addresses."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HeliothermWebMIClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Heliotherm WebMI",
            update_interval=update_interval,
            always_update=False,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, WebMIReadResult]:
        """Fetch enabled WebMI values."""
        descriptions = self._active_descriptions()
        addresses = [
            description.address
            for description in descriptions
            if description.address is not None
        ]
        try:
            values_by_address = await self.api.read_addresses(addresses)
        except WebMIError as err:
            raise UpdateFailed(f"Could not read WebMI values: {err}") from err

        return {
            description.key: values_by_address.get(
                description.address,
                WebMIReadResult(error=-1, errorstring="Address was not returned"),
            )
            for description in descriptions
            if description.address is not None
        }

    def _active_descriptions(self) -> Iterable:
        contexts = set(self.async_contexts())
        if contexts:
            active_keys = {key for key in contexts if key in DESCRIPTIONS_BY_KEY}
        else:
            active_keys = {
                description.key
                for description in DESCRIPTIONS_BY_KEY.values()
                if description.entity_registry_enabled_default
            }

        read_keys: set[str] = set()
        pending = list(active_keys)
        while pending:
            key = pending.pop()
            description = DESCRIPTIONS_BY_KEY.get(key)
            if description is None:
                continue
            if description.address is not None:
                read_keys.add(key)
            pending.extend(getattr(description, "dependencies", ()))

        return [DESCRIPTIONS_BY_KEY[key] for key in sorted(read_keys)]
