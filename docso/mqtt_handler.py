import paho.mqtt.client as mqtt
from detect_plate import detect_license_plate, save_to_sql

def on_message(client, userdata, msg):
    image_path = "received_image.jpg"
    with open(image_path, "wb") as f:
        f.write(msg.payload)
    plate_number = detect_license_plate(image_path)
    save_to_sql(plate_number, image_path)

def start_mqtt():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect("192.168.0.103", 1883, 60)
    client.subscribe("esp32/camera")
    client.loop_start()
