"""
Worker - Background Task Processor
Chương 3: Async Processing with RabbitMQ
Chương 2: Image Processing
"""

import os
import sys
import time
import json
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.config.settings import (
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD,
    LOGS_DIR, LOG_LEVEL, DATABASE_URL
)
from src.middleware.models import get_db, Task, File, StorageNode
from src.middleware.redis_client import get_redis_client
from src.worker.tasks import TaskDispatcher

# Configure logging with UTF-8 encoding for Windows compatibility
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'worker.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Worker:
    """
    Background worker for async task processing
    - Image compression
    - Thumbnail generation
    - Auto file deletion
    - Future: Video processing, PDF conversion, etc.
    """
    
    def __init__(self):
        # Initialize database
        self.db = get_db()
        
        # Initialize Redis client
        self.redis_client = get_redis_client()
        
        # Initialize task dispatcher
        self.task_dispatcher = TaskDispatcher(self.db, self.redis_client)
        
        self.running = False
        logger.info("Worker initialized")
    
    @property
    def db_session(self):
        """Compatibility property for legacy code that uses db_session"""
        # Return a fake session that wraps our db
        from src.middleware.models import get_session
        return get_session()
    
    def start(self):
        """Start worker main loop"""
        self.running = True
        logger.info("Worker started. Waiting for tasks...")
        
        try:
            while self.running:
                try:
                    # Process task queue
                    self._process_task_queue()
                    
                    # Process delete queue
                    self._process_delete_queue()
                    
                    # Small sleep to avoid busy loop
                    time.sleep(1)
                
                except KeyboardInterrupt:
                    logger.info("Worker interrupted by user")
                    break
                
                except Exception as e:
                    logger.error(f"Error in worker loop: {e}", exc_info=True)
                    time.sleep(5)  # Wait before retrying
        
        finally:
            self.stop()
    
    def stop(self):
        """Stop worker gracefully"""
        self.running = False
        logger.info("Worker stopped")
    
    def _process_task_queue(self):
        """
        Process tasks from task_queue
        (compress, thumbnail, etc.)
        """
        try:
            # Pop task from queue (non-blocking)
            task_data = self.redis_client.pop_queue('task_queue')
            
            if not task_data:
                return  # No tasks available
            
            task_id = task_data.get('task_id')
            file_id = task_data.get('file_id')
            task_type = task_data.get('task_type')
            file_path = task_data.get('file_path')
            node_id = task_data.get('node_id')
            
            logger.info(f"Processing task: {task_type} for file {file_id}")
            
            # Get task from database
            task = self.db_session.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found in database")
                return
            
            # Update task status to processing
            task.status = 'processing'
            task.started_at = datetime.utcnow()
            self.db_session.commit()
            
            # Dispatch task to appropriate handler
            success = self.task_dispatcher.dispatch(task_data)
            
            if success:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                logger.info(f"Task {task_id} completed successfully")
            else:
                task.status = 'failed'
                task.retry_count += 1
                
                # Retry logic
                if task.retry_count < 3:
                    logger.warning(f"Task {task_id} failed. Retrying ({task.retry_count}/3)")
                    # Push back to queue for retry
                    self.redis_client.push_queue('task_queue', task_data)
                    task.status = 'pending'
                else:
                    logger.error(f"Task {task_id} failed after 3 retries")
            
            self.db_session.commit()
        
        except Exception as e:
            logger.error(f"Error processing task queue: {e}", exc_info=True)
            if 'task' in locals() and task:
                task.status = 'failed'
                task.error_message = str(e)
                self.db_session.commit()
    
    def _process_delete_queue(self):
        """
        Process auto-deletion tasks from delete_queue
        """
        try:
            # Pop delete task from queue (non-blocking)
            delete_data = self.redis_client.pop_queue('delete_queue')
            
            if not delete_data:
                return  # No delete tasks
            
            task_id = delete_data.get('task_id')
            file_id = delete_data.get('file_id')
            scheduled_at_str = delete_data.get('scheduled_at')
            primary_node = delete_data.get('primary_node')
            replica_nodes = delete_data.get('replica_nodes', [])
            filename = delete_data.get('filename')
            
            # Parse scheduled time
            scheduled_at = datetime.fromisoformat(scheduled_at_str.replace('Z', '+00:00'))
            
            # Check if it's time to delete
            now = datetime.utcnow()
            if now < scheduled_at:
                # Not time yet, push back to queue
                wait_seconds = (scheduled_at - now).total_seconds()
                logger.debug(f"File {file_id} not ready for deletion. Waiting {wait_seconds:.0f}s")
                time.sleep(min(wait_seconds, 60))  # Sleep up to 60 seconds
                self.redis_client.push_queue('delete_queue', delete_data)
                return
            
            logger.info(f"Deleting file {file_id} (scheduled at {scheduled_at_str})")
            
            # Get task from database
            task = self.db_session.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = 'processing'
                task.started_at = datetime.utcnow()
                self.db_session.commit()
            
            # Delete from all nodes
            deleted_count = 0
            all_nodes = [primary_node] + replica_nodes
            
            for node_id in all_nodes:
                try:
                    from src.middleware.models import StorageNode
                    node = self.db_session.query(StorageNode).filter(
                        StorageNode.node_id == node_id
                    ).first()
                    
                    if node:
                        file_path = os.path.join(node.path, filename)
                        
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"Deleted file from node {node_id}: {file_path}")
                            
                            # Update node statistics
                            file_record = self.db_session.query(File).filter(File.id == file_id).first()
                            if file_record:
                                node.used_space -= file_record.file_size
                                node.file_count -= 1
                            
                            deleted_count += 1
                        else:
                            logger.warning(f"File not found on node {node_id}: {file_path}")
                
                except Exception as e:
                    logger.error(f"Error deleting file from node {node_id}: {e}")
            
            # Delete file record from database
            file_record = self.db_session.query(File).filter(File.id == file_id).first()
            if file_record:
                self.db_session.delete(file_record)
            
            # Delete from Redis cache
            self.redis_client.delete_cache(f"file_metadata:{file_id}")
            self.redis_client.delete_cache(f"download_counter:{file_id}")
            
            # Update task status
            if task:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                task.result = json.dumps({'deleted_nodes': deleted_count, 'total_nodes': len(all_nodes)})
            
            self.db_session.commit()
            
            logger.info(f"File {file_id} deleted from {deleted_count}/{len(all_nodes)} nodes")
        
        except Exception as e:
            logger.error(f"Error processing delete queue: {e}", exc_info=True)
            if 'task' in locals() and task:
                task.status = 'failed'
                task.error_message = str(e)
                self.db_session.commit()


def main():
    """Main entry point"""
    logger.info("Starting Distributed Image Storage Worker v2.0")
    
    worker = Worker()
    
    try:
        worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker crashed: {e}", exc_info=True)
    finally:
        worker.stop()


if __name__ == '__main__':
    main()
