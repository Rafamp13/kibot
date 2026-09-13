"""Painéis para adicionar emojis e figurinhas ao servidor."""
import asyncio
import io
import re
import urllib.request
import urllib.parse
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

from cogs.embed_style import KibotEmbed

EMOJI_MAX_BYTES = 256 * 1024
STICKER_MAX_BYTES = 512 * 1024
URL_TIMEOUT = 15
CUSTOM_EMOJI_RE = re.compile(r"<a?:([A-Za-z0-9_]{2,32}):(\d{15,25})>")


def _safe_name(value: str, *, max_len: int = 30) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", (value or "").strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:max_len]


def _filename_for(url: str, fallback: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".apng"}:
        suffix = ".png"
    return fallback + suffix


def _download_url_sync(url: str, max_bytes: int):
    if not re.match(r"^https?://", url, re.I):
        raise ValueError("A URL precisa começar com http:// ou https://.")
    request = urllib.request.Request(url, headers={"User-Agent": "Kibot/43 Discord Bot"})
    with urllib.request.urlopen(request, timeout=URL_TIMEOUT) as response:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError(f"O arquivo ultrapassa o limite de {max_bytes // 1024} KB.")
        chunks = []
        total = 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"O arquivo ultrapassa o limite de {max_bytes // 1024} KB.")
            chunks.append(chunk)
        return b"".join(chunks), response.headers.get_content_type(), response.geturl()


async def download_url(url: str, max_bytes: int):
    return await asyncio.to_thread(_download_url_sync, url.strip(), max_bytes)


async def attachment_bytes(attachment: discord.Attachment, max_bytes: int):
    if attachment.size and attachment.size > max_bytes:
        raise ValueError(f"O arquivo ultrapassa o limite de {max_bytes // 1024} KB.")
    data = await attachment.read()
    if len(data) > max_bytes:
        raise ValueError(f"O arquivo ultrapassa o limite de {max_bytes // 1024} KB.")
    return data, attachment.content_type or "application/octet-stream", attachment.filename


class AssetUrlModal(discord.ui.Modal):
    def __init__(self, panel, asset_kind: str):
        super().__init__(title="Adicionar figurinha" if asset_kind == "sticker" else "Adicionar emoji")
        self.panel = panel
        self.asset_kind = asset_kind
        self.name_input = discord.ui.TextInput(
            label="Nome",
            placeholder="ex.: kibacursed",
            min_length=2,
            max_length=30 if asset_kind == "sticker" else 32,
            required=True,
        )
        self.url_input = discord.ui.TextInput(
            label="URL da imagem",
            placeholder="https://.../imagem.png",
            max_length=500,
            required=True,
        )
        self.add_item(self.name_input)
        self.add_item(self.url_input)
        if asset_kind == "sticker":
            self.emoji_input = discord.ui.TextInput(
                label="Emoji associado",
                placeholder="😈",
                max_length=8,
                required=False,
                default="😈",
            )
            self.add_item(self.emoji_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.panel.create_from_url(
            interaction,
            str(self.name_input.value),
            str(self.url_input.value),
            str(getattr(self, "emoji_input", "😈").value) if hasattr(self, "emoji_input") else None,
        )


class AssetFileModal(discord.ui.Modal):
    def __init__(self, panel, asset_kind: str):
        super().__init__(title="Preparar figurinha" if asset_kind == "sticker" else "Preparar emoji")
        self.panel = panel
        self.asset_kind = asset_kind
        self.name_input = discord.ui.TextInput(
            label="Nome",
            placeholder="ex.: kibacursed",
            min_length=2,
            max_length=30 if asset_kind == "sticker" else 32,
            required=True,
        )
        self.add_item(self.name_input)
        if asset_kind == "sticker":
            self.emoji_input = discord.ui.TextInput(label="Emoji associado", placeholder="😈", max_length=8, required=False, default="😈")
            self.add_item(self.emoji_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"📎 Agora envie **o arquivo/imagem** neste canal nos próximos **120 segundos**.\n"
            f"O nome será `{self.name_input.value}`.\n"
            + (f"Emoji associado: {self.emoji_input.value}\n" if self.asset_kind == "sticker" else "")
            + "O Kibot vai pegar o anexo e adicionar automaticamente.",
            ephemeral=True,
        )
        emoji = str(self.emoji_input.value) if self.asset_kind == "sticker" else None
        await self.panel.wait_for_attachment(interaction, str(self.name_input.value), emoji)


class AssetPanelView(discord.ui.View):
    def __init__(self, bot, author: discord.Member, asset_kind: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.author = author
        self.asset_kind = asset_kind
        label = "figurinha" if asset_kind == "sticker" else "emoji"
        self.title_label = label

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("🔒 Esse painel pertence a quem abriu o comando. Abra seu próprio painel com `K!addemoji` ou `K!addfigurinha`.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📎 Arquivo / imagem", style=discord.ButtonStyle.primary, row=0)
    async def file_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AssetFileModal(self, self.asset_kind))

    @discord.ui.button(label="🔗 URL da imagem", style=discord.ButtonStyle.secondary, row=0)
    async def url_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AssetUrlModal(self, self.asset_kind))

    @discord.ui.button(label="🧩 Já existente", style=discord.ButtonStyle.success, row=1)
    async def existing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            ("🧩 **Figurinha existente:** envie uma mensagem contendo a figurinha que deseja importar.\n"
             "Ela pode vir de outro servidor. O Kibot vai baixar o arquivo e recriá-la neste servidor.\n\n"
             "Se for um emoji, use o botão de emoji existente e envie o emoji personalizado."),
            ephemeral=True,
        ) if self.asset_kind == "sticker" else await interaction.response.send_message(
            "🧩 **Emoji existente:** envie uma mensagem contendo o emoji personalizado (`<:nome:id>` ou `<a:nome:id>`) que deseja importar. O Kibot vai copiar a imagem para este servidor.",
            ephemeral=True,
        )
        await self.wait_for_existing(interaction)

    @discord.ui.button(label="❌ Fechar", style=discord.ButtonStyle.danger, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="🗑️ Painel fechado.", embed=None, view=None)

    async def _wait_message(self, interaction, predicate):
        def check(message):
            return message.author.id == self.author.id and message.channel.id == interaction.channel_id and predicate(message)
        try:
            return await self.bot.wait_for("message", timeout=120, check=check)
        except asyncio.TimeoutError:
            try:
                await interaction.followup.send("⌛ Tempo esgotado. Abra o painel novamente quando quiser.", ephemeral=True)
            except Exception:
                pass
            return None

    async def wait_for_attachment(self, interaction, name, sticker_emoji=None):
        msg = await self._wait_message(interaction, lambda m: bool(m.attachments))
        if not msg:
            return
        attachment = msg.attachments[0]
        try:
            data, _, filename = await attachment_bytes(attachment, STICKER_MAX_BYTES if self.asset_kind == "sticker" else EMOJI_MAX_BYTES)
            await self._create(interaction, name, data, filename, sticker_emoji)
            try:
                await msg.delete()
            except Exception:
                pass
        except Exception as exc:
            await interaction.followup.send(f"❌ Não consegui adicionar o arquivo: {exc}", ephemeral=True)

    async def wait_for_existing(self, interaction):
        if self.asset_kind == "sticker":
            msg = await self._wait_message(interaction, lambda m: bool(getattr(m, "stickers", [])))
            if not msg:
                return
            sticker = msg.stickers[0]
            try:
                data, _, final_url = await download_url(str(sticker.url), STICKER_MAX_BYTES)
                name = _safe_name(getattr(sticker, "name", "sticker") or "sticker") or "sticker"
                emoji = getattr(sticker, "emoji", None) or "😈"
                await self._create(interaction, name, data, _filename_for(final_url, name), emoji)
            except Exception as exc:
                await interaction.followup.send(f"❌ Não consegui importar essa figurinha: {exc}", ephemeral=True)
        else:
            msg = await self._wait_message(interaction, lambda m: bool(CUSTOM_EMOJI_RE.search(m.content or "")))
            if not msg:
                return
            match = CUSTOM_EMOJI_RE.search(msg.content or "")
            pe = discord.PartialEmoji.from_str(match.group(0))
            try:
                data, _, final_url = await download_url(str(pe.url), EMOJI_MAX_BYTES)
                name = _safe_name(pe.name or "emoji", max_len=32) or "emoji"
                await self._create(interaction, name, data, _filename_for(final_url, name), None)
            except Exception as exc:
                await interaction.followup.send(f"❌ Não consegui importar esse emoji: {exc}", ephemeral=True)

    async def create_from_url(self, interaction, name, url, sticker_emoji=None):
        clean = _safe_name(name, max_len=30 if self.asset_kind == "sticker" else 32)
        if len(clean) < 2:
            return await interaction.response.send_message("❌ O nome precisa ter pelo menos 2 caracteres alfanuméricos ou `_`.", ephemeral=True)
        try:
            data, _, final_url = await download_url(url, STICKER_MAX_BYTES if self.asset_kind == "sticker" else EMOJI_MAX_BYTES)
            await interaction.followup.send("⏳ Baixando e adicionando...", ephemeral=True)
            await self._create(interaction, clean, data, _filename_for(final_url, clean), sticker_emoji)
        except Exception as exc:
            await interaction.followup.send(f"❌ Não consegui baixar a imagem: {exc}", ephemeral=True)

    async def _create(self, interaction, name, data, filename, sticker_emoji=None):
        name = _safe_name(name, max_len=30 if self.asset_kind == "sticker" else 32)
        if len(name) < 2:
            raise ValueError("Nome inválido. Use pelo menos 2 caracteres alfanuméricos ou `_`.")
        guild = interaction.guild
        reason = f"Adicionado por {interaction.user} via Kibot"
        if self.asset_kind == "emoji":
            emoji = await guild.create_custom_emoji(name=name, image=data, reason=reason)
            await interaction.followup.send(f"✅ Emoji criado com sucesso: {emoji} (`{emoji.name}`)", ephemeral=True)
            return
        emoji = (sticker_emoji or "😈").strip()[:8] or "😈"
        file = discord.File(io.BytesIO(data), filename=filename)
        sticker = await guild.create_sticker(name=name, description="Figurinha adicionada pelo Kibot.", emoji=emoji, file=file, reason=reason)
        await interaction.followup.send(f"✅ Figurinha **{sticker.name}** adicionada ao servidor! {emoji}", ephemeral=True)


class ServerAssets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _panel(self, interaction_or_ctx, asset_kind):
        guild = interaction_or_ctx.guild
        member = interaction_or_ctx.user if isinstance(interaction_or_ctx, discord.Interaction) else interaction_or_ctx.author
        me = guild.me
        if not me or not me.guild_permissions.manage_emojis_and_stickers:
            text = "❌ Preciso da permissão **Gerenciar Expressões** (`Gerenciar emojis e figurinhas`) para fazer isso."
            return await interaction_or_ctx.response.send_message(text, ephemeral=True) if isinstance(interaction_or_ctx, discord.Interaction) else await interaction_or_ctx.send(text)
        label = "FIGURINHA" if asset_kind == "sticker" else "EMOJI"
        description = (
            f"Escolha como você quer adicionar o **{label}** ao servidor.\n\n"
            "📎 **Arquivo / imagem** — o Kibot espera um anexo enviado por você.\n"
            "🔗 **URL da imagem** — informe uma URL direta para a imagem.\n"
            "🧩 **Já existente** — envie uma figurinha/emoji personalizado que já existe e o Kibot tenta importar a imagem.\n\n"
            "🔐 O painel só pode ser usado por quem abriu o comando."
        )
        embed = KibotEmbed(title=f"🛠️ Adicionar {label.title()} ao servidor", description=description, color=discord.Color.blurple())
        view = AssetPanelView(self.bot, member, asset_kind)
        if isinstance(interaction_or_ctx, discord.Interaction):
            await interaction_or_ctx.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction_or_ctx.send(embed=embed, view=view)

    @commands.command(name="addfigurinha", aliases=["addsticker", "sticker", "figurinha"])
    @commands.guild_only()
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def addfigurinha(self, ctx):
        await self._panel(ctx, "sticker")

    @commands.command(name="addemoji", aliases=["emoji", "addemote"])
    @commands.guild_only()
    @commands.has_permissions(manage_emojis_and_stickers=True)
    async def addemoji(self, ctx):
        await self._panel(ctx, "emoji")

    @app_commands.command(name="addfigurinha", description="Abre o painel para adicionar uma figurinha ao servidor")
    @app_commands.checks.has_permissions(manage_emojis_and_stickers=True)
    async def addfigurinha_slash(self, interaction):
        await self._panel(interaction, "sticker")

    @app_commands.command(name="addemoji", description="Abre o painel para adicionar um emoji ao servidor")
    @app_commands.checks.has_permissions(manage_emojis_and_stickers=True)
    async def addemoji_slash(self, interaction):
        await self._panel(interaction, "emoji")


async def setup(bot):
    await bot.add_cog(ServerAssets(bot))
