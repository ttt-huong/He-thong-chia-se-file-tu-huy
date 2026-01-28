# 🎨 SƠ ĐỒ KIẾN TRÚC HỆ THỐNG - TỰ ĐỘNG & HƯỚNG DẪN VẼ THỦ CÔNG

> **Hệ thống lưu trữ ảnh phân tán có khả năng tự phục hồi và xử lý hậu kỳ bất đồng bộ**  
> Kiến trúc: Master-Slave + Event-Driven + Microservices  
> ⚠️ **KHÔNG SỬ DỤNG MinIO** - Chỉ dùng Local Disk Storage

---

## 📑 MỤC LỤC

1. [Sơ đồ tự động (Mermaid)](#1-sơ-đồ-tự-động-mermaid) - Dùng render ngay trên GitHub
2. [Sơ đồ PlantUML](#2-sơ-đồ-plantuml) - Chuyên nghiệp, chi tiết
3. [Hướng dẫn vẽ draw.io từng bước](#3-hướng-dẫn-vẽ-drawio-từng-bước) - Vẽ thủ công chi tiết

---

## 1. SƠ ĐỒ TỰ ĐỘNG (MERMAID)

### 1.1 Các Công Cụ Render

| Công cụ | Ưu điểm | Sử dụng khi |
|---------|---------|-------------|
| **Mermaid** | Tích hợp GitHub, dễ version control | README.md, docs |
| **PlantUML** | Chuyên nghiệp, nhiều loại diagram | Confluence, Wiki |
| **Draw.io** | GUI trực quan, export đẹp | Báo cáo, presentation |
| **Excalidraw** | Style vẽ tay, collaboration | Team brainstorm |

---

## 2. Sơ Đồ Kiến Trúc v2.0 của Bạn (Mermaid)

### 2.1 Mermaid Diagram - 4 Layers

\`\`\`mermaid
graph TB
    subgraph CLIENT["🖥️ CLIENT LAYER"]
        Web["Web Browser"]
        Mobile["Mobile App"]
        CLI["CLI Client"]
    end
    
    subgraph GATEWAY["🎯 GATEWAY LAYER (Orchestration)"]
        GW1["Gateway 1:5000"]
        GW2["Gateway 2:5000"]
        LB["⚖️ Load Balancer<br/>Nginx:80/443"]
    end
    
    subgraph MIDDLEWARE["📊 MIDDLEWARE LAYER (Coordination)"]
        Redis["Redis:6379<br/>Cache, Counter<br/>Redlock"]
        RabbitMQ["RabbitMQ:5672<br/>Task Queue"]
        SQLite["SQLite<br/>Metadata DB"]
    end
    
    subgraph STORAGE["💾 STORAGE + PROCESSING LAYER"]
        Node1["Node1:5001<br/>storage/node1<br/>100GB"]
        Node2["Node2:5002<br/>storage/node2<br/>100GB"]
        Node3["Node3:5003<br/>storage/node3<br/>100GB"]
        Worker["Worker Service<br/>Image Processing"]
    end
    
    CLIENT -->|HTTP Upload/Download| LB
    LB -->|Route Requests| GW1
    LB -->|Route Requests| GW2
    
    GW1 -->|Cache Metadata| Redis
    GW2 -->|Cache Metadata| Redis
    GW1 -->|Query/Store| SQLite
    GW2 -->|Query/Store| SQLite
    
    GW1 -->|Queue Tasks| RabbitMQ
    GW2 -->|Queue Tasks| RabbitMQ
    Worker -->|Consume Tasks| RabbitMQ
    
    GW1 -->|Save Primary| Node1
    GW1 -->|Replicate| Node2
    GW2 -->|Save Primary| Node3
    GW2 -->|Replicate| Node1
    
    Worker -->|Compress/Thumbnail| Node1
    Worker -->|Compress/Thumbnail| Node2
    Worker -->|Compress/Thumbnail| Node3
\`\`\`

---

## 3. Chi Tiết Từng Layer

### Layer 1: CLIENT (Client)
```
┌─────────────────────────────────────────┐
│          CLIENT LAYER                   │
├─────────────────────────────────────────┤
│                                         │
│  • Web Browser (React/Vue)              │
│  • Mobile App (iOS/Android)             │
│  • CLI Tool (curl/requests)             │
│  • SDKs (Python/Node.js/Java)          │
│                                         │
│  📤 Upload file to server               │
│  📥 Download file from server           │
│  📊 Query file metadata                 │
│  ⚙️ Manage storage nodes                │
└─────────────────────────────────────────┘
```

### Layer 2: GATEWAY (Orchestration)
```
┌──────────────────────────────────────────────────┐
│           GATEWAY LAYER                          │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │  Nginx/HAProxy Load Balancer            │   │
│  │  • Port: 80 (HTTP), 443 (HTTPS)        │   │
│  │  • Load balancing algorithm: round-robin│   │
│  │  • SSL termination                      │   │
│  └─────────────────────────────────────────┘   │
│                    ↓                             │
│  ┌─────────────────────────────────────────┐   │
│  │  Gateway Instance 1 (Flask)             │   │
│  │  • Port: 5000                          │   │
│  │  • Routes: /upload, /download, /health │   │
│  │  • Node selection (smart)              │   │
│  │  • Replication management              │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │  Gateway Instance 2 (Flask)             │   │
│  │  • Port: 5000                          │   │
│  │  • Same features as Instance 1         │   │
│  │  • Horizontal scalability              │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  Key Components:                                 │
│  ✓ Node Selector (health-based)                │
│  ✓ Health Monitor (auto-failover)              │
│  ✓ Request Router (load distribution)          │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Layer 3: MIDDLEWARE (Coordination)
```
┌──────────────────────────────────────────────────┐
│          MIDDLEWARE LAYER                        │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │  Redis:6379                             │   │
│  │  ┌─────────────────────────────────┐   │   │
│  │  │ Cache Layer (Chapter 6)        │   │   │
│  │  │ • file_metadata:{file_id}      │   │   │
│  │  │ • download_counter:{file_id}   │   │   │
│  │  │ • TTL based expiration         │   │   │
│  │  └─────────────────────────────────┘   │   │
│  │  ┌─────────────────────────────────┐   │   │
│  │  │ Distributed Locking (Ch. 4)    │   │   │
│  │  │ • Redlock: download_lock:{}    │   │   │
│  │  │ • Prevents race conditions     │   │   │
│  │  └─────────────────────────────────┘   │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │  RabbitMQ:5672                          │   │
│  │  ┌─────────────────────────────────┐   │   │
│  │  │ Task Queue (Chapter 3)         │   │   │
│  │  │ • task_queue: compress jobs    │   │   │
│  │  │ • task_queue: thumbnail gen    │   │   │
│  │  │ • delete_queue: auto-cleanup   │   │   │
│  │  └─────────────────────────────────┘   │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │  SQLite (data/metadata.db)              │   │
│  │  ┌─────────────────────────────────┐   │   │
│  │  │ Metadata Tables               │   │   │
│  │  │ • File                         │   │   │
│  │  │ • StorageNode                 │   │   │
│  │  │ • Task                        │   │   │
│  │  │ • ReplicationLog              │   │   │
│  │  └─────────────────────────────────┘   │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Layer 4: STORAGE + PROCESSING
```
┌──────────────────────────────────────────────────┐
│      STORAGE & PROCESSING LAYER                  │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐  ┌──────────────┐ ┌─────────┐│
│  │ Storage      │  │ Storage      │ │Storage  ││
│  │ Node 1       │  │ Node 2       │ │ Node 3  ││
│  ├──────────────┤  ├──────────────┤ ├─────────┤│
│  │ Port: 5001   │  │ Port: 5002   │ │Port:5003││
│  │ Path:        │  │ Path:        │ │ Path:   ││
│  │ storage/node1│  │ storage/node2│ │storage/ ││
│  │              │  │              │ │ node3   ││
│  │ Capacity:    │  │ Capacity:    │ │Capacity:││
│  │ 100GB        │  │ 100GB        │ │ 100GB   ││
│  │ Status:      │  │ Status:      │ │Status:  ││
│  │ Online ✓     │  │ Online ✓     │ │Online ✓ ││
│  └──────────────┘  └──────────────┘ └─────────┘│
│        ↑ Replication               ↑            │
│        └────────────┬──────────────┘            │
│                     ↓                            │
│  ┌─────────────────────────────────────────┐   │
│  │  Worker Service                         │   │
│  │  ┌─────────────────────────────────┐   │   │
│  │  │ Image Processing (Ch. 3, 5)    │   │   │
│  │  │ • Consume from task_queue      │   │   │
│  │  │ • compress_image()             │   │   │
│  │  │ • create_thumbnail()           │   │   │
│  │  │ • get_image_info()             │   │   │
│  │  └─────────────────────────────────┘   │   │
│  │  ┌─────────────────────────────────┐   │   │
│  │  │ Auto-Deletion (TTL)            │   │   │
│  │  │ • Monitor delete_queue         │   │   │
│  │  │ • Clean up expired files       │   │   │
│  │  │ • Remove replicas              │   │   │
│  │  └─────────────────────────────────┘   │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
└──────────────────────────────────────────────────┘
```

---

## 4. Data Flow Diagrams

### 4.1 Upload Flow
```
Client
  │
  │ POST /api/upload (file.jpg)
  ↓
┌─────────────────────────┐
│ Load Balancer (Nginx)   │
└──────────┬──────────────┘
           │
           ↓
┌─────────────────────────┐
│ Gateway (Flask)         │
├─────────────────────────┤
│ 1. Validate file        │─→ ✓ MIME type OK
│ 2. Generate UUID        │─→ file_id: uuid-v4
│ 3. Calculate checksum   │─→ SHA256
│ 4. Check for duplicate  │─→ ✓ Not exists
│ 5. Select primary node  │─→ node1 (100GB free)
│ 6. Save to primary      │─→ /storage/node1/{file_id}.jpg
│ 7. Select replicas      │─→ node2, node3
│ 8. Replicate            │─→ /storage/node2/{file_id}.jpg
│ 9. Create DB record     │─→ INSERT File
│ 10.Cache metadata       │─→ Redis SET
│ 11.Queue tasks          │─→ RabbitMQ compress, thumbnail
└─────────────────────────┘
           ↓
    ✅ 201 Created
    {
      "file_id": "uuid-v4",
      "download_url": "/api/download/uuid-v4",
      "primary_node": "node1",
      "replica_nodes": ["node2", "node3"]
    }
```

### 4.2 Download Flow
```
Client
  │
  │ GET /api/download/{file_id}
  ↓
┌─────────────────────────┐
│ Load Balancer (Nginx)   │
└──────────┬──────────────┘
           │
           ↓
┌─────────────────────────┐
│ Gateway (Flask)         │
├─────────────────────────┤
│ 1. Acquire lock         │─→ Redlock (10s)
│ 2. Get metadata         │─→ Redis cache or DB
│ 3. Check expiration     │─→ ✓ Not expired
│ 4. Check downloads left │─→ ✓ Count > 0
│ 5. Decrement counter    │─→ Redis counter--
│ 6. Try primary node     │─→ node1 ✓ exists
│ 7. Stream file          │─→ send_file()
│ 8. Release lock         │─→ Redlock release
└─────────────────────────┘
           ↓
    ✅ 200 OK
    Content-Type: image/jpeg
    Content-Length: 1305
    [binary file data]
```

### 4.3 Processing Flow (Async)
```
Upload Complete
       │
       ↓
┌──────────────────┐
│ Queue Task       │
│ {               │
│   file_id,      │
│   task_type,    │
│   node_id       │
│ }               │
└────────┬─────────┘
         │
    RabbitMQ Queue
         │
         ├─→ task_queue ─→ ┌──────────────────┐
         │                  │ Worker Service   │
         │                  ├──────────────────┤
         │                  │ Task 1: compress │
         │                  │ • Input: img.jpg │
         │                  │ • Output:img.cps │
         │                  │ • Size: 50% orig │
         │                  └──────────────────┘
         │
         └─→ task_queue ─→ ┌──────────────────┐
                            │ Task 2: thumbnail│
                            │ • Input: img.jpg │
                            │ • Output:img.thm │
                            │ • Size: 200x200  │
                            └──────────────────┘
```

---

## 5. Data Model (Entity Relationship)

```
┌──────────────────────┐
│      File            │
├──────────────────────┤
│ id (UUID)            │
│ filename             │
│ original_name        │
│ file_size (bytes)    │
│ mime_type            │
│ checksum (SHA256)    │
│ primary_node (FK)    │──┐
│ replica_nodes (JSON) │  │
│ download_limit       │  │
│ downloads_left       │  │
│ expires_at           │  │
│ created_at           │  │
│ is_compressed        │  │
│ has_thumbnail        │  │
└──────────────────────┘  │
                          │
           ┌──────────────┘
           │
           ↓
┌──────────────────────┐
│   StorageNode        │
├──────────────────────┤
│ node_id (PK)         │
│ host                 │
│ port                 │
│ path                 │
│ is_online            │
│ total_space          │
│ used_space           │
│ file_count           │
│ error_count          │
│ last_heartbeat       │
└──────────────────────┘

┌──────────────────────┐
│      Task            │
├──────────────────────┤
│ id (UUID)            │
│ file_id (FK) ────────┼──→ File
│ task_type            │
│ status (pending...)  │
│ created_at           │
│ completed_at         │
│ result               │
│ retry_count          │
└──────────────────────┘
```

---

## 6. Cách Vẽ Chi Tiết

### Phương Pháp 1: Mermaid trong GitHub
\`\`\`markdown
# README.md
## Kiến Trúc

\`\`\`mermaid
graph TB
    ...diagram code...
\`\`\`
\`\`\`

### Phương Pháp 2: Draw.io Online
1. Truy cập: https://app.diagrams.net
2. New → Create Diagram
3. Kéo thả các shape:
   - Rectangle: Cho layer, service
   - Cylinder: Cho database
   - Oval: Cho client
   - Arrow: Kết nối, data flow
4. Thêm text, style, color
5. Export SVG/PNG

### Phương Pháp 3: PlantUML (Advanced)
\`\`\`plantuml
@startuml architecture
package "CLIENT" {
  [Web Browser]
  [Mobile App]
}
package "GATEWAY" {
  [Load Balancer]
  [Gateway 1]
  [Gateway 2]
}
...
@enduml
\`\`\`

### Phương Pháp 4: Excalidraw (Collaborative)
1. Truy cập: https://excalidraw.com
2. Vẽ tự do style
3. Collaboration realtime
4. Export SVG

---

## 7. Các Thành Phần Cần Trong Diagram

### ✅ PHẢI CÓ
- [ ] Tất cả 4 layers (Client, Gateway, Middleware, Storage)
- [ ] Load balancer
- [ ] Multiple gateway instances
- [ ] Redis + RabbitMQ + SQLite
- [ ] Storage nodes (3 nodes)
- [ ] Worker service
- [ ] Data flow arrows
- [ ] Ports/Endpoints
- [ ] Replication arrows

### ❌ KHÔNG CẦN
- Quá chi tiết internal code
- Quá nhiều text trên diagram
- Tô màu rối mắt
- Logo công ty lớn

---

## 8. Best Practices

### ✓ DO
- Sử dụng consistent colors (Gateway=Blue, Storage=Green, etc.)
- Thêm legend/key giải thích
- Grouping related components
- Clear data flow với arrows
- Thêm numbers cho sequence

### ✗ DON'T
- Quá phức tạp, khó hiểu
- Không nhất quán
- Quá nhiều chi tiết
- Sử dụng màu sắc khác nhau cho cùng loại
- Không rõ hướng data flow

---

## 9. Template Mermaid Full (Copy & Use)

\`\`\`mermaid
graph TB
    subgraph CLIENT["🖥️ CLIENT LAYER"]
        direction TB
        Web["Web Browser<br/>React/Vue"]
        Mobile["Mobile App<br/>iOS/Android"]
    end
    
    subgraph GATEWAY["🎯 GATEWAY LAYER"]
        direction TB
        LB["⚖️ Nginx Load Balancer<br/>:80, :443"]
        GW["🌐 Flask Gateway<br/>:5000<br/>Routes, Selection, Health"]
    end
    
    subgraph MIDDLEWARE["📊 MIDDLEWARE LAYER"]
        direction LR
        Redis["🔴 Redis:6379<br/>Cache, Counter<br/>Redlock"]
        RabbitMQ["🐰 RabbitMQ:5672<br/>Task Queue"]
        SQLite["💾 SQLite<br/>Metadata"]
    end
    
    subgraph STORAGE["💾 STORAGE LAYER"]
        direction LR
        N1["Node1:5001<br/>storage/node1<br/>100GB"]
        N2["Node2:5002<br/>storage/node2<br/>100GB"]
        N3["Node3:5003<br/>storage/node3<br/>100GB"]
    end
    
    subgraph PROCESSING["⚙️ PROCESSING"]
        Worker["Worker Service<br/>Compress, Thumbnail<br/>Auto-delete"]
    end
    
    CLIENT -->|Upload/Download| LB
    LB -->|Route| GW
    
    GW -->|Read/Write| Redis
    GW -->|Query/Insert| SQLite
    GW -->|Enqueue| RabbitMQ
    
    GW -->|Save/Replicate| N1
    GW -->|Save/Replicate| N2
    GW -->|Save/Replicate| N3
    
    RabbitMQ -->|Consume| Worker
    Worker -->|Process| N1
    Worker -->|Process| N2
    Worker -->|Process| N3
\`\`\`

---

## 10. Recommended Tools by Use Case

| Use Case | Tool | Why |
|----------|------|-----|
| Quick docs in GitHub | **Mermaid** | Built-in, easy version control |
| Team presentation | **Draw.io** | Visual, professional, exportable |
| Collaborative design | **Excalidraw** | Real-time, intuitive |
| Enterprise docs | **PlantUML** | Detailed, standardized |
| Whiteboard style | **Excalidraw** | Freehand, casual |
| ASCII art | **Monodraw** (Mac) | Minimalist, text-based |

---

## Tổng Kết

Để vẽ sơ đồ kiến trúc tốt:
1. **Chọn công cụ** phù hợp (Mermaid nhanh nhất)
2. **Phân layer** rõ ràng (4 layers)
3. **Thêm data flow** (arrows với label)
4. **Highlight components** quan trọng
5. **Thêm ports/endpoints** cụ thể
6. **Giải thích** trong legend
7. **Review** với team
8. **Update** khi architecture thay đổi

**Tiếp theo:** Bạn muốn tôi vẽ sơ đồ cụ thể cho hệ thống của bạn không?
