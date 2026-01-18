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

# Kết nối MinIO
s3 = boto3.client('s3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

print(' [*] Worker đang chạy và chờ tin nhắn xóa file...')
print(' [*] Nhấn CTRL+C để thoát')

def callback(ch, method, properties, body):
    try:
        # Giải mã tin nhắn
        data = json.loads(body)
        filename = data['filename']
        
        print(f" [Received] Nhận yêu cầu xóa cho file: {filename}")

        # --- MÔ PHỎNG: Đợi 50 giây trước khi xóa ---
        print(" ... Đang đếm ngược 50 giây trước khi hủy ...")
        time.sleep(50)

        # --- THỰC HIỆN XÓA ---
        s3.delete_object(Bucket=BUCKET_NAME, Key=filename)
        print(f" [Deleted] Đã xóa vĩnh viễn file: {filename}")
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