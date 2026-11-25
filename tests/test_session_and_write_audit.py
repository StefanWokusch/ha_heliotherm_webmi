"""Network-free tests of production method bodies (stdlib, no HA installation)."""
import ast
import asyncio
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import logging
import math
from pathlib import Path
import re
import secrets
import sys
import types
import unittest
from urllib.parse import urlparse

SRC = Path(__file__).resolve().parents[1] / 'custom_components/ha_heliotherm_webmi'

class NoNetwork:
    def __getattr__(self, name):
        raise AssertionError('Real HTTP forbidden: ' + name)

class Timeout:
    def __init__(self, total): self.total = total

class EntityStub: pass
class CoordinatorStub:
    @classmethod
    def __class_getitem__(cls, key): return cls
    def __init__(self, *args, **kwargs): self.data = {}
    def async_set_updated_data(self, value): self.data = value

class HAError(Exception): pass

def load(name, extra=None):
    tree = ast.parse((SRC / name).read_text(encoding='utf-8-sig'))
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    tree.body.insert(0, ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0))
    ast.fix_missing_locations(tree)
    module = types.ModuleType('isolated_' + name.replace('.', '_'))
    sys.modules[module.__name__] = module
    module.__dict__.update(globals())
    module.__dict__.update({'ClientSession': NoNetwork, 'ClientTimeout': Timeout, 'ClientError': OSError})
    module.__dict__.update(extra or {})
    exec(compile(tree, name, 'exec'), module.__dict__)
    return module.__dict__

api = load('api.py')
Client, Error = api['HeliothermWebMIClient'], api['WebMIError']
Changed, SessionError = api['WebMISessionChanged'], api['WebMISessionError']
coord = load('coordinator.py', {**api, 'DataUpdateCoordinator': CoordinatorStub, 'UpdateFailed': HAError, 'DESCRIPTIONS_BY_KEY': {}})
Coord = coord['HeliothermWebMICoordinator']
platform_base = {'NumberEntity': EntityStub, 'SelectEntity': EntityStub, 'HeliothermWebMIEntity': type('Base', (), {}),
                 'WebMIError': Error, 'HomeAssistantError': HAError, 'NUMBER_DESCRIPTIONS': (), 'SELECT_DESCRIPTIONS': (),
                 'CONF_ENABLE_WRITES': 'enable_writes', 'DEFAULT_ENABLE_WRITES': True, 'DOMAIN': 'test', 'number_value': float}
Number = load('number.py', platform_base)['HeliothermWebMINumber']
Select = load('select.py', platform_base)['HeliothermWebMISelect']

class Tests(unittest.IsolatedAsyncioTestCase):
    def client(self):
        c = Client(NoNetwork(), 'offline.invalid')
        c.calls = []
        async def post(command, data=None, headers=None, timeout=None):
            c.calls.append(command)
            if command == 'info': return {'encryptionmodulus': 'ff' * 128, 'encryptionexponent': '10001'}
            if command == 'createsession':
                await asyncio.sleep(0)
                return {'sessionid': 'test-session-' + str(c.calls.count(command))}
            if command == 'deletesession': return {'error': 0}
            return {'result': [{'error': 0}]}
        c._post_json = post
        c._rsa_pkcs1_v15_encrypt = lambda *args: 'test-cipher'
        return c

    def capture_audit(self):
        stream = io.StringIO()
        logger = api['_WRITE_LOGGER']
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        old = logger.propagate
        logger.propagate = False
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(setattr, logger, 'propagate', old)
        return stream

    def records(self, stream):
        return [json.loads(line.split('WEBMI_WRITE_AUDIT ', 1)[1]) for line in stream.getvalue().splitlines()]

    async def test_single_flight_session_initialization(self):
        c = self.client()
        await asyncio.gather(*(c._ensure_session() for _ in range(20)))
        self.assertEqual(c.calls.count('createsession'), 1)

    async def test_lifecycle_failure_messages_identify_operation_and_hide_server_data(self):
        c = self.client()
        await c._ensure_session()
        async def reply(command, **kwargs):
            if command == 'deletesubscription':
                return {'result': [{'error': 301, 'errorstring': 'private-body'}]}
            return {'detail': 'private-body'}
        c._post_json = reply
        with self.assertLogs(api['_LOGGER'], 'WARNING') as logs:
            with self.assertRaises(Error):
                await c.create_subscription()
            with self.assertRaises(Error):
                await c.delete_subscription('private-subscription')
        messages = '\n'.join(logs.output)
        self.assertIn('createsubscription not confirmed (missing ID', messages)
        self.assertIn('deletesubscription not confirmed (controller error 301)', messages)
        for private in ('private-body', 'private-subscription', c._sessionid, c._secret):
            self.assertNotIn(private, messages)

    async def test_lifecycle_timeout_and_ambiguous_cleanup_warn(self):
        c = self.client()
        await c._ensure_session()
        async def reply(command, **kwargs):
            if command == 'createsubscription':
                raise api['WebMITimeout']('private transport detail')
            return {}
        c._post_json = reply
        with self.assertLogs(api['_LOGGER'], 'WARNING') as logs:
            with self.assertRaises(api['WebMITimeout']):
                await c.create_subscription()
            await c.async_close()
        self.assertIn('createsubscription not confirmed (WebMITimeout)', logs.output[0])
        self.assertIn('deletesession returned without explicit cleanup confirmation', logs.output[1])
        self.assertNotIn('private transport detail', str(logs.output))

    async def test_confirmed_lifecycle_uses_debug(self):
        c = self.client()
        with self.assertLogs(api['_LOGGER'], 'DEBUG') as logs:
            await c._ensure_session()
            await c.async_close()
        self.assertEqual([record.levelname for record in logs.records], ['DEBUG', 'DEBUG'])
        self.assertIn('createsession', logs.output[0])
        self.assertIn('deletesession', logs.output[1])

    async def test_stale_inflight_read_is_discarded(self):
        c = self.client(); await c._ensure_session()
        started, release = asyncio.Event(), asyncio.Event(); original = c._post_json
        async def post(command, **kwargs):
            if command == 'read':
                started.set(); await release.wait()
                return {'result': [{'error': 0, 'value': 99}]}
            return await original(command, **kwargs)
        c._post_json = post
        task = asyncio.create_task(c._read_addresses_once(['point']))
        await started.wait(); await c.async_reset_session(); release.set()
        with self.assertRaises(Changed): await task
        self.assertEqual(c.calls.count('deletesession'), 1)

    async def test_reset_does_not_invalidate_newer_generation(self):
        c = self.client(); await c._ensure_session(); old = c.session_generation
        await c.async_reset_session(); await c._ensure_session(); current = c.session_generation
        await c.async_reset_session(expected_generation=old)
        self.assertEqual(c.session_generation, current)
        self.assertIsNotNone(c._sessionid)

    async def test_close_cleans_up_inflight_creation_without_reopening(self):
        c = self.client(); started, release = asyncio.Event(), asyncio.Event(); original = c._post_json
        async def post(command, **kwargs):
            if command == 'createsession': started.set(); await release.wait()
            return await original(command, **kwargs)
        c._post_json = post
        task = asyncio.create_task(c._ensure_session()); await started.wait()
        closing = asyncio.create_task(c.async_close()); await asyncio.sleep(0); release.set()
        with self.assertRaises(Error): await task
        await closing
        self.assertIsNone(c._sessionid)
        self.assertEqual(c.calls.count('createsession'), 1)
        self.assertEqual(c.calls.count('deletesession'), 1)
        with self.assertRaises(Error): await c._ensure_session()

    async def test_rebind_after_shared_session_change(self):
        class Fake:
            session_generation = 1
            def __init__(self): self.created = 0; self.subscribed = 0; self.published = 0; self.resets = 0
            async def create_subscription(self): self.created += 1; return 'sub'
            async def subscribe_addresses(self, *args, **kwargs): self.subscribed += 1
            async def delete_subscription(self, *args, **kwargs):
                if kwargs['expected_generation'] != self.session_generation: raise Changed()
            async def publish_subscription(self, **kwargs):
                self.published += 1
                if self.published == 1: self.session_generation += 1; raise Changed()
                raise asyncio.CancelledError()
            async def async_reset_session(self, **kwargs): self.resets += 1
        a = Fake(); c = Coord(None, a, None); c._active_address_to_keys = lambda: {'point': ['key']}
        with self.assertRaises(asyncio.CancelledError): await c._subscription_loop()
        self.assertEqual((a.created, a.subscribed, a.resets), (2, 2, 0))

    async def test_registration_failure_cleanup_and_backoff(self):
        class Fake:
            session_generation = 1
            def __init__(self): self.created = 0; self.deleted = 0; self.resets = 0
            async def create_subscription(self):
                if self.created == 3: raise asyncio.CancelledError()
                self.created += 1; return 'sub'
            async def subscribe_addresses(self, *args, **kwargs): raise Error('non-session address failure')
            async def delete_subscription(self, *args, **kwargs): self.deleted += 1
            async def async_reset_session(self, **kwargs): self.resets += 1
        waits = []
        async def wait(value): waits.append(value)
        old = coord['asyncio']; coord['asyncio'] = types.SimpleNamespace(sleep=wait, CancelledError=asyncio.CancelledError)
        try:
            a = Fake(); c = Coord(None, a, None); c._active_address_to_keys = lambda: {'point': ['key']}
            with self.assertRaises(asyncio.CancelledError): await c._subscription_loop()
        finally: coord['asyncio'] = old
        self.assertEqual((a.created, a.deleted, a.resets), (3, 3, 0))
        self.assertEqual(waits, [10, 20, 40])

    async def test_nonce_allocation_remains_unique(self):
        c = self.client(); await c._ensure_session()
        headers = [c._x_webmi_header()['X-WebMI'] for _ in range(1000)]
        self.assertEqual(len(set(headers)), 1000)

    async def test_old_binding_cannot_publish_in_new_session(self):
        c = self.client(); await c._ensure_session(); old = c.session_generation
        await c.async_reset_session(); await c._ensure_session()
        with self.assertRaises(Changed): await c.publish_subscription(expected_generation=old)
        self.assertNotIn('publish', c.calls)

    async def test_close_while_cleanup_pending_cannot_reopen(self):
        c = self.client(); await c._ensure_session(); c.reset_session()
        started, release = asyncio.Event(), asyncio.Event(); original = c._post_json
        async def post(command, **kwargs):
            if command == 'deletesession': started.set(); await release.wait()
            return await original(command, **kwargs)
        c._post_json = post
        task = asyncio.create_task(c._ensure_session()); await started.wait()
        closing = asyncio.create_task(c.async_close()); await asyncio.sleep(0); release.set()
        with self.assertRaises(Error): await task
        await closing
        self.assertEqual(c.calls.count('createsession'), 1)
        self.assertIsNone(c._sessionid)

    async def test_cleanup_cancellation_retains_pending_cleanup(self):
        c = self.client(); await c._ensure_session()
        c.reset_session(); original = c._post_json
        async def cancel(command, **kwargs): raise asyncio.CancelledError()
        c._post_json = cancel
        with self.assertRaises(asyncio.CancelledError): await c._cleanup_retired_sessions()
        self.assertEqual(len(c._retired_sessions), 1)
        c._post_json = original; await c._cleanup_retired_sessions()
        self.assertEqual(c._retired_sessions, [])

    async def test_write_ack_audit_and_context_no_credentials(self):
        c = self.client(); out = self.capture_audit()
        await c.write_address('webregler/sp/3200/value', 22, audit_context={'entity_id': 'number.test', 'context_id': 'call', 'user_id': 'user', 'password': 'do-not-log'})
        records = self.records(out)
        self.assertEqual([r['outcome'] for r in records], ['attempt', 'acknowledged'])
        self.assertEqual(records[1]['value'], 22)
        self.assertEqual(records[1]['context_id'], 'call')
        self.assertNotIn(c._secret, out.getvalue()); self.assertNotIn(c._sessionid, out.getvalue())
        self.assertNotIn('do-not-log', out.getvalue())
        self.assertEqual(records[0]['request_id'], records[1]['request_id'])

    async def test_write_auth_retry_is_bounded_and_logged(self):
        c = self.client(); out = self.capture_audit(); original = c._post_json; writes = []
        async def post(command, **kwargs):
            if command == 'write':
                writes.append(kwargs['data'])
                return {'error': 462} if len(writes) == 1 else {'result': [{'error': 0}]}
            return await original(command, **kwargs)
        c._post_json = post
        await c.write_address('webregler/sp/3200/value', 22)
        self.assertEqual(len(writes), 2); self.assertEqual(writes[0], writes[1])
        self.assertEqual([r['outcome'] for r in self.records(out)], ['attempt', 'session_rejected_retry', 'attempt', 'acknowledged'])
        self.assertEqual(c.calls.count('deletesession'), 1)

    async def test_write_timeout_is_unknown_and_not_retried(self):
        c = self.client(); out = self.capture_audit(); count = 0
        async def write(*args):
            nonlocal count
            count += 1; raise api['WebMITimeout']('timeout')
        c._write_addresses_once = write
        with self.assertRaises(api['WebMITimeout']): await c.write_address('point', 22)
        self.assertEqual(count, 1)
        self.assertEqual(self.records(out)[-1]['outcome'], 'timeout_outcome_unknown')

    async def test_write_cancelled_is_logged(self):
        c = self.client(); out = self.capture_audit()
        async def write(*args): raise asyncio.CancelledError()
        c._write_addresses_once = write
        with self.assertRaises(asyncio.CancelledError): await c.write_address('point', 22)
        self.assertEqual(self.records(out)[-1]['outcome'], 'cancelled_outcome_unknown')

    async def test_missing_write_ack_not_success_or_retry(self):
        c = self.client(); out = self.capture_audit(); calls = []
        async def write(*args): calls.append(1); return {}
        c._write_addresses_once = write
        with self.assertRaises(Error): await c.write_address('point', 22)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.records(out)[-1]['outcome'], 'error_outcome_unknown')

    async def test_non_session_read_error_does_not_reset(self):
        c = self.client(); out = self.capture_audit(); original = c._post_json
        async def post(command, **kwargs):
            if command == 'read': return {'error': 999}
            return await original(command, **kwargs)
        c._post_json = post
        with self.assertRaises(Error): await c.read_addresses(['point'])
        self.assertEqual(c.calls.count('createsession'), 1)
        self.assertEqual(c.calls.count('deletesession'), 0)
        self.assertEqual(out.getvalue(), '')

    async def test_number_range_guard_and_context(self):
        calls = []
        async def write(*args, **kwargs): calls.append((args, kwargs))
        async def refresh(): pass
        n = Number(); n.native_min_value = 10; n.native_max_value = 30; n.entity_id = 'number.test'
        n.entity_description = types.SimpleNamespace(address='webregler/sp/3200/value', translation_key='test')
        n._context = types.SimpleNamespace(id='ctx', parent_id='parent', user_id='user')
        n.coordinator = types.SimpleNamespace(api=types.SimpleNamespace(write_address=write), async_request_refresh=refresh)
        for bad in (-50, float('nan'), float('inf')):
            with self.assertRaises(HAError): await n.async_set_native_value(bad)
        self.assertEqual(calls, [])
        await n.async_set_native_value(22)
        self.assertEqual(calls[0][1]['audit_context']['context_id'], 'ctx')

    async def test_select_context_and_unsupported_option(self):
        calls = []
        async def write(*args, **kwargs): calls.append((args, kwargs))
        async def refresh(): pass
        s = Select(); s.entity_id = 'select.test'
        s.entity_description = types.SimpleNamespace(address='webregler/sp/313/value', translation_key='test', options_by_value={1: 'Auto'})
        s.coordinator = types.SimpleNamespace(api=types.SimpleNamespace(write_address=write), async_request_refresh=refresh)
        with self.assertRaises(HAError): await s.async_select_option('invalid')
        await s.async_select_option('Auto')
        self.assertEqual(calls[0][1]['audit_context']['entity_id'], 'select.test')
        self.assertIsNone(calls[0][1]['audit_context']['user_id'])

if __name__ == '__main__': unittest.main()
