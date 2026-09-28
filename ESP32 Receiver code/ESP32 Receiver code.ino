#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <LoRa.h>
#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26
#define LORA_FREQUENCY 433E6

const char* WIFI_SSID =
  "YOUR_WIFI_NAME";

const char* WIFI_PASSWORD =
  "YOUR_WIFI_PASSWORD";


const char* SERVER_URL =
  "http://10.29.7.15:8000/api/ingest";


void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("======================================");
  Serial.println("LORA RECEIVER + WIFI GATEWAY");
  Serial.println("======================================");


  WiFi.begin(
    WIFI_SSID,
    WIFI_PASSWORD
  );

  Serial.print("Connecting to Wi-Fi");


  while (
    WiFi.status() != WL_CONNECTED
  ) {

    delay(500);

    Serial.print(".");
  }


  Serial.println();

  Serial.println("Wi-Fi connected!");


  Serial.print("Receiver ESP32 IP: ");

  Serial.println(
    WiFi.localIP()
  );


  Serial.print("Backend server: ");

  Serial.println(
    SERVER_URL
  );

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

    Serial.println(
      "ERROR: LoRa initialization failed!"
    );

    while (true) {
      delay(1000);
    }
  }

  LoRa.setTxPower(17);
  LoRa.setSpreadingFactor(7);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);


  Serial.println(
    "LoRa receiver initialized."
  );

  Serial.println(
    "Frequency: 433 MHz"
  );

  Serial.println(
    "Waiting for slope data..."
  );


  Serial.println(
    "======================================"
  );
}

void loop() {

  if (
    WiFi.status() != WL_CONNECTED
  ) {

    Serial.println(
      "Wi-Fi disconnected. Reconnecting..."
    );

    WiFi.disconnect();

    WiFi.begin(
      WIFI_SSID,
      WIFI_PASSWORD
    );

    delay(3000);

    return;
  }



  int packetSize =
    LoRa.parsePacket();


  if (packetSize > 0) {

    Serial.println();
    Serial.println(
      "======================================"
    );

    Serial.println(
      "LORA PACKET RECEIVED"
    );


    String packet = "";


    while (
      LoRa.available()
    ) {

      packet +=
        (char)LoRa.read();
    }


    Serial.print(
      "Raw packet: "
    );

    Serial.println(
      packet
    );



    int rssi =
      LoRa.packetRssi();


    Serial.print(
      "RSSI: "
    );

    Serial.print(
      rssi
    );

    Serial.println(
      " dBm"
    );


  

    int firstComma =
      packet.indexOf(',');


    int secondComma =
      packet.indexOf(
        ',',
        firstComma + 1
      );


    if (
      firstComma > 0 &&
      secondComma > firstComma
    ) {



      String nodeID =
        packet.substring(
          0,
          firstComma
        );



      String slopeID =
        packet.substring(
          firstComma + 1,
          secondComma
        );



      String waterString =
        packet.substring(
          secondComma + 1
        );


      float water =
        waterString.toFloat();


      Serial.print(
        "Node ID: "
      );

      Serial.println(
        nodeID
      );


      Serial.print(
        "Slope ID: "
      );

      Serial.println(
        slopeID
      );


      Serial.print(
        "Water: "
      );

      Serial.println(
        water,
        4
      );



      sendToBackend(
        nodeID,
        slopeID,
        water,
        rssi
      );


    } else {

      Serial.println(
        "ERROR: Invalid LoRa packet format!"
      );
    }


    Serial.println(
      "======================================"
    );
  }
}



void sendToBackend(
  String nodeID,
  String slopeID,
  float water,
  int rssi
) {



  if (
    WiFi.status() != WL_CONNECTED
  ) {

    Serial.println(
      "Cannot send: Wi-Fi disconnected."
    );

    return;
  }




  HTTPClient http;


  http.begin(
    SERVER_URL
  );



  http.addHeader(
    "Content-Type",
    "application/json"
  );



  String body =
    "{"
    "\"slope_id\":\"" +
    slopeID +
    "\","
    "\"node_id\":\"" +
    nodeID +
    "\","
    "\"source\":\"lora\","
    "\"water\":" +
    String(water, 4) +
    ","
    "\"rssi\":" +
    String(rssi) +
    "}";


  Serial.println();
  Serial.println(
    "Sending data to backend..."
  );


  Serial.print(
    "JSON: "
  );

  Serial.println(
    body
  );



  int responseCode =
    http.POST(
      body
    );


  if (
    responseCode > 0
  ) {

    Serial.print(
      "HTTP response code: "
    );

    Serial.println(
      responseCode
    );


    String response =
      http.getString();


    Serial.print(
      "Server response: "
    );

    Serial.println(
      response
    );


  } else {

    Serial.print(
      "HTTP POST failed: "
    );


    Serial.println(
      http.errorToString(
        responseCode
      )
    );
  }


  http.end();
}