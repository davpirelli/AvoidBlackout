"""Integrazione AvoidBlackout - PowerManager per Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from homeassistant.const import CONF_NAME, Platform
from .const import (
    CONF_TEST_MODE,
    DOMAIN,
    SERVICE_SIMULATE_OVERLOAD,
    SERVICE_RESET_HISTORY,
)
from .coordinator import PowerCoordinator
from .power_manager import PowerManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


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
    
    # Registrazione del percorso statico (compatibile con vecchie e nuove versioni di HA)
    if hasattr(hass.http, "register_static_path"):
        hass.http.register_static_path(static_path, local_path)
    else:
        # Fallback per versioni HA 2024.12+ 
        from homeassistant.components.http import StaticPathConfig
        await hass.http.async_register_static_paths([
            StaticPathConfig(static_path, local_path, True)
        ])
    
    # Aggiunge la card al frontend con un parametro versione per forzare il refresh della cache browser
    version = "1.0.3" # Dovrebbe corrispondere al manifest
    add_extra_js_url(hass, f"{static_path}/avoidblackout-card.js?v={version}")

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
    """Ricarica l'integrazione quando le options cambiano.

    Args:
        hass: Istanza Home Assistant
        entry: Config entry modificata
    """
    _LOGGER.info("Reload integrazione AvoidBlackout per entry %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


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
