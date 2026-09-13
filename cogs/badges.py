"""Sistema de badges/conquistas do Kibot."""
from cogs.embed_style import KibotEmbed
import time
import discord
from discord import app_commands
from discord.ext import commands, tasks
from database import db
import config
from cogs.utils import set_anime_gif
from cogs.utils import boosted_xp

BADGES = [
    ("primeiro_passo", "🐣 Primeiro Passo", "Mandou sua primeira mensagem no servidor.", "messages", 1, 25, 10),
    ("conversador", "💬 Conversador", "Mandou 100 mensagens.", "messages", 100, 500, 75),
    ("tagarela", "🗣️ Tagarela", "Mandou 1.000 mensagens.", "messages", 1000, 3000, 250),
    ("lenda_do_chat", "👑 Lenda do Chat", "Mandou 5.000 mensagens.", "messages", 5000, 10000, 750),
    ("voz_ativa", "🎙️ Voz Ativa", "Ficou 10 minutos em call.", "voice_minutes", 10, 100, 25),
    ("uma_hora", "⏱️ Uma Hora", "Ficou 1 hora em call.", "voice_minutes", 60, 750, 150),
    ("plantao_call", "🎧 Plantão da Call", "Ficou 5 horas em call.", "voice_minutes", 300, 3000, 500),
    ("morador_da_call", "🏠 Morador da Call", "Ficou 24 horas em call no total.", "voice_minutes", 1440, 10000, 1500),
    ("daily_7", "📅 Semana de Daily", "Pegou 7 dailies.", "dailies", 7, 1000, 200),
    ("daily_30", "🗓️ Mês de Daily", "Pegou 30 dailies.", "dailies", 30, 5000, 600),
    ("daily_100", "☀️ Viciado em Daily", "Pegou 100 dailies.", "dailies", 100, 20000, 2000),
    ("trabalhador_10", "🧰 Trabalhador", "Concluiu 10 turnos.", "works", 10, 1000, 250),
    ("trabalhador_50", "🏗️ Operário Incansável", "Concluiu 50 turnos.", "works", 50, 5000, 750),
    ("trabalhador_200", "💼 Máquina de Trabalhar", "Concluiu 200 turnos.", "works", 200, 20000, 2500),
    ("bico_1", "🧹 Primeiro Bico", "Concluiu seu primeiro bico.", "bicos", 1, 100, 30),
    ("bico_25", "🧾 Freelancer", "Concluiu 25 bicos.", "bicos", 25, 2500, 500),
    ("bico_100", "📋 Rei dos Bicos", "Concluiu 100 bicos.", "bicos", 100, 15000, 1800),
    ("empresa_1", "🏢 Empreendedor", "Abriu sua primeira empresa.", "companies", 1, 2500, 500),
    ("empresa_3", "📈 Empresário Serial", "Abriu 3 empresas ao longo da carreira.", "companies", 3, 10000, 1200),
    ("lucro_10", "💰 Primeiro Milhão", "Coletou lucro de empresa 10 vezes.", "company_profits", 10, 5000, 750),
    ("lucro_50", "🏦 Magnata", "Coletou lucro de empresa 50 vezes.", "company_profits", 50, 25000, 3000),
    ("chat_25000", "📡 Frequência Kiba", "Mandou 25.000 mensagens.", "messages", 25000, 50000, 5000),
    ("chat_50000", "🌌 Entidade do Chat", "Mandou 50.000 mensagens.", "messages", 50000, 100000, 10000),
    ("voz_100", "🎙️ Voz de Ferro", "Ficou 100 horas em call no total.", "voice_minutes", 6000, 50000, 7500),
    ("daily_365", "🐦 Ano do Corvo", "Pegou 365 dailies.", "dailies", 365, 100000, 10000),
    ("trabalho_500", "🏆 Patrão do Mês", "Concluiu 500 turnos.", "works", 500, 60000, 7000),
    ("bico_500", "🪶 Lenda dos Bicos", "Concluiu 500 bicos.", "bicos", 500, 75000, 9000),
    ("empresa_5", "🏙️ Conglomerado", "Abriu 5 empresas ao longo da carreira.", "companies", 5, 50000, 5000),
    ("empresa_lucro_100", "💎 Império do Corvo", "Coletou lucro de empresa 100 vezes.", "company_profits", 100, 100000, 12000),
]


class BadgePager(discord.ui.View):
    def __init__(self, cog, user, pages, earned_count):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user
        self.pages = pages
        self.earned_count = earned_count
        self.page = 0
        self.message = None
        self._sync()

    def _sync(self):
        self.prev.disabled = self.page == 0
        self.next.disabled = self.page >= len(self.pages) - 1

    def make_embed(self):
        earned_count = self.earned_count
        e = KibotEmbed(
            title=f"🏆 Badges de {self.user.display_name}",
            description=f"Conquistas desbloqueadas: **{earned_count}/{len(BADGES)}**",
            color=discord.Color.gold(),
        )
        e.add_field(name=f"Progresso • página {self.page + 1}/{len(self.pages)}", value=self.pages[self.page], inline=False)
        e.set_footer(text="O Corvo está de olho 👀")
        return e

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("🔒 Essa lista não é sua kkkkk.", ephemeral=True)
        self.page -= 1
        self._sync()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary)
    async def next(self, interaction, button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("🔒 Essa lista não é sua kkkkk.", ephemeral=True)
        self.page += 1
        self._sync()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


class Badges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_users = {}
        self.last_earned_count = 0
        self.voice_loop.start()

    def cog_unload(self):
        self.voice_loop.cancel()

    async def record(self, user_id, guild_id, activity, amount=1, member=None):
        if amount <= 0:
            return []
        await db.increment_activity(user_id, guild_id, activity, amount)
        value = await db.get_activity(user_id, guild_id, activity)
        existing_rows = await db.get_earned_badges(user_id, guild_id)
        existing = {r["badge_key"] for r in existing_rows}
        earned = []
        for key, title, desc, kind, target, crw, xp in BADGES:
            if kind != activity or value < target or key in existing:
                continue
            if not await db.award_badge(user_id, guild_id, key):
                continue
            await db.update_balance(user_id, guild_id, crw)
            new_level, old_level, _ = await db.add_xp(user_id, guild_id, boosted_xp(member or await self._get_member(guild_id, user_id), xp))
            if new_level > old_level:
                levels = self.bot.get_cog("Levels")
                if levels and member:
                    await levels.sync_member_level_roles(member)
            awarded_xp = boosted_xp(member or await self._get_member(guild_id, user_id), xp)
            earned.append((key, title, desc, crw, awarded_xp, new_level > old_level, new_level))
            await self._notify(member or await self._get_member(guild_id, user_id), earned[-1])
        return earned

    async def _get_member(self, guild_id, user_id):
        guild = self.bot.get_guild(guild_id)
        return guild.get_member(user_id) if guild else None

    async def _notify(self, member, item):
        if not member:
            return
        _, title, desc, crw, xp, leveled, level = item
        text = f"🏆 **NOVA CONQUISTA!**\n\n{title}\n{desc}\n\n🎁 Recompensa: **{config.CURRENCY_SYMBOL} {config.CURRENCY_CODE} {crw:,}** + **{xp} XP**".replace(",", ".")
        if leveled:
            text += f"\n🎖️ E ainda subiu para o **nível {level}**!"
        try:
            await member.send(text)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild and not message.author.bot:
            await self.record(message.author.id, message.guild.id, "messages", 1, message.author)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        key = (member.guild.id, member.id)
        if after.channel is not None and before.channel is None:
            self.voice_users[key] = time.time()
        elif after.channel is None and before.channel is not None:
            self.voice_users.pop(key, None)
        elif after.channel != before.channel and after.channel is not None:
            self.voice_users[key] = time.time()

    @tasks.loop(minutes=1)
    async def voice_loop(self):
        for guild_id, user_id in list(self.voice_users):
            guild = self.bot.get_guild(guild_id)
            member = guild.get_member(user_id) if guild else None
            if not member or not member.voice or not member.voice.channel:
                self.voice_users.pop((guild_id, user_id), None)
                continue
            await self.record(user_id, guild_id, "voice_minutes", 1, member)

    @voice_loop.before_loop
    async def before_voice_loop(self):
        await self.bot.wait_until_ready()

    async def _show(self, ctx):
        user = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        try:
            rows = await db.get_earned_badges(user.id, ctx.guild.id)
            earned = {r["badge_key"] for r in rows}
            earned_count = len(earned)

            lines = []
            for key, title, desc, kind, target, crw, xp in BADGES:
                status = "✅" if key in earned else "🔒"
                line = (
                    f"{status} **{title}** — {desc}\n"
                    f"🎁 {config.CURRENCY_SYMBOL} {config.CURRENCY_CODE} {crw:,} + {xp} XP"
                ).replace(",", ".")
                lines.append(line)

            # Discord limita cada field.value a 1024 caracteres.
            # Montamos páginas com margem de segurança e também garantimos
            # que uma linha individual nunca ultrapasse o limite.
            pages = []
            current = ""
            LIMIT = 900
            for line in lines:
                chunks = [line[i:i+LIMIT] for i in range(0, len(line), LIMIT)] if len(line) > LIMIT else [line]
                for chunk in chunks:
                    candidate = chunk if not current else current + "\n\n" + chunk
                    if current and len(candidate) > LIMIT:
                        pages.append(current)
                        current = chunk
                    else:
                        current = candidate
            if current:
                pages.append(current)
            if not pages:
                pages = ["Nenhuma conquista disponível."]

            view = BadgePager(self, user, pages, earned_count)
            embed_obj = view.make_embed()
            await set_anime_gif(embed_obj, "happy" if earned_count else "think")

            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(embed=embed_obj, view=view, ephemeral=True)
                view.message = await ctx.original_response()
            else:
                view.message = await ctx.send(embed=embed_obj, view=view)

        except Exception:
            import logging
            logging.getLogger("kibot.badges").exception(
                "Falha ao abrir badges para %s", user.id
            )
            msg = "❌ Deu erro ao carregar suas badges. O erro foi registrado no console do Kibot."
            if isinstance(ctx, discord.Interaction):
                if ctx.response.is_done():
                    await ctx.followup.send(msg, ephemeral=True)
                else:
                    await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.send(msg)

    @commands.command(name="badges", aliases=["badge", "conquistas", "conquista"])
    async def p_badges(self, ctx):
        await self._show(ctx)

    @app_commands.command(name="badges", description="Veja suas badges e o progresso das conquistas")
    async def badges_slash(self, interaction):
        await self._show(interaction)


async def setup(bot):
    await bot.add_cog(Badges(bot))
