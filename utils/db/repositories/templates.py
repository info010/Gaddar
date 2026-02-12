import json
import sqlite3

class TemplateRepository:
    def __init__(self, db_connection):
        self.db_connection = db_connection

    def init_table(self):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                name TEXT PRIMARY KEY,
                roles TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def save_template(self, name: str, roles: list):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        roles_json = json.dumps(roles, ensure_ascii=False)
        cursor.execute('INSERT OR REPLACE INTO templates (name, roles) VALUES (?, ?)', (name, roles_json))
        conn.commit()
        conn.close()

    def get_template(self, name: str):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT roles FROM templates WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'name': name, 'roles': json.loads(row[0])}
        return None

    def get_all_templates(self):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM templates')
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def delete_template(self, name: str):
        conn = self.db_connection.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM templates WHERE name = ?', (name,))
        conn.commit()
        conn.close()
