import cv2
import pytesseract
import easyocr
import re
import pyodbc
from ultralytics import YOLO
from config import SERVER_NAME, DATABASE_NAME

db = pyodbc.connect(f"DRIVER={{SQL Server}};SERVER={SERVER_NAME};DATABASE={DATABASE_NAME};Trusted_Connection=yes;")
cursor = db.cursor()

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

        text = pytesseract.image_to_string(gray, config="--psm 6")
        text = re.sub(r'[^a-zA-Z0-9]', '', text)

        reader = easyocr.Reader(['en'])
        result_easyocr = reader.readtext(gray, detail=0)
        easyocr_text = ''.join(re.findall(r'[a-zA-Z0-9]', ''.join(result_easyocr)))

        plate_number = easyocr_text if len(easyocr_text) > len(text) else text

    return plate_number

def save_to_sql(plate_number, image_path):
    if not plate_number:
        print("Không nhận diện được biển số!")
        return

    query = "INSERT INTO XeRaVao (BienSo, AnhBienSo) VALUES (?, ?)"
    values = (plate_number, image_path)

    try:
        cursor.execute(query, values)
        db.commit()
        print(f"Đã lưu biển số {plate_number} vào SQL Server.")
    except Exception as e:
        print(f"Lỗi SQL: {e}")
