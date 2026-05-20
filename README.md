# Heliotherm WebMI for Home Assistant

Home Assistant custom integration for Heliotherm RCG/WebMI controllers.

This integration uses the local WebMI API behind the controller web UI. It
started as a read-only observer and now exposes a deliberately small set of
user-facing write controls. The write controls can be disabled in the
integration options.

## Why this exists

This project was started after problems with the existing Heliotherm control
path in this installation. The current working suspicion is that enabling the
external Smartboss/Smart Grid/Modbus-style control path can change how the
Heliotherm controller interprets requests and may disturb normal programmed
behavior.

For that reason this integration is intentionally a separate WebMI path. The
first goal was to observe the controller safely through the same local API used
by the web UI, without changing heat pump settings. Write/control support starts
small: only selected user-facing WebMI controls are exposed,
while service, heating-curve, pump, compressor, lock, reset, and raw diagnostic
values stay read-only.

## Current scope

- Live local updates via WebMI `subscribedata` + `publish`
- Fallback polling via HTTP `POST /webMI/?read`
- Anonymous WebMI session creation
- Small default-enabled sensor set for normal observation
- Curated diagnostic sensors and binary sensors
- Generated disabled-by-default catalogue for all known successful WebMI reads,
  using recovered WebMI UI labels where available
- Two clearly marked calculated setpoint sensors for the heating dashboard
- Calculated total SCOP matching the WebMI efficiency page
- Home Assistant diagnostics download with an on-demand full WebMI snapshot
- Write controls for a small user-facing set:
  - `Betriebsart setzen`
  - `Raum Soll`
  - `Warmwasser Soll Norm`
  - `Warmwasser Soll Min`
- No Modbus dependency

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

The integration uses WebMI live updates by default. It creates a read-only
WebMI session, subscribes only the addresses required by enabled Home Assistant
entities, and waits for value changes through WebMI `publish` long-poll. This
is the live-update mechanism used by the WebMI API on this controller; direct
WebSocket support was probed but is not active on the current installation.

The existing batched `read` path remains as a fallback. With live updates
enabled, the configured polling interval is treated as the fallback full-read
interval and is clamped to at least `300` seconds. If live updates are disabled
in the integration options, the integration behaves as a normal polling
integration and uses the configured polling interval directly.

Entities that are disabled in Home Assistant are not subscribed or polled during
normal updates.

Write-capable Home Assistant entities are created for the current small write
scope: Betriebsart, Raum Soll, and Warmwasser Sollwerte. The write controls can
be disabled in the integration options. The Warmwasser controls are present but
disabled by default. There is no fault acknowledge button and no write access to
heating-curve parameters, pump hand-values, compressor request, EVU/external
request, reset counters, or other service points.

The default-enabled entity set is intentionally focused on normal observation:
outside temperature, main flow/return/buffer temperatures, Mischer1 flow
temperature, observed mixer percentage, current demand/mode/status, readable
compressor/fault/lock/request states, current thermal/electrical power, COP,
calculated total SCOP, WMZ flow, Heizstab operation, compressor request, and
the calculated heating setpoints. Deeper service, room, setting, counter,
actuator, and unknown WebMI points are present in the entity registry but
disabled by default. Enable individual diagnostics in Home Assistant only when
you want them polled.

Entity categories follow the Home Assistant convention: normal user-facing
values are plain sensors, while controller internals, raw generated points,
service parameters, uncertain values, and support/debug fields are marked as
diagnostic. Useful but currently non-dashboard values, including Warmwasser
temperature/energy and user-facing generated setpoints, are kept as normal
sensors but disabled by default.

The Home Assistant diagnostics download performs a separate on-demand crawl of
the visible WebMI SVG pages and reads all discovered addresses. This is intended
for investigation snapshots, not normal polling.

`EQ Luefter Istwert` uses the live WebMI value `webregler/mp/248/value`. Nearby
EQA02 `sp/*` values such as `SP3327=40%` are configuration parameters from the
same controller page, not the current fan output.

## Calculated setpoints

The controller WebMI read API does not expose the current calculated `Ruecklauf
Soll` / `Heizkreis Soll` values as direct readable addresses. The integration
therefore exposes two values with `berechnet` in the entity name:

- `Ruecklauf Soll berechnet`
- `Heizkreis Soll berechnet`

They are derived from the visible heating-curve parameters, the delayed outside
temperature, and the `Aufheiztemp` offset:

```text
Ruecklauf Soll berechnet = HKR curve(Aussentemperatur verzoegert) + HKR Aufheiztemp
Heizkreis Soll berechnet = Mischer1 curve(Aussentemperatur verzoegert) + Mischer1 Aufheiztemp
```

This matched retained Modbus snapshots and one physical display check closely,
but it remains an inferred value, not a direct WebMI value. The entity attributes
include `source=calculated`, the formula, and the dependency keys.

## Calculated SCOP

The WebMI efficiency page does not expose `SCOP` as its own readable WebMI
address in the local snapshots. The displayed `SCOP Gesamt` matches the ratio
of the cumulative total energy counters:

```text
SCOP Gesamt berechnet = Thermische Energie Gesamt / Elektrische Energie Gesamt
```

Example from the `2026-05-19 21:17` read-only snapshot:
`2016.4 kWh / 375.8 kWh = 5.3656`, displayed by WebMI as `5.4`.

## Write safety

Every Home Assistant control writes one explicitly mapped WebMI address and then
requests an immediate readback refresh. The write scope is kept deliberately
narrow; deeper service and control-loop parameters remain read-only until they
are understood and tested separately.
