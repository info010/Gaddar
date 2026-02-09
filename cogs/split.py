import discord
from discord.ext import commands
from discord import app_commands
from utils.wrapper import log_execution
from utils.config import ConfigManager

# Dangerous permissions that should not be in splittable roles
DANGEROUS_PERMISSIONS = [
    "administrator",
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "mention_everyone",
    "manage_webhooks",
    "manage_expressions"
]

class Split(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="splitcomplate", description="Split işlemini tamamlar ve ilgili rolü temizler.")
    @app_commands.describe(role_input="Silinecek rolü seçin (Yalnızca güvenli roller listelenir)")
    @app_commands.rename(role_input="role")
    @log_execution("splitcomplate")
    async def splitcomplete(self, interaction: discord.Interaction, role_input: str):
        # 1. Permission Check
        user = interaction.user
        if not isinstance(user, discord.Member):
            user = interaction.guild.get_member(user.id)

        if not ConfigManager.can_use_command(user, "splitcomplate"):
             await interaction.response.send_message("⛔ Bu komutu kullanma yetkiniz yok.", ephemeral=True)
             return {"status": "UNAUTHORIZED", "reason": "User/Role not in config whitelist"}

        # Resolve Role
        # Autocomplete sends ID as string value
        role = interaction.guild.get_role(int(role_input)) if role_input.isdigit() else None
        
        if not role:
            # Fallback: Try name match if user typed manually
            role = discord.utils.get(interaction.guild.roles, name=role_input)
            
        if not role:
             await interaction.response.send_message(f"❌ Rol bulunamadı: '{role_input}'", ephemeral=True)
             return {"status": "FAILED", "reason": "Role not found"}

        # 2. Safety Check
        if role.position >= interaction.guild.me.top_role.position:
             await interaction.response.send_message("⛔ Bu rolü yönetemem (Rol benim yetkimden yüksek veya eşit).", ephemeral=True)
             return {"status": "FAILED", "reason": "Role hierarchy issue"}
             
        # Check permissions
        perms = role.permissions
        if perms.administrator:
            await interaction.response.send_message("⛔ **Yönetici (Administrator)** rolü bu komutla silinemez.", ephemeral=True)
            return {"status": "ABORTED", "reason": "Target role is admin"}

        # Check dangerous permissions
        dangerous_found = []
        for p_name in DANGEROUS_PERMISSIONS:
            if getattr(perms, p_name, False):
                dangerous_found.append(p_name)
        
        if dangerous_found:
             d_list = ", ".join(dangerous_found)
             await interaction.response.send_message(f"⛔ Bu rol şu kritik izinlere sahip olduğu için güvenli silinemez: `{d_list}`", ephemeral=True)
             return {"status": "ABORTED", "reason": f"Dangerous permissions found: {d_list}"}
             
        # 3. Execute
        role_name = role.name
        role_id = role.id
        
        try:
            await role.delete(reason=f"Split Complete: {interaction.user}")
            await interaction.response.send_message(f"✅ **{role_name}** rolü başarıyla silindi ve split tamamlandı.", ephemeral=True)
            return {
                "role_name": role_name,
                "role_id": role_id,
                "action": "deleted",
                "status": "SUCCESS"
            }
        except discord.Forbidden:
            await interaction.response.send_message("⛔ Rolü silmek için yetkim yetersiz.", ephemeral=True)
            return {"status": "FAILED", "reason": "Forbidden"}
        except Exception as e:
            await interaction.response.send_message(f"❌ Bir hata oluştu: {e}", ephemeral=True)
            raise e

    @splitcomplete.autocomplete('role_input')
    async def splitcomplete_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        roles = interaction.guild.roles
        choices = []
        
        current_lower = current.lower()
        
        for role in roles:
            # Basic filters
            if role.is_default(): continue # @everyone
            if role.managed: continue # Bot integration roles
            
            # Permission filters
            perms = role.permissions
            if perms.administrator: continue
            
            # Check dangerous perms
            is_dangerous = False
            for p_name in DANGEROUS_PERMISSIONS:
                 if getattr(perms, p_name, False):
                     is_dangerous = True
                     break
            if is_dangerous: continue
            
            # Match current input
            if current_lower in role.name.lower():
                choices.append(app_commands.Choice(name=role.name, value=str(role.id)))
                if len(choices) >= 25: break
        
        return choices

async def setup(bot):
    await bot.add_cog(Split(bot))
