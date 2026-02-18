"""Costanti per l'integrazione AvoidBlackout - PowerManager."""

# Dominio dell'integrazione
DOMAIN = "avoidblackout"

# Configuration keys
CONF_POWER_SENSORS = "power_sensors"
CONF_MAX_THRESHOLD = "max_threshold"
CONF_DEBOUNCE_TIME = "debounce_time"
CONF_MANAGED_ENTITIES = "managed_entities"
CONF_TEST_MODE = "test_mode"

# Default values
DEFAULT_THRESHOLD = 3500  # Watt
DEFAULT_DEBOUNCE = 30  # secondi
DEFAULT_TEST_MODE = False

# Event names
EVENT_LOAD_SHEDDING = "powermanager_load_shedding"

# State machine states
STATE_MONITORING = "monitoring"
STATE_SHEDDING = "shedding"
STATE_WAITING = "waiting"
STATE_TEST_MODE = "test_mode"

# Attributi per verificare sensori di potenza validi
POWER_UNIT_OF_MEASUREMENT = "W"

# Service names
SERVICE_SIMULATE_OVERLOAD = "simulate_overload"
SERVICE_RESET_HISTORY = "reset_history"

# Error messages keys
ERROR_INVALID_POWER_SENSORS = "invalid_power_sensors"
ERROR_NO_DEVICES_SELECTED = "no_devices_selected"
ERROR_THRESHOLD_INVALID = "threshold_invalid"
ERROR_DEBOUNCE_INVALID = "debounce_invalid"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

# Info messages
INFO_SETUP_COMPLETE = "Setup complete"
INFO_TEST_MODE_ACTIVE = "Test mode active"
INFO_LOAD_SHEDDING_TRIGGERED = "Load shedding triggered"

# Limiti validazione
MIN_THRESHOLD = 100  # Watt
MAX_THRESHOLD = 10000  # Watt
MIN_DEBOUNCE = 5  # secondi
MAX_DEBOUNCE = 300  # secondi
THRESHOLD_STEP = 100  # Watt
DEBOUNCE_STEP = 5  # secondi
