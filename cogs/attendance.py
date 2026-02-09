import discord
import os
from discord.ext import commands
from discord import app_commands
from utils.wrapper import log_execution
from utils.config import ConfigManager

# Tehlikeli izinlerin listesi (Bunlar varsa uyarı verilecek)
DANGEROUS_PERMISSIONS = [
    "ban_members",
    "kick_members",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "mention_everyone",
    "manage_webhooks",
    "manage_expressions"
]

class ConfirmView(discord.ui.View):
    def __init__(self, timeout=30):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Onayla ve Devam Et", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="İptal", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.defer()

class Attendance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="attendance", description="Ses kanalındaki kullanıcılara rol verir.")
    @app_commands.describe(
        channel="Hedef ses kanalı",
        role_name="Verilecek rolün adı (Yoksa oluşturulur)"
    )
    @log_execution("attendance")
    async def attendance(self, interaction: discord.Interaction, channel: discord.VoiceChannel, role_name: str):
        # 1. Whitelist Kontrolü (Yeni ConfigManager ile)
        # Interaction.user normalde Member döner ama emin olalım
        user = interaction.user
        if not isinstance(user, discord.Member):
            user = interaction.guild.get_member(user.id)

        if not ConfigManager.can_use_command(user, "attendance"):
             await interaction.response.send_message("⛔ Bu komutu kullanma yetkiniz yok.", ephemeral=True)
             return {"status": "UNAUTHORIZED", "reason": "User/Role not in config whitelist"}

        # 2. Ses kanalı boş mu?
        if not channel.members:
            await interaction.response.send_message(f"⚠️ {channel.mention} kanalında kimse yok.", ephemeral=True)
            return {"status": "ABORTED", "reason": "Empty channel"}

        guild = interaction.guild
        target_role = discord.utils.get(guild.roles, name=role_name)
        role_created = False

        # 3. Rol İşlemleri ve Güvenlik Kontrolü
        if target_role:
            # Rol zaten varsa izinleri kontrol et
            permissions = target_role.permissions
            
            # KESİN YASAK: Administrator
            if permissions.administrator:
                await interaction.response.send_message("⛔ **Yönetici (Administrator)** yetkisine sahip bir rol verilemez.", ephemeral=True)
                return {"status": "ABORTED", "reason": "Target role is admin"}

            # UYARI GEREKTİREN: Tehlikeli izinler
            dangerous_found = [perm for perm, value in permissions if value and perm in DANGEROUS_PERMISSIONS]
            
            if dangerous_found:
                d_list = ", ".join(dangerous_found)
                view = ConfirmView()
                await interaction.response.send_message(
                    f"⚠️ **DİKKAT!** '{role_name}' rolü şu kritik izinlere sahip: `{d_list}`.\n"
                    "Yine de bu rolü ses kanalındaki herkese vermek istiyor musunuz?",
                    view=view,
                    ephemeral=True
                )
                await view.wait()
                
                if view.value is None:
                    await interaction.followup.send("Zaman aşımı. İşlem iptal edildi.", ephemeral=True)
                    return {"status": "CANCELLED", "reason": "Timeout on dangerous role confirmation"}
                elif view.value is False:
                    await interaction.followup.send("İşlem iptal edildi.", ephemeral=True)
                    return {"status": "CANCELLED", "reason": "User cancelled dangerous role confirmation"}
                # Onay verildiyse devam et
                
        else:
            # Rol yoksa oluştur (Varsayılan güvenli izinlerle)
            try:
                # defer yanıtı beklet, çünkü rol oluşturma biraz sürebilir
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                    
                target_role = await guild.create_role(name=role_name, reason=f"Attendance komutu: {interaction.user}")
                role_created = True
                await interaction.followup.send(f"✅ '{role_name}' rolü oluşturuldu.", ephemeral=True)
            except discord.Forbidden:
                if not interaction.response.is_done():
                    await interaction.response.send_message("⛔ Rol oluşturmak için yetkim yetersiz.", ephemeral=True)
                else:
                    await interaction.followup.send("⛔ Rol oluşturmak için yetkim yetersiz.", ephemeral=True)
                return {"status": "FAILED", "reason": "Missing permissions to create role"}

        # defer çağrılmadıysa çağır (rol var ve güvenliyse buraya düşer)
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # 4. Rolü Dağıtma
        given_count = 0
        failed_count = 0
        
        members = channel.members
        processed_users = [] # Log için kullanıcı listesi
        
        status_msg = await interaction.followup.send(f"⏳ {len(members)} kişiye rol veriliyor...", ephemeral=True)

        for member in members:
            if member.bot: # Botları atla
                continue
                
            if target_role in member.roles:
                continue # Zaten rolü varsa geç

            try:
                await member.add_roles(target_role, reason=f"Attendance: {interaction.user} tarafından verildi.")
                given_count += 1
                processed_users.append({"id": member.id, "name": member.name})
            except discord.Forbidden:
                failed_count += 1
            except Exception as e:
                print(f"Hata ({member}): {e}")
                failed_count += 1

        # Sonuç mesajı
        result_message = f"✅ İşlem Tamamlandı!\n" \
                         f"📂 Rol: {target_role.mention}\n" \
                         f"🔊 Kanal: {channel.mention}\n" \
                         f"👤 Verilen Kişi: {given_count}\n"
        
        if role_created:
            result_message += "✨ (Yeni rol oluşturuldu)"
        
        if failed_count > 0:
            result_message += f"\n❌ Başarısız: {failed_count} (Yetkim yetmemiş olabilir)"

        await interaction.followup.send(result_message, ephemeral=True)
        
        # LOGLAMA İÇİN DEĞER DÖNÜYORUZ
        return {
            "channel_id": channel.id,
            "channel_name": channel.name,
            "role_id": target_role.id,
            "role_name": target_role.name,
            "role_created": role_created,
            "given_count": given_count,
            "failed_count": failed_count,
            "users": processed_users, 
            "result_message": result_message
        }

async def setup(bot):
    await bot.add_cog(Attendance(bot))
