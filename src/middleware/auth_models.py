"""
User and File Models for Authentication & Authorization
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()


class User(Base):
    """User model for authentication"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    files = relationship('File', back_populates='owner', cascade='all, delete-orphan')
    access_logs = relationship('FileAccessLog', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password: str) -> None:
        """Hash and set password"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password: str) -> bool:
        """Verify password"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<User {self.username}>'


class File(Base):
    """File model with permission and ownership tracking"""
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    file_id = Column(String(255), unique=True, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(String(100), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    is_public = Column(Boolean, default=False, index=True)
    storage_node = Column(String(10), nullable=True)
    file_path = Column(Text, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow, index=True)
    modified_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    download_count = Column(Integer, default=0)
    deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    owner = relationship('User', back_populates='files')
    access_logs = relationship('FileAccessLog', back_populates='file', cascade='all, delete-orphan')

    def to_dict(self, include_path: bool = False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'file_id': self.file_id,
            'filename': self.filename,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'user_id': self.user_id,
            'is_public': self.is_public,
            'storage_node': self.storage_node,
            'upload_date': self.upload_date.isoformat() if self.upload_date else None,
            'download_count': self.download_count
        }
        if include_path:
            data['file_path'] = self.file_path
        return data

    def __repr__(self):
        return f'<File {self.filename}>'


class FileAccessLog(Base):
    """Audit log for file access"""
    __tablename__ = 'file_access_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    file_id = Column(Integer, ForeignKey('files.id', ondelete='CASCADE'), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # 'download', 'view', 'delete', 'share'
    access_date = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)

    # Relationships
    user = relationship('User', back_populates='access_logs')
    file = relationship('File', back_populates='access_logs')

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'file_id': self.file_id,
            'action': self.action,
            'access_date': self.access_date.isoformat() if self.access_date else None,
            'ip_address': self.ip_address
        }

    def __repr__(self):
        return f'<FileAccessLog {self.action}>'
