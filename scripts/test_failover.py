"""
Patroni Failover Testing - Cluster Health & Failover Scenarios
Phase 4.4: Test automatic failover trong PostgreSQL cluster
"""

import os
import sys
import time
import requests
import psycopg2
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """Vai trò node trong cluster"""
    MASTER = "master"
    STANDBY = "standby"
    UNKNOWN = "unknown"


class PatroniCluster:
    """Quản lý Patroni cluster và failover testing"""
    
    def __init__(self):
        # Patroni API endpoints
        self.nodes = {
            "master": {
                "host": os.getenv("PATRONI_MASTER_HOST", "localhost"),
                "port": int(os.getenv("PATRONI_MASTER_PORT", 8008)),
                "pg_port": 5432,
                "name": "postgres-master"
            },
            "standby1": {
                "host": os.getenv("PATRONI_STANDBY1_HOST", "localhost"),
                "port": int(os.getenv("PATRONI_STANDBY1_PORT", 8009)),
                "pg_port": 5433,
                "name": "postgres-standby1"
            },
            "standby2": {
                "host": os.getenv("PATRONI_STANDBY2_HOST", "localhost"),
                "port": int(os.getenv("PATRONI_STANDBY2_PORT", 8010)),
                "pg_port": 5434,
                "name": "postgres-standby2"
            }
        }
        
        # PostgreSQL connection info
        self.pg_user = os.getenv("POSTGRES_USER", "postgres")
        self.pg_password = os.getenv("POSTGRES_PASSWORD", "postgres_secure_pass")
        self.pg_db = os.getenv("POSTGRES_DB", "fileshare")
        
        # etcd info
        self.etcd_host = os.getenv("ETCD_HOST", "localhost")
        self.etcd_port = int(os.getenv("ETCD_PORT", 2379))
        
        self.test_results = []
    
    def get_patroni_health(self, node_key: str) -> Dict[str, Any]:
        """Lấy health status từ Patroni REST API"""
        try:
            node = self.nodes[node_key]
            url = f"http://{node['host']}:{node['port']}/health"
            response = requests.get(url, timeout=5)
            return {
                "status": "ok",
                "node": node_key,
                "http_status": response.status_code,
                "data": response.json() if response.status_code == 200 else {}
            }
        except Exception as e:
            return {
                "status": "error",
                "node": node_key,
                "error": str(e)
            }
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Lấy cluster status từ Patroni"""
        try:
            # Query master cluster endpoint
            node = self.nodes["master"]
            url = f"http://{node['host']}:{node['port']}/cluster"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "ok",
                    "cluster": data.get("cluster", "unknown"),
                    "members": len(data.get("members", [])),
                    "leader": data.get("leader", {}).get("name", "unknown"),
                    "data": data
                }
            else:
                return {
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_node_role(self, node_key: str) -> NodeRole:
        """Xác định vai trò của node (master hay standby)"""
        try:
            node = self.nodes[node_key]
            url = f"http://{node['host']}:{node['port']}/master"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                return NodeRole.MASTER
            elif response.status_code == 503:
                return NodeRole.STANDBY
            else:
                return NodeRole.UNKNOWN
        except Exception:
            return NodeRole.UNKNOWN
    
    def check_postgres_connection(self, node_key: str) -> Tuple[bool, str]:
        """Kiểm tra kết nối PostgreSQL trực tiếp"""
        try:
            node = self.nodes[node_key]
            conn = psycopg2.connect(
                host=node["host"],
                port=node["pg_port"],
                user=self.pg_user,
                password=self.pg_password,
                database=self.pg_db,
                connect_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            conn.close()
            return True, version
        except Exception as e:
            return False, str(e)
    
    def get_replication_lag(self, master_key: str = "master") -> Dict[str, Any]:
        """Lấy replication lag giữa master và standby"""
        try:
            # Kết nối master
            master_node = self.nodes[master_key]
            master_conn = psycopg2.connect(
                host=master_node["host"],
                port=master_node["pg_port"],
                user=self.pg_user,
                password=self.pg_password,
                database=self.pg_db,
                connect_timeout=5
            )
            master_cursor = master_conn.cursor()
            master_cursor.execute("""
                SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')::text as master_lsn
            """)
            master_lsn = master_cursor.fetchone()[0]
            master_conn.close()
            
            # Kiểm tra lag trên standby
            lags = {}
            for standby_key in ["standby1", "standby2"]:
                try:
                    standby_node = self.nodes[standby_key]
                    standby_conn = psycopg2.connect(
                        host=standby_node["host"],
                        port=standby_node["pg_port"],
                        user=self.pg_user,
                        password=self.pg_password,
                        database=self.pg_db,
                        connect_timeout=5
                    )
                    standby_cursor = standby_conn.cursor()
                    standby_cursor.execute("""
                        SELECT pg_wal_lsn_diff(pg_last_wal_receive_lsn(), '0/0')::text as standby_lsn
                    """)
                    standby_lsn = standby_cursor.fetchone()[0]
                    standby_conn.close()
                    
                    lag_bytes = float(master_lsn) - float(standby_lsn)
                    lags[standby_key] = {
                        "lag_bytes": lag_bytes,
                        "lag_mb": lag_bytes / (1024 * 1024),
                        "is_healthy": lag_bytes < 1048576  # < 1MB
                    }
                except Exception as e:
                    lags[standby_key] = {"error": str(e)}
            
            return {
                "status": "ok",
                "master_lsn": master_lsn,
                "standby_lags": lags
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def test_cluster_health(self) -> Dict[str, Any]:
        """Test 1: Kiểm tra sức khỏe cluster"""
        logger.info("\n" + "="*60)
        logger.info("TEST 1: Cluster Health Check")
        logger.info("="*60)
        
        result = {
            "test": "cluster_health",
            "timestamp": datetime.now().isoformat(),
            "nodes": {},
            "overall_status": "unknown"
        }
        
        # Check each node
        for node_key in self.nodes.keys():
            logger.info(f"\nChecking {node_key}...")
            
            # Patroni health
            patroni_health = self.get_patroni_health(node_key)
            logger.info(f"  Patroni health: {patroni_health['status']}")
            
            # PostgreSQL connection
            pg_ok, pg_info = self.check_postgres_connection(node_key)
            logger.info(f"  PostgreSQL: {'✓' if pg_ok else '✗'}")
            if pg_ok:
                logger.info(f"    Version: {pg_info[:50]}...")
            else:
                logger.info(f"    Error: {pg_info}")
            
            # Node role
            role = self.get_node_role(node_key)
            logger.info(f"  Role: {role.value}")
            
            result["nodes"][node_key] = {
                "patroni": patroni_health,
                "postgres": {"connected": pg_ok, "info": pg_info},
                "role": role.value
            }
        
        # Cluster status
        cluster_status = self.get_cluster_status()
        logger.info(f"\nCluster Status:")
        logger.info(f"  Cluster: {cluster_status.get('cluster', 'unknown')}")
        logger.info(f"  Leader: {cluster_status.get('leader', 'unknown')}")
        logger.info(f"  Members: {cluster_status.get('members', 0)}")
        
        result["cluster_status"] = cluster_status
        result["overall_status"] = "healthy" if cluster_status.get("status") == "ok" else "degraded"
        
        self.test_results.append(result)
        return result
    
    def test_replication(self) -> Dict[str, Any]:
        """Test 2: Kiểm tra replication lag"""
        logger.info("\n" + "="*60)
        logger.info("TEST 2: Replication Lag Check")
        logger.info("="*60)
        
        result = {
            "test": "replication_lag",
            "timestamp": datetime.now().isoformat()
        }
        
        lag_info = self.get_replication_lag()
        result["replication"] = lag_info
        
        if lag_info.get("status") == "ok":
            logger.info(f"Master LSN: {lag_info['master_lsn']}")
            for standby_key, lag_data in lag_info.get("standby_lags", {}).items():
                if "error" not in lag_data:
                    status = "✓" if lag_data["is_healthy"] else "✗"
                    logger.info(f"{status} {standby_key}: {lag_data['lag_mb']:.2f}MB lag")
                else:
                    logger.info(f"✗ {standby_key}: {lag_data['error']}")
        else:
            logger.info(f"✗ Error: {lag_info.get('error', 'unknown')}")
        
        self.test_results.append(result)
        return result
    
    def test_write_read_consistency(self) -> Dict[str, Any]:
        """Test 3: Kiểm tra consistency giữa write và read"""
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Write-Read Consistency Test")
        logger.info("="*60)
        
        result = {
            "test": "write_read_consistency",
            "timestamp": datetime.now().isoformat(),
            "writes": 0,
            "reads": 0,
            "consistency_ok": False
        }
        
        try:
            # Write test data
            logger.info("Writing test data to master...")
            master_node = self.nodes["master"]
            master_conn = psycopg2.connect(
                host=master_node["host"],
                port=master_node["pg_port"],
                user=self.pg_user,
                password=self.pg_password,
                database=self.pg_db,
                connect_timeout=5
            )
            master_cursor = master_conn.cursor()
            
            # Create test table
            master_cursor.execute("""
                CREATE TABLE IF NOT EXISTS failover_test (
                    id SERIAL PRIMARY KEY,
                    test_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            master_conn.commit()
            
            # Insert test record
            test_value = f"test_{int(time.time())}"
            master_cursor.execute(
                "INSERT INTO failover_test (test_data) VALUES (%s) RETURNING id",
                (test_value,)
            )
            test_id = master_cursor.fetchone()[0]
            master_conn.commit()
            logger.info(f"✓ Wrote test record: {test_id}")
            result["writes"] = 1
            
            # Wait for replication
            logger.info("Waiting for replication...")
            time.sleep(2)
            
            # Read from standby
            logger.info("Reading from standby...")
            standby_node = self.nodes["standby1"]
            standby_conn = psycopg2.connect(
                host=standby_node["host"],
                port=standby_node["pg_port"],
                user=self.pg_user,
                password=self.pg_password,
                database=self.pg_db,
                connect_timeout=5
            )
            standby_cursor = standby_conn.cursor()
            standby_cursor.execute("SELECT test_data FROM failover_test WHERE id = %s", (test_id,))
            row = standby_cursor.fetchone()
            
            if row and row[0] == test_value:
                logger.info(f"✓ Read data from standby: {row[0]}")
                result["reads"] = 1
                result["consistency_ok"] = True
            else:
                logger.info(f"✗ Data not found or mismatch on standby")
                result["consistency_ok"] = False
            
            standby_conn.close()
            master_conn.close()
            
        except Exception as e:
            logger.info(f"✗ Error: {e}")
            result["consistency_ok"] = False
        
        self.test_results.append(result)
        return result
    
    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Chạy tất cả tests"""
        logger.info("\n" + "="*60)
        logger.info("PATRONI FAILOVER TEST SUITE")
        logger.info("="*60)
        
        self.test_cluster_health()
        self.test_replication()
        self.test_write_read_consistency()
        
        return self.test_results
    
    def print_summary(self):
        """In tóm tắt kết quả"""
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        
        for test_result in self.test_results:
            test_name = test_result.get("test", "unknown")
            status = "PASS" if test_result.get("overall_status") == "healthy" or test_result.get("consistency_ok") else "FAIL"
            logger.info(f"{status}: {test_name}")
        
        logger.info("="*60)


def main():
    """Main execution"""
    cluster = PatroniCluster()
    results = cluster.run_all_tests()
    cluster.print_summary()
    
    # Return exit code based on results
    all_passed = all(
        r.get("overall_status") == "healthy" or r.get("consistency_ok") 
        for r in results
    )
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
