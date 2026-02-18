"""Sensore di stato per AvoidBlackout."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATE_MONITORING

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura i sensori della entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    manager = data["manager"]

    async_add_entities([AvoidBlackoutStatusSensor(coordinator, manager, entry)])


class AvoidBlackoutStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensore che rappresenta lo stato del PowerManager."""

    _attr_has_entity_name = True
    _attr_translation_key = "avoidblackout_status"
    _attr_icon = "mdi:shield-flash"

    def __init__(self, coordinator, manager, entry: ConfigEntry) -> None:
        """Inizializza il sensore."""
        super().__init__(coordinator)
        self.manager = manager
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_avoidblackout_status"
        self._attr_name = "AvoidBlackout Status"
        self._unsub_manager = None

    async def async_added_to_hass(self) -> None:
        """Chiamato quando l'entità viene aggiunta a HA."""
        await super().async_added_to_hass()
        # Listener per aggiornamenti dal manager
        self._unsub_manager = self.manager.async_add_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Chiamato quando l'entità viene rimossa da HA."""
        if self._unsub_manager:
            self._unsub_manager()
        await super().async_will_remove_from_hass()

    @property
    def state(self) -> str:
        """Ritorna lo stato del manager."""
        return self.manager._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Ritorna gli attributi del sensore."""
        status = self.manager.get_status()
        data = self.coordinator.data or {}
        
        return {
            "total_power": data.get("total_power", 0),
            "threshold": status.get("threshold"),
            "is_over_threshold": data.get("is_over_threshold", False),
            "shutdown_entities": status.get("shutdown_entities", []),
            "managed_entities_count": status.get("managed_entities_count", 0),
            "test_mode": status.get("test_mode", False),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Gestisce l'aggiornamento quando il coordinator cambia dati."""
        self.async_write_ha_state()
