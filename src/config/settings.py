"""
src/config/settings.py - Environment Configuration
Quản lý tất cả các setting từ environment variables
"""

import os
from pathlib import Path

# ===== PATHS =====
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = BASE_DIR / "src"
STORAGE_DIR = BASE_DIR / "storage"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

# Create directories if not exist
STORAGE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ===== FLASK SETTINGS =====
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
HOST = os.getenv("FLASK_HOST", "0.0.0.0")
PORT = int(os.getenv("FLASK_PORT", 5000))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# ===== DATABASE SETTINGS =====
DATABASE_PATH = os.getenv("DATABASE_PATH", DATA_DIR / "sqlite" / "metadata.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# ===== REDIS SETTINGS =====
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_URL = f"redis://{'':'' if not REDIS_PASSWORD else f':{REDIS_PASSWORD}@'}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# ===== RABBITMQ SETTINGS =====
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
RABBITMQ_URL = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"

# ===== STORAGE NODES SETTINGS =====
STORAGE_NODES = {
    "node1": {
        "host": os.getenv("NODE1_HOST", "localhost"),
        "port": int(os.getenv("NODE1_PORT", 5001)),
        "path": os.getenv("NODE1_PATH", STORAGE_DIR / "node1"),
    },
    "node2": {
        "host": os.getenv("NODE2_HOST", "localhost"),
        "port": int(os.getenv("NODE2_PORT", 5002)),
        "path": os.getenv("NODE2_PATH", STORAGE_DIR / "node2"),
    },
    "node3": {
        "host": os.getenv("NODE3_HOST", "localhost"),
        "port": int(os.getenv("NODE3_PORT", 5003)),
        "path": os.getenv("NODE3_PATH", STORAGE_DIR / "node3"),
    },
}

# ===== FILE SETTINGS =====
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
THUMBNAIL_SIZE = tuple(map(int, os.getenv("THUMBNAIL_SIZE", "200,200").split(",")))
COMPRESSION_QUALITY = int(os.getenv("COMPRESSION_QUALITY", 85))

# ===== TTL & COUNTER SETTINGS =====
FILE_TTL_SECONDS = int(os.getenv("FILE_TTL_SECONDS", 3600))  # 1 hour
DOWNLOAD_LIMIT = int(os.getenv("DOWNLOAD_LIMIT", 3))  # 3 downloads
WORKER_DELAY_SECONDS = int(os.getenv("WORKER_DELAY_SECONDS", 60))  # 60 seconds before delete

# ===== REPLICATION SETTINGS =====
REPLICATION_FACTOR = int(os.getenv("REPLICATION_FACTOR", 2))  # Replicate to 2 nodes
REPLICATION_ENABLED = os.getenv("REPLICATION_ENABLED", "True").lower() == "true"

# ===== HEALTH CHECK SETTINGS =====
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", 10))  # 10 seconds
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", 5))  # 5 seconds

# ===== LOGGING SETTINGS =====
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOGS_DIR / "app.log"

# ===== NGROK SETTINGS =====
NGROK_URL = os.getenv("NGROK_URL", None)  # Set for public access

print("[SETTINGS] Configuration loaded successfully")
