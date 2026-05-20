"""Constants for the Heliotherm WebMI integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "ha_heliotherm_webmi"

ATTR_MANUFACTURER = "Heliotherm"
DEFAULT_NAME = "Heliotherm WebMI"
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_SUBSCRIPTION_FALLBACK_INTERVAL = 300
DEFAULT_USE_SUBSCRIPTIONS = True
DEFAULT_ENABLE_WRITES = False
MIN_SCAN_INTERVAL = 15

CONF_ENABLE_WRITES = "enable_writes"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_USE_SUBSCRIPTIONS = "use_subscriptions"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT, Platform.NUMBER]
