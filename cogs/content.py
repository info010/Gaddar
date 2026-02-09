import discord
from discord.ext import commands
from discord import app_commands
from utils.wrapper import log_execution
from utils.config import ConfigManager
from utils.database import db

# --- Shared UI Components ---

class RegisterModal(discord.ui.Modal, title="Content Kayıt"):
    role_input = discord.ui.TextInput(
        label="Hangi Sırada/Rolde Oynayacaksınız?",
        placeholder="Örn: Earthrune veya Row 1",
        min_length=1,
        max_length=50
    )

    def __init__(self, message_id):
        super().__init__()
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        # We process registration logic
        # Constraint: User cannot register if already registered.
        
        content = db.get_content_by_message_id(self.message_id)
        if not content:
            await interaction.response.send_message("❌ Bu içerik aktif değil.", ephemeral=True)
            return

        signups = content['signups']
        user_id = interaction.user.id
        role_text = self.role_input.value
        
        # Check duplicate
        if any(s['user_id'] == user_id for s in signups):
            await interaction.response.send_message("❌ Zaten kaydınız var. Önce kaydı silin.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        signups.append({
            'user_id': user_id,
            'name': interaction.user.display_name,
            'role': role_text
        })
        msg = f"✅ Kaydınız alındı: **{role_text}**"

        db.update_content_signups(self.message_id, signups)
        await ContentView.update_embed(interaction, self.message_id)
        await interaction.followup.send(msg, ephemeral=True)

class TemplateModal(discord.ui.Modal, title="Albion Tablo Şablonu"):
    roles_input = discord.ui.TextInput(
        label="Roller (Virgülle ayırın)",
        placeholder="Kılıç, Balta, Tank, Healer, Support...",
        style=discord.TextStyle.paragraph,
        min_length=2,
        max_length=2000
    )

    def __init__(self, template_name):
        super().__init__()
        self.template_name = template_name

    async def on_submit(self, interaction: discord.Interaction):
        raw_text = self.roles_input.value
        # Parse by comma
        parsed_rows = [r.strip() for r in raw_text.split(',') if r.strip()]
        
        if not parsed_rows:
            await interaction.response.send_message("❌ Geçerli bir liste girmediniz.", ephemeral=True)
            return
            
        db.save_template(self.template_name, parsed_rows)
        await interaction.response.send_message(f"✅ Tablo şablonu **{self.template_name}** kaydedildi ({len(parsed_rows)} satır).", ephemeral=True)


class DescriptionModal(discord.ui.Modal, title="İçerik Açıklaması"):
    description_input = discord.ui.TextInput(
        label="Açıklama",
        placeholder="Örn: 6 kişi olmadan başlamaz. Min IP 1200...",
        style=discord.TextStyle.paragraph,
        min_length=1,
        max_length=1000,
        required=False
    )

    def __init__(self, name, template_name):
        super().__init__()
        self.name = name
        self.template_name = template_name

    async def on_submit(self, interaction: discord.Interaction):
        template = db.get_template(self.template_name)
        if not template:
            await interaction.response.send_message("❌ Şablon bulunamadı.", ephemeral=True)
            return

        description = self.description_input.value or ""
        data = [[] for _ in template['roles']]
        
        # Create Embed
        embed = discord.Embed(title=f"⚔️ {self.name} - (Oluşturuluyor...)", color=discord.Color.gold())
        embed.set_footer(text=f"Şablon: {self.template_name}")
        
        try:
             table_str = ContentView._create_table_str(template['roles'], data)
             desc_text = f"{description}\n\n```prolog\n{table_str}\n```" if description else f"```prolog\n{table_str}\n```"
             embed.description = desc_text
        except: embed.description = "Hata"
        embed.add_field(name="📋 Kayıt Bekleyenler", value="*Kimse kayıt olmadı*", inline=False)

        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        
        # Save to DB - Returns New ID
        new_id = db.create_content(msg.id, interaction.channel.id, self.name, self.template_name, data, description)
        
        # Update Embed with Real ID
        new_title = f"⚔️ {self.name} - {new_id}"
        embed.title = new_title
        embed.set_footer(text=f"Şablon: {self.template_name} | ID: {new_id}")
        await msg.edit(embed=embed, view=ContentView(msg.id))

class ContentView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="Kayıt Ol", style=discord.ButtonStyle.success, custom_id="content_register")
    async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegisterModal(interaction.message.id))

    @discord.ui.button(label="Kaydı Sil", style=discord.ButtonStyle.danger, custom_id="content_unregister")
    async def unregister_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        message_id = interaction.message.id
        content = db.get_content_by_message_id(message_id)
        
        if not content:
            await interaction.followup.send("❌ İçerik bulunamadı.", ephemeral=True)
            return

        signups = content['signups']
        user_id = interaction.user.id
        new_signups = [s for s in signups if s['user_id'] != user_id]
        
        if len(new_signups) == len(signups):
            await interaction.followup.send("⚠️ Zaten kaydınız yok.", ephemeral=True)
        else:
            db.update_content_signups(message_id, new_signups)
            await ContentView.update_embed(interaction, message_id)
            await interaction.followup.send("✅ Kaydınız silindi.", ephemeral=True)

    @staticmethod
    def _create_table_str(template_rows, assignments):
        w_role = 15
        w_player = 15
        
        is_list_data = isinstance(assignments, list)
        
        # Calculate Widths
        for i, row in enumerate(template_rows):
            # Handle string or dict (legacy)
            r_name = row['name'] if isinstance(row, dict) else str(row)
            
            w_role = max(w_role, len(r_name))
            
            assigned = []
            if is_list_data:
                if i < len(assignments): assigned = assignments[i]
            else:
                assigned = assignments.get(r_name, [])
            
            player_str = ", ".join(assigned) if assigned else "-"
            w_player = max(w_player, len(player_str))
            
        w_player = min(w_player, 30) # Cap player width
        
        header = f"{'ROLE':<{w_role}} | {'PLAYER':<{w_player}}"
        separator = "-" * len(header)
        lines = [header, separator]
        
        for i, row in enumerate(template_rows):
            r_name = row['name'] if isinstance(row, dict) else str(row)
            
            assigned = []
            if is_list_data:
                if i < len(assignments): assigned = assignments[i]
            else:
                assigned = assignments.get(r_name, [])
                
            player = ", ".join(assigned) if assigned else "-"
            
            d_role = (r_name[:w_role-2] + "..") if len(r_name) > w_role else r_name
            d_player = (player[:w_player-2] + "..") if len(player) > w_player else player
            
            line = f"{d_role:<{w_role}} | {d_player:<{w_player}}"
            lines.append(line)
            
        return "\n".join(lines)

    @staticmethod
    async def update_embed(interaction: discord.Interaction, message_id: int):
        # Use Message ID lookup
        content = db.get_content_by_message_id(message_id)
        if not content: return # Deleted from DB
        
        # Format Title with Name - ID (Integer ID)
        title = f"⚔️ {content['name']} - {content['id']}"
        embed = discord.Embed(title=title, color=discord.Color.gold())
        embed.set_footer(text=f"Şablon: {content['template_name']} | ID: {content['id']}")
        
        data = content['data']
        signups = content['signups']
        description = content.get('description', "")
        template = db.get_template(content['template_name'])
        
        rows = []
        if template:
             rows = template['roles']
        else:
             # Legacy
             if isinstance(data, dict): rows = list(data.keys())
        
        if not rows and not isinstance(data, dict):
             embed.description = "⚠️ Şablon verisi bozulmuş veya silinmiş."
        else:
             try:
                 table_str = ContentView._create_table_str(rows, data)
                 full_desc = f"{description}\n\n```prolog\n{table_str}\n```" if description else f"```prolog\n{table_str}\n```"
                 
                 if len(full_desc) < 3900: embed.description = full_desc
                 else: embed.description = f"{description[:500]}...\n⚠️ Tablo/Açıklama çok uzun.\n```prolog\n{table_str[:1500]}...\n```"
             except Exception as e:
                 embed.description = f"Hata: {e}"

        if signups:
            sl = []
            for s in signups:
                sl.append(f"• <@{s['user_id']}> ({s['role']})")
            st = "\n".join(sl)
            if len(st) > 1000: st = st[:950] + "..."
            embed.add_field(name="📋 Kayıt Bekleyenler", value=st, inline=False)
        else:
            embed.add_field(name="📋 Kayıt Bekleyenler", value="*Kimse kayıt olmadı*", inline=False)

        try:
            # Try editing the message attached to interaction OR fetch via channel
            target_msg = None
            if interaction.message and interaction.message.id == message_id:
                target_msg = interaction.message
            else:
                guild = interaction.guild
                channel = guild.get_channel(content['channel_id'])
                if channel:
                    try:
                        target_msg = await channel.fetch_message(message_id)
                    except: pass
            
            if target_msg:
                if target_msg.embeds and target_msg.embeds[0].title != title:
                    embed.title = title
                await target_msg.edit(embed=embed)
        except Exception as e:
            print(f"Embed update error: {e}")



class Content(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    content_group = app_commands.Group(name="content", description="İçerik Yönetim Sistemi")
    template_group = app_commands.Group(name="template", description="Şablon yönetimi", parent=content_group)

    @template_group.command(name="create")
    async def template_create(self, interaction: discord.Interaction, name: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return
        await interaction.response.send_modal(TemplateModal(name))

    @template_group.command(name="edit")
    async def template_edit(self, interaction: discord.Interaction, name: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return
        template = db.get_template(name)
        if not template:
            await interaction.response.send_message("❌ Şablon bulunamadı.", ephemeral=True)
            return
            
        # Pre-fill (legacy dict or new string list)
        lines = []
        for r in template['roles']:
            if isinstance(r, dict): lines.append(r['name']) # Legacy: just name, drop build
            else: lines.append(str(r))
            
        modal = TemplateModal(name)
        modal.roles_input.default = ", ".join(lines)
        await interaction.response.send_modal(modal)

    @template_group.command(name="remove")
    async def template_remove(self, interaction: discord.Interaction, name: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return
        db.delete_template(name)
        await interaction.response.send_message(f"✅ Şablon **{name}** silindi.", ephemeral=True)

    @template_edit.autocomplete('name')
    @template_remove.autocomplete('name')
    async def template_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        templates = db.get_all_templates()
        return [app_commands.Choice(name=t, value=t) for t in templates if current.lower() in t.lower()][:25]

    @content_group.command(name="create", description="Yeni içerik oluştur")
    @app_commands.describe(name="İçerik Başlığı", template_name="Şablon")
    @log_execution("content_create")
    async def create(self, interaction: discord.Interaction, name: str, template_name: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return

        template = db.get_template(template_name)
        if not template:
            await interaction.response.send_message("❌ Şablon bulunamadı.", ephemeral=True)
            return

        await interaction.response.send_modal(DescriptionModal(name, template_name))

    @content_group.command(name="edit", description="İçerik düzenle/ata")
    @app_commands.describe(
        content_ref="İçerik Seçiniz (İsim veya ID)",
        role="Şablondaki Rol (Otomatik Tamamlama)",
        player="Kayıtlı Oyuncu (Otomatik Tamamlama)"
    )
    @log_execution("content_edit")
    async def edit(self, interaction: discord.Interaction, content_ref: str, role: str, player: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return

        # Resolve Content (content_ref is Integer ID or String)
        content = None
        
        if content_ref.isdigit():
             content = db.get_content(int(content_ref))
        
        if not content:
             # Search by name in active contents of channel (or latest)
             actives = db.get_active_contents_by_channel(interaction.channel_id)
             # Try exact name match
             match = next((c for c in actives if c['name'] == content_ref), None)
             if match: content = match
             # Try ID match from string again
             if not content and " - " in content_ref:
                 try: 
                     cid = int(content_ref.split(" - ")[-1])
                     content = db.get_content(cid)
                 except: pass
        
        if not content:
            await interaction.response.send_message("❌ İçerik bulunamadı (ID veya İsim kontrol edin).", ephemeral=True)
            return

        # Core Edit Logic
        template = db.get_template(content['template_name'])
        data = content['data']
        
        entry = player.strip()
        
        # Check if player already in table (Prevent Multi-Role)
        # Skip check if clearing (-)
        if entry != "-" and entry:
             for slot_list in data:
                 # slot_list is a list of strings
                 if any(p.lower() == entry.lower() for p in slot_list):
                      await interaction.response.send_message(f"❌ **{entry}** zaten tabloda bir role atanmış! Önce listeden çıkarmalısınız (/content kick).", ephemeral=True)
                      return

        # Find matches
        matches = []
        for i, r in enumerate(template['roles']):
            r_name = r['name'] if isinstance(r, dict) else str(r)
            if role.lower() in r_name.lower(): matches.append(i)
        matches.sort()
        
        if not matches:
             await interaction.response.send_message("❌ Rol bulunamadı.", ephemeral=True)
             return

        # Parse player
        
        # If entry empty or "-", clean slots
        if entry == "-" or not entry:
             count = 0
             for i in matches:
                 if i < len(data) and data[i]:
                     data[i] = []
                     count += 1
             msg = f"✅ Temizlendi: {count} slot."
        else:
             placed = False
             for i in matches:
                 if i < len(data):
                     if not data[i]:
                         data[i] = [entry]
                         placed = True
                         break
             if placed: 
                 msg = f"✅ Atandı: {entry} -> {role}"
                 
                 # Remove from signups automatically
                 signups = content['signups']
                 original_len = len(signups)
                 new_signups = [s for s in signups if s['name'].lower() != entry.lower()]
                 
                 if len(new_signups) < original_len:
                     db.update_content_signups(content['message_id'], new_signups)
                     
             else: msg = "⚠️ Slotlar dolu!"

        db.update_content_data(content['message_id'], data)
        await ContentView.update_embed(interaction, content['message_id'])
        await interaction.response.send_message(msg, ephemeral=True)

    @content_group.command(name="unregister", description="Oyuncuyu tablodan (slotlardan) sil")
    @app_commands.describe(content_ref="İçerik", player="Tablodaki Oyuncu")
    @log_execution("content_unregister")
    async def unregister(self, interaction: discord.Interaction, content_ref: str, player: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return

        content = self._resolve_content(interaction, content_ref)
        if not content:
            await interaction.response.send_message("❌ İçerik bulunamadı.", ephemeral=True)
            return

        data = content['data']
        entry = player.strip()
        removed_count = 0
        
        for slot_list in data:
            original_len = len(slot_list)
            new_list = [p for p in slot_list if p.lower() != entry.lower()]
            if len(new_list) < original_len:
                slot_list[:] = new_list
                removed_count += (original_len - len(new_list))

        if removed_count > 0:
            db.update_content_data(content['message_id'], data)
            await ContentView.update_embed(interaction, content['message_id'])
            await interaction.response.send_message(f"✅ **{entry}** tablodan çıkarıldı.", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ **{entry}** tabloda bulunamadı.", ephemeral=True)

    @content_group.command(name="register", description="Oyuncuyu ön kayıt (bekleme) listesine ekle")
    @app_commands.describe(content_ref="İçerik", player="Oyuncu İsmi", role="Rol")
    @log_execution("content_register")
    async def register(self, interaction: discord.Interaction, content_ref: str, player: str, role: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return

        content = self._resolve_content(interaction, content_ref)
        if not content:
            await interaction.response.send_message("❌ İçerik bulunamadı.", ephemeral=True)
            return

        signups = content['signups']
        if any(s['name'].lower() == player.lower() for s in signups):
             await interaction.response.send_message("❌ Bu isimde bir kayıt zaten var.", ephemeral=True)
             return

        signups.append({
            'user_id': 0,
            'name': player,
            'role': role
        })
        
        db.update_content_signups(content['message_id'], signups)
        await ContentView.update_embed(interaction, content['message_id'])
        await interaction.response.send_message(f"✅ **{player}** ön kayıt listesine eklendi.", ephemeral=True)

    @content_group.command(name="kick", description="Oyuncuyu ön kayıt (bekleme) listesinden sil")
    @app_commands.describe(content_ref="İçerik", player="Listeden Oyuncu")
    @log_execution("content_kick")
    async def kick(self, interaction: discord.Interaction, content_ref: str, player: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return

        content = self._resolve_content(interaction, content_ref)
        if not content:
            await interaction.response.send_message("❌ İçerik bulunamadı.", ephemeral=True)
            return

        signups = content['signups']
        original_len = len(signups)
        new_signups = [s for s in signups if s['name'].lower() != player.lower()]
        
        if len(new_signups) < original_len:
            db.update_content_signups(content['message_id'], new_signups)
            await ContentView.update_embed(interaction, content['message_id'])
            await interaction.response.send_message(f"✅ **{player}** ön kayıt listesinden silindi.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Oyuncu listede bulunamadı.", ephemeral=True)

    @content_group.command(name="remove", description="İçerik sil (Veritabanından)")
    @app_commands.describe(content_ref="Silinecek İçerik")
    async def remove(self, interaction: discord.Interaction, content_ref: str):
        if not ConfigManager.can_use_command(interaction.user, "content"):
             await interaction.response.send_message("⛔ Yetkiniz yok.", ephemeral=True)
             return
        
        content = self._resolve_content(interaction, content_ref)
        if not content:
             await interaction.response.send_message("❌ İçerik çözümlenemedi.", ephemeral=True)
             return
             
        db.delete_content(content['id'])
        await interaction.response.send_message(f"✅ İçerik (ID: {content['id']}) veritabanından silindi.", ephemeral=True)

    def _resolve_content(self, interaction, content_ref):
        if content_ref.isdigit():
             return db.get_content(int(content_ref))
        
        actives = db.get_active_contents_by_channel(interaction.channel_id)
        match = next((c for c in actives if c['name'] == content_ref), None)
        if match: return match
        
        if " - " in content_ref:
             try: return db.get_content(int(content_ref.split(" - ")[-1]))
             except: pass
        return None

    # Autocompletes
    @create.autocomplete('template_name')
    async def template_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        templates = db.get_all_templates()
        return [app_commands.Choice(name=t, value=t) for t in templates if current.lower() in t.lower()][:25]

    @edit.autocomplete('content_ref')
    @remove.autocomplete('content_ref')
    @kick.autocomplete('content_ref')
    @unregister.autocomplete('content_ref')
    @register.autocomplete('content_ref')
    async def content_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        actives = db.get_active_contents_by_channel(interaction.channel_id)
        choices = []
        for c in actives:
            # Format: "Name - ID"
            display = f"{c['name']} - {c['id']}"
            if current.lower() in display.lower():
                choices.append(app_commands.Choice(name=display, value=str(c['id'])))
        return choices[:25]

    @edit.autocomplete('role')
    @register.autocomplete('role')
    async def role_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        content_ref = getattr(interaction.namespace, 'content_ref', None) 
        roles = []
        
        if content_ref:
             content = self._resolve_content(interaction, content_ref)
             if content:
                 t = db.get_template(content['template_name'])
                 if t:
                     for r in t['roles']:
                         if isinstance(r, dict): roles.append(r['name'])
                         else: roles.append(str(r))
        
        return [app_commands.Choice(name=r, value=r) for r in roles if current.lower() in r.lower()][:25]

    @edit.autocomplete('player')
    @kick.autocomplete('player')
    async def signup_player_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        # List players from SIGNUPS
        content_ref = getattr(interaction.namespace, 'content_ref', None)
        players = []
        
        if content_ref:
             content = self._resolve_content(interaction, content_ref)
             if content:
                 for s in content['signups']:
                     players.append(s['name']) 
        
        return [app_commands.Choice(name=p, value=p) for p in players if current.lower() in p.lower()][:25]

    @unregister.autocomplete('player')
    async def table_player_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        # List players assigned in TABLE
        content_ref = getattr(interaction.namespace, 'content_ref', None)
        players = set()
        
        if content_ref:
             content = self._resolve_content(interaction, content_ref)
             if content:
                 data = content['data'] # List of lists
                 for slot_list in data:
                     for p in slot_list:
                         players.add(p)
                         
        return [app_commands.Choice(name=p, value=p) for p in players if current.lower() in p.lower()][:25]


    async def cog_load(self):
        # Persistent Views only
        self.bot.add_view(ContentView(None))

async def setup(bot):
    await bot.add_cog(Content(bot))
