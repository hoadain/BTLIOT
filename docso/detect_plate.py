import cv2
import pytesseract
import easyocr
import re
import mysql.connector
from ultralytics import YOLO
from config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

# Kết nối MySQL
try:
    db = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )
    cursor = db.cursor()
    print("✅ Kết nối MySQL thành công!")
except Exception as e:
    print(f"❌ Lỗi kết nối MySQL: {e}")

# Load mô hình YOLO & cấu hình Tesseract
model = YOLO(r"D:\zalo\docso\docso\runs\detect\train2\weights\best.pt")
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def detect_license_plate(image_path):
    results = model(image_path)
    image = cv2.imread(image_path)
    boxes = results[0].boxes.data.cpu().numpy()

    plate_number = None
    for box in boxes:
        x_min, y_min, x_max, y_max = map(int, box[:4])
        cropped = image[y_min:y_max, x_min:x_max]
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

        # Nhận diện bằng Tesseract
        text = pytesseract.image_to_string(gray, config="--psm 6")
        text = re.sub(r'[^a-zA-Z0-9]', '', text)

        # Nhận diện bằng EasyOCR
        reader = easyocr.Reader(['en'])
        result_easyocr = reader.readtext(gray, detail=0)
        easyocr_text = ''.join(re.findall(r'[a-zA-Z0-9]', ''.join(result_easyocr)))

        plate_number = easyocr_text if len(easyocr_text) > len(text) else text

    return plate_number

def save_or_update_sql(plate_number, image_path):
    if not plate_number:
        print("❌ Không nhận diện được biển số!")
        return

    try:
        # Kiểm tra xem xe đã vào nhưng chưa ra chưa
        cursor.execute("SELECT ID, TrangThai FROM XeRaVao WHERE BienSo = %s ORDER BY ID DESC LIMIT 1", (plate_number,))
        existing_entry = cursor.fetchone()

        if existing_entry:
            last_id, trang_thai = existing_entry

            if trang_thai == "Xe vào":  # Nếu xe đã vào mà chưa có trạng thái "Xe ra"
                cursor.execute("UPDATE XeRaVao SET ThoiGianRa = NOW(), TrangThai = 'Xe ra' WHERE ID = %s", (last_id,))
                db.commit()
                print(f"🚗 Biển số {plate_number} đã cập nhật trạng thái: Xe ra")
                return

        # Nếu chưa có hoặc đã ra, thêm mới
        query = "INSERT INTO XeRaVao (BienSo, ThoiGianVao, TrangThai, AnhBienSo) VALUES (%s, NOW(), 'Xe vào', %s)"
        values = (plate_number, image_path)
        cursor.execute(query, values)
        db.commit()
        print(f"✅ Đã lưu biển số {plate_number} vào MySQL với trạng thái: Xe vào.")
    except Exception as e:
        print(f"❌ Lỗi SQL: {e}")
