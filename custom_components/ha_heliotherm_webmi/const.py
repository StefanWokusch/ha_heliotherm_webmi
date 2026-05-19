"""Constants for the Heliotherm WebMI integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "ha_heliotherm_webmi"

ATTR_MANUFACTURER = "Heliotherm"
DEFAULT_NAME = "Heliotherm WebMI"
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15

CONF_SCAN_INTERVAL = "scan_interval"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

