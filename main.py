"""
Kibot — gerenciamento, Crowings, XP e diversão.
Prefixo textual: K! (ex.: K! saldo, K! daily, K! ajuda).
"""
import asyncio, logging, re, difflib, os
import discord
from discord.ext import commands
import config
from database.db import init_db
from cogs.help_center import HelpView, make_help_embed

BUILD_ID = "2026-09-13-KIBOT-WEB-DASHBOARD-v51"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger=logging.getLogger("kibot")
INTENTS=discord.Intents.default()
INTENTS.members=True
INTENTS.message_content=True
INTENTS.presences=True
INTENTS.voice_states=True

EXTENSIONS=["cogs.code_guard", "cogs.economy", "cogs.slash_aliases","cogs.moderation","cogs.management","cogs.fun", "cogs.dice_engine","cogs.levels","cogs.arcade","cogs.crime","cogs.bicos","cogs.afk","cogs.embed_builder","cogs.tutorial","cogs.badges","cogs.tags", "cogs.ai_chat", "cogs.realtime_data","cogs.forms","cogs.security","cogs.admin_economy", "cogs.tempvoice", "cogs.transcritor", "cogs.tickets", "cogs.server_builder", "cogs.server_assets"]

def prefix_callable(bot, message):
    # "K!" funciona tanto como K!saldo quanto K! saldo.
    return commands.when_mentioned_or(config.PREFIX)(bot,message)

KIBOT_ACTIVITIES = [
    "🪶 Protegendo o bando",
    "💰 Contando Crowings",
    "🎲 Jogando RPG",
    "🛡️ Mantendo o servidor seguro",
    "👀 Observando vocês...",
    "🐦‍⬛ Sobrevoando o servidor",
    "🏆 Contando os vencedores",
    "📋 Organizando a bagunça",
    "☕ Tomando café no ninho",
    "😈 Planejando alguma coisa...",
]

class Kibot(commands.Bot):
    def __init__(self):
        self.presence_cache = {}
        super().__init__(command_prefix=prefix_callable,intents=INTENTS,help_command=None,
                         max_messages=200,member_cache_flags=discord.MemberCacheFlags.from_intents(INTENTS),
                         chunk_guilds_at_startup=True,case_insensitive=True)
    async def rotate_status(self):
        await self.wait_until_ready()
        index = 0
        while not self.is_closed():
            text = KIBOT_ACTIVITIES[index % len(KIBOT_ACTIVITIES)]
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Game(name=text)
            )
            index += 1
            await asyncio.sleep(30)

    async def setup_hook(self):
        await init_db()
        failed_extensions = []
        for extension in EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Extensão carregada: %s", extension)
            except Exception as exc:
                failed_extensions.append((extension, exc))
                logger.exception("Falha ao carregar extensão: %s", extension)
        self.failed_extensions = failed_extensions
        if failed_extensions:
            logger.error("%d extensão(ões) NÃO foram carregadas: %s", len(failed_extensions), ", ".join(name for name, _ in failed_extensions))
        # Sincroniza os comandos globalmente e também nos servidores configurados.
        # A cópia por guilda aparece imediatamente; o registro global funciona
        # mesmo quando GUILD_IDS não foi configurado no ambiente.
        try:
            await self.tree.sync()
            logger.info("Comandos slash globais sincronizados: %d", len(self.tree.get_commands()))
        except Exception:
            logger.exception("Falha ao sincronizar comandos slash globais")

        for gid in config.GUILD_IDS:
            try:
                guild = discord.Object(id=gid)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info("Comandos slash sincronizados na guild %s: %d", gid, len(synced))
            except Exception:
                logger.exception("Falha ao sincronizar comandos slash na guild %s", gid)
    async def on_presence_update(self, before, after):
        self.presence_cache[(after.guild.id, after.id)] = after.status

    async def on_ready(self):
        logger.info("Kibot conectado como %s (ID: %s)", self.user, self.user.id)
        logger.info("Prefixo: %r | Comandos de prefixo: %d | Comandos slash: %d", config.PREFIX, len(list(self.walk_commands())), len(self.tree.get_commands()))
        failed = getattr(self, "failed_extensions", [])
        if failed:
            logger.error("Extensões com falha no startup: %s", ", ".join(name for name, _ in failed))
            guard = self.get_cog("CodeGuard")
            if guard:
                for extension, exc in failed:
                    asyncio.create_task(guard.diagnose_exception(exc, guild=None, command_name=f"startup:{extension}"))
        logger.info("Intents: message_content=%s members=%s presences=%s voice_states=%s | Security=%s", self.intents.message_content, self.intents.members, self.intents.presences, self.intents.voice_states, bool(self.get_cog("Security")))
        forms = self.get_cog("Forms")
        if forms:
            await forms.initialize_views()
        for guild in self.guilds:
            me = guild.me
            if me:
                logger.info("Guild %s (%s): manage_messages=%s moderate_members=%s top_role=%s", guild.name, guild.id, me.guild_permissions.manage_messages, me.guild_permissions.moderate_members, me.top_role.position)
        if not hasattr(self, "_status_rotation_task") or self._status_rotation_task.done():
            self._status_rotation_task = asyncio.create_task(self.rotate_status())
    async def is_owner(self,user):
        return user.id in config.OWNER_IDS or await super().is_owner(user)

bot=Kibot()

@bot.command(name="ping")
async def ping(ctx):
    ms=round(bot.latency*1000)
    await ctx.send(f"🏓 Pong! Tô vivo e respondendo em **{ms}ms** kkkkk.")

@bot.command(name="kibotversion", aliases=["versao", "build"])
async def kibotversion(ctx):
    await ctx.send(f"🛠️ Kibot Build: `{BUILD_ID}`\nPresence Intent: `{bot.intents.presences}`\nEventos de presença recebidos: `{len(bot.presence_cache)}`")

@bot.command(name="presenciatest", aliases=["testepresenca"])
async def presenciatest(ctx, member: discord.Member = None):
    m = member or ctx.author
    cached = bot.presence_cache.get((ctx.guild.id, m.id), discord.Status.offline)
    await ctx.send(f"🔎 **Diagnóstico de presença — {m.display_name}**\nMember.status: `{m.status}`\nDesktop: `{getattr(m, 'desktop_status', None)}`\nMobile: `{getattr(m, 'mobile_status', None)}`\nWeb: `{getattr(m, 'web_status', None)}`\nCache próprio: `{cached}`\nPresence Intent: `{bot.intents.presences}`")

@bot.tree.command(name="ping", description="Testa se o Kibot tá vivo e respondendo")
async def ping_slash(interaction):
    ms=round(bot.latency*1000)
    await interaction.response.send_message(f"🏓 Pong! Tô vivo e respondendo em **{ms}ms** kkkkk.")

@bot.tree.error
async def on_app_command_error(interaction, error):
    """Garante uma resposta visível quando um slash command falha."""
    original = getattr(error, "original", error)
    guard = bot.get_cog("CodeGuard")
    if guard and not isinstance(original, (commands.MissingPermissions, commands.BotMissingPermissions)):
        asyncio.create_task(guard.diagnose_exception(original, guild=interaction.guild, command_name=getattr(getattr(interaction, "command", None), "qualified_name", "slash")))
    if isinstance(original, (commands.MissingPermissions, commands.BotMissingPermissions)):
        text = "❌ Você não tem as permissões necessárias para usar esse comando." if isinstance(original, commands.MissingPermissions) else "❌ O Kibot não tem as permissões necessárias para executar esse comando."
    else:
        logger.error("Erro em slash command %s: %r", getattr(getattr(interaction, "command", None), "qualified_name", "desconhecido"), original, exc_info=(type(original), original, original.__traceback__))
        text = "❌ Deu ruim aqui enquanto eu rodava esse comando. Tenta de novo daqui a pouco."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException:
        logger.exception("Não consegui responder ao erro do slash command")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if bot.user and bot.user in message.mentions and "pru pru" in message.content.lower():
        await message.channel.send("Pru Pru pra você também meu querido kkkkkk")

    # O AutoMod agora é um listener próprio da Cog Security.
    # Aqui só processamos os comandos, evitando qualquer risco de dupla execução do AutoMod.
    await bot.process_commands(message)

@bot.command(name="ajuda",aliases=["help","h","comandos"])
async def ajuda(ctx):
    await ctx.send(embed=make_help_embed("inicio", bot), view=HelpView(ctx.author.id, bot))

@bot.command(name="sync", aliases=["sincronizar"])
@commands.is_owner()
async def sync(ctx):
    synced=await bot.tree.sync(); await ctx.send(f"✅ Fechou! Sincronizei **{len(synced)}** comando(s).")

@bot.command(name="reload", aliases=["recarregar"])
@commands.is_owner()
async def reload(ctx,extensao:str):
    try:
        await bot.reload_extension(extensao); await ctx.send(f"🔄 Fechou! A extensão `{extensao}` foi recarregada.")
    except Exception as e: await ctx.send(f"❌ Deu ruim: {e}")

def _command_usage(command):
    """Monta uma dica de uso para comandos de prefixo."""
    signature = getattr(command, "signature", "") or ""
    return f"{config.PREFIX}{command.qualified_name}{(' ' + signature) if signature else ''}"

def _command_aliases(command):
    return [command.name, *getattr(command, "aliases", [])]

def _find_similar_command(typed_name, limit=3):
    """Procura nomes/aliases próximos do que o usuário digitou."""
    typed_name = typed_name.lower().strip()
    candidates = {}
    for command in bot.walk_commands():
        if command.hidden:
            continue
        for name in _command_aliases(command):
            candidates[name.lower()] = command
    matches = difflib.get_close_matches(typed_name, candidates.keys(), n=limit, cutoff=0.55)
    result = []
    seen = set()
    for match in matches:
        command = candidates[match]
        if command.qualified_name not in seen:
            result.append((match, command))
            seen.add(command.qualified_name)
    return result

def _typed_command_name(message_content):
    """Extrai o nome digitado depois do prefixo K, aceitando Kkick e K kick."""
    content = (message_content or "").strip()
    if not content:
        return ""
    if content.lower().startswith(config.PREFIX.lower()):
        rest = content[len(config.PREFIX):].lstrip()
        return rest.split(maxsplit=1)[0].lower() if rest else ""
    return ""

@bot.event
async def on_command_error(ctx,error):
    if isinstance(error,commands.CommandNotFound):
        typed = _typed_command_name(ctx.message.content)
        if typed:
            import random
            unknown_replies = [
                "Nãokkkkkk", "Só se mamar", "Kys",
                "Irmão, esse comando foi inventado agora? KKKKK",
                "Tá tirando comando da cartola agora?",
                "Isso aí nem existe, meu mano KKKKK",
                "KKKKKKKK de onde você tirou isso?",
                "Nem o Kibot sabe que porra é essa KKKKK",
                "Meu banco de dados olhou isso e disse: não.",
                "Você tá digitando comandos em idioma secreto?",
                "Essa função não foi desbloqueada ainda KKKKK",
                "Erro 404: comando foi de arrasta.",
                "Amigo... quem te ensinou esse comando? 😭",
                "O comando pediu demissão antes de existir.",
                "Você desbloqueou o comando secreto: absolutamente nada.",
                "Kkkkk não força a amizade, esse comando não existe.",
                "Aí é complicado, chefia. Esse comando é fake.",
                "Fonte: vozes da sua cabeça. Esse comando não existe.",
                "Você acabou de tentar um comando DLC que eu não tenho KKKKK.",
                "Não foi dessa vez, guerreiro.",
            ]
            # Uma única mensagem: não há resposta padrão, sugestões ou segundo embed.
            await ctx.send(f"{random.choice(unknown_replies)}\n👉 Manda `{config.PREFIX}ajuda`.")
        return

    if isinstance(error,commands.MissingPermissions):
        await ctx.send("❌ Aí não, você não tem permissão pra usar isso kkkkk.")
    elif isinstance(error,commands.MissingRequiredArgument):
        command = ctx.command
        usage = _command_usage(command) if command else f"{config.PREFIX} ajuda"
        missing = getattr(error, "param", None)
        missing_name = getattr(missing, "name", "argumento")
        await ctx.send(
            f"❌ Faltou `{missing_name}` aí kkkkk.\n"
            f"👉 Usa assim: `{usage}`"
        )
    elif isinstance(error,commands.BadArgument):
        command = ctx.command
        usage = _command_usage(command) if command else f"{config.PREFIX} ajuda"
        await ctx.send(
            f"❌ Não consegui entender esse argumento kkkkk.\n"
            f"👉 O formato certo é: `{usage}`"
        )
    else:
        logger.exception("Erro em comando de prefixo",exc_info=error)
        await ctx.send("❌ Deu ruim aqui enquanto eu rodava o comando. Tenta de novo daqui a pouco.")

async def main():
    if not config.TOKEN: raise RuntimeError("DISCORD_TOKEN não encontrado. Configure o .env.")
    web_enabled = os.getenv("WEB_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
    if not web_enabled:
        async with bot:
            await bot.start(config.TOKEN)
        return

    # Site e bot podem rodar no mesmo processo/host, compartilhando o mesmo SQLite.
    import uvicorn
    from web_api import app as web_app
    web_port = int(os.getenv("PORT", os.getenv("WEB_PORT", "8080")))
    web_host = os.getenv("WEB_HOST", "0.0.0.0")
    server = uvicorn.Server(uvicorn.Config(web_app, host=web_host, port=web_port, log_level="info"))
    async with bot:
        await asyncio.gather(bot.start(config.TOKEN), server.serve())
if __name__=="__main__": asyncio.run(main())
