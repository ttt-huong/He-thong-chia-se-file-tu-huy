# 1. Khai báo thư viện
from flask import Flask, request, jsonify, render_template_string
import boto3
from botocore.exceptions import NoCredentialsError
import os
import time

app = Flask(__name__)

# 2. Cấu hình kết nối MinIO (Dùng thư viện boto3)
s3 = boto3.client('s3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='admin',         # Giống trong docker-compose
    aws_secret_access_key='password123', # Giống trong docker-compose
    config=boto3.session.Config(signature_version='s3v4')
)

BUCKET_NAME = 'fileshare'

# 3. Hàm tạo Bucket nếu chưa có (Chạy 1 lần lúc bật)
def create_bucket():
    try:
        s3.create_bucket(Bucket=BUCKET_NAME)
        print(f"--- Đã tạo Bucket '{BUCKET_NAME}' ---")
    except:
        print(f"--- Bucket '{BUCKET_NAME}' đã tồn tại (hoặc có lỗi nhẹ) ---")

create_bucket()

# --- API 1: TRANG CHỦ với Form Upload ---
@app.route('/')
def index():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Upload File</title>
        <style>
            body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
            h2 { color: #333; }
            .upload-box { border: 2px dashed #ccc; padding: 30px; text-align: center; }
            button { background: #007bff; color: white; border: none; padding: 10px 20px; cursor: pointer; font-size: 16px; }
            button:hover { background: #0056b3; }
            #result { margin-top: 20px; padding: 15px; border-radius: 5px; }
            .success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
            .error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        </style>
    </head>
    <body>
        <h2>🚀 Hệ thống Chia sẻ File Phân tán</h2>
        <div class="upload-box">
            <h3>Chọn file để upload</h3>
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" id="fileInput" name="file" required>
                <br><br>
                <button type="submit">📤 Upload</button>
            </form>
        </div>
        <div id="result"></div>
        
        <script>
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData();
                formData.append('file', document.getElementById('fileInput').files[0]);
                
                const resultDiv = document.getElementById('result');
                resultDiv.innerHTML = 'Đang upload...';
                
                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        resultDiv.className = 'success';
                        resultDiv.innerHTML = `
                            <strong>✅ ${data.message}</strong><br>
                            Tên file: ${data.filename}<br>
                            <a href="${data.url}" target="_blank">📥 Tải về</a>
                        `;
                    } else {
                        resultDiv.className = 'error';
                        resultDiv.innerHTML = `<strong>❌ Lỗi:</strong> ${data.error}`;
                    }
                } catch (error) {
                    resultDiv.className = 'error';
                    resultDiv.innerHTML = `<strong>❌ Lỗi:</strong> ${error.message}`;
                }
            });
        </script>
    </body>
    </html>
    '''
    return render_template_string(html)

# --- API 2: UPLOAD FILE (Quan trọng) ---
@app.route('/upload', methods=['POST'])
def upload_file():
    # Kiểm tra có file gửi lên không
    if 'file' not in request.files:
        return jsonify({"error": "Chưa chọn file"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Tên file rỗng"}), 400

    try:
        # Đặt tên file (Thêm thời gian để không trùng)
        filename = str(int(time.time())) + "-" + file.filename
        
        # Upload lên MinIO
        s3.upload_fileobj(
            file,
            BUCKET_NAME,
            filename,
            ExtraArgs={'ContentType': file.content_type} # Để browser hiểu đây là ảnh/pdf...
        )

        # Trả về link download
        url = f"http://localhost:9000/{BUCKET_NAME}/{filename}"
        
        return jsonify({
            "message": "Upload thành công!",
            "filename": filename,
            "url": url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 4. Chạy Server
if __name__ == '__main__':
    app.run(debug=True, port=5000)
