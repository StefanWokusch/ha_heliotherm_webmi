"""Entity descriptions for Heliotherm WebMI points."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.number import NumberEntityDescription, NumberMode
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.select import SelectEntityDescription
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


def active_state(value: Any) -> str | None:
    """Render common diagnostic active/inactive values."""
    numeric = number_value(value)
    if numeric == 0:
        return "inaktiv"
    if numeric == 1:
        return "aktiv"
    return optional_text(value)


def compressor_state(value: Any) -> str | None:
    """Render compressor running state."""
    numeric = number_value(value)
    if numeric == 0:
        return "aus"
    if numeric == 1:
        return "laeuft"
    return optional_text(value)


def fault_state(value: Any) -> str | None:
    """Render fault state."""
    numeric = number_value(value)
    if numeric == 0:
        return "ok"
    if numeric == 1:
        return "stoerung"
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


def heating_curve_setpoint(
    outside_temp: float,
    heating_limit: float,
    setpoint_at_limit: float,
    setpoint_at_zero: float,
    setpoint_at_minus_15: float,
    offset: float,
) -> float:
    """Calculate a Heliotherm heating-curve setpoint."""
    if outside_temp >= heating_limit:
        setpoint = setpoint_at_limit
    elif outside_temp >= 0:
        setpoint = setpoint_at_limit + (
            (heating_limit - outside_temp)
            * (setpoint_at_zero - setpoint_at_limit)
            / heating_limit
        )
    elif outside_temp >= -15:
        setpoint = setpoint_at_zero + (
            (0 - outside_temp)
            * (setpoint_at_minus_15 - setpoint_at_zero)
            / 15
        )
    else:
        setpoint = setpoint_at_minus_15

    return round(setpoint + offset, 1)


def calculated_hkr_ruecklauf_soll(values: dict[str, Any]) -> float | None:
    """Calculate the heat-pump return setpoint from the HKR curve."""
    required = (
        "aussentemperatur_verzoegert",
        "hkr_heizgrenze",
        "hkr_ruecklaufsoll_bei_heizgrenze",
        "hkr_ruecklaufsoll_bei_0c",
        "hkr_ruecklaufsoll_bei_minus_15c",
        "hkr_aufheiztemp",
    )
    if any(not isinstance(values.get(key), int | float) for key in required):
        return None

    return heating_curve_setpoint(
        values["aussentemperatur_verzoegert"],
        values["hkr_heizgrenze"],
        values["hkr_ruecklaufsoll_bei_heizgrenze"],
        values["hkr_ruecklaufsoll_bei_0c"],
        values["hkr_ruecklaufsoll_bei_minus_15c"],
        values["hkr_aufheiztemp"],
    )


def calculated_mischer1_soll(values: dict[str, Any]) -> float | None:
    """Calculate the Mischer1 heating-circuit setpoint from its curve."""
    required = (
        "aussentemperatur_verzoegert",
        "mischer1_heizgrenze",
        "mischer1_ruecklaufsoll_bei_heizgrenze",
        "mischer1_ruecklaufsoll_bei_0c",
        "mischer1_ruecklaufsoll_bei_minus_15c",
        "mischer1_aufheiztemp",
    )
    if any(not isinstance(values.get(key), int | float) for key in required):
        return None

    return heating_curve_setpoint(
        values["aussentemperatur_verzoegert"],
        values["mischer1_heizgrenze"],
        values["mischer1_ruecklaufsoll_bei_heizgrenze"],
        values["mischer1_ruecklaufsoll_bei_0c"],
        values["mischer1_ruecklaufsoll_bei_minus_15c"],
        values["mischer1_aufheiztemp"],
    )


def calculated_scop_gesamt(values: dict[str, Any]) -> float | None:
    """Calculate the WebMI total SCOP from cumulative total energy counters."""
    thermal = values.get("thermische_energie_gesamt")
    electrical = values.get("elektrische_energie_gesamt")
    if not isinstance(thermal, int | float) or not isinstance(electrical, int | float):
        return None
    if electrical <= 0:
        return None
    return round(thermal / electrical, 1)


@dataclass(frozen=True, kw_only=True)
class WebMISensorEntityDescription(SensorEntityDescription):
    """Description for a WebMI sensor."""

    address: str | None = None
    value_fn: Callable[[Any], Any] = raw_value
    dependencies: tuple[str, ...] = ()
    calculate_fn: Callable[[dict[str, Any]], Any] | None = None
    calculation_attributes: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True, kw_only=True)
class WebMIBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for a WebMI binary sensor."""

    address: str
    on_values: frozenset[Any] = frozenset({1, "1", True, "true", "on", "Ein"})


@dataclass(frozen=True, kw_only=True)
class WebMINumberEntityDescription(NumberEntityDescription):
    """Description for a writable WebMI number."""

    address: str
    value_fn: Callable[[Any], float | int | None] = number_value


@dataclass(frozen=True, kw_only=True)
class WebMISelectEntityDescription(SelectEntityDescription):
    """Description for a writable WebMI select."""

    address: str
    options_by_value: Mapping[int, str]


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


NORMAL_GENERATED_POINT_PREFIXES = (
    "Heizkreis Sollwert ",
    "Mischer1 Sollwert ",
    "Mischer2 Sollwert ",
    "Warmwasser Sollwert ",
)


def generated_entity_category(point: Mapping[str, Any]) -> EntityCategory | None:
    """Classify generated points by recovered WebMI label."""
    name = point.get("name")
    if isinstance(name, str) and (
        name.startswith(NORMAL_GENERATED_POINT_PREFIXES)
        or name == "Main Kuehlen Soll"
    ):
        return None
    return EntityCategory.DIAGNOSTIC


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
        key="hkr_ruecklaufsoll_bei_heizgrenze",
        translation_key="hkr_ruecklaufsoll_bei_heizgrenze",
        address="webregler/sp/380/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="hkr_ruecklaufsoll_bei_0c",
        translation_key="hkr_ruecklaufsoll_bei_0c",
        address="webregler/sp/381/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="hkr_ruecklaufsoll_bei_minus_15c",
        translation_key="hkr_ruecklaufsoll_bei_minus_15c",
        address="webregler/sp/382/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="hkr_aufheiztemp",
        translation_key="hkr_aufheiztemp",
        address="webregler/sp/371/value",
        native_unit_of_measurement="K",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_ruecklaufsoll_bei_heizgrenze",
        translation_key="mischer1_ruecklaufsoll_bei_heizgrenze",
        address="webregler/sp/3209/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_ruecklaufsoll_bei_0c",
        translation_key="mischer1_ruecklaufsoll_bei_0c",
        address="webregler/sp/3210/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_ruecklaufsoll_bei_minus_15c",
        translation_key="mischer1_ruecklaufsoll_bei_minus_15c",
        address="webregler/sp/3211/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_aufheiztemp",
        translation_key="mischer1_aufheiztemp",
        address="webregler/sp/3202/value",
        native_unit_of_measurement="K",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="ruecklauf_soll_berechnet",
        translation_key="ruecklauf_soll_berechnet",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        dependencies=(
            "aussentemperatur_verzoegert",
            "hkr_heizgrenze",
            "hkr_ruecklaufsoll_bei_heizgrenze",
            "hkr_ruecklaufsoll_bei_0c",
            "hkr_ruecklaufsoll_bei_minus_15c",
            "hkr_aufheiztemp",
        ),
        calculate_fn=calculated_hkr_ruecklauf_soll,
        calculation_attributes=MappingProxyType(
            {
                "source": "calculated",
                "note": "Not directly read from WebMI; derived from the HKR heating curve.",
                "formula": "curve(Aussentemperatur verzoegert, HKR points) + HKR Aufheiztemp",
            }
        ),
    ),
    WebMISensorEntityDescription(
        key="heizkreis_soll_berechnet",
        translation_key="heizkreis_soll_berechnet",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        dependencies=(
            "aussentemperatur_verzoegert",
            "mischer1_heizgrenze",
            "mischer1_ruecklaufsoll_bei_heizgrenze",
            "mischer1_ruecklaufsoll_bei_0c",
            "mischer1_ruecklaufsoll_bei_minus_15c",
            "mischer1_aufheiztemp",
        ),
        calculate_fn=calculated_mischer1_soll,
        calculation_attributes=MappingProxyType(
            {
                "source": "calculated",
                "note": "Not directly read from WebMI; derived from the Mischer1 heating curve.",
                "formula": "curve(Aussentemperatur verzoegert, Mischer1 points) + Mischer1 Aufheiztemp",
            }
        ),
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
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="vortex_flow_2",
        translation_key="vortex_flow_2",
        address="webregler/mp/2105/value",
        native_unit_of_measurement="l/min",
        state_class=SensorStateClass.MEASUREMENT,
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
        key="mischerpumpe_zustand",
        translation_key="mischerpumpe_zustand",
        address="webregler/mp/265/value",
    ),
    WebMIBinarySensorEntityDescription(
        key="pufferpumpe_handwert",
        translation_key="pufferpumpe_handwert",
        address="webregler/mp/223/value",
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="eq_pumpe_zustand",
        translation_key="eq_pumpe_zustand",
        address="webregler/mp/224/value",
        entity_registry_enabled_default=False,
    ),
    WebMIBinarySensorEntityDescription(
        key="brauchwasserpumpe_handwert",
        translation_key="brauchwasserpumpe_handwert",
        address="webregler/mp/225/value",
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
        entity_registry_enabled_default=False,
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
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="aussentemperatur_verzoegert",
        translation_key="aussentemperatur_verzoegert",
        address="webregler/mp/21/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="brauchwasser_temperatur",
        translation_key="brauchwasser_temperatur",
        address="webregler/mp/22/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
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
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="ruecklauf_temperatur",
        translation_key="ruecklauf_temperatur",
        address="webregler/mp/24/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="pufferspeicher_temperatur",
        translation_key="pufferspeicher_temperatur",
        address="webregler/mp/25/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="eq_eintritt_temperatur",
        translation_key="eq_eintritt_temperatur",
        address="webregler/mp/26/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
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
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer1_ruecklauf_temperatur",
        translation_key="mischer1_ruecklauf_temperatur",
        address="webregler/mp/264/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
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
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="elektrische_aufnahmeleistung",
        translation_key="elektrische_aufnahmeleistung",
        address="webregler/mp/283/value",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="cop_gesamt",
        translation_key="cop_gesamt",
        address="webregler/mp/292/value",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="scop_gesamt_berechnet",
        translation_key="scop_gesamt_berechnet",
        state_class=SensorStateClass.MEASUREMENT,
        dependencies=(
            "thermische_energie_gesamt",
            "elektrische_energie_gesamt",
        ),
        calculate_fn=calculated_scop_gesamt,
        calculation_attributes=MappingProxyType(
            {
                "source": "calculated",
                "formula": "thermische_energie_gesamt / elektrische_energie_gesamt",
                "note": "Matches the WebMI total SCOP display rounded to one decimal.",
            }
        ),
    ),
    WebMISensorEntityDescription(
        key="thermische_energie_gesamt",
        translation_key="thermische_energie_gesamt",
        address="webregler/mp/284/value",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
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
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
)

STATUS_SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = (
    WebMISensorEntityDescription(
        key="anforderung",
        translation_key="anforderung",
        address="webregler/mp/256/value",
        value_fn=demand_mode,
    ),
    WebMISensorEntityDescription(
        key="betriebsart",
        translation_key="betriebsart",
        address="webregler/sp/313/value",
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
        key="verdichter_status",
        translation_key="verdichter_status",
        address="webregler/mp/230/value",
        value_fn=compressor_state,
    ),
    WebMISensorEntityDescription(
        key="stoerung_status",
        translation_key="stoerung_status",
        address="webregler/mp/231/value",
        value_fn=fault_state,
    ),
    WebMISensorEntityDescription(
        key="externe_anforderung_status",
        translation_key="externe_anforderung_status",
        address="webregler/mp/235/value",
        value_fn=active_state,
    ),
    WebMISensorEntityDescription(
        key="betriebsschalter_status",
        translation_key="betriebsschalter_status",
        address="webregler/mp/236/value",
        value_fn=active_state,
    ),
    WebMISensorEntityDescription(
        key="evu_sperre_status",
        translation_key="evu_sperre_status",
        address="webregler/mp/237/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=active_state,
    ),
    WebMISensorEntityDescription(
        key="mischer1_betriebsart",
        translation_key="mischer1_betriebsart",
        address="webregler/sp/3221/value",
        entity_registry_enabled_default=False,
        value_fn=operating_mode,
    ),
    WebMISensorEntityDescription(
        key="hochdruck",
        translation_key="hochdruck",
        address="webregler/mp/221/value",
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="niederdruck",
        translation_key="niederdruck",
        address="webregler/mp/220/value",
        native_unit_of_measurement="bar",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="wmz_volumenstrom",
        translation_key="wmz_volumenstrom",
        address="webregler/mp/285/value",
        native_unit_of_measurement="l/h",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="heizstab_betrieb",
        translation_key="heizstab_betrieb",
        address="webregler/mp/249/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
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
        entity_registry_enabled_default=False,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="eqa02_istwert",
        translation_key="eqa02_istwert",
        address="webregler/mp/248/value",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
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

SELECT_DESCRIPTIONS: tuple[WebMISelectEntityDescription, ...] = (
    WebMISelectEntityDescription(
        key="control_betriebsart",
        translation_key="control_betriebsart",
        address="webregler/sp/313/value",
        options_by_value=MappingProxyType(
            {
                0: "Aus",
                1: "Automatik",
                3: "Sommer",
                4: "Dauerbetrieb",
                5: "Absenkbetrieb",
                6: "Urlaub",
                7: "Party",
            }
        ),
    ),
)

NUMBER_DESCRIPTIONS: tuple[WebMINumberEntityDescription, ...] = (
    WebMINumberEntityDescription(
        key="control_raum_soll",
        translation_key="control_raum_soll",
        address="webregler/sp/3200/value",
        native_min_value=10,
        native_max_value=30,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    WebMINumberEntityDescription(
        key="control_warmwasser_soll_norm",
        translation_key="control_warmwasser_soll_norm",
        address="webregler/sp/383/value",
        native_min_value=30,
        native_max_value=65,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
    WebMINumberEntityDescription(
        key="control_warmwasser_soll_min",
        translation_key="control_warmwasser_soll_min",
        address="webregler/sp/385/value",
        native_min_value=5,
        native_max_value=60,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_registry_enabled_default=False,
    ),
)

GENERATED_SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = tuple(
    WebMISensorEntityDescription(
        key=point["key"],
        name=point["name"],
        address=point["address"],
        native_unit_of_measurement=generated_native_unit(point["unit"]),
        device_class=generated_device_class(point["unit"]),
        entity_category=generated_entity_category(point),
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


ALL_DESCRIPTIONS = (
    SENSOR_DESCRIPTIONS
    + BINARY_SENSOR_DESCRIPTIONS
    + SELECT_DESCRIPTIONS
    + NUMBER_DESCRIPTIONS
)
DESCRIPTIONS_BY_KEY = {description.key: description for description in ALL_DESCRIPTIONS}
