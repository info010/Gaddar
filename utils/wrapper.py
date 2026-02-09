import functools
import time
import traceback
import discord
from utils.database import db

def log_execution(command_name: str = None):
    """
    Decorator to log command execution details to SQLite database.
    The decorated function should return a dictionary of details to be logged.
    If it returns None, basic argument details are implicitly logged.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            start_time = time.perf_counter()
            details = {}
            error_occurred = False
            error_msg = None
            
            try:
                # Execute the actual command
                result = await func(self, interaction, *args, **kwargs)
                if isinstance(result, dict):
                    details = result
                elif result is None:
                    # If nothing returned, try to capture kwargs
                    details = {k: str(v) for k, v in kwargs.items()}
                else:
                    details = {"result": str(result)}
            except Exception as e:
                error_occurred = True
                error_msg = str(e)
                details["error"] = error_msg
                # Re-raise the exception so error handler can catch it
                raise e
            finally:
                end_time = time.perf_counter()
                execution_time = (end_time - start_time) * 1000
                
                try:
                    # Determine command name
                    actual_cmd_name = command_name 
                    if not actual_cmd_name and interaction.command:
                        actual_cmd_name = interaction.command.name
                    if not actual_cmd_name:
                        actual_cmd_name = "Unknown"

                    # If command failed, add status to details
                    status = "FAILED" if error_occurred else "SUCCESS"
                    channel_id = interaction.channel.id if interaction.channel else None
                    
                    db.log_command(
                        user_id=interaction.user.id,
                        username=interaction.user.name,
                        command_name=actual_cmd_name,
                        channel_id=channel_id,
                        args=details,
                        status=status,
                        execution_time=execution_time,
                        error_message=error_msg
                    )
                except Exception as log_err:
                    print(f"Logging failed: {log_err}")
            
        return wrapper
    return decorator
