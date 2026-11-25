"""Network-free contract tests for the curated monitoring entities."""
import ast
from dataclasses import dataclass, make_dataclass
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any
from collections.abc import Callable, Mapping
import sys, types, unittest
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

if __name__=='__main__':unittest.main()
