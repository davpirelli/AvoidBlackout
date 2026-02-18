"""PowerManager - Core logic per load shedding intelligente."""
import asyncio
from datetime import datetime
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_DEBOUNCE_TIME,
    CONF_MANAGED_ENTITIES,
    CONF_MAX_THRESHOLD,
    CONF_TEST_MODE,
    EVENT_LOAD_SHEDDING,
    STATE_MONITORING,
    STATE_SHEDDING,
    STATE_WAITING,
)
from .coordinator import PowerCoordinator
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)


class PowerManager:
    """Gestisce la logica di load shedding con state machine.

    State Machine:
    MONITORING → (power > threshold per debounce_time) → SHEDDING
    SHEDDING → (spegne dispositivo) → WAITING
    WAITING → (attesa debounce_time) →
        ├─ Se ancora sopra soglia: SHEDDING (spegne successivo)
        └─ Se sotto soglia: MONITORING
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PowerCoordinator,
        config: dict[str, Any],
    ) -> None:
        """Inizializza il PowerManager.

        Args:
            hass: Istanza Home Assistant
            coordinator: PowerCoordinator per dati potenza
            config: Configurazione con threshold, debounce, managed_entities, test_mode
        """
        self.hass = hass
        self.coordinator = coordinator
        self._threshold = config[CONF_MAX_THRESHOLD]
        self._debounce_time = config[CONF_DEBOUNCE_TIME]
        self._managed_entities = config[CONF_MANAGED_ENTITIES]
        self._test_mode = config.get(CONF_TEST_MODE, False)

        self._state = STATE_MONITORING
        self._debounce_task = None
        self._current_priority_index = 0
        self._shutdown_entities = []  # Lista dispositivi già spenti
        self._listeners = set()

        self._unsub_coordinator = None
        self._unsub_entities = None
        
        # ... (omitted)

    @callback
    def async_add_listener(self, update_callback) -> callback:
        """Aggiunge un listener per i cambiamenti di stato del manager."""
        self._listeners.add(update_callback)
        
        @callback
        def remove_listener():
            self._listeners.discard(update_callback)
            
        return remove_listener

    @callback
    def _notify_listeners(self) -> None:
        """Notifica tutti i listener del cambiamento di stato."""
        for update_callback in self._listeners:
            update_callback()

        _LOGGER.info(
            "PowerManager inizializzato: soglia=%dW, debounce=%ds, dispositivi=%d, test_mode=%s",
            self._threshold,
            self._debounce_time,
            len(self._managed_entities),
            self._test_mode,
        )


    async def async_start(self) -> None:
        """Avvia il PowerManager registrando listener sul coordinator e sui device."""
        # 1. Listener aggiornamenti di potenza
        self._unsub_coordinator = self.coordinator.async_add_listener(self._handle_power_update)
        
        # 2. Listener stato dispositivi (per rilevare accensioni manuali durante overload)
        self._unsub_entities = async_track_state_change_event(
            self.hass,
            self._managed_entities,
            self._handle_entity_state_change
        )
        
        _LOGGER.info("PowerManager avviato, stato iniziale: %s", self._state)

        # 3. Controllo iniziale immediato (con ritardo di sicurezza)
        # Se il coordinator ha già dati, verifichiamo tra poco per lasciare respirare il loop
        if self.coordinator.data:
            self.hass.async_create_task(self._delayed_initial_check())

    async def _delayed_initial_check(self) -> None:
        """Esegue il controllo iniziale dopo un breve ritardo."""
        await asyncio.sleep(1)
        if self._state == STATE_MONITORING:  # Verifica che siamo ancora attivi
            _LOGGER.debug("Eseguendo controllo stato iniziale ritardato")
            self._handle_power_update()

    async def async_stop(self) -> None:
        """Ferma il PowerManager e cancella task pendenti."""
        # 1. Rimuovi listener coordinator
        if self._unsub_coordinator:
            self._unsub_coordinator()
            self._unsub_coordinator = None
            _LOGGER.debug("Listener coordinator rimosso")

        # 2. Rimuovi listener entità
        if self._unsub_entities:
            self._unsub_entities()
            self._unsub_entities = None
            _LOGGER.debug("Listener entità rimosso")

        # 3. Cancella task pendente e attendi terminazione

        if self._debounce_task:
            if not self._debounce_task.done():
                self._debounce_task.cancel()
                # Non attendere await qui per evitare deadlock se stop è chiamato dal task stesso
                # L'evento CancelledError verrà gestito nel task loop
            
            self._debounce_task = None
            _LOGGER.debug("Task debounce richiesto cancellazione")

        self._state = STATE_MONITORING
        self._current_priority_index = 0
        self._shutdown_entities = []
        _LOGGER.info("PowerManager fermato")

    @callback
    def _handle_power_update(self) -> None:
        """Chiamato quando il coordinator aggiorna i dati di potenza.

        Implementa la logica della state machine.
        """
        data = self.coordinator.data
        total_power = data.get("total_power", 0)
        is_over = data.get("is_over_threshold", False)

        _LOGGER.debug(
            "Aggiornamento potenza: %.1fW, soglia superata=%s, stato=%s",
            total_power,
            is_over,
            self._state,
        )

        if self._state == STATE_MONITORING:
            if is_over:
                # Potenza sopra soglia: avvia debounce
                _LOGGER.info(
                    "Soglia superata (%.1fW > %dW), avvio debounce di %ds",
                    total_power,
                    self._threshold,
                    self._debounce_time,
                )
                self.hass.async_create_task(self._start_debounce())
            else:
                # Tutto OK, continua monitoring
                pass

        elif self._state == STATE_WAITING:
            if not is_over:
                # La potenza è rientrata durante l'attesa!
                _LOGGER.info("Carico rientrato sotto soglia durante attesa, annullo intervento")
                if self._debounce_task and not self._debounce_task.done():
                    self._debounce_task.cancel()
                # Passiamo subito allo stato monitoring per aggiornare la UI istantaneamente
                self._reset_to_monitoring()

    @callback
    def _handle_entity_state_change(self, event) -> None:
        """Chiamato quando uno dei dispositivi gestiti cambia stato.

        Se un dispositivo viene ACCESO mentre siamo in MONITORING e c'è overload,
        dobbiamo attivare subito la logica, perché il consumo potrebbe essere costante (simulato)
        e non triggerare il coordinator.
        """
        if self._state != STATE_MONITORING:
            return

        new_state = event.data.get("new_state")
        if new_state is None or new_state.state != "on":
            return

        # Verifica se c'è overload corrente
        data = self.coordinator.data
        if not data:
            return
            
        is_over = data.get("is_over_threshold", False)
        
        if is_over:
            _LOGGER.info(
                "Rilevata accensione manuale di %s durante overload (%.1fW > %dW), riavvio gestione",
                event.data.get("entity_id"),
                data.get("total_power", 0),
                self._threshold,
            )
            # Simula un update di potenza per far ripartire la macchina a stati
            self._handle_power_update()

    async def _start_debounce(self) -> None:
        """Avvia il timer di debounce.

        Cambia stato in WAITING e aspetta per debounce_time secondi.
        Se la potenza rientra prima della scadenza, il task viene cancellato.
        """
        # Cancella eventuale task precedente
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
            _LOGGER.debug("Task debounce precedente cancellato")

        self._state = STATE_WAITING
        self._notify_listeners()
        self._debounce_task = self.hass.async_create_task(self._wait_and_check())

    async def _wait_and_check(self) -> None:
        """Aspetta il tempo di debounce e poi verifica se occorre spegnere.

        Se durante l'attesa la potenza rientra, questo task viene cancellato.
        """
        try:
            _LOGGER.debug("Inizio attesa debounce: %ds", self._debounce_time)
            await asyncio.sleep(self._debounce_time)

            # Dopo l'attesa, controlla ancora lo stato
            data = self.coordinator.data
            is_over = data.get("is_over_threshold", False)
            total_power = data.get("total_power", 0)

            if is_over:
                # Ancora sopra soglia dopo debounce: spegni dispositivo
                _LOGGER.warning(
                    "Soglia ancora superata dopo debounce (%.1fW > %dW), attivo load shedding",
                    total_power,
                    self._threshold,
                )
                await self._shed_next_load()
            else:
                # Potenza rientrata durante debounce
                _LOGGER.info(
                    "Potenza rientrata sotto soglia (%.1fW), torno a monitoring",
                    total_power,
                )
                self._reset_to_monitoring()

        except asyncio.CancelledError:
            # Timer cancellato perché potenza rientrata
            _LOGGER.info("Debounce cancellato, potenza rientrata prima della scadenza")
            self._reset_to_monitoring()

    async def _shed_next_load(self) -> None:
        """Spegne il prossimo dispositivo disponibile nella lista priorità.

        Scorre la lista dei dispositivi gestiti in ordine di priorità.
        Il primo dispositivo trovato ACCESO viene spento.
        """
        target_entity_id = None
        priority_index = -1

        # Cerca il primo dispositivo acceso
        for index, entity_id in enumerate(self._managed_entities):
            state = self.hass.states.get(entity_id)
            if state and state.state == "on":
                target_entity_id = entity_id
                priority_index = index
                break
            else:
                _LOGGER.debug(
                    "Dispositivo %s (priorità %d) già spento o non disponibile (stato: %s), passo al prossimo",
                    entity_id,
                    index,
                    state.state if state else "None",
                )

        # Se non abbiamo trovato nessun dispositivo da spegnere
        if target_entity_id is None:
            _LOGGER.error(
                "Nessun dispositivo da spegnere trovato! Tutti i dispositivi gestiti risultano già spenti. "
                "Potenza attuale: %.1fW > %dW. Torno a monitoring.",
                self.coordinator.data.get("total_power", 0),
                self._threshold,
            )
            self._reset_to_monitoring()
            return

        # Abbiamo un bersaglio
        total_power = self.coordinator.data.get("total_power", 0)
        self._current_priority_index = priority_index  # Aggiorniamo l'indice per coerenza nei log

        if self._test_mode:
            # Modalità test: non spegne realmente
            _LOGGER.info(
                "TEST MODE: Simulazione spegnimento di %s (priorità %d)",
                target_entity_id,
                priority_index,
            )
            # In test mode, dobbiamo simulare che sia stato "gestito" per non loopare sempre sullo stesso
            # Ma dato che la richiesta è di basarsi sullo stato reale, in test mode questo creerà un loop
            # a meno che l'utente non lo spenga davvero.
            # Per evitare spam in test mode, potremmo dover gestire diversamente, ma per ora seguiamo la logica reale.
        else:
            # Spegni realmente il dispositivo
            _LOGGER.warning(
                "Spegnimento dispositivo %s (priorità %d) per load shedding",
                target_entity_id,
                priority_index,
            )
            try:
                await self._turn_off_entity(target_entity_id)
            except Exception as err:
                _LOGGER.error(
                    "Errore durante spegnimento di %s: %s",
                    target_entity_id,
                    err,
                )
                # Genera evento con flag di errore
                self._fire_load_shedding_event(
                    target_entity_id,
                    total_power,
                    error=str(err),
                )
                # Se fallisce lo spegnimento, purtroppo al prossimo giro lo ritroveremo "on" e riproveremo.
                # Questo è corretto per sicurezza. Per evitare loop infiniti su errori, servirebbe logica più complessa,
                # ma per ora riproviamo dopo il debounce.
                await self._start_debounce()
                return

        # Registra spegnimento
        if target_entity_id not in self._shutdown_entities:
            self._shutdown_entities.append(target_entity_id)
            self._notify_listeners()

        # Genera evento per notifiche
        self._fire_load_shedding_event(target_entity_id, total_power)

        # Entra in stato WAITING per prossimo debounce
        _LOGGER.debug("Entro in WAITING dopo spegnimento, avvio nuovo debounce")
        await self._start_debounce()

    async def _turn_off_entity(self, entity_id: str) -> None:
        """Spegne un'entità chiamando il servizio appropriato.

        Args:
            entity_id: ID dell'entità da spegnere (es. switch.device_1)

        Raises:
            Exception: Se il servizio fallisce
        """
        domain = entity_id.split(".")[0]

        _LOGGER.info("Tentativo spegnimento %s: chiamata servizio %s.turn_off", entity_id, domain)

        # Verifica che l'entità esista
        state = self.hass.states.get(entity_id)
        if state is None:
            _LOGGER.error("Entità %s non trovata!", entity_id)
            raise ValueError(f"Entità {entity_id} non esiste")

        _LOGGER.debug("Stato attuale di %s: %s", entity_id, state.state)

        await self.hass.services.async_call(
            domain,
            "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

        _LOGGER.info("Dispositivo %s spento con successo", entity_id)

    def _fire_load_shedding_event(
        self,
        entity_id: str,
        total_power: float,
        error: str | None = None,
    ) -> None:
        """Genera evento di load shedding per automazioni.

        Args:
            entity_id: Dispositivo spento
            total_power: Potenza totale al momento dello spegnimento
            error: Messaggio di errore opzionale
        """
        event_data = {
            "entity_id": entity_id,
            "priority": self._current_priority_index,
            "total_power": total_power,
            "threshold": self._threshold,
            "timestamp": datetime.now().isoformat(),
            "test_mode": self._test_mode,
        }

        if error:
            event_data["error"] = error

        self.hass.bus.async_fire(EVENT_LOAD_SHEDDING, event_data)

        _LOGGER.info(
            "Evento %s generato: entity=%s, power=%.1fW, priority=%d",
            EVENT_LOAD_SHEDDING,
            entity_id,
            total_power,
            self._current_priority_index,
        )

    def _reset_to_monitoring(self) -> None:
        """Resetta lo stato a MONITORING.

        NON resetta current_priority_index e shutdown_entities per mantenere
        traccia di cosa è stato spento (utente deve riaccendere manualmente).
        """
        old_state = self._state
        self._state = STATE_MONITORING

        if old_state != STATE_MONITORING:
            # Resetta sempre lo storico quando si torna sotto soglia
            # Così al prossimo evento si ricontrolla tutto dall'inizio
            self._current_priority_index = 0
            self._shutdown_entities = []
            
            _LOGGER.info(
                "Transizione stato: %s -> %s (Reset priorità e storico spegnimenti)",
                old_state,
                STATE_MONITORING,
            )
            self._notify_listeners()

    async def simulate_overload(self) -> None:
        """Simula un superamento della soglia per testing.

        Funziona solo se test_mode è attivo.
        """
        if not self._test_mode:
            _LOGGER.warning(
                "simulate_overload chiamato ma test_mode non è attivo, ignoro"
            )
            return

        _LOGGER.info("SIMULAZIONE: Forzatura condizione di sovraccarico")

        # Simula direttamente uno shed
        if self._current_priority_index >= len(self._managed_entities):
            _LOGGER.warning("SIMULAZIONE: Tutti i dispositivi già simulati come spenti")
            return

        await self._shed_next_load()

    def reset_shutdown_history(self) -> None:
        """Resetta lo storico degli spegnimenti.

        Utile se l'utente ha riacceso manualmente i dispositivi e vuole
        ricominciare dalla priorità 0.
        """
        old_count = len(self._shutdown_entities)
        self._shutdown_entities = []
        self._current_priority_index = 0
        self._notify_listeners()

        _LOGGER.info(
            "Storico spegnimenti resettato (%d dispositivi erano stati spenti)",
            old_count,
        )

    def get_status(self) -> dict[str, Any]:
        """Ritorna lo stato corrente del PowerManager.

        Returns:
            Dict con stato, dispositivi spenti, prossima priorità
        """
        return {
            "state": self._state,
            "shutdown_entities": self._shutdown_entities.copy(),
            "next_priority_index": self._current_priority_index,
            "test_mode": self._test_mode,
            "threshold": self._threshold,
            "debounce_time": self._debounce_time,
            "managed_entities_count": len(self._managed_entities),
        }
