import yaml
import os
import discord

class ConfigManager:
    _config = {}
    _config_path = "config.yml"

    @classmethod
    def load_config(cls):
        if not os.path.exists(cls._config_path):
            return {}
        try:
            with open(cls._config_path, 'r', encoding='utf-8') as f:
                cls._config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Config yükleme hatası: {e}")
            cls._config = {}
        return cls._config

    @classmethod
    def can_use_command(cls, user: discord.Member, command_name: str) -> bool:
        """
        Check if a user can use a specific command based on config.yml
        Checks both User ID and Role IDs.
        """
        # Reload config every time to allow dynamic updates
        cls.load_config()
        
        commands = cls._config.get("commands", {})
        cmd_config = commands.get(command_name)
        
        if not cmd_config:
            # If command not in config, assume restricted (or allow? usually restrict)
            # User request implies whitelist logic, so default deny.
            return False

        # Check User ID
        allowed_users = cmd_config.get("users", []) or []
        if user.id in allowed_users:
            return True

        # Check Role IDs
        allowed_roles = cmd_config.get("roles", []) or []
        if not allowed_roles:
            return False
            
        user_role_ids = [role.id for role in user.roles]
        # Check intersection
        if any(r_id in user_role_ids for r_id in allowed_roles):
            return True

        return False

# Initialize
ConfigManager.load_config()
