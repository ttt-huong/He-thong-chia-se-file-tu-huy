"""
src/utils/uuid_generator.py - UUID Generation
Chương 5: UUID Identification
"""

import uuid
import hashlib
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def generate_file_id() -> str:
    """
    Generate unique file ID using UUID v4
    Chương 5: UUID Identification
    """
    file_id = str(uuid.uuid4())
    logger.debug(f"[UUID] Generated file ID: {file_id}")
    return file_id


def generate_checksum(file_path: str) -> str:
    """
    Generate SHA-256 checksum for file
    Used for integrity checking and deduplication
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        checksum = sha256_hash.hexdigest()
        logger.debug(f"[UUID] Checksum for {file_path}: {checksum}")
        return checksum
    except Exception as e:
        logger.error(f"[UUID] Failed to generate checksum: {e}")
        return None


def generate_task_id() -> str:
    """Generate unique task ID"""
    task_id = str(uuid.uuid4())
    return task_id


def generate_node_id(node_name: str) -> str:
    """Generate unique node ID"""
    return f"{node_name}-{str(uuid.uuid4())[:8]}"


if __name__ == "__main__":
    print("File ID:", generate_file_id())
    print("Task ID:", generate_task_id())
