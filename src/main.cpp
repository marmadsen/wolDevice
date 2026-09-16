#include "config.h"
#include <Arduino.h>
#include <Ethernet.h>
#include <EthernetUdp.h>
#include <SPI.h>
#include <WebServer.h>
#include <WiFi.h>

namespace {
constexpr uint16_t WOL_PORT = 9;
WebServer server(80);
EthernetUDP udp;

bool parseMac(const char* text, uint8_t out[6]) {
  if (text == nullptr) {
    return false;
  }

  char buffer[32];
  snprintf(buffer, sizeof(buffer), "%s", text);

  char* cursor = buffer;
  for (int i = 0; i < 6; ++i) {
    char* end = nullptr;
    const long value = strtol(cursor, &end, 16);
    if (end == cursor || value < 0 || value > 255) {
      return false;
    }
    out[i] = static_cast<uint8_t>(value);

    if (i < 5) {
      if (*end == '\0') {
        return false;
      }
      cursor = end + 1;
      while (*cursor == ':' || *cursor == '-' || *cursor == ' ' || *cursor == '.') {
        ++cursor;
      }
    }
  }

  return true;
}

bool sendMagicPacket(const uint8_t mac[6]) {
  if (Ethernet.linkStatus() != LinkON) {
    Serial.println("Ethernet not linked");
    return false;
  }

  uint8_t packet[102];
  memset(packet, 0xFF, 6);
  for (int i = 0; i < 16; ++i) {
    memcpy(&packet[6 + (i * 6)], mac, 6);
  }

  if (!udp.beginPacket(IPAddress(255, 255, 255, 255), WOL_PORT)) {
    Serial.println("UDP beginPacket failed");
    return false;
  }

  udp.write(packet, sizeof(packet));
  const int sent = udp.endPacket();
  Serial.printf("Magic packet sent: %d\n", sent);
  return sent == 1;
}

void sendJsonStatus() {
  const String wifiState = (WiFi.status() == WL_CONNECTED) ? "connected" : "disconnected";
  const String ethState = (Ethernet.linkStatus() == LinkON) ? "up" : "down";
  const String ip = WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : "0.0.0.0";

  String payload = "{\"wifi\":\"" + wifiState + "\",\"ethernet\":\"" + ethState + "\",\"ip\":\"" + ip + "\"}";
  server.send(200, "application/json", payload);
}

void handleWakeRequest() {
  if (HA_TOKEN[0] != '\0') {
    const String token = server.hasArg("token") ? server.arg("token") : "";
    if (token != HA_TOKEN) {
      server.send(401, "text/plain", "Unauthorized");
      return;
    }
  }

  // Without a mac parameter the request wakes the default target from config.h.
  const String macArg = server.hasArg("mac") ? server.arg("mac") : String(DEFAULT_TARGET_MAC);
  if (macArg.isEmpty()) {
    server.send(400, "text/plain", "Missing mac parameter");
    return;
  }

  uint8_t targetMac[6] = {0};
  if (!parseMac(macArg.c_str(), targetMac)) {
    server.send(400, "text/plain", "Invalid MAC address");
    return;
  }

  if (sendMagicPacket(targetMac)) {
    server.send(200, "text/plain", "Wake packet sent");
  } else {
    server.send(500, "text/plain", "Wake packet failed");
  }
}

void handleRoot() {
  server.send(200, "text/plain", "ESP32-S3 WOL bridge OK");
}

void handleStatus() {
  sendJsonStatus();
}

void waitForUsbCdc() {
  uint32_t startMs = millis();
  while (!Serial && (millis() - startMs) < 5000) {
    delay(10);
  }

  delay(500);
  Serial.println("USB CDC ready");
  Serial.flush();
}

void startEthernet() {
  pinMode(W5500_RESET_PIN, OUTPUT);
  digitalWrite(W5500_RESET_PIN, HIGH);
  delay(200);
  digitalWrite(W5500_RESET_PIN, LOW);
  delay(200);
  digitalWrite(W5500_RESET_PIN, HIGH);

  SPI.begin(W5500_SCK_PIN, W5500_MISO_PIN, W5500_MOSI_PIN, W5500_CS_PIN);
  Ethernet.init(W5500_CS_PIN);

  Serial.println("Starting Ethernet...");

  byte mac[6] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};

  // Optionally try DHCP, then fall back to the static address from config.h so the
  // WoL broadcast always carries a valid source IP.
  bool haveDhcpLease = false;
  if (ETHERNET_USE_DHCP) {
    haveDhcpLease = Ethernet.begin(mac, ETHERNET_DHCP_TIMEOUT_MS, 2000) != 0;
    if (!haveDhcpLease) {
      Serial.println("Ethernet DHCP failed, using static IP");
    }
  }
  if (!haveDhcpLease) {
    Ethernet.begin(mac, ETHERNET_IP, ETHERNET_DNS, ETHERNET_GATEWAY, ETHERNET_SUBNET);
  }

  // hardwareStatus() is only meaningful after begin() has probed the chip.
  if (Ethernet.hardwareStatus() == EthernetNoHardware) {
    Serial.println("W5500 not detected, check SPI wiring");
  } else {
    Serial.printf("Ethernet chip type: %d\n", static_cast<int>(Ethernet.hardwareStatus()));
  }

  // Give the PHY a moment to negotiate before reporting the link state.
  for (int i = 0; i < 30 && Ethernet.linkStatus() != LinkON; ++i) {
    delay(100);
  }
  Serial.printf("Ethernet IP: %s\n", Ethernet.localIP().toString().c_str());
  if (Ethernet.linkStatus() == LinkON) {
    Serial.println("Ethernet link up");
  } else {
    Serial.println("Ethernet link down (checked again on each wake request)");
  }
}

void startWifi() {
  Serial.println("Connecting to WiFi...");
  WiFi.mode(WIFI_STA);
  // Modem power save adds hundreds of ms of latency and drops connections,
  // which makes the HTTP server unreachable in practice. Keep the radio on.
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  for (int i = 0; i < 30; ++i) {
    delay(500);
    Serial.printf("WiFi status=%d attempt=%d\n", WiFi.status(), i + 1);
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("WiFi connected: %s\n", WiFi.localIP().toString().c_str());
      return;
    }
  }

  Serial.println("WiFi did not connect yet, will keep retrying in the background");
}
}  // namespace

void setup() {
  Serial.begin(115200);
  waitForUsbCdc();
  Serial.println("ESP32-S3 WOL bridge starting");

  startEthernet();
  startWifi();

  udp.begin(WOL_PORT);

  server.on("/", HTTP_GET, handleRoot);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/wake", HTTP_GET, handleWakeRequest);
  server.begin();

  Serial.println("HTTP server started on port 80");
}

void loop() {
  server.handleClient();
  delay(10);
}
