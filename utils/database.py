import sqlite3
import json
import os
from datetime import datetime

class Database:
    _instance = None

    def __new__(cls, db_path='database.db'):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            
            # Ensure Absolute Path
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cls._instance.db_path = os.path.join(base_dir, db_path)
            
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Command Logs Table
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

        # Templates Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                name TEXT PRIMARY KEY,
                roles TEXT
            )
        ''')

        # Active Contents V2 Table (With Auto-Increment ID)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_contents_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                channel_id INTEGER,
                name TEXT,
                template_name TEXT,
                description TEXT,
                data TEXT,
                signups TEXT
            )
        ''')
        
        # Migration: Add description column if not exists
        try:
            cursor.execute("ALTER TABLE active_contents_v2 ADD COLUMN description TEXT")
        except:
            pass
        
        conn.commit()
        conn.close()

    def log_command(self, user_id, username, command_name, channel_id, args, status, execution_time, error_message=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO command_logs (user_id, username, command_name, channel_id, timestamp, args, status, execution_time, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, command_name, channel_id, datetime.now(), json.dumps(args, ensure_ascii=False), status, execution_time, error_message))
        conn.commit()
        conn.close()

    def get_logs(self, limit=10, offset=0):
        # ... (Same as before, simplified for this replacement block)
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM command_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?', (limit, offset))
        rows = cursor.fetchall()
        
        cursor.execute('SELECT COUNT(*) FROM command_logs')
        total = cursor.fetchone()[0]
        
        conn.close()
        return rows, total

    def get_log_details(self, log_id):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM command_logs WHERE id = ?', (log_id,))
        row = cursor.fetchone()
        conn.close()
        return row

    # --- Template Methods ---

    def save_template(self, name: str, roles: list):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        roles_json = json.dumps(roles, ensure_ascii=False)
        cursor.execute('INSERT OR REPLACE INTO templates (name, roles) VALUES (?, ?)', (name, roles_json))
        conn.commit()
        conn.close()

    def get_template(self, name: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT roles FROM templates WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'name': name, 'roles': json.loads(row[0])}
        return None

    def get_all_templates(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM templates')
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def delete_template(self, name: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM templates WHERE name = ?', (name,))
        conn.commit()
        conn.close()

    # --- Content Methods (V2) ---

    def create_content(self, message_id: int, channel_id: int, name: str, template_name: str, data: dict, description: str = ""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        data_json = json.dumps(data, ensure_ascii=False)
        signups_json = json.dumps([], ensure_ascii=False)
        cursor.execute('''
            INSERT INTO active_contents_v2 (message_id, channel_id, name, template_name, description, data, signups)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, channel_id, name, template_name, description, data_json, signups_json))
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def get_content(self, content_id: int):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_contents_v2 WHERE id = ?', (content_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_content_row(row)

    def get_content_by_message_id(self, message_id: int):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_contents_v2 WHERE message_id = ?', (message_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_content_row(row)

    def get_latest_content_by_channel(self, channel_id: int):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_contents_v2 WHERE channel_id = ? ORDER BY id DESC LIMIT 1', (channel_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_content_row(row)

    def get_active_contents_by_channel(self, channel_id: int):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_contents_v2 WHERE channel_id = ? ORDER BY id DESC', (channel_id,))
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            res = self._parse_content_row(row)
            if res: results.append(res)
        return results

    def _parse_content_row(self, row):
        if row:
            # Check for description column existence safely
            desc = ""
            if 'description' in row.keys():
                desc = row['description'] or ""

            return {
                'id': row['id'],
                'message_id': row['message_id'],
                'channel_id': row['channel_id'],
                'name': row['name'],
                'template_name': row['template_name'],
                'description': desc,
                'data': json.loads(row['data']),
                'signups': json.loads(row['signups']) if row['signups'] else []
            }
        return None

    def update_content_data(self, message_id: int, data: dict):
        # Keeps using message_id for easier lookups from Discord messages
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        data_json = json.dumps(data, ensure_ascii=False)
        cursor.execute('UPDATE active_contents_v2 SET data = ? WHERE message_id = ?', (data_json, message_id))
        conn.commit()
        conn.close()

    def update_content_signups(self, message_id: int, signups: list):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        signups_json = json.dumps(signups, ensure_ascii=False)
        cursor.execute('UPDATE active_contents_v2 SET signups = ? WHERE message_id = ?', (signups_json, message_id))
        conn.commit()
        conn.close()

    def delete_content(self, content_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM active_contents_v2 WHERE id = ?', (content_id,))
        conn.commit()
        conn.close()

db = Database()
