import re
import time
from datetime import timedelta
from collections import defaultdict, deque
import asyncio

import discord
from discord.ext import commands

from cogs.utils import log_action
from database import db


# AutoMod do Kibot: já vem ligado. O único bypass de usuário é o cargo "automod".
# Ajuste esta lista se quiser deixar a moderação mais ou menos pesada.
BLOCKED_TERMS = {
    "filho da puta",
    "filha da puta",
    "vai tomar no cu",
    "vai se foder",
}

INVITE_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/[\w-]+", re.I)
URL_RE = re.compile(r"https?://\S+", re.I)

AUTOMOD_MESSAGES = {
    "flood/spam": "PARA DE SPAMMAR CARALHOOOOOOOOOOOO 😭",
    "mensagem repetida/spam": "PARA DE SPAMMAR CARALHOOOOOOOOOOOO 😭",
    "palavra/frase bloqueada": "OPA OPA! OLHA A BOCA PARCEIRO! JÁ TOMA PRA FICAR ESPERTO!",
    "caps lock abusivo": "CALMA AÍ, GRITÃO! NÃO PRECISA ESCREVER COMO SE O SERVIDOR ESTIVESSE PEGANDO FOGO! 😭",
    "link de convite do Discord": "OPA! CONVITE DE OUTRO SERVIDOR AQUI NÃO, CHEFE! 🛑",
    "menções em massa": "EI EI EI! PARA DE MARCAR O SERVIDOR INTEIRO, MALUCO! 📢",
}


class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_cache = {}
        self.message_order = deque(maxlen=2000)
        self.user_messages = defaultdict(deque)
        self.recent_content = defaultdict(deque)
        self.violations = defaultdict(int)
        self.automod_deleted = set()
        self.auto_ban_in_progress = set()
        self.event_count = 0
        self.last_event = None
        self.last_rule = None

    @staticmethod
    def has_automod_role(member: discord.Member) -> bool:
        return any(role.name.casefold() == "automod" for role in member.roles)

    @staticmethod
    def is_auto_ban_bypass(member: discord.Member) -> bool:
        # Protege a equipe contra um canal de quarentena mal configurado.
        perms = member.guild_permissions
        return perms.administrator or perms.manage_guild

    async def purge_user_history(self, guild: discord.Guild, user_id: int) -> int:
        """Apaga o histórico acessível do usuário em todos os canais de texto.

        Não usa bulk delete porque mensagens antigas de 14 dias ou mais não podem
        ser removidas pela API em lote. A exclusão individual funciona para todo o
        histórico que o bot consegue ler, respeitando as permissões de cada canal.
        """
        channels = list(guild.text_channels)
        # Threads ativas também fazem parte do servidor e podem conter spam.
        for thread in getattr(guild, "threads", []):
            if thread not in channels:
                channels.append(thread)

        deleted = 0
        for channel in channels:
            perms = channel.permissions_for(guild.me) if guild.me else None
            if perms and (not perms.read_message_history or not perms.manage_messages):
                continue
            try:
                async for msg in channel.history(limit=None):
                    if msg.author.id != user_id:
                        continue
                    try:
                        await msg.delete(reason="Kibot Anti-BetSpam: limpeza de histórico após ban automático")
                        deleted += 1
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
            except (discord.Forbidden, discord.HTTPException):
                continue
            # Cede o loop entre canais/históricos para não travar outros eventos do bot.
            await asyncio.sleep(0)
        return deleted

    async def auto_ban_bets(self, message: discord.Message) -> bool:
        """Quarentena: qualquer mensagem/anexo no canal configurado gera ban + limpeza."""
        if not message.guild or message.author.bot:
            return False
        cfg = await db.get_guild_config(message.guild.id)
        channel_id = cfg["auto_ban_bets_channel_id"]
        if not cfg["auto_ban_bets_enabled"] or not channel_id or message.channel.id != channel_id:
            return False
        if self.is_auto_ban_bypass(message.author):
            return False

        key = (message.guild.id, message.author.id)
        if key in self.auto_ban_in_progress:
            return True
        self.auto_ban_in_progress.add(key)

        reason = "Anti-BetSpam: atividade detectada no canal de quarentena"
        banned = False
        try:
            try:
                await message.author.ban(reason=f"Kibot — {reason}", delete_message_days=0)
                banned = True
            except (discord.Forbidden, discord.HTTPException):
                # Mesmo sem conseguir banir, remove a mensagem que disparou a regra.
                try:
                    await message.delete(reason="Kibot Anti-BetSpam")
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
                await log_action(
                    message.guild,
                    "🚨 Anti-BetSpam — FALHA AO BANIR",
                    f"**Usuário:** {message.author.mention} (`{message.author.id}`)\n**Canal:** {message.channel.mention}\n**Motivo:** Kibot não conseguiu banir. Verifique a permissão **Banir membros** e a hierarquia do cargo.",
                    discord.Color.orange(),
                )
                return True

            deleted = await self.purge_user_history(message.guild, message.author.id)
            await log_action(
                message.guild,
                "🚨 Kibot Anti-BetSpam — BAN AUTOMÁTICO",
                f"**Usuário:** `{message.author}` (`{message.author.id}`)\n"
                f"**Canal de gatilho:** {message.channel.mention}\n"
                f"**Ação:** usuário banido automaticamente + histórico acessível limpo\n"
                f"**Mensagens apagadas:** `{deleted}`\n"
                f"**Gatilho:** mensagem/arquivo enviado no canal protegido.",
                discord.Color.dark_red(),
            )
            return banned
        finally:
            self.auto_ban_in_progress.discard(key)

    def remember(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if message.id not in self.message_cache:
            self.message_order.append(message.id)
        self.message_cache[message.id] = {
            "content": message.content or "*(sem texto)*",
            "author_id": message.author.id,
            "author_name": str(message.author),
            "channel_id": message.channel.id,
            "guild_id": message.guild.id,
            "attachments": [a.url for a in message.attachments],
            "created_at": message.created_at,
        }
        # Mantém a memória limitada.
        while len(self.message_cache) > self.message_order.maxlen:
            old_id = self.message_order.popleft()
            self.message_cache.pop(old_id, None)

    async def automod(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if self.has_automod_role(message.author):
            return

        # Canal de quarentena Anti-BetSpam: qualquer fala ou arquivo dispara ban + limpeza.
        if await self.auto_ban_bets(message):
            return

        content = message.content or ""
        lowered = content.casefold()
        now = time.monotonic()
        key = (message.guild.id, message.author.id)

        # 1) Convite externo do Discord.
        if INVITE_RE.search(content):
            await self.take_action(message, "link de convite do Discord")
            return

        # 2) Menções em massa.
        if len(message.mentions) >= 6 or message.mention_everyone:
            await self.take_action(message, "menções em massa")
            return

        # 3) Flood/repetição podem ser liberados por canal (ex.: Mudae).
        spam_exempt = await db.is_automod_spam_exempt(message.guild.id, message.channel.id)
        if spam_exempt:
            return

        # 4) Flood: muitas mensagens em poucos segundos.
        history = self.user_messages[key]
        history.append(now)
        while history and now - history[0] > 6:
            history.popleft()
        if len(history) >= 6:
            await self.take_action(message, "flood/spam")
            history.clear()
            return

        # 5) Mensagem repetida várias vezes.
        repeated = self.recent_content[key]
        repeated.append((now, lowered.strip()))
        while repeated and now - repeated[0][0] > 12:
            repeated.popleft()
        if lowered.strip() and sum(1 for _, text in repeated if text == lowered.strip()) >= 4:
            await self.take_action(message, "mensagem repetida/spam")
            repeated.clear()
            return

        # 6) Caps lock abusivo (sem punir mensagens curtas).
        letters = [c for c in content if c.isalpha()]
        if len(letters) >= 18:
            upper_ratio = sum(c.isupper() for c in letters) / len(letters)
            if upper_ratio >= 0.85:
                await self.take_action(message, "caps lock abusivo")
                return

        # 7) Termos bloqueados.
        if any(term in lowered for term in BLOCKED_TERMS):
            await self.take_action(message, "palavra/frase bloqueada")
            return

    async def take_action(self, message: discord.Message, reason: str):
        self.last_rule = reason
        key = (message.guild.id, message.author.id)
        self.violations[key] += 1
        count = self.violations[key]

        try:
            self.automod_deleted.add(message.id)
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            self.automod_deleted.discard(message.id)

        # Primeira e segunda ocorrência: apaga. A partir da terceira, tenta timeout.
        timeout_text = ""
        if count >= 3:
            try:
                minutes = min(60, 5 * (count - 2))
                await message.author.timeout(
                    discord.utils.utcnow() + timedelta(minutes=minutes),
                    reason=f"Kibot AutoMod: {reason}",
                )
                timeout_text = f"\n**Punição extra:** timeout de {minutes} min."
            except (discord.Forbidden, discord.HTTPException):
                timeout_text = "\n**Punição extra:** não consegui aplicar timeout (permissões/cargo)."

            # Depois de aplicar/tentar a punição, começa uma nova sequência.
            # Assim, o próximo spam não herda a ocorrência anterior e não gera
            # uma sequência de punições em cadeia.
            self.violations[key] = 0

        await log_action(
            message.guild,
            "🛡️ Kibot AutoMod — mensagem bloqueada",
            f"**Usuário:** {message.author.mention} (`{message.author.id}`)\n"
            f"**Canal:** {message.channel.mention}\n"
            f"**Regra:** {reason}\n"
            f"**Ocorrência:** #{count}\n"
            f"**Mensagem:** {discord.utils.escape_markdown(message.content[:1500]) or '*(sem texto)*'}"
            f"{timeout_text}",
            discord.Color.red(),
        )

        try:
            reaction = AUTOMOD_MESSAGES.get(
                reason,
                "🛡️ EI! ESSA MENSAGEM FOI BARRADA PELO AUTOMOD, PARCEIRO!"
            )
            await message.channel.send(
                f"{message.author.mention} {reaction}",
                delete_after=6,
            )
        except discord.HTTPException:
            pass

    async def handle_message(self, message):
        """Entrada do AutoMod. Fica dentro da Cog para não depender do on_message global."""
        if not message.guild or message.author.bot:
            return
        self.event_count += 1
        self.last_event = {
            "message_id": message.id,
            "channel_id": message.channel.id,
            "author_id": message.author.id,
            "content_len": len(message.content or ""),
            "content_preview": (message.content or "")[:80],
        }
        try:
            self.remember(message)
            await self.automod(message)
        except Exception:
            # O AutoMod nunca pode derrubar o processamento normal das mensagens.
            import logging
            logging.getLogger("kibot.security").exception(
                "Erro processando mensagem no AutoMod: guild=%s channel=%s author=%s message=%s",
                getattr(message.guild, "id", None), getattr(message.channel, "id", None),
                getattr(message.author, "id", None), getattr(message, "id", None),
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        # Listener próprio da Cog: mais confiável que depender de bot.get_cog() no evento global.
        await self.handle_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild or after.author.bot:
            return
        self.remember(after)
        old = before.content or self.message_cache.get(before.id, {}).get("content", "*(sem texto)*")
        new = after.content or "*(sem texto)*"
        if old == new and not before.attachments and not after.attachments:
            return

        old = old[:1800]
        new = new[:1800]
        await log_action(
            after.guild,
            "✏️ Mensagem editada",
            f"**Autor:** {after.author.mention} (`{after.author.id}`)\n"
            f"**Canal:** {after.channel.mention}\n"
            f"**Antes:**\n```\n{old}\n```\n"
            f"**Depois:**\n```\n{new}\n```\n"
            f"**Mensagem:** [abrir mensagem]({after.jump_url})",
            discord.Color.orange(),
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild or message.author.bot:
            return
        # A exclusão feita pelo próprio AutoMod já possui um log específico.
        if message.id in self.automod_deleted:
            self.automod_deleted.discard(message.id)
            self.message_cache.pop(message.id, None)
            return
        cached = self.message_cache.pop(message.id, {})
        content = message.content or cached.get("content", "*(conteúdo não disponível no cache)*")
        author_id = message.author.id or cached.get("author_id")
        channel = message.channel or message.guild.get_channel(cached.get("channel_id"))
        channel_text = channel.mention if channel else f"`{cached.get('channel_id', 'desconhecido')}`"
        await log_action(
            message.guild,
            "🗑️ Mensagem excluída",
            f"**Autor:** <@{author_id}> (`{author_id}`)\n"
            f"**Canal:** {channel_text}\n"
            f"**Conteúdo:**\n```\n{content[:2500]}\n```",
            discord.Color.red(),
        )

async def setup(bot):
    await bot.add_cog(Security(bot))
