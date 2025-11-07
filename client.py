import socket

HOST = "127.0.0.1"
PORT = 5000

def run_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        data = s.recv(8192).decode("utf-8")  # danh sách quốc gia
        print(data, end="")

        choice = input("> ")
        s.sendall(choice.encode("utf-8"))

        result = s.recv(2048).decode("utf-8")
        print(result)

if __name__ == "__main__":
    run_client()
