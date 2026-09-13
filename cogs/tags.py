from cogs.embed_style import KibotEmbed
import time
import random
import re
import discord
from discord.ext import commands
from discord import app_commands
from database import db


# Tags nativas: funcionam automaticamente em qualquer canal sem precisar
# cadastrar manualmente em cada servidor. As respostas são aleatórias para
# o Kibot não parecer um papagaio preso em uma única fala.
BUILTIN_TAGS = {
    "kibot": [
        "🐦‍⬛ Chamou? Tô aqui. Que foi, criatura?",
        "🪶 Kibot na escuta. Pode falar.",
        "👀 Você fala meu nome e eu apareço. Conveniente, né?",
        "🐦‍⬛ Presente. Infelizmente para você.",
    ],
    "kiba": [
        "🪶 Chamou o Kiba? Tô ouvindo.",
        "👀 Kiba presente. Qual é a treta?",
        "🐦‍⬛ Fala, chefe.",
    ],
    "kibo": [
        "🤨 Kibo? Quase. Mas eu deixo passar.",
        "🐦‍⬛ Kibo foi convocado com sucesso.",
    ],
    "bot": [
        "🤖 Chamou o funcionário?",
        "📋 Bot trabalhando. Milagre registrado.",
        "🐦‍⬛ Eu tenho nome, sabia? É Kibot.",
    ],
    "robô": [
        "🤖 Robô é a sua máquina de lavar.",
        "🐦‍⬛ Tecnicamente, sim. Emocionalmente, não pergunte.",
    ],
    "robo": [
        "🤖 Robô é a sua máquina de lavar.",
        "🐦‍⬛ Tecnicamente, sim. Emocionalmente, não pergunte.",
    ],
    "máquina": [
        "⚙️ Máquina é teu pai. Eu sou uma entidade digital sofisticada.",
        "🤖 *Bip bop* — respeito à máquina, por favor.",
    ],
    "ia": [
        "🧠 IA? Sim. Onisciente? Aí você já está exagerando.",
        "🤖 Inteligência artificial, decisões questionáveis.",
    ],
    "chatgpt": [
        "👀 Você está procurando o concorrente errado.",
        "🐦‍⬛ ChatGPT? Aqui é Kibot, pô.",
    ],
    "crw": [
        "💰 Falou CRW, apareceu o fiscal da pobreza.",
        "🪙 Crowings: a unidade oficial de problemas financeiros do servidor.",
    ],
    "crowings": [
        "🪙 Crowings detectados. Proteja sua carteira.",
        "💰 CRW é temporário. A dívida é eterna.",
    ],
    "dinheiro": [
        "💸 Dinheiro? Eu também queria.",
        "🪙 Falar de dinheiro não faz ele aparecer, infelizmente.",
    ],
    "pobre": [
        "💸 Pobreza detectada. Consulte seu saldo antes que seja tarde.",
        "📉 Seu patrimônio pediu demissão.",
    ],
    "rico": [
        "🤑 Rico? Então paga um lanche pra todo mundo.",
        "💰 Calma, Elon Musk do Discord.",
    ],
    "dinheiro sujo": [
        "🕳️ Dinheiro Sujo detectado. Já sabe onde levar: `K! crime lavagem`.",
        "🕳️ O dinheiro está sujo. A consciência também pode estar.",
    ],
    "lavagem": [
        "🧼 Lavagem? Só não esquece que o Kibot cobra taxa.",
        "🕳️ Quer lavar CRW? Primeiro precisa ter o que lavar.",
    ],
    "crime": [
        "🚨 Crime detectado. Eu não vi nada.",
        "🕳️ Se for cometer crime, pelo menos leia as regras do submundo.",
    ],
    "cassino": [
        "🎰 A casa sempre tem uma opinião muito forte sobre sua sorte.",
        "🎲 Cassino aberto. Responsabilidade fechada.",
    ],
    "aposta": [
        "🎰 Vai apostar? Lembra: o servidor agradece sua contribuição.",
        "🎲 Apostador detectado. A economia está tremendo.",
    ],
    "apostar": [
        "🎰 Apostar é fácil. Recuperar o CRW é a parte artística.",
        "🤑 Vai em frente. Eu adoro quando a estatística trabalha pra mim.",
    ],
    "buckshot": [
        "🔫🎲 Buckshot? Três vidas, oito itens e decisões ruins.",
        "🔫 A roleta russa ganhou interface de Discord. Excelente ideia.",
    ],
    "jackpot": [
        "🎰 JACKPOT! Ou talvez você só tenha falado a palavra. Tenta `K! cassino`.",
        "🤑 Alguém sentiu cheiro de CRW.",
    ],
    "azar": [
        "🍀 O azar não é permanente. Seu saldo talvez seja.",
        "🎲 Se o dado te odeia, pelo menos ele é consistente.",
    ],
    "sorte": [
        "🍀 Boa sorte. Você vai precisar.",
        "🎲 Sorte é só estatística usando perfume.",
    ],
    "socorro": [
        "🚨 Socorro registrado. Prazo de atendimento: quando der.",
        "🐦‍⬛ Calma. Eu também não sei o que está acontecendo.",
    ],
    "fudeu": [
        "🚨 Confirmado: fudeu.",
        "🐦‍⬛ Diagnóstico técnico: deu ruim pra caralho.",
    ],
    "ferrou": [
        "🚨 Sistema confirma: ferrou.",
        "📉 Situação classificada como 'não ideal'.",
    ],
    "caos": [
        "😈 Finalmente alguém falou minha língua.",
        "🔥 Caos? Onde? Eu não vi nada.",
    ],
    "inferno": [
        "🔥 O inferno ligou. Disse que está lotado.",
        "😈 Se você está procurando o inferno, olha o histórico do servidor.",
    ],
    "deus": [
        "🙏 Deus? Não. Mas tenho permissão de administrador em alguns lugares.",
        "👀 Se Deus estiver vendo isso, eu não tenho envolvimento.",
    ],
    "diabo": [
        "😈 Chamou o diabo? Ele está ocupado cobrando juros.",
        "🔥 O RH do inferno recebeu sua mensagem.",
    ],
    "regras": [
        "📜 Regras? `K! ajuda` e procura a parte que você provavelmente vai ignorar.",
        "👀 Leia as regras. É mais rápido do que discutir com a moderação.",
    ],
    "staff": [
        "🛡️ A staff foi invocada. Boa sorte a todos os envolvidos.",
        "📢 Staff detectada. Comportem-se por pelo menos 30 segundos.",
    ],
    "moderador": [
        "🛡️ Moderador detectado. Hora de fingir que estava lendo as regras.",
        "👀 A moderação chegou. Guardem os crimes.",
    ],
    "admin": [
        "👑 Admin detectado. Agora todo mundo vira santo.",
        "🛡️ Chamaram a autoridade máxima do servidor.",
    ],
    "ticket": [
        "🎫 Ticket? Abre um e explica direito, criatura.",
        "🎫 O suporte recebeu o chamado. Provavelmente.",
    ],
    "suporte": [
        "🛠️ Suporte ativado. Primeiro passo: respira.",
        "🎫 Quer suporte? Abre um ticket e evita explicar por telepatia.",
    ],
    "bug": [
        "🐛 Bug detectado. Se eu responder 'funciona na minha máquina', você me perdoa?",
        "🔧 Anotado: mais um problema para a coleção.",
    ],
    "erro": [
        "⚠️ Erro detectado. Pelo menos não fui eu... provavelmente.",
        "🐦‍⬛ Sistema: 'deu ruim'. Diagnóstico avançado concluído.",
    ],
    "ajuda": [
        "📚 Precisa de ajuda? `K! ajuda` é literalmente meu trabalho.",
        "🐦‍⬛ Quer comandos? Manda `K! ajuda`.",
    ],
    "chefe": [
        "👑 Chamou o chefe? Quem te deu essa liberdade?",
        "🪶 Chefe é uma palavra forte. Eu prefiro 'entidade superior'.",
    ],
    "patrão": [
        "💼 Patrão? Finalmente reconhecimento.",
        "👑 Pode falar, funcionário.",
    ],
    "entidade": [
        "👁️ Você finalmente percebeu o que eu sou.",
        "🐦‍⬛ Entidade digital em horário de expediente.",
    ],
    "criador": [
        "👀 O criador foi mencionado. Isso nunca termina bem.",
        "🪶 Digamos que meu criador tem algumas ideias questionáveis.",
    ],
}

class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldowns = {}
        self._tag_cache = {}
        self._tag_cache_at = {}

    async def _reply(self, ctx, text, ephemeral=False):
        if isinstance(ctx, discord.Interaction):
            if ctx.response.is_done():
                return await ctx.followup.send(text, ephemeral=ephemeral)
            return await ctx.response.send_message(text, ephemeral=ephemeral)
        return await ctx.send(text)

    @app_commands.command(name="tag", description="Cria, remove e lista tags automáticas")
    @app_commands.describe(acao="criar, remover ou listar", nome="Nome da tag", resposta="Resposta automática da tag")
    async def tag(self, interaction, acao: str, nome: str = None, resposta: str = None):
        if not interaction.guild:
            return await self._reply(interaction, "❌ Esse comando só funciona em servidor.", True)
        if not interaction.user.guild_permissions.manage_guild:
            return await self._reply(interaction, "🚫 Você precisa de **Gerenciar Servidor** para mexer nas tags.", True)
        acao = acao.lower().strip()
        if acao == "criar": return await self._create(interaction, nome, resposta)
        if acao in ("remover", "deletar", "apagar"): return await self._delete(interaction, nome)
        if acao == "listar": return await self._list(interaction)
        return await self._reply(interaction, "❌ Ação inválida. Use `criar`, `remover` ou `listar`.", True)

    @commands.command(name="tag", aliases=["tags"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def p_tag(self, ctx, acao: str = "listar", nome: str = None, *, resposta: str = None):
        acao = acao.lower().strip()
        if acao == "criar": return await self._create(ctx, nome, resposta)
        if acao in ("remover", "deletar", "apagar"): return await self._delete(ctx, nome)
        if acao == "listar": return await self._list(ctx)
        await ctx.send("❌ Ação inválida. Use `K! tag criar nome resposta`, `K! tag remover nome` ou `K! tag listar`.")

    async def _create(self, ctx, nome, resposta):
        if not nome or not resposta:
            return await self._reply(ctx, "❌ Use: `K! tag criar nome resposta`.", True if isinstance(ctx, discord.Interaction) else False)
        nome = " ".join(nome.strip().lower().split())[:50]
        resposta = resposta.strip()[:1900]
        if len(nome) < 1 or not resposta:
            return await self._reply(ctx, "❌ A tag e a resposta precisam existir.", True if isinstance(ctx, discord.Interaction) else False)
        await db.upsert_tag(ctx.guild.id, nome, resposta)
        self._invalidate_cache(ctx.guild.id)
        return await self._reply(ctx, f"🏷️ Tag **{nome}** salva! Quando alguém mencionar `{nome}`, eu respondo automaticamente. 🐦‍⬛", True if isinstance(ctx, discord.Interaction) else False)

    async def _delete(self, ctx, nome):
        if not nome:
            return await self._reply(ctx, "❌ Diga qual tag remover.", True if isinstance(ctx, discord.Interaction) else False)
        ok = await db.delete_tag(ctx.guild.id, nome.strip().lower())
        self._invalidate_cache(ctx.guild.id)
        return await self._reply(ctx, "🗑️ Tag removida." if ok else "❌ Essa tag não existe.", True if isinstance(ctx, discord.Interaction) else False)

    async def _list(self, ctx):
        rows = await db.get_tags(ctx.guild.id)
        if not rows:
            return await self._reply(ctx, "🏷️ Nenhuma tag automática configurada ainda.", True if isinstance(ctx, discord.Interaction) else False)
        lines = [f"• `{r['name']}` → {r['response'][:120]}" for r in rows]
        e = KibotEmbed(title="🏷️ Tags automáticas", description="\n".join(lines), color=discord.Color.gold())
        return await self._send_embed(ctx, e)

    async def _send_embed(self, ctx, embed):
        if isinstance(ctx, discord.Interaction):
            return await ctx.response.send_message(embed=embed, ephemeral=True)
        return await ctx.send(embed=embed)

    async def _get_all_tags(self, guild_id):
        # Cache curto evita uma consulta SQLite a cada mensagem do servidor.
        now = time.monotonic()
        if guild_id in self._tag_cache and now - self._tag_cache_at.get(guild_id, 0) < 30:
            return self._tag_cache[guild_id]
        rows = await db.get_tags(guild_id)
        custom = {str(r["name"]).lower(): {"id": r["id"], "name": r["name"], "responses": [r["response"]]} for r in rows}
        # Tag cadastrada pelo servidor substitui a resposta nativa de mesmo nome.
        merged = {name: {"id": f"builtin:{name}", "name": name, "responses": responses} for name, responses in BUILTIN_TAGS.items()}
        merged.update(custom)
        self._tag_cache[guild_id] = list(merged.values())
        self._tag_cache_at[guild_id] = now
        return self._tag_cache[guild_id]

    def _invalidate_cache(self, guild_id):
        self._tag_cache.pop(guild_id, None)
        self._tag_cache_at.pop(guild_id, None)

    # As tags automáticas ficam desativadas para não disputar respostas com a IA do Kibot.
    # O sistema de criação/listagem continua no código para preservar compatibilidade,
    # mas nenhuma tag dispara resposta sozinha.

async def setup(bot):
    await bot.add_cog(Tags(bot))
