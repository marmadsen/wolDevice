# ESP32-S3 WOL Bridge

This project turns an ESP32-S3 board with a W5500 Ethernet controller into a small Wi‑Fi to Ethernet bridge for Home Assistant. Home Assistant sends an HTTP command over Wi‑Fi, and the device wakes a target computer by sending a Wake-on-LAN magic packet out of its Ethernet port.

The Ethernet port is cabled straight into the target PC. That way the magic packet reaches the PC's network card even when the PC is off, and nothing else on the network has to forward broadcasts.

## What it does

- Connects to your Wi‑Fi network.
- Starts a tiny HTTP server on port 80.
- Accepts a wake command from Home Assistant.
- Sends a standard WoL packet over the Ethernet interface to the target computer's MAC address.

## Repository layout

- `src/` firmware for the ESP32-S3 (PlatformIO, Arduino framework)
- `custom_components/esp32_wol/` Home Assistant integration that talks to the bridge
- `hacs.json` lets the repository be added to HACS as a custom repository

## Firmware

### Configure

1. Copy `src/secrets.example.h` to `src/secrets.h` and fill in your Wi‑Fi name and password. `secrets.h` is ignored by git.
2. Optionally set `HA_TOKEN` in `secrets.h`. When it is not blank, `/wake` requires `token=...`.
3. Set `DEFAULT_TARGET_MAC` in [src/config.h](src/config.h) to the MAC address of the PC's Ethernet card. This is the address woken when a request carries no `mac` parameter.

### Build and flash

1. Open the folder in VS Code with the PlatformIO extension installed, or use the `pio` command line.
2. Build with `pio run`.
3. Flash with `pio run -t upload`.
4. Watch the log with `pio device monitor`.

The board enumerates as "USB Serial Device" because the ESP32-S3 uses native USB CDC for the console. Any baud rate works.

### Board-specific note

This board uses a W5500 SPI Ethernet controller, not the ESP32's built-in RMII MAC. The SPI pin mapping in [src/config.h](src/config.h) (MOSI 11, MISO 12, SCK 13, CS 14, RESET 9, INT 10) matches the vendor wiring. If your board uses different pins, change the `W5500_*` values before building.

### Ethernet addressing

Because the Ethernet port is connected directly to the PC there is no DHCP server on that link, so DHCP is off by default and the bridge uses the link-local address from `config.h`. The magic packet is a broadcast, so the exact address does not matter for waking. If you plug the bridge into a router instead, set `ETHERNET_USE_DHCP` to `true`.

### Example serial output

```text
USB CDC ready
ESP32-S3 WOL bridge starting
Starting Ethernet...
Ethernet chip type: 3
Ethernet IP: 169.254.42.42
Ethernet link up
Connecting to WiFi...
WiFi connected: 192.168.1.57
HTTP server started on port 80
```

### Device API

- `GET /` returns a simple status message
- `GET /status` returns JSON: `{"wifi":"connected","ethernet":"up","ip":"192.168.1.57"}`
- `GET /wake` sends a magic packet to `DEFAULT_TARGET_MAC`
- `GET /wake?mac=AA:BB:CC:DD:EE:FF` sends a magic packet to the given MAC
- `GET /wake?token=YOUR_TOKEN&mac=AA:BB:CC:DD:EE:FF` same, but requires the configured token

Give the bridge a fixed IP in your router's DHCP settings so Home Assistant can always find it.

## Home Assistant integration

The integration in `custom_components/esp32_wol` works with Home Assistant 2022.9 and newer. It creates one device with a single **Wake** button that sends the magic packet.

### Install

Copy the `custom_components/esp32_wol` folder into the `custom_components` folder of your Home Assistant configuration directory, so you end up with `config/custom_components/esp32_wol/manifest.json`. Then restart Home Assistant.

Alternatively add this repository to HACS as a custom repository of type Integration.

### Add the device

1. Go to Settings, Devices & Services, Add Integration and search for "ESP32 WoL Bridge".
2. Enter the bridge's Wi‑Fi IP address, for example `192.168.1.57`.
3. Optionally enter the token and a MAC address (leave both empty to use the firmware defaults).

The button can then be placed on any dashboard or used in automations. All settings can be changed later under the integration's Configure button.

### Without the integration

The bridge can also be driven with a plain REST command. This works on any Home Assistant version:

```yaml
rest_command:
  esp32_wol:
    url: "http://192.168.1.57/wake"
    method: GET
    timeout: 10

automation:
  - alias: Wake desktop
    trigger:
      - platform: state
        entity_id: input_boolean.desktop_wake
        to: "on"
    action:
      - service: rest_command.esp32_wol
```

## Typical issues

- If the serial log says `W5500 not detected`, check the SPI pin mapping.
- If the Ethernet link stays down, check the cable and the far end. The link LED on the RJ45 jack should light even when the PC is off.
- If WoL does not wake the PC, make sure Wake on Magic Packet is enabled in the network card's driver settings and in the BIOS, and that the card stays powered when the PC is off. On Windows, Fast Startup can interfere with waking from a full shutdown.
- If Home Assistant cannot reach the bridge, check that both are on the same Wi‑Fi network and that the bridge's IP has not changed. After moving to a new router, update the address under the integration's Configure button. The bridge registers as `wol-bridge` in the router's client list.
- If the bridge does not join Wi‑Fi, watch the serial log for `WiFi disconnected, reason ...`. The bridge retries every 30 seconds while disconnected. The ESP32-S3 has no 5 or 6 GHz radio, so the SSID must also be broadcast on 2.4 GHz.
