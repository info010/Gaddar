import discord
from discord import app_commands
from discord.ext import commands
import traceback
import sys
import os
from datetime import datetime

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists('crash'):
            os.makedirs('crash')

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Standard discord.ext.commands error handler"""
        await self.handle_error(ctx, error)

    def _get_interaction_details(self, interaction: discord.Interaction):
        return {
            "user": f"{interaction.user} ({interaction.user.id})",
            "command": interaction.command.name if interaction.command else "Unknown",
            "channel": f"{interaction.channel.name} ({interaction.channel.id})" if interaction.channel else "Unknown"
        }

    def _get_ctx_details(self, ctx):
        return {
            "user": f"{ctx.author} ({ctx.author.id})",
            "command": ctx.command.name if ctx.command else "Unknown",
            "channel": f"{ctx.channel.name} ({ctx.channel.id})" if ctx.channel else "Unknown"
        }

    async def handle_error(self, source, error):
        # Ignore pass-through errors
        if hasattr(source, 'command') and source.command:
            return

        # Unwrap common wrapper errors
        if isinstance(error, (commands.CommandInvokeError, app_commands.CommandInvokeError)):
            error = error.original

        # Ignore specific errors if needed
        if isinstance(error, (commands.CommandNotFound, app_commands.CommandNotFound)):
            return

        # Prepare log content
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"crash/report_{timestamp_str}.log"
        
        details = {}
        respond = None
        
        if isinstance(source, discord.Interaction):
            details = self._get_interaction_details(source)
            if not source.response.is_done():
                respond = source.response.send_message
            else:
                respond = source.followup.send
        else:
            # Context
            details = self._get_ctx_details(source)
            respond = source.send

        # format traceback
        tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
        tb_text = "".join(tb_lines)
        
        log_content = f"""
ERROR REPORT - {timestamp_str}
========================================
User: {details.get('user')}
Command: {details.get('command')}
Channel: {details.get('channel')}
Error Type: {type(error).__name__}
Error Message: {str(error)}

FULL TRACEBACK:
----------------------------------------
{tb_text}
========================================
        """
        
        # Save to file
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(log_content)
            print(f"Error logged to {filename}")
        except Exception as e:
            print(f"Failed to save crash log: {e}")
            
        # Notify user (Ephemeral if possible)
        error_msg = f"❌ **Beklenmeyen bir hata oluştu!**\nSistem yöneticisine şu rapor ID'sini iletin: `{filename}`"
        
        try:
            if isinstance(source, discord.Interaction):
                await respond(error_msg, ephemeral=True)
            else:
                await respond(error_msg)
        except:
            # If we can't even respond, just log to console
            print("Could not send error message to user.")

async def setup(bot):
    handler = ErrorHandler(bot)
    await bot.add_cog(handler)
    # Register app_commands error handler globally
    bot.tree.on_error = handler.handle_error
