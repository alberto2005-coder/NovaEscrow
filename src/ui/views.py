import discord
import asyncio
from datetime import datetime
import secrets
import os
from src.utils.logging import enviar_log

CRIPTOMONEDAS = {
    "BTC": {"nombre": "Bitcoin", "emoji": "₿"},
    "ETH": {"nombre": "Ethereum", "emoji": "Ξ"},
    "SOL": {"nombre": "Solana", "emoji": "◎"},
    "LTC": {"nombre": "Litecoin", "emoji": "Ł"},
    "USDT": {"nombre": "Tether (ERC-20)", "emoji": "₮"},
    "USDC": {"nombre": "USD Coin (ERC-20)", "emoji": "$"}
}

class IniciarDealView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Iniciar Deal", style=discord.ButtonStyle.green, custom_id="iniciar_deal")
    async def iniciar_deal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        db = interaction.client.db
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="📋 TICKETS ACTIVOS")
        if not category:
            category = await guild.create_category("📋 TICKETS ACTIVOS")

        ticket_number = await db.get_next_ticket_number(guild.id)
        ticket_name = f"ticket-{ticket_number}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await category.create_text_channel(ticket_name, overwrites=overwrites)
        await db.create_ticket(channel.id, guild.id, interaction.user.id, ticket_number)

        embed = discord.Embed(
            title="🎫 Nuevo Ticket de Escrow",
            description=f"**Bienvenido {interaction.user.mention}**\n\n"
                       "Este es tu ticket privado para realizar una transacción segura de criptomonedas.\n\n"
                       "**📝 Próximos pasos:**\n"
                       "1️⃣ Menciona a tu contraparte\n"
                       "2️⃣ Confirmen sus roles (Enviador/Receptor)\n"
                       "3️⃣ Especifiquen cantidad y criptomoneda\n"
                       "4️⃣ El receptor proporcionará su dirección de retiro\n"
                       "5️⃣ El enviador transferirá a la dirección de escrow\n"
                       "6️⃣ Sistema verificará el depósito automáticamente\n"
                       "7️⃣ Confirmación final para liberar fondos\n\n"
                       "**💡 Instrucciones:**\n"
                       "Menciona a la persona con quien harás la transacción.",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Ticket #{ticket_number}")
        view = AgregarContraparteView(interaction.user.id)
        await channel.send(embed=embed, view=view)
        try:
            await interaction.followup.send(f"✅ Ticket creado: {channel.mention}", ephemeral=True)
        except discord.errors.HTTPException:
            pass

class AgregarContraparteView(discord.ui.View):
    def __init__(self, creator_id):
        super().__init__(timeout=None)
        self.creator_id = creator_id

    @discord.ui.button(label="➕ Agregar Contraparte", style=discord.ButtonStyle.primary, custom_id="agregar_contraparte")
    async def agregar_contraparte(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("❌ Solo el creador del ticket puede agregar la contraparte.", ephemeral=True)
            return

        modal = AgregarContraparteModal()
        await interaction.response.send_modal(modal)

class AgregarContraparteModal(discord.ui.Modal, title="Agregar Contraparte"):
    usuario = discord.ui.TextInput(
        label="Usuario o ID de Discord",
        placeholder="@usuario o 123456789012345678",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = interaction.client.db
        user_input = self.usuario.value.strip()
        user_id = None

        if user_input.startswith("<@") and user_input.endswith(">"):
            user_id = int(user_input.replace("<@", "").replace(">", "").replace("!", ""))
        else:
            try:
                user_id = int(user_input)
            except ValueError:
                await interaction.followup.send("❌ Formato inválido. Usa una mención (@usuario) o un ID numérico.", ephemeral=True)
                return

        try:
            contraparte = await interaction.guild.fetch_member(user_id)
        except:
            await interaction.followup.send("❌ Usuario no encontrado en este servidor.", ephemeral=True)
            return

        if contraparte.bot:
            await interaction.followup.send("❌ No puedes agregar un bot como contraparte.", ephemeral=True)
            return

        if contraparte.id == interaction.user.id:
            await interaction.followup.send("❌ No puedes agregarte a ti mismo como contraparte.", ephemeral=True)
            return

        await interaction.channel.set_permissions(contraparte, read_messages=True, send_messages=True)
        await db.update_ticket(interaction.channel.id, counterparty_id=contraparte.id)

        embed = discord.Embed(
            title="✅ Contraparte Agregada",
            description=f"{contraparte.mention} ha sido agregado al ticket.\n\n"
                       "**👥 Participantes:**\n"
                       f"• {interaction.user.mention}\n"
                       f"• {contraparte.mention}\n\n"
                       "**📋 Siguiente paso:**\n"
                       "Cada uno debe confirmar su rol en la transacción.",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        view = ConfirmarRolesView(interaction.user.id, contraparte.id)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send(f"✅ {contraparte.mention} agregado.", ephemeral=True)

class ConfirmarRolesView(discord.ui.View):
    def __init__(self, user1_id, user2_id):
        super().__init__(timeout=None)
        self.user1_id = user1_id
        self.user2_id = user2_id
        self.confirmaciones = {}

    @discord.ui.button(label="📤 Soy el Enviador", style=discord.ButtonStyle.primary, custom_id="rol_enviador")
    async def rol_enviador(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirmar_rol(interaction, "enviador")

    @discord.ui.button(label="📥 Soy el Receptor", style=discord.ButtonStyle.success, custom_id="rol_receptor")
    async def rol_receptor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.confirmar_rol(interaction, "receptor")

    async def confirmar_rol(self, interaction, rol):
        if interaction.user.id not in [self.user1_id, self.user2_id]:
            await interaction.response.send_message("❌ No eres participante de este ticket.", ephemeral=True)
            return
        if interaction.user.id in self.confirmaciones:
            await interaction.response.send_message("❌ Ya has confirmado tu rol.", ephemeral=True)
            return

        other_user_id = self.user2_id if interaction.user.id == self.user1_id else self.user1_id
        if other_user_id in self.confirmaciones and self.confirmaciones[other_user_id] == rol:
            await interaction.response.send_message(f"❌ La otra parte ya se confirmó como {rol}.", ephemeral=True)
            return

        self.confirmaciones[interaction.user.id] = rol
        await interaction.response.send_message(f"✅ Te has confirmado como **{rol.capitalize()}**.", ephemeral=True)

        if len(self.confirmaciones) == 2:
            await self.procesar_confirmaciones(interaction)

    async def procesar_confirmaciones(self, interaction):
        db = interaction.client.db
        channel = interaction.channel
        enviador_id = next(uid for uid, rol in self.confirmaciones.items() if rol == "enviador")
        receptor_id = next(uid for uid, rol in self.confirmaciones.items() if rol == "receptor")
        await db.update_ticket(channel.id, sender_id=enviador_id, receiver_id=receptor_id)

        enviador = await channel.guild.fetch_member(enviador_id)
        receptor = await channel.guild.fetch_member(receptor_id)

        embed = discord.Embed(
            title="✅ Roles Confirmados",
            description=f"**📤 Enviador:** {enviador.mention}\n"
                       f"**📥 Receptor:** {receptor.mention}\n\n"
                       "**💰 Siguiente paso:**\n"
                       "El **Enviador** debe especificar la cantidad y criptomoneda.",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        view = SeleccionarCriptomonedaView(enviador_id)
        await channel.send(embed=embed, view=view)

        await enviar_log(channel.guild, discord.Embed(
            title="📝 Roles Confirmados",
            description=f"Ticket: {channel.name}\nEnviador: {enviador.mention}\nReceptor: {receptor.mention}",
            color=discord.Color.blue()
        ))

class SeleccionarCriptomonedaView(discord.ui.View):
    def __init__(self, enviador_id):
        super().__init__(timeout=None)
        self.enviador_id = enviador_id

    @discord.ui.button(label="💰 Seleccionar Cantidad y Cripto", style=discord.ButtonStyle.primary, custom_id="seleccionar_cripto")
    async def seleccionar_cripto(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.enviador_id:
            await interaction.response.send_message("❌ Solo el enviador puede seleccionar la cantidad.", ephemeral=True)
            return

        modal = SeleccionarCriptoModal()
        await interaction.response.send_modal(modal)

class SeleccionarCriptoModal(discord.ui.Modal, title="Cantidad y Criptomoneda"):
    cantidad = discord.ui.TextInput(
        label="Cantidad",
        placeholder="Ejemplo: 0.5",
        required=True,
        max_length=50
    )

    criptomoneda = discord.ui.TextInput(
        label="Criptomoneda",
        placeholder="BTC, ETH, SOL, LTC, USDT o USDC",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = interaction.client.db

        try:
            cantidad_float = float(self.cantidad.value)
            if cantidad_float <= 0:
                raise ValueError()
        except ValueError:
            await interaction.followup.send("❌ La cantidad debe ser un número positivo.", ephemeral=True)
            return

        cripto = self.criptomoneda.value.upper().strip()

        if cripto not in CRIPTOMONEDAS:
            await interaction.followup.send(
                f"❌ Criptomoneda no soportada. Usa: {', '.join(CRIPTOMONEDAS.keys())}",
                ephemeral=True
            )
            return

        ticket_data = await db.get_ticket(interaction.channel.id)

        await db.update_ticket(
            interaction.channel.id,
            amount=cantidad_float,
            currency=cripto
        )

        cripto_info = CRIPTOMONEDAS[cripto]

        embed = discord.Embed(
            title="💰 Cantidad Especificada",
            description=f"**Cantidad:** {cantidad_float} {cripto_info['emoji']} {cripto}\n"
                       f"**Criptomoneda:** {cripto_info['nombre']}\n\n"
                       "**⏳ Esperando confirmación del receptor...**",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )

        view = ConfirmarCantidadView(ticket_data['receiver_id'], cantidad_float, cripto)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ Cantidad especificada.", ephemeral=True)

class ConfirmarCantidadView(discord.ui.View):
    def __init__(self, receptor_id, cantidad, cripto):
        super().__init__(timeout=None)
        self.receptor_id = receptor_id
        self.cantidad = cantidad
        self.cripto = cripto

    @discord.ui.button(label="✅ Confirmar Cantidad", style=discord.ButtonStyle.success, custom_id="confirmar_cantidad")
    async def confirmar_cantidad(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receptor_id:
            await interaction.response.send_message("❌ Solo el receptor puede confirmar.", ephemeral=True)
            return

        modal = DireccionReceptorModal(self.cantidad, self.cripto)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Rechazar Cantidad", style=discord.ButtonStyle.danger, custom_id="rechazar_cantidad")
    async def rechazar_cantidad(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.receptor_id:
            await interaction.response.send_message("❌ Solo el receptor puede rechazar.", ephemeral=True)
            return

        db = interaction.client.db
        await interaction.response.send_message("❌ Has rechazado la cantidad.", ephemeral=True)
        ticket_data = await db.get_ticket(interaction.channel.id)

        embed = discord.Embed(
            title="❌ Cantidad Rechazada",
            description="El receptor ha rechazado la cantidad.\n\nPor favor, especifica una nueva cantidad.",
            color=discord.Color.red()
        )

        view = SeleccionarCriptomonedaView(ticket_data['sender_id'])
        await interaction.channel.send(embed=embed, view=view)

class DireccionReceptorModal(discord.ui.Modal, title="Dirección de Retiro"):
    def __init__(self, cantidad, cripto):
        super().__init__()
        self.cantidad = cantidad
        self.cripto = cripto

    direccion = discord.ui.TextInput(
        label="Tu Dirección de Wallet",
        placeholder="Dirección donde recibirás los fondos",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = interaction.client.db
        wallet_manager = interaction.client.wallet_manager

        direccion_receptor = self.direccion.value.strip()

        if not wallet_manager.validate_address(direccion_receptor, self.cripto):
            await interaction.followup.send(
                f"❌ Dirección inválida para {self.cripto}. Verifica e intenta de nuevo.",
                ephemeral=True
            )
            return

        ticket_data = await db.get_ticket(interaction.channel.id)
        enviador = await interaction.guild.fetch_member(ticket_data['sender_id'])

        wallet_info = wallet_manager.generate_wallet_address(self.cripto, interaction.channel.id)
        direccion_escrow = wallet_info['address']

        await db.update_ticket(
            interaction.channel.id,
            escrow_address=direccion_escrow,
            receiver_wallet_address=direccion_receptor,
            status="esperando_envio"
        )

        cripto_info = CRIPTOMONEDAS[self.cripto]

        embed = discord.Embed(
            title="🔒 Deal Confirmado - Instrucciones de Envío",
            description=f"**{enviador.mention}**, por favor envía exactamente:\n\n"
                       f"**💰 Cantidad:** `{self.cantidad}` {cripto_info['emoji']} **{self.cripto}**\n"
                       f"**📍 Dirección de Escrow:**\n```{direccion_escrow}```\n\n"
                       "**⚠️ IMPORTANTE:**\n"
                       "• Envía EXACTAMENTE la cantidad especificada\n"
                       "• Usa la red correcta (ERC-20 para USDT/USDC)\n"
                       "• Verifica la dirección cuidadosamente\n"
                       "• El sistema verificará automáticamente el depósito\n\n"
                       "**📥 Destino final:** Los fondos se enviarán a:\n"
                       f"```{direccion_receptor}```\n\n"
                       "Una vez enviado, el bot monitoreará la transacción automáticamente.",
            color=discord.Color.orange(),
            timestamp=datetime.utcnow()
        )

        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Dirección confirmada. Esperando depósito...", ephemeral=True)

        asyncio.create_task(monitorear_deposito(interaction.client, interaction.channel, wallet_info, self.cantidad, self.cripto))

async def monitorear_deposito(client, channel, wallet_info, cantidad_esperada, cripto):
    db = client.db
    wallet_manager = client.wallet_manager
    max_intentos = 60
    intentos = 0

    while intentos < max_intentos:
        await asyncio.sleep(30)

        balance = await wallet_manager.check_balance(wallet_info['address'], cripto)

        if balance >= cantidad_esperada:
            ticket_data = await db.get_ticket(channel.id)

            await db.update_ticket(
                channel.id,
                status="fondos_en_escrow",
                confirmations_received=1
            )

            enviador = await channel.guild.fetch_member(ticket_data['sender_id'])
            receptor = await channel.guild.fetch_member(ticket_data['receiver_id'])

            embed = discord.Embed(
                title="✅ Depósito Detectado",
                description=f"**💰 {balance} {cripto}** recibidos en escrow!\n\n"
                           "**Estado:** 🔒 Fondos en Escrow Seguro\n\n"
                           "**📋 Próximo paso:**\n"
                           "Cuando ambas partes completen el acuerdo, deben confirmar para liberar los fondos.",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )

            view = LiberarFondosView(ticket_data['sender_id'], ticket_data['receiver_id'], wallet_info)
            await channel.send(embed=embed, view=view)

            await enviar_log(channel.guild, discord.Embed(
                title="💰 Fondos Recibidos",
                description=f"Ticket: {channel.name}\nCantidad: {balance} {cripto}\nEscrow: {wallet_info['address'][:20]}...",
                color=discord.Color.green()
            ))

            break

        intentos += 1

class LiberarFondosView(discord.ui.View):
    def __init__(self, enviador_id, receptor_id, wallet_info):
        super().__init__(timeout=None)
        self.enviador_id = enviador_id
        self.receptor_id = receptor_id
        self.wallet_info = wallet_info
        self.confirmaciones = set()

    @discord.ui.button(label="✅ Confirmar Liberación", style=discord.ButtonStyle.success, custom_id="liberar_fondos")
    async def liberar_fondos(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.enviador_id, self.receptor_id]:
            await interaction.response.send_message("❌ Solo los participantes pueden confirmar.", ephemeral=True)
            return

        if interaction.user.id in self.confirmaciones:
            await interaction.response.send_message("❌ Ya has confirmado.", ephemeral=True)
            return

        self.confirmaciones.add(interaction.user.id)
        db = interaction.client.db
        wallet_manager = interaction.client.wallet_manager

        if len(self.confirmaciones) == 1:
            await interaction.response.send_message(
                f"✅ Confirmación registrada ({len(self.confirmaciones)}/2)",
                ephemeral=True
            )

            embed = discord.Embed(
                title="⏳ Confirmación Parcial",
                description=f"{interaction.user.mention} ha confirmado la liberación.\n\n"
                           f"**Progreso:** {len(self.confirmaciones)}/2",
                color=discord.Color.gold()
            )
            await interaction.channel.send(embed=embed)

        elif len(self.confirmaciones) == 2:
            await interaction.response.defer()

            ticket_data = await db.get_ticket(interaction.channel.id)
            receptor = await interaction.guild.fetch_member(ticket_data['receiver_id'])
            enviador = await interaction.guild.fetch_member(ticket_data['sender_id'])

            embed_procesando = discord.Embed(
                title="⏳ Procesando Transacción",
                description="Enviando fondos a la dirección del receptor...",
                color=discord.Color.orange()
            )
            await interaction.channel.send(embed=embed_procesando)

            tx_hash = await wallet_manager.send_funds(
                self.wallet_info,
                ticket_data['receiver_wallet_address'],
                ticket_data['amount'],
                ticket_data['currency']
            )

            if tx_hash:
                await db.update_ticket(
                    interaction.channel.id,
                    status="completado",
                    transaction_hash=tx_hash
                )

                volume_usd = ticket_data['amount']
                if ticket_data['currency'] not in ['USDT', 'USDC']:
                    volume_usd = ticket_data['amount'] * 50000

                await db.increment_trade_stats(enviador.id, interaction.guild.id, volume_usd)
                await db.increment_trade_stats(receptor.id, interaction.guild.id, volume_usd)

                cripto_info = CRIPTOMONEDAS[ticket_data['currency']]

                embed = discord.Embed(
                    title="🎉 ¡Deal Completado!",
                    description=f"**✅ Fondos liberados exitosamente**\n\n"
                                f"**💰 Detalles:**\n"
                                f"• Cantidad: {ticket_data['amount']} {cripto_info['emoji']} {ticket_data['currency']}\n"
                                f"• Enviador: {enviador.mention}\n"
                                f"• Receptor: {receptor.mention}\n"
                                f"• TX Hash: `{tx_hash[:20]}...`\n\n"
                                f"**📊 Estado:** ✅ Completado\n\n"
                                "**⭐ Califica a tu contraparte:**",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )

                await interaction.channel.send(
                    f"{enviador.mention}, califica a {receptor.mention}:",
                    view=CalificarUsuarioView(interaction.channel.id, receptor.id)
                )
                await interaction.channel.send(
                    f"{receptor.mention}, califica a {enviador.mention}:",
                    view=CalificarUsuarioView(interaction.channel.id, enviador.id)
                )

                await interaction.channel.send(embed=embed)

                await enviar_log(interaction.guild, discord.Embed(
                    title="✅ Transacción Completada",
                    description=f"Ticket: {interaction.channel.name}\nTX: {tx_hash}",
                    color=discord.Color.green()
                ))

                await asyncio.sleep(60)
                await interaction.channel.delete(reason="Ticket completado")
            else:
                embed_error = discord.Embed(
                    title="❌ Error en Transacción",
                    description="No se pudo completar el envío. Contacta a un administrador.",
                    color=discord.Color.red()
                )
                await interaction.channel.send(embed=embed_error)

    @discord.ui.button(label="⚠️ Abrir Disputa", style=discord.ButtonStyle.danger, custom_id="abrir_disputa")
    async def abrir_disputa(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.enviador_id, self.receptor_id]:
            await interaction.response.send_message("❌ Solo los participantes pueden abrir disputa.", ephemeral=True)
            return

        modal = AbrirDisputaModal()
        await interaction.response.send_modal(modal)

class AbrirDisputaModal(discord.ui.Modal, title="Abrir Disputa"):
    razon = discord.ui.TextInput(
        label="Razón de la Disputa",
        placeholder="Describe el problema...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = interaction.client.db

        await db.update_ticket(
            interaction.channel.id,
            status="en_disputa",
            dispute_status="pendiente",
            dispute_reason=self.razon.value
        )

        admin_role = discord.utils.get(interaction.guild.roles, permissions=discord.Permissions(administrator=True))

        embed = discord.Embed(
            title="⚠️ Disputa Abierta",
            description=f"**Solicitado por:** {interaction.user.mention}\n\n"
                       f"**Razón:**\n{self.razon.value}\n\n"
                       f"**Estado:** Esperando mediación de administrador\n\n"
                       f"{admin_role.mention if admin_role else '@Administradores'} - Se requiere mediación.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )

        view = MediacionDisputaView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("⚠️ Disputa abierta. Un administrador revisará el caso.", ephemeral=True)

class MediacionDisputaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Liberar al Receptor", style=discord.ButtonStyle.success, custom_id="mediacion_receptor")
    async def liberar_receptor(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden mediar.", ephemeral=True)
            return

        await interaction.response.defer()

        embed = discord.Embed(
            title="✅ Disputa Resuelta - Favor al Receptor",
            description=f"**Mediador:** {interaction.user.mention}\n\n"
                       "Fondos serán liberados al receptor.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed)

    @discord.ui.button(label="↩️ Reembolsar al Enviador", style=discord.ButtonStyle.primary, custom_id="mediacion_enviador")
    async def reembolsar_enviador(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores pueden mediar.", ephemeral=True)
            return

        modal = DireccionReembolsoModal()
        await interaction.response.send_modal(modal)

class DireccionReembolsoModal(discord.ui.Modal, title="Dirección de Reembolso"):
    direccion = discord.ui.TextInput(
        label="Dirección del Enviador para Reembolso",
        placeholder="Dirección donde se reembolsarán los fondos",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = interaction.client.db
        wallet_manager = interaction.client.wallet_manager

        ticket_data = await db.get_ticket(interaction.channel.id)
        direccion_reembolso = self.direccion.value.strip()

        if not wallet_manager.validate_address(direccion_reembolso, ticket_data['currency']):
            await interaction.followup.send("❌ Dirección inválida.", ephemeral=True)
            return

        await db.update_ticket(
            interaction.channel.id,
            sender_refund_address=direccion_reembolso,
            status="reembolsado"
        )

        embed = discord.Embed(
            title="↩️ Disputa Resuelta - Reembolso al Enviador",
            description=f"**Mediador:** {interaction.user.mention}\n\n"
                       f"Los fondos serán devueltos a: `{direccion_reembolso}`",
            color=discord.Color.blue()
        )
        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Reembolso procesado.", ephemeral=True)

class SeleccionarCriptoDepositoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(
        placeholder="Selecciona una criptomoneda",
        options=[
            discord.SelectOption(label="Bitcoin (BTC)", value="BTC", emoji="🪙"),
            discord.SelectOption(label="Ethereum (ETH)", value="ETH", emoji="💎"),
            discord.SelectOption(label="Solana (SOL)", value="SOL", emoji="☀️"),
            discord.SelectOption(label="Litecoin (LTC)", value="LTC", emoji="🔷"),
            discord.SelectOption(label="Tether (USDT)", value="USDT", emoji="💵"),
            discord.SelectOption(label="USD Coin (USDC)", value="USDC", emoji="💰"),
        ]
    )
    async def select_crypto(self, interaction: discord.Interaction, select: discord.ui.Select):
        currency = select.values[0]
        wallet_manager = interaction.client.wallet_manager
        wallet_info = wallet_manager.generate_wallet_address(currency, interaction.user.id)

        embed = discord.Embed(
            title="💳 Depositar Fondos",
            description=f"**Criptomoneda:** {CRIPTOMONEDAS[currency]['nombre']} {CRIPTOMONEDAS[currency]['emoji']}\n\n"
                       f"**Dirección de Depósito:**\n```{wallet_info['address']}```\n\n"
                       "**⚠️ IMPORTANTE:**\n"
                       "• Envía solo esta criptomoneda a esta dirección\n"
                       "• Usa la red correcta (ERC-20 para USDT/USDC)\n"
                       "• Los fondos se acreditarán automáticamente\n"
                       "• Guarda esta dirección para futuros depósitos",
            color=discord.Color.green()
        )

        await interaction.response.edit_message(embed=embed, view=None)

        asyncio.create_task(monitorear_deposito_balance(
            interaction.client,
            interaction.user.id, 
            interaction.guild.id,
            wallet_info, 
            currency
        ))

class CalificarUsuarioView(discord.ui.View):
    def __init__(self, ticket_id, user_to_rate_id):
        super().__init__(timeout=300)
        self.ticket_id = ticket_id
        self.user_to_rate_id = user_to_rate_id

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.secondary, custom_id="rate_1")
    async def rate_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_rating(interaction, 1)

    @discord.ui.button(label="⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rate_2")
    async def rate_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_rating(interaction, 2)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.secondary, custom_id="rate_3")
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_rating(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.primary, custom_id="rate_4")
    async def rate_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_rating(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.success, custom_id="rate_5")
    async def rate_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_rating(interaction, 5)

    async def process_rating(self, interaction, stars):
        modal = ComentarioCalificacionModal(self.ticket_id, self.user_to_rate_id, stars)
        await interaction.response.send_modal(modal)

class ComentarioCalificacionModal(discord.ui.Modal, title="Agregar Comentario"):
    def __init__(self, ticket_id, user_to_rate_id, stars):
        super().__init__()
        self.ticket_id = ticket_id
        self.user_to_rate_id = user_to_rate_id
        self.stars = stars

    comentario = discord.ui.TextInput(
        label="Comentario (Opcional)",
        placeholder="Escribe tu opinión sobre la transacción...",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = interaction.client.db

        await db.add_rating(
            self.ticket_id,
            interaction.user.id,
            self.user_to_rate_id,
            self.stars,
            self.comentario.value if self.comentario.value else None
        )

        user = await interaction.guild.fetch_member(self.user_to_rate_id)
        stars_display = "⭐" * self.stars

        await interaction.followup.send(
            f"✅ Has calificado a {user.mention} con {stars_display}",
            ephemeral=True
        )

async def monitorear_deposito_balance(client, user_id, guild_id, wallet_info, currency):
    db = client.db
    wallet_manager = client.wallet_manager
    max_intentos = 60
    intentos = 0
    balance_anterior = 0.0

    while intentos < max_intentos:
        await asyncio.sleep(30)

        balance_actual = await wallet_manager.check_balance(wallet_info['address'], currency)

        if balance_actual > balance_anterior:
            cantidad_depositada = balance_actual - balance_anterior
            await db.update_balance(user_id, guild_id, currency, cantidad_depositada)

            print(f"✅ Depósito detectado: {cantidad_depositada} {currency} para usuario {user_id}")
            balance_anterior = balance_actual

        intentos += 1


class RetiroModal(discord.ui.Modal, title="Retirar Fondos"):
    def __init__(self, currency):
        super().__init__()
        self.currency = currency

    cantidad = discord.ui.TextInput(
        label="Cantidad a Retirar",
        placeholder="Ejemplo: 0.5",
        required=True,
        max_length=50
    )

    direccion = discord.ui.TextInput(
        label="Dirección de Destino",
        placeholder="Tu dirección de wallet",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = interaction.client.db
        wallet_manager = interaction.client.wallet_manager

        try:
            cantidad = float(self.cantidad.value)
        except ValueError:
            await interaction.followup.send("❌ Cantidad inválida.", ephemeral=True)
            return

        balance_actual = await db.get_user_balance(
            interaction.user.id, 
            interaction.guild.id, 
            self.currency
        )

        if cantidad > balance_actual:
            await interaction.followup.send(
                f"❌ Balance insuficiente. Tienes {balance_actual} {self.currency}",
                ephemeral=True
            )
            return

        if not wallet_manager.validate_address(self.direccion.value, self.currency):
            await interaction.followup.send(
                f"❌ Dirección inválida para {self.currency}",
                ephemeral=True
            )
            return

        # Descontar del balance
        await db.update_balance(
            interaction.user.id,
            interaction.guild.id,
            self.currency,
            -cantidad
        )

        cripto_info = CRIPTOMONEDAS[self.currency]
        embed_procesando = discord.Embed(
            title="⏳ Procesando Retiro",
            description=f"**Cantidad:** {cantidad} {cripto_info['emoji']} {self.currency}\n"
                       f"**Destino:** `{self.direccion.value}`\n\n"
                       "Enviando fondos a la blockchain...",
            color=discord.Color.orange()
        )
        await interaction.followup.send(embed=embed_procesando, ephemeral=True)

        # Generar wallet desde el balance interno
        wallet_info = wallet_manager.generate_wallet_address(self.currency, interaction.user.id)
        
        # Realizar envío real
        tx_hash = await wallet_manager.send_funds(
            wallet_info,
            self.direccion.value,
            cantidad,
            self.currency
        )

        if tx_hash:
            embed_exito = discord.Embed(
                title="✅ Retiro Exitoso",
                description=f"**Cantidad:** {cantidad} {cripto_info['emoji']} {self.currency}\n"
                           f"**Destino:** `{self.direccion.value}`\n"
                           f"**TX Hash:** `{tx_hash[:20]}...`\n\n"
                           "Los fondos han sido enviados a la blockchain.",
                color=discord.Color.green()
            )
            await interaction.channel.send(embed=embed_exito)
            
            await enviar_log(interaction.guild, discord.Embed(
                title="💸 Retiro Completado",
                description=f"Usuario: {interaction.user.mention}\nCantidad: {cantidad} {self.currency}\nTX: {tx_hash}",
                color=discord.Color.green()
            ))
        else:
            # Reembolsar el balance si falla
            await db.update_balance(
                interaction.user.id,
                interaction.guild.id,
                self.currency,
                cantidad
            )
            
            embed_error = discord.Embed(
                title="❌ Error en Retiro",
                description="No se pudo completar el envío. Tu balance ha sido restaurado.\n\n"
                           "**Posibles causas:**\n"
                           "• APIs de blockchain no configuradas\n"
                           "• Red congestionada\n"
                           "• Balance insuficiente para fees\n\n"
                           "Contacta a un administrador.",
                color=discord.Color.red()
            )
            await interaction.channel.send(embed=embed_error)
