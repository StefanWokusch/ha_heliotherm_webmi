# Heliotherm WebMI for Home Assistant

Read-only Home Assistant custom integration for Heliotherm RCG/WebMI controllers.

This integration uses the local WebMI API behind the controller web UI. It is
intentionally read-only: it creates no `select`, `number`, `switch`, or
`climate` entities and does not call WebMI `write`.

## Current scope

- Local polling via HTTP `POST /webMI/?read`
- Anonymous WebMI session creation
- Curated diagnostic sensors and binary sensors
- Home Assistant diagnostics download with an on-demand full WebMI snapshot
- No Modbus dependency
- No write/control support

## Installation

Copy `custom_components/ha_heliotherm_webmi` into the Home Assistant
`custom_components` directory, then restart Home Assistant.

Add the integration from the UI:

1. Settings
2. Devices & services
3. Add integration
4. Heliotherm WebMI

Use the controller IP or hostname, for example `192.168.0.131`.

## Data updates

The integration polls enabled entities every `60` seconds by default. It uses a
single coordinator and batches WebMI addresses into one read request per update.
Entities that are disabled in Home Assistant are not polled during normal
updates.

The Home Assistant diagnostics download performs a separate on-demand crawl of
the visible WebMI SVG pages and reads all discovered addresses. This is intended
for investigation snapshots, not normal polling.

## Safety

The first version is deliberately read-only. It never calls WebMI `write` and
does not expose Home Assistant controls that can change heat pump settings.

