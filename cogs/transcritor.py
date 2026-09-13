from cogs.embed_style import KibotEmbed
import asyncio
import io
import os
import tempfile
from datetime import timezone

import discord
from discord.ext import commands
from discord import app_commands


class Transcritor(commands.Cog):
    """Grava mensagens de um canal a partir da ativação e gera uma transcrição .txt."""

    def __init__(self, bot):
        self.bot = bot
        # guild_id -> channel_id -> session
        self.sessions = {}
        self._lock = asyncio.Lock()

    def _guild_sessions(self, guild_id):
        return self.sessions.setdefault(guild_id, {})

    async def _start(self, guild, channel, actor):
        async with self._lock:
            gs = self._guild_sessions(guild.id)
            if channel.id in gs:
                return False, "⚠️ O **Transcritor já está ativo** nesse canal."
            gs[channel.id] = {
                "channel_id": channel.id,
                "started_at": discord.utils.utcnow(),
                "started_by": actor.id,
                "messages": [],
            }
        return True, f"🎙️ **Transcritor ativado** em {channel.mention}.\nA partir de agora, novas mensagens serão registradas."

    async def _stop(self, guild, channel):
        async with self._lock:
            gs = self.sessions.get(guild.id, {})
            session = gs.pop(channel.id, None)
        if not session:
            return None, "⚠️ O **Transcritor não está ativo** nesse canal."
        if not gs:
            self.sessions.pop(guild.id, None)

        lines = []
        started = session["started_at"].astimezone(timezone.utc)
        lines.append("KIBOT — TRANSCRIÇÃO DE CANAL")
        lines.append("=" * 72)
        lines.append(f"Servidor: {guild.name} ({guild.id})")
        lines.append(f"Canal: #{getattr(channel, 'name', channel.id)} ({channel.id})")
        lines.append(f"Início: {started.isoformat()}")
        lines.append(f"Fim: {discord.utils.utcnow().astimezone(timezone.utc).isoformat()}")
        lines.append(f"Mensagens registradas: {len(session['messages'])}")
        lines.append("=" * 72)
        lines.append("")

        for item in session["messages"]:
            lines.append(f"[{item['timestamp']}] {item['author']} ({item['author_id']})")
            lines.append(item["content"] or "[sem texto]")
            for att in item["attachments"]:
                lines.append(f"[Anexo] {att}")
            if item["stickers"]:
                lines.append(f"[Figurinhas] {', '.join(item['stickers'])}")
            lines.append("")

        data = "\n".join(lines).encode("utf-8")
        filename = f"transcricao-{guild.id}-{channel.id}-{discord.utils.utcnow().strftime('%Y%m%d-%H%M%S')}.txt"
        return (filename, data, len(session["messages"])), None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return
        # O comando de controle que encerra a sessão não entra na própria transcrição.
        if message.content.lower().startswith(("k!transcritor", "k!transcricao", "k!transcrição")):
            return
        gs = self.sessions.get(message.guild.id)
        if not gs:
            return
        session = gs.get(message.channel.id)
        if not session:
            return
        # O transcritor registra inclusive mensagens do próprio Kibot, caso ocorram depois da ativação.
        item = {
            "timestamp": message.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "author": str(message.author),
            "author_id": message.author.id,
            "content": message.content,
            "attachments": [a.url for a in message.attachments],
            "stickers": [s.name for s in message.stickers],
        }
        async with self._lock:
            # A sessão pode ter sido encerrada enquanto aguardávamos o lock.
            current = self.sessions.get(message.guild.id, {}).get(message.channel.id)
            if current is session:
                session["messages"].append(item)

    @app_commands.command(name="transcritor", description="Inicia, para ou consulta a transcrição de um canal")
    @app_commands.describe(acao="iniciar, parar ou status", canal="Canal que será transcrito")
    @app_commands.choices(acao=[
        app_commands.Choice(name="Iniciar", value="iniciar"),
        app_commands.Choice(name="Parar e gerar TXT", value="parar"),
        app_commands.Choice(name="Status", value="status"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def transcritor_slash(self, interaction: discord.Interaction, acao: str, canal: discord.TextChannel):
        if acao == "iniciar":
            ok, msg = await self._start(interaction.guild, canal, interaction.user)
            e = KibotEmbed(title="🎙️ Transcritor", description=msg, color=discord.Color.green() if ok else discord.Color.orange())
            await interaction.response.send_message(embed=e, ephemeral=True)
        elif acao == "status":
            active = canal.id in self.sessions.get(interaction.guild.id, {})
            e = KibotEmbed(title="🎙️ Transcritor — Status", color=discord.Color.green() if active else discord.Color.dark_grey())
            e.description = f"Canal: {canal.mention}\nEstado: **{'ATIVO' if active else 'INATIVO'}**"
            if active:
                s = self.sessions[interaction.guild.id][canal.id]
                e.add_field(name="Mensagens", value=f"`{len(s['messages'])}`", inline=True)
                e.add_field(name="Iniciado em", value=discord.utils.format_dt(s["started_at"], "F"), inline=True)
            await interaction.response.send_message(embed=e, ephemeral=True)
        else:
            result, error = await self._stop(interaction.guild, canal)
            if error:
                await interaction.response.send_message(embed=KibotEmbed(title="🎙️ Transcritor", description=error, color=discord.Color.orange()), ephemeral=True)
                return
            filename, data, count = result
            file = discord.File(io.BytesIO(data), filename=filename)
            e = KibotEmbed(title="📝 Transcrição concluída", description=f"Transcrição de {canal.mention} finalizada com **{count} mensagens**.", color=discord.Color.gold())
            await interaction.response.send_message(embed=e, file=file)

    @commands.group(name="transcritor", aliases=["transcricao", "transcrição"], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def transcritor_prefix(self, ctx: commands.Context, acao: str = None, canal: discord.TextChannel = None):
        if not acao:
            await ctx.send("🎙️ Use `K!transcritor iniciar #canal`, `K!transcritor parar #canal` ou `K!transcritor status #canal`.")
            return
        acao = acao.lower()
        if canal is None:
            canal = ctx.channel
        if acao in ("iniciar", "start", "on", "ativar"):
            ok, msg = await self._start(ctx.guild, canal, ctx.author)
            await ctx.send(embed=KibotEmbed(title="🎙️ Transcritor", description=msg, color=discord.Color.green() if ok else discord.Color.orange()))
        elif acao in ("status", "estado"):
            active = canal.id in self.sessions.get(ctx.guild.id, {})
            desc = f"Canal: {canal.mention}\nEstado: **{'ATIVO' if active else 'INATIVO'}**"
            if active:
                desc += f"\nMensagens: **{len(self.sessions[ctx.guild.id][canal.id]['messages'])}**"
            await ctx.send(embed=KibotEmbed(title="🎙️ Transcritor — Status", description=desc, color=discord.Color.green() if active else discord.Color.dark_grey()))
        elif acao in ("parar", "stop", "off", "desativar"):
            result, error = await self._stop(ctx.guild, canal)
            if error:
                await ctx.send(embed=KibotEmbed(title="🎙️ Transcritor", description=error, color=discord.Color.orange()))
                return
            filename, data, count = result
            await ctx.send(embed=KibotEmbed(title="📝 Transcrição concluída", description=f"Transcrição de {canal.mention} finalizada com **{count} mensagens**.", color=discord.Color.gold()), file=discord.File(io.BytesIO(data), filename=filename))
        else:
            await ctx.send("❌ Ação inválida. Use `iniciar`, `parar` ou `status`.")

    @transcritor_prefix.error
    async def transcritor_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Você precisa da permissão **Gerenciar Servidor** para usar o Transcritor.", delete_after=8)


async def setup(bot):
    await bot.add_cog(Transcritor(bot))
