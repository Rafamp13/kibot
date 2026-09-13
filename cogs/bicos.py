"""Sistema de Bicos do Kibot. Tudo é uma mecânica fictícia de economia virtual."""
from cogs.embed_style import KibotEmbed
import random
import time
import datetime
import discord
from discord.ext import commands
from discord import app_commands
from database import db
import config
from cogs.utils import boosted_xp
from cogs.economy import format_money

# Os 10 bicos do dia são gerados de forma determinística por servidor/data.
BIKO_POOL = [
    ("📦 Entregar umas encomendas", 80, 180, 5),
    ("🧹 Dar aquela geral num depósito", 100, 220, 8),
    ("🍕 Fazer umas entregas de comida", 140, 300, 10),
    ("🐕 Passear com uma matilha", 180, 380, 15),
    ("🎪 Ajudar numa montagem de evento", 250, 520, 20),
    ("🎨 Fazer um freela de arte", 350, 750, 30),
    ("💻 Resolver um pepino de computador", 450, 950, 35),
    ("📸 Cobrir um evento", 600, 1250, 45),
    ("🚚 Fazer uma entrega grandona", 800, 1700, 55),
    ("🧾 Fechar um freela absurdo", 1000, 2400, 70),
]


def day_key():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def generate_bicos(guild_id: int):
    seed = f"{guild_id}:{day_key()}"
    rng = random.Random(seed)
    choices = list(BIKO_POOL)
    rng.shuffle(choices)
    result = []
    for i, (name, lo, hi, minutes) in enumerate(choices, 1):
        payout = rng.randint(lo, hi)
        # Quanto mais CRW, mais tempo. Mantém uma variação pequena sem ficar injusto.
        duration = max(5, minutes + rng.randint(-2, 5))
        result.append({"id": i, "name": name, "payout": payout, "duration": duration})
    return result


def fmt_time(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class Bicos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _send(self, ctx, content=None, embed=None, ephemeral=False):
        if isinstance(ctx, discord.Interaction):
            if ctx.response.is_done():
                return await ctx.followup.send(content=content, embed=embed, ephemeral=ephemeral)
            return await ctx.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        return await ctx.send(content=content, embed=embed)

    async def _finish_if_ready(self, user_id, guild_id):
        return await db.claim_bico_completion(user_id, guild_id)

    @commands.command(name="bico", aliases=["bicos"])
    async def p_bico(self, ctx, escolha: str = None, membro: discord.Member = None):
        if not escolha:
            return await self._list(ctx)
        if escolha.lower() in {"status", "andamento", "progresso"}:
            return await self._status(ctx, membro)
        try:
            numero = int(escolha)
        except ValueError:
            return await self._send(ctx, "❌ Manda o número do bico ou `K! bico status`, sem inventar moda kkkkk.")
        await self._accept(ctx, numero)

    @app_commands.command(name="bicos", description="Vê os 10 bicos de hoje e quanto cada um paga")
    async def bicos_slash(self, interaction):
        await self._list(interaction)

    @app_commands.command(name="bico", description="Escolhe um bico pelo número ou vê seu bico em andamento")
    @app_commands.describe(escolha="Número do bico ou: status")
    async def bico_slash(self, interaction, escolha: str):
        if escolha.lower() in {"status", "andamento", "progresso"}:
            return await self._status(interaction)
        try:
            numero = int(escolha)
        except ValueError:
            return await self._send(interaction, "❌ Manda um número de 1 a 10 ou `status` kkkkk.", ephemeral=True)
        await self._accept(interaction, numero)

    @app_commands.command(name="bico_status", description="Vê quanto falta para um bico terminar")
    @app_commands.describe(membro="Membro cujo bico você quer consultar (opcional; padrão: você)")
    async def bico_status_slash(self, interaction, membro: discord.Member = None):
        await self._status(interaction, membro)

    async def _list(self, ctx):
        user = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        row = await db.get_user(user.id, ctx.guild.id)
        done = await self._finish_if_ready(user.id, ctx.guild.id)
        if done:
            row = await db.get_user(user.id, ctx.guild.id)
            badges=self.bot.get_cog("Badges")
            if badges: await badges.record(user.id,ctx.guild.id,"bicos",1,user)
            new_level,old_level,_=await db.add_xp(user.id,ctx.guild.id,boosted_xp(user,config.XP_BICO))
            if new_level>old_level:
                levels=self.bot.get_cog("Levels")
                if levels: await levels.sync_member_level_roles(user)
            level_msg=f" ⭐ +**{boosted_xp(user,config.XP_BICO)} XP**" + (f" • 🎖️ Nível **{new_level}**!" if new_level>old_level else "")
            await self._send(ctx, f"🎉 Seu bico acabou enquanto você tava fora! Caiu **{format_money(done[1])}** na carteira. Bora pro próximo kkkkk.{level_msg}", ephemeral=isinstance(ctx, discord.Interaction))
        bicos = generate_bicos(ctx.guild.id)
        lines = []
        for b in bicos:
            lines.append(f"**{b['id']}.** {b['name']} — **{format_money(b['payout'])}** • ⏱️ {b['duration']}min")
        e = KibotEmbed(
            title="🧰 Bicos de hoje",
            description="Tem **10 bicos** na rua hoje. Escolhe **um** e manda `K! bico número`. Depois é só esperar o tempo passar.",
            color=discord.Color.dark_gold(),
        )
        e.add_field(name="📋 Cardápio", value="\n".join(lines), inline=False)
        if row["active_bico"]:
            e.add_field(name="🚧 Seu bico atual", value=f"**{row['active_bico']}** — vê o tempo com `K! bico status`.", inline=False)
        e.set_footer(text="Bico é bico: trabalha primeiro, CRW depois kkkkk.")
        await self._send(ctx, embed=e, ephemeral=isinstance(ctx, discord.Interaction))

    async def _accept(self, ctx, numero):
        user = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        if numero < 1 or numero > 10:
            return await self._send(ctx, "❌ Só tem bico de **1 a 10**, meu querido kkkkk.", ephemeral=isinstance(ctx, discord.Interaction))
        finished = await self._finish_if_ready(user.id, ctx.guild.id)
        row = await db.get_user(user.id, ctx.guild.id)
        if row["active_bico"]:
            remain = row["bico_ends_at"] - int(time.time())
            return await self._send(ctx, f"🚧 Você já tá fazendo **{row['active_bico']}**. Faltam **{fmt_time(remain)}**. Usa `K! bico status` pra acompanhar.", ephemeral=isinstance(ctx, discord.Interaction))
        elapsed = int(time.time()) - row["last_bico_accept"]
        if elapsed < 3600:
            return await self._send(ctx, f"⏳ Calma aí, trabalhador kkkkk. Seu próximo bico libera em **{fmt_time(3600 - elapsed)}**.", ephemeral=isinstance(ctx, discord.Interaction))
        b = generate_bicos(ctx.guild.id)[numero - 1]
        now = int(time.time())
        started = await db.start_bico(user.id, ctx.guild.id, b["name"], b["payout"], now + b["duration"] * 60)
        if not started:
            return await self._send(ctx, "❌ Ih, alguém chegou primeiro nessa vaga ou seu cooldown ainda tá rolando kkkkk. Tenta de novo.", ephemeral=isinstance(ctx, discord.Interaction))
        e = KibotEmbed(
            title="🧰 Bico aceito!",
            description=f"Você pegou **{b['name']}**. Agora é trabalhar e esperar o relógio andar kkkkk.",
            color=discord.Color.orange(),
        )
        e.add_field(name="💰 Vai pingar", value=format_money(b["payout"]), inline=True)
        e.add_field(name="⏱️ Tempo", value=f"{b['duration']} minutos", inline=True)
        e.add_field(name="📡 Acompanhar", value="`K! bico status`", inline=False)
        e.set_footer(text="Não dá pra pegar dois bicos ao mesmo tempo, né patrão? 😂")
        await self._send(ctx, embed=e)

    async def _status(self, ctx, target=None):
        requester = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        user = target or requester
        is_self = user.id == requester.id

        # Só finaliza/credita o bico quando o próprio dono consulta o status.
        # Consultar o status de outro membro é somente leitura.
        finished = await self._finish_if_ready(user.id, ctx.guild.id) if is_self else None
        row = await db.get_user(user.id, ctx.guild.id)
        if finished:
            badges=self.bot.get_cog("Badges")
            if badges: await badges.record(user.id,ctx.guild.id,"bicos",1,user)
            new_level,old_level,_=await db.add_xp(user.id,ctx.guild.id,boosted_xp(user,config.XP_BICO))
            if new_level>old_level:
                levels=self.bot.get_cog("Levels")
                if levels: await levels.sync_member_level_roles(user)
            level_text=f"\n⭐ +**{config.XP_BICO} XP**" + (f"\n🎖️ Você subiu para o **nível {new_level}**!" if new_level>old_level else "")
            e = KibotEmbed(title="🎉 Bico concluído!", description=f"**{finished[0]}** acabou e você recebeu **{format_money(finished[1])}**. Tá pago kkkkk.{level_text}", color=discord.Color.green())
            return await self._send(ctx, embed=e, ephemeral=isinstance(ctx, discord.Interaction))
        if not row["active_bico"]:
            if is_self:
                msg = "😴 Você não tá fazendo bico nenhum agora. Manda `K! bico` pra ver os 10 de hoje."
            else:
                msg = f"😴 {user.mention} não está fazendo nenhum bico agora."
            return await self._send(ctx, msg, ephemeral=isinstance(ctx, discord.Interaction))
        remain = row["bico_ends_at"] - int(time.time())
        prefix = "Você tá" if is_self else f"{user.mention} está"
        e = KibotEmbed(title="⏳ Bico em andamento", description=f"{prefix} no **{row['active_bico']}**.", color=discord.Color.orange())
        e.add_field(name="🕐 Falta", value=f"**{fmt_time(remain)}**", inline=True)
        e.add_field(name="💰 Pagamento", value=format_money(row["active_bico_payout"]), inline=True)
        e.set_footer(text="Vai tomar um café e para de olhar o relógio a cada 10 segundos kkkkk.")
        await self._send(ctx, embed=e, ephemeral=isinstance(ctx, discord.Interaction))


async def setup(bot):
    await bot.add_cog(Bicos(bot))
