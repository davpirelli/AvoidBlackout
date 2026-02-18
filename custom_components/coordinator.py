"""PowerCoordinator per monitoraggio real-time dei sensori di potenza."""
from datetime import datetime
import logging
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_MAX_THRESHOLD, CONF_POWER_SENSORS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PowerCoordinator(DataUpdateCoordinator):
    """Coordinator per monitorare i sensori di potenza in tempo reale.

    Usa un approccio event-driven (non polling) per massimizzare performance e reattività.
    """

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Inizializza il coordinator.

        Args:
            hass: Istanza Home Assistant
            config: Configurazione con power_sensors e max_threshold
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Event-driven, no polling
        )
        self._power_sensors = config[CONF_POWER_SENSORS]
        self._threshold = config[CONF_MAX_THRESHOLD]
        self._unsubscribe = None
        _LOGGER.debug(
            "PowerCoordinator inizializzato con %d sensori, soglia %dW",
            len(self._power_sensors),
            self._threshold,
        )

    async def async_start(self) -> None:
        """Avvia il monitoring dei sensori.

        Registra listener per state changes e calcola i valori iniziali.
        """
        # Registra listener per cambiamenti di stato
        self._unsubscribe = async_track_state_change_event(
            self.hass,
            self._power_sensors,
            self._handle_state_change,
        )

        # Calcolo iniziale
        self.data = await self._calculate_total_power()
        _LOGGER.info("Monitoring avviato per %d sensori", len(self._power_sensors))

    async def async_stop(self) -> None:
        """Ferma il monitoring e rimuove i listener."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None
            _LOGGER.info("Monitoring fermato")

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Callback chiamato quando uno dei sensori cambia stato.

        Args:
            event: Evento di cambio stato
        """
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")

        if new_state is None:
            _LOGGER.debug("Sensore %s rimosso, ignorato", entity_id)
            return

        _LOGGER.debug(
            "Cambio stato rilevato per %s: %s",
            entity_id,
            new_state.state,
        )

        # Ricalcola potenza totale
        self.hass.async_create_task(self._async_update_power())

    async def _async_update_power(self) -> None:
        """Ricalcola la potenza totale e notifica i listener."""
        self.data = await self._calculate_total_power()
        # Notifica tutti i listener (PowerManager)
        self.async_update_listeners()

    async def _calculate_total_power(self) -> dict[str, Any]:
        """Calcola la potenza totale da tutti i sensori.

        Returns:
            Dict con total_power, sensor_values, last_update, is_over_threshold
        """
        total = 0.0
        sensor_values = {}

        for entity_id in self._power_sensors:
            state = self.hass.states.get(entity_id)

            if state is None:
                # Potrebbe non essere ancora pronto all'avvio
                _LOGGER.debug("Sensore %s non trovato (o non ancora disponibile)", entity_id)
                continue

            if state.state in ["unknown", "unavailable"]:
                _LOGGER.debug(
                    "Sensore %s in stato %s, ignorato",
                    entity_id,
                    state.state,
                )
                sensor_values[entity_id] = None
                continue

            try:
                value = float(state.state)
                sensor_values[entity_id] = value
                total += value
                _LOGGER.debug("Sensore %s: %.1fW", entity_id, value)
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Impossibile convertire valore di %s a float: %s (errore: %s)",
                    entity_id,
                    state.state,
                    err,
                )
                sensor_values[entity_id] = None

        is_over_threshold = total > self._threshold

        _LOGGER.debug(
            "Potenza totale calcolata: %.1fW (soglia: %dW, superata: %s)",
            total,
            self._threshold,
            is_over_threshold,
        )

        return {
            "total_power": total,
            "sensor_values": sensor_values,
            "last_update": datetime.now(),
            "is_over_threshold": is_over_threshold,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data - chiamato solo manualmente o al setup iniziale.

        Returns:
            Dati di potenza calcolati
        """
        return await self._calculate_total_power()

    def update_threshold(self, new_threshold: int) -> None:
        """Aggiorna la soglia massima.

        Args:
            new_threshold: Nuova soglia in Watt
        """
        old_threshold = self._threshold
        self._threshold = new_threshold
        _LOGGER.info(
            "Soglia aggiornata: %dW -> %dW",
            old_threshold,
            new_threshold,
        )

        # Ricalcola per aggiornare is_over_threshold
        self.hass.async_create_task(self._async_update_power())
