import pika
import time
import json
import os


def _detect_local_ip():
    """Best-effort LAN IP detection to avoid returning localhost."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('8.8.8.8', 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return 'localhost'

# --- CẤU HÌNH ---
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
STORAGE_DIR = os.getenv('STORAGE_DIR', os.path.join(os.path.dirname(__file__), 'storage'))
os.makedirs(STORAGE_DIR, exist_ok=True)

print(' [*] Worker đang chạy và chờ tin nhắn xóa file...')
print(' [*] Nhấn CTRL+C để thoát')

def callback(ch, method, properties, body):
    try:
        # Giải mã tin nhắn
        data = json.loads(body)
        filename = data['filename']
        
        print(f" [Received] Nhận yêu cầu xóa cho file: {filename}")

        # --- MÔ PHỎNG: Đợi 90 giây trước khi xóa ---
        print(" ... Đang đếm ngược 90 giây trước khi hủy ...")
        time.sleep(90)

        # --- THỰC HIỆN XÓA TRÊN Ổ ĐĨA ---
        file_path = os.path.join(STORAGE_DIR, filename)
        try:
            os.remove(file_path)
            print(f" [Deleted] Đã xóa vĩnh viễn file: {filename}")
        except FileNotFoundError:
            print(f" [Skip] File không tồn tại: {filename}")
        print(" ----------------------------------------------------")

    except Exception as e:
        print(f" [Error] Có lỗi xảy ra: {e}")

# Vòng lặp lắng nghe tin nhắn
while True:
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue='delete_queue')
        
        # Khi có tin nhắn -> Gọi hàm callback
        channel.basic_consume(queue='delete_queue', on_message_callback=callback, auto_ack=True)
        channel.start_consuming()
    except Exception as e:
        print(f"Lỗi kết nối RabbitMQ (Thử lại sau 5s): {e}")
        time.sleep(5)