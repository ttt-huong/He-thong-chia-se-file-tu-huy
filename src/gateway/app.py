"""
Gateway API - Flask Application Factory
Chương 8: Load Balancing & High Availability
Chương 4: Distributed Locking (Redis)
"""

import os
from flask import Flask, jsonify
from flask_cors import CORS
import logging
from datetime import datetime

# Import configuration and middleware
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.config.settings import (
    DEBUG as FLASK_DEBUG,
    HOST as FLASK_HOST,
    PORT as FLASK_PORT,
    DATABASE_URL, LOGS_DIR, LOG_LEVEL,
    RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_USER, RABBITMQ_PASSWORD
)
from src.middleware.models import get_db, get_session
from src.middleware.redis_client import get_redis_client

# Configure logging
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'gateway.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def create_app():
    """
    Application Factory Pattern
    Khởi tạo Flask app với tất cả dependencies
    """
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
    
    # Enable CORS for all routes
    CORS(app)
    
    # Initialize database
    try:
        app.db = get_db()
        app.db_session = get_session()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Initialize Redis client
    try:
        redis_client = get_redis_client()
        if redis_client.health_check():
            app.redis_client = redis_client
            logger.info("Redis client initialized successfully")
        else:
            raise Exception("Redis health check failed")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise
    
    # Register blueprints
    from src.gateway.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Health check endpoint (no prefix)
    @app.route('/health', methods=['GET'])
    def health():
        """System health check endpoint"""
        try:
            # Check database
            db_healthy = app.db is not None
            
            # Check Redis
            redis_healthy = app.redis_client.health_check()

            # Check RabbitMQ (simple connect)
            rabbitmq_healthy = False
            try:
                import pika
                credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
                params = pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials, blocked_connection_timeout=2)
                connection = pika.BlockingConnection(params)
                rabbitmq_healthy = connection.is_open
                connection.close()
            except Exception:
                rabbitmq_healthy = False
            
            # Overall health
            healthy = db_healthy and redis_healthy and rabbitmq_healthy
            
            return jsonify({
                'status': 'healthy' if healthy else 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'components': {
                    'database': 'ok' if db_healthy else 'error',
                    'redis': 'ok' if redis_healthy else 'error',
                    'rabbitmq': 'ok' if rabbitmq_healthy else 'error'
                }
            }), 200 if healthy else 503
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 503
    
    # Root endpoint
    @app.route('/', methods=['GET'])
    def root():
        """API information endpoint"""
        return jsonify({
            'service': 'Distributed Image Storage System',
            'version': '2.0.0',
            'description': 'Hệ thống lưu trữ ảnh phân tán có khả năng tự phục hồi và xử lý hậu kỳ bất đồng bộ',
            'endpoints': {
                'health': '/health',
                'upload': '/api/upload',
                'download': '/api/download/<file_id>',
                'file_info': '/api/files/<file_id>',
                'nodes': '/api/nodes'
            },
            'features': [
                'UUID Identification (Chapter 5)',
                'Distributed Locking (Chapter 4)',
                'Auto Replication (Chapter 7)',
                'Async Processing (Chapter 3)',
                'Load Balancing (Chapter 8)',
                'Caching (Chapter 6)'
            ]
        }), 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        return jsonify({'error': 'File too large. Maximum size is 100MB'}), 413
    
    logger.info(f"Gateway application created successfully")
    return app


if __name__ == '__main__':
    app = create_app()
    logger.info(f"Starting Gateway API on {FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
