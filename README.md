# Heliotherm WebMI for Home Assistant

Read-only Home Assistant custom integration for Heliotherm RCG/WebMI controllers.

This integration uses the local WebMI API behind the controller web UI. It is
intentionally read-only: it creates no `select`, `number`, `switch`, or
`climate` entities and does not call WebMI `write`.

## Why this exists

This project was started after problems with the existing Heliotherm control
path in this installation. The current working suspicion is that enabling the
external Smartboss/Smart Grid/Modbus-style control path can change how the
Heliotherm controller interprets requests and may disturb normal programmed
behavior.

For that reason this integration is intentionally a separate WebMI read path.
The first goal is to observe the controller safely through the same local API
used by the web UI, without changing heat pump settings. Write/control support
is out of scope until the read-only entities are stable and the controller
behavior is understood better.

## Current scope

- Local polling via HTTP `POST /webMI/?read`
- Anonymous WebMI session creation
- Small default-enabled sensor set for normal observation
- Curated diagnostic sensors and binary sensors
- Generated disabled-by-default catalogue for all known successful WebMI reads,
  using recovered WebMI UI labels where available
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

The default-enabled entity set is intentionally focused on normal observation:
outside temperature, main flow/return/buffer temperatures, Mischer1 flow
temperature, observed mixer percentage, current demand/mode/status, compressor
and lock/request binary states, current thermal/electrical power, COP, WMZ flow,
and compressor request. Deeper service, room, setting, counter, actuator, and
unknown WebMI points are present in the entity registry but disabled by default.
Enable individual diagnostics in Home Assistant only when you want them polled.

The Home Assistant diagnostics download performs a separate on-demand crawl of
the visible WebMI SVG pages and reads all discovered addresses. This is intended
for investigation snapshots, not normal polling.

## Safety

The first version is deliberately read-only. It never calls WebMI `write` and
does not expose Home Assistant controls that can change heat pump settings.
