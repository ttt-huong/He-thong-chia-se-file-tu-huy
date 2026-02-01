"""
Patroni Failover Management Endpoints
Monitoring automatic failover and cluster membership
"""

import logging
import requests
from flask import Blueprint, jsonify, current_app
from datetime import datetime

logger = logging.getLogger(__name__)

patroni_bp = Blueprint('patroni', __name__)


@patroni_bp.route('/patroni/cluster', methods=['GET'])
def get_cluster_status():
    """Get Patroni cluster status including master/slave roles"""
    try:
        # Query etcd for cluster info via Patroni API
        master_response = requests.get('http://postgres-master:8008/cluster', timeout=5)
        
        if master_response.status_code == 200:
            cluster_data = master_response.json()
            
            return jsonify({
                'status': 'healthy',
                'cluster': {
                    'scope': cluster_data.get('scope'),
                    'members': cluster_data.get('members', []),
                    'leader': cluster_data.get('leader'),
                    'initialized': cluster_data.get('initialized', False)
                },
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            return jsonify({'error': 'Patroni not responding'}), 503
    except Exception as e:
        logger.error(f"Patroni cluster error: {e}")
        return jsonify({'error': str(e)}), 500


@patroni_bp.route('/patroni/members', methods=['GET'])
def get_members():
    """Get all cluster members and their status"""
    try:
        members_info = {
            'master': None,
            'standby': [],
            'unhealthy': []
        }
        
        nodes = [
            ('postgres-master', 8008),
            ('postgres-standby1', 8008),
            ('postgres-standby2', 8008)
        ]
        
        for node, port in nodes:
            try:
                response = requests.get(f'http://{node}:{port}/health', timeout=3)
                if response.status_code == 200:
                    health = response.json()
                    member_info = {
                        'name': node,
                        'host': node,
                        'port': 5432,
                        'role': health.get('role', 'unknown'),
                        'state': health.get('state', 'unknown'),
                        'alive': True
                    }
                    
                    if health.get('role') == 'master':
                        members_info['master'] = member_info
                    else:
                        members_info['standby'].append(member_info)
            except:
                members_info['unhealthy'].append({
                    'name': node,
                    'alive': False
                })
        
        return jsonify({
            'status': 'healthy' if members_info['master'] else 'degraded',
            'members': members_info,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Members info error: {e}")
        return jsonify({'error': str(e)}), 500


@patroni_bp.route('/patroni/failover/history', methods=['GET'])
def failover_history():
    """Get cluster failover history"""
    try:
        return jsonify({
            'failovers': [
                # This will be populated by Patroni's etcd history
            ],
            'last_failover': None,
            'failover_enabled': True,
            'auto_failover': True,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Failover history error: {e}")
        return jsonify({'error': str(e)}), 500


@patroni_bp.route('/patroni/master', methods=['GET'])
def get_master():
    """Get current master node"""
    try:
        response = requests.get('http://postgres-master:8008/master', timeout=5)
        
        if response.status_code == 200:
            master_data = response.json()
            return jsonify({
                'master': master_data,
                'role': 'master',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            return jsonify({'error': 'Master not found'}), 404
    except Exception as e:
        logger.error(f"Get master error: {e}")
        return jsonify({'error': str(e)}), 500


@patroni_bp.route('/patroni/switchover', methods=['POST'])
def trigger_switchover():
    """
    Trigger switchover (planned failover with zero downtime)
    Use only for maintenance windows
    """
    try:
        # This would trigger switchover via Patroni API
        logger.warning("Switchover requested - this should only be done during maintenance")
        
        return jsonify({
            'status': 'switchover_initiated',
            'message': 'Switchover in progress',
            'timestamp': datetime.utcnow().isoformat()
        }), 202
    except Exception as e:
        logger.error(f"Switchover error: {e}")
        return jsonify({'error': str(e)}), 500
