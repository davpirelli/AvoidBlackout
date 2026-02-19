"""Number entities configurabili per AvoidBlackout: soglia massima e tempo di debounce."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEBOUNCE_TIME,
    CONF_MAX_THRESHOLD,
    DEFAULT_DEBOUNCE,
    DEFAULT_THRESHOLD,
    DEBOUNCE_STEP,
    DOMAIN,
    MAX_DEBOUNCE,
    MAX_THRESHOLD,
    MIN_DEBOUNCE,
    MIN_THRESHOLD,
    THRESHOLD_STEP,
)
from .coordinator import PowerCoordinator
from .power_manager import PowerManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura i number entities per soglia e debounce."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: PowerCoordinator = data["coordinator"]
    manager: PowerManager = data["manager"]

    threshold_entity = AvoidBlackoutThresholdNumber(hass, entry, coordinator, manager)
    debounce_entity = AvoidBlackoutDebounceNumber(hass, entry, manager)

    async_add_entities([threshold_entity, debounce_entity])

    # Salva riferimenti per aggiornamenti bidirezionali dall'options flow
    data["threshold_entity"] = threshold_entity
    data["debounce_entity"] = debounce_entity
    _LOGGER.debug("Number entities soglia e debounce registrati")


# ─── Classe base condivisa ───────────────────────────────────────────────────

class _AvoidBlackoutNumberBase(NumberEntity):
    """Classe base per i number entity di AvoidBlackout."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    @property
    def device_info(self) -> dict[str, Any]:
        """Raggruppa tutte le entità nello stesso device virtuale."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "AvoidBlackout PowerManager",
            "manufacturer": "AvoidBlackout",
            "model": "PowerManager",
        }


# ─── Soglia Massima ──────────────────────────────────────────────────────────

class AvoidBlackoutThresholdNumber(_AvoidBlackoutNumberBase):
    """Number entity per la soglia massima di potenza (W).

    Le modifiche vengono applicate in tempo reale senza riavvio dell'integrazione
    e persistite nelle options della config entry.
    """

    _attr_icon = "mdi:lightning-bolt"
    _attr_native_unit_of_measurement = "W"
    _attr_translation_key = "max_threshold"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: PowerCoordinator,
        manager: PowerManager,
    ) -> None:
        """Inizializza il number entity per la soglia."""
        super().__init__(entry)
        self.hass = hass
        self._coordinator = coordinator
        self._manager = manager

        self._attr_unique_id = f"{entry.entry_id}_max_threshold"
        self._attr_native_min_value = float(MIN_THRESHOLD)
        self._attr_native_max_value = float(MAX_THRESHOLD)
        self._attr_native_step = float(THRESHOLD_STEP)

        # Valore iniziale: options ha precedenza su data
        config = {**entry.data, **entry.options}
        self._attr_native_value = float(config.get(CONF_MAX_THRESHOLD, DEFAULT_THRESHOLD))

    async def async_set_native_value(self, value: float) -> None:
        """Applica la nuova soglia immediatamente e la persiste nelle options."""
        new_threshold = int(value)
        _LOGGER.info(
            "Soglia massima: %dW → %dW (via entity)",
            int(self._attr_native_value),
            new_threshold,
        )

        # Applica subito al coordinator e manager
        self._coordinator.update_threshold(new_threshold)
        self._manager.update_threshold(new_threshold)

        # Aggiorna stato locale
        self._attr_native_value = float(new_threshold)
        self.async_write_ha_state()

        # Persisti nelle options (flag evita reload inutile nel listener)
        self.hass.data[DOMAIN][self._entry.entry_id]["_updating_threshold"] = True
        current_options = dict(self._entry.options)
        current_options[CONF_MAX_THRESHOLD] = new_threshold
        self.hass.config_entries.async_update_entry(self._entry, options=current_options)

    @callback
    def async_refresh_from_config(self, new_threshold: int) -> None:
        """Sincronizza il valore quando la soglia cambia dalle impostazioni."""
        if int(self._attr_native_value) == new_threshold:
            return
        self._attr_native_value = float(new_threshold)
        self.async_write_ha_state()
        _LOGGER.debug("Soglia sincronizzata da config: %dW", new_threshold)


# ─── Tempo di Debounce ───────────────────────────────────────────────────────

class AvoidBlackoutDebounceNumber(_AvoidBlackoutNumberBase):
    """Number entity per il tempo di debounce (s).

    Le modifiche vengono applicate in tempo reale senza riavvio dell'integrazione
    e persistite nelle options della config entry.
    """

    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "s"
    _attr_translation_key = "debounce_time"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        manager: PowerManager,
    ) -> None:
        """Inizializza il number entity per il debounce."""
        super().__init__(entry)
        self.hass = hass
        self._manager = manager

        self._attr_unique_id = f"{entry.entry_id}_debounce_time"
        self._attr_native_min_value = float(MIN_DEBOUNCE)
        self._attr_native_max_value = float(MAX_DEBOUNCE)
        self._attr_native_step = float(DEBOUNCE_STEP)

        # Valore iniziale: options ha precedenza su data
        config = {**entry.data, **entry.options}
        self._attr_native_value = float(config.get(CONF_DEBOUNCE_TIME, DEFAULT_DEBOUNCE))

    async def async_set_native_value(self, value: float) -> None:
        """Applica il nuovo debounce immediatamente e lo persiste nelle options."""
        new_debounce = int(value)
        _LOGGER.info(
            "Debounce: %ds → %ds (via entity)",
            int(self._attr_native_value),
            new_debounce,
        )

        # Applica subito al manager
        self._manager.update_debounce(new_debounce)

        # Aggiorna stato locale
        self._attr_native_value = float(new_debounce)
        self.async_write_ha_state()

        # Persisti nelle options (flag evita reload inutile nel listener)
        self.hass.data[DOMAIN][self._entry.entry_id]["_updating_debounce"] = True
        current_options = dict(self._entry.options)
        current_options[CONF_DEBOUNCE_TIME] = new_debounce
        self.hass.config_entries.async_update_entry(self._entry, options=current_options)

    @callback
    def async_refresh_from_config(self, new_debounce: int) -> None:
        """Sincronizza il valore quando il debounce cambia dalle impostazioni."""
        if int(self._attr_native_value) == new_debounce:
            return
        self._attr_native_value = float(new_debounce)
        self.async_write_ha_state()
        _LOGGER.debug("Debounce sincronizzato da config: %ds", new_debounce)
