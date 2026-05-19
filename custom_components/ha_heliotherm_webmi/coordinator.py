"""Data update coordinator for Heliotherm WebMI."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import suppress
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    HeliothermWebMIClient,
    WebMIError,
    WebMIReadResult,
    WebMISubscriptionEvent,
    WebMITimeout,
)
from .descriptions import DESCRIPTIONS_BY_KEY

_LOGGER = logging.getLogger(__name__)

PUBLISH_TIMEOUT_SECONDS = 65
SUBSCRIPTION_RETRY_DELAY_SECONDS = 10


class HeliothermWebMICoordinator(DataUpdateCoordinator[dict[str, WebMIReadResult]]):
    """Coordinator that batch-reads enabled WebMI addresses."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HeliothermWebMIClient,
        update_interval: timedelta,
        use_subscriptions: bool = True,
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
        self._use_subscriptions = use_subscriptions
        self._subscription_task: asyncio.Task | None = None

    def async_start_subscription(self) -> None:
        """Start the WebMI subscribedata/publish loop."""
        if not self._use_subscriptions or self._subscription_task is not None:
            return
        self._subscription_task = self.hass.async_create_background_task(
            self._subscription_loop(),
            "heliotherm_webmi_subscription",
        )

    async def async_stop_subscription(self) -> None:
        """Stop the WebMI subscribedata/publish loop."""
        if self._subscription_task is None:
            return
        self._subscription_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._subscription_task
        self._subscription_task = None

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

    async def _subscription_loop(self) -> None:
        """Subscribe to WebMI changes and push partial updates into HA."""
        subscription_id: str | None = None
        subscribed_addresses: tuple[str, ...] = ()
        try:
            while True:
                address_to_keys = self._active_address_to_keys()
                addresses = tuple(address_to_keys)

                if not addresses:
                    await asyncio.sleep(SUBSCRIPTION_RETRY_DELAY_SECONDS)
                    continue

                if subscription_id is None or addresses != subscribed_addresses:
                    if subscription_id is not None:
                        with suppress(WebMIError):
                            await self.api.delete_subscription(subscription_id)
                    try:
                        subscription_id = await self.api.create_subscription()
                        await self.api.subscribe_addresses(subscription_id, addresses)
                    except WebMIError as err:
                        _LOGGER.debug(
                            "Could not create WebMI subscription; retrying: %s",
                            err,
                        )
                        self.api.reset_session()
                        subscription_id = None
                        subscribed_addresses = ()
                        await asyncio.sleep(SUBSCRIPTION_RETRY_DELAY_SECONDS)
                        continue
                    subscribed_addresses = addresses
                    _LOGGER.debug(
                        "Subscribed to %s WebMI address updates",
                        len(subscribed_addresses),
                    )

                try:
                    events = await self.api.publish_subscription(
                        timeout=PUBLISH_TIMEOUT_SECONDS,
                    )
                except WebMITimeout:
                    continue
                except WebMIError as err:
                    _LOGGER.debug(
                        "WebMI publish subscription failed; recreating session: %s",
                        err,
                    )
                    self.api.reset_session()
                    subscription_id = None
                    subscribed_addresses = ()
                    await asyncio.sleep(SUBSCRIPTION_RETRY_DELAY_SECONDS)
                    continue

                if events:
                    self._apply_subscription_events(events, address_to_keys)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # pragma: no cover - defensive background guard
            _LOGGER.warning("WebMI subscription loop stopped unexpectedly: %s", err)
        finally:
            if subscription_id is not None:
                with suppress(WebMIError):
                    await self.api.delete_subscription(subscription_id)

    def _apply_subscription_events(
        self,
        events: Iterable[WebMISubscriptionEvent],
        address_to_keys: dict[str, list[str]],
    ) -> None:
        """Apply partial subscribedata updates to coordinator data."""
        current_data = dict(self.data or {})
        changed = False

        for event in events:
            for key in address_to_keys.get(event.address, []):
                if current_data.get(key) != event.result:
                    current_data[key] = event.result
                    changed = True

        if changed:
            self.async_set_updated_data(current_data)

    def _active_address_to_keys(self) -> dict[str, list[str]]:
        """Return active WebMI addresses mapped to all matching description keys."""
        address_to_keys: dict[str, list[str]] = {}
        for description in self._active_descriptions():
            if description.address is None:
                continue
            address_to_keys.setdefault(description.address, []).append(description.key)
        return address_to_keys

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
