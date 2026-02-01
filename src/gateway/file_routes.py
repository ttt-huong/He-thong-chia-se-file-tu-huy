"""
File Management Routes - Upload, Download, List, Delete with User Permissions
"""

from flask import Blueprint, request, jsonify, send_file
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import logging
from datetime import datetime, timedelta
import uuid

from src.middleware.auth_models import Base, User, File, FileAccessLog
from src.middleware.jwt_auth import jwt_required, get_current_user_id
from src.utils.file_permissions import FilePermissionManager, get_user_files, get_public_files, toggle_file_privacy

# Setup
file_bp = Blueprint('files', __name__)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres_secure_pass@postgres-master:5432/fileshare')
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Storage nodes configuration
STORAGE_NODES = {
    'node1': os.getenv('NODE1_URL', 'http://storage-node1:8000'),
    'node2': os.getenv('NODE2_URL', 'http://storage-node2:8000'),
    'node3': os.getenv('NODE3_URL', 'http://storage-node3:8000')
}


def select_storage_node():
    """Simple round-robin node selection"""
    import random
    return random.choice(list(STORAGE_NODES.keys()))


@file_bp.route('/upload', methods=['POST'])
@jwt_required
def upload_file():
    """
    Upload file - Owner can upload files
    
    Request:
    - file: The file to upload (multipart/form-data)
    - is_public: (optional) true/false - default false (private)
    
    Returns:
        File metadata with file_id
    """
    try:
        user_id = get_current_user_id()
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        is_public = request.form.get('is_public', 'false').lower() == 'true'
        
        session = Session()
        try:
            # Verify user exists
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            storage_node = select_storage_node()
            
            # Create file record in database
            new_file = File(
                id=file_id,  # Use UUID directly as id (TEXT)
                filename=file.filename,
                original_name=file.filename,
                file_size=len(file.read()),
                mime_type=file.content_type or 'unknown',
                file_type=file.content_type or 'unknown',
                user_id=user_id,
                is_public=is_public,
                primary_node=storage_node,
                storage_node=storage_node,
                file_path=f'/{file_id}/{file.filename}',
                checksum='',
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            file.seek(0)  # Reset file pointer
            
            session.add(new_file)
            session.commit()
            
            # Log the upload action
            log_entry = FileAccessLog(
                user_id=user_id,
                file_id=new_file.id,
                action='upload',
                ip_address=request.remote_addr
            )
            session.add(log_entry)
            session.commit()
            
            return jsonify({
                'message': 'File uploaded successfully',
                'file': new_file.to_dict(),
                'storage_node': storage_node
            }), 201
        
        except Exception as e:
            session.rollback()
            logger.error(f'Upload error: {str(e)}')
            return jsonify({'error': 'Upload failed'}), 500
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f'Unexpected error in upload: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@file_bp.route('', methods=['GET'])
@jwt_required
def list_files():
    """
    List files - Show user's files + public files
    
    Query params:
    - show_all: 'true' to show only user's files, 'false' to include public
    - limit: Number of files (default 50)
    - offset: Pagination offset (default 0)
    
    Returns:
        List of accessible files
    """
    try:
        user_id = get_current_user_id()
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        
        session = Session()
        try:
            files_list = []
            
            # Get user's own files
            user_files = get_user_files(session, user_id, include_deleted=False)
            files_list.extend(user_files)
            
            # Get public files if not filtering
            if not show_all:
                public_files = get_public_files(session, limit=limit-len(files_list), offset=offset)
                files_list.extend(public_files)
            
            # Convert to dict
            files_data = [f.to_dict() for f in files_list]
            
            return jsonify({
                'message': 'Files retrieved successfully',
                'count': len(files_data),
                'files': files_data
            }), 200
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f'List files error: {str(e)}')
        return jsonify({'error': 'Failed to retrieve files'}), 500


@file_bp.route('/<file_id>', methods=['GET'])
@jwt_required
def download_file(file_id):
    """
    Download file - Check permissions before allowing download
    
    Permissions:
    - Owner can always download
    - Public files can be downloaded by anyone
    
    Returns:
        File content or error
    """
    try:
        user_id = get_current_user_id()
        
        session = Session()
        try:
            file = session.query(File).filter(File.file_id == file_id).first()
            
            if not file:
                return jsonify({'error': 'File not found'}), 404
            
            # Check permissions
            has_access, message = FilePermissionManager.check_file_access(
                file, user_id, action='download'
            )
            
            if not has_access:
                return jsonify({'error': message}), 403
            
            # Log the download
            log_entry = FileAccessLog(
                user_id=user_id,
                file_id=file.id,
                action='download',
                ip_address=request.remote_addr
            )
            session.add(log_entry)
            
            # Increment download count
            file.download_count += 1
            session.commit()
            
            # Return file metadata (actual file transfer would be handled by storage nodes)
            return jsonify({
                'file': file.to_dict(include_path=True),
                'storage_node': file.storage_node,
                'download_url': f"{STORAGE_NODES.get(file.storage_node, '')}/download/{file_id}"
            }), 200
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f'Download error: {str(e)}')
        return jsonify({'error': 'Download failed'}), 500


@file_bp.route('/<file_id>', methods=['DELETE'])
@jwt_required
def delete_file(file_id):
    """
    Delete file - Only owner can delete
    
    Returns:
        Success message
    """
    try:
        user_id = get_current_user_id()
        
        session = Session()
        try:
            file = session.query(File).filter(File.file_id == file_id).first()
            
            if not file:
                return jsonify({'error': 'File not found'}), 404
            
            # Check permissions
            if not FilePermissionManager.can_delete_file(file, user_id):
                return jsonify({'error': 'Access denied: Only file owner can delete'}), 403
            
            # Soft delete
            file.deleted = True
            file.deleted_at = datetime.utcnow()
            
            # Log the deletion
            log_entry = FileAccessLog(
                user_id=user_id,
                file_id=file.id,
                action='delete',
                ip_address=request.remote_addr
            )
            session.add(log_entry)
            session.commit()
            
            return jsonify({
                'message': 'File deleted successfully',
                'file_id': file_id
            }), 200
        
        except Exception as e:
            session.rollback()
            logger.error(f'Delete error: {str(e)}')
            return jsonify({'error': 'Delete failed'}), 500
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f'Unexpected error in delete: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@file_bp.route('/<file_id>/permissions', methods=['PUT'])
@jwt_required
def update_file_permissions(file_id):
    """
    Update file permissions - Only owner can change
    
    Request body:
    {
        "is_public": true/false
    }
    
    Returns:
        Updated file metadata
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json()
        
        if not data or 'is_public' not in data:
            return jsonify({'error': 'is_public field is required'}), 400
        
        is_public = data['is_public']
        if not isinstance(is_public, bool):
            return jsonify({'error': 'is_public must be boolean'}), 400
        
        session = Session()
        try:
            file = session.query(File).filter(File.file_id == file_id).first()
            
            if not file:
                return jsonify({'error': 'File not found'}), 404
            
            # Check permissions
            if not FilePermissionManager.can_modify_permissions(file, user_id):
                return jsonify({'error': 'Access denied: Only file owner can modify permissions'}), 403
            
            # Update permissions
            file.is_public = is_public
            session.commit()
            
            status = 'public' if is_public else 'private'
            return jsonify({
                'message': f'File is now {status}',
                'file': file.to_dict()
            }), 200
        
        except Exception as e:
            session.rollback()
            logger.error(f'Permission update error: {str(e)}')
            return jsonify({'error': 'Failed to update permissions'}), 500
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f'Unexpected error in update_permissions: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@file_bp.route('/user/<int:user_id>/files', methods=['GET'])
def get_user_public_files(user_id):
    """
    Get public files from a specific user
    
    Returns:
        List of public files
    """
    try:
        session = Session()
        try:
            # Verify user exists
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Get user's public files
            public_files = session.query(File).filter(
                (File.user_id == user_id) & 
                (File.is_public == True) & 
                (File.deleted == False)
            ).all()
            
            return jsonify({
                'user': user.to_dict(),
                'file_count': len(public_files),
                'files': [f.to_dict() for f in public_files]
            }), 200
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f'Get user files error: {str(e)}')
        return jsonify({'error': 'Failed to retrieve user files'}), 500


@file_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'File service is running'}), 200
