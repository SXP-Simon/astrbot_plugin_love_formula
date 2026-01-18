import sqlite3
import os

db_path = "/AstrBot/data/plugins/astrbot_plugin_love_formula/love_formula.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(0)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if columns exist
    cursor.execute("PRAGMA table_info(love_daily_ref)")
    columns = [row[1] for row in cursor.fetchall()]

    if "repeat_count" not in columns:
        print("Adding repeat_count column...")
        cursor.execute(
            "ALTER TABLE love_daily_ref ADD COLUMN repeat_count INTEGER DEFAULT 0"
        )

    if "topic_count" not in columns:
        print("Adding topic_count column...")
        cursor.execute(
            "ALTER TABLE love_daily_ref ADD COLUMN topic_count INTEGER DEFAULT 0"
        )

    conn.commit()
    conn.close()
    print("Migration successful.")
except Exception as e:
    print(f"Migration failed: {e}")
    exit(1)
