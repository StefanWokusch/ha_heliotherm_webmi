"""Entity descriptions for Heliotherm WebMI points."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)

from .generated_points import GENERATED_SENSOR_POINTS


def raw_value(value: Any) -> Any:
    """Return a value unchanged."""
    return value


def number_value(value: Any) -> float | int | None:
    """Convert WebMI payload values to numeric values."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if converted.is_integer():
        return int(converted)
    return converted


def optional_text(value: Any) -> str | None:
    """Convert WebMI payload values to text."""
    if value is None:
        return None
    return str(value)


def on_off(value: Any) -> str | None:
    """Render common WebMI 0/1 values."""
    numeric = number_value(value)
    if numeric == 0:
        return "off"
    if numeric == 1:
        return "on"
    return optional_text(value)


def pump_state(value: Any) -> str | None:
    """Render the observed pump state enum."""
    numeric = number_value(value)
    return {
        0: "off",
        1: "on",
        2: "pulse",
    }.get(numeric, optional_text(value))


def operating_mode(value: Any) -> str | None:
    """Render the observed WebMI operating mode enum."""
    numeric = number_value(value)
    return {
        0: "aus",
        1: "automatik",
        2: "kuehlen",
        3: "sommer",
        4: "dauerbetrieb",
        5: "absenkbetrieb",
        6: "urlaub",
        7: "party",
    }.get(numeric, optional_text(value))


def demand_mode(value: Any) -> str | None:
    """Render the observed Infobox demand enum."""
    numeric = number_value(value)
    return {
        0: "keine_anforderung",
        1: "kuehlen",
        2: "heizen",
        3: "warmwasser",
        4: "externe_anforderung",
        5: "pv_anforderung",
    }.get(numeric, optional_text(value))


@dataclass(frozen=True, kw_only=True)
class WebMISensorEntityDescription(SensorEntityDescription):
    """Description for a WebMI sensor."""

    address: str
    value_fn: Callable[[Any], Any] = raw_value


@dataclass(frozen=True, kw_only=True)
class WebMIBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for a WebMI binary sensor."""

    address: str
    on_values: frozenset[Any] = frozenset({1, "1", True, "true", "on", "Ein"})


def generated_native_unit(unit: str | None) -> str | None:
    """Map generated catalogue unit keys to Home Assistant units."""
    return {
        "bar": "bar",
        "celsius": UnitOfTemperature.CELSIUS,
        "h": UnitOfTime.HOURS,
        "kwh": UnitOfEnergy.KILO_WATT_HOUR,
        "kw": UnitOfPower.KILO_WATT,
        "lph": "l/h",
        "percent": PERCENTAGE,
        "s": UnitOfTime.SECONDS,
        "w": UnitOfPower.WATT,
    }.get(unit)


def generated_device_class(unit: str | None) -> SensorDeviceClass | None:
    """Return a device class only for generated points with reliable units."""
    if unit == "celsius":
        return SensorDeviceClass.TEMPERATURE
    return None


SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = (
    WebMISensorEntityDescription(
        key="mischer1_heizgrenze",
        translation_key="mischer1_heizgrenze",
        address="webregler/sp/3205/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="hkr_heizgrenze",
        translation_key="hkr_heizgrenze",
        address="webregler/sp/376/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="hkpa01_istwert",
        translation_key="hkpa01_istwert",
        address="webregler/mp/247/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer_betrieb",
        translation_key="mischer_betrieb",
        address="webregler/mp/268/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer_sollpos",
        translation_key="mischer_sollpos",
        address="webregler/sp/3220/value",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="vortex_flow_1",
        translation_key="vortex_flow_1",
        address="webregler/mp/2104/value",
        native_unit_of_measurement="l/min",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="vortex_flow_2",
        translation_key="vortex_flow_2",
        address="webregler/mp/2105/value",
        native_unit_of_measurement="l/min",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="heizkreispumpe_modus",
        translation_key="heizkreispumpe_modus",
        address="webregler/sp/3294/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
    WebMISensorEntityDescription(
        key="heizkreispumpe_zustand",
        translation_key="heizkreispumpe_zustand",
        address="webregler/sp/337/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=pump_state,
    ),
    WebMISensorEntityDescription(
        key="vortex_type_1",
        translation_key="vortex_type_1",
        address="webregler/sp/3424/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
    WebMISensorEntityDescription(
        key="vortex_type_2",
        translation_key="vortex_type_2",
        address="webregler/sp/3425/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
    WebMISensorEntityDescription(
        key="pv_power",
        translation_key="pv_power",
        address="mcg/data/pvPower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="rcg_serial",
        translation_key="rcg_serial",
        address="mcg/data/rcgSerial",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
    WebMISensorEntityDescription(
        key="rcg_version",
        translation_key="rcg_version",
        address="mcg/data/version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
    WebMISensorEntityDescription(
        key="webregler_version",
        translation_key="webregler_version",
        address="mcg/data/web/version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
    WebMISensorEntityDescription(
        key="controller_zeit",
        translation_key="controller_zeit",
        address="mcg/data/web/time",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
)


BINARY_SENSOR_DESCRIPTIONS: tuple[WebMIBinarySensorEntityDescription, ...] = (
    WebMIBinarySensorEntityDescription(
        key="fu_soll_extern",
        translation_key="fu_soll_extern",
        address="webregler/sp/3452/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="heizkreispumpe_service_ein",
        translation_key="heizkreispumpe_service_ein",
        address="webregler/mp/222/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="pufferpumpe_handwert",
        translation_key="pufferpumpe_handwert",
        address="webregler/mp/223/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="eq_pumpe_zustand",
        translation_key="eq_pumpe_zustand",
        address="webregler/mp/224/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="brauchwasserpumpe_handwert",
        translation_key="brauchwasserpumpe_handwert",
        address="webregler/mp/225/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="umv_kuehlen_ein",
        translation_key="umv_kuehlen_ein",
        address="webregler/mp/227/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="externe_pumpe_handwert",
        translation_key="externe_pumpe_handwert",
        address="webregler/mp/228/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="zirkpumpe_zustand",
        translation_key="zirkpumpe_zustand",
        address="webregler/mp/229/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="verdichter_ein",
        translation_key="verdichter_ein",
        address="webregler/mp/230/value",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WebMIBinarySensorEntityDescription(
        key="stoerung_ein",
        translation_key="stoerung_ein",
        address="webregler/mp/231/value",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WebMIBinarySensorEntityDescription(
        key="vierwegeventil_ein",
        translation_key="vierwegeventil_ein",
        address="webregler/mp/232/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="hochdruckbe_aktiv",
        translation_key="hochdruckbe_aktiv",
        address="webregler/mp/233/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="mse_quelle_aktiv",
        translation_key="mse_quelle_aktiv",
        address="webregler/mp/234/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="ext_anforderung",
        translation_key="ext_anforderung",
        address="webregler/mp/235/value",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WebMIBinarySensorEntityDescription(
        key="betriebsschalter_aktiv",
        translation_key="betriebsschalter_aktiv",
        address="webregler/mp/236/value",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WebMIBinarySensorEntityDescription(
        key="evu_sperre_aktiv",
        translation_key="evu_sperre_aktiv",
        address="webregler/mp/237/value",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WebMIBinarySensorEntityDescription(
        key="solarpumpe_status",
        translation_key="solarpumpe_status",
        address="webregler/mp/245/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="heizkreispumpe_ext_anf_abhaengig",
        translation_key="heizkreispumpe_ext_anf_abhaengig",
        address="webregler/sp/3388/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


TEMPERATURE_SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = (
    WebMISensorEntityDescription(
        key="aussentemperatur",
        translation_key="aussentemperatur",
        address="webregler/mp/20/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="brauchwasser_temperatur",
        translation_key="brauchwasser_temperatur",
        address="webregler/mp/22/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="vorlauf_temperatur",
        translation_key="vorlauf_temperatur",
        address="webregler/mp/23/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="ruecklauf_temperatur",
        translation_key="ruecklauf_temperatur",
        address="webregler/mp/24/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="pufferspeicher_temperatur",
        translation_key="pufferspeicher_temperatur",
        address="webregler/mp/25/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="eq_eintritt_temperatur",
        translation_key="eq_eintritt_temperatur",
        address="webregler/mp/26/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="eq_austritt_temperatur",
        translation_key="eq_austritt_temperatur",
        address="webregler/mp/27/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="oelsumpf_temperatur",
        translation_key="oelsumpf_temperatur",
        address="webregler/mp/28/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="sauggas_temperatur",
        translation_key="sauggas_temperatur",
        address="webregler/mp/29/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="frischwasser_temperatur",
        translation_key="frischwasser_temperatur",
        address="webregler/mp/211/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="unterkuehlen_temperatur",
        translation_key="unterkuehlen_temperatur",
        address="webregler/mp/214/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="heissgas_temperatur",
        translation_key="heissgas_temperatur",
        address="webregler/mp/215/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="raumtemperatur_1",
        translation_key="raumtemperatur_1",
        address="webregler/mp/216/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="raumtemperatur_2",
        translation_key="raumtemperatur_2",
        address="webregler/mp/217/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="raumtemperatur_3",
        translation_key="raumtemperatur_3",
        address="webregler/mp/218/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="raumtemperatur_4",
        translation_key="raumtemperatur_4",
        address="webregler/mp/219/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="solar_kt1_temperatur",
        translation_key="solar_kt1_temperatur",
        address="webregler/mp/243/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_vorlauf_temperatur",
        translation_key="mischer1_vorlauf_temperatur",
        address="webregler/mp/263/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_ruecklauf_temperatur",
        translation_key="mischer1_ruecklauf_temperatur",
        address="webregler/mp/264/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer2_vorlauf_temperatur",
        translation_key="mischer2_vorlauf_temperatur",
        address="webregler/mp/269/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer2_ruecklauf_temperatur",
        translation_key="mischer2_ruecklauf_temperatur",
        address="webregler/mp/270/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
)

EFFICIENCY_SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = (
    WebMISensorEntityDescription(
        key="thermische_leistung",
        translation_key="thermische_leistung",
        address="webregler/mp/289/value",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="elektrische_aufnahmeleistung",
        translation_key="elektrische_aufnahmeleistung",
        address="webregler/mp/283/value",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="cop_gesamt",
        translation_key="cop_gesamt",
        address="webregler/mp/292/value",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="thermische_energie_gesamt",
        translation_key="thermische_energie_gesamt",
        address="webregler/mp/284/value",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="elektrische_energie_gesamt",
        translation_key="elektrische_energie_gesamt",
        address="webregler/mp/275/value",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="thermische_energie_heizen",
        translation_key="thermische_energie_heizen",
        address="webregler/mp/252/value",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="elektrische_energie_heizen",
        translation_key="elektrische_energie_heizen",
        address="webregler/mp/253/value",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="thermische_energie_warmwasser",
        translation_key="thermische_energie_warmwasser",
        address="webregler/mp/254/value",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="elektrische_energie_warmwasser",
        translation_key="elektrische_energie_warmwasser",
        address="webregler/mp/255/value",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
)

STATUS_SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = (
    WebMISensorEntityDescription(
        key="anforderung",
        translation_key="anforderung",
        address="webregler/mp/256/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=demand_mode,
    ),
    WebMISensorEntityDescription(
        key="betriebsart",
        translation_key="betriebsart",
        address="webregler/sp/313/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=operating_mode,
    ),
    WebMISensorEntityDescription(
        key="startseiten_statuscode",
        translation_key="startseiten_statuscode",
        address="webregler/sp/310/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_betriebsart",
        translation_key="mischer1_betriebsart",
        address="webregler/sp/3221/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=operating_mode,
    ),
    WebMISensorEntityDescription(
        key="hochdruck",
        translation_key="hochdruck",
        address="webregler/mp/21/value",
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="wmz_volumenstrom",
        translation_key="wmz_volumenstrom",
        address="webregler/mp/285/value",
        native_unit_of_measurement="l/h",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="vdmod_status",
        translation_key="vdmod_status",
        address="webregler/mp/240/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="verdichter_n_soll",
        translation_key="verdichter_n_soll",
        address="webregler/mp/290/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="expansionsventil_istwert",
        translation_key="expansionsventil_istwert",
        address="webregler/mp/251/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer2_betrieb",
        translation_key="mischer2_betrieb",
        address="webregler/mp/274/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="eqa02_istwert",
        translation_key="eqa02_istwert",
        address="webregler/sp/3327/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="fehlerlog",
        translation_key="fehlerlog",
        address="mcg/data/errorLog",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=optional_text,
    ),
)

GENERATED_SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = tuple(
    WebMISensorEntityDescription(
        key=point["key"],
        name=point["name"],
        address=point["address"],
        native_unit_of_measurement=generated_native_unit(point["unit"]),
        device_class=generated_device_class(point["unit"]),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=raw_value,
    )
    for point in GENERATED_SENSOR_POINTS
)


SENSOR_DESCRIPTIONS = (
    SENSOR_DESCRIPTIONS
    + TEMPERATURE_SENSOR_DESCRIPTIONS
    + EFFICIENCY_SENSOR_DESCRIPTIONS
    + STATUS_SENSOR_DESCRIPTIONS
    + GENERATED_SENSOR_DESCRIPTIONS
)


ALL_DESCRIPTIONS = SENSOR_DESCRIPTIONS + BINARY_SENSOR_DESCRIPTIONS
DESCRIPTIONS_BY_KEY = {description.key: description for description in ALL_DESCRIPTIONS}
