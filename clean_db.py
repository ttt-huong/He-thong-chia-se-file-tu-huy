import sqlite3
import os

db_path = '/app/data/fileshare.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"Tables: {tables}")

# Delete from file_metadata table
try:
    cursor.execute("DELETE FROM file_metadata")
    print(f"Deleted from file_metadata")
except Exception as e:
    print(f"Error deleting from file_metadata: {e}")

conn.commit()
conn.close()

print("Database cleaned successfully")
