"""Base entity for Heliotherm WebMI."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import WebMIReadResult
from .const import ATTR_MANUFACTURER, DOMAIN
from .coordinator import HeliothermWebMICoordinator


class HeliothermWebMIEntity(CoordinatorEntity[HeliothermWebMICoordinator]):
    """Base class for WebMI entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeliothermWebMICoordinator,
        config_entry: ConfigEntry,
        description,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, context=description.key)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer=ATTR_MANUFACTURER,
            name=config_entry.title,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        result = self.webmi_result
        return super().available and result is not None and result.error == 0

    @property
    def webmi_result(self) -> WebMIReadResult | None:
        """Return the latest WebMI result for this entity."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

