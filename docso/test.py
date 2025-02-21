import os
import cv2
import pytesseract
import easyocr
import re
import pyodbc
import paho.mqtt.client as mqtt
import base64
import numpy as np
from flask import Flask, render_template
from ultralytics import YOLO
from datetime import datetime, timedelta

# === CẤU HÌNH MQTT ===
MQTT_BROKER = "192.168.0.103"
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/camera"

# === CẤU HÌNH SQL SERVER ===
SERVER_NAME = "MSI\\SQLEXPRESS"
DATABASE_NAME = "QuanLyBaiDoXe"
db = pyodbc.connect(f"DRIVER={{SQL Server}};SERVER={SERVER_NAME};DATABASE={DATABASE_NAME};Trusted_Connection=yes;")
cursor = db.cursor()

# === CẤU HÌNH NHẬN DIỆN BIỂN SỐ ===
model = YOLO(r"D:\zalo\docso\docso\runs\detect\train2\weights\best.pt")
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# === GIẢI MÃ BASE64 & LƯU ẢNH ===
def save_base64_image(base64_string, folder="images"):
    if not os.path.exists(folder):
        os.makedirs(folder)

    try:
        image_data = base64.b64decode(base64_string)
        filename = f"{folder}/plate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

        with open(filename, "wb") as f:
            f.write(image_data)

        return filename  # Trả về đường dẫn ảnh đã lưu
    except Exception as e:
        print(f"Lỗi khi giải mã Base64: {e}")
        return None


# === NHẬN DIỆN BIỂN SỐ ===
def detect_license_plate(image_path):
    results = model(image_path)
    image = cv2.imread(image_path)
    image_info = results[0]
    boxes = image_info.boxes.data.cpu().numpy()

    plate_number = None
    for i, box in enumerate(boxes):
        x_min, y_min, x_max, y_max = map(int, box[:4])
        cropped_image = image[y_min:y_max, x_min:x_max]
        gray_image = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
        blurred_image = cv2.GaussianBlur(gray_image, (5, 5), 0)

        # Nhận diện bằng Tesseract
        text = pytesseract.image_to_string(blurred_image, config="--psm 6")
        text = re.sub(r'[^a-zA-Z0-9]', '', text)

        # Nhận diện bằng EasyOCR
        reader = easyocr.Reader(['en'])
        result_easyocr = reader.readtext(gray_image, detail=0, paragraph=True)
        easyocr_text = ''.join(re.findall(r'[a-zA-Z0-9]', ''.join(result_easyocr)))

        plate_number = easyocr_text if len(easyocr_text) > len(text) else text

    return plate_number


# === LƯU HOẶC CẬP NHẬT BIỂN SỐ VÀO SQL ===
def save_or_update_sql(plate_number, image_path):
    if not plate_number:
        print("Không có biển số hợp lệ!")
        return

    # Kiểm tra xe có trong hệ thống chưa
    cursor.execute("SELECT TOP 1 ID, ThoiGianVao, TrangThai FROM XeRaVao WHERE BienSo = ? ORDER BY ID DESC",
                   (plate_number,))
    existing_entry = cursor.fetchone()

    if existing_entry:
        last_id, thoi_gian_vao, trang_thai = existing_entry

        # Nếu xe đã vào nhưng chưa ra, cập nhật trạng thái thành "Xe ra"
        if trang_thai == "Xe vào":
            query = "UPDATE XeRaVao SET ThoiGianRa = ?, TrangThai = ? WHERE ID = ?"
            values = (datetime.now(), "Xe ra", last_id)
            cursor.execute(query, values)
            db.commit()
            print(f"Biển số {plate_number} đã được cập nhật trạng thái: Xe ra")
            return

    # Nếu xe chưa có trong hệ thống hoặc đã ra, thêm mới
    query = "INSERT INTO XeRaVao (BienSo, ThoiGianVao, TrangThai, AnhBienSo) VALUES (?, ?, ?, ?)"
    values = (plate_number, datetime.now(), "Xe vào", image_path)

    cursor.execute(query, values)
    db.commit()
    print(f"Đã lưu biển số {plate_number} vào SQL với trạng thái: Xe vào")


# === CALLBACK KHI NHẬN BASE64 TỪ MQTT ===
def on_message(client, userdata, msg):
    try:
        base64_string = msg.payload.decode("utf-8")  # Giải mã chuỗi base64
        image_path = save_base64_image(base64_string)  # Lưu ảnh từ base64

        if image_path:
            plate_number = detect_license_plate(image_path)  # Nhận diện biển số
            save_or_update_sql(plate_number, image_path)  # Xử lý trạng thái xe vào/ra

    except Exception as e:
        print(f"Lỗi xử lý MQTT: {e}")


# === KHỞI ĐỘNG MQTT ===
client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(MQTT_TOPIC)
client.loop_start()

# === GIAO DIỆN WEB ===
app = Flask(__name__)


@app.route("/")
def index():
    cursor.execute("SELECT ID, BienSo, ThoiGianVao, ThoiGianRa, TrangThai, AnhBienSo FROM XeRaVao ORDER BY ID DESC")
    data = cursor.fetchall()

    # Xử lý dữ liệu để hiển thị ảnh
    processed_data = []
    for xe in data:
        anh_bien_so = xe.AnhBienSo
        if anh_bien_so:
            anh_bien_so = f"data:image/jpeg;base64,{anh_bien_so}"
        else:
            anh_bien_so = None

        processed_data.append({
            "ID": xe.ID,
            "BienSo": xe.BienSo,
            "ThoiGianVao": xe.ThoiGianVao,
            "ThoiGianRa": xe.ThoiGianRa,
            "TrangThai": xe.TrangThai,
            "AnhBienSo": anh_bien_so
        })

    return render_template("index.html", data=processed_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
