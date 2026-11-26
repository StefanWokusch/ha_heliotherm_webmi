"""Data update coordinator for Heliotherm WebMI."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import suppress
from datetime import datetime, timedelta, timezone
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
PHASE_KEY = "startseiten_statuscode"
TIMER_KEY = "diag_sp_311"
PHASE_ADDRESS = "webregler/sp/310/value"
TIMER_ADDRESS = "webregler/sp/311/value"
TIMER_CHECK_SECONDS = 3600


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
        self._data_lock = asyncio.Lock()
        self._timer_wakeup = asyncio.Event()
        self._timer_task: asyncio.Task | None = None
        self._timer_due = 0.0
        self._expiry_check = False
        self._checked_expiry = False
        self._sample_generation: int | None = None
        self.timer_attributes: dict = {}

    def async_start_subscription(self) -> None:
        """Start the WebMI subscribedata/publish loop."""
        if self._timer_task is None:
            self._timer_task = self.hass.async_create_background_task(
                self._timer_loop(), "heliotherm_webmi_timer"
            )
        if not self._use_subscriptions or self._subscription_task is not None:
            return
        _LOGGER.debug("Starting WebMI subscription monitoring (minimal profile: %s)", self.minimal_monitoring)
        self._subscription_task = self.hass.async_create_background_task(
            self._subscription_loop(),
            "heliotherm_webmi_subscription",
        )

    async def async_stop_subscription(self) -> None:
        """Stop the WebMI subscribedata/publish loop."""
        if self._timer_task is not None:
            self._timer_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._timer_task
            self._timer_task = None
        if self._subscription_task is None:
            return
        _LOGGER.debug("Stopping WebMI subscription monitoring")
        self._subscription_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._subscription_task
        self._subscription_task = None

    async def _async_update_data(self) -> dict[str, WebMIReadResult]:
        """Fetch enabled WebMI values."""
        async with self._data_lock:
            return await self._read_active_points()

    async def _read_active_points(self) -> dict[str, WebMIReadResult]:
        address_to_keys = self._active_address_to_keys()
        if not address_to_keys:
            _LOGGER.debug("Skipping WebMI read: no enabled addresses")
            return {}
        addresses = list(address_to_keys)
        timer_enabled = TIMER_ADDRESS in address_to_keys
        if timer_enabled and self.data and TIMER_KEY in self.data:
            addresses.remove(TIMER_ADDRESS)
        _LOGGER.debug("WebMI batch read (%d addresses): %s", len(addresses), ", ".join(addresses))
        try:
            values_by_address = await self.api.read_addresses(addresses)
            if timer_enabled:
                if TIMER_ADDRESS in addresses:
                    self._record_timer(values_by_address)
                elif (
                    self._phase_changed(values_by_address)
                    or self._sample_generation != self.api.session_generation
                    or not self.last_update_success
                ):
                    values_by_address.update(await self._read_timer())
                else:
                    values_by_address[TIMER_ADDRESS] = self.data[TIMER_KEY]
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

    def _phase_changed(self, values: dict[str, WebMIReadResult]) -> bool:
        phase = values.get(PHASE_ADDRESS)
        previous = (self.data or {}).get(PHASE_KEY)
        return phase is not None and (
            previous is None or (phase.value, phase.error) != (previous.value, previous.error)
        )

    async def _read_timer(self) -> dict[str, WebMIReadResult]:
        """Take one paired observation so a timer is never assigned to an old phase."""
        try:
            values = await self.api.read_addresses([PHASE_ADDRESS, TIMER_ADDRESS])
        except WebMIError as err:
            _LOGGER.warning("WebMI timer read failed (%s); retry in 60s", type(err).__name__)
            values = {}
        phase = values.get(PHASE_ADDRESS)
        if TIMER_ADDRESS not in values or phase is None or phase.error != 0:
            values[TIMER_ADDRESS] = WebMIReadResult(error=-1, errorstring="Missing paired phase/timer sample")
        self._record_timer(values)
        return values

    def _record_timer(self, values: dict[str, WebMIReadResult]) -> None:
        phase = values.get(PHASE_ADDRESS)
        timer = values.get(TIMER_ADDRESS)
        previous_phase = self.timer_attributes.get("phase")
        self.timer_attributes = {}
        delay = 60  # Retry missing or invalid observations.
        self._expiry_check = False
        self._sample_generation = self.api.session_generation
        if phase and timer and phase.error == 0 and timer.error == 0:
            try:
                seconds = abs(int(timer.value))
                code = int(phase.value)
                now = datetime.now(timezone.utc)
                delta = timedelta(seconds=seconds)
                attrs = {"phase": code, "sampled_at": now.isoformat()}
                if previous_phase != code:
                    self._checked_expiry = False
                if code in (0, 10) and seconds:
                    attrs["timer_ends_at"] = (now + delta).isoformat()
                elif code == 9:
                    attrs["running_since"] = (now - delta).isoformat()
                delay = TIMER_CHECK_SECONDS
                if code in (0, 10) and 0 < seconds <= delay and not self._checked_expiry:
                    delay = seconds
                    self._expiry_check = True
                self.timer_attributes = attrs
                _LOGGER.debug("WebMI phase %d, observed timer %ds; next timer check in %ds", code, seconds, delay)
            except (ValueError, TypeError, OverflowError):
                _LOGGER.debug("Invalid WebMI phase/timer observation")
        self._schedule_timer(delay)

    def _schedule_timer(self, seconds: int) -> None:
        self._timer_due = asyncio.get_running_loop().time() + seconds
        self._timer_wakeup.set()

    async def _timer_loop(self) -> None:
        """Keep the hourly/expiry check independent of normal reads and push traffic."""
        loop = asyncio.get_running_loop()
        while True:
            self._timer_wakeup.clear()
            if not self._timer_due:
                await self._timer_wakeup.wait()
                continue
            try:
                await asyncio.wait_for(self._timer_wakeup.wait(), max(0, self._timer_due - loop.time()))
                continue
            except asyncio.TimeoutError:
                pass
            if not self.last_update_success:
                # Recover the entire data set before making any entity available.
                self._schedule_timer(60)
                await self.async_request_refresh()
                continue
            async with self._data_lock:
                if self._timer_due > loop.time():
                    continue
                if TIMER_ADDRESS not in self._active_address_to_keys():
                    self._timer_due = 0.0
                    continue
                if self._expiry_check:
                    self._checked_expiry = True
                await self._push_timer_sample(self._active_address_to_keys())

    async def _subscription_loop(self) -> None:
        """Subscribe to WebMI changes and push partial updates into HA."""
        subscription_id: str | None = None
        subscription_generation: int | None = None
        subscribed_addresses: tuple[str, ...] = ()
        failures = 0
        registered_before = False
        try:
            while True:
                address_to_keys = self._active_address_to_keys()
                addresses = tuple(a for a in address_to_keys if a != TIMER_ADDRESS)

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
                        if TIMER_ADDRESS in address_to_keys and (
                            registered_before or self._sample_generation != subscription_generation
                        ):
                            async with self._data_lock:
                                await self._push_timer_sample(address_to_keys)
                        registered_before = True
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
                    if events:
                        async with self._data_lock:
                            if TIMER_ADDRESS in address_to_keys and any(
                                event.address == PHASE_ADDRESS
                                and self._phase_changed({PHASE_ADDRESS: event.result})
                                for event in events
                            ):
                                await self._push_timer_sample(address_to_keys, events)
                            else:
                                self._apply_subscription_events(events, address_to_keys)
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

    async def _push_timer_sample(
        self,
        address_to_keys: dict[str, list[str]],
        events: Iterable[WebMISubscriptionEvent] = (),
    ) -> None:
        values = await self._read_timer()
        paired = [WebMISubscriptionEvent(address=a, result=v) for a, v in values.items()]
        self._apply_subscription_events([*events, *paired], address_to_keys, timer_sampled=True)

    def _apply_subscription_events(
        self,
        events: Iterable[WebMISubscriptionEvent],
        address_to_keys: dict[str, list[str]],
        *, timer_sampled: bool = False,
    ) -> None:
        """Apply partial subscribedata updates to coordinator data."""
        current_data = dict(self.data or {})
        changed = False

        for event in events:
            for key in address_to_keys.get(event.address, []):
                if current_data.get(key) != event.result:
                    current_data[key] = event.result
                    changed = True

        if changed or timer_sampled:
            self.async_set_updated_data(current_data)

    def _active_address_to_keys(self) -> dict[str, list[str]]:
        """Return active WebMI addresses mapped to all matching description keys."""
        address_to_keys: dict[str, list[str]] = {}
        for description in self._active_descriptions():
            if description.address is None:
                continue
            address_to_keys.setdefault(description.address, []).append(description.key)
        if TIMER_ADDRESS in address_to_keys:
            keys = address_to_keys.setdefault(PHASE_ADDRESS, [])
            if PHASE_KEY not in keys:
                keys.append(PHASE_KEY)
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
