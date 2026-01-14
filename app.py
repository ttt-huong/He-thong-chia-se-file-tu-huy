from flask import Flask, request, redirect, render_template_string
import boto3
import redis
import pika
import time
import json

app = Flask(__name__)

# KẾT NỐI MINIO (Cái bếp bạn đã xây ở Giai đoạn 1)
s3 = boto3.client('s3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='admin',
    aws_secret_access_key='password123'
)
BUCKET_NAME = 'fileshare'

# --- Redis (Bộ đếm) ---
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# --- RabbitMQ (Gửi tin nhắn xóa) ---
def send_delete_message(filename):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        channel.queue_declare(queue='delete_queue')
        message = json.dumps({'filename': filename})
        channel.basic_publish(exchange='', routing_key='delete_queue', body=message)
        connection.close()
    except Exception as e:
        print(f"Lỗi RabbitMQ: {e}")

# Tạo cái xô đựng file (Bucket) nếu chưa có
try:
    s3.create_bucket(Bucket=BUCKET_NAME)
    print("--- Đã kết nối MinIO thành công! ---")
except:
    print("--- MinIO đã sẵn sàng ---")

@app.route('/')
def home():
    html = '''
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
    return render_template_string(html)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return "Chưa chọn file!", 400
    
    file = request.files['file']
    filename = str(int(time.time())) + "-" + file.filename
    
    try:
        # Upload lên MinIO
        s3.upload_fileobj(file, BUCKET_NAME, filename)
        
        # Đặt giới hạn download là 3 lần trong Redis
        r.set(f"count:{filename}", 3) 
        
        # Gửi tin nhắn hẹn giờ xóa (Worker sẽ lo)
        send_delete_message(filename)

        # Trả về link download (Link này trỏ vào API download bên dưới)
        return {
            "message": "Upload thành công! Tối đa 3 lượt tải.",
            "download_link": f"http://localhost:5000/download/{filename}"
        }
    except Exception as e:
        return str(e), 500

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    # Kiểm tra lượt tải còn không
    luot_tai = r.get(f"count:{filename}")
    
    if luot_tai is None:
        return "File không tồn tại hoặc đã bị xóa!", 404

    if int(luot_tai) <= 0:
        return "Link đã hết hạn (Hết lượt tải)!", 403

    # Giảm lượt tải đi 1
    r.decr(f"count:{filename}")

    # Lấy link thật từ MinIO để người dùng tải (Tạo presigned URL sống trong 60 giây)
    try:
        url = s3.generate_presigned_url('get_object',
                                        Params={'Bucket': BUCKET_NAME, 'Key': filename},
                                        ExpiresIn=60)
        return redirect(url)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)