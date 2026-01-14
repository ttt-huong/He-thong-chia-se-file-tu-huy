import pika
import boto3
import time
import json
import os

# --- CẤU HÌNH ---
RABBITMQ_HOST = 'localhost'
MINIO_ENDPOINT = 'http://localhost:9000'
ACCESS_KEY = 'admin'
SECRET_KEY = 'password123'
BUCKET_NAME = 'fileshare'

# 1. Kết nối MinIO (Để thực hiện lệnh xóa)
s3 = boto3.client('s3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

print(' [*] Worker đang chạy và chờ tin nhắn xóa file...')
print(' [*] Nhấn CTRL+C để thoát')

# 2. Hàm xử lý công việc (Khi nhận được tin nhắn)
def callback(ch, method, properties, body):
    try:
        # Giải mã tin nhắn từ RabbitMQ
        data = json.loads(body)
        filename = data['filename']
        
        print(f" [Received] Nhận yêu cầu xóa cho file: {filename}")

        # --- MÔ PHỎNG TÍNH NĂNG TỰ HỦY ---
        # Ở đây chúng ta cho Worker ngủ 10 giây để bạn kịp nhìn thấy file trên MinIO
        # Trong thực tế, bạn có thể set là 24 giờ (86400 giây)
        print(" ... Đang đếm ngược 10 giây trước khi hủy ...")
        time.sleep(10) 

        # --- THỰC HIỆN XÓA ---
        s3.delete_object(Bucket=BUCKET_NAME, Key=filename)
        print(f" [Deleted] Đã xóa vĩnh viễn file: {filename} khỏi hệ thống.")
        print(" ----------------------------------------------------")

    except Exception as e:
        print(f" [Error] Có lỗi xảy ra: {e}")

# 3. Kết nối RabbitMQ và lắng nghe
while True:
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()

        # Đảm bảo hàng đợi tồn tại
        channel.queue_declare(queue='delete_queue')

        # Đăng ký hàm callback để xử lý tin nhắn
        channel.basic_consume(queue='delete_queue', on_message_callback=callback, auto_ack=True)

        channel.start_consuming()
    except Exception as e:
        print(f"Lỗi kết nối RabbitMQ (Đang thử lại sau 5s): {e}")
        time.sleep(5)