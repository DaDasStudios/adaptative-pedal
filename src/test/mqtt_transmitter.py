import paho.mqtt.client as mqtt

# Parámetros de conexión
broker = "test.mosquitto.org"  # Puedes usar tu propio broker o uno público
puerto = 1883
topico = "adaptative-pedal/actions"

# Crear cliente MQTT
cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

# Conectarse al broker
cliente.connect(broker, puerto)

# Publicar mensaje al tópico
mensaje = "Hola desde Python"
cliente.publish(topico, mensaje)

# Cerrar conexión
cliente.disconnect()
