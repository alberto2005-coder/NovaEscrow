import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from src.database.manager import Database
from src.services.wallet import CryptoWalletManager
from src.ui.views import IniciarDealView

# Cargar variables de entorno
load_dotenv()

# Configurar intents del bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class EscrowBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inicializar y adjuntar servicios al bot para acceso global limpio
        self.db = Database()
        self.wallet_manager = CryptoWalletManager()

    async def setup_hook(self):
        # 1. Inicializar Base de Datos SQLite de manera asíncrona
        await self.db.init_db()
        
        # 2. Cargar Cogs de comandos modularizados
        await self.load_extension("src.cogs.escrow")
        await self.load_extension("src.cogs.balance")
        print("✅ Módulos de comandos (Cogs) cargados exitosamente")
        
        # 3. Registrar vistas persistentes de Discord
        self.add_view(IniciarDealView())
        print("✅ Vistas persistentes (Botones interactivos) registradas")

# Instanciar el Bot
bot = EscrowBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    print(f"📊 Conectado a {len(bot.guilds)} servidor(es)")

    # Sincronizar los comandos de barra diagonal (Slash Commands) con Discord
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comandos de barra diagonal sincronizados")
    except Exception as e:
        print(f"❌ Error al sincronizar comandos: {e}")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")

    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN no encontrado en el archivo .env")
        print("💡 Duplica el archivo .env.example como .env y rellena las credenciales.")
        exit(1)

    # Iniciar el bot de Discord
    bot.run(TOKEN)