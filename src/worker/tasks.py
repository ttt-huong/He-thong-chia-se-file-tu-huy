"""
Task Dispatcher - Điều phối task đến handler tương ứng
Modular design for extensibility (images, videos, PDFs, etc.)
"""

import os
import json
import logging
from typing import Dict, Callable, Any

from src.worker.image_processor import ImageProcessor
from src.middleware.models import File

logger = logging.getLogger(__name__)


class TaskDispatcher:
    """
    Dispatch tasks to appropriate handlers based on file type
    Extensible design: easy to add new file type handlers
    """
    
    def __init__(self, db_session, redis_client):
        self.db_session = db_session
        self.redis_client = redis_client
        self.image_processor = ImageProcessor()
        
        # Task handler registry (extensible)
        self.task_handlers: Dict[str, Callable] = {
            'compress': self.handle_compress_task,
            'thumbnail': self.handle_thumbnail_task,
            # Future handlers:
            # 'video_compress': self.handle_video_compress,
            # 'video_thumbnail': self.handle_video_thumbnail,
            # 'pdf_convert': self.handle_pdf_convert,
            # 'audio_normalize': self.handle_audio_normalize,
        }
        
        logger.info(f"TaskDispatcher initialized with {len(self.task_handlers)} handlers")
    
    def dispatch(self, task_data: Dict[str, Any]) -> bool:
        """
        Dispatch task to appropriate handler
        
        Args:
            task_data: Task information dict
        
        Returns:
            True if task handled successfully, False otherwise
        """
        try:
            task_type = task_data.get('task_type')
            file_id = task_data.get('file_id')
            
            logger.info(f"Dispatching task: {task_type} for file {file_id}")
            
            # Get handler
            handler = self.task_handlers.get(task_type)
            
            if not handler:
                logger.error(f"No handler found for task type: {task_type}")
                return False
            
            # Execute handler
            success = handler(task_data)
            
            return success
        
        except Exception as e:
            logger.error(f"Error dispatching task: {e}", exc_info=True)
            return False
    
    def handle_compress_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Handle image compression task
        
        Args:
            task_data: Task information
        
        Returns:
            True if successful
        """
        try:
            file_id = task_data.get('file_id')
            file_path = task_data.get('file_path')
            node_id = task_data.get('node_id')
            
            logger.info(f"Compressing image: {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False
            
            # Check if it's an image
            if not self.image_processor.is_valid_image(file_path):
                logger.error(f"Not a valid image: {file_path}")
                return False
            
            # Compress image (overwrite original)
            success, output_path, metadata = self.image_processor.compress_image(
                input_path=file_path,
                output_path=file_path,  # Overwrite original
                quality=85,
                max_dimension=2048  # Max 2048px on longest side
            )
            
            if success:
                # Update file record
                file_record = self.db_session.query(File).filter(File.id == file_id).first()
                if file_record:
                    # Update file size
                    new_size = metadata.get('compressed_size', file_record.file_size)
                    old_size = file_record.file_size
                    file_record.file_size = new_size
                    file_record.is_compressed = True
                    
                    # Update node used space
                    from src.middleware.models import StorageNode
                    node = self.db_session.query(StorageNode).filter(
                        StorageNode.node_id == node_id
                    ).first()
                    if node:
                        space_saved = old_size - new_size
                        node.used_space -= space_saved
                        logger.info(f"Saved {space_saved / 1024:.2f} KB on node {node_id}")
                    
                    self.db_session.commit()
                
                # Update cache
                self.redis_client.delete_cache(f"file_metadata:{file_id}")
                
                logger.info(f"Compression successful: {metadata.get('compression_ratio')}% reduction")
                return True
            else:
                logger.error(f"Compression failed: {metadata.get('error')}")
                return False
        
        except Exception as e:
            logger.error(f"Error in compress task: {e}", exc_info=True)
            self.db_session.rollback()
            return False
    
    def handle_thumbnail_task(self, task_data: Dict[str, Any]) -> bool:
        """
        Handle thumbnail generation task
        
        Args:
            task_data: Task information
        
        Returns:
            True if successful
        """
        try:
            file_id = task_data.get('file_id')
            file_path = task_data.get('file_path')
            node_id = task_data.get('node_id')
            
            logger.info(f"Creating thumbnail: {file_path}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return False
            
            # Check if it's an image
            if not self.image_processor.is_valid_image(file_path):
                logger.error(f"Not a valid image: {file_path}")
                return False
            
            # Create thumbnail
            base, ext = os.path.splitext(file_path)
            thumbnail_path = f"{base}_thumb{ext}"
            
            success, output_path, metadata = self.image_processor.create_thumbnail(
                input_path=file_path,
                output_path=thumbnail_path,
                size=(200, 200),
                quality=80
            )
            
            if success:
                # Update file record
                file_record = self.db_session.query(File).filter(File.id == file_id).first()
                if file_record:
                    file_record.has_thumbnail = True
                    
                    # Update node used space
                    from src.middleware.models import StorageNode
                    node = self.db_session.query(StorageNode).filter(
                        StorageNode.node_id == node_id
                    ).first()
                    if node:
                        thumb_size = metadata.get('thumbnail_size', 0)
                        node.used_space += thumb_size
                    
                    self.db_session.commit()
                
                # Update cache
                self.redis_client.delete_cache(f"file_metadata:{file_id}")
                
                logger.info(f"Thumbnail created: {output_path}")
                return True
            else:
                logger.error(f"Thumbnail creation failed: {metadata.get('error')}")
                return False
        
        except Exception as e:
            logger.error(f"Error in thumbnail task: {e}", exc_info=True)
            self.db_session.rollback()
            return False
    
    # Example of how to add new handlers for other file types:
    
    def handle_video_compress(self, task_data: Dict[str, Any]) -> bool:
        """
        Future: Handle video compression
        Would use ffmpeg or similar
        """
        logger.warning("Video compression not yet implemented")
        return False
    
    def handle_pdf_convert(self, task_data: Dict[str, Any]) -> bool:
        """
        Future: Handle PDF to image conversion
        Would use pdf2image or similar
        """
        logger.warning("PDF conversion not yet implemented")
        return False
    
    def register_handler(self, task_type: str, handler: Callable):
        """
        Register a new task handler (for extensibility)
        
        Args:
            task_type: Type of task (e.g., 'video_compress')
            handler: Function to handle the task
        """
        self.task_handlers[task_type] = handler
        logger.info(f"Registered new handler for task type: {task_type}")
