"""
src/middleware/models.py - Data Models (Metadata Schema)
Định nghĩa các data models cho SQLite
"""

from sqlalchemy import Column, String, Integer, DateTime, Float, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime, timedelta
import json

Base = declarative_base()


class File(Base):
    """
    Metadata của mỗi file upload
    Chương 5: UUID Identification
    """
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String(50), nullable=False)
    
    # Storage info
    primary_node = Column(String(50), nullable=False)  # node1, node2, node3
    replica_nodes = Column(String(255), default="")  # JSON: ["node2", "node3"]
    
    # Download info
    download_limit = Column(Integer, default=3)
    downloads_left = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # TTL expiration
    
    # Metadata
    checksum = Column(String(64), nullable=True)  # SHA-256
    is_compressed = Column(Boolean, default=False)
    has_thumbnail = Column(Boolean, default=False)
    
    # Status
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<File id={self.id} name={self.filename}>"

    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "primary_node": self.primary_node,
            "replica_nodes": json.loads(self.replica_nodes) if self.replica_nodes else [],
            "downloads_left": self.downloads_left,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


class StorageNode(Base):
    """
    Thông tin về mỗi Storage Node
    Chương 7, 8: Replication, Health Monitoring
    """
    __tablename__ = "storage_nodes"

    node_id = Column(String(50), primary_key=True)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    path = Column(String(255), nullable=False)  # Local disk path
    
    # Status
    is_online = Column(Boolean, default=True)
    total_space = Column(Integer, default=0)  # bytes
    used_space = Column(Integer, default=0)   # bytes
    file_count = Column(Integer, default=0)
    
    # Health monitoring
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    error_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<StorageNode id={self.node_id} host={self.host}:{self.port}>"

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "is_online": self.is_online,
            "used_space": self.used_space,
            "total_space": self.total_space,
            "file_count": self.file_count,
            "error_count": self.error_count,
        }


class Task(Base):
    """
    Background job tasks (image processing, file deletion)
    Chương 3, 4: Async processing
    """
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), nullable=False)
    task_type = Column(String(50), nullable=False)  # "compress", "thumbnail", "delete"
    
    # Status
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    result = Column(String(500), nullable=True)  # JSON result
    error_message = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0)

    def __repr__(self):
        return f"<Task id={self.id} type={self.task_type} status={self.status}>"

    def to_dict(self):
        return {
            "id": self.id,
            "file_id": self.file_id,
            "task_type": self.task_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


class ReplicationLog(Base):
    """
    Log của mỗi lần replication
    Chương 7: Data Replication tracking
    """
    __tablename__ = "replication_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String(36), nullable=False)
    source_node = Column(String(50), nullable=False)
    target_node = Column(String(50), nullable=False)
    
    # Status
    status = Column(String(20), default="pending")  # pending, in_progress, completed, failed
    error_message = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    def __repr__(self):
        return f"<ReplicationLog file={self.file_id} {self.source_node}->{self.target_node}>"


def init_db(database_url):
    """Initialize database connection and create tables"""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


if __name__ == "__main__":
    # Test: Create tables
    from src.config.settings import DATABASE_URL
    engine, Session = init_db(DATABASE_URL)
    print("[MODELS] Database tables created successfully")
