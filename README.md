# HỆ THỐNG CHIA SẺ FILE PHÂN TÁN

## 1. Giới thiệu

Đồ án này xây dựng một **hệ thống chia sẻ file phân tán**, cho phép người dùng upload file và tải về với số lượt tải giới hạn. File sẽ **tự động bị xóa** sau khi hết lượt tải hoặc được **worker xử lý nền**.

Mục tiêu chính của hệ thống:

* Áp dụng kiến trúc **hệ phân tán**
* Sử dụng **message queue** cho xử lý bất đồng bộ
* Tách biệt rõ ràng giữa API server và worker
* Đảm bảo hiệu năng và khả năng mở rộng

---

## 2. Công nghệ sử dụng

| Thành phần      | Công nghệ      | Vai trò                          |
| --------------- | -------------- | -------------------------------- |
| API Server      | Flask (Python) | Xử lý request từ client          |
| Object Storage  | MinIO          | Lưu trữ file dạng object         |
| Cache / Counter | Redis          | Đếm số lượt tải file             |
| Message Queue   | RabbitMQ       | Gửi yêu cầu xóa file bất đồng bộ |
| Worker          | Python         | Xử lý nền, xóa file              |
| Giao diện       | HTML/CSS       | Demo người dùng                  |

---

## 3. Kiến trúc hệ thống

### 3.1 Sơ đồ kiến trúc tổng quát

![alt text](image.png)

### 3.2 Mô tả vai trò các thành phần

* **Flask API Server**: Nhận request upload/download từ client, điều phối các dịch vụ còn lại.
* **MinIO**: Lưu trữ file upload theo mô hình object storage.
* **Redis**: Lưu số lượt tải còn lại của mỗi file (in-memory, tốc độ cao).
* **RabbitMQ**: Hàng đợi tin nhắn, giúp xử lý xóa file bất đồng bộ.
* **Worker**: Tiến trình chạy độc lập, lắng nghe RabbitMQ và thực hiện xóa file.

---

## 4. Luồng hoạt động của hệ thống

### 4.1 Luồng Upload File

1. Người dùng upload file từ trình duyệt
2. Flask API nhận file
3. File được lưu vào MinIO
4. Redis khởi tạo bộ đếm lượt tải (3 lần)
5. Flask gửi message vào RabbitMQ
6. Worker sẽ xử lý xóa file khi cần

### 4.2 Luồng Download File

1. Người dùng truy cập link download
2. Flask kiểm tra số lượt tải trong Redis
3. Nếu còn lượt → giảm lượt tải đi 1
4. Flask tạo presigned URL từ MinIO
5. Trình duyệt được redirect sang MinIO để tải file

### 4.3 Luồng Xóa File (Worker)

1. Worker lắng nghe hàng đợi RabbitMQ
2. Nhận message chứa tên file
3. Thực hiện xử lý nền (delay hoặc điều kiện)
4. Xóa file khỏi MinIO
5. Xóa key tương ứng trong Redis

---

## 5. Hướng dẫn chạy hệ thống

### 5.1 Khởi động các service

```bash
# Redis
redis-server

# RabbitMQ
rabbitmq-server

# MinIO
minio server data
```

### 5.2 Chạy Flask API

```bash
python app.py
```

### 5.3 Chạy Worker

```bash
python worker.py
```

---

## 6. Đánh giá & kết luận

Hệ thống đáp ứng đầy đủ các tiêu chí của một **ứng dụng phân tán**:

* Có nhiều service độc lập
* Giao tiếp bất đồng bộ qua message queue
* Tách biệt xử lý request và xử lý nền
* Có khả năng mở rộng và nâng cấp

Đồ án thể hiện rõ việc áp dụng các kiến thức về **Distributed Systems**, **Message Queue**, **Cache**, và **Object Storage** trong thực tế.
