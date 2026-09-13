"""Construtor visual de Embeds do Kibot."""
from cogs.embed_style import KibotEmbed
import re
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

MAX_FIELD_VALUE = 1024
MAX_FIELDS = 25


def parse_color(value: str | None):
    if not value:
        return discord.Color.gold()
    value = value.strip().lower().replace("#", "")
    if value.startswith("0x"):
        value = value[2:]
    if not re.fullmatch(r"[0-9a-f]{6}", value):
        raise ValueError("cor inválida; use HEX, por exemplo `#C9A227`.")
    return discord.Color(int(value, 16))


def parse_timestamp(value: str | None):
    if not value:
        return None
    value = value.strip()
    if value.lower() in {"agora", "now", "sim"}:
        return discord.utils.utcnow()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp inválido; use `agora` ou ISO 8601.")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def build_embed(data: dict) -> discord.Embed:
    e = KibotEmbed(
        title=data.get("title") or None,
        description=data.get("description") or None,
        color=parse_color(data.get("color")),
        url=data.get("url") or None,
        timestamp=parse_timestamp(data.get("timestamp")),
    )
    if data.get("author"):
        e.set_author(name=data["author"], url=data.get("author_url") or None,
                     icon_url=data.get("author_icon") or None)
    if data.get("thumbnail"):
        e.set_thumbnail(url=data["thumbnail"])
    if data.get("image"):
        e.set_image(url=data["image"])
    if data.get("footer"):
        e.set_footer(text=data["footer"], icon_url=data.get("footer_icon") or None)
    for field in data.get("fields", [])[:MAX_FIELDS]:
        e.add_field(name=field["name"][:256], value=field["value"][:MAX_FIELD_VALUE], inline=field.get("inline", False))
    return e


def empty_data():
    return {
        "title": "",
        "description": "",
        "color": "C9A227",
        "url": "",
        "author": "",
        "author_url": "",
        "author_icon": "",
        "thumbnail": "",
        "image": "",
        "footer": "",
        "footer_icon": "",
        "timestamp": "",
        "fields": [],
    }


def safe_url(value: str):
    if not value:
        return True
    return value.startswith(("http://", "https://"))


class TextModal(discord.ui.Modal):
    def __init__(self, builder, title, key, label, default="", required=False, max_length=4000):
        super().__init__(title=title[:45], timeout=300)
        self.builder = builder
        self.key = key
        self.value_input = discord.ui.TextInput(label=label[:45], default=default[:4000], required=required,
                                                 max_length=max_length, style=discord.TextStyle.paragraph if max_length > 300 else discord.TextStyle.short)
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction):
        value = str(self.value_input.value).strip()
        if self.key in {"url", "author_url", "author_icon", "thumbnail", "image", "footer_icon"} and not safe_url(value):
            await interaction.response.send_message("❌ Essa URL tá errada kkkkk. Ela precisa começar com `http://` ou `https://`.", ephemeral=True)
            return
        self.builder.data[self.key] = value
        await interaction.response.defer()
        await self.builder.refresh()


class ColorModal(discord.ui.Modal):
    def __init__(self, builder):
        super().__init__(title="🎨 Cor da Embed")
        self.builder = builder
        self.value_input = discord.ui.TextInput(label="Cor HEX", placeholder="#C9A227", default=builder.data.get("color", "C9A227"), max_length=7)
        self.add_item(self.value_input)

    async def on_submit(self, interaction):
        try:
            parse_color(str(self.value_input.value))
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        self.builder.data["color"] = str(self.value_input.value).strip()
        await interaction.response.defer()
        await self.builder.refresh()


class FieldModal(discord.ui.Modal):
    def __init__(self, builder, index=None):
        super().__init__(title="➕ Adicionar campo" if index is None else "✏️ Editar campo")
        self.builder = builder
        self.index = index
        old = builder.data["fields"][index] if index is not None else {"name": "", "value": "", "inline": False}
        self.name_input = discord.ui.TextInput(label="Nome do campo", default=old["name"][:256], max_length=256)
        self.value_input = discord.ui.TextInput(label="Valor do campo", default=old["value"][:1024], max_length=1024, style=discord.TextStyle.paragraph)
        self.inline_input = discord.ui.TextInput(label="Inline? (sim/não)", default="sim" if old.get("inline") else "não", max_length=3)
        self.add_item(self.name_input)
        self.add_item(self.value_input)
        self.add_item(self.inline_input)

    async def on_submit(self, interaction):
        field = {"name": str(self.name_input.value).strip(), "value": str(self.value_input.value).strip(),
                 "inline": str(self.inline_input.value).strip().lower() in {"sim", "s", "yes", "true", "1"}}
        if not field["name"] or not field["value"]:
            await interaction.response.send_message("❌ Coloca o nome e o valor aí, senão não tenho o que montar kkkkk.", ephemeral=True)
            return
        if self.index is None:
            if len(self.builder.data["fields"]) >= MAX_FIELDS:
                await interaction.response.send_message("❌ O Discord deixa no máximo 25 campos por Embed.", ephemeral=True)
                return
            self.builder.data["fields"].append(field)
        else:
            self.builder.data["fields"][self.index] = field
        await interaction.response.defer()
        await self.builder.refresh()


class FieldSelect(discord.ui.Select):
    def __init__(self, builder):
        self.builder = builder
        options = [discord.SelectOption(label=f"{i+1}. {f['name'][:90]}", value=str(i)) for i, f in enumerate(builder.data["fields"][:25])]
        super().__init__(placeholder="Escolha um campo para editar/remover...", min_values=1, max_values=1, options=options, row=4)

    async def callback(self, interaction):
        index = int(self.values[0])
        self.builder.selected_field = index
        await interaction.response.send_message(
            f"📌 Campo **{index + 1}** selecionado. Use **Editar campo** ou **Remover campo**.", ephemeral=True)


class ChannelPicker(discord.ui.View):
    def __init__(self, panel):
        super().__init__(timeout=120)
        self.panel = panel
        select = discord.ui.ChannelSelect(
            placeholder="Selecione o canal onde a Embed será enviada...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1, max_values=1, row=0,
        )
        async def callback(interaction: discord.Interaction):
            channel = select.values[0]
            if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                await interaction.response.send_message("❌ Escolhe um canal de texto primeiro.", ephemeral=True)
                return
            self.panel.target_channel_id = channel.id
            await interaction.response.send_message(f"✅ Canal definido: {channel.mention}", ephemeral=True)
            await self.panel.refresh()
            self.stop()
        select.callback = callback
        self.add_item(select)


class EmbedPanel(discord.ui.View):
    def __init__(self, author_id, channel_id, bot, private=True):
        super().__init__(timeout=900)
        self.author_id = author_id
        self.channel_id = channel_id
        self.target_channel_id = None
        self.bot = bot
        self.private = private
        self.data = empty_data()
        self.selected_field = None
        self.message = None
        self.rebuild_items()

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("🔒 Este construtor pertence a outra pessoa.", ephemeral=True)
            return False
        return True

    def rebuild_items(self):
        # Discord permite no máximo 5 componentes por linha e 25 no total.
        self.clear_items()
        buttons = [
            ("📝 Título", discord.ButtonStyle.secondary, self.title_button, 0),
            ("📄 Descrição", discord.ButtonStyle.secondary, self.description_button, 0),
            ("🎨 Cor", discord.ButtonStyle.secondary, self.color_button, 0),
            ("🔗 URL", discord.ButtonStyle.secondary, self.url_button, 0),
            ("👤 Autor", discord.ButtonStyle.secondary, self.author_button, 1),
            ("🖼️ Thumbnail", discord.ButtonStyle.secondary, self.thumbnail_button, 1),
            ("🌄 Imagem", discord.ButtonStyle.secondary, self.image_button, 1),
            ("📌 Rodapé", discord.ButtonStyle.secondary, self.footer_button, 1),
            ("🕐 Timestamp", discord.ButtonStyle.secondary, self.timestamp_button, 1),
            ("➕ Campo", discord.ButtonStyle.secondary, self.add_field_button, 2),
            ("✏️ Editar campo", discord.ButtonStyle.primary, self.edit_field_button, 2),
            ("🗑️ Remover campo", discord.ButtonStyle.danger, self.remove_field_button, 2),
            ("📨 Canal", discord.ButtonStyle.primary, self.channel_button, 3),
            ("📤 Enviar", discord.ButtonStyle.success, self.send_button, 3),
            ("🔄 Limpar", discord.ButtonStyle.secondary, self.clear_button, 3),
            ("❌ Cancelar", discord.ButtonStyle.danger, self.cancel_button, 3),
        ]
        for label, style, callback, row in buttons:
            b = discord.ui.Button(label=label, style=style, row=row)
            b.callback = callback
            self.add_item(b)
        if self.data["fields"]:
            self.add_item(FieldSelect(self))

    def panel_embed(self):
        e = build_embed(self.data)
        e.title = "🦅 KIBOT • CONSTRUTOR DE EMBED" if not self.data["title"] else self.data["title"]
        if not self.data["description"]:
            e.description = "Usa os botões aí embaixo pra montar sua Embed.\n\n**A prévia vai mudando na hora 👀**"
        return e

    def panel_content(self):
        d = self.data
        fields = len(d["fields"])
        status = [
            f"**Título:** {'✅' if d['title'] else '—'}",
            f"**Descrição:** {'✅' if d['description'] else '—'}",
            f"**Cor:** `#{str(d['color']).replace('#','')}`",
            f"**Campos:** `{fields}/25`",
        ]
        target = f"<#{self.target_channel_id}>" if self.target_channel_id else "❌ Nenhum canal"
        status.append(f"**Enviar para:** {target}")
        return "🛠️ **Construtor visual** • clique nos botões para editar\n" + " • ".join(status)

    async def refresh(self):
        self.rebuild_items()
        if self.message:
            await self.message.edit(content=self.panel_content(), embed=self.panel_embed(), view=self)

    async def title_button(self, interaction):
        await interaction.response.send_modal(TextModal(self, "📝 Título", "title", "Título", self.data["title"], False, 256))

    async def description_button(self, interaction):
        await interaction.response.send_modal(TextModal(self, "📄 Descrição", "description", "Descrição", self.data["description"], False, 4000))

    async def color_button(self, interaction):
        await interaction.response.send_modal(ColorModal(self))

    async def url_button(self, interaction):
        await interaction.response.send_modal(TextModal(self, "🔗 URL", "url", "URL", self.data["url"], False, 500))

    async def author_button(self, interaction):
        await interaction.response.send_modal(AuthorModal(self))

    async def thumbnail_button(self, interaction):
        await interaction.response.send_modal(TextModal(self, "🖼️ Thumbnail", "thumbnail", "URL da miniatura", self.data["thumbnail"], False, 500))

    async def image_button(self, interaction):
        await interaction.response.send_modal(TextModal(self, "🌄 Imagem", "image", "URL da imagem", self.data["image"], False, 500))

    async def footer_button(self, interaction):
        await interaction.response.send_modal(FooterModal(self))

    async def timestamp_button(self, interaction):
        await interaction.response.send_modal(TextModal(self, "🕐 Timestamp", "timestamp", "Digite 'agora' ou ISO 8601; deixe vazio para remover", self.data["timestamp"], False, 50))

    async def add_field_button(self, interaction):
        await interaction.response.send_modal(FieldModal(self))

    async def edit_field_button(self, interaction):
        if self.selected_field is None or self.selected_field >= len(self.data["fields"]):
            await interaction.response.send_message("📌 Primeiro selecione um campo no menu abaixo.", ephemeral=True)
            return
        await interaction.response.send_modal(FieldModal(self, self.selected_field))

    async def remove_field_button(self, interaction):
        if self.selected_field is None or self.selected_field >= len(self.data["fields"]):
            await interaction.response.send_message("📌 Primeiro selecione um campo no menu abaixo.", ephemeral=True)
            return
        removed = self.data["fields"].pop(self.selected_field)
        self.selected_field = None
        await interaction.response.defer()
        await self.refresh()
        await interaction.followup.send(f"🗑️ Campo **{removed['name']}** removido.", ephemeral=True)

    async def channel_button(self, interaction):
        picker = ChannelPicker(self)
        await interaction.response.send_message(
            "📨 **Escolha o canal de destino**",
            view=picker,
            ephemeral=True,
        )

    async def send_button(self, interaction):
        if not self.target_channel_id:
            await interaction.response.send_message("❌ Escolhe primeiro o canal de destino.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(self.target_channel_id) if interaction.guild else None
        if channel is None:
            await interaction.response.send_message("❌ Não achei esse canal selecionado.", ephemeral=True)
            return
        perms = channel.permissions_for(interaction.guild.me) if interaction.guild and interaction.guild.me else None
        if perms and (not perms.send_messages or not perms.embed_links):
            await interaction.response.send_message("❌ Não tenho permissão pra mandar mensagem/Embed nesse canal.", ephemeral=True)
            return
        final = build_embed(self.data)
        try:
            await channel.send(embed=final)
        except discord.HTTPException as exc:
            await interaction.response.send_message(f"❌ Deu ruim pra mandar a Embed nesse canal: `{exc}`", ephemeral=True)
            return
        await interaction.response.send_message(f"📤 Embed enviada em {channel.mention}.", ephemeral=True)
        self.stop()
        if self.message:
            await self.message.edit(content="✅ **Embed enviada!** Fechando esse painel aqui 😎", view=None)

    async def clear_button(self, interaction):
        self.data = empty_data()
        self.selected_field = None
        await interaction.response.defer()
        await self.refresh()

    async def cancel_button(self, interaction):
        self.stop()
        await interaction.response.edit_message(content="❌ **Construtor cancelado.**", embed=None, view=None)

    async def on_timeout(self):
        self.stop()
        if self.message:
            try:
                await self.message.edit(content="⌛ **Construtor expirado por inatividade.**", view=None)
            except discord.HTTPException:
                pass


class AuthorModal(discord.ui.Modal):
    def __init__(self, builder):
        super().__init__(title="👤 Autor")
        self.builder = builder
        self.name = discord.ui.TextInput(label="Nome do autor", default=builder.data["author"][:256], max_length=256)
        self.url = discord.ui.TextInput(label="URL do autor (opcional)", default=builder.data["author_url"][:500], required=False, max_length=500)
        self.icon = discord.ui.TextInput(label="URL do ícone (opcional)", default=builder.data["author_icon"][:500], required=False, max_length=500)
        self.add_item(self.name); self.add_item(self.url); self.add_item(self.icon)

    async def on_submit(self, interaction):
        values = [str(self.url.value).strip(), str(self.icon.value).strip()]
        if any(v and not safe_url(v) for v in values):
            await interaction.response.send_message("❌ As URLs tão erradas kkkkk. Elas precisam começar com `http://` ou `https://`.", ephemeral=True)
            return
        self.builder.data["author"] = str(self.name.value).strip()
        self.builder.data["author_url"] = values[0]
        self.builder.data["author_icon"] = values[1]
        await interaction.response.defer(); await self.builder.refresh()


class FooterModal(discord.ui.Modal):
    def __init__(self, builder):
        super().__init__(title="📌 Rodapé")
        self.builder = builder
        self.text = discord.ui.TextInput(label="Texto do rodapé", default=builder.data["footer"][:2048], max_length=2048)
        self.icon = discord.ui.TextInput(label="URL do ícone (opcional)", default=builder.data["footer_icon"][:500], required=False, max_length=500)
        self.add_item(self.text); self.add_item(self.icon)

    async def on_submit(self, interaction):
        icon = str(self.icon.value).strip()
        if icon and not safe_url(icon):
            await interaction.response.send_message("❌ Essa URL tá errada kkkkk. Ela precisa começar com `http://` ou `https://`.", ephemeral=True)
            return
        self.builder.data["footer"] = str(self.text.value).strip()
        self.builder.data["footer_icon"] = icon
        await interaction.response.defer(); await self.builder.refresh()


class EmbedBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _permission(self, ctx_or_interaction):
        user = getattr(ctx_or_interaction, "user", None) or getattr(ctx_or_interaction, "author", None)
        return isinstance(user, discord.Member) and user.guild_permissions.manage_messages

    async def open_panel(self, target, user):
        panel = EmbedPanel(user.id, getattr(target, "channel_id", None), self.bot)
        panel.message = await target.send(content=panel.panel_content(), embed=panel.panel_embed(), view=panel)
        return panel

    @commands.command(name="embed", aliases=["emb", "criarembed"])
    @commands.guild_only()
    async def embed_prefix(self, ctx, *, argumentos: str = ""):
        """Abre o construtor visual de Embeds."""
        if not await self._permission(ctx):
            await ctx.send("❌ Você precisa de **Gerenciar Mensagens** pra brincar com esse construtor.", delete_after=8)
            return
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
        await ctx.author.send(
            "🔒 **Construtor de Embed privado**\n"
            "Para usar o painel com seleção de canal, abra `/embed` dentro do servidor. "
            "Comando com K não tem resposta efêmera no Discord, então essa mensagem fica normal."
        )

    @app_commands.command(name="embed", description="Abre o construtor de Embeds pra montar sua mensagem")
    @app_commands.default_permissions(manage_messages=True)
    async def embed_slash(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Usa esse comando dentro de um servidor, chefia.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ Você precisa de **Gerenciar Mensagens** pra brincar com esse construtor.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        panel = EmbedPanel(interaction.user.id, interaction.channel_id, self.bot, private=True)
        panel.message = await interaction.followup.send(content=panel.panel_content(), embed=panel.panel_embed(), view=panel, ephemeral=True, wait=True)


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
