# HƯỚNG DẪN VẼ SƠ ĐỒ KIẾN TRÚC TRÊN DRAW.IO

## Phương án 1: Dùng PlantUML (Đã tạo sẵn)

### Bước 1: Render PlantUML online
1. Mở: https://www.planttext.com/ hoặc http://www.plantuml.com/plantuml/uml/
2. Copy nội dung file `architecture.puml` vào
3. Click "Generate" → xuất ra hình PNG
4. Lưu file: `architecture_diagram.png`

### Bước 2: Chỉnh sửa (nếu cần)
- Thay đổi màu sắc: `#E1F5FF`, `#FFF4E6`, `#F3E5F5`, `#E8F5E9`
- Thay đổi vị trí: `-down->`, `-right->`, `.left.>`, `.down.>`
- Thêm ghi chú: chèn text bên trong component

---

## Phương án 2: Vẽ trực tiếp trên Draw.io (Chi tiết từng bước)

### Bước 1: Chuẩn bị Canvas
1. Mở: https://app.diagrams.net/
2. Chọn "Create New Diagram"
3. Chọn template "Blank Diagram"

### Bước 2: Tạo 4 vùng (Zones)

#### Zone 1: CLIENT ZONE (Màu xanh nhạt #E1F5FF)
1. Kéo shape "Rectangle" từ thanh công cụ
2. Đổi tên: "CLIENT ZONE"
3. Đổi màu nền: Click shape → Fill Color → `#E1F5FF`
4. Bên trong: Thêm icon "Actor" (Client Browser)

#### Zone 2: ORCHESTRATION LAYER (Màu vàng nhạt #FFF4E6)
1. Tạo Rectangle lớn, tên: "ORCHESTRATION LAYER (Master Node)"
2. Fill Color: `#FFF4E6`
3. Bên trong thêm 2 component:
   - **Load Balancer (Nginx)**: Rectangle nhỏ
     - Text: "Load Balancer\n(Nginx)\n\n📌 Chương 8:\nLoad Balancing & Failover"
   - **API Gateway (Flask)**: Rectangle nhỏ
     - Text: "API Gateway\n(Flask Server)\n\nĐiều phối toàn bộ hệ thống"

#### Zone 3: MIDDLEWARE LAYER (Màu tím nhạt #F3E5F5)
1. Rectangle lớn: "MIDDLEWARE & DATA LAYER"
2. Fill Color: `#F3E5F5`
3. Bên trong thêm 3 component:
   - **SQLite**: Dùng shape "Cylinder" (Database)
     - Text: "SQLite Database\n\n📌 Chương 5: UUID Identification\n\nLưu Metadata: file_id, title, node_url"
   - **Redis**: Dùng shape "Storage"
     - Text: "Redis Cache\n\n📌 Chương 4,6: Distributed Locking (Redlock)\nCaching & Counter"
   - **RabbitMQ**: Dùng shape "Queue"
     - Text: "RabbitMQ\n\n📌 Chương 3,4: Message Queue\nAsynchronous Background Jobs"

#### Zone 4: STORAGE & PROCESSING LAYER (Màu xanh lá nhạt #E8F5E9)
1. Rectangle lớn: "STORAGE & PROCESSING LAYER (Slaves & Workers)"
2. Fill Color: `#E8F5E9`
3. Bên trong thêm 4 component:
   - **Storage Node 1**: Shape "Server"
     - Text: "Storage Node 1\n(Slave Server 1)\n\nLưu file vật lý"
   - **Storage Node 2**: Shape "Server"
     - Text: "Storage Node 2\n(Slave Server 2)\n\n📌 Chương 7: Data Replication"
   - **Storage Node 3**: Shape "Server"
     - Text: "Storage Node 3\n(Slave Server 3)\n\nBackup Node"
   - **Worker**: Rectangle
     - Text: "Worker\n(Image Processor)\n\n📌 Chương 3: Xử lý hậu kỳ\nNén ảnh, Thumbnail"

### Bước 3: Vẽ các mũi tên (Luồng dữ liệu)

#### Luồng Upload (Mũi tên liền, màu đen):
1. Client → Load Balancer: "1. POST /upload"
2. Load Balancer → Gateway: "2. Forward request"
3. Gateway → SQLite: "3. Lưu Metadata (UUID, title, node_url)"
4. Gateway → Node1: "4. Lựa chọn node lưu file vật lý"
5. Node1 → Node2: "5. Auto Replicate" (mũi tên đứt)
6. Node2 → Node3: "6. Backup" (mũi tên đứt)
7. Gateway → RabbitMQ: "7. Đẩy tin nhắn 'Xử lý ảnh'"
8. RabbitMQ → Worker: "8. Worker lấy task"
9. Worker → Node1: "9. Đọc ảnh gốc"
10. Worker → Node1: "10. Lưu ảnh đã xử lý"

#### Luồng Download (Mũi tên liền, màu xanh dương):
11. Client → Load Balancer: "11. GET /download"
12. Gateway → Redis: "12. Check Cache"
13. Redis → Gateway: "Cache Hit" (mũi tên đứt)
14. Gateway → SQLite: "13. Lấy node_url"
15. Gateway → Node1: "14. Tải file"
16. Gateway → Redis: "15. Update Counter"
17. Gateway → Client: "16. Return file"

#### Health Monitoring (Mũi tên đứt, màu xám):
- Gateway → Node1: "Health Check"
- Gateway → Node2: "Health Check"
- Gateway → Node3: "Health Check"

### Bước 4: Định dạng cuối cùng
1. **Font**: Arial, size 10-12
2. **Màu mũi tên**:
   - Luồng chính: Đen
   - Replication: Xanh dương đứt
   - Health Check: Xám đứt
3. **Căn chỉnh**: Dùng "Align" tool để căn đều các component
4. **Khoảng cách**: Đảm bảo các zone không chồng lên nhau

### Bước 5: Export
1. File → Export as → PNG
2. Chọn:
   - ✅ Transparent Background
   - ✅ Include a copy of my diagram
   - Resolution: 300 DPI
3. Save: `architecture_diagram.png`

---

## Phương án 3: Dùng Mermaid.live (Render online)

1. Mở: https://mermaid.live/
2. Copy code Mermaid từ file `architecture.md` (section ```mermaid)
3. Click "Render" → Export PNG
4. Lưu file: `architecture_diagram.png`

---

## Checklist đạt điểm tối đa

- ✅ Chia 4 zones rõ ràng với màu sắc khác nhau
- ✅ Ghi chú đầy đủ 📌 Chương X tại mỗi component
- ✅ Vẽ đủ 16 bước luồng dữ liệu (Upload + Download)
- ✅ Thể hiện Auto Replication giữa Storage Nodes
- ✅ Thể hiện Health Monitoring
- ✅ Sử dụng icon phù hợp (Database, Server, Queue...)
- ✅ Trình bày sạch sẽ, không chồng chéo

---

## Lưu ý quan trọng

1. **Đừng quên đánh số thứ tự** trên các mũi tên (1, 2, 3...)
2. **Mũi tên đứt vs liền**: 
   - Liền: Luồng dữ liệu chính
   - Đứt: Replication, health check, cache hit
3. **Màu sắc zones**: Phải khác nhau để dễ phân biệt
4. **Chú thích 📌 Chương X**: Giúp giám khảo chấm điểm dễ dàng

---

Sau khi vẽ xong, thay thế file `image.png` trong README bằng file mới!
