"""
Database Monitoring Endpoints
Theo dõi replication status, lag, và failover events
"""

import logging
from flask import Blueprint, jsonify, current_app
from datetime import datetime

logger = logging.getLogger(__name__)

db_bp = Blueprint('database', __name__)


@db_bp.route('/db/health', methods=['GET'])
def db_health():
    """Get database and replication health status"""
    try:
        db_manager = getattr(current_app, 'db_manager', None)
        if not db_manager:
            return jsonify({'error': 'Database manager not initialized'}), 500
        
        status = db_manager.get_replication_status()
        
        return jsonify({
            'status': 'healthy' if status.get('status') != 'error' else 'error',
            'database': {
                'type': status.get('db_type', 'unknown'),
                'master': status.get('master'),
                'replica': status.get('replica')
            },
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"DB health check error: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500


@db_bp.route('/db/replication/lag', methods=['GET'])
def replication_lag():
    """Get replication lag between master and slave"""
    try:
        db_manager = getattr(current_app, 'db_manager', None)
        if not db_manager:
            return jsonify({'error': 'Database manager not initialized'}), 500
        
        # Get current LAG (only for PostgreSQL)
        status = db_manager.get_replication_status()
        
        if status.get('db_type') != 'postgresql':
            return jsonify({
                'status': 'N/A',
                'message': 'Database is SQLite, not PostgreSQL'
            }), 200
        
        # Calculate lag from LSN positions
        lag_info = {
            'master_lsn': status.get('master', {}).get('wal_lsn'),
            'replica_lsn': status.get('replica', {}).get('wal_replay_lsn'),
            'receive_lsn': status.get('replica', {}).get('wal_receive_lsn'),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify(lag_info), 200
    except Exception as e:
        logger.error(f"Replication lag error: {e}")
        return jsonify({'error': str(e)}), 500


@db_bp.route('/db/failover/status', methods=['GET'])
def failover_status():
    """Get failover status and history"""
    try:
        return jsonify({
            'failover_enabled': True,
            'auto_failover': False,  # Will be true after Patroni setup
            'last_failover': None,
            'failover_method': 'manual (Patroni in Phase 4.1)',
            'recovery_time_objective': '< 5 minutes',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Failover status error: {e}")
        return jsonify({'error': str(e)}), 500


@db_bp.route('/db/connections', methods=['GET'])
def db_connections():
    """Get database connection pool statistics"""
    try:
        db_manager = getattr(current_app, 'db_manager', None)
        if not db_manager:
            return jsonify({'error': 'Database manager not initialized'}), 500
        
        if db_manager.db_type == 'postgresql':
            connections_info = {
                'write_pool': {
                    'min': 1,
                    'max': 10,
                    'type': 'PostgreSQL Master'
                },
                'read_pool': {
                    'min': 1,
                    'max': 20,
                    'type': 'PostgreSQL Standby'
                }
            }
        else:
            connections_info = {
                'type': 'SQLite',
                'max_connections': 'unlimited'
            }
        
        return jsonify({
            'db_type': db_manager.db_type,
            'connections': connections_info,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Connections info error: {e}")
        return jsonify({'error': str(e)}), 500
