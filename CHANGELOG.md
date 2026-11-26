# Changelog

## 0.1.35 — 2026-11-26

- Read the phase timer on startup, reconnection and phase changes. Check it hourly and once when a countdown is expected to expire. Only the phase is subscribed.
- The existing timer sensor retains the last observed seconds and exposes the observation time, phase and applicable running start or countdown end as UTC timestamp attributes.

## 0.1.34 — 2026-11-26

- Default to read-only minimal heating monitoring for both new and existing entries.
- Resolve addresses from registered listeners before the first read and export diagnostics from cache.
- Log read and subscription selections, transport errors, generations, timeouts and reconnect delays at debug level.

## 0.1.33 — 2026-11-25

- Report unconfirmed session and subscription creation or cleanup, subscription retries and recovery in the standard HA log. Successful lifecycle requests are logged at debug level. Routine long-poll timeouts remain quiet.

## 0.1.32 — 2026-11-25

- Add a heating room target control for SP369, adjustable from 10 to 25 °C in 0.5 °C steps. The existing mixer 1 room target uses SP3200.

## 0.1.31 — 2026-11-19

- Read heating/buffer and mixer 1 targets directly from MP257 and MP266; remove both calculated target entities and their curve approximations.
- Correct pump, mixer, Vortex and energy labels, diagnostic units and the heating-pump mode enumeration while preserving existing entity keys and addresses.
- Add four optional read-only hand-mode/hand-value diagnostics for AO1 and the mixer 1 pump.
- Enable AO1 output and Vortex 2 flow by default for new registrations; keep unused domestic-hot-water, solar and mixer 2 diagnostics disabled by default.
- Keep schedules outside the normal entity set and preserve the existing transport and write-control scope.

Migration: Replace dashboard references to `ruecklauf_soll_berechnet` and `heizkreis_soll_berechnet` with the native controller targets. Existing entity-registry enable/disable choices remain unchanged.

Validation: 23 network-free tests pass. No live Home Assistant installation or controller configuration change was performed for this release.

## 0.1.30 — 2026-11-14

- Serialize session initialization and bind subscriptions to their session generation.
- Discard stale responses and rebuild subscriptions after a shared-session change.
- Clean up failed subscriptions and retired sessions; back off repeated failures.
- Prevent closed clients from reopening sessions during concurrent initialization or cleanup.
- Log every explicit parameter-write attempt and outcome with UTC time, request ID, address, value, and available HA context. Authentication data is excluded.
- Treat timeouts, cancellation and missing write acknowledgements as unknown outcomes; do not blindly retry them.
- Validate numeric inputs locally for finite values and allowed range.

Validation: 18 network-free tests of production method bodies, plus syntax and whitespace checks. No live controller test or Home Assistant installation was performed for this release. These fixes do not establish the cause of earlier controller lockouts or heating-curve changes.

See [WRITE_AUDIT.md](WRITE_AUDIT.md) for log outcomes, retention and attribution limits.
