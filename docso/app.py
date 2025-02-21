from flask import Flask, render_template
import pyodbc
import base64
from config import SERVER_NAME, DATABASE_NAME
from mqtt_handler import start_mqtt

app = Flask(__name__)

# Kết nối SQL Server
db = pyodbc.connect(f"DRIVER={{SQL Server}};SERVER={SERVER_NAME};DATABASE={DATABASE_NAME};Trusted_Connection=yes;")
cursor = db.cursor()


@app.route("/")
def index():
    # Lấy danh sách xe vào/ra
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

    # Thống kê số lần đỗ xe theo biển số, tháng, năm
    cursor.execute("""
        SELECT BienSo, MONTH(ThoiGianVao) AS Thang, YEAR(ThoiGianVao) AS Nam, COUNT(*) AS SoLanDo
        FROM XeRaVao
        GROUP BY BienSo, MONTH(ThoiGianVao), YEAR(ThoiGianVao)
        ORDER BY Nam DESC, Thang DESC
    """)
    thongke_data = cursor.fetchall()

    return render_template("index.html", data=processed_data, thongke_data=thongke_data)


if __name__ == "__main__":
    start_mqtt()
    app.run(host="0.0.0.0", port=5000, debug=True)
