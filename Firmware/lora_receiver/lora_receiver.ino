/*
 * lora_receiver.ino  —  Slope Stability Monitor: LoRa RECEIVER / GATEWAY
 * ---------------------------------------------------------------------------
 * ESP32 + SX1276/RFM95 LoRa RX + Wi-Fi.
 *
 * Receives JSON packets from the sensor node(s) and forwards each one to the
 * laptop server two ways (either is enough):
 *   1) Wi-Fi  : HTTP POST to http://<server-ip>:8000/api/ingest   (primary)
 *   2) Serial : prints the raw JSON line, for Server/serial_bridge.py (USB path)
 *
 * Libraries (Arduino Library Manager):
 *   - "LoRa" by Sandeep Mistry
 * (WiFi + HTTPClient are bundled with the ESP32 Arduino core.)
 *
 * ADJUST: WIFI_SSID / WIFI_PASS / SERVER_URL and the LoRa pins + FREQUENCY
 * (frequency MUST match the sender).
 * ---------------------------------------------------------------------------
 */

#include <SPI.h>
#include <LoRa.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ------------------------- configuration -------------------------
const char* WIFI_SSID  = "YOUR_WIFI";
const char* WIFI_PASS  = "YOUR_PASSWORD";
const char* SERVER_URL = "http://192.168.1.50:8000/api/ingest";  // laptop LAN IP
const bool  USE_WIFI   = true;    // set false to use only the USB/serial bridge

#define LORA_FREQUENCY   433E6           // MUST match sensor_node.ino
#define LORA_SS   18
#define LORA_RST  14
#define LORA_DIO0 26

void wifiConnect() {
  if (!USE_WIFI) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Wi-Fi connecting");
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) { delay(500); Serial.print("."); }
  Serial.println(WiFi.status() == WL_CONNECTED ? " connected" : " FAILED");
}

void setup() {
  Serial.begin(115200);
  wifiConnect();

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQUENCY)) {
    Serial.println("LoRa init failed — check wiring/frequency");
    while (true) delay(1000);
  }
  Serial.println("LoRa receiver ready");
}

void postToServer(const String& json) {
  if (!USE_WIFI) return;
  if (WiFi.status() != WL_CONNECTED) { wifiConnect(); if (WiFi.status() != WL_CONNECTED) return; }
  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  int code = http.POST((uint8_t*)json.c_str(), json.length());
  Serial.printf("  POST -> %d\n", code);
  http.end();
}

void loop() {
  int packetSize = LoRa.parsePacket();
  if (packetSize == 0) return;

  String json = "";
  while (LoRa.available()) json += (char)LoRa.read();

  // Serial path (for serial_bridge.py). One JSON object per line.
  Serial.println(json);
  // Wi-Fi path (direct to FastAPI).
  postToServer(json);
}
