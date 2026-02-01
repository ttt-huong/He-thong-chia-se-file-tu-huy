"""
PgBouncer Connection Pool Monitoring
Provides endpoints to monitor PgBouncer connection pooling statistics
"""

import socket
import os
from typing import Dict, List, Any

def get_pgbouncer_stats() -> Dict[str, Any]:
    """
    Query PgBouncer admin console for statistics
    Connects to PgBouncer admin port (6431) and retrieves pool statistics
    """
    try:
        pgbouncer_host = os.getenv("PGBOUNCER_HOST", "pgbouncer")
        pgbouncer_admin_port = int(os.getenv("PGBOUNCER_ADMIN_PORT", "6431"))
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((pgbouncer_host, pgbouncer_admin_port))
        
        # Query STATS command
        sock.sendall(b"SHOW STATS;\n")
        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        
        sock.close()
        
        # Parse stats response
        lines = response.decode('utf-8', errors='ignore').split('\n')
        stats = []
        for line in lines:
            if line.strip() and not line.startswith(' '):
                stats.append(line)
        
        return {
            "status": "ok",
            "stats": stats
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def get_pgbouncer_pools() -> Dict[str, Any]:
    """
    Get PgBouncer pool information
    """
    try:
        pgbouncer_host = os.getenv("PGBOUNCER_HOST", "pgbouncer")
        pgbouncer_admin_port = int(os.getenv("PGBOUNCER_ADMIN_PORT", "6431"))
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((pgbouncer_host, pgbouncer_admin_port))
        
        # Query POOLS command
        sock.sendall(b"SHOW POOLS;\n")
        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        
        sock.close()
        
        lines = response.decode('utf-8', errors='ignore').split('\n')
        pools = []
        for line in lines:
            if line.strip() and not line.startswith(' '):
                pools.append(line)
        
        return {
            "status": "ok",
            "pools": pools
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def get_pgbouncer_clients() -> Dict[str, Any]:
    """
    Get connected clients information
    """
    try:
        pgbouncer_host = os.getenv("PGBOUNCER_HOST", "pgbouncer")
        pgbouncer_admin_port = int(os.getenv("PGBOUNCER_ADMIN_PORT", "6431"))
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((pgbouncer_host, pgbouncer_admin_port))
        
        # Query CLIENTS command
        sock.sendall(b"SHOW CLIENTS;\n")
        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        
        sock.close()
        
        lines = response.decode('utf-8', errors='ignore').split('\n')
        clients = []
        for line in lines:
            if line.strip() and not line.startswith(' '):
                clients.append(line)
        
        return {
            "status": "ok",
            "clients_count": len(clients) - 1,  # Exclude header
            "clients": clients
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def get_pgbouncer_config() -> Dict[str, Any]:
    """
    Get PgBouncer configuration settings
    """
    try:
        pgbouncer_host = os.getenv("PGBOUNCER_HOST", "pgbouncer")
        pgbouncer_admin_port = int(os.getenv("PGBOUNCER_ADMIN_PORT", "6431"))
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((pgbouncer_host, pgbouncer_admin_port))
        
        # Query CONFIG command
        sock.sendall(b"SHOW CONFIG;\n")
        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break
        
        sock.close()
        
        lines = response.decode('utf-8', errors='ignore').split('\n')
        config = {}
        for line in lines:
            if '=' in line and not line.startswith(' '):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
        
        return {
            "status": "ok",
            "config": config
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def get_pool_summary() -> Dict[str, Any]:
    """
    Get summary of connection pool metrics
    """
    try:
        stats = get_pgbouncer_stats()
        pools = get_pgbouncer_pools()
        clients = get_pgbouncer_clients()
        config = get_pgbouncer_config()
        
        return {
            "status": "ok",
            "pool_mode": config.get("config", {}).get("pool_mode", "unknown"),
            "max_client_conn": config.get("config", {}).get("max_client_conn", "unknown"),
            "default_pool_size": config.get("config", {}).get("default_pool_size", "unknown"),
            "reserve_pool_size": config.get("config", {}).get("reserve_pool_size", "unknown"),
            "connected_clients": clients.get("clients_count", 0),
            "stats": stats.get("stats", []),
            "pools": pools.get("pools", [])
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
