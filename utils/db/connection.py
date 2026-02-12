import sqlite3
import os

class DatabaseConnection:
    _instance = None
    
    def __new__(cls, db_path='database.db'):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cls._instance.db_path = os.path.join(base_dir, db_path)
        return cls._instance

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn
