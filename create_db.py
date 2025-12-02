from models import app, db

with app.app_context():
    print("Đang tạo các bảng database...")
    
    db.create_all()
    
    print("Đã tạo database 'chat.db' và các bảng thành công!")