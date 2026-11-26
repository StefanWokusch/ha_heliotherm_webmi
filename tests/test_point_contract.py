"""Network-free contract tests for the curated monitoring entities."""
import ast
import asyncio
from datetime import datetime
from dataclasses import dataclass, make_dataclass
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any
from collections.abc import Callable, Mapping
import sys, types, unittest
from unittest.mock import AsyncMock
from test_session_and_write_audit import coord, CoordinatorStub, NoNetwork
from test_session_and_write_audit import load, EntityStub

SRC=Path(__file__).resolve().parents[1]/'custom_components/ha_heliotherm_webmi'

def load_descriptions():
    tree=ast.parse((SRC/'descriptions.py').read_text(encoding='utf8'))
    fields={k.arg for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id.startswith('WebMI') for k in n.keywords if k.arg}
    base=make_dataclass('Description',[(key,Any,None if key!='entity_registry_enabled_default' else True) for key in sorted(fields)],frozen=True,kw_only=True)
    generated=ast.parse((SRC/'generated_points.py').read_text(encoding='utf8'))
    points=ast.literal_eval(next(n.value for n in generated.body if isinstance(n,ast.AnnAssign)))
    class Constants:
        def __getattr__(self,name):return name.lower()
    ns={'SensorEntityDescription':base,'BinarySensorEntityDescription':base,'SelectEntityDescription':base,'NumberEntityDescription':base,
        'GENERATED_SENSOR_POINTS':points,'MappingProxyType':MappingProxyType,'Mapping':Mapping,'Callable':Callable,'dataclass':dataclass,'Any':Any,
        'SensorDeviceClass':Constants(),'SensorStateClass':Constants(),'EntityCategory':SimpleNamespace(DIAGNOSTIC='diagnostic'),
        'NumberMode':SimpleNamespace(BOX='box'),'UnitOfTime':SimpleNamespace(SECONDS='s',HOURS='h'),
        'UnitOfEnergy':SimpleNamespace(KILO_WATT_HOUR='kWh'),'UnitOfPower':SimpleNamespace(WATT='W',KILO_WATT='kW'),
        'UnitOfTemperature':SimpleNamespace(CELSIUS='°C'),'PERCENTAGE':'%'}
    return load('descriptions.py',ns)

D=load_descriptions()
POINTS=D['DESCRIPTIONS_BY_KEY']
Sensor=load('sensor.py',{'SensorEntity':EntityStub,'HeliothermWebMIEntity':type('Base',(),{}),'SENSOR_DESCRIPTIONS':D['SENSOR_DESCRIPTIONS'],'DESCRIPTIONS_BY_KEY':POINTS})['HeliothermWebMISensor']

class PointContract(unittest.TestCase):
    def test_heating_room_control_uses_its_own_address_and_ui_limits(self):
        heating = POINTS['control_raum_soll_heizung']
        self.assertIn(heating, D['NUMBER_DESCRIPTIONS'])
        self.assertEqual(heating.address, POINTS['diag_sp_369'].address)
        self.assertEqual(heating.address, 'webregler/sp/369/value')
        self.assertEqual((heating.native_min_value, heating.native_max_value, heating.native_step), (10, 25, 0.5))
        self.assertEqual(POINTS['control_raum_soll'].address, 'webregler/sp/3200/value')

    def test_native_targets_are_direct_and_independent_of_curve(self):
        for key,address,v in [('heizen_soll','webregler/mp/257/value',38.9),('mischer1_soll','webregler/mp/266/value',42.9)]:
            d=POINTS[key];self.assertEqual(d.address,address);self.assertIsNone(d.calculate_fn)
            sensor=Sensor();sensor.entity_description=d;sensor.webmi_result=SimpleNamespace(value=v,error=0)
            sensor.coordinator=SimpleNamespace(data={'irrelevant_curve':999})
            self.assertEqual(sensor.native_value,v)
            sensor.webmi_result=SimpleNamespace(value=999,error=301)
            self.assertIsNone(sensor.native_value)

    def test_curve_estimates_are_removed(self):
        for key in ['ruecklauf_soll_berechnet','heizkreis_soll_berechnet']:
            self.assertNotIn(key,POINTS)
        for name in ['heating_curve_setpoint','calculated_hkr_ruecklauf_soll','calculated_mischer1_soll']:
            self.assertNotIn(name,D)

    def test_new_hand_points_are_four_optional_read_only_entities(self):
        keys=['hkpa01_handwert','hkpa01_handbetrieb','mischer1_pumpe_handwert','mischer1_pumpe_handbetrieb']
        for key in keys:
            self.assertFalse(POINTS[key].entity_registry_enabled_default)
            self.assertIn(POINTS[key].address.rsplit('/',1)[-1],{'handAkt','handVal'})
        self.assertEqual(POINTS['hkpa01_handwert'].native_unit_of_measurement,'%')
        write_addresses={d.address for d in D['NUMBER_DESCRIPTIONS']+D['SELECT_DESCRIPTIONS']}
        self.assertTrue(all(POINTS[k].address not in write_addresses for k in keys))

    def test_unused_and_schedule_points_not_default_polled(self):
        for key,d in POINTS.items():
            if any(t in key for t in ['warmwasser','brauchwasser','zirkpumpe','solarpumpe','solar_','mischer2_','frischwasser']):
                self.assertFalse(d.entity_registry_enabled_default,key)
            self.assertFalse(d.address and '/tp/' in d.address,key)

    def test_mode_and_generated_regulator_units(self):
        self.assertEqual(POINTS['heizkreispumpe_modus'].address,'webregler/sp/3294/value')
        self.assertEqual(POINTS['heizkreispumpe_zustand'].address,'webregler/sp/337/value')
        self.assertEqual(POINTS['heizkreispumpe_zustand'].value_fn(3),'continuous')
        self.assertEqual(POINTS['diag_sp_3359'].native_unit_of_measurement,'%')
        self.assertEqual(POINTS['diag_sp_3369'].native_unit_of_measurement,'K')
        self.assertEqual(len(D['ALL_DESCRIPTIONS']),len(POINTS))

class MonitoringTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.allowed = D['MINIMAL_SENSOR_KEYS']
        self.client = SimpleNamespace(session_generation=1, read_addresses=AsyncMock(return_value={}))
        module = load('coordinator.py', {
            **coord, 'DataUpdateCoordinator': CoordinatorStub,
            'DESCRIPTIONS_BY_KEY': POINTS, 'MINIMAL_SENSOR_KEYS': self.allowed,
        })
        self.coordinator = module['HeliothermWebMICoordinator'](None, self.client, None)
        self.coordinator.last_update_success = True

    def timer_fixture(self, phase, seconds):
        c = self.coordinator
        c.async_contexts = lambda: iter(['diag_sp_311'])
        state = {coord['PHASE_ADDRESS']: phase, coord['TIMER_ADDRESS']: seconds}
        async def read(addresses):
            return {a: coord['WebMIReadResult'](value=state[a], error=0) for a in addresses}
        self.client.read_addresses.side_effect = read
        return state

    async def test_poll_timer_only_on_start_phase_or_session_change(self):
        c = self.coordinator
        state = self.timer_fixture(9, 4000)
        phase, timer = coord['PHASE_ADDRESS'], coord['TIMER_ADDRESS']
        c.data = await c._async_update_data()
        attrs = c.timer_attributes
        self.assertEqual((datetime.fromisoformat(attrs['sampled_at']) -
                          datetime.fromisoformat(attrs['running_since'])).total_seconds(), 4000)
        c.data = await c._async_update_data()
        self.assertEqual(self.client.read_addresses.await_args.args[0], [phase])
        self.assertEqual(c.data['diag_sp_311'].value, 4000)
        state[phase], state[timer] = 0, 900
        c.data = await c._async_update_data()
        self.assertEqual(self.client.read_addresses.await_args.args[0], [phase, timer])
        attrs = c.timer_attributes
        self.assertEqual((datetime.fromisoformat(attrs['timer_ends_at']) -
                          datetime.fromisoformat(attrs['sampled_at'])).total_seconds(), 900)
        self.client.session_generation += 1
        c.data = await c._async_update_data()
        self.assertEqual(self.client.read_addresses.await_args.args[0], [phase, timer])

    async def test_subscription_phase_transition_and_rebind_without_timer_subscription(self):
        c = self.coordinator
        state = self.timer_fixture(9, 300)
        phase, timer = coord['PHASE_ADDRESS'], coord['TIMER_ADDRESS']
        c.data = await c._async_update_data()
        self.client.create_subscription = AsyncMock(return_value='sub')
        self.client.subscribe_addresses = AsyncMock()
        self.client.delete_subscription = AsyncMock()
        count = 0
        async def publish(**kwargs):
            nonlocal count
            count += 1
            if count == 1:
                state[phase], state[timer] = 0, 120
                return [coord['WebMISubscriptionEvent'](phase, coord['WebMIReadResult'](value=0, error=0))]
            if count == 2:
                self.assertEqual(c.data['diag_sp_311'].value, 120)
                state[timer] = 100
                self.client.session_generation += 1
                raise coord['WebMISessionChanged']()
            raise asyncio.CancelledError()
        self.client.publish_subscription = publish
        with self.assertRaises(asyncio.CancelledError):
            await c._subscription_loop()
        for call in self.client.subscribe_addresses.await_args_list:
            self.assertEqual(call.args[1], (phase,))
        self.assertEqual(self.client.read_addresses.await_count, 3)
        self.assertEqual(c.data['diag_sp_311'].value, 100)

    async def test_one_expiry_check_and_hourly_resample_during_continuous_push(self):
        c = self.coordinator
        self.timer_fixture(0, 20)
        c.data = await c._async_update_data()
        loop = asyncio.get_running_loop()
        self.assertAlmostEqual(c._timer_due - loop.time(), 20, delta=1)
        c._schedule_timer(0)
        c._timer_task = asyncio.create_task(c._timer_loop())
        for _ in range(10):
            await asyncio.sleep(0)
        self.assertEqual(self.client.read_addresses.await_count, 2)
        self.assertAlmostEqual(c._timer_due - loop.time(), 3600, delta=1)
        c._schedule_timer(0)
        for _ in range(10):
            await asyncio.sleep(0)
        self.assertEqual(self.client.read_addresses.await_count, 3)
        await c.async_stop_subscription()
        self.assertIsNone(c._timer_task)

    async def test_failed_phase_sample_never_reuses_previous_timer(self):
        c = self.coordinator
        self.timer_fixture(0, 90)
        c.data = await c._async_update_data()
        self.client.read_addresses.side_effect = coord['WebMIError']('offline')
        with self.assertLogs(level='WARNING'):
            await c._push_timer_sample(c._active_address_to_keys())
        self.assertNotEqual(c.data['diag_sp_311'].error, 0)
        self.assertFalse(c.timer_attributes)
        self.assertAlmostEqual(c._timer_due - asyncio.get_running_loop().time(), 60, delta=1)

    async def test_empty_and_mixed_registered_contexts(self):
        coordinator = self.coordinator
        for minimal in (True, False):
            coordinator.minimal_monitoring = minimal
            coordinator.async_contexts = lambda: iter(())
            self.assertEqual(await coordinator._async_update_data(), {})
            self.client.read_addresses.assert_not_awaited()
        coordinator.minimal_monitoring = True
        coordinator.async_contexts = lambda: iter(['hkpa01_istwert', 'hochdruck', 'scop_gesamt_berechnet'])
        self.assertEqual(set(await coordinator._async_update_data()), {'hkpa01_istwert'})
        self.assertEqual(set(self.client.read_addresses.await_args.args[0]), {'webregler/mp/247/value'})
        self.assertEqual(set(coordinator._active_address_to_keys()), {'webregler/mp/247/value'})

    async def test_legacy_entry_with_every_context_only_selects_direct_minimal_points(self):
        self.coordinator.async_contexts = lambda: iter(POINTS)
        self.assertEqual(set(await self.coordinator._async_update_data()), self.allowed)
        addresses = self.coordinator._active_address_to_keys()
        self.assertEqual(len(addresses), 13)
        self.assertIn('webregler/sp/311/value', addresses)
        self.assertTrue(all(POINTS[key] in D['SENSOR_DESCRIPTIONS'] for key in self.allowed))

    async def test_expanded_profile_fetches_only_selected_dependencies(self):
        self.coordinator.minimal_monitoring = False
        self.coordinator.async_contexts = lambda: iter(['scop_gesamt_berechnet'])
        self.assertEqual(set(await self.coordinator._async_update_data()),
                         {'thermische_energie_gesamt', 'elektrische_energie_gesamt'})

    async def test_diagnostics_uses_cached_data_without_network(self):
        diagnostics = load('diagnostics.py', {
            'DOMAIN': 'test', 'CONF_HOST': 'host', 'CONF_PORT': 'port',
            'DESCRIPTIONS_BY_KEY': POINTS,
        })
        class Offline(NoNetwork):
            session_generation = 2
            base_url = 'offline.invalid'
        self.coordinator.data = {'heizen_soll': coord['WebMIReadResult'](value=40, error=0)}
        self.coordinator.last_update_success = True
        runtime = SimpleNamespace(api=Offline(), coordinator=self.coordinator)
        entry = SimpleNamespace(entry_id='a', title='Offline', data={}, options={})
        result = await diagnostics['async_get_config_entry_diagnostics'](
            SimpleNamespace(data={'test': {'a': runtime}}), entry)
        self.assertEqual(result['address_count'], 1)
        self.assertEqual(result['addresses']['webregler/mp/257/value']['value'], 40)

    async def test_first_refresh_after_registration_and_failed_setup_cleanup(self):
        from test_session_and_write_audit import Client, Error
        calls = []
        class FakeCoordinator:
            def __init__(self, *args, **kwargs):
                self.minimal = kwargs['minimal_monitoring']
            async def async_config_entry_first_refresh(self):
                calls.append('read')
                self_test.assertTrue(self.minimal)
                if fail:
                    raise Error('offline')
            def async_start_subscription(self):
                calls.append('subscribe')
            async def async_stop_subscription(self):
                calls.append('stop')
        async def register(*args):
            calls.append('registered')
        async def unload(*args):
            calls.append('unloaded')
        self_test = self
        client = Client(NoNetwork(), 'offline.invalid')
        client.async_close = AsyncMock()
        setup = load('__init__.py', {
            'DOMAIN': 'test', 'CONF_HOST': 'host', 'CONF_PORT': 'port',
            'CONF_SCAN_INTERVAL': 'scan', 'DEFAULT_SCAN_INTERVAL': 60,
            'MIN_SCAN_INTERVAL': 15, 'CONF_MINIMAL_MONITORING': 'minimal_monitoring',
            'CONF_USE_SUBSCRIPTIONS': 'subscriptions', 'DEFAULT_USE_SUBSCRIPTIONS': True,
            'DEFAULT_SUBSCRIPTION_FALLBACK_INTERVAL': 300, 'DEFAULT_PORT': 80,
            'PLATFORMS': ('sensor',), 'HeliothermWebMIClient': lambda *a, **kw: client,
            'async_get_clientsession': lambda hass: None, 'WebMIError': Error,
            'HeliothermWebMICoordinator': FakeCoordinator,
        })['async_setup_entry']
        entry = SimpleNamespace(entry_id='a', data={'host': 'offline.invalid'}, options={},
                                async_on_unload=lambda f: None, add_update_listener=lambda f: f)
        hass = SimpleNamespace(data={}, config_entries=SimpleNamespace(
            async_entries=lambda domain: [], async_forward_entry_setups=register,
            async_unload_platforms=unload))
        for fail in (False, True):
            calls.clear()
            if fail:
                with self.assertRaises(Error):
                    await setup(hass, entry)
                self.assertEqual(calls, ['registered', 'read', 'unloaded', 'stop'])
                client.async_close.assert_awaited_once()
                self.assertNotIn('a', hass.data['test'])
            else:
                self.assertTrue(await setup(hass, entry))
                self.assertEqual(calls, ['registered', 'read', 'subscribe'])

if __name__=='__main__':unittest.main()
