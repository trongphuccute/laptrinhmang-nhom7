import socket
import threading
import time
import sys
import logging

# -----------------------------
# Cấu hình Client
# -----------------------------
SERVER_HOST = "127.0.0.1"     # Có thể thay đổi khi triển khai mạng LAN
SERVER_PORT = 5000
RECONNECT_DELAY = 5           # Thời gian thử kết nối lại khi mất server (giây)
LOG_FILE = "client_log.txt"

# -----------------------------
# Cấu hình Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)

# -----------------------------
# Hàm lấy danh sách quốc gia từ server
# -----------------------------
def get_country_list():
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((SERVER_HOST, SERVER_PORT))
        data = client_socket.recv(8192).decode("utf-8")
        client_socket.close()
        return data
    except Exception as e:
        logging.error(f"❌ Lỗi khi lấy danh sách quốc gia: {e}")
        return None

# -----------------------------
# Hàm lấy thời gian theo quốc gia (phục vụ GUI hoặc console)
# -----------------------------
def get_time_by_country(choice):
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((SERVER_HOST, SERVER_PORT))

        # Nhận danh sách quốc gia từ server (bỏ qua, chỉ để đồng bộ)
        _ = client_socket.recv(8192).decode("utf-8")

        # Gửi lựa chọn quốc gia
        client_socket.sendall(str(choice).encode("utf-8"))

        # Nhận kết quả thời gian
        result = client_socket.recv(1024).decode("utf-8")
        client_socket.close()
        return result.strip()

    except ConnectionRefusedError:
        return "❌ Không thể kết nối tới server (Server chưa khởi động)."
    except Exception as e:
        return f"⚠️ Lỗi khi nhận thời gian: {e}"

# -----------------------------
# Thread cập nhật tự động (console)
# -----------------------------
def auto_update(choice):
    while True:
        result = get_time_by_country(choice)
        print(result)
        logging.info(result)
        time.sleep(5)

# -----------------------------
# Chương trình chạy console (CLI)
# -----------------------------
def run_console_client():
    print("===== 🌍 CLIENT HIỂN THỊ THỜI GIAN THẾ GIỚI =====")
    print(f"Kết nối tới server {SERVER_HOST}:{SERVER_PORT}...\n")

    # Thử lấy danh sách quốc gia (tự reconnect nếu thất bại)
    country_list = None
    while country_list is None:
        country_list = get_country_list()
        if country_list is None:
            print(f"🔁 Mất kết nối server, thử lại sau {RECONNECT_DELAY}s...")
            time.sleep(RECONNECT_DELAY)

    print(country_list)

    # Nhập số quốc gia
    while True:
        try:
            choice = int(input("➡️  Nhập số quốc gia bạn muốn xem giờ: "))
            if 1 <= choice <= 50:
                break
            else:
                print("⚠️  Vui lòng nhập số trong khoảng 1–50.")
        except ValueError:
            print("⚠️  Nhập sai định dạng. Hãy nhập số nguyên.")

    # Bắt đầu thread cập nhật
    print(f"\n🔁 Hiển thị giờ quốc gia #{choice} (tự cập nhật mỗi 5 giây)...\n")
    thread = threading.Thread(target=auto_update, args=(choice,), daemon=True)
    thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️ Dừng client...")
        logging.info("Client đã dừng.")
        sys.exit(0)

# -----------------------------
# Điểm khởi chạy chính
# -----------------------------
if __name__ == "__main__":
    run_console_client()
