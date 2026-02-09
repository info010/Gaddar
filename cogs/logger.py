import discord
from discord.ext import commands
from discord import app_commands
import json
import math
from datetime import timezone
from utils.database import db

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="showlog", description="Log kayıtlarını görüntüler.")
    @app_commands.describe(
        log_id="Görüntülemek istediğiniz log ID (boş bırakırsanız liste görüntülenir)"
    )
    async def showlog(self, interaction: discord.Interaction, log_id: int = None):
        if log_id is not None:
            # Show specific log
            await self.show_log_details(interaction, log_id)
        else:
            # Show list (default page 1)
            await self.show_log_list(interaction, 1)

    async def show_log_details(self, interaction: discord.Interaction, log_id: int):
        log = db.get_log_by_id(log_id)
        if not log:
            await interaction.response.send_message(f"❌ Log ID #{log_id} bulunamadı.", ephemeral=True)
            return

        # Prepare embed
        embed = discord.Embed(title=f"📜 Log Detayı #{log['id']}", color=discord.Color.blue())
        # DB stores UTC, so we must tell python it is UTC before converting to timestamp
        ts = int(log['timestamp'].replace(tzinfo=timezone.utc).timestamp())
        embed.add_field(name="Zaman", value=f"<t:{ts}:F>", inline=True)
        
        executor = interaction.guild.get_member(log['executor_id'])
        executor_text = executor.mention if executor else f"{log['executor_name']} (ID: {log['executor_id']})"
        embed.add_field(name="Komutu Çalıştıran", value=executor_text, inline=True)
        
        embed.add_field(name="Komut Türü", value=f"`{log['command_type']}`", inline=True)
        embed.add_field(name="Süre", value=f"{log['execution_time_ms']:.2f} ms", inline=True)

        # Parse details
        try:
            details = json.loads(log['details'])
            # Format details nicely
            details_str = ""
            for k, v in details.items():
                # Handle lists cleanly
                if isinstance(v, list):
                    val_str = ", ".join(map(str, v))
                    if len(val_str) > 900: val_str = val_str[:900] + "..."
                else:
                    val_str = str(v)
                details_str += f"**{k}:** {val_str}\n"
            
            if not details_str:
                details_str = "Detay yok."
        except:
            details_str = str(log['details'])

        embed.add_field(name="İşlem Detayları", value=details_str, inline=False)
        
        await interaction.response.send_message(embed=embed)

    async def show_log_list(self, interaction: discord.Interaction, page: int):
        ITEMS_PER_PAGE = 10
        total_logs = db.get_total_log_count()
        max_pages = math.ceil(total_logs / ITEMS_PER_PAGE)
        
        # Kullanıcı isteği: Max 20 sayfa
        if max_pages > 20:
            max_pages = 20
        
        if max_pages == 0:
            max_pages = 1
            
        if page < 1 or page > max_pages:
             page = 1

        offset = (page - 1) * ITEMS_PER_PAGE
        logs = db.get_logs(ITEMS_PER_PAGE, offset)
        
        embed = discord.Embed(title="📜 Komut Logları", description=f"Sayfa {page}/{max_pages}", color=discord.Color.dark_grey())
        
        # log_id | zaman | command_executor(mention) | komut
        # Since table format is hard in embed, we use lines
        
        if not logs:
            embed.description += "\n\n*Henüz kayıtlı log yok.*"
        else:
            for log in logs:
                # Format timestamp
                # DB stores UTC
                ts_val = int(log['timestamp'].replace(tzinfo=timezone.utc).timestamp())
                ts = f"<t:{ts_val}:R>"
                
                # Format executor
                # We can't fetch every user object efficiently here, so use mention string format
                executor_mention = f"<@{log['executor_id']}>"
                
                # Format command details brief
                cmd_type = log['command_type']
                
                embed.add_field(
                    name=f"#{log['id']} - {cmd_type}",
                    value=f"👤 {executor_mention} | 🕒 {ts}",
                    inline=False
                )

        # View for pagination
        view = PaginationView(page, max_pages) if max_pages > 1 else discord.utils.MISSING
        
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)


class PaginationView(discord.ui.View):
    def __init__(self, current_page, max_pages):
        super().__init__(timeout=60)
        self.current_page = current_page
        self.max_pages = max_pages
        
        # Update buttons state
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = (self.current_page == 1)
        self.children[1].disabled = (self.current_page == self.max_pages)

    @discord.ui.button(label="⬅️ Önceki", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        # Re-fetch logs for new page
        # Getting the cog instance to call show_log_list logic is tricky from here without passing it.
        # But we can just use the DB directly here or duplicate logic slightly for simplicity, 
        # or better: attach the callback.
        # Actually, let's just re-implement the fetch here to avoid circular dep or passing complex objects.
        # Or better yet, make `show_log_list` static or standalone helper.
        
        # Simpler: just call the db directly here and edit message.
        await self.update_message(interaction)

    @discord.ui.button(label="Sonraki ➡️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        ITEMS_PER_PAGE = 10
        offset = (self.current_page - 1) * ITEMS_PER_PAGE
        logs = db.get_logs(ITEMS_PER_PAGE, offset)
        
        embed = discord.Embed(title="📜 Komut Logları", description=f"Sayfa {self.current_page}/{self.max_pages}", color=discord.Color.dark_grey())
        
        if not logs:
            embed.description += "\n\n*Henüz kayıtlı log yok.*"
        else:
            for log in logs:
                ts_val = int(log['timestamp'].replace(tzinfo=timezone.utc).timestamp())
                ts = f"<t:{ts_val}:R>"
                executor_mention = f"<@{log['executor_id']}>"
                cmd_type = log['command_type']
                embed.add_field(
                    name=f"#{log['id']} - {cmd_type}",
                    value=f"👤 {executor_mention} | 🕒 {ts}",
                    inline=False
                )
        
        await interaction.response.edit_message(embed=embed, view=self)

async def setup(bot):
    await bot.add_cog(Logger(bot))
