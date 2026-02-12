from utils.db.connection import DatabaseConnection
from utils.db.repositories.logs import LogRepository
from utils.db.repositories.templates import TemplateRepository
from utils.db.repositories.contents import ContentRepository

class Database:
    _instance = None

    def __new__(cls, db_path='database.db'):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            
            # Sub-components
            cls._instance.connection = DatabaseConnection(db_path)
            cls._instance.logs = LogRepository(cls._instance.connection)
            cls._instance.templates = TemplateRepository(cls._instance.connection)
            cls._instance.contents = ContentRepository(cls._instance.connection)
            
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        # Delegate table creation
        self.logs.init_table()
        self.templates.init_table()
        self.contents.init_table()

    # --- Wrapped Methods for Backward Compatibility ---

    # Logs
    def log_command(self, *args, **kwargs):
        return self.logs.log_command(*args, **kwargs)

    def get_logs(self, *args, **kwargs):
        return self.logs.get_logs(*args, **kwargs)

    def get_log_details(self, *args, **kwargs):
        return self.logs.get_log_details(*args, **kwargs)

    # Templates
    def save_template(self, *args, **kwargs):
        return self.templates.save_template(*args, **kwargs)

    def get_template(self, *args, **kwargs):
        return self.templates.get_template(*args, **kwargs)

    def get_all_templates(self, *args, **kwargs):
        return self.templates.get_all_templates(*args, **kwargs)

    def delete_template(self, *args, **kwargs):
        return self.templates.delete_template(*args, **kwargs)

    # Contents
    def create_content(self, *args, **kwargs):
        return self.contents.create_content(*args, **kwargs)
    
    def get_content(self, *args, **kwargs):
        return self.contents.get_content(*args, **kwargs)

    def get_content_by_message_id(self, *args, **kwargs):
        return self.contents.get_content_by_message_id(*args, **kwargs)

    def get_latest_content_by_channel(self, *args, **kwargs):
        return self.contents.get_latest_content_by_channel(*args, **kwargs)

    def get_active_contents_by_channel(self, *args, **kwargs):
        return self.contents.get_active_contents_by_channel(*args, **kwargs)

    def update_content_data(self, *args, **kwargs):
        return self.contents.update_content_data(*args, **kwargs)

    def update_content_signups(self, *args, **kwargs):
        return self.contents.update_content_signups(*args, **kwargs)

    def delete_content(self, *args, **kwargs):
        return self.contents.delete_content(*args, **kwargs)

# Singleton instance
db = Database()
