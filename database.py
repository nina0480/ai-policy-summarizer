import sqlite3
import json
from datetime import datetime

DB_PATH = "database.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_name TEXT NOT NULL,
            description TEXT,
            benefits TEXT,
            eligibility TEXT,
            last_date TEXT,
            upload_date TEXT NOT NULL,
            filename TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_policy(policy_name, description, benefits, eligibility, last_date, filename):
    conn = get_connection()
    cursor = conn.cursor()
    upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    benefits_str = json.dumps(benefits) if isinstance(benefits, list) else benefits
    eligibility_str = json.dumps(eligibility) if isinstance(eligibility, list) else eligibility

    cursor.execute("""
        INSERT INTO policies (policy_name, description, benefits, eligibility, last_date, upload_date, filename)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (policy_name, description, benefits_str, eligibility_str, last_date, upload_date, filename))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_all_policies(search=None):
    conn = get_connection()
    cursor = conn.cursor()
    if search:
        cursor.execute("""
            SELECT * FROM policies
            WHERE policy_name LIKE ?
            ORDER BY upload_date DESC
        """, (f"%{search}%",))
    else:
        cursor.execute("SELECT * FROM policies ORDER BY upload_date DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_policy_by_id(policy_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM policies WHERE id = ?", (policy_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def delete_policy(policy_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
    conn.commit()
    conn.close()
