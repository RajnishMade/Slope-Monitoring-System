/*
 * sensor_node.ino  —  Slope Stability: SENSOR NODE  (ESP32 + LoRa TX)
 * ---------------------------------------------------------------------------
 * Reads the slope sensors, packages them as JSON, and transmits over LoRa:
 *   {"slope_id":"SLOPE-001","source":"esp32",
 *    "water":0.32,"vibration":0.04,"tilt":2.1,"displacement":6.3,"crack":0.8}
 *
 * Model inputs (drive the FoS prediction):
 *   water     : 0-1 saturation      -> water_level
 *   vibration : g (dynamic accel)   -> seismic_kh
 * Telemetry (shown on dashboard, NOT model inputs):
 *   tilt (deg), displacement (mm), crack (mm)
 *
 * SLOPE_ID must match a slope created in the app ("Current Slope Status").
 *
 * Libraries: "LoRa" by Sandeep Mistry. MPU6050 read over raw I2C (Wire).
 * ADJUST: SLOPE_ID, LoRa pins + FREQUENCY, and analog calibration/sensors.
 * ---------------------------------------------------------------------------
 */

#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <math.h>

// ------------------------- configuration -------------------------
const char* SLOPE_ID = "SLOPE-001";       // must exist on the server

#define LORA_FREQUENCY 433E6              // set for your region (433/866/915 MHz)
#define LORA_SS 18
#define LORA_RST 14
#define LORA_DIO0 26

#define PIN_WATER 34                      // analog: water/soil-moisture
#define PIN_DISP  32                      // analog: displacement transducer (mm)
#define PIN_CRACK 33                      // analog: crack meter (mm)
#define MPU_ADDR 0x68

const int WATER_RAW_DRY = 3200, WATER_RAW_WET = 1200;
const float DISP_MM_FULL = 50.0;          // mm at full-scale ADC
const float CRACK_MM_FULL = 10.0;
const unsigned long SEND_PERIOD_MS = 5000;

float norm01(int raw, int dry, int wet) {
  float v = (float)(dry - raw) / (float)(dry - wet);
  return v < 0 ? 0 : (v > 1 ? 1 : v);
}

void mpuBegin() {
  Wire.begin();
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x6B); Wire.write(0x00); Wire.endTransmission(true);
}

void readAccel(float& x, float& y, float& z) {
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x3B); Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 6, true);
  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();
  x = ax / 16384.0; y = ay / 16384.0; z = az / 16384.0;
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  mpuBegin();
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(LORA_FREQUENCY)) { Serial.println("LoRa init failed"); while (true) delay(1000); }
  Serial.printf("Sensor node for %s ready\n", SLOPE_ID);
}

void loop() {
  float ax, ay, az; readAccel(ax, ay, az);
  float amag = sqrt(ax * ax + ay * ay + az * az);
  float vibration = fabs(amag - 1.0);                                   // dynamic accel, g
  float tilt = atan2(sqrt(ax * ax + ay * ay), fabs(az)) * 180.0 / PI;   // deg from vertical
  float water = norm01(analogRead(PIN_WATER), WATER_RAW_DRY, WATER_RAW_WET);
  float disp = analogRead(PIN_DISP) / 4095.0 * DISP_MM_FULL;
  float crack = analogRead(PIN_CRACK) / 4095.0 * CRACK_MM_FULL;

  char payload[192];
  snprintf(payload, sizeof(payload),
           "{\"slope_id\":\"%s\",\"source\":\"esp32\",\"water\":%.3f,\"vibration\":%.3f,"
           "\"tilt\":%.2f,\"displacement\":%.2f,\"crack\":%.2f}",
           SLOPE_ID, water, vibration, tilt, disp, crack);

  LoRa.beginPacket(); LoRa.print(payload); LoRa.endPacket();
  Serial.print("TX "); Serial.println(payload);
  delay(SEND_PERIOD_MS);
}
