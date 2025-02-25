import os
import cv2
import pytesseract
import easyocr
import re
import paho.mqtt.client as mqtt
import base64
import numpy as np
from flask import Flask, render_template, jsonify, send_file
from ultralytics import YOLO
from datetime import datetime
import mysql.connector

# Cấu hình MQTT
MQTT_BROKER = "192.168.0.133"
MQTT_PORT = 1883
MQTT_TOPIC_IMAGE = "doxe/cam/image"

app = Flask(__name__)

# Kết nối MySQL
db = mysql.connector.connect(
    host="localhost",
    user="hoa",
    password="12345",
    database="QuanLyDoXe"
)
cursor = db.cursor(dictionary=True)

# Load model YOLO
model = YOLO(r"D:\\zalo\\docso\\docso\\runs\\detect\\train2\\weights\\best.pt")
pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'

latest_image = None
latest_plate_number = None

# Dictionary lưu trữ dữ liệu ảnh bị chia nhỏ
image_data_buffer = {}

def detect_license_plate(image_data):
    np_arr = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if image is None:
        return None, None

    results = model(image)
    boxes = results[0].boxes.data.cpu().numpy()
    plate_number = None

    for box in boxes:
        x_min, y_min, x_max, y_max = map(int, box[:4])
        cropped_image = image[y_min:y_max, x_min:x_max]
        gray_image = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)

        reader = easyocr.Reader(['en'])
        result_easyocr = reader.readtext(gray_image, detail=0, paragraph=True)
        text_easyocr = ''.join(re.findall(r'[a-zA-Z0-9]', ''.join(result_easyocr)))

        text_tesseract = pytesseract.image_to_string(gray_image, config='--psm 7')
        text_tesseract = ''.join(re.findall(r'[a-zA-Z0-9]', text_tesseract))

        plate_number = text_easyocr if len(text_easyocr) > len(text_tesseract) else text_tesseract

    return image, plate_number if plate_number else None

def save_or_update_sql(plate_number):
    if not plate_number:
        return

    cursor.execute("SELECT ID, TrangThai FROM XeRaVao WHERE BienSo = %s ORDER BY ID DESC LIMIT 1", (plate_number,))
    existing_entry = cursor.fetchone()

    if existing_entry and existing_entry["TrangThai"] == "Xe vào":
        cursor.execute("UPDATE XeRaVao SET ThoiGianRa = %s, TrangThai = %s WHERE ID = %s",
                       (datetime.now(), "Xe ra", existing_entry["ID"]))
    else:
        cursor.execute("INSERT INTO XeRaVao (BienSo, ThoiGianVao, TrangThai) VALUES (%s, %s, %s)",
                       (plate_number, datetime.now(), "Xe vào"))
    db.commit()

def on_message(client, userdata, msg):
    global latest_image, latest_plate_number

    try:
        payload = msg.payload.decode("utf-8")
        topic = msg.topic

        if topic.startswith("doxe/cam/image/"):
            image_id = topic.split("/")[-1]
            if image_id not in image_data_buffer:
                image_data_buffer[image_id] = ""

            image_data_buffer[image_id] += payload

            if "--END--" in image_data_buffer[image_id]:
                image_data_buffer[image_id] = image_data_buffer[image_id].replace("--END--", "")

                try:
                    image_data = base64.b64decode(image_data_buffer[image_id])
                    latest_image, latest_plate_number = detect_license_plate(image_data)
                    save_or_update_sql(latest_plate_number)
                    del image_data_buffer[image_id]
                except Exception as e:
                    print(f"❌ Lỗi giải mã ảnh: {e}")
    except Exception as e:
        print(f"❌ Lỗi xử lý MQTT: {e}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(MQTT_TOPIC_IMAGE + "/#")  # Lắng nghe cả ảnh bị chia nhỏ
client.loop_start()

@app.route("/")
def index():
    cursor.execute("SELECT * FROM XeRaVao ORDER BY ID DESC")
    data = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) AS today_in FROM XeRaVao WHERE DATE(ThoiGianVao) = CURDATE() AND TrangThai = 'Xe vào'")
    today_in = cursor.fetchone()["today_in"]

    cursor.execute(
        "SELECT COUNT(*) AS today_out FROM XeRaVao WHERE DATE(ThoiGianRa) = CURDATE() AND TrangThai = 'Xe ra'")
    today_out = cursor.fetchone()["today_out"]

    stats = {"today_in": today_in, "today_out": today_out}

    return render_template("index.html", data=data, stats=stats)

@app.route("/latest-image")
def latest_image_api():
    global latest_image
    if latest_image is not None:
        _, buffer = cv2.imencode('.jpg', latest_image)
        return send_file(
            "latest_image.jpg", mimetype='image/jpeg', as_attachment=False, data=buffer.tobytes()
        )
    return "Không có ảnh mới", 404

@app.route("/latest-data")
def latest_data():
    global latest_plate_number
    return jsonify({"plate_number": latest_plate_number})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
