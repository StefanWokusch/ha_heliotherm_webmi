"""Async client for the local Heliotherm WebMI API."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import asyncio
import hashlib
import json
import logging
import re
import secrets
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)
_WRITE_LOGGER = logging.getLogger(__name__ + ".write_audit")
SESSION_ERRORS = {-1, -2, 454, 462}

ADDRESS_RE = re.compile(r"webregler/(?:sp|mp)/\d+/value|mcg/data/[A-Za-z0-9_/]+")


class WebMIError(Exception):
    """Base exception for WebMI errors."""


class WebMITimeout(WebMIError):
    """Raised when a WebMI request times out."""


class WebMISessionChanged(WebMIError):
    """An in-flight response belongs to a replaced session."""


class WebMISessionError(WebMIError):
    """The server rejected authentication/session state."""


@dataclass(frozen=True)
class WebMIReadResult:
    """One WebMI read result."""

    value: Any | None = None
    error: int | None = None
    errorstring: str | None = None
    timestamp: float | None = None
    status: int | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "WebMIReadResult":
        """Build a result from a WebMI response item."""
        if payload is None:
            return cls(error=-1, errorstring="Missing WebMI response item")
        return cls(
            value=payload.get("value"),
            error=payload.get("error"),
            errorstring=payload.get("errorstring"),
            timestamp=payload.get("timestamp"),
            status=payload.get("status"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class WebMISubscriptionEvent:
    """One WebMI subscribedata publish event."""

    address: str
    result: WebMIReadResult


class HeliothermWebMIClient:
    """Small WebMI client."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int = 80,
        timeout: int = 10,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = self._normalize_base_url(host, port)
        self._timeout = ClientTimeout(total=timeout)
        self._sessionid: str | None = None
        self._secret: str | None = None
        self._cnonce = 1
        self._session_generation = 0
        self._session_lock = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()
        self._retired_sessions: list[dict[str, str]] = []
        self._closed = False

    @property
    def session_generation(self) -> int:
        """Token binding subscriptions to their authenticated session."""
        return self._session_generation

    @property
    def base_url(self) -> str:
        """Return the controller base URL."""
        return self._base_url

    @staticmethod
    def _normalize_base_url(host: str, port: int) -> str:
        host = host.strip().rstrip("/")
        parsed = urlparse(host)
        if parsed.scheme in {"http", "https"}:
            return host
        if port in (80, None):
            return f"http://{host}"
        return f"http://{host}:{port}"

    async def info(self) -> dict[str, Any]:
        """Fetch WebMI capability information."""
        return await self._post_json("info")

    async def read_addresses(
        self,
        addresses: Iterable[str],
    ) -> dict[str, WebMIReadResult]:
        """Read multiple WebMI addresses in one request."""
        unique_addresses = list(dict.fromkeys(addresses))
        if not unique_addresses:
            return {}

        response = await self._read_addresses_once(unique_addresses)
        if self._should_retry_read(response, len(unique_addresses)):
            _LOGGER.debug("WebMI read failed or session expired; recreating session")
            await self.async_reset_session()
            response = await self._read_addresses_once(unique_addresses)

        self._raise_for_invalid_read_response(response, len(unique_addresses))
        result_items = response.get("result") or []

        return {
            address: WebMIReadResult.from_payload(item)
            for address, item in zip(unique_addresses, result_items, strict=False)
        }

    async def write_address(
        self, address: str, value: Any, *, audit_context: dict[str, Any] | None = None
    ) -> None:
        """Audit each explicit write attempt, including uncertain outcomes."""
        request_id = secrets.token_hex(8)
        context = {
            key: (audit_context or {}).get(key)
            for key in ("entity_id", "context_id", "parent_id", "user_id")
        }
        for attempt in (1, 2):
            self._audit_write(request_id, attempt, address, value, context, "attempt")
            response = None
            try:
                response = await self._write_addresses_once([address], [value])
                if attempt == 1 and self._should_retry_write(response, 1):
                    self._audit_write(
                        request_id, attempt, address, value, context,
                        "session_rejected_retry", error_code=response.get("error"),
                    )
                    await self.async_reset_session()
                    continue
                self._raise_for_invalid_write_response(response, 1)
            except asyncio.CancelledError:
                self._audit_write(request_id, attempt, address, value, context, "cancelled_outcome_unknown")
                raise
            except WebMITimeout:
                self._audit_write(request_id, attempt, address, value, context, "timeout_outcome_unknown")
                raise
            except WebMISessionChanged:
                self._audit_write(request_id, attempt, address, value, context, "session_changed_outcome_unknown")
                raise
            except Exception as err:
                self._audit_write(
                    request_id, attempt, address, value, context,
                    "error_outcome_unknown", error_type=type(err).__name__,
                    error_codes=(
                        [response.get("error")]
                        + [item.get("error") for item in (response.get("result") or []) if isinstance(item, dict)]
                        if isinstance(response, dict) and isinstance(response.get("result", []), list)
                        else []
                    ),
                )
                raise
            self._audit_write(request_id, attempt, address, value, context, "acknowledged")
            return

    @staticmethod
    def _audit_write(request_id, attempt, address, value, context, outcome, **details):
        # WARNING intentionally retains successful writes in HA's default logs.
        # Never include response bodies, headers, session IDs, nonces or secrets.
        record = {
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id, "attempt": attempt,
            "address": address, "value": value, "outcome": outcome,
            **context, **details,
        }
        _WRITE_LOGGER.warning("WEBMI_WRITE_AUDIT %s", json.dumps(record, ensure_ascii=True))

    async def create_subscription(self) -> str:
        """Create a WebMI data subscription and return its id."""
        response = await self._session_request(
            "createsubscription",
            data={"Persistent": "true"},
        )
        self._raise_for_session_error(response)
        subscription_id = response.get("subscriptionid")
        if not subscription_id:
            raise WebMIError(f"WebMI createsubscription failed: {response}")
        return str(subscription_id)

    async def subscribe_addresses(
        self,
        subscription_id: str,
        addresses: Iterable[str],
        *, expected_generation: int | None = None,
    ) -> None:
        """Subscribe a WebMI subscription to addresses."""
        unique_addresses = list(dict.fromkeys(addresses))
        if not unique_addresses:
            return

        response = await self._session_request(
            "subscribedata",
            data=[("subscriptionid", subscription_id)]
            + [("address[]", address) for address in unique_addresses],
            expected_generation=expected_generation,
        )
        self._raise_for_session_error(response)
        top_error = response.get("error")
        if top_error not in (None, 0):
            raise WebMIError(
                "WebMI subscribedata returned top-level error "
                f"{top_error}: {response.get('errorstring')}"
            )
        result_items = response.get("result")
        if not isinstance(result_items, list) or len(result_items) != len(unique_addresses):
            result_count = len(result_items) if isinstance(result_items, list) else 0
            raise WebMIError(
                "WebMI subscribedata returned an incomplete result batch "
                f"({result_count}/{len(unique_addresses)} values)"
            )
        errors = [
            (address, item)
            for address, item in zip(unique_addresses, result_items, strict=False)
            if isinstance(item, dict) and item.get("error") not in (None, 0)
        ]
        if errors:
            address, item = errors[0]
            raise WebMIError(
                "WebMI subscribedata failed for "
                f"{address}: {item.get('error')} {item.get('errorstring')}"
            )

    async def publish_subscription(
        self, timeout: int = 65, *, expected_generation: int | None = None
    ) -> list[WebMISubscriptionEvent]:
        """Wait for subscribed WebMI value changes."""
        response = await self._session_request(
            "publish",
            data={"maxresults": "100"},
            timeout=ClientTimeout(total=timeout),
            expected_generation=expected_generation,
        )
        self._raise_for_session_error(response)
        top_error = response.get("error")
        if top_error not in (None, 0):
            raise WebMIError(
                "WebMI publish returned top-level error "
                f"{top_error}: {response.get('errorstring')}"
            )
        result_items = response.get("result") or []
        if not isinstance(result_items, list):
            raise WebMIError("WebMI publish returned a non-list result")

        events: list[WebMISubscriptionEvent] = []
        for item in result_items:
            if not isinstance(item, dict):
                continue
            address = item.get("address")
            if not address:
                continue
            events.append(
                WebMISubscriptionEvent(
                    address=address,
                    result=WebMIReadResult(
                        value=item.get("value"),
                        error=item.get("error", 0),
                        errorstring=item.get("errorstring"),
                        timestamp=item.get("timestamp"),
                        status=item.get("status"),
                    ),
                )
            )
        return events

    async def delete_subscription(
        self, subscription_id: str, *, expected_generation: int | None = None
    ) -> None:
        """Best-effort delete of a WebMI subscription."""
        if not self._sessionid:
            return
        response = await self._session_request(
            "deletesubscription",
            data={"subscriptionid": subscription_id},
            expected_generation=expected_generation,
        )
        self._raise_for_session_error(response)

    async def _read_addresses_once(self, addresses: list[str]) -> dict[str, Any]:
        """Read addresses once with the current or a newly created session."""
        return await self._session_request(
            "read",
            data=[("address[]", address) for address in addresses],
        )

    async def _write_addresses_once(
        self,
        addresses: list[str],
        values: list[Any],
    ) -> dict[str, Any]:
        """Write addresses once with the current or a newly created session."""
        return await self._session_request(
            "write",
            data=[
                item
                for address, value in zip(addresses, values, strict=True)
                for item in (("address[]", address), ("value[]", str(value)))
            ],
        )

    @staticmethod
    def _should_retry_read(response: dict[str, Any], expected_count: int) -> bool:
        """Return whether a read response looks like a stale-session batch."""
        top_error = response.get("error")
        if top_error not in (None, 0):
            return top_error in SESSION_ERRORS

        result_items = response.get("result")
        if not isinstance(result_items, list) or len(result_items) != expected_count:
            return False

        if any(isinstance(item, dict) and item.get("error") in SESSION_ERRORS for item in result_items):
            return True

        return False

    @staticmethod
    def _should_retry_write(response: dict[str, Any], expected_count: int) -> bool:
        """Return whether a write response looks like a stale-session batch."""
        top_error = response.get("error")
        if top_error not in (None, 0):
            return top_error in SESSION_ERRORS

        result_items = response.get("result")
        if result_items is None:
            return False
        if not isinstance(result_items, list) or len(result_items) != expected_count:
            return False
        if any(isinstance(item, dict) and item.get("error") in SESSION_ERRORS for item in result_items):
            return True

        return False

    @staticmethod
    def _raise_for_invalid_read_response(
        response: dict[str, Any],
        expected_count: int,
    ) -> None:
        """Raise when a read response cannot be mapped safely to addresses."""
        top_error = response.get("error")
        if top_error not in (None, 0):
            raise WebMIError(
                "WebMI read returned top-level error "
                f"{top_error}: {response.get('errorstring')}"
            )

        result_items = response.get("result")
        if not isinstance(result_items, list) or len(result_items) != expected_count:
            result_count = len(result_items) if isinstance(result_items, list) else 0
            raise WebMIError(
                "WebMI read returned an incomplete result batch "
                f"({result_count}/{expected_count} values)"
            )

    @staticmethod
    def _raise_for_invalid_write_response(
        response: dict[str, Any],
        expected_count: int,
    ) -> None:
        """Raise when a write response reports failure."""
        top_error = response.get("error")
        if top_error not in (None, 0):
            raise WebMIError(
                "WebMI write returned top-level error "
                f"{top_error}: {response.get('errorstring')}"
            )

        result_items = response.get("result")
        if result_items is None:
            raise WebMIError("WebMI write returned no item acknowledgement")
        if not isinstance(result_items, list) or len(result_items) != expected_count:
            result_count = len(result_items) if isinstance(result_items, list) else 0
            raise WebMIError(
                "WebMI write returned an incomplete result batch "
                f"({result_count}/{expected_count} values)"
            )

        for item in result_items:
            if not isinstance(item, dict) or item.get("error") is None:
                raise WebMIError("WebMI write returned an invalid item acknowledgement")
            if isinstance(item, dict) and item.get("error") not in (None, 0):
                raise WebMIError(
                    "WebMI write returned item error "
                    f"{item.get('error')}: {item.get('errorstring')}"
                )

    async def discover_addresses(self) -> list[str]:
        """Discover visible WebMI addresses by crawling the SVG menu tree."""
        displays_payload = await self._get_text("/de/svg/displays.js")
        displays = json.loads(displays_payload)
        display_ids = self._iter_display_ids(displays.get("menu", []))
        addresses: set[str] = set()

        for display_id in sorted(display_ids):
            try:
                svg_text = await self._get_text(f"/de/svg/{display_id}.svg")
            except WebMIError as err:
                _LOGGER.debug("Could not fetch WebMI display %s: %s", display_id, err)
                continue
            addresses.update(ADDRESS_RE.findall(svg_text))

        return sorted(addresses)

    def reset_session(self) -> None:
        """Invalidate locally and retain old credentials only for cleanup."""
        if self._sessionid and self._secret:
            self._retired_sessions.append(self._x_webmi_header())
        self._sessionid = None
        self._secret = None
        self._cnonce = 1
        self._session_generation += 1

    async def async_reset_session(self, *, expected_generation: int | None = None) -> None:
        """Retire this generation without invalidating a newer session."""
        if expected_generation is None or expected_generation == self._session_generation:
            self.reset_session()
        await self._cleanup_retired_sessions()

    async def _cleanup_retired_sessions(self) -> None:
        async with self._cleanup_lock:
            while self._retired_sessions:
                headers = self._retired_sessions.pop(0)
                try:
                    response = await self._post_json(
                        "deletesession", headers=headers, timeout=ClientTimeout(total=5),
                    )
                    if response.get("error") not in (None, 0) or any(
                        isinstance(item, dict) and item.get("error") not in (None, 0)
                        for item in (response.get("result") or [])
                    ):
                        _LOGGER.warning("WebMI session cleanup rejected; server expiry may be needed")
                except asyncio.CancelledError:
                    self._retired_sessions.insert(0, headers)
                    raise
                except WebMIError:
                    _LOGGER.warning("Could not retire WebMI session; server expiry may be needed")

    async def async_close(self) -> None:
        """Stop future requests and retire sessions, including an in-flight creation."""
        self._closed = True
        self.reset_session()
        async with self._session_lock:
            await self._cleanup_retired_sessions()

    async def _ensure_session(self) -> None:
        async with self._session_lock:
            if self._closed:
                raise WebMIError("WebMI client is closed")
            while not (self._sessionid and self._secret):
                if self._closed:
                    raise WebMIError("WebMI client is closed")
                await self._cleanup_retired_sessions()
                if self._closed:
                    raise WebMIError("WebMI client is closed")
                generation = self._session_generation
                info = await self.info()
                modulus = int(info["encryptionmodulus"], 16)
                exponent = int(info["encryptionexponent"], 16)
                secret = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))
                response = await self._post_json(
                    "createsession",
                    data={"cipher": self._rsa_pkcs1_v15_encrypt(secret, modulus, exponent)},
                )
                session_id = response["sessionid"]
                if generation != self._session_generation:
                    self._retired_sessions.append(self._make_header(session_id, secret, 2))
                    continue
                self._sessionid = session_id
                self._secret = secret
                self._cnonce = 1
                self._session_generation += 1

    async def _session_request(self, command, data=None, timeout=None, expected_generation=None):
        await self._ensure_session()
        generation = self._session_generation
        if expected_generation is not None and expected_generation != generation:
            raise WebMISessionChanged("WebMI subscription session changed")
        response = await self._post_json(
            command, data=data, headers=self._x_webmi_header(), timeout=timeout,
        )
        if generation != self._session_generation:
            raise WebMISessionChanged("Discarded response from retired WebMI session")
        return response

    @staticmethod
    def _raise_for_session_error(response):
        if response.get("error") in SESSION_ERRORS:
            raise WebMISessionError("WebMI rejected session/authentication")

    def _x_webmi_header(self) -> dict[str, str]:
        if not self._sessionid or not self._secret:
            raise WebMIError("WebMI session is not initialized")

        self._cnonce += 1
        return self._make_header(self._sessionid, self._secret, self._cnonce)

    @staticmethod
    def _make_header(session_id: str, secret: str, nonce: int) -> dict[str, str]:
        digest = hashlib.md5(
            f"{session_id}:{secret}:{nonce}".encode()
        ).hexdigest()
        return {
            "X-WebMI": (
                f'sessionid="{session_id}", '
                f'cnonce="{nonce}", '
                f'digest="{digest}"'
            )
        }

    async def _post_json(
        self,
        command: str,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: ClientTimeout | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/webMI/?{command}"
        try:
            async with self._session.post(
                url,
                data=data,
                headers=headers,
                timeout=timeout or self._timeout,
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except TimeoutError as err:
            raise WebMITimeout(f"WebMI POST {command} timed out") from err
        except (ClientError, json.JSONDecodeError) as err:
            raise WebMIError(f"WebMI POST {command} failed: {err}") from err

    async def _get_text(self, path: str) -> str:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(url, timeout=self._timeout) as response:
                response.raise_for_status()
                return await response.text()
        except ClientError as err:
            raise WebMIError(f"WebMI GET {path} failed: {err}") from err

    @staticmethod
    def _iter_display_ids(menu_items: list[dict[str, Any]]) -> set[str]:
        found: set[str] = set()
        stack = list(menu_items)
        while stack:
            item = stack.pop()
            display = item.get("display")
            if display:
                found.add(str(display))
            stack.extend(item.get("sub", []))
        return found

    @staticmethod
    def _rsa_pkcs1_v15_encrypt(text: str, modulus: int, exponent: int) -> str:
        payload = text.encode("utf-8")
        key_length = (modulus.bit_length() + 7) // 8
        padding_length = key_length - len(payload) - 3
        if padding_length < 8:
            raise WebMIError("Invalid WebMI RSA key length")

        padding = bytearray()
        while len(padding) < padding_length:
            value = secrets.randbelow(255) + 1
            padding.append(value)

        message = b"\x00\x02" + bytes(padding) + b"\x00" + payload
        encrypted = pow(int.from_bytes(message, "big"), exponent, modulus)
        return encrypted.to_bytes(key_length, "big").hex()
