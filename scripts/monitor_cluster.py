"""
Patroni Cluster Real-time Monitoring Dashboard
Hiển thị trạng thái cluster, replication lag, member status real-time
"""

import os
import sys
import time
import requests
import psycopg2
import json
from datetime import datetime
from typing import Dict, Any
from collections import deque

# ANSI color codes
class Colors:
    """Định nghĩa màu cho terminal"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class PatroniMonitor:
    """Giám sát cluster Patroni real-time"""
    
    def __init__(self, refresh_interval: int = 5):
        self.refresh_interval = refresh_interval
        
        # Patroni endpoints
        self.patroni_endpoints = {
            "master": ("localhost", 8008),
            "standby1": ("localhost", 8009),
            "standby2": ("localhost", 8010)
        }
        
        # PostgreSQL connection info
        self.pg_user = os.getenv("POSTGRES_USER", "postgres")
        self.pg_password = os.getenv("POSTGRES_PASSWORD", "postgres_secure_pass")
        self.pg_db = os.getenv("POSTGRES_DB", "fileshare")
        
        # Store history
        self.history = {
            "master": deque(maxlen=30),
            "standby1": deque(maxlen=30),
            "standby2": deque(maxlen=30)
        }
    
    def clear_screen(self):
        """Xóa màn hình terminal"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def get_node_status(self, node_name: str, host: str, port: int) -> Dict[str, Any]:
        """Lấy trạng thái của node"""
        try:
            # Patroni health endpoint
            health_url = f"http://{host}:{port}/health"
            health_response = requests.get(health_url, timeout=3)
            
            # Determine role
            role_url = f"http://{host}:{port}/master"
            role_response = requests.get(role_url, timeout=3)
            
            if role_response.status_code == 200:
                role = "MASTER"
            else:
                role = "STANDBY"
            
            return {
                "name": node_name,
                "status": "ONLINE" if health_response.status_code == 200 else "OFFLINE",
                "role": role,
                "http_status": health_response.status_code,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "name": node_name,
                "status": "ERROR",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_cluster_info(self) -> Dict[str, Any]:
        """Lấy thông tin cluster từ Patroni"""
        try:
            response = requests.get("http://localhost:8008/cluster", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "ok",
                    "cluster_name": data.get("cluster", "unknown"),
                    "leader": data.get("leader", {}).get("name", "unknown"),
                    "members": len(data.get("members", [])),
                    "data": data
                }
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_pg_connections(self, host: str, port: int) -> int:
        """Lấy số connections PostgreSQL"""
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=self.pg_user,
                password=self.pg_password,
                database=self.pg_db,
                connect_timeout=3
            )
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state IS NOT NULL")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except:
            return -1
    
    def format_status_line(self, node_status: Dict[str, Any]) -> str:
        """Định dạng dòng trạng thái node"""
        name = node_status.get("name", "unknown")
        status = node_status.get("status", "UNKNOWN")
        role = node_status.get("role", "unknown")
        
        # Chọn màu
        if status == "ONLINE":
            status_color = Colors.GREEN
            status_symbol = "●"
        elif status == "ERROR":
            status_color = Colors.RED
            status_symbol = "✗"
        else:
            status_color = Colors.YELLOW
            status_symbol = "○"
        
        # Chọn role color
        if role == "MASTER":
            role_color = Colors.RED
        else:
            role_color = Colors.BLUE
        
        return (f"{name:15} {status_color}{status_symbol} {status:8}{Colors.RESET} "
                f"{role_color}{role:8}{Colors.RESET}")
    
    def display_header(self):
        """Hiển thị header"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}PostgreSQL Patroni Cluster Monitor{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Colors.BOLD}{'='*70}{Colors.RESET}\n")
    
    def display_nodes(self, nodes_status: list):
        """Hiển thị trạng thái các node"""
        print(f"{Colors.BOLD}Cluster Members:{Colors.RESET}")
        print(f"{'-'*70}")
        for node_status in nodes_status:
            print(self.format_status_line(node_status))
        print()
    
    def display_cluster_info(self, cluster_info: Dict[str, Any]):
        """Hiển thị thông tin cluster"""
        if cluster_info.get("status") == "ok":
            print(f"{Colors.BOLD}Cluster Info:{Colors.RESET}")
            print(f"{'-'*70}")
            print(f"Cluster: {cluster_info['cluster_name']:20} "
                  f"Leader: {cluster_info['leader']:20} "
                  f"Members: {cluster_info['members']}")
            print()
        else:
            print(f"{Colors.RED}Cluster Error: {cluster_info.get('error')}{Colors.RESET}\n")
    
    def monitor_loop(self):
        """Vòng giám sát chính"""
        try:
            while True:
                self.clear_screen()
                self.display_header()
                
                # Collect node statuses
                nodes_status = []
                for node_name, (host, port) in self.patroni_endpoints.items():
                    status = self.get_node_status(node_name, host, port)
                    nodes_status.append(status)
                
                # Display nodes
                self.display_nodes(nodes_status)
                
                # Display cluster info
                cluster_info = self.get_cluster_info()
                self.display_cluster_info(cluster_info)
                
                # Display connection counts
                print(f"{Colors.BOLD}Connection Counts:{Colors.RESET}")
                print(f"{'-'*70}")
                ports = {
                    "Master": 5432,
                    "Standby1": 5433,
                    "Standby2": 5434
                }
                for label, port in ports.items():
                    conn_count = self.get_pg_connections("localhost", port)
                    if conn_count >= 0:
                        print(f"{label:15} Connections: {Colors.CYAN}{conn_count:3}{Colors.RESET}")
                    else:
                        print(f"{label:15} Connections: {Colors.RED}ERROR{Colors.RESET}")
                print()
                
                # Display instructions
                print(f"{Colors.YELLOW}Press Ctrl+C to exit | Refresh interval: {self.refresh_interval}s{Colors.RESET}")
                print(f"{Colors.BOLD}{'='*70}{Colors.RESET}")
                
                # Wait before refresh
                time.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Monitoring stopped.{Colors.RESET}")
            sys.exit(0)


def main():
    """Main execution"""
    refresh_interval = int(os.getenv("MONITOR_REFRESH_INTERVAL", "5"))
    monitor = PatroniMonitor(refresh_interval=refresh_interval)
    monitor.monitor_loop()


if __name__ == "__main__":
    main()
