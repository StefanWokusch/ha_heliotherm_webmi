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
        "percent": PERCENTAGE,
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
    + GENERATED_SENSOR_DESCRIPTIONS
)


ALL_DESCRIPTIONS = SENSOR_DESCRIPTIONS + BINARY_SENSOR_DESCRIPTIONS
DESCRIPTIONS_BY_KEY = {description.key: description for description in ALL_DESCRIPTIONS}
