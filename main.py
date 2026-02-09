import discord
import os
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# TOKEN'ı al
TOKEN = os.getenv('DISCORD_TOKEN')

# Intent'leri ayarla (Botun çalışması için gerekli izinler)
intents = discord.Intents.default()

intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!', # Prefix gereklidir ancak message_content kapalı olduğu için çalışmaz (Slash-only)
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Cogları (eklenti/modülleri) yükle
        # cogs klasöründeki her .py dosyasını yükler
        if os.path.exists('./cogs'):
            for filename in os.listdir('./cogs'):
                if filename.endswith('.py'):
                    try:
                        await self.load_extension(f'cogs.{filename[:-3]}')
                        print(f'Yüklendi: {filename}')
                    except Exception as e:
                        print(f'Yüklenemedi: {filename}. Hata: {e}')
        
        # Slash komutlarını senkronize et (opsiyonel ama önerilir)
        try:
            synced = await self.tree.sync()
            print(f"{len(synced)} slash komutu senkronize edildi.")
        except Exception as e:
            print(f"Komutlar senkronize edilemedi: {e}")

    async def on_ready(self):
        print(f'{self.user} olarak giriş yapıldı!')
        print(f'ID: {self.user.id}')
        await self.change_presence(activity=discord.Game(name="Yardım için !help"))

if __name__ == '__main__':
    if not TOKEN or TOKEN == "BURAYA_TOKEN_YAZILACAK":
        print("HATA: Lütfen .env dosyasına geçerli bir DISCORD_TOKEN girdiğinizden emin olun.")
    else:
        bot = MyBot()
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"Bot başlatılamadı: {e}")
