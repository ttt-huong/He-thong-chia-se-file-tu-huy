# 🚀 DEPLOYMENT GUIDE: PostgreSQL + Redis HA

## 📋 QUICK START

### 1️⃣ Start Services

```bash
# Deploy PostgreSQL Master-Slave + Redis Sentinel
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# Expected output:
# postgres-master    Running (port 5432) ✅
# postgres-slave1    Running (port 5433) ✅
# postgres-slave2    Running (port 5434) ✅
# redis-master       Running (port 6379) ✅
# redis-slave1       Running (port 6380) ✅
# redis-slave2       Running (port 6381) ✅
# sentinel1/2/3      Running (port 26379+) ✅
# rabbitmq           Running (port 5672) ✅
```

### 2️⃣ Migrate Data from SQLite to PostgreSQL

```bash
# Make sure PostgreSQL is running and healthy
docker-compose -f docker-compose.prod.yml logs postgres-master

# Run migration script
python scripts/migrate_sqlite_to_postgres.py \
  --source sqlite:///data/metadata.db \
  --target postgresql://fileshare_user:secure_password_change_me@localhost:5432/fileshare_db

# Expected output:
# ✅ Tables created successfully
# ✅ Migrated X Files
# ✅ Migrated Y Storage Nodes
# ✅ Migrated Z Tasks
# ✅ All records migrated successfully!
```

### 3️⃣ Update Application Config

**Create .env file:**
```bash
# Database
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fileshare_db
DB_USER=fileshare_user
DB_PASSWORD=secure_password_change_me

# Redis (Sentinel will auto-failover)
REDIS_HOST=localhost
REDIS_PORT=26379  # Sentinel port (not direct Redis)
REDIS_SENTINEL_ENABLED=true
REDIS_SENTINEL_SERVICE_NAME=mymaster

# Application
DEBUG=False
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### 4️⃣ Run Application

```bash
# Install dependencies
pip install python-dotenv psycopg2-binary redis

# Load .env
export $(cat .env | xargs)

# Run Flask app
python src/gateway/app.py
```

---

## 🔍 VERIFICATION STEPS

### Check PostgreSQL Replication

```bash
# Connect to Master
psql -h localhost -U fileshare_user -d fileshare_db

# Check replication status
SELECT pid, usename, application_name, state, sync_state FROM pg_stat_replication;

# Expected: 2 rows (slave1 and slave2 connected) ✅
```

### Check Redis Replication

```bash
# Connect to Master
redis-cli -h localhost -p 6379

# Check connected slaves
INFO replication

# Expected output:
# role:master
# connected_slaves:2
# slave0:ip=...,port=...,state=online
# slave1:ip=...,port=...,state=online
```

### Check Redis Sentinel

```bash
# Connect to Sentinel
redis-cli -h localhost -p 26379

# Check master status
sentinel masters

# Expected: mymaster is running ✅
```

---

## ⚡ TESTING HA FAILOVER

### Test 1: Kill PostgreSQL Master

```bash
# Kill master
docker-compose -f docker-compose.prod.yml stop postgres-master

# Check slave promotion
# After 30-60 seconds, one slave should become master

# Verify with:
psql -h localhost -p 5433 -U fileshare_user -d fileshare_db
SELECT version();  # Should connect ✅
```

### Test 2: Kill Redis Master

```bash
# Kill Redis Master
docker-compose -f docker-compose.prod.yml stop redis-master

# Sentinel automatically promotes slave
# Check:
redis-cli -h localhost -p 6379 ping
# Expected: PONG ✅ (from new master)

# Or use Sentinel:
redis-cli -h localhost -p 26379 sentinel get-master-addr-by-name mymaster
# Shows new master address
```

### Test 3: Partial Network Failure

```bash
# Simulate network partition
docker network disconnect fileshare-network postgres-master

# Database should failover to slave
# After network recovery:
docker network connect fileshare-network postgres-master
# Master rejoins as slave (resync from new master)
```

---

## 📊 MONITORING

### PostgreSQL Monitoring

```bash
# Check replication lag
psql -h localhost -U fileshare_user -d fileshare_db
SELECT now() - pg_last_wal_receive_lsn() AS replication_lag;

# Check database size
SELECT pg_size_pretty(pg_database_size('fileshare_db'));

# Check active connections
SELECT count(*) FROM pg_stat_activity;
```

### Redis Monitoring

```bash
# Memory usage
redis-cli INFO memory

# Commands per second
redis-cli INFO stats

# Connected clients
redis-cli INFO clients
```

### Application Logs

```bash
# Flask logs
tail -f logs/app.log

# Database logs
docker-compose -f docker-compose.prod.yml logs -f postgres-master

# Redis logs
docker-compose -f docker-compose.prod.yml logs -f redis-master
```

---

## 🔒 PRODUCTION CHECKLIST

- [ ] Change `DB_PASSWORD` from default
- [ ] Change `REDIS_PASSWORD` if needed
- [ ] Update `RABBITMQ_PASSWORD`
- [ ] Backup SQLite before migration
- [ ] Verify all 3 Sentinels are running
- [ ] Test failover procedure
- [ ] Setup automated backups
- [ ] Configure firewall rules
- [ ] Setup monitoring & alerting
- [ ] Document emergency recovery procedure

---

## 📈 PERFORMANCE TUNING

### PostgreSQL Tuning

```bash
# Edit docker-compose.prod.yml, add POSTGRES_INITDB_ARGS:
-c shared_buffers=512MB
-c effective_cache_size=2GB
-c work_mem=32MB
-c random_page_cost=1.1
```

### Redis Tuning

```bash
# Edit Dockerfile or add command override:
redis-server
  --maxmemory 512mb
  --maxmemory-policy allkeys-lru
  --tcp-keepalive 60
```

---

## 🚨 TROUBLESHOOTING

### PostgreSQL Won't Start

```bash
# Check logs
docker logs fileshare-postgres-master

# Common issues:
# 1. Port already in use → Change port in docker-compose.prod.yml
# 2. Volume permission → sudo chown -R 999:999 postgres_data/
# 3. Corrupt recovery → rm -rf postgres_*_data/* and restart
```

### Redis Sentinel Not Failover

```bash
# Verify Sentinel is running
docker ps | grep sentinel

# Check Sentinel logs
docker logs fileshare-redis-sentinel1

# Manually failover:
redis-cli -p 26379 sentinel failover mymaster
```

### Application Connection Error

```bash
# Test PostgreSQL connection
psql -h localhost -U fileshare_user -d fileshare_db

# Test Redis connection
redis-cli -h localhost -p 6379 ping

# Check application .env file
cat .env | grep DB_
cat .env | grep REDIS_
```

---

## 🔄 BACKUP & RECOVERY

### Automated PostgreSQL Backups

```bash
# Create backup script
cat > scripts/backup_postgres.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/postgres"
mkdir -p $BACKUP_DIR
pg_dump -h localhost -U fileshare_user fileshare_db | gzip > $BACKUP_DIR/fileshare_$(date +%Y%m%d_%H%M%S).sql.gz
EOF

# Schedule with cron (every 6 hours)
0 */6 * * * /path/to/scripts/backup_postgres.sh
```

### Recovery from Backup

```bash
# Restore from backup
gzip -dc backups/postgres/fileshare_20260127_120000.sql.gz | psql -h localhost -U fileshare_user fileshare_db
```

---

## 📞 SUPPORT

For issues:
1. Check logs: `docker-compose -f docker-compose.prod.yml logs -f [service]`
2. Test connectivity: `telnet localhost 5432` (PostgreSQL)
3. Verify migration: `python scripts/migrate_sqlite_to_postgres.py --verify-only`
4. Review: docker-compose.prod.yml configuration

---

## 🎯 NEXT STEPS

1. ✅ Deploy docker-compose.prod.yml
2. ✅ Migrate data from SQLite
3. ✅ Update .env with PostgreSQL settings
4. ✅ Test application connections
5. ✅ Verify replication & failover
6. ✅ Setup automated backups
7. ✅ Configure monitoring
8. ✅ Document runbooks

---

**Production Ready! 🚀**
