# CẤU TRÚC DỰ ÁN - HỆ THỐNG LƯU TRỮ ẢNH PHÂN TÁN

```
FileShareSystem/
│
├── README.md                          # Tài liệu dự án
├── architecture.md                    # Sơ đồ Mermaid
├── architecture.puml                  # PlantUML code
├── DRAW_GUIDE.md                      # Hướng dẫn vẽ sơ đồ
├── PROJECT_STRUCTURE.md               # File này
│
├── docker-compose.yml                 # Khởi động Redis + RabbitMQ
│
├── src/                               # Mã nguồn chính
│   │
│   ├── gateway/                       # API Gateway (Master Node)
│   │   ├── __init__.py
│   │   ├── app.py                     # Flask API Server
│   │   ├── routes.py                  # API endpoints
│   │   ├── health_check.py            # Health monitoring
│   │   ├── node_selector.py           # Lựa chọn Storage Node
│   │   └── error_handler.py           # Xử lý lỗi
│   │
│   ├── worker/                        # Background Worker
│   │   ├── __init__.py
│   │   ├── worker.py                  # Main worker process
│   │   ├── image_processor.py         # Xử lý ảnh (nén, thumbnail)
│   │   ├── tasks.py                   # Định nghĩa tasks
│   │   └── scheduler.py               # Job scheduling
│   │
│   ├── storage/                       # Storage Node (Slave)
│   │   ├── __init__.py
│   │   ├── node_server.py             # Storage Node HTTP server
│   │   ├── replicator.py              # Auto replication script
│   │   ├── file_manager.py            # Quản lý file trên disk
│   │   └── sync_handler.py            # Xử lý đồng bộ hóa
│   │
│   ├── middleware/                    # Data Layer (Redis, RabbitMQ, SQLite)
│   │   ├── __init__.py
│   │   ├── database.py                # SQLite ORM (metadata)
│   │   ├── redis_client.py            # Redis operations
│   │   ├── rabbitmq_client.py         # RabbitMQ operations
│   │   ├── models.py                  # Data models (metadata)
│   │   └── cache_manager.py           # Cache layer
│   │
│   ├── utils/                         # Utility functions
│   │   ├── __init__.py
│   │   ├── uuid_generator.py          # UUID generation
│   │   ├── logger.py                  # Logging
│   │   ├── validators.py              # Input validation
│   │   ├── constants.py               # Global constants
│   │   └── helpers.py                 # Helper functions
│   │
│   └── config/                        # Configuration
│       ├── __init__.py
│       ├── settings.py                # Environment settings
│       ├── database_config.py         # Database config
│       ├── redis_config.py            # Redis config
│       └── rabbitmq_config.py         # RabbitMQ config
│
├── config/                            # Config files
│   ├── nginx.conf                     # Nginx Load Balancer config
│   ├── supervisord.conf               # Process manager config
│   └── logrotate.conf                 # Log rotation config
│
├── nginx/                             # Nginx Load Balancer
│   ├── Dockerfile                     # Nginx container
│   └── nginx.conf                     # Nginx configuration
│
├── scripts/                           # Utility scripts
│   ├── init_db.py                     # Initialize SQLite database
│   ├── health_check.sh                # Health check script
│   ├── backup.py                      # Backup data
│   ├── deploy.sh                      # Deployment script
│   └── start_all_nodes.sh             # Start all storage nodes
│
├── tests/                             # Unit tests
│   ├── test_gateway.py                # Test API Gateway
│   ├── test_worker.py                 # Test Worker
│   ├── test_storage.py                # Test Storage Node
│   ├── test_replication.py            # Test Replication
│   └── test_metadata.py               # Test Metadata DB
│
├── docs/                              # Documentation
│   ├── API_DOCS.md                    # API documentation
│   ├── DEPLOYMENT.md                  # Deployment guide
│   ├── TROUBLESHOOTING.md             # Troubleshooting
│   └── PERFORMANCE.md                 # Performance tuning
│
├── storage/                           # Local file storage (Slave Node)
│   ├── node1/                         # Storage Node 1
│   │   ├── files/                     # Actual image files
│   │   ├── thumbnails/                # Generated thumbnails
│   │   └── compressed/                # Compressed images
│   ├── node2/                         # Storage Node 2
│   └── node3/                         # Storage Node 3
│
├── data/                              # Data persistence
│   ├── sqlite/
│   │   └── metadata.db                # SQLite database file
│   └── redis/                         # Redis data (in Docker)
│
├── logs/                              # Log files
│   ├── gateway.log                    # Gateway logs
│   ├── worker.log                     # Worker logs
│   ├── storage_node1.log              # Node 1 logs
│   └── errors.log                     # Error logs
│
├── requirements.txt                   # Python dependencies
├── .env                               # Environment variables (git-ignored)
├── .gitignore                         # Git ignore file
├── app.py                             # Legacy: Simple Flask app (v1.0)
└── worker.py                          # Legacy: Simple Worker (v1.0)
```

---

## 📁 MỤC ĐÍCH CỦA TỪNG THÀNH PHẦN

### **src/gateway/** - API Gateway (Master Node)
- **app.py**: Khởi tạo Flask app, cấu hình routes
- **routes.py**: Các endpoint `/upload`, `/download`, `/health`
- **health_check.py**: Định kỳ check health của Storage Nodes, trigger failover
- **node_selector.py**: Chọn Storage Node tối ưu dựa trên load, available space
- **error_handler.py**: Xử lý HTTP errors, exceptions

### **src/worker/** - Background Worker
- **worker.py**: Main loop lắng nghe RabbitMQ queue
- **image_processor.py**: Nén ảnh, tạo thumbnail (Pillow/ImageMagick)
- **tasks.py**: Định nghĩa các task (resize, compress, generate_thumbnail)
- **scheduler.py**: Scheduling recurring jobs (cleanup, health check)

### **src/storage/** - Storage Node (Slave Server)
- **node_server.py**: HTTP server nhỏ cho mỗi Storage Node
- **replicator.py**: Script tự động sao chép file sang node khác
- **file_manager.py**: Quản lý file: upload, download, delete, list
- **sync_handler.py**: Xử lý đồng bộ hóa giữa các node

### **src/middleware/** - Data Layer
- **database.py**: ORM wrapper cho SQLite (metadata)
- **redis_client.py**: Wrapper Redis (caching, locking, counter)
- **rabbitmq_client.py**: Wrapper RabbitMQ (publish, consume)
- **models.py**: Data models (File, Node, Task metadata)
- **cache_manager.py**: Cache policy (TTL, invalidation)

### **src/utils/** - Utility Functions
- **uuid_generator.py**: Tạo UUID v4 cho file ID
- **logger.py**: Centralized logging (file, console, rotation)
- **validators.py**: Validate input (file size, type, user quota)
- **constants.py**: Định nghĩa constants (TTL, max_size, node_count)
- **helpers.py**: Helper functions (path joining, file extension check, etc)

### **src/config/** - Configuration
- **settings.py**: Environment variables (DATABASE_URL, REDIS_HOST, etc)
- **database_config.py**: SQLite connection settings
- **redis_config.py**: Redis connection & pool settings
- **rabbitmq_config.py**: RabbitMQ connection & exchange settings

### **config/** - Configuration Files
- **nginx.conf**: Load Balancer config (upstream, proxy_pass, health check)
- **supervisord.conf**: Process manager (manage multiple worker instances)
- **logrotate.conf**: Automatic log rotation

### **scripts/** - Automation Scripts
- **init_db.py**: Tạo SQLite schema tables
- **health_check.sh**: Cron job check node health
- **backup.py**: Backup metadata database
- **deploy.sh**: Automated deployment
- **start_all_nodes.sh**: Start multiple storage nodes

### **tests/** - Test Suite
- Unit tests cho mỗi component
- Integration tests cho entire system
- Load tests

### **docs/** - Documentation
- API reference, deployment guide, troubleshooting

### **storage/** - Physical Storage
- Thư mục lưu file thực tế trên mỗi Storage Node
- Subfolder: `files/`, `thumbnails/`, `compressed/`

### **data/** - Persistent Data
- SQLite database file
- Redis snapshots (backup)

### **logs/** - Log Files
- Centralized logging

---

## 🔄 LUỒNG HOẠT ĐỘNG THEO CẤU TRÚC

### Upload Ảnh:
```
Client 
  ↓ POST /upload
Gateway (app.py → routes.py)
  ↓ 1. Validate file (validators.py)
  ↓ 2. Generate UUID (uuid_generator.py)
  ↓ 3. Select Storage Node (node_selector.py)
  ↓ 4. Save metadata (database.py → models.py)
  ↓ 5. Save file to Storage Node (storage/node_server.py)
  ↓ 6. Replicate to other nodes (storage/replicator.py)
  ↓ 7. Set Redis counter (middleware/redis_client.py)
  ↓ 8. Publish task to RabbitMQ (middleware/rabbitmq_client.py)
Worker (worker.py)
  ↓ 9. Consume task
  ↓ 10. Process image (worker/image_processor.py)
  ↓ 11. Save thumbnail/compressed (storage/node_server.py)
```

### Download Ảnh:
```
Client 
  ↓ GET /download/{file_id}
Gateway (routes.py)
  ↓ 1. Check Redis cache (middleware/redis_client.py)
  ↓ 2. Get metadata from SQLite (database.py)
  ↓ 3. Decrease download counter (middleware/redis_client.py)
  ↓ 4. Get file from Storage Node (storage/file_manager.py)
  ↓ 5. Return file stream to Client
```

---

## 🚀 CÁC BƯỚC TIẾP THEO

1. **Tạo các file trong src/** với code cơ bản
2. **Viết SQLite models** (File, Node, Task)
3. **Implement API endpoints** (routes.py)
4. **Implement Worker** (image_processor.py)
5. **Implement Storage Nodes** (node_server.py + replicator.py)
6. **Setup Nginx config** (nginx/nginx.conf)
7. **Viết tests** (tests/)
8. **Deployment** (scripts/deploy.sh)

---

**Phiên bản**: 2.0 (Structure)
**Ngày tạo**: 22/01/2026
