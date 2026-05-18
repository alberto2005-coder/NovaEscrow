import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from src.ui.views import (
    SeleccionarCriptoDepositoView,
    RetiroModal,
    CRIPTOMONEDAS
)

class BalanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="Ver tu balance interno")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db

        balances = await db.get_all_balances(interaction.user.id, interaction.guild.id)

        embed = discord.Embed(
            title="💼 Tu Balance Interno",
            description=f"Balance de {interaction.user.mention}",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )

        if not balances:
            embed.add_field(name="Estado", value="No tienes fondos depositados", inline=False)
        else:
            for bal in balances:
                cripto_info = CRIPTOMONEDAS.get(bal['currency'], {})
                emoji = cripto_info.get('emoji', '')
                embed.add_field(
                    name=f"{emoji} {bal['currency']}", 
                    value=f"`{bal['amount']:.8f}`", 
                    inline=True
                )

        embed.set_footer(text="Usa /depositar y /retirar para gestionar tus fondos")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="depositar", description="Depositar fondos a tu balance interno")
    async def depositar(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "💳 Selecciona la criptomoneda para depositar:",
            view=SeleccionarCriptoDepositoView(),
            ephemeral=True
        )

    @app_commands.command(name="retirar", description="Retirar fondos de tu balance interno")
    async def retirar(self, interaction: discord.Interaction):
        db = self.bot.db
        balances = await db.get_all_balances(interaction.user.id, interaction.guild.id)

        if not balances:
            await interaction.response.send_message(
                "❌ No tienes fondos para retirar. Usa `/balance` para verificar.",
                ephemeral=True
            )
            return

        options = []
        for bal in balances:
            cripto_info = CRIPTOMONEDAS.get(bal['currency'], {})
            options.append(
                discord.SelectOption(
                    label=f"{bal['currency']} - {bal['amount']:.8f}",
                    value=bal['currency'],
                    emoji=cripto_info.get('emoji', '💰')
                )
            )

        view = discord.ui.View(timeout=180)
        select = discord.ui.Select(placeholder="Selecciona la criptomoneda a retirar", options=options)

        async def select_callback(interaction: discord.Interaction):
            currency = select.values[0]
            modal = RetiroModal(currency)
            await interaction.response.send_modal(modal)

        select.callback = select_callback
        view.add_item(select)

        await interaction.response.send_message(
            "💸 Selecciona la criptomoneda que deseas retirar:",
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(BalanceCog(bot))
