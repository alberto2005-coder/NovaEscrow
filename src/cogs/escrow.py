import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from src.ui.views import IniciarDealView, CRIPTOMONEDAS

class EscrowCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configurar canal de deals (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db

        embed = discord.Embed(
            title="🔒 Sistema de Escrow de Criptomonedas",
            description="**Sistema de escrow automatizado con blockchain real**\n\n"
                       "**💎 Criptomonedas Soportadas:**\n"
                       f"• {CRIPTOMONEDAS['BTC']['emoji']} Bitcoin (BTC)\n"
                       f"• {CRIPTOMONEDAS['ETH']['emoji']} Ethereum (ETH)\n"
                       f"• {CRIPTOMONEDAS['SOL']['emoji']} Solana (SOL)\n"
                       f"• {CRIPTOMONEDAS['LTC']['emoji']} Litecoin (LTC)\n"
                       f"• {CRIPTOMONEDAS['USDT']['emoji']} Tether ERC-20 (USDT)\n"
                       f"• {CRIPTOMONEDAS['USDC']['emoji']} USD Coin ERC-20 (USDC)\n\n"
                       "**✅ Características:**\n"
                       "• 🔒 Wallets de escrow reales\n"
                       "• 🤖 Verificación automática de blockchain\n"
                       "• 💸 Liberación automatizada de fondos\n"
                       "• ⚖️ Sistema de disputas con mediación\n"
                       "• ↩️ Función de reembolso\n\n"
                       "**¡Haz clic para comenzar!**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        view = IniciarDealView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ Canal configurado.", ephemeral=True)

    @app_commands.command(name="cerrar", description="Cerrar ticket (Participantes/Admin)")
    async def cerrar_ticket(self, interaction: discord.Interaction):
        db = self.bot.db
        ticket_data = await db.get_ticket(interaction.channel.id)

        if not ticket_data:
            await interaction.response.send_message("❌ Este no es un ticket válido.", ephemeral=True)
            return

        if interaction.user.id not in [ticket_data['creator_id'], ticket_data.get('counterparty_id')]:
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ Solo participantes o admin pueden cerrar.", ephemeral=True)
                return

        await interaction.response.send_message("🗑️ Cerrando ticket...", ephemeral=True)
        await db.delete_ticket(interaction.channel.id)
        await interaction.channel.delete(reason=f"Cerrado por {interaction.user}")

    @app_commands.command(name="info", description="Información del bot")
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="ℹ️ Bot de Escrow Blockchain",
            description="Sistema de escrow con integración blockchain real.\n\n**💎 Criptomonedas Soportadas:**",
            color=discord.Color.blue()
        )

        for codigo, info_crypto in CRIPTOMONEDAS.items():
            embed.add_field(name=f"{info_crypto['emoji']} {codigo}", value=info_crypto['nombre'], inline=True)

        embed.add_field(
            name="📊 Comandos Disponibles",
            value="• `/setup` - Configurar canal de deals (Solo Admins)\n"
                  "• `/cerrar` - Cerrar y borrar ticket actual\n"
                  "• `/info` - Ver información general del bot\n"
                  "• `/stats` - Estadísticas globales del servidor\n"
                  "• `/perfil` - Ver perfil y reputación de trading\n"
                  "• `/balance` - Ver tus fondos en el monedero interno\n"
                  "• `/depositar` - Obtener dirección para depositar fondos\n"
                  "• `/retirar` - Retirar tus fondos a una billetera externa",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="stats", description="Estadísticas del servidor")
    async def stats(self, interaction: discord.Interaction):
        db = self.bot.db
        stats_data = await db.get_guild_stats(interaction.guild.id)

        embed = discord.Embed(
            title="📊 Estadísticas",
            description=f"**Servidor:** {interaction.guild.name}",
            color=discord.Color.gold()
        )

        embed.add_field(name="📝 Total", value=stats_data['total_tickets'], inline=True)
        embed.add_field(name="✅ Completados", value=stats_data['completed_tickets'], inline=True)
        embed.add_field(name="🔄 Activos", value=stats_data['active_tickets'], inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="perfil", description="Ver tu perfil de trading")
    async def perfil(self, interaction: discord.Interaction, usuario: discord.User = None):
        db = self.bot.db
        target_user = usuario or interaction.user
        profile = await db.get_user_profile(target_user.id, interaction.guild.id)

        stars_display = "⭐" * int(profile['average_rating'])
        if profile['average_rating'] > int(profile['average_rating']):
            stars_display += "½"

        embed = discord.Embed(
            title=f"👤 Perfil de {target_user.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="📊 Trades Completados", value=profile['total_trades'], inline=True)
        embed.add_field(name="💰 Volumen Total", value=f"${profile['total_volume_usd']:,.2f}", inline=True)
        embed.add_field(name="⭐ Calificación", value=f"{stars_display} ({profile['average_rating']:.1f}/5.0)", inline=True)
        embed.add_field(name="📝 Total Opiniones", value=profile['total_ratings'], inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(EscrowCog(bot))
