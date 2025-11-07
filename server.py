import socket
import datetime
import logging
import sys
from concurrent.futures import ThreadPoolExecutor

# -----------------------------
# Cấu hình server
# -----------------------------
HOST = "0.0.0.0"
PORT = 5000
MAX_CLIENTS = 20
LOG_FILE = "server_worldtime_50.log"

# -----------------------------
# Danh sách 50 quốc gia phổ biến với người Việt (UTC offset)
# -----------------------------
TIMEZONES = {
    "🇻🇳 Vietnam": 7,
    "🇨🇳 China": 8,
    "🇯🇵 Japan": 9,
    "🇰🇷 South Korea": 9,
    "🇹🇭 Thailand": 7,
    "🇲🇾 Malaysia": 8,
    "🇸🇬 Singapore": 8,
    "🇮🇩 Indonesia (Jakarta)": 7,
    "🇵🇭 Philippines": 8,
    "🇮🇳 India": 5.5,
    "🇦🇪 UAE": 4,
    "🇸🇦 Saudi Arabia": 3,
    "🇶🇦 Qatar": 3,
    "🇰🇼 Kuwait": 3,
    "🇦🇺 Australia (Sydney)": 10,
    "🇳🇿 New Zealand": 12,
    "🇺🇸 United States (New York)": -5,
    "🇺🇸 United States (Los Angeles)": -8,
    "🇨🇦 Canada (Toronto)": -5,
    "🇨🇦 Canada (Vancouver)": -8,
    "🇬🇧 United Kingdom": 0,
    "🇫🇷 France": 1,
    "🇩🇪 Germany": 1,
    "🇮🇹 Italy": 1,
    "🇪🇸 Spain": 1,
    "🇳🇱 Netherlands": 1,
    "🇸🇪 Sweden": 1,
    "🇨🇭 Switzerland": 1,
    "🇳🇴 Norway": 1,
    "🇩🇰 Denmark": 1,
    "🇫🇮 Finland": 2,
    "🇷🇺 Russia (Moscow)": 3,
    "🇺🇦 Ukraine": 2,
    "🇹🇷 Turkey": 3,
    "🇮🇱 Israel": 2,
    "🇪🇬 Egypt": 2,
    "🇿🇦 South Africa": 2,
    "🇧🇷 Brazil": -3,
    "🇲🇽 Mexico": -6,
    "🇦🇷 Argentina": -3,
    "🇨🇱 Chile": -4,
    "🇸🇪 Sweden": 1,
    "🇵🇱 Poland": 1,
    "🇨🇿 Czech Republic": 1,
    "🇵🇹 Portugal": 0,
    "🇮🇪 Ireland": 0,
    "🇸🇰 Slovakia": 1,
    "🇭🇺 Hungary": 1,
    "🇷🇴 Romania": 2,
    "🇧🇪 Belgium": 1,
    "🇱🇦 Laos": 7,
}

# -----------------------------
# Logging
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
# Xử lý client
# -----------------------------
def handle_client(conn, addr):
    logging.info(f"📡 Kết nối mới từ {addr}")
    try:
        # Tạo danh sách quốc gia cho client
        country_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(TIMEZONES.keys())])
        conn.sendall(f"🌍 Chọn quốc gia để xem giờ (1-{len(TIMEZONES)}):\n{country_list}\n> ".encode("utf-8"))

        # Nhận dữ liệu từ client
        data = conn.recv(1024).decode("utf-8").strip()
        if not data:
            conn.sendall("❌ Không nhận được lựa chọn.\n".encode("utf-8"))
            return

        try:
            index = int(data) - 1
            if 0 <= index < len(TIMEZONES):
                country, offset = list(TIMEZONES.items())[index]
                utc_now = datetime.datetime.utcnow()
                local_time = utc_now + datetime.timedelta(hours=offset)
                message = f"🕒 Giờ hiện tại tại {country}: {local_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC{offset:+})\n"
            else:
                message = f"❌ Lựa chọn không hợp lệ (1-{len(TIMEZONES)}).\n"
        except ValueError:
            message = "❌ Vui lòng nhập số thứ tự hợp lệ.\n"

        conn.sendall(message.encode("utf-8"))
        logging.info(f"✅ Đã trả kết quả cho {addr}")

    except Exception as e:
        logging.error(f"❌ Lỗi xử lý client {addr}: {e}")
    finally:
        conn.close()
        logging.info(f"🔌 Đóng kết nối với {addr}")

# -----------------------------
# Khởi động server
# -----------------------------
def start_server():
    logging.info("🚀 Khởi động WorldTimeServer (50 quốc gia phổ biến với người Việt)...")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(MAX_CLIENTS)
        logging.info(f"✅ Server đang lắng nghe tại {HOST}:{PORT}\n")

        with ThreadPoolExecutor(max_workers=MAX_CLIENTS) as executor:
            try:
                while True:
                    conn, addr = s.accept()
                    executor.submit(handle_client, conn, addr)
            except KeyboardInterrupt:
                logging.info("🛑 Dừng server do người dùng yêu cầu.")
            finally:
                logging.info("🔻 Server đã tắt.")

if __name__ == "__main__":
    start_server()
