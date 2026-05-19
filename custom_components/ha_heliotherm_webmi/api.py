"""Async client for the local Heliotherm WebMI API."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import re
import secrets
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

ADDRESS_RE = re.compile(r"webregler/(?:sp|mp)/\d+/value|mcg/data/[A-Za-z0-9_/]+")


class WebMIError(Exception):
    """Base exception for WebMI errors."""


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


class HeliothermWebMIClient:
    """Small read-only WebMI client."""

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
            self.reset_session()
            response = await self._read_addresses_once(unique_addresses)

        self._raise_for_invalid_read_response(response, len(unique_addresses))
        result_items = response.get("result") or []

        return {
            address: WebMIReadResult.from_payload(item)
            for address, item in zip(unique_addresses, result_items, strict=False)
        }

    async def _read_addresses_once(self, addresses: list[str]) -> dict[str, Any]:
        """Read addresses once with the current or a newly created session."""
        await self._ensure_session()
        return await self._post_json(
            "read",
            data=[("address[]", address) for address in addresses],
            headers=self._x_webmi_header(),
        )

    @staticmethod
    def _should_retry_read(response: dict[str, Any], expected_count: int) -> bool:
        """Return whether a read response looks like a stale-session batch."""
        top_error = response.get("error")
        if top_error not in (None, 0):
            return True

        result_items = response.get("result")
        if not isinstance(result_items, list) or len(result_items) != expected_count:
            return True

        if any(item.get("error") == 454 for item in result_items):
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
        """Forget the local WebMI session."""
        self._sessionid = None
        self._secret = None
        self._cnonce = 1

    async def _ensure_session(self) -> None:
        if self._sessionid and self._secret:
            return

        info = await self.info()
        modulus = int(info["encryptionmodulus"], 16)
        exponent = int(info["encryptionexponent"], 16)
        secret = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))
        response = await self._post_json(
            "createsession",
            data={"cipher": self._rsa_pkcs1_v15_encrypt(secret, modulus, exponent)},
        )
        self._sessionid = response["sessionid"]
        self._secret = secret
        self._cnonce = 1

    def _x_webmi_header(self) -> dict[str, str]:
        if not self._sessionid or not self._secret:
            raise WebMIError("WebMI session is not initialized")

        self._cnonce += 1
        digest = hashlib.md5(
            f"{self._sessionid}:{self._secret}:{self._cnonce}".encode()
        ).hexdigest()
        return {
            "X-WebMI": (
                f'sessionid="{self._sessionid}", '
                f'cnonce="{self._cnonce}", '
                f'digest="{digest}"'
            )
        }

    async def _post_json(
        self,
        command: str,
        data: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/webMI/?{command}"
        try:
            async with self._session.post(
                url,
                data=data,
                headers=headers,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, json.JSONDecodeError) as err:
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
