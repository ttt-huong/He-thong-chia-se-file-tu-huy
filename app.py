from flask import Flask, request, redirect, jsonify
import boto3
import pika
import redis
import time
import json
import os

app = Flask(__name__)

# --- 1. CẤU HÌNH KẾT NỐI ---
SERVER_HOST = os.getenv('SERVER_HOST', 'localhost')  # Đặt IP máy chạy Flask/MinIO
MINIO_HOST = os.getenv('MINIO_HOST', SERVER_HOST)

# Kết nối MinIO (Kho lưu trữ)
s3 = boto3.client('s3',
    endpoint_url=f'http://{MINIO_HOST}:9000',
    aws_access_key_id='admin',
    aws_secret_access_key='password123'
)
BUCKET_NAME = 'fileshare'

# Kết nối Redis (Bộ đếm lượt tải)
# decode_responses=True để khi lấy dữ liệu ra nó là String, không phải Bytes
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Tạo Bucket nếu chưa có
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
except:
    pass

# Thêm Lifecycle rule để tự động xóa file cũ (backup khi Worker lỗi)
try:
    s3.put_bucket_lifecycle_configuration(
        Bucket=BUCKET_NAME,
        LifecycleConfiguration={
            'Rules': [{
                'ID': 'AutoDeleteAfter1Day',  # <- Chữ hoa!
                'Status': 'Enabled',
                'Expiration': {'Days': 1},
                'Filter': {'Prefix': ''}
            }]
        }
    )
    print("--- Lifecycle rule đã được thêm vào! ---")
except Exception as e:
    print(f"--- Lifecycle rule error (bỏ qua): {e} ---")

# --- 2. HÀM PHỤ TRỢ ---
def send_delete_message(filename):
    """Gửi tin nhắn vào RabbitMQ để yêu cầu xóa file sau này"""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='delete_queue')
        
        message = json.dumps({'filename': filename})
        channel.basic_publish(exchange='', routing_key='delete_queue', body=message)
        
        connection.close()
    except Exception as e:
        print(f"Lỗi RabbitMQ: {e}")

# --- 3. CÁC API (ĐƯỜNG DẪN) ---

@app.route('/')
def home():
    """Giao diện trang chủ để chọn file upload"""
    return '''
    <!doctype html>
    <html>
    <head><title>Hệ thống Chia sẻ File</title></head>
    <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
        <h1>📂 Hệ thống Chia sẻ File Phân tán</h1>
        <p>File sẽ tự hủy sau 3 lần tải hoặc khi Worker dọn dẹp.</p>
        <div style="border: 2px dashed #333; padding: 40px; display: inline-block; margin-top: 20px;">
            <form method="post" enctype="multipart/form-data" action="/upload">
                <input type="file" name="file" required>
                <br><br>
                <input type="submit" value="🚀 Upload lên Server" style="padding: 10px 20px; cursor: pointer;">
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return "Chưa chọn file!", 400
    
    file = request.files['file']
    if file.filename == '':
        return "Tên file rỗng!", 400

    # Đặt tên file (Thêm timestamp để không trùng)
    filename = str(int(time.time())) + "-" + file.filename
    
    try:
        # 1. Upload lên MinIO
        s3.upload_fileobj(file, BUCKET_NAME, filename)
        
        # 2. Đặt giới hạn download là 3 lần trong Redis (hết hạn sau 3600s = 1 giờ)
        r.setex(f"count:{filename}", 3600, 3)
        
        # 3. Gửi tin nhắn hẹn giờ xóa (Worker sẽ lo)
        send_delete_message(filename)

        # Trả về kết quả JSON (với tiếng Việt)
        return jsonify({
            "message": "Upload thành công! Tối đa 3 lượt tải.",
            "download_link": f"http://{SERVER_HOST}:5000/download/{filename}"
        })
    except Exception as e:
        return str(e), 500

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    # 1. Kiểm tra lượt tải còn không trong Redis
    luot_tai = r.get(f"count:{filename}")
    
    if luot_tai is None:
        return "❌ File không tồn tại hoặc đã bị xóa!", 404

    if int(luot_tai) <= 0:
        return "⛔ Link đã hết hạn (Hết lượt tải)!", 403

    # 2. Giảm lượt tải đi 1
    r.decr(f"count:{filename}")

    # 3. Lấy link thật từ MinIO (Presigned URL sống trong 60s)
    try:
        url = s3.generate_presigned_url('get_object',
                                        Params={'Bucket': BUCKET_NAME, 'Key': filename},
                                        ExpiresIn=60)
        return redirect(url)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)