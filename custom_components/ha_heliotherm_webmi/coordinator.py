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
    WebMISessionChanged,
    WebMISessionError,
)
from .descriptions import DESCRIPTIONS_BY_KEY, MINIMAL_SENSOR_KEYS

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
        minimal_monitoring: bool = True,
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
        self.minimal_monitoring = minimal_monitoring
        self._use_subscriptions = use_subscriptions
        self._subscription_task: asyncio.Task | None = None

    def async_start_subscription(self) -> None:
        """Start the WebMI subscribedata/publish loop."""
        if not self._use_subscriptions or self._subscription_task is not None:
            return
        _LOGGER.debug("Starting WebMI subscription monitoring (minimal profile: %s)", self.minimal_monitoring)
        self._subscription_task = self.hass.async_create_background_task(
            self._subscription_loop(),
            "heliotherm_webmi_subscription",
        )

    async def async_stop_subscription(self) -> None:
        """Stop the WebMI subscribedata/publish loop."""
        if self._subscription_task is None:
            return
        _LOGGER.debug("Stopping WebMI subscription monitoring")
        self._subscription_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._subscription_task
        self._subscription_task = None

    async def _async_update_data(self) -> dict[str, WebMIReadResult]:
        """Fetch enabled WebMI values."""
        address_to_keys = self._active_address_to_keys()
        if not address_to_keys:
            _LOGGER.debug("Skipping WebMI read: no enabled addresses")
            return {}
        _LOGGER.debug("WebMI batch read (%d addresses): %s", len(address_to_keys), ", ".join(address_to_keys))
        try:
            values_by_address = await self.api.read_addresses(address_to_keys)
        except WebMIError as err:
            raise UpdateFailed(f"Could not read WebMI values: {err}") from err

        return {
            key: values_by_address.get(
                address,
                WebMIReadResult(error=-1, errorstring="Address was not returned"),
            )
            for address, keys in address_to_keys.items()
            for key in keys
        }

    async def _subscription_loop(self) -> None:
        """Subscribe to WebMI changes and push partial updates into HA."""
        subscription_id: str | None = None
        subscription_generation: int | None = None
        subscribed_addresses: tuple[str, ...] = ()
        failures = 0
        try:
            while True:
                address_to_keys = self._active_address_to_keys()
                addresses = tuple(address_to_keys)

                if not addresses:
                    if subscription_id is not None:
                        with suppress(WebMIError):
                            await self.api.delete_subscription(
                                subscription_id, expected_generation=subscription_generation,
                            )
                        subscription_id = None
                        subscription_generation = None
                        subscribed_addresses = ()
                    await asyncio.sleep(SUBSCRIPTION_RETRY_DELAY_SECONDS)
                    continue

                if (
                    subscription_id is None or addresses != subscribed_addresses
                    or subscription_generation != self.api.session_generation
                ):
                    if subscription_id is not None:
                        with suppress(WebMIError):
                            await self.api.delete_subscription(
                                subscription_id, expected_generation=subscription_generation,
                            )
                    subscription_id = None
                    subscription_generation = None
                    try:
                        _LOGGER.debug("Registering %d WebMI addresses: %s", len(addresses), ", ".join(addresses))
                        subscription_id = await self.api.create_subscription()
                        subscription_generation = self.api.session_generation
                        await self.api.subscribe_addresses(
                            subscription_id, addresses,
                            expected_generation=subscription_generation,
                        )
                    except WebMISessionChanged:
                        _LOGGER.debug("WebMI session changed during registration; registering again")
                        subscription_id = None
                        subscription_generation = None
                        subscribed_addresses = ()
                        continue
                    except WebMIError as err:
                        _LOGGER.warning(
                            "WebMI subscription %s failed (%s); retrying",
                            "registration" if subscription_id is not None else "setup",
                            type(err).__name__,
                        )
                        if subscription_id is not None:
                            with suppress(WebMIError):
                                await self.api.delete_subscription(
                                    subscription_id, expected_generation=subscription_generation,
                                )
                        if isinstance(err, WebMISessionError):
                            await self.api.async_reset_session(expected_generation=subscription_generation)
                        subscription_id = None
                        subscription_generation = None
                        subscribed_addresses = ()
                        failures = min(failures + 1, 6)
                        await self._wait_before_retry(failures)
                        continue
                    subscribed_addresses = addresses
                    _LOGGER.debug(
                        "Subscribed to %s WebMI address updates",
                        len(subscribed_addresses),
                    )

                try:
                    events = await self.api.publish_subscription(
                        timeout=PUBLISH_TIMEOUT_SECONDS,
                        expected_generation=subscription_generation,
                    )
                except WebMITimeout:
                    _LOGGER.debug("WebMI publish wait timed out (generation %s); continuing", subscription_generation)
                    continue
                except WebMISessionChanged:
                    _LOGGER.debug("WebMI publish generation changed from %s to %s; registering again",
                                  subscription_generation, self.api.session_generation)
                    # Another read/control already replaced the session. Do not
                    # invalidate that newer session; recreate only the binding.
                    subscription_id = None
                    subscription_generation = None
                    subscribed_addresses = ()
                    continue
                except WebMIError as err:
                    _LOGGER.warning(
                        "WebMI publish failed (%s); rebuilding subscription", type(err).__name__
                    )
                    if subscription_id is not None:
                        with suppress(WebMIError):
                            await self.api.delete_subscription(
                                subscription_id, expected_generation=subscription_generation,
                            )
                    if isinstance(err, WebMISessionError):
                        await self.api.async_reset_session(expected_generation=subscription_generation)
                    subscription_id = None
                    subscription_generation = None
                    subscribed_addresses = ()
                    failures = min(failures + 1, 6)
                    await self._wait_before_retry(failures)
                    continue

                if failures:
                    _LOGGER.warning("WebMI subscription recovered; publish succeeded after retry")
                failures = 0
                if events:
                    self._apply_subscription_events(events, address_to_keys)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # pragma: no cover - defensive background guard
            _LOGGER.warning("WebMI subscription loop stopped unexpectedly: %s", err)
        finally:
            if subscription_id is not None:
                with suppress(WebMIError):
                    await self.api.delete_subscription(
                        subscription_id, expected_generation=subscription_generation,
                    )

    async def _wait_before_retry(self, failures: int) -> None:
        delay = min(300, SUBSCRIPTION_RETRY_DELAY_SECONDS * 2 ** (failures - 1))
        _LOGGER.debug("WebMI subscription retry in %ds (generation %d)", delay, self.api.session_generation)
        await asyncio.sleep(delay)

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
        read_keys: set[str] = set()
        pending = list(self.async_contexts())
        visited: set[str] = set()
        while pending:
            key = pending.pop()
            if key in visited or (self.minimal_monitoring and key not in MINIMAL_SENSOR_KEYS):
                continue
            visited.add(key)
            description = DESCRIPTIONS_BY_KEY.get(key)
            if description is None:
                continue
            if description.address is not None:
                read_keys.add(key)
            pending.extend(getattr(description, "dependencies", ()))

        return [DESCRIPTIONS_BY_KEY[key] for key in sorted(read_keys)]
