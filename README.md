# This project is forked from bdcrrbb/broadair_FE6Pro_HACS (https://github.com/bdcrrbb/broadair_FE6Pro_HACS) 

I just modified it slightly to work with the FF100-Pro.

# Broad Fresh Air Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom component for controlling Broad (远大) fresh air units via the cloud API.

## Supported Devices

- Broad FE6-Pro (新风肺保FE6)
- Other Broad fresh air units using the same cloud API (untested)

## Features

### Controls
- **Power**: Turn the unit on/off
- **Fan Speed**: 6-speed fan control (preset modes 1-6)
- **Sleep Mode**: Toggle sleep mode on/off
- **Reset HEPA Filter**: Reset HEPA filter used time counter (after replacing filter)
- **Reset Primary Filter**: Reset primary/coarse filter used time counter (after cleaning)

### Sensors
- **Air Volume**: Current airflow rate (m³/h)
- **Speed Level**: Current speed setting (1-6)
- **HEPA Filter Life**: Remaining filter life percentage
- **HEPA Filter Used Time**: Hours the HEPA filter has been used
- **Coarse Filter Used Time**: Hours the coarse filter has been used
- **Fault Status**: Current fault code and description

### Optional Sensors (if modules installed)
- **CO2**: CO2 concentration (ppm)
- **PM2.5**: Particulate matter 2.5 (µg/m³)
- **PM10**: Particulate matter 10 (µg/m³)
- **Room Temperature**: Indoor temperature (°C)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Click "Add"
6. Search for "Broad Fresh Air" and install it
7. Restart Home Assistant

### Manual Installation

1. Download the `broadair` folder from this repository
2. Copy it to your `config/custom_components/` directory:
   ```
   config/
   └── custom_components/
       └── broadair/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           ├── const.py
           ├── coordinator.py
           ├── api.py
           ├── fan.py
           ├── switch.py
           ├── sensor.py
           └── translations/
   ```
3. Restart Home Assistant

## Configuration

### Easy Setup (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Broad Fresh Air"
4. Enter your phone number and password (same as the mobile app)
5. Select your device from the list
6. Done!

The integration will automatically handle login and token refresh.

## Entities

### Fan Entity
| Entity ID | Description |
|-----------|-------------|
| `fan.<device_name>` | Main control - power on/off, 6 speed levels |

### Switch Entities
| Entity ID | Description |
|-----------|-------------|
| `switch.<device_name>_sleep_mode` | Toggle sleep mode |

### Button Entities
| Entity ID | Description |
|-----------|-------------|
| `button.<device_name>_reset_hepa_filter` | Reset HEPA filter used time |
| `button.<device_name>_reset_primary_filter` | Reset primary filter used time |

### Sensor Entities
| Entity ID | Description | Unit |
|-----------|-------------|------|
| `sensor.<device_name>_air_volume` | Current air flow | m³/h |
| `sensor.<device_name>_speed_level` | Current speed (1-6) | - |
| `sensor.<device_name>_fault_status` | Fault status | - |
| `sensor.<device_name>_hepa_filter_life` | HEPA filter remaining | % |
| `sensor.<device_name>_hepa_filter_used` | HEPA filter used time | hours |
| `sensor.<device_name>_coarse_filter_used` | Coarse filter used time | hours |
| `sensor.<device_name>_co2` | CO2 level (if module installed) | ppm |
| `sensor.<device_name>_pm25` | PM2.5 (if module installed) | µg/m³ |
| `sensor.<device_name>_pm10` | PM10 (if module installed) | µg/m³ |
| `sensor.<device_name>_temperature` | Room temp (if module installed) | °C |

## Session Management

The integration automatically handles session tokens. If a token expires, the integration will automatically re-authenticate using your stored credentials.

If automatic re-authentication fails:

1. The integration will show an authentication error
2. Go to **Settings** → **Devices & Services** → **Broad Fresh Air**
3. Click **Reconfigure** and enter your credentials again

## Troubleshooting

### "Invalid phone number or password"

- Make sure you're using the same credentials as the mobile app
- Check that your phone number includes country code if required
- Try logging into the mobile app to verify credentials work

### "Unable to connect"

- Check your Home Assistant's internet connection
- Verify the Broad cloud service is accessible
- Check if your firewall is blocking outgoing connections to `broadair.remotcon.mobi:8201`

### Device shows unavailable

- The device may be offline (check `Online` status)
- Try power cycling the fresh air unit
- Check the device status in the official app

### Air quality sensors show unavailable

- These sensors require optional modules (CO2, dust, temperature)
- If the module is not installed, the sensor will be unavailable
- Check `*_MODULE_ACCESSORIES` fields in the API response

## API Reference

For developers interested in the API:

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/System/Login` | POST | User login |
| `/api/Equipment/GetEquipments` | POST | Get device list |
| `/api/Equipment/SetFreshLung` | POST | Control device / get status |

### Control Commands (sjx parameter)

| sjx | cs | Action |
|-----|-----|--------|
| 1 | - | Poll status |
| 2 | - | Power off |
| 3 | - | Power on |
| 4 | 1-6 | Set fan speed |
| 5 | 0/1 | Sleep mode off/on |
| 8 | 1 | Reset HEPA filter timer |
| 9 | 1 | Reset primary filter timer |

### Status Response Fields

| Field | Description |
|-------|-------------|
| `FB_ON` | Power state (1=on, 0=off) |
| `GEAR_POSITION` | Current gear setting |
| `RUNNING_GEAR` | Actual running gear |
| `FB_SLEEPMODEL_ON` | Sleep mode state |
| `FB_AUTOMODEL_ON` | Auto mode state |
| `AIR_VOLUME` | Air volume (m³/h) |
| `FAULT` | Fault code (00=OK) |
| `EFFICIENT_LIFE_CYCLE` | HEPA filter total life |
| `EFFICIENT_USED_TIME` | HEPA filter used hours |
| `COARSE_USED_TIME` | Coarse filter used hours |
| `CO2_CONCENTRATION` | CO2 level |
| `PM_2_5` | PM2.5 level |
| `PM_10` | PM10 level |
| `ROOM_TEMPERATURE` | Room temperature |
| `*_MODULE_ACCESSORIES` | Module installation status |

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## Disclaimer

This custom component is created using Claude. This integration is not affiliated with or endorsed by Broad Group (远大集团). Use at your own risk.

## License

MIT License
