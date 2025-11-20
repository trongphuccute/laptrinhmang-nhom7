# Messenger Lite (Simple Chat App)

Đồ án Mạng Máy Tính - Hệ thống Chat Mạng Real-time đơn giản.

## 1. Cài đặt môi trường

Chạy lệnh sau để cài các thư viện cần thiết:
pip install -r requirements.txt

## 2. Khởi tạo Database

Chạy script sau 1 lần duy nhất để tạo file chat.db:
python create_db.py

## 3. Cách chạy chương trình

Hệ thống cần chạy 3 thành phần theo thứ tự sau:
- Bước 1: Chạy Microservice (gRPC)**
python grpc_server.py
- Bước 2: Chạy Main Server**
python MainServer.py
- Bước 3: Chạy Client (Người dùng)**
python client_gui.py
(Có thể mở nhiều terminal để chạy nhiều Client cùng lúc)
