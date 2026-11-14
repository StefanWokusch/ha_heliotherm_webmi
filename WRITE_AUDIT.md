# Write audit and session lifecycle

Included in version 0.1.30; installation in Home Assistant is a separate step. No live device test has been performed for these changes.

## Write records

All explicit `write_address` requests emit structured JSON to the normal HA log under
`custom_components.ha_heliotherm_webmi.api.write_audit`, with the marker `WEBMI_WRITE_AUDIT`.
They use **WARNING** deliberately, so successful writes are retained by HA's usual default logging level without requiring DEBUG. A custom logging configuration can still suppress them. This is not an independent or tamper-proof journal; retention follows HA/container log retention.

Each record contains UTC time, request ID, attempt number, address, value and outcome.
Number/select controls attach entity ID and available HA context ID, parent ID and user ID.
Missing context stays null. Context is correlation metadata, not proof of a named human or whether an automation caused the action.
Session IDs, authentication secrets, digests, nonces, response bodies and cookies are not logged.

Outcomes:

- `attempt`: the caller requested a write; this does not prove transmission.
- `acknowledged`: the server returned explicit successful item acknowledgement; this does not independently verify a physical/controller state change.
- `session_rejected_retry`: authentication/session rejection, followed by at most one repeat with the same requested value and request ID.
- `timeout_outcome_unknown`, `cancelled_outcome_unknown`, `session_changed_outcome_unknown`, `error_outcome_unknown`: do not assume the controller either applied or rejected the request. Timeouts, malformed acknowledgements and transport failures are not blindly retried.

Reads, publishes and subscription management do not produce parameter-write audit records.
The audit describes this plugin only; it does not record browser, Modbus, service or other clients, and cannot reconstruct historical writes before installation.

## Lifecycle changes

- Single-flight session creation with an asyncio lock.
- Session generation binds subscriptions and discards responses from retired sessions.
- Another caller replacing the shared session forces a fresh subscription binding without resetting the newer session.
- Explicit best-effort session deletion on retirement/unload; deletion is limited to five seconds. Server expiry may still be necessary if cleanup is rejected or unreachable.
- Cleanup of subscriptions whose address registration failed; backoff of10/20/40/80/160/300 seconds for repeated errors. Non-session errors no longer automatically create a new session.
- Closed clients cannot reopen sessions, including during an in-flight creation/cleanup.
- Number setters independently reject nonfinite and out-of-range values.

## Offline verification

Run with a standard Python installation, without HA or network access:

```text
python tests/test_session_and_write_audit.py -v
```

The suite executes production method definitions with dummy HA classes and a transport that forbids real network access. It covers session races/rebinding/cleanup, cancellation, retry limits, write audit/context/redaction, and number/select input guards. It does not establish real device compatibility or explain earlier heating-curve changes/lockouts.
