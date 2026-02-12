import sqlite3
import json

class ContentRepository:
    def __init__(self, db_connection):
        self.db_connection = db_connection

    def init_table(self):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
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

    def create_content(self, message_id: int, channel_id: int, name: str, template_name: str, data: dict, description: str = ""):
        conn = self.db_connection.get_connection()
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
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_contents_v2 WHERE id = ?', (content_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_content_row(row)

    def get_content_by_message_id(self, message_id: int):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_contents_v2 WHERE message_id = ?', (message_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_content_row(row)

    def get_latest_content_by_channel(self, channel_id: int):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM active_contents_v2 WHERE channel_id = ? ORDER BY id DESC LIMIT 1', (channel_id,))
        row = cursor.fetchone()
        conn.close()
        return self._parse_content_row(row)

    def get_active_contents_by_channel(self, channel_id: int):
        conn = self.db_connection.get_connection()
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
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        data_json = json.dumps(data, ensure_ascii=False)
        cursor.execute('UPDATE active_contents_v2 SET data = ? WHERE message_id = ?', (data_json, message_id))
        conn.commit()
        conn.close()

    def update_content_signups(self, message_id: int, signups: list):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        signups_json = json.dumps(signups, ensure_ascii=False)
        cursor.execute('UPDATE active_contents_v2 SET signups = ? WHERE message_id = ?', (signups_json, message_id))
        conn.commit()
        conn.close()

    def delete_content(self, content_id: int):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM active_contents_v2 WHERE id = ?', (content_id,))
        conn.commit()
        conn.close()
