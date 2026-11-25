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
while service, heating-curve, pump, compressor, reset, and raw diagnostic values
stay read-only.

## Current scope

- Live local updates via WebMI `subscribedata` + `publish`
- Fallback polling via HTTP `POST /webMI/?read`
- Anonymous WebMI session creation
- Small default-enabled sensor set for normal observation
- Curated diagnostic sensors and binary sensors
- Generated disabled-by-default catalogue for all known successful WebMI reads,
  using recovered WebMI UI labels where available
- Native controller heating/buffer and mixer-flow targets; no estimated target entities
- Calculated total SCOP matching the WebMI efficiency page
- Home Assistant diagnostics download with an on-demand full WebMI snapshot
- Write controls for a small user-facing set:
  - Operating mode (`Betriebsart setzen`)
  - Heating room target (`Raum Soll Heizung`, SP369) and mixer 1 room target (`Raum Soll`, SP3200)
  - Normal domestic hot water target (`Warmwasser Soll Norm`)
  - Minimum domestic hot water target (`Warmwasser Soll Min`)
- No Modbus dependency

## Installation

Copy `custom_components/ha_heliotherm_webmi` into the Home Assistant
`custom_components` directory, then restart Home Assistant.

Add the integration from the UI:

1. Settings
2. Devices & services
3. Add integration
4. Heliotherm WebMI

Enter your controller's local IP address or hostname. Use the address assigned
to your own controller; there is no predefined address.

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
scope: operating mode, room temperature target, and domestic hot water targets.
The write controls can be disabled in the integration options. The domestic hot
water controls are present but
disabled by default. There is no fault acknowledge button and no write access to
heating-curve parameters, pump hand-values, compressor request, EVU/external
request, reset counters, or other service points.

The default-enabled entity set is intentionally focused on normal observation:
outside temperature, main flow/return/buffer temperatures, mixer 1 flow
temperature, observed mixer percentage, current demand/mode/status, readable
compressor/fault/request states, current thermal/electrical power, COP,
calculated total SCOP, heat meter flow, electric backup heater operation, compressor request, and
the native controller heating/buffer and mixer 1 flow targets. Deeper service, room, setting, counter,
actuator, and unknown WebMI points are present in the entity registry but
disabled by default. Enable individual diagnostics in Home Assistant only when
you want them polled.

Entity categories follow the Home Assistant convention: normal user-facing
values are plain sensors, while controller internals, raw generated points,
service parameters, uncertain values, and support/debug fields are marked as
diagnostic. Useful but currently non-dashboard values, including domestic hot water
temperature/energy and user-facing generated setpoints, are kept as normal
sensors but disabled by default.

The Home Assistant diagnostics download performs a separate on-demand crawl of
the visible WebMI SVG pages and reads all discovered addresses. This is intended
for investigation snapshots, not normal polling.

`EQ Luefter Istwert` uses the live WebMI value `webregler/mp/248/value`. Nearby
EQA02 `sp/*` values such as `SP3327=40%` are configuration parameters from the
same controller page, not the current fan output.

`EVU Eingang` uses `webregler/mp/237/value` from the WebMI service page
`Gesamtdaten > EinAusgang > EingDigital > EVUSperre`. On the observed
installation this input can stay `aktiv` while the compressor is running, so it
is not the compressor restart lockout / `Sperrzeit` shown after a run. It is
kept as a disabled-by-default diagnostic input, not as a normal dashboard lock
state.

`Mischerpumpe` uses the visible WebMI state `webregler/mp/265/value` from
`Gesamtdaten > EinAusgang > AusgDigital > Mischerpumpe` and is the best-known
on/off state for the active mixed heating circuit pump on the observed
installation. The separate `Heizkreispumpe WP Ausgang` value uses
`webregler/mp/222/value` from `AusgDigital > Heizkreispumpe` and is kept as a
disabled-by-default diagnostic because it does not reliably describe the
dashboard heating-circuit pump in this setup. The separate `HKPA01
Analogausgang` value uses `webregler/mp/247/value` from `AusgAnalog > HKPA01`;
it is a percentage output and must not be displayed as the simple on/off
heating-circuit pump state. It is kept disabled by default as a diagnostic
value until its exact physical pump/actuator mapping is confirmed.

`Kondensatordruck` and `Verdampferdruck` use the WebMI pressure values from
`Service > Sicherheitskette`: `webregler/mp/221/value` for condensate/condenser
pressure and `webregler/mp/220/value` for evaporator pressure. Older candidate
points such as `MP21` and `SP3308` are not used for the dashboard pressure
cards because live WebMI display checks showed that they do not match the
visible pressure pages on this installation.

## Direct controller setpoints

`Heizen Soll` reads `webregler/mp/257/value`; `Mischer1 Soll` reads
`webregler/mp/266/value`. Both are enabled by default. On2026-11-07 the native
touchdisplay showed46.0/49.6 C at room target25 C, matching nearby direct reads
46.1/49.7 C. These values include the controller's own room/operating corrections.
They are read-only sensors; no controller setting is changed.

## Removed calculated setpoints

The old `ruecklauf_soll_berechnet` and `heizkreis_soll_berechnet` entities and
their curve-estimation code have been removed at the owner's request. Use the
existing native `heizen_soll` (MP257) and `mischer1_soll` (MP266) sensors instead.
No recorder/history data is deleted. Existing dashboard cards referencing the
removed entities need to select the native target sensors during deployment.

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


## Curated monitoring update

The normal observation set has 27 default-enabled sensor/binary-sensor entities.
It uses MP257 for the controller heating/buffer target and MP266 for the mixer1
flow target. Those values are read directly and never replaced by a locally
calculated curve. The two old curve-calculation entities are removed; only native targets are exposed.

Four new read-only diagnostics are optional, not control entities:

| Key | Address | Meaning |
|---|---|---|
| hkpa01_handwert | webregler/mp/247/handVal | Stored AO1 manual percentage |
| hkpa01_handbetrieb | webregler/mp/247/handAkt | AO1 manual override enabled |
| mischer1_pumpe_handwert | webregler/mp/265/handVal | Stored mixer1 pump on/off target |
| mischer1_pumpe_handbetrieb | webregler/mp/265/handAkt | Mixer1 pump manual override enabled |

AO1 output MP247 and WP-side Vortex2 flow MP2105 are enabled by default for new
entity registrations. Native targets, WP and mixer temperatures, electrical and
thermal power, compressor request and operating states form the useful normal
profile. AO1 minimum/target-spread/PID settings, Vortex sensor types and meter
factors are existing optional diagnostics; their corrected labels and units do
not create new entities. Solar thermal, mixer2, DHW/FWS/circulation and other
unused legacy diagnostics remain disabled by default. No time-program addresses
or full snapshot inventory are imported into normal monitoring.

Apart from the two explicitly removed curve-estimation keys, existing keys, unique-ID construction and addresses are preserved. History is not purged.
Legacy registry diagnostics remain available for compatibility. HA remembers
the enabled/disabled status of existing entities: changing a registration default
does not override an existing user's registry choices. A later deployment must
explicitly select the intended entities and replace old calculated dashboard
targets with the two existing native target sensors. No history purge is needed.

SP3294 is the HKP EVU setting; SP337 is its operating mode (off/saving pulse/
pulse/continuous). Their legacy entity keys remain unchanged. MP268 is a mixer
command, not a measured valve position; MP247/248 are output commands, not
measured motor speeds. AO4 has no confirmed address and is not added. The four
existing user-facing write controls are unchanged; no pump/service writes are
introduced.
