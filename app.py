from flask import Flask, request, redirect, jsonify, send_file
import pika
import redis
import socket
import time
import json
import os

app = Flask(__name__)


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


# --- 1. CẤU HÌNH KẾT NỐI ---
_auto_ip = _detect_local_ip()
SERVER_HOST = os.getenv('SERVER_HOST', _auto_ip)  # Đặt IP máy chạy Flask
REDIS_HOST = os.getenv('REDIS_HOST', SERVER_HOST)
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', SERVER_HOST)
STORAGE_DIR = os.getenv('STORAGE_DIR', os.path.join(os.path.dirname(__file__), 'storage'))
os.makedirs(STORAGE_DIR, exist_ok=True)

# Kết nối Redis (Bộ đếm lượt tải)
# decode_responses=True để khi lấy dữ liệu ra nó là String, không phải Bytes
r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)

print(f"[INIT] STORAGE_DIR = {STORAGE_DIR}")

# --- 2. HÀM PHỤ TRỢ ---
def resolve_server_host(req):
    """Chọn host tốt nhất cho link tải; ưu tiên env, sau đó host của request, cuối cùng IP dò được."""
    if SERVER_HOST not in ('localhost', '127.0.0.1'):
        return SERVER_HOST
    host = req.host.split(':')[0]
    if host not in ('localhost', '127.0.0.1'):
        return host
    return _detect_local_ip()


def send_delete_message(filename):
    """Gửi tin nhắn vào RabbitMQ để yêu cầu xóa file sau này"""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
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
        # 1. Lưu vào ổ đĩa cục bộ
        save_path = os.path.join(STORAGE_DIR, filename)
        file.save(save_path)
        
        # 2. Đặt giới hạn download là 3 lần trong Redis (hết hạn sau 3600s = 1 giờ)
        r.setex(f"count:{filename}", 3600, 3)
        
        # 3. Gửi tin nhắn hẹn giờ xóa (Worker sẽ lo)
        send_delete_message(filename)

        # Trả về kết quả JSON (với tiếng Việt)
        server_host = resolve_server_host(request)
        return jsonify({
            "message": "Upload thành công! Tối đa 3 lượt tải.",
            "download_link": f"http://{server_host}:5000/download/{filename}"
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

    # 3. Gửi trực tiếp file từ ổ đĩa
    file_path = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        return "❌ File đã bị xóa hoặc không tồn tại (disk)!", 404
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)