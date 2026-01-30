"""
Storage Node API - Independent Storage Service
Mỗi node chạy như 1 service riêng biệt với API riêng
Có thể deploy trên máy khác nhau hoặc Docker containers
"""

import os
import logging
from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from datetime import datetime

# Configuration
NODE_ID = os.getenv('NODE_ID', 'node1')
STORAGE_PATH = os.getenv('STORAGE_PATH', '/data')
PORT = int(os.getenv('PORT', 8000))

# Create Flask app
app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure storage directory exists
os.makedirs(STORAGE_PATH, exist_ok=True)

logger.info(f"Storage Node {NODE_ID} initialized at {STORAGE_PATH}")


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    Returns node status and available space
    """
    try:
        # Calculate storage stats
        total, used, free = os.statvfs(STORAGE_PATH).f_blocks, \
                           os.statvfs(STORAGE_PATH).f_blocks - os.statvfs(STORAGE_PATH).f_bavail, \
                           os.statvfs(STORAGE_PATH).f_bavail
        
        file_count = len([f for f in os.listdir(STORAGE_PATH) if os.path.isfile(os.path.join(STORAGE_PATH, f))])
        
        return jsonify({
            'node_id': NODE_ID,
            'status': 'online',
            'storage_path': STORAGE_PATH,
            'file_count': file_count,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload():
    """
    Upload file to this storage node
    
    Expected: multipart/form-data with 'file' field
    Returns: filename and size
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Get filename from form or use original
        filename = request.form.get('filename', secure_filename(file.filename))
        filepath = os.path.join(STORAGE_PATH, filename)
        
        # Save file
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        logger.info(f"File uploaded: {filename} ({file_size} bytes) to {NODE_ID}")
        
        return jsonify({
            'status': 'success',
            'node_id': NODE_ID,
            'filename': filename,
            'size': file_size,
            'path': filepath
        }), 200
        
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    """
    Download file from this storage node
    
    Args:
        filename: Name of file to download
    
    Returns: File content
    """
    try:
        filepath = os.path.join(STORAGE_PATH, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        logger.info(f"File downloaded: {filename} from {NODE_ID}")
        return send_from_directory(STORAGE_PATH, filename)
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/delete/<filename>', methods=['DELETE'])
def delete(filename):
    """
    Delete file from this storage node
    
    Args:
        filename: Name of file to delete
    
    Returns: Success status
    """
    try:
        filepath = os.path.join(STORAGE_PATH, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        os.remove(filepath)
        logger.info(f"File deleted: {filename} from {NODE_ID}")
        
        return jsonify({
            'status': 'success',
            'node_id': NODE_ID,
            'filename': filename,
            'action': 'deleted'
        }), 200
        
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/files', methods=['GET'])
def list_files():
    """
    List all files on this storage node
    
    Returns: Array of file info
    """
    try:
        files = []
        for filename in os.listdir(STORAGE_PATH):
            filepath = os.path.join(STORAGE_PATH, filename)
            if os.path.isfile(filepath):
                files.append({
                    'filename': filename,
                    'size': os.path.getsize(filepath),
                    'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                })
        
        return jsonify({
            'node_id': NODE_ID,
            'file_count': len(files),
            'files': files
        }), 200
        
    except Exception as e:
        logger.error(f"List files error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def stats():
    """
    Get storage statistics
    
    Returns: Storage usage info
    """
    try:
        total_size = 0
        file_count = 0
        
        for filename in os.listdir(STORAGE_PATH):
            filepath = os.path.join(STORAGE_PATH, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
                file_count += 1
        
        return jsonify({
            'node_id': NODE_ID,
            'file_count': file_count,
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2)
        }), 200
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    logger.info(f"Starting Storage Node {NODE_ID} on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
