"""
API Routes - Upload, Download, File Management
Chương 5: UUID Identification
Chương 6: Caching
Chương 4: Distributed Locking
"""

import os
import tempfile
import mimetypes
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
import json

from src.config.settings import (
    ALLOWED_EXTENSIONS, MAX_FILE_SIZE, FILE_TTL_SECONDS,
    DOWNLOAD_LIMIT, REPLICATION_ENABLED, REPLICATION_FACTOR
)
from src.middleware.models import get_db, File, StorageNode, Task
from src.utils.uuid_generator import generate_file_id, generate_checksum, generate_task_id
from src.gateway.node_selector import NodeSelector
import math
import shutil
from src.worker.image_processor import ImageProcessor


logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# =========================
# Chunked Upload Endpoints
# =========================

@api_bp.route('/chunk/init', methods=['POST'])
def chunk_init():
    """Initialize a chunked upload session and return upload_id.
    Body JSON: { filename, size, mime_type, chunk_size? }
    """
    try:
        data = request.get_json(force=True)
        filename = secure_filename(data.get('filename', ''))
        total_size = int(data.get('size', 0))
        mime_type = data.get('mime_type', 'application/octet-stream')
        chunk_size = int(data.get('chunk_size', 5 * 1024 * 1024))  # default 5MB

        if not filename or total_size <= 0:
            return jsonify({'error': 'Invalid filename or size'}), 400

        # Generate upload session id
        upload_id = generate_file_id()

        parts_expected = math.ceil(total_size / chunk_size)

        # Prepare temp dir
        temp_dir = os.path.join(tempfile.gettempdir(), 'chunks', upload_id)
        os.makedirs(temp_dir, exist_ok=True)

        # Save manifest in Redis
        manifest = {
            'upload_id': upload_id,
            'filename': filename,
            'mime_type': mime_type,
            'total_size': total_size,
            'chunk_size': chunk_size,
            'parts_expected': parts_expected,
            'received': 0,
            'parts': {},  # part_number -> {size, checksum, path}
            'status': 'in_progress',
            'temp_dir': temp_dir,
            'created_at': datetime.utcnow().isoformat()
        }

        redis_client = current_app.redis_client
        redis_client.set_cache(f"upload:{upload_id}", manifest, ttl=3600)

        return jsonify({
            'upload_id': upload_id,
            'chunk_size': chunk_size,
            'parts_expected': parts_expected
        }), 200
    except Exception as e:
        logger.error(f"Chunk init error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/chunk/upload', methods=['POST'])
def chunk_upload():
    """Upload a single chunk.
    Query/Form: upload_id, part_number, checksum
    Body: raw bytes of the chunk
    """
    try:
        upload_id = request.args.get('upload_id') or request.form.get('upload_id')
        part_number = request.args.get('part_number') or request.form.get('part_number')
        checksum = request.args.get('checksum') or request.form.get('checksum')

        if not upload_id or part_number is None:
            return jsonify({'error': 'Missing upload_id or part_number'}), 400
        try:
            part_number = int(part_number)
        except:
            return jsonify({'error': 'part_number must be integer'}), 400

        redis_client = current_app.redis_client
        manifest = redis_client.get_cache(f"upload:{upload_id}")
        if not manifest:
            return jsonify({'error': 'Upload session not found'}), 404
        if manifest.get('status') != 'in_progress':
            return jsonify({'error': 'Upload session not active'}), 409

        parts_expected = int(manifest['parts_expected'])
        if part_number < 1 or part_number > parts_expected:
            return jsonify({'error': 'Invalid part_number'}), 400

        chunk_bytes = request.get_data()
        if not chunk_bytes:
            return jsonify({'error': 'Empty chunk'}), 400

        # Save chunk to temp dir
        temp_dir = manifest['temp_dir']
        os.makedirs(temp_dir, exist_ok=True)
        part_path = os.path.join(temp_dir, f"part_{part_number:06d}")
        with open(part_path, 'wb') as pf:
            pf.write(chunk_bytes)

        # Verify checksum if provided
        if checksum:
            try:
                calc = generate_checksum(part_path)
                if calc != checksum:
                    os.remove(part_path)
                    return jsonify({'error': 'Checksum mismatch'}), 400
            except Exception:
                pass

        # Update manifest
        parts = manifest.get('parts', {})
        parts[str(part_number)] = {
            'size': len(chunk_bytes),
            'checksum': checksum,
            'path': part_path
        }
        manifest['parts'] = parts
        manifest['received'] = len(parts)

        redis_client.set_cache(f"upload:{upload_id}", manifest, ttl=3600)

        return jsonify({
            'received': manifest['received'],
            'parts_expected': parts_expected,
            'progress': round(manifest['received'] / parts_expected * 100, 2)
        }), 200
    except Exception as e:
        logger.error(f"Chunk upload error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/chunk/status', methods=['GET'])
def chunk_status():
    """Return status of a chunked upload session."""
    try:
        upload_id = request.args.get('upload_id')
        if not upload_id:
            return jsonify({'error': 'Missing upload_id'}), 400
        manifest = current_app.redis_client.get_cache(f"upload:{upload_id}")
        if not manifest:
            return jsonify({'error': 'Upload session not found'}), 404
        parts_expected = int(manifest['parts_expected'])
        received = int(manifest['received'])
        return jsonify({
            'upload_id': upload_id,
            'received': received,
            'parts_expected': parts_expected,
            'progress': round(received / parts_expected * 100, 2),
            'map': manifest.get('parts', {})
        }), 200
    except Exception as e:
        logger.error(f"Chunk status error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/chunk/complete', methods=['POST'])
def chunk_complete():
    """Finalize an upload: stitch chunks, store file, write metadata."""
    try:
        data = request.get_json(force=True)
        upload_id = data.get('upload_id')
        file_checksum = data.get('file_checksum')  # optional
        download_limit = data.get('download_limit', DOWNLOAD_LIMIT)
        ttl_seconds = data.get('ttl_seconds', FILE_TTL_SECONDS)

        if not upload_id:
            return jsonify({'error': 'Missing upload_id'}), 400

        redis_client = current_app.redis_client
        # Acquire lock to avoid race
        if not redis_client.acquire_lock(f"upload:{upload_id}:lock", ttl=60, timeout=5):
            return jsonify({'error': 'Upload is being finalized elsewhere'}), 409

        try:
            manifest = redis_client.get_cache(f"upload:{upload_id}")
            if not manifest:
                return jsonify({'error': 'Upload session not found'}), 404

            parts_expected = int(manifest['parts_expected'])
            received = int(manifest['received'])
            if received != parts_expected:
                return jsonify({'error': 'Not all parts uploaded', 'received': received, 'expected': parts_expected}), 409

            # Determine storage node for final file
            db_session = current_app.db_session
            node_selector = NodeSelector(db_session)
            total_size = int(manifest['total_size'])
            primary_node = node_selector.select_primary_node(total_size)
            if not primary_node:
                return jsonify({'error': 'No available storage nodes'}), 503

            # Prepare final file path
            original_name = manifest['filename']
            ext = original_name.rsplit('.', 1)[1].lower() if '.' in original_name else ''
            file_id = generate_file_id()
            stored_filename = f"{file_id}.{ext}" if ext else file_id
            final_path = os.path.join(primary_node.path, stored_filename)
            os.makedirs(primary_node.path, exist_ok=True)

            # Stitch parts in order
            parts = manifest.get('parts', {})
            with open(final_path, 'wb') as out:
                for idx in range(1, parts_expected + 1):
                    pinfo = parts.get(str(idx))
                    if not pinfo:
                        return jsonify({'error': f'Missing part {idx}'}), 500
                    with open(pinfo['path'], 'rb') as pf:
                        shutil.copyfileobj(pf, out)

            # Verify final checksum if provided
            if file_checksum:
                calc = generate_checksum(final_path)
                if calc != file_checksum:
                    try:
                        os.remove(final_path)
                    except Exception:
                        pass
                    return jsonify({'error': 'Final checksum mismatch'}), 400

            # Replicate if needed
            replica_nodes = []
            if REPLICATION_ENABLED and REPLICATION_FACTOR > 1:
                replicas = node_selector.select_replica_nodes(primary_node, REPLICATION_FACTOR - 1, total_size)
                for rnode in replicas:
                    os.makedirs(rnode.path, exist_ok=True)
                    shutil.copyfile(final_path, os.path.join(rnode.path, stored_filename))
                    replica_nodes.append(rnode.node_id)

            # Write metadata to DB
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            checksum = generate_checksum(final_path)
            new_file = File(
                id=file_id,
                filename=stored_filename,
                original_name=original_name,
                file_size=total_size,
                mime_type=manifest['mime_type'],
                primary_node=primary_node.node_id,
                replica_nodes=json.dumps(replica_nodes),
                download_limit=download_limit,
                downloads_left=download_limit,
                expires_at=expires_at,
                checksum=checksum
            )
            db_session.add(new_file)

            # Update node stats
            primary_node.used_space += total_size
            primary_node.file_count += 1
            for rid in replica_nodes:
                rnode = node_selector.get_node_by_id(rid)
                if rnode:
                    rnode.used_space += total_size
                    rnode.file_count += 1

            db_session.commit()

            # Redis counter + cache
            redis_client.set_download_counter(file_id, download_limit, ttl_seconds)
            redis_client.set_cache(
                f"file_metadata:{file_id}",
                {
                    'file_id': file_id,
                    'original_name': original_name,
                    'file_size': total_size,
                    'mime_type': manifest['mime_type'],
                    'primary_node': primary_node.node_id,
                    'replica_nodes': replica_nodes,
                    'downloads_left': download_limit,
                    'expires_at': expires_at.isoformat()
                },
                ttl_seconds
            )

            # Cleanup temp parts
            try:
                shutil.rmtree(manifest['temp_dir'])
            except Exception:
                pass
            redis_client.delete_cache(f"upload:{upload_id}")

            return jsonify({
                'message': 'Upload completed',
                'file_id': file_id,
                'download_url': f"/api/download/{file_id}",
                'primary_node': primary_node.node_id,
                'replica_nodes': replica_nodes
            }), 201
        finally:
            redis_client.release_lock(f"upload:{upload_id}:lock")
    except Exception as e:
        logger.error(f"Chunk complete error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    Upload file endpoint
    Chương 5: UUID Identification
    Chương 7: Auto Replication
    
    Returns:
        JSON with file_id, download_url, metadata
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
            return jsonify({'error': f'File too large. Maximum size: {MAX_FILE_SIZE / (1024**2):.0f}MB'}), 413
        
        # Get optional parameters
        download_limit = request.form.get('download_limit', DOWNLOAD_LIMIT, type=int)
        ttl_seconds = request.form.get('ttl_seconds', FILE_TTL_SECONDS, type=int)
        
        # Generate UUID for file
        file_id = generate_file_id()
        
        # Get secure filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        stored_filename = f"{file_id}.{file_extension}" if file_extension else file_id
        
        # Detect MIME type (extensible design)
        mime_type, _ = mimetypes.guess_type(original_filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        logger.info(f"Uploading file: {original_filename} ({mime_type}) - Size: {file_size} bytes")
        
        # Calculate checksum (Chapter 7: Deduplication) - Use tempfile for cross-platform support
        file.seek(0)  # Reset file pointer
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"{file_id}_temp")
        try:
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(file_content)
            checksum = generate_checksum(temp_path)
            logger.info(f"Checksum calculated: {checksum}")
        except Exception as e:
            logger.error(f"Error calculating checksum: {e}")
            return jsonify({'error': f'Error processing file: {str(e)}'}), 500
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
        # Check for duplicate (by checksum)
        db_session = current_app.db_session
        existing_file = db_session.query(File).filter(File.checksum == checksum).first()
        if existing_file:
            logger.info(f"Duplicate file detected: {checksum}. Returning existing file_id: {existing_file.id}")
            return jsonify({
                'message': 'File already exists (duplicate detected)',
                'file_id': existing_file.id,
                'download_url': f"/api/download/{existing_file.id}",
                'duplicate': True
            }), 200
        
        # Select primary storage node (Chapter 7)
        node_selector = NodeSelector(db_session)
        primary_node = node_selector.select_primary_node(file_size)
        
        if not primary_node:
            return jsonify({'error': 'No available storage nodes'}), 503
        
        # Save file to primary node
        node_storage_path = primary_node.path
        os.makedirs(node_storage_path, exist_ok=True)
        file_path = os.path.join(node_storage_path, stored_filename)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        logger.info(f"File saved to primary node: {primary_node.node_id} at {file_path}")
        
        # Select replica nodes if replication enabled
        replica_nodes = []
        if REPLICATION_ENABLED:
            replica_nodes = node_selector.select_replica_nodes(
                primary_node=primary_node,
                count=REPLICATION_FACTOR - 1,  # -1 because primary counts as one
                file_size=file_size
            )
            
            # Save to replica nodes
            for replica_node in replica_nodes:
                replica_storage_path = replica_node.path
                os.makedirs(replica_storage_path, exist_ok=True)
                replica_file_path = os.path.join(replica_storage_path, stored_filename)
                
                with open(replica_file_path, 'wb') as f:
                    f.write(file_content)
                
                logger.info(f"File replicated to node: {replica_node.node_id}")
        
        # Create File record in database
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        replica_node_ids = [node.node_id for node in replica_nodes]
        
        new_file = File(
            id=file_id,
            filename=stored_filename,
            original_name=original_filename,
            file_size=file_size,
            mime_type=mime_type,
            primary_node=primary_node.node_id,
            replica_nodes=json.dumps(replica_node_ids),
            download_limit=download_limit,
            downloads_left=download_limit,
            expires_at=expires_at,
            checksum=checksum
        )
        
        db_session.add(new_file)
        
        # Update node statistics
        primary_node.used_space += file_size
        primary_node.file_count += 1
        primary_node.last_heartbeat = datetime.utcnow()
        
        for replica_node in replica_nodes:
            replica_node.used_space += file_size
            replica_node.file_count += 1
        
        db_session.commit()
        
        # Set download counter in Redis (Chapter 6: Caching)
        redis_client = current_app.redis_client
        redis_client.set_download_counter(file_id, download_limit, ttl_seconds)
        
        # Cache file metadata in Redis
        redis_client.set_cache(
            f"file_metadata:{file_id}",
            {
                'file_id': file_id,
                'original_name': original_filename,
                'file_size': file_size,
                'mime_type': mime_type,
                'primary_node': primary_node.node_id,
                'replica_nodes': replica_node_ids,
                'downloads_left': download_limit,
                'expires_at': expires_at.isoformat()
            },
            ttl_seconds
        )
        
        # Create async processing task (Chapter 3: Async Processing)
        # Only for images
        if mime_type.startswith('image/'):
            # Create compress task
            compress_task = Task(
                id=generate_task_id(),
                file_id=file_id,
                task_type='compress',
                status='pending'
            )
            db_session.add(compress_task)
            
            # Create thumbnail task
            thumbnail_task = Task(
                id=generate_task_id(),
                file_id=file_id,
                task_type='thumbnail',
                status='pending'
            )
            db_session.add(thumbnail_task)
            db_session.commit()
            
            # Push to RabbitMQ queue
            redis_client.push_queue('task_queue', {
                'task_id': compress_task.id,
                'file_id': file_id,
                'task_type': 'compress',
                'file_path': file_path,
                'node_id': primary_node.node_id
            })
            
            redis_client.push_queue('task_queue', {
                'task_id': thumbnail_task.id,
                'file_id': file_id,
                'task_type': 'thumbnail',
                'file_path': file_path,
                'node_id': primary_node.node_id
            })
            
            logger.info(f"Created async tasks for image processing: {file_id}")
        
        # Schedule auto-deletion task
        delete_task = Task(
            id=generate_task_id(),
            file_id=file_id,
            task_type='delete',
            status='pending'
        )
        db_session.add(delete_task)
        db_session.commit()
        
        # Push delete task with delay
        redis_client.push_queue('delete_queue', {
            'task_id': delete_task.id,
            'file_id': file_id,
            'scheduled_at': expires_at.isoformat(),
            'primary_node': primary_node.node_id,
            'replica_nodes': replica_node_ids,
            'filename': stored_filename
        })
        
        logger.info(f"File upload successful: {file_id}")
        
        return jsonify({
            'message': 'File uploaded successfully',
            'file_id': file_id,
            'download_url': f"/api/download/{file_id}",
            'original_name': original_filename,
            'file_size': file_size,
            'mime_type': mime_type,
            'download_limit': download_limit,
            'downloads_left': download_limit,
            'expires_at': expires_at.isoformat(),
            'storage': {
                'primary_node': primary_node.node_id,
                'replica_nodes': replica_node_ids,
                'replication_enabled': REPLICATION_ENABLED
            }
        }), 201
    
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
    """
    Download file endpoint
    Chương 6: Caching
    Chương 4: Distributed Locking
    
    Args:
        file_id: UUID of the file
    
    Returns:
        File stream or error
    """
    try:
        db_session = current_app.db_session
        redis_client = current_app.redis_client
        
        # Try to get metadata from cache first
        cached_metadata = redis_client.get_cache(f"file_metadata:{file_id}")
        
        if not cached_metadata:
            # Get from database
            file_record = db_session.query(File).filter(File.id == file_id).first()
            
            if not file_record:
                return jsonify({'error': 'File not found'}), 404
            
            # Check if expired
            if datetime.utcnow() > file_record.expires_at:
                return jsonify({'error': 'File has expired'}), 410
            
            # Check downloads left
            if file_record.downloads_left <= 0:
                return jsonify({'error': 'Download limit reached'}), 403
        else:
            # Use cached metadata
            logger.info(f"Using cached metadata for file: {file_id}")
            
            # Still need to check DB for accurate download count
            file_record = db_session.query(File).filter(File.id == file_id).first()
            if not file_record:
                return jsonify({'error': 'File not found'}), 404
        
        # Acquire distributed lock (Chapter 4: Distributed Locking)
        lock_key = f"download_lock:{file_id}"
        if not redis_client.acquire_lock(lock_key, ttl=10, timeout=5):
            return jsonify({'error': 'File is being accessed by another request'}), 429
        
        try:
            # Decrement download counter
            downloads_left = redis_client.decrement_counter(file_id)
            
            if downloads_left is None or downloads_left < 0:
                redis_client.release_lock(lock_key)
                return jsonify({'error': 'Download limit reached'}), 403
            
            # Update database
            file_record.downloads_left = downloads_left
            db_session.commit()
            
            # Try to get file from primary node
            node_selector = NodeSelector(db_session)
            primary_node = node_selector.get_node_by_id(file_record.primary_node)
            
            if primary_node:
                file_path = os.path.join(primary_node.path, file_record.filename)
                
                if os.path.exists(file_path):
                    logger.info(f"Serving file from primary node: {primary_node.node_id}")
                    redis_client.release_lock(lock_key)
                    
                    return send_file(
                        file_path,
                        as_attachment=True,
                        download_name=file_record.original_name,
                        mimetype=file_record.mime_type
                    )
            
            # Failover: Try replica nodes (Chapter 7: Fault Tolerance)
            replica_nodes = json.loads(file_record.replica_nodes)
            for replica_node_id in replica_nodes:
                replica_node = node_selector.get_node_by_id(replica_node_id)
                if replica_node:
                    file_path = os.path.join(replica_node.path, file_record.filename)
                    
                    if os.path.exists(file_path):
                        logger.warning(f"Failover: Serving file from replica node: {replica_node_id}")
                        redis_client.release_lock(lock_key)
                        
                        return send_file(
                            file_path,
                            as_attachment=True,
                            download_name=file_record.original_name,
                            mimetype=file_record.mime_type
                        )
            
            # File not found on any node
            redis_client.release_lock(lock_key)
            logger.error(f"File {file_id} not found on any storage node")
            return jsonify({'error': 'File not found on storage nodes'}), 500
        
        finally:
            # Always release lock
            if redis_client.is_locked(lock_key):
                redis_client.release_lock(lock_key)
    
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error during download'}), 500


@api_bp.route('/files/<file_id>', methods=['GET'])
def get_file_info(file_id: str):
    """
    Get file metadata
    
    Args:
        file_id: UUID of the file
    
    Returns:
        JSON with file metadata
    """
    try:
        redis_client = current_app.redis_client
        
        # Try cache first
        cached_metadata = redis_client.get_cache(f"file_metadata:{file_id}")
        if cached_metadata:
            logger.info(f"Returning cached metadata for file: {file_id}")
            return jsonify(cached_metadata), 200
        
        # Get from database
        db_session = current_app.db_session
        file_record = db_session.query(File).filter(File.id == file_id).first()
        
        if not file_record:
            return jsonify({'error': 'File not found'}), 404
        
        # Build basic metadata
        metadata = {
            'file_id': file_record.id,
            'original_name': file_record.original_name,
            'file_size': file_record.file_size,
            'mime_type': file_record.mime_type,
            'primary_node': file_record.primary_node,
            'replica_nodes': json.loads(file_record.replica_nodes),
            'download_limit': file_record.download_limit,
            'downloads_left': file_record.downloads_left,
            'created_at': file_record.created_at.isoformat(),
            'expires_at': file_record.expires_at.isoformat(),
            'checksum': file_record.checksum,
            'is_compressed': file_record.is_compressed,
            'has_thumbnail': file_record.has_thumbnail
        }

        # Enrich with image dimensions and color_hex
        try:
            db_session = current_app.db_session
            node_selector = NodeSelector(db_session)
            check_nodes = [file_record.primary_node] + json.loads(file_record.replica_nodes)
            img_info = None
            color_hex = None
            for nid in check_nodes:
                node = node_selector.get_node_by_id(nid)
                if node:
                    fpath = os.path.join(node.path, file_record.filename)
                    if os.path.exists(fpath):
                        img_info = ImageProcessor.get_image_info(fpath)
                        color_hex = ImageProcessor.dominant_color_hex(fpath)
                        break
            if img_info:
                metadata['width'] = img_info.get('width')
                metadata['height'] = img_info.get('height')
            if color_hex:
                metadata['color_hex'] = color_hex
        except Exception:
            pass
        
        return jsonify(metadata), 200
    
    except Exception as e:
        logger.error(f"Get file info error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/files', methods=['GET'])
def list_files():
    """Return recent files with minimal metadata for gallery (masonry)."""
    try:
        db_session = current_app.db_session
        # Simple: get latest 50 files
        files = db_session.query(File).order_by(File.created_at.desc()).limit(50).all()
        node_selector = NodeSelector(db_session)
        result = []
        for fr in files:
            item = {
                'file_id': fr.id,
                'original_name': fr.original_name,
                'file_size': fr.file_size,
                'mime_type': fr.mime_type,
                'is_compressed': fr.is_compressed,
                'has_thumbnail': fr.has_thumbnail,
                'primary_node': fr.primary_node,
                'replica_nodes': json.loads(fr.replica_nodes),
                'created_at': fr.created_at.isoformat(),
                'download_url': f"/api/download/{fr.id}"
            }
            # Try get dimensions and color
            try:
                check_nodes = [fr.primary_node] + json.loads(fr.replica_nodes)
                for nid in check_nodes:
                    node = node_selector.get_node_by_id(nid)
                    if node:
                        fpath = os.path.join(node.path, fr.filename)
                        if os.path.exists(fpath):
                            info = ImageProcessor.get_image_info(fpath)
                            if info:
                                item['width'] = info.get('width')
                                item['height'] = info.get('height')
                            ch = ImageProcessor.dominant_color_hex(fpath)
                            if ch:
                                item['color_hex'] = ch
                            break
            except Exception:
                pass
            result.append(item)

        return jsonify({'count': len(result), 'files': result}), 200
    except Exception as e:
        logger.error(f"List files error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/nodes', methods=['GET'])
def get_nodes():
    """
    Get all storage nodes status
    
    Returns:
        JSON with list of nodes and their status
    """
    try:
        db_session = current_app.db_session
        nodes = db_session.query(StorageNode).all()
        
        node_list = []
        for node in nodes:
            node_list.append({
                'node_id': node.node_id,
                'host': node.host,
                'port': node.port,
                'is_online': node.is_online,
                'total_space_gb': round(node.total_space / (1024**3), 2),
                'used_space_gb': round(node.used_space / (1024**3), 2),
                'available_space_gb': round((node.total_space - node.used_space) / (1024**3), 2),
                'file_count': node.file_count,
                'last_heartbeat': node.last_heartbeat.isoformat() if node.last_heartbeat else None,
                'error_count': node.error_count
            })
        
        return jsonify({
            'total_nodes': len(node_list),
            'nodes': node_list
        }), 200
    
    except Exception as e:
        logger.error(f"Get nodes error: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
