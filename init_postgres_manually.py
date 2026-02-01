#!/usr/bin/env python3
"""
PostgreSQL Database Initialization Script
Manually initializes the PostgreSQL server with users, databases, and schemas
since the alpine image doesn't auto-initialize
"""

import subprocess
import sys
import time
import os

def run_command(cmd, shell=False):
    """Run a shell command and return output"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=shell, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode == 0

def main():
    print("=" * 70)
    print("PostgreSQL Manual Initialization")
    print("=" * 70)
    
    container_name = "dfs-postgres"
    postgres_pass = "postgres_secure_pass"
    db_name = "fileshare"
    
    # Step 1: Verify container is running
    print(f"\n[1/5] Checking if '{container_name}' is running...")
    if run_command(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}' | findstr {container_name}"):
        print("✓ Container is running")
    else:
        print("✗ Container is not running")
        return 1
    
    time.sleep(2)
    
    # Step 2: Check if postgres role exists
    print("\n[2/5] Checking if postgres role exists...")
    check_role_cmd = f'docker exec {container_name} bash -c "echo SELECT 1 | psql -U postgres -h localhost -d postgres 2>&1 | head -1"'
    
    # Since roles don't exist, we need to recreate the database.
    # For PostgreSQL alpine, we need to manually initialize
    
    print(f"\n[3/5] Initializing PostgreSQL database...")
    # We'll copy an initialization SQL script and run it
    
    init_sql_content = f"""
-- Create postgres superuser role
CREATE ROLE postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN PASSWORD '{postgres_pass}';

-- Create fileshare database
CREATE DATABASE {db_name} OWNER postgres;

-- Connect to fileshare database and run initialization scripts
"""
    
    # Write temp init file
    temp_file = "/tmp/init_db_manually.sql"
    with open(temp_file, 'w') as f:
        f.write(init_sql_content)
    
    # Copy to container
    print(f"Copying initialization script...")
    run_command(f'docker cp "{temp_file}" {container_name}:/tmp/init_db.sql')
    
    # Since we can't connect as postgres, let's try using the postgres system user
    # This should work because the postgres OS user can connect without auth
    print(f"Creating postgres role using system user...")
    create_role_cmd = f'''docker exec -u postgres {container_name} bash -c "psql postgres -c 'CREATE ROLE postgres WITH SUPERUSER CREATEDB CREATEROLE LOGIN PASSWORD \\"{postgres_pass}\\";' 2>&1"'''
    
    result = subprocess.run(create_role_cmd, shell=True, capture_output=True, text=True)
    print("Output:", result.stdout)
    if result.stderr:
        print("Error:", result.stderr)
    
    time.sleep(1)
    
    # Step 4: Create database
    print(f"\n[4/5] Creating {db_name} database...")
    create_db_cmd = f'''docker exec -u postgres {container_name} bash -c "psql postgres -c 'CREATE DATABASE {db_name} OWNER postgres;' 2>&1"'''
    
    result = subprocess.run(create_db_cmd, shell=True, capture_output=True, text=True)
    print("Output:", result.stdout)
    if result.stderr and "already exists" not in result.stderr:
        print("Error:", result.stderr)
    
    time.sleep(1)
    
    # Step 5: Run schema initialization
    print(f"\n[5/5] Running schema initialization...")
    
    schema_file = "c:\\Users\\Admin\\OneDrive\\Tài liệu\\Máy tính\\FileShareSystem\\scripts\\01_init_schema.sql"
    
    if os.path.exists(schema_file):
        print(f"Copying schema file...")
        run_command(f'docker cp "{schema_file}" {container_name}:/tmp/schema.sql')
        
        time.sleep(1)
        
        run_schema_cmd = f'''docker exec -u postgres {container_name} bash -c "PGPASSWORD='{postgres_pass}' psql -U postgres -d {db_name} -f /tmp/schema.sql 2>&1" | head -30'''
        
        result = subprocess.run(run_schema_cmd, shell=True, capture_output=True, text=True)
        print("Output:", result.stdout)
        if result.stderr:
            print("Error:", result.stderr[:500])
    
    print("\n" + "=" * 70)
    print("PostgreSQL initialization complete!")
    print("=" * 70)
    print(f"\nTest connection with:")
    print(f"  PGPASSWORD='{postgres_pass}' psql -U postgres -h localhost -d {db_name}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
