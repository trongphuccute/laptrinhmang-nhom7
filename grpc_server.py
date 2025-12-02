import grpc
from concurrent import futures
import time
import service_pb2
import service_pb2_grpc

class UserValidationService(service_pb2_grpc.UserValidationServicer):
    def CheckUserStatus(self, request, context):
        print(f"[gRPC] Đang kiểm tra User ID: {request.user_id} ({request.username})")
        
        # --- LOGIC KIỂM TRA ---
        BANNED_IDS = [2] 
        
        if request.user_id in BANNED_IDS:
            return service_pb2.UserResponse(
                is_banned=True, 
                message="Tài khoản của bạn đã bị khóa do vi phạm quy định."
            )
        else:
            return service_pb2.UserResponse(
                is_banned=False, 
                message="Trạng thái hoạt động bình thường."
            )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service_pb2_grpc.add_UserValidationServicer_to_server(UserValidationService(), server)
    
    # Chạy trên port 50051
    server.add_insecure_port('[::]:50051')
    print("[gRPC Microservice] Validation Server đang chạy trên port 50051...")
    server.start()
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()