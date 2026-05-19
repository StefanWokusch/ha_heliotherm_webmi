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
from homeassistant.const import PERCENT, UnitOfPower, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.entity import EntityCategory


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


SENSOR_DESCRIPTIONS: tuple[WebMISensorEntityDescription, ...] = (
    WebMISensorEntityDescription(
        key="mischer1_heizgrenze",
        translation_key="mischer1_heizgrenze",
        address="webregler/sp/3205/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="hkr_heizgrenze",
        translation_key="hkr_heizgrenze",
        address="webregler/sp/376/value",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="hkpa01_istwert",
        translation_key="hkpa01_istwert",
        address="webregler/mp/247/value",
        native_unit_of_measurement=PERCENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer_betrieb",
        translation_key="mischer_betrieb",
        address="webregler/mp/268/value",
        native_unit_of_measurement=PERCENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="mischer_sollpos",
        translation_key="mischer_sollpos",
        address="webregler/sp/3220/value",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="vortex_flow_1",
        translation_key="vortex_flow_1",
        address="webregler/mp/2104/value",
        native_unit_of_measurement="l/min",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=number_value,
    ),
    WebMISensorEntityDescription(
        key="vortex_flow_2",
        translation_key="vortex_flow_2",
        address="webregler/mp/2105/value",
        native_unit_of_measurement="l/min",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
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
    ),
    WebMIBinarySensorEntityDescription(
        key="heizkreispumpe_service_ein",
        translation_key="heizkreispumpe_service_ein",
        address="webregler/mp/222/value",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WebMIBinarySensorEntityDescription(
        key="heizkreispumpe_ext_anf_abhaengig",
        translation_key="heizkreispumpe_ext_anf_abhaengig",
        address="webregler/sp/3388/value",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


ALL_DESCRIPTIONS = SENSOR_DESCRIPTIONS + BINARY_SENSOR_DESCRIPTIONS
DESCRIPTIONS_BY_KEY = {description.key: description for description in ALL_DESCRIPTIONS}

