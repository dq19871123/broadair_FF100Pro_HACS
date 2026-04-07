"""Constants for Broad Fresh Air integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "broadair"

# API Configuration
API_HOST: Final = "broadair.remotcon.mobi"
API_PORT: Final = 8201
API_BASE_URL: Final = f"https://{API_HOST}:{API_PORT}"

# App Token (fixed secret for sign calculation)
APP_TOKEN: Final = "8q7l82AxXB8Qo99vesUUvy1ED5tIuPT31NoIL6ZE5THH7clkfN"

# Endpoints
ENDPOINT_LOGIN: Final = "/api/System/Login"
ENDPOINT_DEVICES: Final = "/api/Equipment/GetEquipments"
ENDPOINT_CONTROL: Final = "/api/Equipment/SetFreshLung"

# Commands (sjx values)
CMD_POLL: Final = "1"
CMD_POWER_OFF: Final = "2"
CMD_POWER_ON: Final = "3"
CMD_SET_SPEED: Final = "4"
CMD_SLEEP_MODE: Final = "5"
CMD_RESET_HEPA_FILTER: Final = "8"
CMD_RESET_COARSE_FILTER: Final = "9"

# Defaults
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)
FAN_SPEED_COUNT: Final = 3

# Config keys
CONF_TOKEN: Final = "token"
CONF_ACCOUNT: Final = "account"
CONF_PASSWORD: Final = "password"
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_MAC: Final = "device_mac"
CONF_DEVICE_MODEL: Final = "device_model"

# State field names from API response - Core status
FIELD_POWER: Final = "FB_ON"
FIELD_GEAR: Final = "GEAR_POSITION"
FIELD_RUNNING_GEAR: Final = "RUNNING_GEAR"
FIELD_AIR_VOLUME: Final = "AIR_VOLUME"
FIELD_SLEEP_MODE: Final = "FB_SLEEPMODEL_ON"
FIELD_AUTO_MODE: Final = "FB_AUTOMODEL_ON"
FIELD_FAULT: Final = "FAULT"
FIELD_ALL_FAULT: Final = "ALLFAULT"
FIELD_EXCEPTION_REMINDER: Final = "EXCEPTION_REMINDER"

# Filter life fields
FIELD_HEPA_LIFE_CYCLE: Final = "EFFICIENT_LIFE_CYCLE"
FIELD_HEPA_USED_TIME: Final = "EFFICIENT_USED_TIME"
FIELD_HEPA_TIME_CLEARING: Final = "EFFICIENT_TIME_CLEARING"
FIELD_PRIMARY_CLEANING_CYCLE: Final = "PRIMARY_CLEANING_CYCLE"
FIELD_COARSE_USED_TIME: Final = "COARSE_USED_TIME"
FIELD_COARSE_TIME_CLEARING: Final = "COARSE_TIME_CLEARING"

# Air quality sensor fields
FIELD_CO2: Final = "CO2_CONCENTRATION"
FIELD_PM_0_3: Final = "PM_0_3"
FIELD_PM_2_5: Final = "PM_2_5"
FIELD_PM_10: Final = "PM_10"
FIELD_PM_2_5_DUST: Final = "PM_2_5_DUST_CONCENTRATION"
FIELD_ROOM_TEMP: Final = "ROOM_TEMPERATURE"

# Sensor module accessories (0 = not installed, 1 = installed)
FIELD_CO2_MODULE: Final = "CO2_MODULE_ACCESSORIES"
FIELD_DUST_MODULE: Final = "DUST_MODULE_ACCESSORIES"
FIELD_TEMP_MODULE: Final = "TEMPERATURE_MODULE_ACCESSORIES"

# Module failure flags
FIELD_DUST_MODULE_FAILURE: Final = "DUST_MODULE_COMMUNICATION_FAILURE"
FIELD_TEMP_MODULE_FAILURE: Final = "TEMPERATURE_MODULE_FAILURE"

# Other fields
FIELD_DUST_DETECTION_START: Final = "DUST_DETECTION_START"
FIELD_DUST_REGULATION: Final = "DUST_REGULATION_VALUE"
FIELD_DUST_ALARM: Final = "DUST_ALARM_VALUE"
FIELD_CO2_ADJUSTMENT: Final = "CO2_ADJUSTMENT_VALUE"
FIELD_CO2_ALARM: Final = "CO2_ALARM_VALUE"
FIELD_MAN_OFF_TIME: Final = "MAN_OFF_TIME"
FIELD_OPENING_FUNCTION: Final = "OPENING_FUNCTION"
FIELD_TYPE_SELECTION: Final = "TYPE_SELECTION"
FIELD_TYPE_DUST_SENSOR: Final = "TYPE_DUST_SENSOR"

# Device info fields from device list
DEVICE_FIELD_ID: Final = "ID"
DEVICE_FIELD_MAC: Final = "MAC"
DEVICE_FIELD_NAME: Final = "Name"
DEVICE_FIELD_MODEL: Final = "EquipmentMode"
DEVICE_FIELD_ONLINE: Final = "Online"
