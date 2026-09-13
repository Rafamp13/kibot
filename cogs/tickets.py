from cogs.embed_style import KibotEmbed
import io
import re
import asyncio
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands

from database import db

PANEL_CHANNEL = "🎫・abrir-ticket"
CATEGORY_NAME = "🎫・ATENDIMENTO"
LOG_CHANNEL = "📋・ticket-logs"
REPORT_LOG_CHANNEL = "🚨・denúncias-logs"
EVALUATION_CHANNEL = "⭐・avaliações"
HELP_CHANNEL = "🆘・ajudas"
ARAUToS_ROLE_ID = 1541094751242166453
DOUBT_MENTION_ROLE_ID = 1541094604626198619
MOD_ROLE_ID = 1541094492847743066
STAFF_ROLE_ID = ARAUToS_ROLE_ID
STAFF_NAMES = ("dono", "imperador", "administrador", "gestão", "gestao", "moderador", "mestre", "narrador", "staff", "suporte", "atendimento")

TYPE_INFO = {
    "duvida": ("❓", "Dúvida", "Atendimento para dúvidas, orientações e suporte geral."),
    "denuncia": ("🚨", "Denúncia", "Canal privado para denúncias e situações que precisam de análise da equipe."),
}


def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild or member.guild_permissions.manage_channels:
        return True
    if any(role.id in {ARAUToS_ROLE_ID, DOUBT_MENTION_ROLE_ID, MOD_ROLE_ID} for role in member.roles):
        return True
    return any(any(token in role.name.lower() for token in STAFF_NAMES) for role in member.roles)


async def find_staff_role(guild: discord.Guild):
    # Cargo oficial usado pelo botão "Mencionar Staff".
    configured = await db.get_ticket_config(guild.id)
    role = guild.get_role(STAFF_ROLE_ID)
    if role:
        return role
    if configured and configured["staff_role_id"]:
        role = guild.get_role(configured["staff_role_id"])
        if role:
            return role
    candidates = [r for r in guild.roles if any(token in r.name.lower() for token in STAFF_NAMES)]
    candidates.sort(key=lambda r: r.position, reverse=True)
    return candidates[0] if candidates else None


async def ensure_ticket_structure(guild: discord.Guild):
    cfg = await db.get_ticket_config(guild.id)
    category = guild.get_channel(cfg["category_id"]) if cfg and cfg["category_id"] else None
    if not isinstance(category, discord.CategoryChannel):
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(CATEGORY_NAME, reason="Kibot Tickets — estrutura automática")

    arautos_role = guild.get_role(ARAUToS_ROLE_ID)
    doubt_role = guild.get_role(DOUBT_MENTION_ROLE_ID)
    mod_role = guild.get_role(MOD_ROLE_ID)
    me = guild.me
    everyone = guild.default_role

    # Logs gerais: destinados à equipe responsável pelos atendimentos.
    general_log_ow = {everyone: discord.PermissionOverwrite(view_channel=False)}
    if arautos_role:
        general_log_ow[arautos_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
    if mod_role:
        general_log_ow[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
    if me:
        general_log_ow[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, manage_channels=True)

    # Logs de denúncias: EXCLUSIVAMENTE moderadores + Kibot.
    report_log_ow = {everyone: discord.PermissionOverwrite(view_channel=False)}
    if mod_role:
        report_log_ow[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
    if me:
        report_log_ow[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, manage_channels=True)

    log_channel = guild.get_channel(cfg["log_channel_id"]) if cfg and cfg["log_channel_id"] else None
    if not isinstance(log_channel, discord.TextChannel):
        log_channel = discord.utils.get(category.text_channels, name=LOG_CHANNEL)
    if log_channel is None:
        log_channel = await guild.create_text_channel(LOG_CHANNEL, category=category, overwrites=general_log_ow, reason="Kibot Tickets — logs de dúvidas")
    else:
        await log_channel.edit(overwrites=general_log_ow, reason="Kibot Tickets — atualizar permissões dos logs")

    report_log_channel = guild.get_channel(cfg["report_log_channel_id"]) if cfg and "report_log_channel_id" in cfg.keys() and cfg["report_log_channel_id"] else None
    if not isinstance(report_log_channel, discord.TextChannel):
        report_log_channel = discord.utils.get(category.text_channels, name=REPORT_LOG_CHANNEL)
    if report_log_channel is None:
        report_log_channel = await guild.create_text_channel(REPORT_LOG_CHANNEL, category=category, overwrites=report_log_ow, reason="Kibot Tickets — logs de denúncias")
    else:
        await report_log_channel.edit(overwrites=report_log_ow, reason="Kibot Tickets — atualizar permissões dos logs de denúncias")

    eval_ow = {everyone: discord.PermissionOverwrite(view_channel=False)}
    if arautos_role:
        eval_ow[arautos_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
    if mod_role:
        eval_ow[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=False, read_message_history=True)
    if me:
        eval_ow[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
    eval_channel = guild.get_channel(cfg["evaluation_channel_id"]) if cfg and "evaluation_channel_id" in cfg.keys() and cfg["evaluation_channel_id"] else None
    if not isinstance(eval_channel, discord.TextChannel):
        eval_channel = discord.utils.get(category.text_channels, name=EVALUATION_CHANNEL)
    if eval_channel is None:
        eval_channel = await guild.create_text_channel(EVALUATION_CHANNEL, category=category, overwrites=eval_ow, reason="Kibot Tickets — avaliações")
    else:
        await eval_channel.edit(overwrites=eval_ow, reason="Kibot Tickets — atualizar permissões das avaliações")

    help_ow = {
        everyone: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    if arautos_role:
        help_ow[arautos_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True)
    if me:
        help_ow[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True, manage_channels=True)
    help_channel = discord.utils.get(category.text_channels, name=HELP_CHANNEL)
    if help_channel is None:
        help_channel = await guild.create_text_channel(HELP_CHANNEL, category=category, overwrites=help_ow, topic="Dúvidas rápidas e perguntas gerais — atendidas pelos Arautos.", reason="Kibot — canal de ajudas")
        await help_channel.send(embed=KibotEmbed(
            title="🆘 Central de Ajudas",
            description=("Tem uma dúvida rápida ou precisa de orientação? Pergunte aqui sem abrir um ticket.\n\n"
                         f"👑 **Arautos:** <@&{ARAUToS_ROLE_ID}> são responsáveis por responder as perguntas.\n"
                         "🎫 Para assuntos privados, denúncias ou casos que exigem atendimento individual, utilize a Central de Tickets."),
            color=discord.Color.blurple(),
        ), allowed_mentions=discord.AllowedMentions(roles=True))
    else:
        await help_channel.edit(overwrites=help_ow, topic="Dúvidas rápidas e perguntas gerais — atendidas pelos Arautos.", reason="Kibot — atualizar canal de ajudas")

    panel = guild.get_channel(cfg["panel_channel_id"]) if cfg and cfg["panel_channel_id"] else None
    if not isinstance(panel, discord.TextChannel):
        panel = discord.utils.get(guild.text_channels, name=PANEL_CHANNEL)
    if panel is None:
        panel = await guild.create_text_channel(PANEL_CHANNEL, category=category, reason="Kibot Tickets — painel")

    await db.set_ticket_config(
        guild.id,
        category_id=category.id,
        panel_channel_id=panel.id,
        log_channel_id=log_channel.id,
        report_log_channel_id=report_log_channel.id,
        evaluation_channel_id=eval_channel.id,
        staff_role_id=arautos_role.id if arautos_role else None,
    )
    return category, panel, log_channel, report_log_channel, eval_channel, arautos_role, doubt_role, mod_role, help_channel


def panel_embed():
    e = KibotEmbed(
        title="🎫 Central de Atendimento — Kibot",
        description=(
            "Precisa falar com a equipe? Abra um ticket pelo botão correspondente abaixo.\n\n"
            "❓ **Dúvida** — suporte, perguntas e orientações.\n"
            "🚨 **Denúncia** — denúncias e situações que precisam de análise da equipe.\n\n"
            "🔒 Cada ticket é privado entre você e a equipe responsável. Evite abrir tickets duplicados."
        ),
        color=discord.Color.blurple(),
    )
    e.set_footer(text="Kibot • Central de Atendimento")
    return e


class TicketReasonModal(discord.ui.Modal):
    def __init__(self, cog, ticket_type: str):
        label = "Dúvida" if ticket_type == "duvida" else "Denúncia"
        super().__init__(title=f"Abrir ticket — {label}", timeout=300)
        self.cog = cog
        self.ticket_type = ticket_type
        self.reason = discord.ui.TextInput(
            label="Por que você está abrindo este ticket?",
            placeholder="Explique o motivo com o máximo de contexto possível...",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=2000,
            required=True,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.create_ticket(interaction, self.ticket_type, str(self.reason.value).strip())


class TicketPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Dúvida", emoji="❓", style=discord.ButtonStyle.primary, custom_id="kibot:ticket:duvida")
    async def doubt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.open_ticket(interaction, "duvida")

    @discord.ui.button(label="Denúncia", emoji="🚨", style=discord.ButtonStyle.danger, custom_id="kibot:ticket:denuncia")
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.open_ticket(interaction, "denuncia")


class TicketControlView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Assumir ticket", emoji="🙋", style=discord.ButtonStyle.success, custom_id="kibot:ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.claim_ticket(interaction)

    @discord.ui.button(label="📣 Mencionar Staff", style=discord.ButtonStyle.secondary, custom_id="kibot:ticket:mention_staff")
    async def mention_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.mention_staff(interaction)

    @discord.ui.button(label="👤 Mencionar Usuário", style=discord.ButtonStyle.secondary, custom_id="kibot:ticket:mention_user")
    async def mention_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.mention_user(interaction)

    @discord.ui.button(label="Adicionar membro", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="kibot:ticket:add")
    async def add_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Use `K!ticket adicionar @membro` neste ticket.", ephemeral=True)

    @discord.ui.button(label="Fechar ticket", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="kibot:ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.close_ticket(interaction)


class RatingModal(discord.ui.Modal, title="⭐ Avaliação do atendimento"):
    description = discord.ui.TextInput(
        label="Descreva sua experiência",
        placeholder="Conte como foi o atendimento, o que gostou ou o que poderia melhorar...",
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=1000,
        required=True,
    )

    def __init__(self, cog, ticket_id: int, stars: int, target_user_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.ticket_id = ticket_id
        self.stars = stars
        self.target_user_id = target_user_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.target_user_id:
            return await interaction.response.send_message("❌ Esta avaliação não pertence a você.", ephemeral=True)
        await self.cog.submit_rating(interaction, self.ticket_id, self.stars, str(self.description.value).strip())


class RatingView(discord.ui.View):
    def __init__(self, cog, ticket_id: int, target_user_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_id = ticket_id
        self.target_user_id = target_user_id
        for stars in range(1, 6):
            button = discord.ui.Button(
                label="★" * stars,
                style=discord.ButtonStyle.primary if stars >= 4 else discord.ButtonStyle.secondary,
                custom_id=f"kibot:ticket:rating:{ticket_id}:{stars}",
            )
            button.callback = self._make_callback(stars)
            self.add_item(button)

    def _make_callback(self, stars: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.target_user_id:
                return await interaction.response.send_message("❌ Esta avaliação foi enviada para outro usuário.", ephemeral=True)
            await interaction.response.send_modal(RatingModal(self.cog, self.ticket_id, stars, self.target_user_id))
        return callback


class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.closing_tickets = set()

    async def cog_load(self):
        self.bot.add_view(TicketPanelView(self))
        self.bot.add_view(TicketControlView(self))
        try:
            pending = await db.get_pending_ticket_evaluations()
            for row in pending:
                self.bot.add_view(RatingView(self, row["ticket_id"], row["user_id"]))
        except Exception:
            # Banco de uma instalação anterior pode ainda não possuir a tabela; init_db a cria.
            pass

    async def open_ticket(self, interaction: discord.Interaction, ticket_type: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ Tickets só podem ser abertos dentro de um servidor.", ephemeral=True)
        existing = await db.get_open_ticket_for_user(interaction.guild.id, interaction.user.id)
        if existing:
            channel = interaction.guild.get_channel(existing["channel_id"])
            if channel:
                return await interaction.response.send_message(f"⚠️ Você já possui um ticket aberto: {channel.mention}", ephemeral=True)
            await db.close_ticket_record(existing["id"], None, "canal_inexistente")
        # A confirmação acontece antes da criação: o usuário precisa explicar o motivo.
        await interaction.response.send_modal(TicketReasonModal(self, ticket_type))

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, reason: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ Tickets só podem ser abertos dentro de um servidor.", ephemeral=True)
        guild = interaction.guild
        emoji, label, description = TYPE_INFO[ticket_type]
        existing = await db.get_open_ticket_for_user(guild.id, interaction.user.id)
        if existing:
            channel = guild.get_channel(existing["channel_id"])
            if channel:
                return await interaction.response.send_message(f"⚠️ Você já possui um ticket aberto: {channel.mention}", ephemeral=True)
            await db.close_ticket_record(existing["id"], None, "canal_inexistente")

        category, _, log_channel, report_log_channel, _, arautos_role, doubt_role, mod_role, _ = await ensure_ticket_structure(guild)
        me = guild.me
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        }
        # Cargo responsável pelo tipo de ticket. O mesmo cargo é usado pelo botão
        # "Mencionar Staff" quando ainda não existe um atendente assumido.
        staff_role = mod_role if ticket_type == "denuncia" else doubt_role
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                manage_messages=True,
            )
        elif arautos_role:
            # Fallback apenas se o cargo específico não existir.
            staff_role = arautos_role
            overwrites[arautos_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                manage_messages=True,
            )
        if me:
            overwrites[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, manage_channels=True, manage_messages=True)

        prefix = "duvida" if ticket_type == "duvida" else "denuncia"
        safe_name = re.sub(r"[^a-z0-9-]+", "-", interaction.user.name.lower()).strip("-") or str(interaction.user.id)
        channel_name = f"{prefix}-{safe_name[:50]}-{interaction.user.id}"
        if discord.utils.get(category.text_channels, name=channel_name):
            channel_name = f"{prefix}-{interaction.user.id}"
        channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites, reason=f"Kibot Ticket — {label}")
        ticket_id = await db.create_ticket(guild.id, channel.id, interaction.user.id, ticket_type, interaction.user.id, reason)

        embed = KibotEmbed(title=f"{emoji} Ticket de {label}", description=description, color=discord.Color.orange() if ticket_type == "denuncia" else discord.Color.blurple())
        embed.add_field(name="👤 Solicitante", value=interaction.user.mention, inline=True)
        embed.add_field(name="🆔 Ticket", value=f"`#{ticket_id}`", inline=True)
        embed.add_field(name="📌 Status", value="🟢 Aberto", inline=True)
        embed.add_field(name="📝 Motivo da abertura", value=reason[:1024], inline=False)
        embed.add_field(name="📋 Como funciona", value="A equipe analisará sua solicitação. Use os botões abaixo se precisar chamar alguém ou encerrar o atendimento.", inline=False)
        await channel.send(
            content=f"{interaction.user.mention}" + (f" {staff_role.mention}" if staff_role else ""),
            embed=embed,
            view=TicketControlView(self),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )
        await interaction.response.send_message(f"✅ Ticket criado: {channel.mention}", ephemeral=True)
        await self._log(guild, "🎫 Ticket aberto", f"**Ticket:** {channel.mention} (`#{ticket_id}`)\n**Tipo:** {label}\n**Autor:** {interaction.user.mention}\n**Motivo:** {reason[:1000]}", discord.Color.green(), ticket_type=ticket_type)

    async def claim_ticket(self, interaction: discord.Interaction):
        ticket = await db.get_ticket_by_channel(interaction.channel.id if interaction.channel else 0)
        if not ticket:
            return await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas a equipe pode assumir tickets.", ephemeral=True)
        await db.claim_ticket_record(ticket["id"], interaction.user.id)
        await interaction.response.send_message(f"🙋 {interaction.user.mention} assumiu este ticket.", allowed_mentions=discord.AllowedMentions(users=True))
        await self._log(interaction.guild, "🙋 Ticket assumido", f"**Ticket:** {interaction.channel.mention}\n**Atendente:** {interaction.user.mention}", discord.Color.green(), ticket_type=ticket["ticket_type"])

    async def mention_staff(self, interaction: discord.Interaction):
        ticket = await db.get_ticket_by_channel(interaction.channel.id if interaction.channel else 0)
        if not ticket:
            return await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or (interaction.user.id != ticket["user_id"] and not is_staff(interaction.user)):
            return await interaction.response.send_message("❌ Você não pode chamar a equipe neste ticket.", ephemeral=True)
        staff_role = interaction.guild.get_role(MOD_ROLE_ID if ticket["ticket_type"] == "denuncia" else DOUBT_MENTION_ROLE_ID)
        if ticket["claimed_by"]:
            target = f"<@{ticket['claimed_by']}>"
            label = "atendente responsável"
            allowed = discord.AllowedMentions(users=True)
        elif staff_role:
            target = staff_role.mention
            label = "cargo responsável"
            allowed = discord.AllowedMentions(roles=True)
        else:
            return await interaction.response.send_message("❌ Não encontrei um atendente assumido nem um cargo de suporte configurado.", ephemeral=True)
        await interaction.response.send_message(f"📣 Chamando {label}: {target}", allowed_mentions=allowed)
        await self._log(interaction.guild, "📣 Staff mencionado", f"**Ticket:** {interaction.channel.mention}\n**Solicitado por:** {interaction.user.mention}\n**Destino:** {target}", discord.Color.gold(), ticket_type=ticket["ticket_type"])

    async def mention_user(self, interaction: discord.Interaction):
        ticket = await db.get_ticket_by_channel(interaction.channel.id if interaction.channel else 0)
        if not ticket:
            return await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas a equipe pode mencionar o usuário por este botão.", ephemeral=True)
        user = interaction.guild.get_member(ticket["user_id"]) or self.bot.get_user(ticket["user_id"])
        mention = f"<@{ticket['user_id']}>"
        await interaction.response.send_message(f"👤 Chamando o usuário: {mention}", allowed_mentions=discord.AllowedMentions(users=True))
        if user:
            try:
                dm = await user.create_dm()
                await dm.send(f"📣 <@{ticket['user_id']}> a equipe mencionou você no seu ticket em **{interaction.guild.name}**. Volte ao canal para continuar o atendimento: {interaction.channel.mention}", allowed_mentions=discord.AllowedMentions(users=True))
            except (discord.Forbidden, discord.HTTPException):
                pass
        await self._log(interaction.guild, "👤 Usuário mencionado", f"**Ticket:** {interaction.channel.mention}\n**Usuário:** {mention}\n**Por:** {interaction.user.mention}", discord.Color.blurple(), ticket_type=ticket["ticket_type"])

    async def close_ticket(self, interaction: discord.Interaction):
        channel = interaction.channel
        ticket = await db.get_ticket_by_channel(channel.id if channel else 0)
        if not ticket:
            return await interaction.response.send_message("❌ Este canal não é um ticket registrado.", ephemeral=True)
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ Usuário inválido.", ephemeral=True)
        if interaction.user.id != ticket["user_id"] and not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Só o solicitante ou a equipe pode fechar este ticket.", ephemeral=True)
        if ticket["id"] in self.closing_tickets:
            return await interaction.response.send_message("⏳ Este ticket já está sendo encerrado.", ephemeral=True)
        self.closing_tickets.add(ticket["id"])
        try:
            await interaction.response.send_message("🔒 O ticket será fechado em **5 segundos**...", ephemeral=False)
            message = await interaction.original_response()
            for remaining in range(4, 0, -1):
                await asyncio.sleep(1)
                try:
                    await message.edit(content=f"🔒 O ticket será fechado em **{remaining} segundo{'s' if remaining != 1 else ''}**...", embed=None, view=None)
                except discord.HTTPException:
                    break
            await self._finish_close(interaction.guild, channel, ticket, interaction.user)
        finally:
            self.closing_tickets.discard(ticket["id"])

    async def _finish_close(self, guild, channel, ticket, closed_by):
        transcript = await self.make_transcript(channel, ticket)
        await db.close_ticket_record(ticket["id"], closed_by.id, "fechado")
        config = await db.get_ticket_config(guild.id)
        if ticket["ticket_type"] == "denuncia":
            log_channel = guild.get_channel(config["report_log_channel_id"]) if config and "report_log_channel_id" in config.keys() and config["report_log_channel_id"] else None
        else:
            log_channel = guild.get_channel(config["log_channel_id"]) if config and config["log_channel_id"] else None
        emoji, label, _ = TYPE_INFO[ticket["ticket_type"]]
        embed = KibotEmbed(title="🔒 Ticket encerrado", color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="🎫 Ticket", value=f"`#{ticket['id']}` • {channel.name}", inline=True)
        embed.add_field(name="📂 Tipo", value=f"{emoji} {label}", inline=True)
        embed.add_field(name="👤 Autor", value=f"<@{ticket['user_id'] }>", inline=True)
        embed.add_field(name="🔒 Fechado por", value=closed_by.mention, inline=True)
        embed.add_field(name="🙋 Atendente", value=f"<@{ticket['claimed_by']}>" if ticket["claimed_by"] else "Não assumido", inline=True)
        embed.set_footer(text="Kibot • Transcrição de ticket")
        file = discord.File(io.BytesIO(transcript.encode("utf-8")), filename=f"ticket-{ticket['id']}.txt")
        if log_channel:
            await log_channel.send(embed=embed, file=file)

        # Envia a avaliação para o usuário antes de apagar o canal.
        await self.send_rating_request(guild, ticket)
        await channel.delete(reason=f"Kibot Ticket encerrado por {closed_by}")

    async def send_rating_request(self, guild: discord.Guild, ticket):
        try:
            user = guild.get_member(ticket["user_id"]) or self.bot.get_user(ticket["user_id"])
            if user is None:
                user = await self.bot.fetch_user(ticket["user_id"])
            dm = await user.create_dm()
            embed = KibotEmbed(
                title="⭐ Avalie seu atendimento",
                description=(
                    f"Seu ticket **#{ticket['id']}** em **{guild.name}** foi encerrado.\n\n"
                    "Como foi o atendimento? Escolha de **1 a 5 estrelas** abaixo e depois descreva sua experiência."
                ),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="Kibot • Sua avaliação ajuda a melhorar o atendimento")
            message = await dm.send(embed=embed, view=RatingView(self, ticket["id"], ticket["user_id"]))
            await db.create_ticket_evaluation(ticket["id"], guild.id, ticket["user_id"], ticket["claimed_by"], message.id)
        except (discord.Forbidden, discord.HTTPException):
            await self._log(guild, "⚠️ Avaliação não enviada", f"Não foi possível enviar a avaliação do ticket `#{ticket['id']}` por DM.", discord.Color.orange(), ticket_type=ticket["ticket_type"])

    async def submit_rating(self, interaction: discord.Interaction, ticket_id: int, stars: int, description: str):
        evaluation = await db.get_ticket_evaluation(ticket_id)
        if not evaluation or evaluation["status"] != "pending":
            return await interaction.response.send_message("⚠️ Esta avaliação já foi respondida ou não está mais disponível.", ephemeral=True)
        if interaction.user.id != evaluation["user_id"]:
            return await interaction.response.send_message("❌ Esta avaliação não pertence a você.", ephemeral=True)
        await db.complete_ticket_evaluation(ticket_id, stars, description)
        await interaction.response.send_message("✅ Obrigado! Sua avaliação foi registrada com sucesso.", ephemeral=True)

        guild = self.bot.get_guild(evaluation["guild_id"])
        if not guild:
            return
        cfg = await db.get_ticket_config(guild.id)
        eval_channel = guild.get_channel(cfg["evaluation_channel_id"]) if cfg and "evaluation_channel_id" in cfg.keys() and cfg["evaluation_channel_id"] else None
        if not eval_channel:
            try:
                _, _, _, _, eval_channel, _, _, _, _ = await ensure_ticket_structure(guild)
            except discord.HTTPException:
                return

        staff_mention = f"<@{evaluation['claimed_by']}>" if evaluation["claimed_by"] else "⚠️ **Sem atendente definido**"
        stars_text = "⭐" * stars + "☆" * (5 - stars)
        embed = KibotEmbed(title="⭐ Nova avaliação de atendimento", color=discord.Color.gold(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="🎫 Ticket", value=f"`#{ticket_id}`", inline=True)
        embed.add_field(name="👤 Usuário", value=f"<@{evaluation['user_id']}>", inline=True)
        embed.add_field(name="🙋 Atendente", value=staff_mention, inline=True)
        embed.add_field(name="📊 Nota", value=f"{stars_text} **({stars}/5)**", inline=False)
        embed.add_field(name="💬 Descrição", value=description[:1024], inline=False)
        embed.set_footer(text=f"Kibot • Avaliação #{ticket_id}")
        await eval_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False))

    async def make_transcript(self, channel: discord.TextChannel, ticket):
        lines = [
            "KIBOT — TRANSCRIÇÃO DE TICKET",
            "=" * 72,
            f"Ticket: #{ticket['id']}",
            f"Servidor: {channel.guild.name} ({channel.guild.id})",
            f"Canal: {channel.name} ({channel.id})",
            f"Tipo: {TYPE_INFO[ticket['ticket_type']][1]}",
            f"Criado por: {ticket['user_id']}",
            f"Atendente: {ticket['claimed_by'] or 'não assumido'}",
            f"Motivo da abertura: {ticket['reason'] if 'reason' in ticket.keys() else 'não informado'}",
            f"Criado em: {datetime.fromtimestamp(ticket['created_at'], timezone.utc).isoformat()}",
            "=" * 72,
            "",
        ]
        async for message in channel.history(limit=None, oldest_first=True):
            timestamp = message.created_at.astimezone(timezone.utc).isoformat()
            content = message.content or "[sem texto]"
            lines.append(f"[{timestamp}] {message.author} ({message.author.id}): {content}")
            for attachment in message.attachments:
                lines.append(f"    [ANEXO] {attachment.filename} — {attachment.url}")
            for embed in message.embeds:
                if embed.title or embed.description:
                    lines.append(f"    [EMBED] {embed.title or ''} — {embed.description or ''}".replace("\n", " "))
        return "\n".join(lines)

    async def _log(self, guild, title, description, color, ticket_type=None):
        if not guild:
            return
        cfg = await db.get_ticket_config(guild.id)
        if ticket_type == "denuncia":
            channel = guild.get_channel(cfg["report_log_channel_id"]) if cfg and "report_log_channel_id" in cfg.keys() and cfg["report_log_channel_id"] else None
        else:
            channel = guild.get_channel(cfg["log_channel_id"]) if cfg and cfg["log_channel_id"] else None
        if channel:
            await channel.send(embed=KibotEmbed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc)))

    @commands.group(name="ticket", aliases=["tickets", "atendimento"], invoke_without_command=True)
    @commands.guild_only()
    async def ticket(self, ctx):
        await ctx.send("🎫 **Central de Tickets**\n`K!ticket painel` — cria/atualiza o painel\n`K!ticket configurar` — mostra a configuração\n`K!ticket adicionar @membro` — adiciona alguém ao ticket\n`K!ticket remover @membro` — remove alguém do ticket\n`K!ticket fechar` — fecha o ticket atual\n`K!ticket assumir` — assume o ticket atual")

    @ticket.command(name="painel")
    @commands.has_permissions(manage_guild=True)
    async def ticket_panel(self, ctx, canal: discord.TextChannel = None):
        _, panel, _, _, _, _, _, _, _ = await ensure_ticket_structure(ctx.guild)
        target = canal or panel
        await target.send(embed=panel_embed(), view=TicketPanelView(self))
        await ctx.send(f"✅ Painel de tickets publicado em {target.mention}.", delete_after=10)

    @ticket.command(name="configurar", aliases=["config", "status"])
    @commands.has_permissions(manage_guild=True)
    async def ticket_config(self, ctx):
        category, panel, log_channel, report_log_channel, eval_channel, arautos_role, doubt_role, mod_role, help_channel = await ensure_ticket_structure(ctx.guild)
        await ctx.send(
            f"⚙️ **Tickets configurados**\n"
            f"📁 Categoria: {category.mention}\n"
            f"🎫 Painel: {panel.mention}\n"
            f"📋 Logs: {log_channel.mention}\n"
            f"⭐ Avaliações: {eval_channel.mention}\n"
            f"🛡️ Equipe: {staff_role.mention if staff_role else 'não detectada'}"
        )

    @ticket.command(name="adicionar", aliases=["add"])
    @commands.guild_only()
    async def ticket_add(self, ctx, member: discord.Member):
        ticket = await db.get_ticket_by_channel(ctx.channel.id)
        if not ticket or (ctx.author.id != ticket["user_id"] and not is_staff(ctx.author)):
            return await ctx.send("❌ Você não pode alterar este ticket.")
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
        await ctx.send(f"➕ {member.mention} foi adicionado ao ticket.")

    @ticket.command(name="remover", aliases=["remove"])
    @commands.guild_only()
    async def ticket_remove(self, ctx, member: discord.Member):
        ticket = await db.get_ticket_by_channel(ctx.channel.id)
        if not ticket or (ctx.author.id != ticket["user_id"] and not is_staff(ctx.author)):
            return await ctx.send("❌ Você não pode alterar este ticket.")
        if member.id == ticket["user_id"]:
            return await ctx.send("❌ Não é possível remover o autor do ticket.")
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(f"➖ {member.mention} foi removido do ticket.")

    @ticket.command(name="assumir", aliases=["claim"])
    @commands.guild_only()
    async def ticket_claim(self, ctx):
        ticket = await db.get_ticket_by_channel(ctx.channel.id)
        if not ticket or not is_staff(ctx.author):
            return await ctx.send("❌ Apenas a equipe pode assumir um ticket.")
        await db.claim_ticket_record(ticket["id"], ctx.author.id)
        await ctx.send(f"🙋 {ctx.author.mention} assumiu este ticket.")

    @ticket.command(name="fechar", aliases=["close"])
    @commands.guild_only()
    async def ticket_close(self, ctx):
        ticket = await db.get_ticket_by_channel(ctx.channel.id)
        if not ticket:
            return await ctx.send("❌ Este canal não é um ticket registrado.")
        if ctx.author.id != ticket["user_id"] and not is_staff(ctx.author):
            return await ctx.send("❌ Só o solicitante ou a equipe pode fechar este ticket.")
        if ticket["id"] in self.closing_tickets:
            return await ctx.send("⏳ Este ticket já está sendo encerrado.")
        self.closing_tickets.add(ticket["id"])
        try:
            message = await ctx.send("🔒 O ticket será fechado em **5 segundos**...")
            for remaining in range(4, 0, -1):
                await asyncio.sleep(1)
                await message.edit(content=f"🔒 O ticket será fechado em **{remaining} segundo{'s' if remaining != 1 else ''}**...")
            await self._finish_close(ctx.guild, ctx.channel, ticket, ctx.author)
        finally:
            self.closing_tickets.discard(ticket["id"])

    @app_commands.command(name="ticket", description="Central de atendimento do Kibot")
    @app_commands.describe(acao="Ação desejada", canal="Canal onde o painel será publicado")
    @app_commands.choices(acao=[
        app_commands.Choice(name="🎫 Publicar painel", value="painel"),
        app_commands.Choice(name="⚙️ Configurar/mostrar configuração", value="configurar"),
        app_commands.Choice(name="🔒 Fechar ticket atual", value="fechar"),
        app_commands.Choice(name="🙋 Assumir ticket atual", value="assumir"),
    ])
    async def ticket_slash(self, interaction: discord.Interaction, acao: app_commands.Choice[str], canal: discord.TextChannel | None = None):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Use este comando em um servidor.", ephemeral=True)
        if acao.value in {"painel", "configurar"} and not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        if acao.value == "painel":
            _, panel, _, _, _, _, _, _, _ = await ensure_ticket_structure(interaction.guild)
            target = canal or panel
            await target.send(embed=panel_embed(), view=TicketPanelView(self))
            return await interaction.response.send_message(f"✅ Painel publicado em {target.mention}.", ephemeral=True)
        if acao.value == "configurar":
            category, panel, log_channel, report_log_channel, eval_channel, arautos_role, doubt_role, mod_role, help_channel = await ensure_ticket_structure(interaction.guild)
            return await interaction.response.send_message(f"⚙️ Categoria: {category.mention}\n🎫 Painel: {panel.mention}\n📋 Logs de dúvidas: {log_channel.mention}\n🚨 Logs de denúncias: {report_log_channel.mention}\n⭐ Avaliações: {eval_channel.mention}\n🆘 Ajudas: {help_channel.mention}\n🛡️ Arautos: {arautos_role.mention if arautos_role else 'não detectados'}\n🛡️ Moderadores: {mod_role.mention if mod_role else 'não detectados'}", ephemeral=True)
        ticket = await db.get_ticket_by_channel(interaction.channel.id if interaction.channel else 0)
        if not ticket:
            return await interaction.response.send_message("❌ Este canal não é um ticket.", ephemeral=True)
        if acao.value == "assumir":
            if not is_staff(interaction.user):
                return await interaction.response.send_message("❌ Apenas a equipe pode assumir tickets.", ephemeral=True)
            await db.claim_ticket_record(ticket["id"], interaction.user.id)
            return await interaction.response.send_message(f"🙋 {interaction.user.mention} assumiu este ticket.")
        if interaction.user.id != ticket["user_id"] and not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Só o solicitante ou a equipe pode fechar.", ephemeral=True)
        if ticket["id"] in self.closing_tickets:
            return await interaction.response.send_message("⏳ Este ticket já está sendo encerrado.", ephemeral=True)
        self.closing_tickets.add(ticket["id"])
        try:
            await interaction.response.send_message("🔒 O ticket será fechado em **5 segundos**...")
            message = await interaction.original_response()
            for remaining in range(4, 0, -1):
                await asyncio.sleep(1)
                await message.edit(content=f"🔒 O ticket será fechado em **{remaining} segundo{'s' if remaining != 1 else ''}**...")
            await self._finish_close(interaction.guild, interaction.channel, ticket, interaction.user)
        finally:
            self.closing_tickets.discard(ticket["id"])


async def setup(bot):
    await bot.add_cog(TicketCog(bot))
