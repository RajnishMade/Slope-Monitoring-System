#include <SPI.h>
#include <LoRa.h>
#define WATER_SENSOR_PIN 34
#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26
#define LORA_FREQUENCY 433E6



const char* SLOPE_ID = "SLOPE-001";
const char* NODE_ID  = "NODE-001";



void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("======================================");
  Serial.println("SLOPE WATER MONITORING NODE");
  Serial.println("ESP32 + WATER SENSOR + SX1278");
  Serial.println("======================================");


  // ADC resolution
  analogReadResolution(12);



  SPI.begin(
    LORA_SCK,
    LORA_MISO,
    LORA_MOSI,
    LORA_SS
  );



  LoRa.setPins(
    LORA_SS,
    LORA_RST,
    LORA_DIO0
  );


  if (!LoRa.begin(LORA_FREQUENCY)) {

    Serial.println("ERROR: LoRa initialization failed!");

    while (true) {
      delay(1000);
    }
  }


  LoRa.setTxPower(17);
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);


  Serial.println("LoRa initialized successfully.");
  Serial.println("Frequency: 433 MHz");
  Serial.println("Node ID: " + String(NODE_ID));
  Serial.println("Slope ID: " + String(SLOPE_ID));

  Serial.println("======================================");
  Serial.println("Starting water monitoring...");
  Serial.println("======================================");
}


void loop() {


  int sensorValue =
    analogRead(WATER_SENSOR_PIN);


  Serial.println();
  Serial.println("--------------------------------------");

  Serial.print("Raw water sensor ADC: ");
  Serial.println(sensorValue);



  float waterPercent =
    (sensorValue * 100.0) / 4095.0;


  // Keep between 0 and 100
  waterPercent =
    constrain(
      waterPercent,
      0.0,
      100.0
    );


  // Convert percentage to 0-1
  float water =
    waterPercent / 100.0;


  Serial.print("Water percentage: ");
  Serial.print(waterPercent, 2);
  Serial.println("%");


  Serial.print("Water value: ");
  Serial.println(water, 4);


  */

  String packet =
    String(NODE_ID) +
    "," +
    String(SLOPE_ID) +
    "," +
    String(water, 4);


  Serial.print("LoRa packet: ");
  Serial.println(packet);



  LoRa.beginPacket();

  LoRa.print(packet);

  LoRa.endPacket();


  Serial.println("Data transmitted successfully.");



  delay(5000);
}