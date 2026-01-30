# 🐳 Docker Deployment Guide

## Kiến Trúc Distributed System

```
┌──────────────┐
│   Browser    │
└──────┬───────┘
       │ HTTP
       ↓
┌─────────────────────┐
│  Gateway API        │ ← Container (Port 5000)
│  Flask + Routes     │
└──────┬──────────────┘
       │ HTTP/REST
       ├────────┬────────┐
       ↓        ↓        ↓
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Node1    │ │ Node2    │ │ Node3    │ ← 3 Containers độc lập
│ :8001    │ │ :8002    │ │ :8003    │
│ Flask    │ │ Flask    │ │ Flask    │
│ API      │ │ API      │ │ API      │
└──────────┘ └──────────┘ └──────────┘

┌───────────────┐
│ Worker x2     │ ← 2 Containers (scale được)
│ Image Process │
└───────────────┘

┌──────────┐  ┌──────────┐
│ RabbitMQ │  │  Redis   │ ← Infrastructure
└──────────┘  └──────────┘
```

## Yêu Cầu

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

## Khởi Động Hệ Thống

### 1. Build và Start All Services

```bash
docker-compose up --build -d
```

### 2. Kiểm Tra Services Đang Chạy

```bash
docker-compose ps
```

Kết quả mong đợi:
```
NAME                   STATUS    PORTS
fileshare-gateway      Up        0.0.0.0:5000->5000/tcp
fileshare-node1        Up        0.0.0.0:8001->8000/tcp
fileshare-node2        Up        0.0.0.0:8002->8000/tcp
fileshare-node3        Up        0.0.0.0:8003->8000/tcp
fileshare-rabbitmq     Up        5672/tcp, 15672/tcp
fileshare-redis        Up        6379/tcp
worker_1               Up
worker_2               Up
```

### 3. Xem Logs

```bash
# Tất cả services
docker-compose logs -f

# Gateway only
docker-compose logs -f gateway

# Storage nodes
docker-compose logs -f storage-node1 storage-node2 storage-node3

# Workers
docker-compose logs -f worker
```

## Truy Cập Services

| Service | URL | Mô Tả |
|---------|-----|-------|
| **Gateway API** | http://localhost:5000 | Main entry point |
| **Admin Dashboard** | http://localhost:5000/admin | Monitoring UI |
| **Storage Node 1** | http://localhost:8001 | Node 1 API |
| **Storage Node 2** | http://localhost:8002 | Node 2 API |
| **Storage Node 3** | http://localhost:8003 | Node 3 API |
| **RabbitMQ Management** | http://localhost:15672 | Queue UI (guest/guest) |

## Test Hệ Thống

### 1. Health Check All Nodes

```bash
# Gateway
curl http://localhost:5000/api/stats

# Node 1
curl http://localhost:8001/health

# Node 2
curl http://localhost:8002/health

# Node 3
curl http://localhost:8003/health
```

### 2. Upload File Test

```bash
curl -X POST http://localhost:5000/api/upload \
  -F "file=@test.jpg"
```

### 3. List Files

```bash
curl http://localhost:5000/api/files
```

## Scale Workers

Tăng số lượng workers xử lý tasks:

```bash
# Scale to 5 workers
docker-compose up --scale worker=5 -d

# Scale down to 1 worker
docker-compose up --scale worker=1 -d
```

## Dừng Hệ Thống

```bash
# Dừng tất cả services (giữ data)
docker-compose down

# Dừng và XÓA data
docker-compose down -v
```

## Troubleshooting

### 1. Gateway không kết nối được Storage Nodes

```bash
# Check network connectivity
docker exec -it fileshare-gateway ping storage-node1
docker exec -it fileshare-gateway curl http://storage-node1:8000/health
```

### 2. Worker không xử lý tasks

```bash
# Check RabbitMQ connection
docker exec -it worker_1 python -c "import pika; conn = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq')); print('OK')"

# Check logs
docker-compose logs -f worker
```

### 3. Rebuild Specific Service

```bash
# Rebuild gateway only
docker-compose up --build -d gateway

# Rebuild storage nodes
docker-compose up --build -d storage-node1 storage-node2 storage-node3
```

### 4. Reset Database

```bash
docker-compose down
docker volume rm fileshare_gateway-data
docker-compose up -d
```

## Development vs Production

### Development (Local)
```bash
# Run without -d to see logs
docker-compose up --build
```

### Production
```yaml
# Modify docker-compose.yml:
# - Remove port mappings for internal services
# - Add resource limits
# - Configure secrets
# - Use production Redis config
# - Add backup volumes
```

## Monitoring

### View Resource Usage

```bash
docker stats
```

### Inspect Volumes

```bash
docker volume ls
docker volume inspect fileshare_node1-data
```

### Network Inspection

```bash
docker network inspect fileshare_fileshare-network
```

## Architecture Benefits

✅ **Truly Distributed**: Mỗi node chạy độc lập
✅ **Scalable**: Scale workers dễ dàng
✅ **Isolated**: Services không ảnh hưởng lẫn nhau
✅ **Production-Ready**: Deploy được trên nhiều máy
✅ **Network Communication**: HTTP/gRPC giữa services
✅ **Docker Volumes**: Data persistence
✅ **Health Checks**: Auto-recovery khi service fail

## Next Steps

1. Deploy lên cloud (AWS, Azure, GCP)
2. Add Load Balancer trước Gateway
3. Configure SSL/TLS
4. Setup monitoring (Prometheus + Grafana)
5. Add backup strategy
