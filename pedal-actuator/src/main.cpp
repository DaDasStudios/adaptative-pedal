#include <WiFi.h>
#include <PubSubClient.h>
#include <Arduino.h>

char clientId[50];

// WiFi
const char *ssid = "Wokwi-GUEST";
const char *password = "";

// MQTT
const char *mqtt_server = "test.mosquitto.org";
const int mqtt_port = 1883;
const char *action_topic = "adaptative-pedal/actions";

// Pines de salida
const int pinCelestino = 27;
const int pinSostenuto = 26;

// Estados actuales
bool estadoCelestino = false;
bool estadoSostenuto = false;

WiFiClient espClient;
PubSubClient client(espClient);

void setup_wifi()
{
  delay(10);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
  }
}

void toggleCelestino()
{
  estadoCelestino = !estadoCelestino;
  digitalWrite(pinCelestino, estadoCelestino ? HIGH : LOW);
}

void toggleSostenuto()
{
  estadoSostenuto = !estadoSostenuto;
  digitalWrite(pinSostenuto, estadoSostenuto ? HIGH : LOW);
}

void callback(char *topic, byte *payload, unsigned int length)
{
  String message = "";
  for (unsigned int i = 0; i < length; i++)
  {
    message += (char)payload[i];
  }
  Serial.println(message);
  if (message == "TOGGLE_CELESTINO")
  {
    toggleCelestino();
  }
  else if (message == "TOGGLE_SOSTENUTO")
  {
    toggleSostenuto();
  }
}

void reconnect()
{
  while (!client.connected())
  {
    Serial.println("Attempting MQTT connection...");
    long r = random(1000);
    sprintf(clientId, "clientId-%ld", r);
    if (client.connect(clientId))
    {
      client.subscribe(action_topic);
      Serial.print(clientId);
      Serial.println(" connected");
    }
    else
    {
      delay(2000);
    }
  }
}

void setup()
{
  pinMode(pinCelestino, OUTPUT);
  pinMode(pinSostenuto, OUTPUT);
  digitalWrite(pinCelestino, LOW);
  digitalWrite(pinSostenuto, LOW);

  Serial.begin(115200);
  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop()
{
  if (!client.connected())
  {
    reconnect();
  }
  client.loop();
}
