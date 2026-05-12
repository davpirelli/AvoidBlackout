"""Integrazione AvoidBlackout - PowerManager per Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from homeassistant.const import CONF_NAME, Platform
from .const import (
    CONF_DEBOUNCE_TIME,
    CONF_MANAGED_ENTITIES,
    CONF_MAX_THRESHOLD,
    CONF_POWER_SENSORS,
    CONF_TEST_MODE,
    DOMAIN,
    SERVICE_SIMULATE_OVERLOAD,
    SERVICE_RESET_HISTORY,
)
from .coordinator import PowerCoordinator
from .power_manager import PowerManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Setup dell'integrazione (non usato, usiamo config flow).

    Args:
        hass: Istanza Home Assistant
        config: Configurazione da configuration.yaml

    Returns:
        True se setup completato
    """
    # L'integrazione usa solo config flow, non configuration.yaml
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup dell'integrazione da config entry.

    Args:
        hass: Istanza Home Assistant
        entry: Config entry creata dal config flow

    Returns:
        True se setup completato con successo
    """
    _LOGGER.info("Setup integrazione AvoidBlackout per entry %s", entry.entry_id)

    # 1. Registra risorsa Lovelace custom per la card (prima di tutto!)
    from homeassistant.components.frontend import add_extra_js_url
    import os

    # Crea il percorso statico per servire i file dalla cartella www dell'integrazione
    static_path = "/avoidblackout_static"
    local_path = os.path.join(os.path.dirname(__file__), "www")
    
    # Registrazione del percorso statico tramite API async (HA 2024.7+).
    # L'API sincrona register_static_path è deprecata e su alcune versioni non
    # garantisce che il file sia servito prima del primo render della dashboard,
    # causando l'errore "Custom element not found: avoidblackout-card" al refresh.
    from homeassistant.components.http import StaticPathConfig
    await hass.http.async_register_static_paths([
        StaticPathConfig(static_path, local_path, True)
    ])
    
    # Aggiunge la card al frontend con un parametro versione per forzare il refresh della cache browser
    version = "1.2.1" # Dovrebbe corrispondere al manifest
    card_url = f"{static_path}/avoidblackout-card.js?v={version}"
    add_extra_js_url(hass, card_url)

    # Registra la card anche come Lovelace dashboard resource.
    # add_extra_js_url da solo non garantisce che lo script sia eseguito PRIMA
    # del primo render della dashboard al refresh: Lovelace tenta di istanziare
    # avoidblackout-card mentre il browser sta ancora scaricando il JS, causando
    # "Custom element doesn't exist". Registrando come resource di Lovelace, lo
    # script viene caricato in modo bloccante prima del bootstrap della dashboard.
    await _async_register_lovelace_resource(hass, card_url)

    # 2. Continua con il setup normale
    # Recupera configurazione unendo data e options
    config = {**entry.data, **entry.options}

    # Crea coordinator per monitoring
    coordinator = PowerCoordinator(hass, config)

    # Crea PowerManager per load shedding
    manager = PowerManager(hass, coordinator, config)

    # Salva nel hass.data per accesso globale
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "manager": manager,
        "config": config,
    }

    # Avvia manager
    await manager.async_start()

    # Avvia coordinator
    await coordinator.async_start()

    # Registra i servizi
    await _async_register_services(hass, entry)

    # Avvia le piattaforme (sensori)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Registra update listener per options flow
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info(
        "Setup completato: %d sensori, %d dispositivi, soglia=%dW",
        len(config.get("power_sensors", [])),
        len(config.get("managed_entities", [])),
        config.get("max_threshold", 0),
    )

    return True


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Registra il JS della card come Lovelace dashboard resource.

    Aggiunge (o aggiorna) una resource di tipo `module` puntando all'URL della
    card. Funziona solo per dashboard Lovelace in modalità storage (default UI).
    Per dashboard in modalità YAML l'utente deve aggiungere manualmente la
    resource nel `configuration.yaml`. Idempotente: aggiorna l'URL esistente
    se già presente (gestisce cambi di versione nel query string).
    """
    try:
        # lovelace_data contiene la dashboard storage collection
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is None:
            _LOGGER.debug("Lovelace non ancora pronto, skip registrazione resource")
            return

        # Accesso compatibile con strutture HA recenti (dataclass) e legacy (dict)
        resources = getattr(lovelace_data, "resources", None)
        if resources is None and isinstance(lovelace_data, dict):
            resources = lovelace_data.get("resources")

        if resources is None:
            _LOGGER.debug("Lovelace resources non disponibili, skip")
            return

        # Carica lista resources se non già fatto
        if hasattr(resources, "async_load") and not getattr(resources, "loaded", True):
            await resources.async_load()

        # URL base senza query string per match (la version cambia tra release)
        base_url = url.split("?")[0]
        existing = None
        for item in resources.async_items():
            item_url = item.get("url", "")
            if item_url.split("?")[0] == base_url:
                existing = item
                break

        if existing:
            # Aggiorna URL solo se diverso (cambio versione → cache bust)
            if existing.get("url") != url:
                await resources.async_update_item(
                    existing["id"], {"url": url, "res_type": "js"}
                )
                _LOGGER.info("Lovelace resource aggiornata: %s", url)
            else:
                _LOGGER.debug("Lovelace resource già presente e aggiornata: %s", url)
        else:
            await resources.async_create_item({"url": url, "res_type": "js"})
            _LOGGER.info("Lovelace resource creata: %s", url)

    except Exception as err:
        # Non bloccare il setup se la registrazione resource fallisce
        # (es. dashboard YAML mode): add_extra_js_url copre comunque il caso base.
        _LOGGER.warning(
            "Impossibile registrare Lovelace resource (%s). "
            "Fallback su add_extra_js_url. Errore: %s",
            url,
            err,
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload dell'integrazione.

    Args:
        hass: Istanza Home Assistant
        entry: Config entry da rimuovere

    Returns:
        True se unload completato con successo
    """
    _LOGGER.info("Unload integrazione AvoidBlackout per entry %s", entry.entry_id)

    # Recupera componenti
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True

    coordinator: PowerCoordinator = data.get("coordinator")
    manager: PowerManager = data.get("manager")

    # Ferma manager
    if manager:
        await manager.async_stop()

    # Ferma coordinator
    if coordinator:
        await coordinator.async_stop()

    # Scarica le piattaforme
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Rimuovi da hass.data se platforms scaricate correttamente
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    else:
        return False

    # Rimuovi servizi se è l'ultima entry rimossa
    if not hass.data[DOMAIN]:
        for service in [SERVICE_SIMULATE_OVERLOAD, SERVICE_RESET_HISTORY]:
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
                _LOGGER.debug("Servizio %s rimosso", service)

    _LOGGER.info("Unload completato")

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Listener smart per aggiornamenti delle opzioni/dati della config entry.

    Applica in tempo reale le modifiche che non richiedono restart (soglia, debounce).
    Esegue un reload completo solo se cambiano elementi strutturali
    (sensori di potenza, dispositivi gestiti, modalità test).

    Args:
        hass: Istanza Home Assistant
        entry: Config entry modificata
    """
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if not data:
        # Nessun dato in memoria → ricarica normalmente
        _LOGGER.warning("Nessun dato in memoria per entry %s, ricarico", entry.entry_id)
        await hass.config_entries.async_reload(entry.entry_id)
        return

    new_config = {**entry.data, **entry.options}
    old_config = data["config"]

    # Trova le chiavi cambiate
    all_keys = set(new_config.keys()) | set(old_config.keys())
    changed_keys = {k for k in all_keys if new_config.get(k) != old_config.get(k)}

    if not changed_keys:
        _LOGGER.debug("Listener opzioni: nessuna modifica rilevata")
        return

    _LOGGER.debug("Listener opzioni: chiavi modificate = %s", changed_keys)

    # Chiavi che richiedono reload completo (cambiano la struttura del sistema)
    reload_required_keys = {CONF_POWER_SENSORS, CONF_MANAGED_ENTITIES, CONF_TEST_MODE}
    needs_reload = changed_keys & reload_required_keys

    if needs_reload:
        _LOGGER.info(
            "Reload completo richiesto per → %s",
            needs_reload,
        )
        await hass.config_entries.async_reload(entry.entry_id)
        return

    # --- Applicazione in-place senza restart ---
    coordinator = data["coordinator"]
    manager = data["manager"]

    if CONF_MAX_THRESHOLD in changed_keys:
        new_threshold = int(new_config[CONF_MAX_THRESHOLD])

        # Controlla se la modifica viene già applicata dal number entity
        # (flag impostato da AvoidBlackoutThresholdNumber.async_set_native_value)
        from_entity = data.pop("_updating_threshold", False)

        if not from_entity:
            # Modifica dall'options flow → applica al coordinator e manager
            coordinator.update_threshold(new_threshold)
            manager.update_threshold(new_threshold)

        # Aggiorna il number entity per tenerlo sincronizzato (se non è stato lui a cambiare)
        threshold_entity = data.get("threshold_entity")
        if threshold_entity:
            threshold_entity.async_refresh_from_config(new_threshold)

        data["config"][CONF_MAX_THRESHOLD] = new_threshold
        _LOGGER.info("Soglia aggiornata in-place: %dW (da_entity=%s)", new_threshold, from_entity)

    if CONF_DEBOUNCE_TIME in changed_keys:
        new_debounce = int(new_config[CONF_DEBOUNCE_TIME])

        # Controlla se la modifica viene già applicata dal debounce entity
        from_entity = data.pop("_updating_debounce", False)

        if not from_entity:
            # Modifica dall'options flow → applica al manager
            manager.update_debounce(new_debounce)

        # Aggiorna il debounce entity per tenerlo sincronizzato
        debounce_entity = data.get("debounce_entity")
        if debounce_entity:
            debounce_entity.async_refresh_from_config(new_debounce)

        data["config"][CONF_DEBOUNCE_TIME] = new_debounce
        _LOGGER.info("Debounce aggiornato in-place: %ds (da_entity=%s)", new_debounce, from_entity)



async def _async_register_services(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Registra i servizi dell'integrazione.

    Args:
        hass: Istanza Home Assistant
        entry: Config entry corrente
    """

    async def handle_simulate_overload(call: ServiceCall) -> None:
        """Gestisce il servizio simulate_overload.

        Args:
            call: Chiamata al servizio
        """
        _LOGGER.info("Servizio simulate_overload chiamato")

        # Recupera manager dalla entry
        # Se non specificato entry_id, usa la prima disponibile
        entry_id = call.data.get("entry_id")

        if entry_id:
            data = hass.data[DOMAIN].get(entry_id)
        else:
            # Usa la prima entry disponibile
            if DOMAIN in hass.data and hass.data[DOMAIN]:
                entry_id = next(iter(hass.data[DOMAIN]))
                data = hass.data[DOMAIN][entry_id]
            else:
                _LOGGER.error("Nessuna entry disponibile per simulate_overload")
                return

        if not data:
            _LOGGER.error("Entry %s non trovata", entry_id)
            return

        manager: PowerManager = data.get("manager")
        if not manager:
            _LOGGER.error("PowerManager non trovato per entry %s", entry_id)
            return

        # Esegui simulazione
        await manager.simulate_overload()

    async def handle_reset_history(call: ServiceCall) -> None:
        """Gestisce il servizio reset_history."""
        _LOGGER.info("Servizio reset_history chiamato")
        entry_id = call.data.get("entry_id")
        
        if entry_id:
            data = hass.data[DOMAIN].get(entry_id)
        else:
            if DOMAIN in hass.data and hass.data[DOMAIN]:
                entry_id = next(iter(hass.data[DOMAIN]))
                data = hass.data[DOMAIN][entry_id]
            else:
                return

        if data:
            manager: PowerManager = data.get("manager")
            if manager:
                manager.reset_shutdown_history()

    # Registra servizi
    hass.services.async_register(
        DOMAIN,
        SERVICE_SIMULATE_OVERLOAD,
        handle_simulate_overload,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_HISTORY,
        handle_reset_history,
    )
    _LOGGER.debug("Servizi AvoidBlackout registrati")


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Chiamato quando la config entry viene rimossa.

    Args:
        hass: Istanza Home Assistant
        entry: Config entry rimossa
    """
    _LOGGER.info("Config entry %s rimossa", entry.entry_id)
    # Cleanup già fatto in async_unload_entry
