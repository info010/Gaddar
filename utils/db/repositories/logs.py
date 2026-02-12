import sqlite3
import json
from datetime import datetime

class LogRepository:
    def __init__(self, db_connection):
        self.db_connection = db_connection

    def init_table(self):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS command_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                command_name TEXT,
                channel_id INTEGER,
                timestamp TIMESTAMP,
                args TEXT,
                status TEXT,
                execution_time REAL,
                error_message TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def log_command(self, user_id, username, command_name, channel_id, args, status, execution_time, error_message=None):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO command_logs (user_id, username, command_name, channel_id, timestamp, args, status, execution_time, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, command_name, channel_id, datetime.now(), json.dumps(args, ensure_ascii=False), status, execution_time, error_message))
        conn.commit()
        conn.close()

    def get_logs(self, limit=10, offset=0):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM command_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        
        cursor.execute('SELECT COUNT(*) FROM command_logs')
        total = cursor.fetchone()[0]
        
        conn.close()
        return rows, total

    def get_log_details(self, log_id):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM command_logs WHERE id = ?', (log_id,))
        row = cursor.fetchone()
        conn.close()
        return row
