from cogs.embed_style import KibotEmbed
import asyncio
import random
from dataclasses import dataclass

import discord
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.utils import parse_amount, async_boosted_crw, set_anime_gif
import config

RNG = random.SystemRandom()
DELAY = 2.25
CRASH_TICK = 1.00
MINES_DELAY = 1.20
JACKPOT_CHANCE = float(getattr(config, "JACKPOT_CHANCE", 0.05))
JACKPOT_MULTIPLIER = int(getattr(config, "JACKPOT_MULTIPLIER", 3))
RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}


def money(n: int, currency: str = "CRW") -> str:
    """Formata valores de aposta em CRW ou XP."""
    n = int(n)
    if currency == "XP":
        return f"⭐ {n:,} XP".replace(",", ".")
    return f"{config.CURRENCY_SYMBOL} {config.CURRENCY_CODE} {n:,}".replace(",", ".")


def parse_bet(value, row):
    """Aceita CRW por padrão e XP com `xp:100`, `xp100` ou `100xp`."""
    raw = str(value).strip().lower().replace(" ", "")
    currency = "CRW"
    if raw.startswith("xp:"):
        currency, raw = "XP", raw[3:]
    elif raw.startswith("xp") and len(raw) > 2:
        currency, raw = "XP", raw[2:]
    elif raw.endswith("xp") and len(raw) > 2:
        currency, raw = "XP", raw[:-2]
    base = None
    if currency == "XP":
        # `all`/`half` também funcionam para XP.
        total_xp = sum(100 * i for i in range(1, max(1, int(row["level"])))) + int(row["xp"])
        base = total_xp
    amount = parse_amount(raw, base)
    return currency, amount


COLORS = {
    "win": 0x2ECC71,
    "loss": 0xE74C3C,
    "draw": 0xF1C40F,
    "neutral": 0xC9A227,
}


def embed(title, description="", color=COLORS["neutral"]):
    return KibotEmbed(title=title, description=description, color=color)


async def begin_component(interaction):
    """Acknowledge a button interaction immediately; all later edits use the original message."""
    if not interaction.response.is_done():
        await interaction.response.defer()


def result_embed(game, status, description, *, wager=None, payout_amount=None, player=None, currency="CRW", jackpot=False):
    """Embed final: verde = ganhou, vermelho = perdeu, amarelo = empate."""
    icons = {"win": "🟢", "loss": "🔴", "draw": "🟡"}
    labels = {"win": "GANHOU", "loss": "PERDEU", "draw": "EMPATE"}
    title = f"🎰 JACKPOT • {game}" if jackpot else f"{icons[status]} {game} • {labels[status]}"
    e = KibotEmbed(
        title=title,
        description=description,
        color=COLORS[status],
    )
    if jackpot:
        e.add_field(name="🎰 JACKPOT", value=f"**{JACKPOT_MULTIPLIER}× a aposta**", inline=True)
    if wager is not None:
        e.add_field(name="🎟️ Aposta", value=f"**{money(wager, currency)}**", inline=True)
    if payout_amount is not None:
        e.add_field(name="💰 Pagamento", value=f"**{money(payout_amount, currency)}**", inline=True)
    e.add_field(name="━━━━━━━━━━━━━━━━", value="⠀", inline=False)
    if player is not None:
        e.set_author(name=f"🎮 Partida de {player.display_name}", icon_url=player.display_avatar.url)
    e.set_footer(text={
        "win": "Aí sim 😎",
        "loss": "Faz parte kkkkk. Tenta de novo quando quiser.",
        "draw": "Deu elas por elas 🤝",
    }[status].strip())
    return e


async def bet(user_id: int, guild_id: int, amount: int, currency: str = "CRW") -> bool:
    if currency == "XP":
        return await db.spend_xp(user_id, guild_id, amount)
    return await db.spend_bank(user_id, guild_id, amount)


async def payout(user_id: int, guild_id: int, amount: int, currency: str = "CRW", member=None):
    if amount <= 0:
        return
    if currency == "XP":
        # XP ganho em jogo também respeita o bônus de 2x do dono/Booster.
        from cogs.utils import boosted_xp
        await db.add_xp(user_id, guild_id, boosted_xp(member, amount))
    else:
        member_gain = await async_boosted_crw(member, amount) if member is not None else amount
        await db.update_bank(user_id, guild_id, member_gain)


def jackpot_hit() -> bool:
    return RNG.random() < JACKPOT_CHANCE


def resolve_win(wager: int, normal_multiplier: int | float) -> tuple[int, bool]:
    """Converte uma vitória em pagamento. Jackpot garante no mínimo 3x."""
    if jackpot_hit():
        return int(wager * max(JACKPOT_MULTIPLIER, normal_multiplier)), True
    return int(wager * normal_multiplier), False


class GameView(discord.ui.View):
    async def on_error(self, interaction, error, item):
        import logging
        logging.getLogger("kibot.arcade").exception(
            "Erro em botão do jogo %s", type(item).__name__, exc_info=error
        )
        msg = "❌ O jogo encontrou um erro. Reinicie a partida e tente novamente."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            logging.getLogger("kibot.arcade").exception("Falha ao informar erro do jogo")

    def __init__(self, author, wager, currency="CRW", timeout=180):
        super().__init__(timeout=timeout)
        self.author = author
        self.guild_id = None
        self.wager = wager
        self.currency = currency
        self.finished = False
        self.busy = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("🔒 Ih, essa partida não é sua kkkkk.", ephemeral=True)
            return False
        if self.finished or self.busy:
            await interaction.response.send_message("⏳ Calma aí kkkkk, deixa essa rodada terminar primeiro.", ephemeral=True)
            return False
        return True

    def disable_game_buttons(self):
        for child in self.children:
            if getattr(child, "custom_id", "") not in {"rules", "replay"}:
                child.disabled = True

    async def on_timeout(self):
        # Se o jogador abandonou uma partida sem finalizar, devolvemos a aposta uma única vez.
        if not self.finished:
            await payout(self.author.id, self.guild_id, self.wager, self.currency, self.author)
            self.finished = True


class RouletteView(GameView):
    def __init__(self, author, wager, currency="CRW"):
        super().__init__(author, wager, currency)

    @discord.ui.button(label="Vermelho", style=discord.ButtonStyle.danger, emoji="🔴")
    async def red(self, interaction, button):
        await self.spin(interaction, "vermelho")

    @discord.ui.button(label="Preto", style=discord.ButtonStyle.secondary, emoji="⚫")
    async def black(self, interaction, button):
        await self.spin(interaction, "preto")

    @discord.ui.button(label="Verde (0)", style=discord.ButtonStyle.success, emoji="🟢")
    async def green(self, interaction, button):
        await self.spin(interaction, "verde")

    async def spin(self, interaction, choice):
        self.busy = True
        self.disable_game_buttons()
        await begin_component(interaction)
        await interaction.edit_original_response(embed=embed("🎡 Roleta", "A roleta está girando..."), view=self)
        await asyncio.sleep(DELAY)
        n = RNG.randrange(37)
        color = "verde" if n == 0 else ("vermelho" if n in RED else "preto")
        if choice == color:
            multiplier = 36 if choice == "verde" else 2
            total, jackpot = resolve_win(self.wager, multiplier)
            await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
            status = "win"
            result = f"🎰 JACKPOT! **{JACKPOT_MULTIPLIER}×** — " if jackpot else ""
            result += f"🎉 BOAAAA! Você acertou **{color}** e levou **{money(total, self.currency)}**!"
        else:
            total = 0
            status = "loss"
            result = f"💸 Aí foi de base kkkkk. Você perdeu **{money(self.wager, self.currency)}**."
        self.finished = True
        self.busy = False
        await interaction.edit_original_response(embed=result_embed(
            "🎡 Roleta", status,
            f"🎯 Caiu o número **{n}** ({color}).\n\n{result}\n\n*Vermelho/preto pagam 2× e verde paga 36×. Jackpot: 3×.*",
            wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot if status == "win" else False
        ), view=self)


class CoinflipView(GameView):
    def __init__(self, author, wager, currency="CRW"):
        super().__init__(author, wager, currency)

    @discord.ui.button(label="Cara", style=discord.ButtonStyle.primary, emoji="🙂")
    async def heads(self, interaction, button):
        await self.flip(interaction, "cara")

    @discord.ui.button(label="Coroa", style=discord.ButtonStyle.secondary, emoji="🪙")
    async def tails(self, interaction, button):
        await self.flip(interaction, "coroa")

    async def flip(self, interaction, choice):
        self.busy = True
        self.disable_game_buttons()
        await begin_component(interaction)
        await interaction.edit_original_response(embed=embed("🪙 Cara ou Coroa", "A moeda está no ar..."), view=self)
        await asyncio.sleep(DELAY)
        result = RNG.choice(["cara", "coroa"])
        if result == choice:
            total, jackpot = resolve_win(self.wager, 2)
            await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
            status = "win"
            text = (f"🎰 JACKPOT! **{JACKPOT_MULTIPLIER}×** — " if jackpot else "") + f"🎉 Deu **{result}**! Tá rico (ou quase) kkkkk. Levou **{money(total, self.currency)}**."
        else:
            total = 0
            status = "loss"
            text = f"💸 Deu **{result}**. A moeda te odeia hoje kkkkk. Você perdeu **{money(self.wager, self.currency)}**."
        self.finished = True
        self.busy = False
        await interaction.edit_original_response(embed=result_embed("🪙 Cara ou Coroa", status, text, wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot if status == "win" else False), view=self)


class DiceView(GameView):
    def __init__(self, author, wager, currency="CRW"):
        super().__init__(author, wager, currency)

    @discord.ui.button(label="Menor (1–3)", style=discord.ButtonStyle.primary)
    async def low(self, interaction, button):
        await self.roll(interaction, "low")

    @discord.ui.button(label="Quatro", style=discord.ButtonStyle.success, emoji="🎯")
    async def seven(self, interaction, button):
        await self.roll(interaction, "seven")

    @discord.ui.button(label="Maior (5–6)", style=discord.ButtonStyle.primary)
    async def high(self, interaction, button):
        await self.roll(interaction, "high")

    async def roll(self, interaction, choice):
        self.busy = True
        self.disable_game_buttons()
        await begin_component(interaction)
        await interaction.edit_original_response(embed=embed("🎲 Dados", "Os dados estão rolando..."), view=self)
        await asyncio.sleep(DELAY)
        n = RNG.randint(1, 6)
        won = (choice == "low" and n <= 3) or (choice == "high" and n >= 5) or (choice == "seven" and n == 4)
        # Aposta em 4 é o evento central e paga 5×; as faixas pagam 2×.
        if won:
            multiplier = 5 if choice == "seven" else 2
            total, jackpot = resolve_win(self.wager, multiplier)
            await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
            status = "win"
            text = (f"🎰 JACKPOT! **{JACKPOT_MULTIPLIER}×** — " if jackpot else "") + f"🎉 Saiu **{n}**! Mandou bem demais. Você levou **{money(total, self.currency)}**."
        else:
            total = 0
            status = "loss"
            text = f"💸 Saiu **{n}**. Hoje os dados resolveram te sacanear kkkkk."
        self.finished = True
        self.busy = False
        await interaction.edit_original_response(embed=result_embed("🎲 Dados", status, text, wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot if status == "win" else False), view=self)


class SlotsView(GameView):
    SYMBOLS = ["🍒", "🍋", "🔔", "⭐", "💎", "7️⃣"]

    def __init__(self, author, wager, currency="CRW"):
        super().__init__(author, wager, currency)

    @discord.ui.button(label="GIRAR", style=discord.ButtonStyle.success, emoji="🎰")
    async def spin(self, interaction, button):
        self.busy = True
        button.disabled = True
        await begin_component(interaction)
        await interaction.edit_original_response(embed=embed("🎰 Slots", "`❔ | ❔ | ❔`\n\nOs rolos estão girando..."), view=self)
        await asyncio.sleep(DELAY)
        roll = [RNG.choice(self.SYMBOLS) for _ in range(3)]
        counts = {x: roll.count(x) for x in set(roll)}
        if len(counts) == 1:
            multiplier = 10 if roll[0] == "7️⃣" else 6
        elif 2 in counts.values():
            multiplier = 2
        else:
            multiplier = 0
        total, jackpot = resolve_win(self.wager, multiplier) if multiplier else (0, False)
        await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
        self.finished = True
        self.busy = False
        self.disable_game_buttons()
        if multiplier:
            status = "win"
            shown_multiplier = JACKPOT_MULTIPLIER if jackpot else multiplier
            text = (f"🎰 JACKPOT! **{JACKPOT_MULTIPLIER}×** — " if jackpot else "") + f"🎉 `{' | '.join(roll)}`\n\nAí sim! **{shown_multiplier}×** → você levou **{money(total, self.currency)}**."
        else:
            status = "loss"
            text = f"😵 `{' | '.join(roll)}`\n\nNada feito kkkkk. Você perdeu **{money(self.wager, self.currency)}**."
        await interaction.edit_original_response(embed=result_embed("🎰 Slots", status, text, wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot if status == "win" else False), view=self)


@dataclass
class Card:
    rank: str
    suit: str


class BlackjackView(GameView):
    def __init__(self, author, wager, currency="CRW"):
        super().__init__(author, wager, currency)
        self.deck = [Card(r, s) for r in ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"] for s in ["♠", "♥", "♦", "♣"]]
        RNG.shuffle(self.deck)
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]

    def value(self, hand):
        total, aces = 0, 0
        for c in hand:
            if c.rank in {"J", "Q", "K"}: total += 10
            elif c.rank == "A": total += 11; aces += 1
            else: total += int(c.rank)
        while total > 21 and aces:
            total -= 10; aces -= 1
        return total

    def cards(self, hand):
        return " ".join(f"{c.rank}{c.suit}" for c in hand)

    def text(self, reveal=False):
        dealer = self.cards(self.dealer) if reveal else f"{self.dealer[0].rank}{self.dealer[0].suit} 🂠"
        dv = self.value(self.dealer) if reveal else self.value([self.dealer[0]])
        return f"**Dealer ({dv})**\n`{dealer}`\n\n**Você ({self.value(self.player)})**\n`{self.cards(self.player)}`"

    @discord.ui.button(label="Comprar", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit(self, interaction, button):
        self.busy = True
        await begin_component(interaction)
        await interaction.edit_original_response(embed=embed("🃏 Blackjack", self.text() + "\n\n⏳ Comprando carta..."), view=self)
        await asyncio.sleep(DELAY)
        self.busy = False
        if self.finished:
            return
        self.player.append(self.deck.pop())
        if self.value(self.player) >= 21:
            await self.finish(interaction)
            return
        await interaction.edit_original_response(embed=embed("🃏 Blackjack", self.text()), view=self)

    @discord.ui.button(label="Parar", style=discord.ButtonStyle.success, emoji="✋")
    async def stand(self, interaction, button):
        await begin_component(interaction)
        await self.finish(interaction)

    async def finish(self, interaction):
        self.busy = True
        self.disable_game_buttons()
        await interaction.edit_original_response(
            embed=embed("🃏 Blackjack", self.text() + "\n\n⏳ O dealer está jogando..."),
            view=self,
        )
        await asyncio.sleep(DELAY)
        pv = self.value(self.player)
        if pv <= 21:
            while self.value(self.dealer) < 17:
                self.dealer.append(self.deck.pop())
                await asyncio.sleep(DELAY)
        dv = self.value(self.dealer)
        if pv > 21:
            multiplier, status, result = 0, "loss", "💥 Você estourou. A mão foi pro espaço kkkkk."
        elif dv > 21 or pv > dv:
            if len(self.player) == 2 and pv == 21:
                multiplier, status, result, jackpot = JACKPOT_MULTIPLIER, "win", "🎰 JACKPOT! Blackjack natural! **3×** a aposta.", True
            else:
                multiplier, jackpot = 2, jackpot_hit()
                if jackpot:
                    multiplier = JACKPOT_MULTIPLIER
                status, result = "win", (f"🎰 JACKPOT! **{JACKPOT_MULTIPLIER}×** a aposta!" if jackpot else "🎉 Você amassou o dealer!")
        elif pv == dv:
            multiplier, status, result, jackpot = 1, "draw", "🤝 Deu empate! Sua aposta voltou inteirinha.", False
        else:
            multiplier, status, result, jackpot = 0, "loss", "💸 O dealer levou essa. Foi quase!", False
        if pv > 21:
            jackpot = False
        total = self.wager * multiplier
        await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
        self.finished = True; self.busy = False
        await interaction.edit_original_response(embed=result_embed(
            "🃏 Blackjack", status,
            f"{self.text(reveal=True)}\n\n{result}",
            wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot
        ), view=self)


class CrashView(GameView):
    def __init__(self, author, wager, currency="CRW"):
        super().__init__(author, wager, currency)
        self.multiplier = 1.0
        self.crash_at = max(1.01, min(20.0, 1.0 / (1.0 - RNG.random())))
        self.crash_at = round(self.crash_at, 2)
        self.running = False
        self._task = None

    @discord.ui.button(label="Iniciar", style=discord.ButtonStyle.primary, emoji="🚀")
    async def start(self, interaction, button):
        if self.running or self.finished:
            return
        self.running = True
        button.disabled = True
        await begin_component(interaction)
        await interaction.edit_original_response(
            embed=embed("🚀 Crash", "🚀 Partiu! Aperta **Sacar** antes do foguete explodir kkkkk."),
            view=self,
        )
        self._task = asyncio.create_task(self._run(interaction))

    async def _run(self, interaction):
        try:
            while self.running and not self.finished and self.multiplier < self.crash_at:
                await asyncio.sleep(CRASH_TICK)
                if self.finished or not self.running:
                    return
                # Crescimento deliberadamente suave: nada de pular de 1.00x para 1.50x.
                increment = 0.015 + (self.multiplier * 0.025)
                self.multiplier = round(min(self.crash_at, self.multiplier + increment), 2)
                if self.multiplier >= self.crash_at:
                    self.finished = True
                    self.running = False
                    self.busy = False
                    self.disable_game_buttons()
                    await interaction.edit_original_response(
                        embed=result_embed(
                            "🚀 Crash", "loss",
                            f"💥 O foguete explodiu em **{self.crash_at:.2f}×**. Você perdeu **{money(self.wager, self.currency)}**.",
                            wager=self.wager, payout_amount=0, player=self.author
                        ), view=self
                    )
                    return
                try:
                    await interaction.edit_original_response(
                        embed=embed(
                            "🚀 Crash",
                            f"Multiplicador: **{self.multiplier:.2f}×**\n\nCorre e aperta **Sacar** antes de dar ruim!"
                        ),
                        view=self,
                    )
                except discord.HTTPException:
                    if self.finished or not self.running:
                        return
        except asyncio.CancelledError:
            return

    @discord.ui.button(label="Sacar", style=discord.ButtonStyle.success, emoji="💰")
    async def cashout(self, interaction, button):
        if not self.running or self.finished:
            await interaction.response.send_message("❌ Aperta **Iniciar** primeiro ou a rodada já acabou kkkkk.", ephemeral=True)
            return
        # Finaliza o estado ANTES de pagar, impedindo o loop do foguete de editar a mensagem depois do saque.
        self.finished = True
        self.running = False
        self.busy = True
        if self._task and not self._task.done():
            self._task.cancel()
        base_total = max(self.wager, int(self.wager * self.multiplier))
        jackpot = jackpot_hit()
        total = max(base_total, int(self.wager * JACKPOT_MULTIPLIER)) if jackpot else base_total
        await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
        self.busy = False
        self.disable_game_buttons()
        await begin_component(interaction)
        await interaction.edit_original_response(
            embed=result_embed(
                "🚀 Crash", "win",
                f"💰 Você sacou em **{self.multiplier:.2f}×** e saiu com **{money(total, self.currency)}**!" + (f"\n🎰 **JACKPOT! 3× a aposta.**" if jackpot else ""),
                wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot
            ),
            view=self,
        )


class MinesView(GameView):
    SIZE = 5
    CELLS = 20
    DEFAULT_BOMBS = 4
    MIN_BOMBS = 1
    MAX_BOMBS = 19

    def __init__(self, author, wager, currency="CRW", bombs=DEFAULT_BOMBS):
        super().__init__(author, wager, currency)
        self.bomb_count = max(self.MIN_BOMBS, min(self.MAX_BOMBS, int(bombs)))
        self.bombs = set(RNG.sample(range(self.CELLS), self.bomb_count))
        self.opened = set()
        self.current_multiplier = 1.0
        # Quanto mais bombas, maior o multiplicador por casa segura.
        # Isso mantém a escolha de dificuldade relevante sem depender de um valor fixo.
        self.step_multiplier = 1.10 + (self.bomb_count * 0.02)
        # 20 casas + botão de saque = 21 componentes.
        for index in range(20):
            button = discord.ui.Button(label="⬜", style=discord.ButtonStyle.secondary, row=index // 5)
            button.callback = self._make_cell_callback(index)
            self.add_item(button)
        cash = discord.ui.Button(label="Sacar", style=discord.ButtonStyle.success, emoji="💰", row=4)
        cash.callback = self.cashout_action
        self.add_item(cash)

    def _make_cell_callback(self, index):
        async def callback(interaction):
            await self.cell(interaction, index)
        return callback

    def render(self):
        # O tabuleiro exibido corresponde às 20 casas jogáveis.
        return "\n".join(
            " ".join(
                "💥" if i in self.opened and i in self.bombs else ("💎" if i in self.opened else "⬜")
                for i in range(r * 5, r * 5 + 5)
            ) for r in range(4)
        )

    async def cell(self, interaction, index):
        if index in self.opened or self.busy or self.finished:
            return
        self.busy = True
        await begin_component(interaction)
        await interaction.edit_original_response(embed=embed("💣 Mines", self.render() + "\n\n⏳ Abrindo a casa..."), view=self)
        await asyncio.sleep(MINES_DELAY)
        self.busy = False
        if self.finished:
            return
        self.opened.add(index)
        if index in self.bombs:
            self.finished = True
            self.disable_game_buttons()
            await interaction.edit_original_response(
                embed=result_embed("💣 Mines", "loss", self.render() + f"\n\n💥 BOOM! Você perdeu **{money(self.wager, self.currency)}**.", wager=self.wager, payout_amount=0, player=self.author, currency=self.currency),
                view=self,
            )
            return
        safe = len(self.opened)
        self.current_multiplier = round(min(10.0, self.step_multiplier ** safe), 2)
        total = int(self.wager * self.current_multiplier)
        await interaction.edit_original_response(
            embed=embed("💣 Mines", self.render() + f"\n\nMultiplicador: **{self.current_multiplier:.2f}×**\nSaque disponível: **{money(total, self.currency)}**"),
            view=self,
        )

    async def cashout_action(self, interaction):
        if not self.opened:
            await interaction.response.send_message("❌ Abre pelo menos uma casinha primeiro kkkkk.", ephemeral=True)
            return
        base_total = int(self.wager * self.current_multiplier)
        jackpot = jackpot_hit()
        total = max(base_total, int(self.wager * JACKPOT_MULTIPLIER)) if jackpot else base_total
        await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
        self.finished = True
        self.disable_game_buttons()
        await begin_component(interaction)
        await interaction.edit_original_response(
            embed=result_embed("💣 Mines", "win", self.render() + f"\n\n💰 Mandou bem! Você sacou **{money(total, self.currency)}**." + (f"\n🎰 **JACKPOT! 3× a aposta.**" if jackpot else ""), wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot),
            view=self,
        )


def view_title(cls):
    return {RouletteView:"🎡 Roleta", CoinflipView:"🪙 Cara ou Coroa", DiceView:"🎲 Dados", SlotsView:"🎰 Slots", BlackjackView:"🃏 Blackjack", CrashView:"🚀 Crash", MinesView:"💣 Mines", BuckshotView:"🔫 Buckshot"}.get(cls, "🎮 Jogo")




BUCKSHOT_DELAY = 5.0
BUCKSHOT_MODES = {
    "normal": {"chambers": 6, "label": "Normal", "emoji": "🔫", "min_live": 1, "max_live": 3, "stop_after": 3},
    "dificil": {"chambers": 8, "label": "Difícil", "emoji": "💀", "min_live": 2, "max_live": 4, "stop_after": 4},
    "v4i": {"chambers": 16, "label": "V4I S3 FUD3R!", "emoji": "☠️", "min_live": 4, "max_live": 8, "stop_after": 8},
}


def buckshot_steps(chambers: int):
    # Cada disparo de festim aumenta o valor da saída. A curva mantém o
    # pico original de 2x se a partida durar até o fim.
    if chambers == 6:
        return [0.25, 0.25, 0.25, 0.25, 0.50, 0.50]
    if chambers == 8:
        return [0.20] * 4 + [0.30] * 4
    return [0.075] * 12 + [0.10] * 2 + [0.50, 0.50]


class BuckshotModeView(discord.ui.View):
    def __init__(self, author, wager, start_game):
        super().__init__(timeout=90)
        self.author = author
        self.wager = wager
        self.start_game = start_game

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("🔒 Ih, essa partida não é sua kkkkk.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Normal • 6", style=discord.ButtonStyle.success, emoji="🔫", row=0)
    async def normal(self, interaction, button):
        await self.start_game(interaction, "normal")

    @discord.ui.button(label="Difícil • 8", style=discord.ButtonStyle.danger, emoji="💀", row=0)
    async def difficult(self, interaction, button):
        await self.start_game(interaction, "dificil")

    @discord.ui.button(label="V4I S3 FUD3R! • 16", style=discord.ButtonStyle.secondary, emoji="☠️", row=1)
    async def v4i(self, interaction, button):
        await self.start_game(interaction, "v4i")


class BuckshotView(GameView):
    """Buckshot PvB com 3 vidas por lado e 3 itens aleatórios por partida.

    Regras desta implementação:
    - O BOT sempre começa a partida, em qualquer dificuldade.
    - Jogador e bot possuem 3 vidas; um disparo verdadeiro remove 1 vida.
    - Tiro verdadeiro mantém a vez de quem atirou; festim passa a vez.
    - Ao zerar as vidas do alvo, a partida termina.
    - O jogador recebe 3 itens aleatórios e únicos no começo da partida.
    """

    ITEMS = {
        "lupa": {
            "name": "Lupa",
            "emoji": "🔍",
            "description": "Revela se a próxima câmara é bala verdadeira ou festim.",
        },
        "serra": {
            "name": "Serra",
            "emoji": "🪚",
            "description": "Seu próximo tiro verdadeiro causa 2 de dano em vez de 1.",
        },
        "cigarro": {
            "name": "Cigarro",
            "emoji": "🚬",
            "description": "Recupera 1 vida, até o máximo de 3.",
        },
        "cerveja": {
            "name": "Cerveja",
            "emoji": "🍺",
            "description": "Ejeta a próxima câmara sem dispará-la e passa a vez.",
        },
        "algemas": {
            "name": "Algemas",
            "emoji": "⛓️",
            "description": "Pula a próxima vez do bot e devolve a vez para você.",
        },
        "telefone": {
            "name": "Telefone",
            "emoji": "📞",
            "description": "Revela a composição de até 2 câmaras futuras.",
        },
        "inversor": {
            "name": "Inversor",
            "emoji": "🔄",
            "description": "Inverte o tipo da próxima câmara.",
        },
        "adrenalina": {
            "name": "Adrenalina",
            "emoji": "💉",
            "description": "Dá +1 de vida temporária, podendo chegar a 4.",
        },
    }

    def __init__(self, author, wager, mode, currency="CRW"):
        info = BUCKSHOT_MODES[mode]
        super().__init__(author, wager, currency=currency, timeout=360 + info["chambers"] * BUCKSHOT_DELAY * 2)
        self.mode = mode
        self.chambers = info["chambers"]
        self.stop_after = info["stop_after"]
        self.steps = buckshot_steps(self.chambers)

        self.live_count = RNG.randint(info["min_live"], info["max_live"])
        self.blank_count = self.chambers - self.live_count
        self.cylinder = [True] * self.live_count + [False] * self.blank_count
        RNG.shuffle(self.cylinder)

        self.position = 0
        self.round = 1
        self.player_turn = False  # BOT SEMPRE COMEÇA.
        self.player_lives = 3
        self.bot_lives = 3
        self.max_player_lives = 3
        self.max_bot_lives = 3
        self.player_survived = 0
        self.bot_survived = 0
        self.multiplier = 1.0
        self.busy = False
        self.next_damage = 1
        self.skip_bot_turn = False
        self.items = RNG.sample(list(self.ITEMS.keys()), 3)
        self.used_items = set()
        self.last_reveal = None

        # Três slots de item: os rótulos são preenchidos conforme o sorteio.
        self.item_buttons = []
        for index in range(3):
            button = getattr(self, f"item_{index + 1}")
            item_key = self.items[index]
            item = self.ITEMS[item_key]
            button.label = item["name"]
            button.emoji = item["emoji"]
            button.custom_id = f"buckshot_item_{item_key}"
            self.item_buttons.append(button)
        self.refresh_item_buttons()
        self.set_player_controls(False)

    @property
    def remaining_live(self):
        return sum(self.cylinder[self.position:])

    @property
    def remaining_blank(self):
        return len(self.cylinder) - self.position - self.remaining_live

    def refresh_item_buttons(self):
        for button, item_key in zip(self.item_buttons, self.items):
            button.disabled = item_key in self.used_items or self.finished or self.busy or not self.player_turn

    def render_items(self):
        lines = []
        for item_key in self.items:
            item = self.ITEMS[item_key]
            marker = "~~USADO~~" if item_key in self.used_items else f"**{item['name']}**"
            lines.append(f"{item['emoji']} {marker} — {item['description']}")
        return "\n".join(lines)

    def render(self, status=None):
        passed = "🟦 " * self.position
        remaining = "⬛ " * max(0, self.chambers - self.position)
        turn = "👤 **SUA VEZ**" if self.player_turn else "🤖 **VEZ DO BOT**"
        stop_text = f"\n🛑 **Parar disponível a partir da rodada {self.stop_after}.**" if self.round >= self.stop_after and self.player_turn else ""
        status_text = f"\n\n{status}" if status else ""
        reveal_text = f"\n🔍 **Informação revelada:** {self.last_reveal}" if self.last_reveal else ""
        return (
            f"**Modo:** {BUCKSHOT_MODES[self.mode]['label']} • **{self.chambers} câmaras**\n"
            f"**Rodada:** {self.round} • {turn}\n\n"
            f"{passed}{remaining}\n\n"
            f"❤️ Você: **{self.player_lives}/{self.max_player_lives}**  •  🤖 Bot: **{self.bot_lives}/{self.max_bot_lives}**\n"
            f"🔴 Balas verdadeiras: **{self.live_count}** • 🟢 Balas de festim: **{self.blank_count}**\n"
            f"📦 Restantes: **{self.remaining_live} verdadeiras** • **{self.remaining_blank} festim**\n"
            f"📈 Multiplicador: **{self.multiplier:.2f}×**\n"
            f"💰 Valor para parar agora: **{money(int(self.wager * self.multiplier), self.currency)}**\n\n"
            f"🎒 **SEUS ITENS**\n{self.render_items()}"
            f"{stop_text}{reveal_text}{status_text}"
        )

    def disable_all(self):
        for child in self.children:
            child.disabled = True

    def set_player_controls(self, enabled=True):
        for child in self.children:
            cid = getattr(child, "custom_id", "") or ""
            if cid == "buckshot_trigger":
                child.disabled = not enabled
            elif cid == "buckshot_stop":
                child.disabled = not (enabled and self.round >= self.stop_after)
        self.refresh_item_buttons()

    async def finish(self, interaction, status, text, total):
        jackpot = False
        if status == "win":
            jackpot = jackpot_hit()
            if jackpot:
                total = int(self.wager * JACKPOT_MULTIPLIER)
                text += f"\n\n🎰 **JACKPOT! 3× a aposta → {money(total, self.currency)}.**"
        self.finished = True
        self.busy = False
        self.disable_all()
        await payout(self.author.id, interaction.guild_id, total, self.currency, self.author)
        await interaction.edit_original_response(
            embed=result_embed("🔫 Buckshot", status, text, wager=self.wager, payout_amount=total, player=self.author, currency=self.currency, jackpot=jackpot),
            view=self,
        )

    async def use_item(self, interaction, item_key):
        if self.finished or self.busy or not self.player_turn or item_key in self.used_items:
            return
        if item_key not in self.items:
            return

        self.busy = True
        self.used_items.add(item_key)
        self.last_reveal = None
        item = self.ITEMS[item_key]
        text = f"{item['emoji']} **{item['name']}** usado. {item['description']}"

        if item_key == "lupa":
            if self.position >= self.chambers:
                self.used_items.discard(item_key)
                self.busy = False
                return
            self.last_reveal = "🔴 **BALA VERDADEIRA**" if self.cylinder[self.position] else "🟢 **BALA DE FESTIM**"
            text += f"\n\nA próxima câmara é: {self.last_reveal}."
            self.busy = False
            self.set_player_controls(True)

        elif item_key == "serra":
            self.next_damage = 2
            text += "\n\n🪚 Seu próximo tiro verdadeiro causará **2 de dano**."
            self.busy = False
            self.set_player_controls(True)

        elif item_key == "cigarro":
            if self.player_lives >= self.max_player_lives:
                self.used_items.discard(item_key)
                self.busy = False
                await interaction.response.send_message("🚬 Você já está com as 3 vidas completas.", ephemeral=True)
                return
            self.player_lives += 1
            text += f"\n\n❤️ Você recuperou **1 vida**. Agora está em **{self.player_lives}/{self.max_player_lives}**."
            self.busy = False
            self.set_player_controls(True)

        elif item_key == "adrenalina":
            self.max_player_lives = 4
            self.player_lives += 1
            text += f"\n\n💉 Seu limite subiu para **4 vidas** e você ganhou **+1 vida**."
            self.busy = False
            self.set_player_controls(True)

        elif item_key == "cerveja":
            if self.position < self.chambers:
                shell = self.cylinder[self.position]
                self.position += 1
                text += f"\n\n🍺 Câmara ejetada: **{'bala verdadeira' if shell else 'festim'}**."
            self.player_turn = False
            self.round += 1
            self.busy = False
            self.set_player_controls(False)
            await interaction.response.edit_message(embed=embed("🔫 Buckshot", self.render(text)), view=self)
            await self.bot_turn(interaction)
            return

        elif item_key == "algemas":
            self.skip_bot_turn = True
            text += "\n\n⛓️ O bot perderá a próxima vez."
            self.busy = False
            self.set_player_controls(True)

        elif item_key == "telefone":
            future = self.cylinder[self.position:self.position + 2]
            if not future:
                self.used_items.discard(item_key)
                self.busy = False
                return
            labels = ["🔴 verdadeira" if value else "🟢 festim" for value in future]
            self.last_reveal = " • ".join(f"Câmara +{i+1}: {label}" for i, label in enumerate(labels))
            text += f"\n\n📞 {self.last_reveal}"
            self.busy = False
            self.set_player_controls(True)

        elif item_key == "inversor":
            if self.position < self.chambers:
                self.cylinder[self.position] = not self.cylinder[self.position]
                self.last_reveal = "🔴 virou **BALA VERDADEIRA**" if self.cylinder[self.position] else "🟢 virou **FESTIM**"
                text += f"\n\n🔄 A próxima câmara {self.last_reveal}."
            self.busy = False
            self.set_player_controls(True)

        await interaction.response.edit_message(embed=embed("🔫 Buckshot", self.render(text)), view=self)

    async def player_pull(self, interaction):
        if self.finished or self.busy or not self.player_turn:
            return
        self.busy = True
        self.set_player_controls(False)
        await interaction.response.edit_message(
            embed=embed("🔫 Buckshot", self.render("⏳ Você puxou o gatilho... **5 segundos** de tensão.")),
            view=self,
        )
        await asyncio.sleep(BUCKSHOT_DELAY)
        if self.finished:
            return
        if self.position >= self.chambers:
            await self.finish(interaction, "draw", "🔄 O tambor acabou antes de alguém perder todas as vidas. Empate!", self.wager)
            return

        live = self.cylinder[self.position]
        self.position += 1
        if live:
            damage = self.next_damage
            self.next_damage = 1
            self.bot_lives = max(0, self.bot_lives - damage)
            self.multiplier = round(self.multiplier + self.steps[min(self.position - 1, len(self.steps) - 1)], 2)
            if self.bot_lives <= 0:
                await self.finish(
                    interaction, "win",
                    f"💥 **BALA VERDADEIRA!** Você acertou o bot e causou **{damage} de dano**.\n\n"
                    f"🤖 O bot ficou sem vidas. **Você venceu!**\n💰 Prêmio: **{money(int(self.wager * self.multiplier), self.currency)}** ({self.multiplier:.2f}×).",
                    int(self.wager * self.multiplier),
                )
                return
            self.player_turn = True
            self.busy = False
            self.set_player_controls(True)
            await interaction.edit_original_response(
                embed=embed("🔫 Buckshot", self.render(f"💥 **BALA VERDADEIRA!** O bot perdeu **{damage} vida(s)**.\n\n🤖 Ele ainda tem **{self.bot_lives}** vida(s). **Você continua!**")),
                view=self,
            )
            return

        self.player_survived += 1
        self.multiplier = round(self.multiplier + self.steps[min(self.position - 1, len(self.steps) - 1)], 2)
        self.player_turn = False
        self.busy = False
        self.set_player_controls(False)
        await interaction.edit_original_response(
            embed=embed("🔫 Buckshot", self.render("🟢 **FESTIM!** Você sobreviveu.\n\n🤖 Agora é a vez do bot...")),
            view=self,
        )
        await self.bot_turn(interaction)

    async def bot_turn(self, interaction):
        if self.finished:
            return
        if self.skip_bot_turn:
            self.skip_bot_turn = False
            self.round += 1
            self.player_turn = True
            self.busy = False
            self.set_player_controls(True)
            await interaction.edit_original_response(
                embed=embed("🔫 Buckshot", self.render("⛓️ **ALGEMAS!** O bot perdeu a vez.\n\n👤 Sua vez.")),
                view=self,
            )
            return

        self.busy = True
        self.disable_all()
        await interaction.edit_original_response(
            embed=embed("🔫 Buckshot", self.render("🤖 O bot está puxando o gatilho... **5 segundos.**")),
            view=self,
        )
        await asyncio.sleep(BUCKSHOT_DELAY)
        if self.finished:
            return
        if self.position >= self.chambers:
            await self.finish(interaction, "draw", "🔄 O tambor acabou antes de alguém perder todas as vidas. Empate!", self.wager)
            return

        live = self.cylinder[self.position]
        self.position += 1
        if live:
            self.player_lives = max(0, self.player_lives - 1)
            self.multiplier = round(self.multiplier + self.steps[min(self.position - 1, len(self.steps) - 1)], 2)
            if self.player_lives <= 0:
                await self.finish(
                    interaction, "loss",
                    f"💥 **BALA VERDADEIRA!** O bot acertou você.\n\n"
                    f"❤️ Suas vidas chegaram a **0**. **Você perdeu a partida.**\n💸 A aposta de **{money(self.wager, self.currency)}** foi de base.",
                    0,
                )
                return
            self.player_turn = False
            self.busy = False
            self.set_player_controls(False)
            await interaction.edit_original_response(
                embed=embed("🔫 Buckshot", self.render(f"💥 **BALA VERDADEIRA!** O bot acertou você.\n\n❤️ Você perdeu **1 vida** e ficou com **{self.player_lives}**.\n🤖 O bot continua!")),
                view=self,
            )
            await self.bot_turn(interaction)
            return

        self.bot_survived += 1
        self.multiplier = round(self.multiplier + self.steps[min(self.position - 1, len(self.steps) - 1)], 2)
        self.round += 1
        self.player_turn = True
        self.busy = False
        self.set_player_controls(True)
        await interaction.edit_original_response(
            embed=embed("🔫 Buckshot", self.render("🟢 **FESTIM!** O bot sobreviveu.\n\n👤 Sua vez.")),
            view=self,
        )

    async def stop_game(self, interaction):
        if self.finished or self.busy or not self.player_turn:
            return
        if self.round < self.stop_after:
            await interaction.response.send_message(
                f"🛑 Ainda não dá pra parar. No modo **{BUCKSHOT_MODES[self.mode]['label']}**, você só pode parar a partir da **rodada {self.stop_after}**.",
                ephemeral=True,
            )
            return
        self.busy = True
        await interaction.response.edit_message(
            embed=embed("🔫 Buckshot", self.render("🛑 **Você decidiu parar.** Contagem do prêmio...")),
            view=self,
        )
        total = int(self.wager * self.multiplier)
        await self.finish(
            interaction, "win",
            f"🛑 Você parou na **rodada {self.round}** antes de arriscar mais.\n\n"
            f"💰 Você garantiu **{money(total, self.currency)}** ({self.multiplier:.2f}×).\n"
            f"❤️ Vidas: **{self.player_lives}/{self.max_player_lives}** • 🤖 Bot: **{self.bot_lives}/{self.max_bot_lives}**.", total,
        )

    @discord.ui.button(label="ITEM 1", style=discord.ButtonStyle.primary, emoji="🎒", custom_id="buckshot_item_1", row=0)
    async def item_1(self, interaction, button):
        await self.use_item(interaction, self.items[0])

    @discord.ui.button(label="ITEM 2", style=discord.ButtonStyle.primary, emoji="🎒", custom_id="buckshot_item_2", row=0)
    async def item_2(self, interaction, button):
        await self.use_item(interaction, self.items[1])

    @discord.ui.button(label="ITEM 3", style=discord.ButtonStyle.primary, emoji="🎒", custom_id="buckshot_item_3", row=0)
    async def item_3(self, interaction, button):
        await self.use_item(interaction, self.items[2])

    @discord.ui.button(label="PUXAR GATILHO", style=discord.ButtonStyle.danger, emoji="🔫", custom_id="buckshot_trigger", row=1)
    async def pull(self, interaction, button):
        await self.player_pull(interaction)

    @discord.ui.button(label="PARAR", style=discord.ButtonStyle.success, emoji="🛑", custom_id="buckshot_stop", row=1, disabled=True)
    async def stop(self, interaction, button):
        await self.stop_game(interaction)


class Arcade(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def start(self, ctx, game_cls, wager, game_kwargs=None):
        user = ctx.author if isinstance(ctx, commands.Context) else ctx.user
        guild_id = ctx.guild.id if isinstance(ctx, commands.Context) else ctx.guild_id
        row = await db.get_user(user.id, guild_id)
        currency, amount = parse_bet(wager, row)
        if amount is None or amount <= 0:
            msg = "❌ A aposta tem que ser maior que 0. Use CRW normalmente ou XP com `xp:100`."
            return await ctx.send(msg) if isinstance(ctx, commands.Context) else await ctx.response.send_message(msg, ephemeral=True)
        available = (sum(100 * i for i in range(1, max(1, int(row["level"])))) + int(row["xp"])) if currency == "XP" else int(row["bank"])
        if available < amount:
            label = "XP total" if currency == "XP" else "Banco"
            msg = f"❌ Você não tem **{money(amount, currency)}** disponível no seu **{label}**."
            if currency == "CRW":
                msg += f"\n🏦 Banco: **{money(row['bank'])}**\n💼 Carteira: **{money(row['balance'])}**"
            else:
                msg += f"\n⭐ XP total: **{money(available, 'XP')}**"
            return await ctx.send(msg) if isinstance(ctx, commands.Context) else await ctx.response.send_message(msg, ephemeral=True)
        if not await bet(user.id, guild_id, amount, currency):
            msg = "❌ Não consegui retirar sua aposta agora. Tenta de novo rapidinho."
            return await ctx.send(msg) if isinstance(ctx, commands.Context) else await ctx.response.send_message(msg, ephemeral=True)
        view = game_cls(user, amount, currency, **(game_kwargs or {}))
        view.guild_id = guild_id
        wallet_label = "Banco" if currency == "CRW" else "XP"
        description = f"🎟️ Aposta: **{money(amount, currency)}**\n📦 Retirada do **{wallet_label}**.\n\nBoa sorte 👀 Jackpot: **3× a aposta** quando a sorte grande cair.\n"
        if currency == "XP":
            description += "⭐ Esta rodada usa XP como aposta; ganhos de XP também respeitam o bônus 2× do dono/Booster.\n"
        if isinstance(view, BlackjackView): description += "\n" + view.text()
        elif isinstance(view, MinesView): description += f"\n💣 Bombas: **{view.bomb_count}/{view.CELLS}**\n" + view.render()
        elif isinstance(view, SlotsView): description += "\nPressione **GIRAR**."
        elif isinstance(view, CrashView): description += "\nPressione **Iniciar**."
        else: description += "\nEscolha uma opção abaixo."
        game_gifs = {
            RouletteView: "spin", SlotsView: "spin", BlackjackView: "think",
            CoinflipView: "spin", DiceView: "shake", CrashView: "shocked",
            MinesView: "think"
        }
        game_embed = embed(view_title(game_cls), description)
        await set_anime_gif(game_embed, game_gifs.get(game_cls, "happy"))
        if isinstance(ctx, commands.Context): await ctx.send(embed=game_embed, view=view)
        else: await ctx.response.send_message(embed=game_embed, view=view)

    @commands.command(name="arcade", aliases=["games", "jogos"])
    async def arcade(self, ctx):
        await ctx.send(embed=embed("🕹️ KIBOT ARCADE", "🎮 Bora brincar de apostar no Kibot kkkkk.\n\n`K! roleta valor` • `K! slots valor` • `K! blackjack valor` • `K! caraoucoroa valor` • `K! dados valor` • `K! crash valor` • `K! mines valor [bombas]` • `K! buckshot valor`\n\n💡 CRW usa o **Banco**. Para apostar XP, use `xp:100`, `xp100` ou `100xp`.\n🎰 **JACKPOT:** qualquer vitória pode virar jackpot e garantir **pelo menos 3× a aposta**, tanto em CRW quanto em XP; prêmios-base maiores não são reduzidos.\n\nTudo aqui é moeda/XP virtual do bot, sem grana de verdade. Não vai vender a alma pro Kibot não 😂"))

    @commands.command(name="roleta", aliases=["roulette"])
    async def roulette(self, ctx, wager: str): await self.start(ctx, RouletteView, wager)
    @commands.command(name="slots", aliases=["slot", "tigrinho", "tiger"])
    async def slots(self, ctx, wager: str): await self.start(ctx, SlotsView, wager)
    @commands.command(name="blackjack", aliases=["bj"])
    async def blackjack(self, ctx, wager: str): await self.start(ctx, BlackjackView, wager)
    @commands.command(name="caraoucoroa", aliases=["coinflip", "coroa"])
    async def coinflip(self, ctx, wager: str): await self.start(ctx, CoinflipView, wager)
    @commands.command(name="dados", aliases=["dice"])
    async def dice(self, ctx, wager: str): await self.start(ctx, DiceView, wager)
    @commands.command(name="crash", aliases=["rocket"])
    async def crash(self, ctx, wager: str): await self.start(ctx, CrashView, wager)
    @commands.command(name="mines", aliases=["mina"])
    async def mines(self, ctx, wager: str, bombas: int = MinesView.DEFAULT_BOMBS):
        if not MinesView.MIN_BOMBS <= bombas <= MinesView.MAX_BOMBS:
            return await ctx.send(f"❌ Escolha entre **{MinesView.MIN_BOMBS} e {MinesView.MAX_BOMBS} bombas** em 20 casas.")
        await self.start(ctx, MinesView, wager, game_kwargs={"bombs": bombas})

    @commands.command(name="buckshot", aliases=["buck", "roletarussa"])
    async def buckshot(self, ctx, wager: str):
        await self.start_buckshot(ctx, wager)

    async def start_buckshot(self, ctx, wager):
        user = ctx.author if isinstance(ctx, commands.Context) else ctx.user
        guild_id = ctx.guild.id if isinstance(ctx, commands.Context) else ctx.guild_id
        row = await db.get_user(user.id, guild_id)
        currency, amount = parse_bet(wager, row)
        if amount is None or amount <= 0:
            msg = "❌ A aposta tem que ser maior que 0 CRW, né kkkkk."
            return await ctx.send(msg) if isinstance(ctx, commands.Context) else await ctx.response.send_message(msg, ephemeral=True)
        available = (sum(100 * i for i in range(1, max(1, int(row["level"])))) + int(row["xp"])) if currency == "XP" else int(row["bank"])
        if available < amount:
            msg = f"❌ Você não tem **{money(amount, currency)}** disponível para essa aposta."
            return await ctx.send(msg) if isinstance(ctx, commands.Context) else await ctx.response.send_message(msg, ephemeral=True)
        if not await bet(user.id, guild_id, amount, currency):
            msg = "❌ Não consegui pegar sua aposta agora. Tenta de novo."
            return await ctx.send(msg) if isinstance(ctx, commands.Context) else await ctx.response.send_message(msg, ephemeral=True)

        async def choose_mode(interaction, mode):
            # O clique da dificuldade também precisa ser reconhecido em até 3s.
            await interaction.response.defer()
            view = BuckshotView(user, amount, mode, currency)
            view.guild_id = guild_id
            await interaction.edit_original_response(
                embed=embed("🔫 Buckshot", view.render("🎲 **Composição e 3 itens sorteados para esta partida.**\n\n🤖 **O BOT começa obrigatoriamente a primeira rodada.**")),
                view=view,
            )
            await view.bot_turn(interaction)

        mode_view = BuckshotModeView(user, amount, choose_mode)
        text = (
            f"🎟️ Aposta: **{money(amount, currency)}**\n📦 Aposta retirada do **{'Banco' if currency == 'CRW' else 'XP'}**.\n\n"
            "Escolha a dificuldade antes de começar.\n\n"
            "**Normal:** 6 câmaras • pode parar a partir da rodada 3\n"
            "**Difícil:** 8 câmaras • pode parar a partir da rodada 4\n"
            "**V4I S3 FUD3R!:** 16 câmaras • pode parar a partir da rodada 8\n\n"
            "🎲 A quantidade de balas verdadeiras e de festim é sorteada a cada partida.\n"
            "⏱️ Cada disparo tem **5 segundos** de espera.\n"
            "🤖 É **você contra o bot**: o **bot começa sempre**, e a vez muda conforme o resultado do disparo.\n"
            "🎒 No início, você recebe **3 itens aleatórios e únicos**."
        )
        buckshot_embed = embed("🔫 Buckshot", text)
        await set_anime_gif(buckshot_embed, "shoot")
        if isinstance(ctx, commands.Context): await ctx.send(embed=buckshot_embed, view=mode_view)
        else: await ctx.response.send_message(embed=buckshot_embed, view=mode_view)

    @app_commands.command(name="arcade", description="Abre a central de jogos do Kibot")
    async def arcade_slash(self, interaction): await self.start(interaction, RouletteView, 1) if False else await interaction.response.send_message(embed=embed("🕹️ KIBOT ARCADE", "Quer jogar? Usa `/roleta`, `/slots`, `/blackjack`, `/caraoucoroa`, `/dados`, `/crash`, `/mines` ou `/buckshot` e manda a quantidade de CRW (ex.: `10k`, `1m`, `2b`)."), ephemeral=True)

    @app_commands.command(name="roleta", description="Manda CRW na roleta e vê se a sorte ajuda")
    @app_commands.describe(aposta="Quanto de CRW você quer arriscar")
    async def roulette_slash(self, interaction, aposta: str): await self.start(interaction, RouletteView, aposta)
    @app_commands.command(name="slots", description="Gira os slots e tenta arrancar uns CRW")
    @app_commands.describe(aposta="Quanto de CRW você quer arriscar")
    async def slots_slash(self, interaction, aposta: str): await self.start(interaction, SlotsView, aposta)
    @app_commands.command(name="blackjack", description="Joga blackjack e tenta passar o carro no dealer")
    @app_commands.describe(aposta="Quanto de CRW você quer arriscar")
    async def blackjack_slash(self, interaction, aposta: str): await self.start(interaction, BlackjackView, aposta)
    @app_commands.command(name="caraoucoroa", description="Joga cara ou coroa valendo CRW")
    @app_commands.describe(aposta="Quanto de CRW você quer arriscar")
    async def coinflip_slash(self, interaction, aposta: str): await self.start(interaction, CoinflipView, aposta)
    @app_commands.command(name="dados", description="Rola os dados valendo CRW")
    @app_commands.describe(aposta="Quanto de CRW você quer arriscar")
    async def dice_slash(self, interaction, aposta: str): await self.start(interaction, DiceView, aposta)
    @app_commands.command(name="crash", description="Sobe o multiplicador e sai antes de explodir")
    @app_commands.describe(aposta="Quanto de CRW você quer arriscar")
    async def crash_slash(self, interaction, aposta: str): await self.start(interaction, CrashView, aposta)
    @app_commands.command(name="mines", description="Abre as casas e escolhe quantas bombas haverá na partida")
    @app_commands.describe(aposta="Quanto você quer arriscar (CRW ou xp:100)", bombas="Quantidade de bombas: 1 a 19")
    async def mines_slash(self, interaction, aposta: str, bombas: app_commands.Range[int, 1, 19] = MinesView.DEFAULT_BOMBS):
        await self.start(interaction, MinesView, aposta, game_kwargs={"bombs": bombas})

    @app_commands.command(name="buckshot", description="Joga Buckshot e tenta sobreviver à roleta russa")
    @app_commands.describe(aposta="Quanto de CRW você quer arriscar")
    async def buckshot_slash(self, interaction, aposta: str): await self.start_buckshot(interaction, aposta)


async def setup(bot): await bot.add_cog(Arcade(bot))
