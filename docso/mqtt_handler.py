import paho.mqtt.client as mqtt
from detect_plate import detect_license_plate, save_or_update_sql
from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC

def on_message(client, userdata, msg):
    try:
        image_path = "received_image.jpg"
        with open(image_path, "wb") as f:
            f.write(msg.payload)

        plate_number = detect_license_plate(image_path)

        if plate_number:
            save_or_update_sql(plate_number, image_path)
        else:
            print("❌ Không nhận diện được biển số!")
    except Exception as e:
        print(f"⚠️ Lỗi khi xử lý ảnh từ MQTT: {e}")

def start_mqtt():
    try:
        client = mqtt.Client()
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(MQTT_TOPIC)
        client.loop_start()
        print(f"✅ Đã kết nối MQTT đến {MQTT_BROKER}:{MQTT_PORT}, đang lắng nghe trên chủ đề '{MQTT_TOPIC}'...")
    except Exception as e:
        print(f"❌ Lỗi kết nối MQTT: {e}")
