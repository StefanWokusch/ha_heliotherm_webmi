# Changelog

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
