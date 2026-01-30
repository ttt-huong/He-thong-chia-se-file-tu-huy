"""
API Routes - Upload, Download, File Management
Chương 5: UUID Identification
Chương 6: Caching
Chương 4: Distributed Locking
Chương 8: Load Balancing & Multi-Node Storage
"""

import os
import mimetypes
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, send_file
from werkzeug.utils import secure_filename

from src.config.settings import (
    ALLOWED_EXTENSIONS, MAX_FILE_SIZE, FILE_TTL_SECONDS
)
from src.utils.uuid_generator import generate_file_id


logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def select_storage_node(storage_manager, file_size: int) -> str:
    """
    Select best storage node using least-used strategy
    Docker mode: queries nodes directly via HTTP
    Returns node_id (node1, node2, node3)
    """
    try:
        # Get all registered nodes and check health
        nodes_health = storage_manager.check_all_health()
        
        if not nodes_health:
            logger.warning("No storage nodes registered, defaulting to node1")
            return 'node1'
        
        # Filter only online nodes
        online_nodes = {nid: health for nid, health in nodes_health.items() if health.get('status') == 'online'}
        
        if not online_nodes:
            logger.warning("No online nodes found, defaulting to node1")
            return 'node1'
        
        # Sort by file_count (ascending) - prefer node with least files
        nodes_sorted = sorted(online_nodes.items(), key=lambda x: x[1].get('file_count', 0))
        
        selected_id = nodes_sorted[0][0]
        logger.info(f"Selected {selected_id} (files: {nodes_sorted[0][1].get('file_count', 0)})")
        
        return selected_id
    
    except Exception as e:
        logger.error(f"Error selecting node: {e}, defaulting to node1")
        return 'node1'


def update_node_stats(db, node_id: str, file_size: int):
    """Update node statistics after file upload"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Update used_space and file_count
        cursor.execute("""
            UPDATE storage_nodes 
            SET used_space = used_space + ?,
                file_count = file_count + 1,
                last_heartbeat = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE node_id = ?
        """, (file_size, node_id))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Updated stats for {node_id}: +{file_size} bytes")
    
    except Exception as e:
        logger.error(f"Error updating node stats: {e}")


# =========================
# Simple Upload Endpoint
# =========================


@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload file endpoint with Multi-Node Load Balancing
    Chương 5: UUID Identification
    Chương 8: Load Balancing
    
    Returns:
        JSON with file_id, size, node
    """
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'File type not allowed. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

        # Read file content
        file_content = file.read()
        file_size = len(file_content)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large. Max: {MAX_FILE_SIZE / (1024**2):.0f}MB'}), 413
        
        # Generate UUID for file
        file_id = generate_file_id()
        
        # Get secure filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'jpg'
        stored_filename = f"{file_id}.{file_extension}"
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(original_filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        logger.info(f"Uploading: {original_filename} - Size: {file_size} bytes")
        
        # Select storage node (load balancing)
        storage_manager = current_app.storage_manager
        selected_node = select_storage_node(storage_manager, file_size)
        
        logger.info(f"Selected node: {selected_node} for file {file_id}")
        
        # Upload to selected storage node via HTTP
        storage_manager = current_app.storage_manager
        node_client = storage_manager.get_node(selected_node)
        
        if not node_client:
            logger.error(f"Storage node {selected_node} not found")
            return jsonify({'error': 'Storage node unavailable'}), 503
        
        try:
            upload_result = node_client.upload_file(file_content, stored_filename)
            # Check if upload was successful (storage node returns 'status': 'success')
            if upload_result.get('status') != 'success':
                raise Exception(upload_result.get('error', 'Upload failed'))
            logger.info(f"File uploaded to {selected_node}: {upload_result}")
        except Exception as upload_err:
            logger.error(f"Failed to upload to node {selected_node}: {upload_err}")
            return jsonify({'error': f'Storage upload failed: {str(upload_err)}'}), 500
        
        # Save to database
        expires_at = (datetime.utcnow() + timedelta(seconds=FILE_TTL_SECONDS)).isoformat()
        
        db.add_file(
            file_id=file_id,
            filename=stored_filename,
            original_name=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            primary_node=selected_node,
            expires_at=expires_at
        )
        
        # Update node statistics
        update_node_stats(db, selected_node, file_size)
        
        logger.info(f"File saved: {file_id} -> {selected_node}/{stored_filename}")
        
        # Create background task for image processing
        if mime_type.startswith('image/'):
            task_id = db.add_task(file_id, 'thumbnail')
            if task_id:
                logger.info(f"📸 Thumbnail task created: {task_id} for file {file_id}")
            else:
                logger.warning(f"Failed to create thumbnail task for {file_id}")
        
        return jsonify({
            'id': file_id,
            'filename': stored_filename,
            'original_name': original_filename,
            'size': file_size,
            'node': selected_node,
            'download_url': f"/api/download/{file_id}"
        }), 200
    
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        if 'db_session' in locals():
            try:
                db_session.rollback()
            except:
                pass
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@api_bp.route('/download/<file_id>', methods=['GET'])
def download_file(file_id: str):
    """Download file endpoint (SIMPLE VERSION)"""
    try:
        db = current_app.db
        file_record = db.get_file(file_id)
        if not file_record:
            return jsonify({'error': 'File not found'}), 404

        node = file_record.get('primary_node', 'node1')
        filename = file_record.get('filename')
        if not filename:
            return jsonify({'error': 'File missing filename'}), 500

        # Download from storage node via HTTP
        storage_manager = current_app.storage_manager
        node_client = storage_manager.get_node(node)
        
        if not node_client:
            return jsonify({'error': 'Storage node unavailable'}), 503
        
        try:
            file_content = node_client.download_file(filename)
            if not file_content:
                return jsonify({'error': 'File not found on storage'}), 404
            
            # Return file content with proper headers
            from flask import Response
            response = Response(file_content)
            response.headers['Content-Type'] = file_record.get('mime_type') or 'application/octet-stream'
            response.headers['Content-Disposition'] = f'attachment; filename="{file_record.get("original_name") or filename}"'
            return response
        except Exception as download_err:
            logger.error(f"Failed to download from node {node}: {download_err}")
            return jsonify({'error': 'Download failed'}), 500
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/files', methods=['GET'])
def list_files():
    """Return recent files with minimal metadata for gallery (masonry)."""
    try:
        db = current_app.db
        # Get all files from database
        all_files_data = db.get_all_files(limit=50)
        
        result = []
        for file_data in all_files_data:
            created_at = file_data.get('created_at')
            if created_at is not None and not isinstance(created_at, str):
                try:
                    created_at = created_at.isoformat()
                except Exception:
                    created_at = str(created_at)

            item = {
                'id': file_data.get('id'),
                'filename': file_data.get('filename'),
                'original_name': file_data.get('original_name'),
                'size': file_data.get('file_size', 0),
                'mime_type': file_data.get('mime_type'),
                'node': file_data.get('primary_node', 'node1'),
                'created_at': created_at,
                'download_url': f"/api/download/{file_data.get('id')}"
            }
            result.append(item)

        return jsonify({'count': len(result), 'files': result}), 200
    except Exception as e:
        logger.error(f"List files error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/nodes', methods=['GET'])
def get_nodes():
    """
    Get storage nodes information with statistics
    Docker mode: queries nodes directly via HTTP health checks
    """
    try:
        # Get storage manager and query all nodes via HTTP
        storage_manager = current_app.storage_manager
        logger.info(f"Storage manager nodes: {storage_manager.nodes.keys() if storage_manager else 'None'}")
        
        nodes_health = storage_manager.check_all_health()
        logger.info(f"Nodes health check result: {nodes_health}")
        
        nodes_data = []
        for node_id, health_data in nodes_health.items():
            status = health_data.get('status', 'offline')
            file_count = health_data.get('file_count', 0)
            
            node_info = {
                'node_id': node_id,
                'host': 'docker',
                'port': '8000',
                'path': health_data.get('storage_path', '/data'),
                'is_online': status == 'online',
                'total_space': 100 * 1024 * 1024 * 1024,  # 100GB default
                'used_space': 0,  # TODO: get from node stats endpoint
                'free_space': 100 * 1024 * 1024 * 1024,
                'usage_percent': 0,
                'file_count': file_count,
                'error_count': 0,
                'last_heartbeat': health_data.get('timestamp', datetime.utcnow().isoformat()),
                'status': status
            }
            nodes_data.append(node_info)
        
        logger.info(f"Returning {len(nodes_data)} nodes")
        return jsonify({
            'total_nodes': len(nodes_data),
            'nodes': nodes_data
        }), 200
    
    except Exception as e:
        logger.error(f"Get nodes error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get system statistics for admin dashboard"""
    try:
        db = current_app.db
        
        # Get all files
        all_files = db.get_all_files(limit=1000)
        
        # Get storage nodes
        nodes = db.get_storage_nodes()
        
        # Calculate statistics
        total_files = len(all_files)
        total_size = sum(f.get('file_size', 0) for f in all_files)
        
        # Group files by node
        files_by_node = {}
        size_by_node = {}
        for f in all_files:
            node = f.get('primary_node', 'unknown')
            files_by_node[node] = files_by_node.get(node, 0) + 1
            size_by_node[node] = size_by_node.get(node, 0) + f.get('file_size', 0)
        
        # Storage capacity
        total_capacity = sum(n.get('total_space', 0) for n in nodes)
        total_used = sum(n.get('used_space', 0) for n in nodes)
        total_free = total_capacity - total_used
        
        # Node status
        online_nodes = sum(1 for n in nodes if n.get('is_online', 0))
        offline_nodes = len(nodes) - online_nodes
        
        stats = {
            'files': {
                'total': total_files,
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'by_node': files_by_node,
                'size_by_node': size_by_node
            },
            'storage': {
                'total_capacity': total_capacity,
                'total_capacity_gb': round(total_capacity / (1024 ** 3), 2),
                'total_used': total_used,
                'total_used_mb': round(total_used / (1024 * 1024), 2),
                'total_free': total_free,
                'total_free_gb': round(total_free / (1024 ** 3), 2),
                'usage_percent': round((total_used / total_capacity * 100), 2) if total_capacity > 0 else 0
            },
            'nodes': {
                'total': len(nodes),
                'online': online_nodes,
                'offline': offline_nodes
            }
        }
        
        return jsonify(stats), 200
    
    except Exception as e:
        logger.error(f"Get stats error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """
    Get background tasks status
    
    Query parameters:
        - status: pending/processing/completed/failed (optional)
        - limit: number of tasks to return (default: 50)
    
    Returns:
        JSON array of tasks with their status
    """
    try:
        db = current_app.db
        status_filter = request.args.get('status', None)
        limit = int(request.args.get('limit', 50))
        
        # Get tasks from database
        conn = db.get_connection()
        cursor = conn.cursor()
        
        if status_filter:
            cursor.execute("""
                SELECT t.*, f.filename, f.original_name, f.mime_type
                FROM tasks t
                LEFT JOIN files f ON t.file_id = f.id
                WHERE t.status = ?
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (status_filter, limit))
        else:
            cursor.execute("""
                SELECT t.*, f.filename, f.original_name, f.mime_type
                FROM tasks t
                LEFT JOIN files f ON t.file_id = f.id
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        tasks = []
        for row in rows:
            tasks.append({
                'id': row['id'],
                'file_id': row['file_id'],
                'filename': row['filename'],
                'original_name': row['original_name'],
                'task_type': row['task_type'],
                'status': row['status'],
                'result': row['result'],
                'error_message': row['error_message'],
                'created_at': row['created_at'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at'],
                'retry_count': row['retry_count']
            })
        
        return jsonify(tasks), 200
    
    except Exception as e:
        logger.error(f"Get tasks error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
