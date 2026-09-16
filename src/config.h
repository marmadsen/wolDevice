#pragma once

#include <Arduino.h>

// Wi-Fi credentials and the optional HTTP token live in secrets.h, which is
// ignored by git. Copy secrets.example.h to secrets.h and fill it in.
#include "secrets.h"

// MAC address woken by GET /wake when no mac parameter is given.
constexpr const char* DEFAULT_TARGET_MAC = "BC:FC:E7:6D:A7:08";

// W5500 Ethernet controller wiring for this board.
// Based on the vendor config: MOSI=GPIO11, MISO=GPIO12, SCK=GPIO13, CS=GPIO14,
// RESET=GPIO9, INT=GPIO10.
constexpr uint8_t W5500_CS_PIN = 14;
constexpr uint8_t W5500_RESET_PIN = 9;
constexpr uint8_t W5500_INT_PIN = 10;
constexpr uint8_t W5500_SCK_PIN = 13;
constexpr uint8_t W5500_MISO_PIN = 12;
constexpr uint8_t W5500_MOSI_PIN = 11;

// Ethernet addressing. The Ethernet port is cabled straight into the target PC,
// so there is no DHCP server on that link and DHCP is off by default. The magic
// packet is a broadcast, so the exact address does not matter for waking; the
// link-local address below simply matches what the PC uses on a direct link.
// Set ETHERNET_USE_DHCP to true if the board is plugged into a router instead.
constexpr bool ETHERNET_USE_DHCP = false;
constexpr unsigned long ETHERNET_DHCP_TIMEOUT_MS = 10000;
static const IPAddress ETHERNET_IP(169, 254, 42, 42);
static const IPAddress ETHERNET_GATEWAY(0, 0, 0, 0);
static const IPAddress ETHERNET_SUBNET(255, 255, 0, 0);
static const IPAddress ETHERNET_DNS(0, 0, 0, 0);
