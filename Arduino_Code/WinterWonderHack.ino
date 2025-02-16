#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ESP32Servo.h>  // Include the ESP32Servo library

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "d86b8526-267d-413b-897e-84545131b842"

#define servo_pin1 8  // Pin connected to the servo
#define test_pin 1
#define wheel_1 14
#define wheel_2 13
#define MIN_THROTTLE 1000  // Minimum throttle (1000 µs)
#define MAX_THROTTLE 2000  // Maximum throttle (2000 µs)

BLEServer* pServer = nullptr;
BLECharacteristic* pCharacteristic = nullptr;
bool deviceConnected = false;

Servo mouth;

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
      Serial.println("Device connected");
    };

    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      Serial.println("Device disconnected");
      BLEDevice::startAdvertising();
    }
};

class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pCharacteristic) {
        String value = pCharacteristic->getValue();
        
        if (value.length() > 0) {
            Serial.print("Received Value: ");
            Serial.println(value.c_str());

            // Convert received value to an integer
            int duration = atoi(value.c_str());

            // Ensure the angle is within the servo's range (0 to 180 degrees)
            for (int i = 0; i < duration*2; i++) {
                mouth.write(50 + random(0, 10));
                delay(240 + random(, 0, 20));
                mouth.write(20 + random(0, 10));
                delay(240 + random(0, 20));
            }
        }
    }
};

void setup() {

  mouth.attach(servo_pin1);

  Serial.begin(115200);
  
  // Create the BLE Device
  BLEDevice::init("ESP32-S3");

  // Create the BLE Server
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  // Create the BLE Service
  BLEService *pService = pServer->createService(SERVICE_UUID);

  // Create a BLE Characteristic
  pCharacteristic = pService->createCharacteristic(
                      CHARACTERISTIC_UUID,
                      BLECharacteristic::PROPERTY_READ   |
                      BLECharacteristic::PROPERTY_WRITE  |
                      BLECharacteristic::PROPERTY_NOTIFY
                    );

  // Add descriptor
  pCharacteristic->addDescriptor(new BLE2902());
  pCharacteristic->setCallbacks(new MyCallbacks());

  // Start the service
  pService->start();

  // Start advertising
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(false);
  pAdvertising->setMinPreferred(0x0);
  BLEDevice::startAdvertising();
  
  Serial.println("Waiting for a client connection...");
}