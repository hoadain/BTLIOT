from flask import Flask, render_template, request, jsonify
import mysql.connector
import os
from config import MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD
from mqtt_handler import start_mqtt

app = Flask(__name__)

# Thư mục lưu ảnh biển số
UPLOAD_FOLDER = "D:/zalo/docso/docso/images/"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Tạo thư mục nếu chưa có
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Kết nối MySQL
try:
    db = mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database="QuanLyDoXe"
    )
    cursor = db.cursor(dictionary=True)  # Trả về kết quả dạng dictionary
    print("Kết nối MySQL thành công!")
except mysql.connector.Error as err:
    print(f"Lỗi kết nối MySQL: {err}")
    exit(1)

@app.route("/")
def index():
    # Lấy danh sách xe vào/ra
    cursor.execute("SELECT ID, BienSo, ThoiGianVao, ThoiGianRa, TrangThai, AnhBienSo FROM XeRaVao ORDER BY ID DESC")
    data = cursor.fetchall()

    # Xử lý đường dẫn ảnh
    processed_data = []
    for xe in data:
        anh_bien_so = xe["AnhBienSo"]
        if anh_bien_so:
            anh_bien_so = f"/static/images/{anh_bien_so}"  # Đường dẫn ảnh trên web
        else:
            anh_bien_so = None

        processed_data.append({
            "ID": xe["ID"],
            "BienSo": xe["BienSo"],
            "ThoiGianVao": xe["ThoiGianVao"],
            "ThoiGianRa": xe["ThoiGianRa"],
            "TrangThai": xe["TrangThai"],
            "AnhBienSo": anh_bien_so
        })

    # Thống kê số lần đỗ xe theo biển số, tháng, năm
    cursor.execute("""
        SELECT BienSo, MONTH(ThoiGianVao) AS Thang, YEAR(ThoiGianVao) AS Nam, COUNT(*) AS SoLanDo
        FROM XeRaVao
        GROUP BY BienSo, Thang, Nam
        ORDER BY Nam DESC, Thang DESC
    """)
    thongke_data = cursor.fetchall()

    return render_template("index.html", data=processed_data, thongke_data=thongke_data)

@app.route("/upload_plate", methods=["POST"])
def upload_plate():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    bien_so = request.form.get("plate_number")  # Biển số nhận diện
    if not file or not bien_so:
        return jsonify({"error": "Missing data"}), 400

    # Lưu ảnh vào thư mục static/images/
    filename = f"{bien_so}.jpg"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Lưu đường dẫn ảnh vào MySQL
    cursor.execute("INSERT INTO XeRaVao (BienSo, ThoiGianVao, AnhBienSo) VALUES (%s, NOW(), %s)",
                   (bien_so, filename))
    db.commit()

    return jsonify({"message": "Upload successful", "image_path": filepath})

if __name__ == "__main__":
    start_mqtt()
    app.run(host="0.0.0.0", port=5000, debug=True)