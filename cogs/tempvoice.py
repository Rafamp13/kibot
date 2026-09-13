from cogs.embed_style import KibotEmbed
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from database import db

CATEGORY_NAME = "TEMPVOICE"
LOBBY_NAME = "Lobby"
PANEL_NAME = "🎛️・tempvoice"
DEFAULT_NAME = "🔊 {user}"
TEXT_DEFAULT_NAME = "💬・{user}"

def is_temp_channel(row):
    return row is not None

class RenameModal(discord.ui.Modal, title="Renomear sala"):
    name = discord.ui.TextInput(
        label="Nome do canal",
        placeholder="Ex.: Sala do Kiba",
        min_length=1,
        max_length=90
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog, self.channel = cog, channel

    async def on_submit(self, interaction):
        row = await db.get_tempvoice_channel(self.channel.id)
        if not row or row["owner_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Só o dono da sala pode fazer isso.", ephemeral=True)
        await self.channel.edit(name=str(self.name).strip(), reason=f"TempVoice: renomeado por {interaction.user}")
        await interaction.response.send_message(f"✅ Sala renomeada para **{self.channel.name}**.", ephemeral=True)

class LimitModal(discord.ui.Modal, title="Limite de usuários"):
    limit = discord.ui.TextInput(
        label="Limite (0 = sem limite)",
        placeholder="0 a 99",
        min_length=1,
        max_length=2
    )
    def __init__(self, cog, channel):
        super().__init__()
        self.cog, self.channel = cog, channel

    async def on_submit(self, interaction):
        row = await db.get_tempvoice_channel(self.channel.id)
        if not row or row["owner_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Só o dono da sala pode fazer isso.", ephemeral=True)
        try:
            value = int(str(self.limit).strip())
            if not 0 <= value <= 99:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ O limite precisa ser um número entre 0 e 99.", ephemeral=True)
        await self.channel.edit(user_limit=value, reason=f"TempVoice: limite por {interaction.user}")
        await interaction.response.send_message(f"✅ Limite definido para **{'sem limite' if value == 0 else value}**.", ephemeral=True)

class UserSelect(discord.ui.UserSelect):
    def __init__(self, action, channel):
        self.action, self.channel = action, channel
        super().__init__(placeholder="Selecione um membro...", min_values=1, max_values=1)

    async def callback(self, interaction):
        row = await db.get_tempvoice_channel(self.channel.id)
        if not row or row["owner_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Só o dono da sala pode gerenciar membros.", ephemeral=True)
        member = self.values[0]
        if member.bot:
            return await interaction.response.send_message("❌ Não é possível gerenciar bots por este painel.", ephemeral=True)
        if self.action == "allow":
            await self.channel.set_permissions(member, connect=True, view_channel=True, reason=f"TempVoice: acesso concedido por {interaction.user}")
            await interaction.response.send_message(f"✅ {member.mention} agora pode entrar na sala.", ephemeral=True)
        elif self.action == "deny":
            if member.voice and member.voice.channel and member.voice.channel.id == self.channel.id:
                await member.move_to(None, reason=f"TempVoice: removido por {interaction.user}")
            await self.channel.set_permissions(member, connect=False, view_channel=False, reason=f"TempVoice: acesso removido por {interaction.user}")
            await interaction.response.send_message(f"✅ {member.mention} foi removido/bloqueado da sala.", ephemeral=True)

class MemberView(discord.ui.View):
    def __init__(self, action, channel):
        super().__init__(timeout=60)
        self.add_item(UserSelect(action, channel))

class TempVoicePanel(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def _owner_channel(self, interaction):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if not channel:
            await interaction.response.send_message("❌ Você não está em uma sala de voz TempVoice.", ephemeral=True)
            return None
        row = await db.get_tempvoice_channel(channel.id)
        if not row or row["owner_id"] != interaction.user.id:
            await interaction.response.send_message("❌ Você precisa ser o dono da sala para usar este painel.", ephemeral=True)
            return None
        return channel

    @discord.ui.button(label="Renomear", emoji="✏️", style=discord.ButtonStyle.primary, custom_id="tempvoice:rename")
    async def rename(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if channel:
            await interaction.response.send_modal(RenameModal(self.cog, channel))

    @discord.ui.button(label="Limite", emoji="👥", style=discord.ButtonStyle.secondary, custom_id="tempvoice:limit")
    async def limit(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if channel:
            await interaction.response.send_modal(LimitModal(self.cog, channel))

    @discord.ui.button(label="Trancar", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="tempvoice:lock")
    async def lock(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, connect=False, reason=f"TempVoice: trancado por {interaction.user}")
        await interaction.response.send_message("🔒 Sua sala foi trancada.", ephemeral=True)

    @discord.ui.button(label="Destrancar", emoji="🔓", style=discord.ButtonStyle.success, custom_id="tempvoice:unlock")
    async def unlock(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, connect=True, reason=f"TempVoice: destrancado por {interaction.user}")
        await interaction.response.send_message("🔓 Sua sala foi destrancada.", ephemeral=True)

    @discord.ui.button(label="Convidar", emoji="➕", style=discord.ButtonStyle.success, custom_id="tempvoice:allow")
    async def allow(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if channel:
            await interaction.response.send_message("Escolha quem poderá entrar:", view=MemberView("allow", channel), ephemeral=True)

    @discord.ui.button(label="Bloquear", emoji="🚫", style=discord.ButtonStyle.danger, custom_id="tempvoice:deny")
    async def deny(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if channel:
            await interaction.response.send_message("Escolha quem será removido/bloqueado:", view=MemberView("deny", channel), ephemeral=True)

    @discord.ui.button(label="Ocultar", emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="tempvoice:hide")
    async def hide(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, view_channel=False, connect=False, reason=f"TempVoice: ocultado por {interaction.user}")
        await channel.set_permissions(interaction.user, view_channel=True, connect=True, reason="TempVoice: dono")
        await interaction.response.send_message("👁️ Sua sala agora está oculta.", ephemeral=True)

    @discord.ui.button(label="Mostrar", emoji="👀", style=discord.ButtonStyle.secondary, custom_id="tempvoice:show")
    async def show(self, interaction, button):
        channel = await self._owner_channel(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, view_channel=True, connect=True, reason=f"TempVoice: exibido por {interaction.user}")
        await interaction.response.send_message("👀 Sua sala voltou a ficar visível.", ephemeral=True)

class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._locks = {}
        self._bootstrap_task = None

    async def cog_load(self):
        # View persistente é registrada também após reinicialização.
        self.bot.add_view(TempVoicePanel(self))

    async def ensure_guild(self, guild):
        cfg = await db.get_tempvoice_config(guild.id)
        category = guild.get_channel(cfg["category_id"]) if cfg and cfg["category_id"] else None
        lobby = guild.get_channel(cfg["lobby_channel_id"]) if cfg and cfg["lobby_channel_id"] else None
        panel = guild.get_channel(cfg["panel_channel_id"]) if cfg and cfg["panel_channel_id"] else None

        if not isinstance(category, discord.CategoryChannel):
            category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if not category:
            category = await guild.create_category(CATEGORY_NAME, reason="TempVoice automático do Kibot")

        if not isinstance(lobby, discord.VoiceChannel) or lobby.category_id != category.id:
            lobby = discord.utils.get(category.voice_channels, name=LOBBY_NAME)
        if not lobby:
            lobby = await guild.create_voice_channel(LOBBY_NAME, category=category, reason="Lobby TempVoice automático")

        if not isinstance(panel, discord.TextChannel) or panel.category_id != category.id:
            panel = discord.utils.get(category.text_channels, name=PANEL_NAME)
        if not panel:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)
            }
            panel = await guild.create_text_channel(PANEL_NAME, category=category, overwrites=overwrites,
                                                     reason="Painel TempVoice automático")
        await db.set_tempvoice_config(guild.id, category.id, lobby.id, panel.id)
        await self._ensure_panel_message(panel)
        return category, lobby, panel

    async def _sync_text_permissions(self, voice, text, owner_id=None):
        """Mantém o canal de texto espelhando quem está na sala de voz."""
        if not isinstance(text, discord.TextChannel):
            return
        guild = voice.guild
        owner_id = int(owner_id) if owner_id else None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False, send_messages=False, read_message_history=False
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                manage_channels=True, manage_messages=True, embed_links=True
            ),
        }
        # Apenas quem está na voz enxerga/fala no texto correspondente.
        for member in voice.members:
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )
        if owner_id:
            owner = guild.get_member(owner_id)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    manage_channels=True, manage_messages=True
                )
        try:
            await text.edit(overwrites=overwrites, reason="TempVoice: sincronização do canal de texto")
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _ensure_panel_message(self, panel):
        marker = "KIBOT_TEMPVOICE_PANEL"
        try:
            async for msg in panel.history(limit=20):
                if msg.author == self.bot.user and msg.embeds and msg.embeds[0].footer and msg.embeds[0].footer.text == marker:
                    return
            embed = KibotEmbed(
                title="🎛️ TempVoice — Controle sua sala",
                description=(
                    "Entre no **Lobby** para criar sua sala privada temporária.\n\n"
                    "Quando sua sala for criada, use os botões abaixo para gerenciá-la:\n"
                    "✏️ Renomear • 👥 Limite • 🔒 Trancar • 🔓 Destrancar\n"
                    "➕ Convidar • 🚫 Bloquear • 👁️ Ocultar • 👀 Mostrar\n\n"
                    "**Importante:** apenas o dono da sala pode usar o painel. "
                    "Quando a sala ficar vazia, ela é excluída automaticamente."
                ),
                color=discord.Color.blurple()
            )
            embed.set_footer(text=marker)
            await panel.send(embed=embed, view=TempVoicePanel(self))
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _ensure_pair_text(self, guild, category, voice, owner_id):
        """Garante o canal de texto privado correspondente à sala de voz."""
        row = await db.get_tempvoice_channel(voice.id)
        text = guild.get_channel(row["text_channel_id"]) if row and row["text_channel_id"] else None
        if not isinstance(text, discord.TextChannel):
            owner = guild.get_member(int(owner_id))
            username = owner.display_name[:80] if owner else voice.name.replace("🔊 ", "")[:80]
            text = discord.utils.get(category.text_channels, name=TEXT_DEFAULT_NAME.format(user=username))
        if not text:
            text = await guild.create_text_channel(
                TEXT_DEFAULT_NAME.format(user=(guild.get_member(int(owner_id)).display_name[:80] if guild.get_member(int(owner_id)) else voice.name.replace("🔊 ", "")[:80])),
                category=category,
                reason="Canal de texto TempVoice automático"
            )
        else:
            await text.edit(category=category, reason="Sincronização do TempVoice")
        await self._sync_text_permissions(voice, text, owner_id)
        await self._ensure_temp_text_panel(text, voice)
        return text

    async def _ensure_temp_text_panel(self, text, voice):
        marker = f"KIBOT_TEMPVOICE_ROOM_{voice.id}"
        try:
            async for msg in text.history(limit=20):
                if msg.author == self.bot.user and msg.embeds and msg.embeds[0].footer and msg.embeds[0].footer.text == marker:
                    return
            embed = KibotEmbed(
                title=f"🎛️ {voice.name}",
                description=(
                    f"Este é o canal de texto temporário da sala de voz **{voice.name}**.\n\n"
                    "Converse aqui enquanto estiver na sala. O acesso acompanha os membros da voz e "
                    "o canal será excluído junto com a sala quando ela ficar vazia.\n\n"
                    "Use o painel **🎛️ TempVoice** do servidor para gerenciar sua sala."
                ),
                color=discord.Color.blurple()
            )
            embed.set_footer(text=marker)
            await text.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                category, _, _ = await self.ensure_guild(guild)
                for row in await db.get_tempvoice_channels(guild.id):
                    voice = guild.get_channel(row["channel_id"])
                    if isinstance(voice, discord.VoiceChannel):
                        await self._ensure_pair_text(guild, category, voice, row["owner_id"])
            except discord.Forbidden:
                print(f"[TempVoice] Sem permissões para configurar automaticamente em {guild.name} ({guild.id}).")
            except Exception:
                import logging
                logging.getLogger("kibot").exception("Falha ao configurar TempVoice em %s", guild.name)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        cfg = await db.get_tempvoice_config(guild.id)
        if not cfg:
            return
        lobby_id = cfg["lobby_channel_id"]

        # Qualquer entrada/saída mantém o chat da sala sincronizado com a voz.
        if after.channel:
            after_row = await db.get_tempvoice_channel(after.channel.id)
            if after_row:
                text_id = after_row["text_channel_id"] if "text_channel_id" in after_row.keys() else None
                text = guild.get_channel(text_id) if text_id else None
                if text:
                    await self._sync_text_permissions(after.channel, text, after_row["owner_id"])

        # Entrou no Lobby -> cria a sala e move o membro.
        if after.channel and after.channel.id == lobby_id:
            lock = self._locks.setdefault(guild.id, asyncio.Lock())
            async with lock:
                # Evita duplicar em eventos de reconexão.
                current = member.voice.channel if member.voice else None
                if current and current.id != lobby_id:
                    return
                category = guild.get_channel(cfg["category_id"])
                if not isinstance(category, discord.CategoryChannel):
                    _, lobby, _ = await self.ensure_guild(guild)
                    category = lobby.category
                name = DEFAULT_NAME.format(user=member.display_name[:80])
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
                    member: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True, move_members=True)
                }
                channel = await guild.create_voice_channel(
                    name, category=category, overwrites=overwrites,
                    reason=f"TempVoice criado para {member} ({member.id})"
                )
                text_channel = await guild.create_text_channel(
                    TEXT_DEFAULT_NAME.format(user=member.display_name[:80]),
                    category=category,
                    overwrites={
                        guild.default_role: discord.PermissionOverwrite(view_channel=False, send_messages=False, read_message_history=False),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True),
                        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True)
                    },
                    reason=f"Canal de texto TempVoice criado para {member} ({member.id})"
                )
                await db.register_tempvoice_channel(guild.id, channel.id, member.id, text_channel.id)
                await self._ensure_temp_text_panel(text_channel, channel)
                try:
                    await member.move_to(channel, reason="TempVoice: entrada pelo Lobby")
                except (discord.Forbidden, discord.HTTPException):
                    await channel.delete(reason="TempVoice: não foi possível mover o criador")
                    try:
                        await text_channel.delete(reason="TempVoice: rollback da sala")
                    except (discord.NotFound, discord.Forbidden):
                        pass
                    await db.unregister_tempvoice_channel(channel.id)
                    return

                await self._sync_text_permissions(channel, text_channel, member.id)

                # O painel é um canal de texto central e não exige configuração manual.
                try:
                    await member.send(f"🎛️ Sua sala **{channel.name}** foi criada em **{guild.name}**. Gerencie-a no canal {guild.get_channel(cfg['panel_channel_id']).mention}.")
                except discord.HTTPException:
                    pass

        # Saiu de uma sala TempVoice -> apaga se ficou vazia.
        if before.channel:
            row = await db.get_tempvoice_channel(before.channel.id)
            if row:
                channel = before.channel
                if len(channel.members) == 0:
                    text_id = row["text_channel_id"] if "text_channel_id" in row.keys() else None
                    text_channel = guild.get_channel(text_id) if text_id else None
                    await db.unregister_tempvoice_channel(channel.id)
                    try:
                        await channel.delete(reason="TempVoice vazio")
                    except discord.NotFound:
                        pass
                    if text_channel:
                        try:
                            await text_channel.delete(reason="Canal de texto TempVoice vazio")
                        except discord.NotFound:
                            pass
                elif int(row["owner_id"]) == member.id:
                    # Transfere a posse para o membro que permaneceu há mais tempo no canal.
                    new_owner = min(channel.members, key=lambda m: m.joined_at or discord.utils.utcnow())
                    await db.set_tempvoice_owner(channel.id, new_owner.id)
                    await channel.set_permissions(new_owner, view_channel=True, connect=True, manage_channels=True, move_members=True)
                    text_id = row["text_channel_id"] if "text_channel_id" in row.keys() else None
                    text_channel = guild.get_channel(text_id) if text_id else None
                    if text_channel:
                        await self._sync_text_permissions(channel, text_channel, new_owner.id)
                    try:
                        await new_owner.send(f"👑 Você agora é o dono da sala **{channel.name}** porque o proprietário saiu.")
                    except discord.HTTPException:
                        pass
                else:
                    text_id = row["text_channel_id"] if "text_channel_id" in row.keys() else None
                    text_channel = guild.get_channel(text_id) if text_id else None
                    if text_channel:
                        await self._sync_text_permissions(channel, text_channel, row["owner_id"])

async def setup(bot):
    await bot.add_cog(TempVoice(bot))
