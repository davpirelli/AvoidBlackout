"""Config flow per AvoidBlackout - PowerManager."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEBOUNCE_TIME,
    CONF_MANAGED_ENTITIES,
    CONF_MAX_THRESHOLD,
    CONF_POWER_SENSORS,
    CONF_TEST_MODE,
    DEBOUNCE_STEP,
    DEFAULT_DEBOUNCE,
    DEFAULT_TEST_MODE,
    DEFAULT_THRESHOLD,
    DOMAIN,
    ERROR_DEBOUNCE_INVALID,
    ERROR_INVALID_POWER_SENSORS,
    ERROR_NO_DEVICES_SELECTED,
    ERROR_THRESHOLD_INVALID,
    MAX_DEBOUNCE,
    MAX_THRESHOLD,
    MIN_DEBOUNCE,
    MIN_THRESHOLD,
    POWER_UNIT_OF_MEASUREMENT,
    THRESHOLD_STEP,
)

_LOGGER = logging.getLogger(__name__)


class AvoidBlackoutConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestisce il config flow per AvoidBlackout."""

    VERSION = 1

    def __init__(self) -> None:
        """Inizializza il config flow."""
        self._config_data: dict[str, Any] = {}
        self._errors: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Gestisce il primo step: benvenuto e opzione test mode.

        Args:
            user_input: Dati inseriti dall'utente

        Returns:
            FlowResult con form o avanzamento a step successivo
        """
        errors = {}

        if user_input is not None:
            # Salva test_mode
            self._config_data[CONF_TEST_MODE] = user_input.get(
                CONF_TEST_MODE, DEFAULT_TEST_MODE
            )
            _LOGGER.debug("Step user completato, test_mode=%s", self._config_data[CONF_TEST_MODE])
            return await self.async_step_sensors()

        # Schema primo step
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TEST_MODE,
                    default=DEFAULT_TEST_MODE,
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "name": "AvoidBlackout - PowerManager",
            },
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Gestisce la selezione dei sensori di potenza.

        Args:
            user_input: Dati inseriti dall'utente

        Returns:
            FlowResult con form o avanzamento a step successivo
        """
        errors = {}

        if user_input is not None:
            sensors = user_input.get(CONF_POWER_SENSORS, [])

            # Validazione sensori
            valid, error_key = self._validate_power_sensors(self.hass, sensors)

            if valid:
                self._config_data[CONF_POWER_SENSORS] = sensors
                _LOGGER.debug(
                    "Step sensors completato, %d sensori selezionati",
                    len(sensors),
                )
                return await self.async_step_threshold()
            else:
                errors["base"] = error_key

        # Schema selezione sensori
        data_schema = vol.Schema(
            {
                vol.Required(CONF_POWER_SENSORS): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="sensors",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_threshold(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Gestisce l'impostazione di soglia e debounce.

        Args:
            user_input: Dati inseriti dall'utente

        Returns:
            FlowResult con form o avanzamento a step successivo
        """
        errors = {}

        if user_input is not None:
            threshold = user_input.get(CONF_MAX_THRESHOLD, DEFAULT_THRESHOLD)
            debounce = user_input.get(CONF_DEBOUNCE_TIME, DEFAULT_DEBOUNCE)

            # Validazione
            threshold_valid, threshold_error = self._validate_threshold(threshold)
            debounce_valid, debounce_error = self._validate_debounce(debounce)

            if threshold_valid and debounce_valid:
                self._config_data[CONF_MAX_THRESHOLD] = threshold
                self._config_data[CONF_DEBOUNCE_TIME] = debounce
                _LOGGER.debug(
                    "Step threshold completato, soglia=%dW, debounce=%ds",
                    threshold,
                    debounce,
                )
                return await self.async_step_devices()
            else:
                if not threshold_valid:
                    errors["base"] = threshold_error
                elif not debounce_valid:
                    errors["base"] = debounce_error

        # Schema soglie
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAX_THRESHOLD,
                    default=DEFAULT_THRESHOLD,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_THRESHOLD,
                        max=MAX_THRESHOLD,
                        step=THRESHOLD_STEP,
                        unit_of_measurement="W",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_DEBOUNCE_TIME,
                    default=DEFAULT_DEBOUNCE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DEBOUNCE,
                        max=MAX_DEBOUNCE,
                        step=DEBOUNCE_STEP,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="threshold",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Gestisce la selezione dei dispositivi da gestire.

        Args:
            user_input: Dati inseriti dall'utente

        Returns:
            FlowResult con form o avanzamento a step successivo
        """
        errors = {}

        if user_input is not None:
            devices = user_input.get(CONF_MANAGED_ENTITIES, [])

            # Validazione
            if not devices or len(devices) == 0:
                errors["base"] = ERROR_NO_DEVICES_SELECTED
            else:
                self._config_data[CONF_MANAGED_ENTITIES] = devices
                _LOGGER.debug(
                    "Step devices completato, %d dispositivi selezionati",
                    len(devices),
                )
                return await self.async_step_confirm()

        # Schema dispositivi
        data_schema = vol.Schema(
            {
                vol.Required(CONF_MANAGED_ENTITIES): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["switch", "light"],
                        multiple=True,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="devices",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Step finale: conferma e creazione entry.

        Args:
            user_input: Conferma dall'utente

        Returns:
            FlowResult con creazione entry
        """
        if user_input is not None or user_input is None:
            # Crea entry con tutti i dati raccolti
            title = "AvoidBlackout PowerManager"

            _LOGGER.info(
                "Creazione config entry: sensori=%d, dispositivi=%d, soglia=%dW",
                len(self._config_data.get(CONF_POWER_SENSORS, [])),
                len(self._config_data.get(CONF_MANAGED_ENTITIES, [])),
                self._config_data.get(CONF_MAX_THRESHOLD, 0),
            )

            return self.async_create_entry(title=title, data=self._config_data)

        # Mostra riepilogo configurazione
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "sensors_count": str(len(self._config_data.get(CONF_POWER_SENSORS, []))),
                "threshold": str(self._config_data.get(CONF_MAX_THRESHOLD, 0)),
                "debounce": str(self._config_data.get(CONF_DEBOUNCE_TIME, 0)),
                "devices_count": str(len(self._config_data.get(CONF_MANAGED_ENTITIES, []))),
                "test_mode": "Sì" if self._config_data.get(CONF_TEST_MODE, False) else "No",
            },
        )

    @staticmethod
    def _validate_power_sensors(hass, sensors: list[str]) -> tuple[bool, str | None]:
        """Valida che i sensori selezionati siano sensori di potenza validi.

        Args:
            hass: Istanza Home Assistant
            sensors: Lista entity_id dei sensori

        Returns:
            Tuple (is_valid, error_key)
        """
        if not sensors or len(sensors) == 0:
            return False, ERROR_INVALID_POWER_SENSORS

        for entity_id in sensors:
            state = hass.states.get(entity_id)

            if state is None:
                _LOGGER.warning("Sensore %s non trovato (ma proseguo comunque)", entity_id)
                # Non blocchiamo la validazione per sensori mancanti (es. non ancora inizializzati)
                # return False, ERROR_INVALID_POWER_SENSORS
                continue

            # Verifica unit_of_measurement
            unit = state.attributes.get("unit_of_measurement")
            if unit != POWER_UNIT_OF_MEASUREMENT:
                _LOGGER.warning(
                    "Sensore %s non ha unit_of_measurement='W' (ha '%s')",
                    entity_id,
                    unit,
                )
                return False, ERROR_INVALID_POWER_SENSORS

        return True, None

    @staticmethod
    def _validate_threshold(threshold: int) -> tuple[bool, str | None]:
        """Valida la soglia massima.

        Args:
            threshold: Soglia in Watt

        Returns:
            Tuple (is_valid, error_key)
        """
        if threshold < MIN_THRESHOLD or threshold > MAX_THRESHOLD:
            return False, ERROR_THRESHOLD_INVALID

        return True, None

    @staticmethod
    def _validate_debounce(debounce: int) -> tuple[bool, str | None]:
        """Valida il tempo di debounce.

        Args:
            debounce: Tempo in secondi

        Returns:
            Tuple (is_valid, error_key)
        """
        if debounce < MIN_DEBOUNCE or debounce > MAX_DEBOUNCE:
            return False, ERROR_DEBOUNCE_INVALID

        return True, None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AvoidBlackoutOptionsFlow:
        """Ottiene l'options flow per modificare configurazione.

        Args:
            config_entry: Config entry esistente

        Returns:
            Instance di AvoidBlackoutOptionsFlow
        """
        return AvoidBlackoutOptionsFlow(config_entry)


class AvoidBlackoutOptionsFlow(config_entries.OptionsFlow):
    """Gestisce l'options flow per modificare configurazione esistente."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Inizializza l'options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Gestisce la modifica della configurazione.

        Args:
            user_input: Nuovi dati inseriti

        Returns:
            FlowResult con form o salvataggio options
        """
        errors = {}

        if user_input is not None:
            # Recupera valori
            sensors = user_input.get(CONF_POWER_SENSORS, [])
            threshold = user_input.get(CONF_MAX_THRESHOLD)
            debounce = user_input.get(CONF_DEBOUNCE_TIME)
            devices = user_input.get(CONF_MANAGED_ENTITIES, [])

            # Validazione
            sensors_valid, _ = AvoidBlackoutConfigFlow._validate_power_sensors(self.hass, sensors)
            threshold_valid, _ = AvoidBlackoutConfigFlow._validate_threshold(threshold)
            debounce_valid, _ = AvoidBlackoutConfigFlow._validate_debounce(debounce)
            
            devices_valid = True
            if not devices:
                devices_valid = False
                
            if sensors_valid and threshold_valid and debounce_valid and devices_valid:
                # Aggiorna options
                _LOGGER.info(
                    "Configurazione aggiornata: soglia=%dW, debounce=%ds",
                    threshold,
                    debounce,
                )
                return self.async_create_entry(title="", data=user_input)
            else:
                if not sensors_valid:
                    errors["base"] = ERROR_INVALID_POWER_SENSORS
                elif not devices_valid:
                    errors["base"] = ERROR_NO_DEVICES_SELECTED
                else:
                    errors["base"] = "invalid_input"

        # Schema per modificare TUTTI i parametri
        current_config = {**self.config_entry.data, **self.config_entry.options}

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_POWER_SENSORS,
                    default=current_config.get(CONF_POWER_SENSORS, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        multiple=True,
                    )
                ),
                vol.Required(
                    CONF_MAX_THRESHOLD,
                    default=current_config.get(CONF_MAX_THRESHOLD, DEFAULT_THRESHOLD),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_THRESHOLD,
                        max=MAX_THRESHOLD,
                        step=THRESHOLD_STEP,
                        unit_of_measurement="W",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_DEBOUNCE_TIME,
                    default=current_config.get(CONF_DEBOUNCE_TIME, DEFAULT_DEBOUNCE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_DEBOUNCE,
                        max=MAX_DEBOUNCE,
                        step=DEBOUNCE_STEP,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_MANAGED_ENTITIES,
                    default=current_config.get(CONF_MANAGED_ENTITIES, []),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["switch", "light"],
                        multiple=True,
                    )
                ),
                vol.Optional(
                    CONF_TEST_MODE,
                    default=current_config.get(CONF_TEST_MODE, DEFAULT_TEST_MODE),
                ): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
        )
