# Phase 4.4: Patroni Failover Testing Guide

## Overview
Kiểm tra automatic failover của Patroni cluster PostgreSQL với các scenarios:
- Sức khỏe cluster
- Replication lag
- Write-read consistency
- Master failure simulation

## Prerequisites

### 1. Running Services
```bash
docker-compose up -d \
  postgres-master \
  postgres-standby1 \
  postgres-standby2 \
  etcd \
  pgbouncer \
  gateway
```

### 2. Verify Cluster Status
```bash
# Check cluster status
curl http://localhost:5000/patroni/cluster

# Check members
curl http://localhost:5000/patroni/members

# Check master
curl http://localhost:5000/patroni/master
```

## Quick Start

### Run All Tests
```bash
cd FileShareSystem
python scripts/test_failover.py
```

Expected output:
```
============================================================
PATRONI FAILOVER TEST SUITE
============================================================

============================================================
TEST 1: Cluster Health Check
============================================================

Checking master...
  Patroni health: ok
  PostgreSQL: ✓
    Version: PostgreSQL 15.1 on x86_64...
  Role: master

Checking standby1...
  Patroni health: ok
  PostgreSQL: ✓
  Role: standby

Checking standby2...
  Patroni health: ok
  PostgreSQL: ✓
  Role: standby

Cluster Status:
  Cluster: fileshare-cluster
  Leader: postgres-master
  Members: 3

============================================================
TEST 2: Replication Lag Check
============================================================

Master LSN: 123456789
✓ standby1: 0.02MB lag
✓ standby2: 0.01MB lag

============================================================
TEST 3: Write-Read Consistency Test
============================================================

Writing test data to master...
✓ Wrote test record: 1
Waiting for replication...
Reading from standby...
✓ Read data from standby: test_1706780000

============================================================
TEST SUMMARY
============================================================

PASS: cluster_health
PASS: replication_lag
PASS: write_read_consistency
============================================================
```

## Real-time Cluster Monitoring

### Start Monitor Dashboard
```bash
python scripts/monitor_cluster.py
```

This will display real-time:
- Node status (Online/Offline)
- Role (Master/Standby)
- Leader information
- Member count
- Connection counts per node
- Auto-refresh every 5 seconds

```
PostgreSQL Patroni Cluster Monitor
======================================================================
Time: 2026-02-01 16:30:45
======================================================================

Cluster Members:
----------------------------------------------------------------------
postgres-master  ● ONLINE   MASTER
postgres-standby1 ● ONLINE   STANDBY
postgres-standby2 ● ONLINE   STANDBY

Cluster Info:
----------------------------------------------------------------------
Cluster: fileshare-cluster   Leader: postgres-master   Members: 3

Connection Counts:
----------------------------------------------------------------------
Master         Connections:   5
Standby1       Connections:   2
Standby2       Connections:   2

Press Ctrl+C to exit | Refresh interval: 5s
======================================================================
```

## Failover Test Scenarios

### Scenario 1: Normal Healthy Cluster
**Objective:** Verify cluster is healthy and all nodes operational

```bash
python scripts/test_failover.py
```

**Expected Results:**
- All 3 nodes show ONLINE
- Master role assigned to postgres-master
- Standbys show STANDBY role
- Replication lag < 1MB
- Write-read consistency passed

### Scenario 2: Simulate Master Failure

**Step 1: Stop Master Container**
```bash
docker-compose stop postgres-master
```

**Step 2: Monitor Failover (30-60 seconds)**
```bash
python scripts/monitor_cluster.py
```

**Expected Behavior:**
- Master shows OFFLINE
- Patroni triggers election
- New leader elected from standbys (usually standby1)
- New master role assigned
- 2 nodes online

**Step 3: Verify Failover Complete**
```bash
# Check new leader
curl http://localhost:5000/patroni/master

# Check cluster status
curl http://localhost:5000/patroni/cluster
```

**Step 4: Recover Original Master**
```bash
docker-compose up -d postgres-master
```

**Expected Behavior:**
- postgres-master comes back as STANDBY (not master)
- Automatically catches up on replication
- Cluster returns to 3 members

### Scenario 3: Simulate Standby Failure

**Step 1: Stop Standby1**
```bash
docker-compose stop postgres-standby1
```

**Step 2: Verify Cluster Continues**
```bash
python scripts/test_failover.py
```

**Expected Results:**
- 2 nodes online (master + standby2)
- Write-read consistency still works
- No automatic failover (master still running)

**Step 3: Recover Standby**
```bash
docker-compose up -d postgres-standby1
```

### Scenario 4: Replication Lag Test

**Objective:** Monitor replication lag during heavy write load

**Step 1: Start Load Generator** (optional, requires additional tool)
```bash
# Insert test data rapidly
for i in {1..1000}; do
  psql -h localhost -U postgres -d fileshare -c \
    "INSERT INTO files (id, filename, original_name, file_size, mime_type, primary_node, expires_at) 
     VALUES ('test_$i', 'file_$i.txt', 'file_$i.txt', 1000, 'text/plain', 'node1', NOW() + interval '1 day')"
done
```

**Step 2: Monitor Lag**
```bash
python scripts/test_failover.py
```

**Expected Results:**
- Lag temporarily increases during load
- Lag returns to < 1MB after load stops
- No data loss

### Scenario 5: Network Partition (Split Brain)

**Objective:** Simulate network partition between master and standbys

**Note:** This requires etcd quorum voting enabled (already configured)

**Expected Behavior:**
- If master loses quorum → Master becomes read-only
- If standby wins quorum → Standby promoted to master
- Patroni prevents split-brain scenario

## API Endpoints for Monitoring

### Patroni Cluster Status
```bash
GET /patroni/cluster
# Returns cluster members and leader info
```

### Patroni Members
```bash
GET /patroni/members
# Returns individual member details and roles
```

### Current Master Info
```bash
GET /patroni/master
# Returns current master node information
```

### Database Health
```bash
GET /db/health
# Returns replication status and connectivity
```

### Replication Lag
```bash
GET /db/replication/lag
# Returns lag between master and standbys
```

### Pool Statistics
```bash
GET /pool/summary
# Returns connection pool statistics
```

## Failover Metrics to Monitor

### Key Metrics
1. **RTO (Recovery Time Objective)**
   - Time from master failure to new master elected
   - Target: < 60 seconds

2. **RPO (Recovery Point Objective)**
   - Data lost during failover
   - Target: 0 (synchronous replication)

3. **Replication Lag**
   - Distance between master and standby
   - Target: < 1MB

4. **Connection Failover Time**
   - Time for application to reconnect to new master
   - Target: < 5 seconds (via PgBouncer)

### Monitoring Commands

```bash
# Check replication slot status
psql -h localhost -U postgres -d fileshare -c \
  "SELECT slot_name, slot_type, active, restart_lsn FROM pg_replication_slots"

# Check WAL sender status
psql -h localhost -U postgres -d fileshare -c \
  "SELECT pid, usename, application_name, client_addr, state FROM pg_stat_replication"

# Check standby status
psql -h localhost -U postgres -d fileshare -c \
  "SELECT pg_is_in_recovery(), pg_wal_lsn_diff(pg_last_wal_receive_lsn(), '0/0')"
```

## Troubleshooting

### Issue: Failover Takes Too Long

**Symptoms:**
- Master failure not detected within 60 seconds
- Standbys not promoted to master

**Solutions:**
1. Check etcd cluster health
   ```bash
   curl http://localhost:2379/health
   ```

2. Verify TTL and loop_wait settings
   ```bash
   curl http://localhost:8008/config | grep -E "ttl|loop_wait"
   ```

3. Check Patroni logs
   ```bash
   docker-compose logs postgres-master | tail -20
   ```

### Issue: Data Loss During Failover

**Symptoms:**
- Some data written before master failure not replicated

**Solutions:**
1. Ensure synchronous replication is enabled
   ```bash
   psql -h localhost -U postgres -d fileshare -c \
     "SHOW synchronous_commit"
   ```

2. Verify replication slots are active
   ```bash
   psql -h localhost -U postgres -d fileshare -c \
     "SELECT * FROM pg_replication_slots"
   ```

### Issue: Cluster Won't Recover After Master Failure

**Symptoms:**
- No new master elected
- All nodes show as offline

**Solutions:**
1. Check etcd connectivity
   ```bash
   docker-compose logs etcd | tail -10
   ```

2. Restart etcd
   ```bash
   docker-compose restart etcd
   ```

3. Check Patroni REST API
   ```bash
   curl http://localhost:8008/health
   ```

## Post-Failover Checklist

After any failover scenario:
- [ ] New master elected and stable
- [ ] All standbys caught up on replication
- [ ] Replication lag < 1MB
- [ ] Connection pool connected to new master
- [ ] No failed connections in app logs
- [ ] Data consistency verified
- [ ] Monitoring shows healthy status
- [ ] Original master recovered (if applicable)

## Advanced: Custom Failover Testing

Create custom test scenarios by:

1. **Modifying test_failover.py**
   - Add custom test methods
   - Define failure scenarios
   - Set specific thresholds

2. **Using Docker commands**
   ```bash
   # Pause container (simulate hang)
   docker-compose pause postgres-master
   
   # Unpause to recover
   docker-compose unpause postgres-master
   
   # Kill container (immediate failure)
   docker-compose kill postgres-master
   
   # Restart
   docker-compose up -d postgres-master
   ```

3. **Testing connection pooling failover**
   ```bash
   # Monitor PgBouncer during failover
   curl http://localhost:5000/pool/summary
   ```

## Performance Benchmarks

Expected performance on healthy cluster:

| Metric | Expected | Notes |
|--------|----------|-------|
| RTO | < 60s | Time to elect new master |
| RPO | 0 bytes | Synchronous replication |
| Replication Lag | < 1MB | Streaming replication |
| Connection Pool Failover | < 5s | PgBouncer reconnect |
| Write Throughput | > 1000 ops/sec | Per node |
| Read Throughput | > 5000 ops/sec | Per node |

## Next Steps

After successful failover testing:
1. **Dashboard Integration** - Add real-time cluster status to UI
2. **Alerting** - Set up monitoring alerts for failover events
3. **Automation** - Create automated runbooks for common scenarios
4. **Documentation** - Document operational procedures
