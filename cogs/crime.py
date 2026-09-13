"""Sistema criminal expandido do Kibot.
Tudo é fictício e usa somente CRW virtual; não fornece instruções de crimes reais.
"""
from cogs.embed_style import KibotEmbed
import random
import time
import discord
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.economy import format_money

# Cada atividade tem progressão, risco, investimento e retorno. Os detalhes são
# deliberadamente abstratos para manter o sistema como mecânica de jogo.
CRIMES = {
    # Rua
    "olheiro": dict(name="Olheiro", category="Rua", level=1, cost=0, min=80, max=180, rep=25, cooldown=1800, chance=.90, emoji="👀", desc="Coleta informação fictícia para o submundo."),
    "furto": dict(name="Furto", category="Rua", level=2, cost=30, min=120, max=260, rep=30, cooldown=2400, chance=.82, emoji="🥷", desc="Pequeno crime de oportunidade, totalmente virtual."),
    "estelionato": dict(name="Estelionato", category="Fraudes", level=3, cost=70, min=180, max=420, rep=45, cooldown=3000, chance=.78, emoji="🎭", desc="Aplica um golpe fictício e tenta sair no lucro."),
    "assalto": dict(name="Assalto", category="Rua", level=4, cost=100, min=260, max=600, rep=65, cooldown=4200, chance=.74, emoji="🕶️", desc="Operação de alto risco representada apenas por uma rolagem."),
    "fraude_digital": dict(name="Fraude Digital", category="Fraudes", level=5, cost=120, min=300, max=720, rep=70, cooldown=4500, chance=.72, emoji="💻", desc="Golpe digital abstrato, sem métodos reais."),
    "roubo_de_veiculos": dict(name="Roubo de Veículos", category="Veículos", level=6, cost=180, min=420, max=900, rep=85, cooldown=5400, chance=.68, emoji="🚗", desc="Rouba um veículo fictício e tenta desaparecer."),

    # Mercado ilegal
    "mercadoria_roubada": dict(name="Mercadoria Roubada", category="Mercado", level=7, cost=220, min=500, max=1050, rep=90, cooldown=6000, chance=.70, emoji="📦", desc="Compra e revende um lote de procedência duvidosa."),
    "mercado_negro": dict(name="Mercado Negro", category="Mercado", level=8, cost=250, min=550, max=1200, rep=105, cooldown=6600, chance=.68, emoji="🧳", desc="Negocia itens fictícios no mercado clandestino."),
    "trafico": dict(name="Tráfico", category="Mercado", level=9, cost=300, min=650, max=1350, rep=120, cooldown=7200, chance=.65, emoji="💊", desc="Movimenta mercadoria ilícita fictícia."),
    "producao_quimicos": dict(name="Produção de Químicos", category="Mercado", level=10, cost=350, min=750, max=1500, rep=130, cooldown=7800, chance=.62, emoji="🧪", desc="Produção de substâncias fictícias; nenhuma receita real é envolvida."),
    "venda_armas": dict(name="Venda de Armas", category="Mercado", level=11, cost=400, min=850, max=1750, rep=145, cooldown=8400, chance=.60, emoji="🔫", desc="Mercado de armas apenas como mecânica abstrata de RPG."),
    "contrabando": dict(name="Contrabando", category="Mercado", level=12, cost=450, min=950, max=2000, rep=160, cooldown=9000, chance=.62, emoji="🚚", desc="Transporta uma carga ilegal fictícia."),
    "falsificacao": dict(name="Falsificação", category="Clandestino", level=13, cost=300, min=700, max=1600, rep=135, cooldown=7800, chance=.63, emoji="🪪", desc="Cria documentos fictícios para uma operação do jogo."),
    "desmanche": dict(name="Desmanche", category="Veículos", level=14, cost=500, min=1100, max=2300, rep=180, cooldown=9600, chance=.58, emoji="🔧", desc="Converte um veículo fictício em peças virtuais."),

    # Serviços e poder
    "servicos_adultos": dict(name="Serviços Adultos", category="Clandestino", level=8, cost=180, min=450, max=1000, rep=80, cooldown=6000, chance=.75, emoji="💋", desc="Atividade adulta fictícia representada somente por economia e risco."),
    "agenciamento": dict(name="Agenciamento", category="Clandestino", level=12, cost=350, min=850, max=1800, rep=120, cooldown=8400, chance=.67, emoji="🤝", desc="Administra uma rede fictícia de serviços clandestinos."),
    "extorsao": dict(name="Extorsão", category="Poder", level=14, cost=400, min=1000, max=2200, rep=175, cooldown=9000, chance=.57, emoji="😈", desc="Pressiona um alvo fictício usando reputação criminal."),
    "assassinato_aluguel": dict(name="Assassinato de Aluguel", category="Poder", level=16, cost=650, min=1500, max=3200, rep=220, cooldown=10800, chance=.52, emoji="🔪", desc="Missão criminal fictícia de altíssimo risco, sem detalhes reais."),
    "informante": dict(name="Informante", category="Poder", level=10, cost=160, min=500, max=1200, rep=95, cooldown=6000, chance=.80, emoji="🕵️", desc="Vende informação fictícia para ganhar vantagem no submundo."),

    # Finanças
    "agiotagem": dict(name="Agiotagem", category="Finanças", level=9, cost=250, min=500, max=1250, rep=100, cooldown=7200, chance=.66, emoji="💸", desc="Empresta CRW virtual e tenta cobrar o retorno."),
    "apostas_clandestinas": dict(name="Apostas Clandestinas", category="Finanças", level=10, cost=300, min=500, max=1800, rep=90, cooldown=7200, chance=.55, emoji="🎰", desc="Organiza uma banca fictícia e arrisca o capital."),
    "lavagem": dict(name="Lavagem de Dinheiro", category="Finanças", level=15, cost=700, min=1200, max=2800, rep=190, cooldown=10800, chance=.64, emoji="💰", desc="Converte parte de uma operação fictícia em CRW utilizável, com taxa de risco."),
    "empresa_fachada": dict(name="Empresa de Fachada", category="Finanças", level=17, cost=900, min=1800, max=3800, rep=240, cooldown=14400, chance=.60, emoji="🏢", desc="Usa um negócio fictício como cobertura econômica."),

    # Corrupção
    "suborno": dict(name="Suborno de Autoridades", category="Corrupção", level=6, cost=250, min=0, max=0, rep=35, cooldown=7200, chance=1.0, emoji="👮", desc="Compra um bônus temporário de chance para a próxima operação."),
    "compra_favores": dict(name="Compra de Favores", category="Corrupção", level=13, cost=600, min=0, max=0, rep=80, cooldown=10800, chance=1.0, emoji="🤝", desc="Garante uma pequena proteção narrativa por tempo limitado."),

    # Chefia
    "chefia": dict(name="Chefia do Submundo", category="Chefia", level=20, cost=1200, min=2500, max=5500, rep=300, cooldown=18000, chance=.55, emoji="👑", desc="Coordena uma grande operação e fica com a maior fatia."),
}

CRIME_RANKS = [
    (0, "Civil suspeito"), (100, "Olheiro"), (300, "Criminoso"),
    (700, "Operador"), (1500, "Chefão"), (3000, "Lenda do Submundo"),
    (6000, "Mito Criminal"),
]

CATEGORY_EMOJI = {"Rua":"🥷", "Fraudes":"🎭", "Veículos":"🚗", "Mercado":"📦", "Clandestino":"🕶️", "Poder":"😈", "Finanças":"💰", "Corrupção":"👮", "Chefia":"👑"}

def crime_rank(rep):
    rank = CRIME_RANKS[0][1]
    for threshold, name in CRIME_RANKS:
        if rep >= threshold:
            rank = name
    return rank

def crime_embed(title, description, color=0x6B1E2B):
    e = KibotEmbed(title=title, description=description, color=color)
    e.set_footer(text="Kibot • Submundo fictício • CRW virtual • Sem instruções de crime real")
    return e

class Crime(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def _send(self, ctx, content=None, embed=None, ephemeral=False):
        if isinstance(ctx, discord.Interaction):
            if ctx.response.is_done():
                return await ctx.followup.send(content=content, embed=embed, ephemeral=ephemeral)
            return await ctx.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
        return await ctx.send(content=content, embed=embed)

    def _key(self, text):
        return text.lower().strip().replace(" ", "_").replace("-", "_")

    def _boost(self, row):
        until = int(row["crime_boost_until"] or 0) if "crime_boost_until" in row.keys() else 0
        amount = int(row["crime_boost_amount"] or 0) if "crime_boost_amount" in row.keys() else 0
        if until > int(time.time()) and amount > 0:
            return amount, until
        return 0, 0

    async def _status(self, ctx):
        user = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        row = await db.get_user(user.id, ctx.guild.id)
        boost, until = self._boost(row)
        e = crime_embed("🕶️ CAMINHO DO CRIME", f"**Nível:** {row['level']}\n**Reputação Criminal:** {row['crime_rep']}\n**Patente:** {crime_rank(row['crime_rep'])}\n**🕳️ Dinheiro Sujo:** {format_money(row['dirty_money'])}")
        if boost:
            e.add_field(name="👮 Proteção ativa", value=f"**+{boost}%** de chance na próxima operação válida • expira em <t:{until}:R>", inline=False)
        for cat in ["Rua","Fraudes","Veículos","Mercado","Clandestino","Poder","Finanças","Corrupção","Chefia"]:
            items=[]
            for key,c in CRIMES.items():
                if c["category"] != cat: continue
                unlocked = row["level"] >= c["level"]
                mark = "🔓" if unlocked else "🔒"
                if c["min"]:
                    reward = f"{format_money(c['min'])}–{format_money(c['max'])}"
                else:
                    reward = "BÔNUS"
                items.append(f"{mark} **{c['emoji']} {c['name']}** — Lv.{c['level']} • {reward}\n`{key}` — {c['desc']}")
            if items: e.add_field(name=f"{CATEGORY_EMOJI[cat]} {cat}", value="\n\n".join(items), inline=False)
        e.add_field(name="Como usar", value="`K! crime <operação>` ou `/operacao <tipo>`\nEx.: `K! crime assalto`", inline=False)
        await self._send(ctx, embed=e, ephemeral=isinstance(ctx, discord.Interaction))

    @commands.command(name="crime", aliases=["crimes", "submundo"])
    async def p_crime(self, ctx, operacao: str = None):
        if not operacao: return await self._status(ctx)
        await self._do_crime(ctx, operacao)

    @app_commands.command(name="crime", description="Mostra o submundo e as operações desbloqueadas")
    async def crime_slash(self, interaction): await self._status(interaction)

    @app_commands.command(name="operacao", description="Executa uma operação criminal fictícia")
    @app_commands.describe(tipo="Nome da operação, como assalto, tráfico, lavagem ou suborno")
    async def operation_slash(self, interaction, tipo: str): await self._do_crime(interaction, tipo)

    async def _do_crime(self, ctx, operacao):
        user = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        key = self._key(operacao)
        aliases = {"drogas":"trafico", "trafico_de_drogas":"trafico", "armas":"venda_armas", "venda_de_armas":"venda_armas", "prostituicao":"servicos_adultos", "servicos_adultos":"servicos_adultos", "desmanche_de_carros":"desmanche", "assassino_de_aluguel":"assassinato_aluguel", "lavagem_de_dinheiro":"lavagem", "empresa_de_fachada":"empresa_fachada", "apostas":"apostas_clandestinas", "falsificacao_de_documentos":"falsificacao"}
        key = aliases.get(key, key)
        c = CRIMES.get(key)
        if not c:
            return await self._send(ctx, "❌ Operação desconhecida. Use `K! crime` para abrir o catálogo do submundo.", ephemeral=isinstance(ctx, discord.Interaction))
        row = await db.get_user(user.id, ctx.guild.id)
        if row["level"] < c["level"]:
            return await self._send(ctx, f"🔒 **{c['name']}** libera no **nível {c['level']}**. Você está no **nível {row['level']}**.", ephemeral=isinstance(ctx, discord.Interaction))
        elapsed = int(time.time()) - int(row["last_crime"] or 0)
        if elapsed < c["cooldown"]:
            remain = c["cooldown"] - elapsed
            return await self._send(ctx, f"🕰️ O submundo está em cooldown. Aguarde **{remain//60}m {remain%60}s**.", ephemeral=isinstance(ctx, discord.Interaction))

        # Operações de corrupção: compram vantagem para a próxima operação.
        if key in ("suborno", "compra_favores"):
            if row["balance"] < c["cost"]:
                return await self._send(ctx, f"💸 Você precisa de **{format_money(c['cost'])}** para essa operação.", ephemeral=isinstance(ctx, discord.Interaction))
            boost = 15 if key == "suborno" else 22
            duration = 2 * 3600 if key == "suborno" else 3 * 3600
            await db.update_balance(user.id, ctx.guild.id, -c["cost"])
            await db.add_crime_rep(user.id, ctx.guild.id, c["rep"])
            await db.set_crime_boost(user.id, ctx.guild.id, boost, int(time.time()) + duration)
            await db.set_last_crime(user.id, ctx.guild.id)
            return await self._send(ctx, embed=crime_embed("👮 FAVORECIMENTO CONSEGUIDO", f"Você gastou **{format_money(c['cost'])}**.\n\n🎯 Próxima operação: **+{boost}% de chance**\n⏳ Duração: **{duration//3600}h**\n🕶️ Reputação: **+{c['rep']}**", 0x8A6D1D))

        boost, _ = self._boost(row)
        chance = min(.95, c["chance"] + boost / 100)

        # Lavagem usa exclusivamente Dinheiro Sujo. O valor convertido é
        # fictício e fica dentro da economia do bot: uma taxa fixa é perdida
        # e o restante vira CRW limpo na carteira.
        if key == "lavagem":
            dirty = int(row["dirty_money"] or 0)
            minimum = int(c["min"])
            fee = int(c["cost"])
            if dirty < minimum:
                return await self._send(ctx, f"🧼 Você precisa de pelo menos **{format_money(minimum)}** em **Dinheiro Sujo** para iniciar a lavagem.\n\n🕳️ Disponível: **{format_money(dirty)}**", ephemeral=isinstance(ctx, discord.Interaction))
            await db.set_last_crime(user.id, ctx.guild.id)
            if boost:
                await db.clear_crime_boost(user.id, ctx.guild.id)
            if random.random() < chance:
                upper = min(int(c["max"]), dirty)
                amount = random.randint(minimum, upper)
                if amount <= fee:
                    amount = min(upper, fee + 1)
                ok, clean = await db.launder_dirty_money(user.id, ctx.guild.id, amount, fee)
                if not ok:
                    return await self._send(ctx, "❌ A operação de lavagem não conseguiu concluir a conversão. Tente novamente.", ephemeral=isinstance(ctx, discord.Interaction))
                await db.add_crime_rep(user.id, ctx.guild.id, c["rep"])
                new_rep = int(row["crime_rep"]) + c["rep"]
                return await self._send(ctx, embed=crime_embed("🧼 💰 LAVAGEM CONCLUÍDA", f"Uma operação fictícia foi concluída.\n\n🕳️ Dinheiro Sujo processado: **{format_money(amount)}**\n💸 Taxa da operação: **{format_money(fee)}**\n💵 CRW limpo recebido: **{format_money(clean)}**\n📈 Reputação: **+{c['rep']}**\n👑 Patente: **{crime_rank(new_rep)}**", 0x2E8B57))
            # Em caso de falha, a taxa é perdida em Dinheiro Sujo.
            await db.spend_dirty_money(user.id, ctx.guild.id, min(fee, dirty))
            return await self._send(ctx, embed=crime_embed("🔴 🧼 LAVAGEM FRACASSOU", f"A operação fictícia falhou.\n\n🕳️ Taxa perdida em Dinheiro Sujo: **{format_money(min(fee, dirty))}**\n🎯 Chance usada: **{chance*100:.0f}%**\n😬 Nenhuma reputação foi ganha.", 0x9B2C2C))

        if row["balance"] < c["cost"]:
            return await self._send(ctx, f"💸 Você precisa de **{format_money(c['cost'])}** de capital para iniciar **{c['name']}**.", ephemeral=isinstance(ctx, discord.Interaction))
        await db.set_last_crime(user.id, ctx.guild.id)
        if boost:
            await db.clear_crime_boost(user.id, ctx.guild.id)
        await db.update_balance(user.id, ctx.guild.id, -c["cost"])
        success = random.random() < chance
        if success:
            ganho = random.randint(c["min"], c["max"]) + int(row["crime_rep"]) // 12
            await db.add_dirty_money(user.id, ctx.guild.id, ganho)
            await db.add_crime_rep(user.id, ctx.guild.id, c["rep"])
            new_rep = int(row["crime_rep"]) + c["rep"]
            e = crime_embed(f"🟢 {c['emoji']} OPERAÇÃO CONCLUÍDA", f"**{c['name']}** deu certo.\n\n🕳️ Dinheiro Sujo recebido: **{format_money(ganho)}**\n💸 Investimento em CRW limpo: **{format_money(c['cost'])}**\n🎯 Chance usada: **{chance*100:.0f}%**\n🕶️ Reputação: **+{c['rep']}**\n👑 Patente: **{crime_rank(new_rep)}**\n\n🧼 Use **`K! crime lavagem`** para tentar converter parte dele em CRW limpo.", 0x238B45)
        else:
            # Uma parte do investimento é perdida e o restante permanece na carteira.
            prejuizo = max(20, c["cost"] // 2 + random.randint(0, max(1, c["cost"] // 3)))
            # Como o custo inteiro já foi debitado, devolvemos a parte não perdida.
            devolucao = max(0, c["cost"] - prejuizo)
            if devolucao: await db.update_balance(user.id, ctx.guild.id, devolucao)
            e = crime_embed(f"🔴 {c['emoji']} OPERAÇÃO FRACASSOU", f"**{c['name']}** deu errado.\n\n💸 Prejuízo líquido: **{format_money(prejuizo)}**\n🎯 Chance usada: **{chance*100:.0f}%**\n😬 Reputação: nenhuma ganha desta vez.", 0x9B2C2C)
        crime_gif = "run" if key in {"assalto", "roubo", "furto", "sequestro", "desmanche"} else ("shoot" if key in {"assassinato_aluguel", "venda_armas"} else "smug")
        await set_anime_gif(e, crime_gif)
        await self._send(ctx, embed=e)

async def setup(bot): await bot.add_cog(Crime(bot))
