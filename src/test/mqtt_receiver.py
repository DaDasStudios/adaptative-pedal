import paho.mqtt.client as mqtt
import json 

# Callback cuando el cliente recibe un mensaje
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())

    # 👉 Aquí va tu acción personalizada
    if msg.topic == "mi/canal" and payload["action"] == "CHANGE_THRESHOLD":
        print(f"✅ Threshold changed to {payload["value"]}")
        # Aquí podrías activar un relé, encender un LED, enviar un comando, etc.

# Crear cliente MQTT
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Asignar el callback de mensajes
client.on_message = on_message

# Conectarse al broker (por ejemplo, test.mosquitto.org o tu broker local)
client.connect("test.mosquitto.org", 1883, 60)

# Suscribirse a un tópico
client.subscribe("mi/canal")

# Iniciar loop de recepción de mensajes (bloqueante)
client.loop_forever()
