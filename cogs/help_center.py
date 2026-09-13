"""Central de ajuda interativa do Kibot.
Uma única mensagem/embed é atualizada pelos componentes da View.
"""
from cogs.embed_style import KibotEmbed
import discord
import config

PAGES = {
    "inicio": {
        "title": "🐦 Kibot — Central de Comandos",
        "description": (
            "Uma central só, sem mural de embeds. Escolha uma categoria abaixo para trocar de página.\n\n"
            f"Prefixo: `{config.PREFIX}` • Slash: `/`\n"
            f"Comando rápido: `{config.PREFIX}ajuda`"
        ),
        "fields": [
            ("📚 Começando", f"`{config.PREFIX}tutorial` (`tuto`, `iniciante`, `começar`) — tutorial interativo\n`/tutorial` — mesma função via slash", False),
            ("💡 Como ler", "Comandos entre parênteses são aliases. Argumentos aparecem depois do nome do comando.", False),
            ("🧭 Navegação", "Use o seletor para abrir uma categoria. Os botões ◀️ ▶️ também mudam de página.", False),
        ],
    },
    "economia": {
        "title": "💰 Kibot — Economia",
        "description": "Tudo que mexe com CRW, empregos, empresas, loja e Fichas Corvo.",
        "fields": [
            ("💰 Carteira e CRW", "`K! saldo` (`bal`, `balance`)\n`K! daily` (`day`)\n`K! trabalhar` (`work`)\n`K! trabalhos` (`jobs`, `empregos`)\n`K! escolher_trabalho ID` (`escolhertrabalho`, `escolherjob`)\n`K! transferir @membro valor` (`pay`, `give`)\n`K! depositar valor` (`dep`)\n`K! sacar valor` (`withdraw`, `wd`)\n`K! ranking` (`rank`, `top`)", False),
            ("🏢 Empresas", "`K! empresa` (`business`, `negocio`)\n`K! criar_empresa` (`criarnempresa`, `abrirempresa`)\n`K! lucro_empresa` (`lucro`, `empresa_lucro`)\n`K! vender_empresa` (`venderempresa`)", False),
            ("🛍️ Loja", "`K! loja` (`shop`)\n`K! comprar ID` (`buy`)", True),
            ("🐦‍⬛ Fichas Corvo", "`K! fichas` (`corvo`, `crowchips`)\n`K! ranking_fichas` (`rankfichas`, `topfichas`)\n`K! loja_corvo` (`corvoloja`, `fichasloja`)\n`K! comprar_corvo ID` (`buycorvo`, `comprarficha`)", True),
            ("⚡ Slash", "Também existem `/saldo`, `/daily`, `/trabalhar`, `/trabalhos`, `/escolher_trabalho`, `/roubar`, `/transferir`, `/depositar`, `/sacar`, `/ranking`, `/empresa`, `/criar_empresa`, `/lucro_empresa`, `/vender_empresa` e os comandos de loja.", False),
        ],
    },
    "crime": {
        "title": "🕶️ Kibot — Submundo",
        "description": "A economia criminal fictícia do Kibot. Tudo usa CRW virtual e mecânicas de RPG.",
        "fields": [
            ("🕶️ Central", "`K! crime` (`crimes`, `submundo`) — abre o catálogo interativo do submundo\n`/crime` — consulta o submundo\n`/operacao tipo` — executa uma operação", False),
            ("🥷 Rua / Fraudes", "`K! crime furto` • `assalto` • `estelionato` • `fraude_digital` • `roubo_veiculos`\n`K! crime falsificacao` • `extorsao`", False),
            ("📦 Mercado ilegal", "`K! crime trafico` • `producao_quimicos` • `venda_armas` • `contrabando` • `mercadoria_roubada` • `desmanche`", False),
            ("🕶️ Serviços clandestinos", "`K! crime servicos_adultos` (`prostituicao`) • `assassinato_aluguel` • `informante`", False),
            ("💰 Finanças / Corrupção", "`K! crime agiotagem` • `apostas_clandestinas` • `lavagem` • `empresa_fachada`\n`K! crime suborno` • `compra_favores`", False),
            ("👑 Progressão", "Reputação criminal libera patentes e operações. Use `K! crime` para ver nível, reputação, bônus e operações desbloqueadas.", False),
        ],
    },
    "rpg": {
        "title": "🎲 Kibot — RPG & Diversão",
        "description": "Dados, testes, brincadeiras e comandos sociais.",
        "fields": [
            ("🎲 Dados", "`K! dado [expressão]` (`d`, `roll`, `rolar`) — ex.: `K! d d20+5`\nTambém aceita expressões como `2d20kh1`, `4d6dl1` e repetições\n`K! coc 65` (`cthulhu`, `percentil`)", False),
            ("🎭 Diversão", "`K! 8ball pergunta` (`bola`, `8b`)\n`K! moeda` (`coin`, `flip`)\n`K! ship @a @b` (`compat`, `shipar`)\n`K! avatar [@membro]` (`av`, `pfp`)\n`K! enquete pergunta` (`poll`, `votar`)", False),
            ("🧰 Bicos", "`K! bico` (`bicos`)\n`K! bico número` — aceita um bico\n`K! bico status [@membro]` — andamento\nSlash: `/bicos`, `/bico`, `/bico_status`", False),
            ("💤 AFK", "`K! afk [motivo]` (`ausente`) — ativa/desativa o AFK e informa quando alguém menciona você.", False),
        ],
    },
    "dados": {
        "title": "🌐 Kibot — Dados Recentes",
        "description": "Consultas externas para informação atual: clima, futebol e notícias.",
        "fields": [
            ("🌤️ Clima", "`K! clima São Paulo` • `/clima` — usa Open-Meteo e não exige chave.", False),
            ("⚽ Futebol", "`K! futebol` • `/futebol` — jogos de hoje das competições configuradas.", False),
            ("📰 Notícias", "`K! noticias` • `K! noticias tecnologia` • `/noticias` — manchetes ou busca por tema.", False),
            ("🧠 IA", "Ao perguntar ao Kibot sobre clima, jogos ou notícias, ele tenta buscar dados recentes automaticamente antes de responder.", False),
            ("🔑 Configuração", "`FOOTBALL_DATA_API_KEY` e `GNEWS_API_KEY` ficam no `.env`. O clima não precisa de chave.", False),
        ],
    },
    "arcade": {
        "title": "🎮 Kibot — Arcade",
        "description": "Jogos que apostam CRW virtual.",
        "fields": [
            ("🎮 Central", "`K! arcade` (`games`, `jogos`)", False),
            ("🎰 Jogos", "`K! roleta valor` (`roulette`)\n`K! slots valor` (`slot`, `tigrinho`, `tiger`)\n`K! blackjack valor` (`bj`)\n`K! caraoucoroa valor` (`coinflip`, `coroa`)\n`K! dados valor` (`dice`)\n`K! crash valor` (`rocket`)\n`K! mines valor [bombas]` (`mina`) — 1 a 19 bombas\n`K! buckshot valor` (`buck`, `roletarussa`) — 6, 8 ou 16 câmaras\n💡 CRW usa o Banco; XP pode ser apostado com `xp:100`, `xp100` ou `100xp`. Qualquer vitória pode acertar **JACKPOT (mín. 3×)**.", False),
            ("🔫 Buckshot", "O **bot sempre começa**. Jogador e bot têm **3 vidas**; bala verdadeira tira 1 vida e festim passa a vez. No início da partida, você recebe **3 itens aleatórios e únicos**. Itens: 🔍 Lupa, 🪚 Serra, 🚬 Cigarro, 🍺 Cerveja, ⛓️ Algemas, 📞 Telefone, 🔄 Inversor ou 💉 Adrenalina.", False),
            ("⚡ Slash", "Todos os jogos principais também têm `/arcade`, `/roleta`, `/slots`, `/blackjack`, `/caraoucoroa`, `/dados`, `/crash`, `/mines` e `/buckshot`.", False),
        ],
    },
    "moderacao": {
        "title": "🛡️ Kibot — Moderação & Administração",
        "description": "Ferramentas para moderar, configurar e administrar o servidor.",
        "fields": [
            ("🛡️ Moderação", "`K! kick @membro` (`k`, `expulsar`)\n`K! ban @membro` (`b`)\n`K! unban ID` (`ub`)\n`K! mutar @membro` (`mute`, `timeout`)\n`K! desmutar @membro` (`unmute`, `untimeout`)\n`K! advertir @membro motivo` (`warn`, `w`)\n`K! advertencias @membro`\n`K! limpar_advertencias @membro`\n`K! limpar quantidade` (`clear`, `clean`, `purge`)\n`K! slowmode segundos` (`slow`)", False),
            ("⚙️ Servidor / Cargos", "`K! boasvindas #canal [estilo] [mensagem]` (`welcome`) — embed com presets\n`/config boasvindas` — Kiba, Elegante, RPG, Caos ou Minimalista\n`K! autobanbets #canal on/off` (`antibetspam`, `betguard`) — ban + limpeza do histórico\n`/config autoban_bets` — configura a quarentena Anti-BetSpam\n`K! configlog #canal` (`log`)\n`K! trancar` (`lock`, `travar`)\n`K! addfigurinha` (`addsticker`, `sticker`, `figurinha`) — painel para importar figurinha\n`K! addemoji` (`emoji`, `addemote`) — painel para importar emoji\n`K! criar_canal nome` (`canal`, `ccanal`)\n`K! criar_cargo nome` (`cargo`, `ccargo`)\n`K! cargo_add @membro @cargo` (`addcargo`, `addrole`)\n`K! cargo_remover @membro @cargo` (`rmcargo`, `delcargo`, `delrole`)\n`K! up @membro` (`promote`, `promover`)\n`K! demote @membro` (`down`, `rebaixar`)", False),
            ("🤖 AutoMod", "`K! automodspam adicionar #canal`\n`K! automodspam remover #canal`\n`K! automodspam listar`\n`K! automodstatus`\n`K! automodtest`", False),
            ("👑 Dono / Economia Admin", "`K! setcrowings @membro valor` (`setcrw`, `setmoney`)\n`K! retirarcrowings @membro valor`\n`K! setfichas @membro valor`\n`K! retirarfichas @membro valor`\n`K! setxp @membro valor`\n`K! retirarxp @membro valor`\n`K! setnivel @membro valor`", False),
        ],
    },
    "todos": {
        "title": "📋 Kibot — Todos os Comandos",
        "description": "Índice gerado diretamente dos comandos registrados. Novos comandos entram aqui automaticamente após serem carregados pelo bot.",
        "fields": [],
    },
    "sistemas": {
        "title": "🔧 Kibot — Sistemas & Ferramentas",
        "description": "Ferramentas extras e comandos de gerenciamento.",
        "fields": [
            ("⭐ XP / Perfil", "`K! nivel` (`lv`, `level`, `xp`, `perfil`)\n`K! topxp` (`rankxp`, `xptop`)\n`K! badges` (`badge`, `conquistas`, `conquista`)\n`K! painel_niveis` (`nivelcargos`, `cargos_nivel`, `nivelcargo`, `cargonivel`)", False),
            ("🏷️ Tags", "**44 tags nativas** respondem automaticamente quando mencionadas em qualquer canal.\nEx.: `Kibot`, `CRW`, `crime`, `Buckshot`, `caos`, `socorro`, `regras`...\n\nTags personalizadas: `K! tag listar`\n`K! tag criar nome resposta`\n`K! tag remover nome`\nSlash: `/tag`", False),
            ("📋 Formulários / Tickets", "`K! formulario ...` — painel, destino, criar, publicar e listar\n`K! ticket ...` — painel, configurar, assumir, adicionar/remover e fechar\nSlash: `/formulario` e `/ticket`", False),
            ("🎙️ Transcritor", "`K! transcritor iniciar #canal`\n`K! transcritor parar #canal`\n`K! transcritor status #canal`\nSlash: `/transcritor`", False),
            ("🎨 Embeds / Servidor", "`K! embed chave=valor | chave=valor` (`emb`, `criarembed`)\n`K! criarservidor` (`servidor`, `serverbuilder`, `builder`)\nSlash: `/embed`, `/criarservidor`, `/anunciar`, `/info_servidor`", False),
            ("🏓 Diagnóstico", "`K! ping` — latência\n`K! kibotversion` (`versao`, `build`)\n`K! presenciatest [@membro]` (`testepresenca`)", False),
        ],
    },
}


def _dynamic_commands_embed_data(bot):
    """Índice completo gerado dos comandos realmente registrados no bot."""
    prefix = {}
    for command in bot.walk_commands():
        if not getattr(command, "hidden", False):
            prefix.setdefault(command.qualified_name, command)
    prefix_lines = []
    for name, command in sorted(prefix.items()):
        aliases = getattr(command, "aliases", []) or []
        alias_text = f" • {', '.join('`'+a+'`' for a in aliases)}" if aliases else ""
        sig = getattr(command, "signature", "") or ""
        usage = f"{config.PREFIX}{name}{(' ' + sig) if sig else ''}"
        prefix_lines.append(f"`{usage}`{alias_text}")
    slash = []
    for command in bot.tree.walk_commands():
        if not getattr(command, "hidden", False):
            slash.append(command.qualified_name)
    return prefix_lines, sorted(set(slash))

ORDER = list(PAGES)
LABELS = {
    "inicio": "🏠 Início", "economia": "💰 Economia", "crime": "🕶️ Submundo",
    "rpg": "🎲 RPG", "dados": "🌐 Dados Recentes", "arcade": "🎮 Arcade", "moderacao": "🛡️ Moderação", "todos": "📋 Todos", "sistemas": "🔧 Sistemas"
}


def _build_todos_pages(bot):
    """Monta páginas seguras para a lista completa de comandos.

    O Discord limita embeds a 25 fields. A versão anterior colocava cada
    bloco de comandos em um field e podia ultrapassar esse limite, fazendo o
    botão "Todos" falhar com HTTP 400. Aqui a lista é paginada e cada página
    usa no máximo 4 fields, ficando também dentro dos limites de caracteres.
    """
    prefix_lines, slash_names = _dynamic_commands_embed_data(bot)
    entries = list(prefix_lines)
    if slash_names:
        entries.append("__**⚡ Comandos Slash**__")
        entries.extend(f"`/{name}`" for name in slash_names)

    if not entries:
        return [[("📋 Comandos", "Nenhum comando registrado no momento.", False)]]

    # Um field do Discord aceita até 1024 caracteres. Mantemos folga para
    # futuras mudanças de aliases/assinaturas.
    FIELD_LIMIT = 900
    FIELDS_PER_PAGE = 4
    chunks = []
    chunk = []
    size = 0
    for line in entries:
        line_size = len(line) + (1 if chunk else 0)
        if chunk and size + line_size > FIELD_LIMIT:
            chunks.append(chunk)
            chunk = []
            size = 0
        chunk.append(line)
        size += line_size
    if chunk:
        chunks.append(chunk)

    pages = []
    for page_start in range(0, len(chunks), FIELDS_PER_PAGE):
        page_chunks = chunks[page_start:page_start + FIELDS_PER_PAGE]
        page_fields = []
        for local_idx, values in enumerate(page_chunks, start=1):
            absolute_idx = page_start + local_idx
            title = "⌨️ Prefixo"
            if values and values[0].startswith("__**⚡"):
                title = "⚡ Slash"
            elif absolute_idx > 1:
                title = f"⌨️ Prefixo — bloco {absolute_idx}"
            page_fields.append((title, "\n".join(values), False))
        pages.append(page_fields)
    return pages


def make_help_embed(key: str, bot=None, todos_page: int = 0) -> discord.Embed:
    page = PAGES[key]
    todos_pages = _build_todos_pages(bot) if key == "todos" and bot is not None else None

    if todos_pages:
        todos_page = max(0, min(int(todos_page), len(todos_pages) - 1))
        fields = todos_pages[todos_page]
        description = (
            "Índice completo dos comandos registrados no Kibot. "
            "Use ◀️/▶️ para navegar entre as páginas desta lista."
        )
    else:
        fields = list(page["fields"])
        description = page["description"]

    e = KibotEmbed(title=page["title"], description=description, color=discord.Color.gold())
    for name, value, inline in fields:
        e.add_field(name=name, value=value, inline=inline)

    if todos_pages:
        footer = (
            f"Kibot • Todos os comandos • Página {todos_page + 1}/{len(todos_pages)} "
            f"• Use {config.PREFIX}ajuda a qualquer momento"
        )
    else:
        footer = f"Kibot • Página {ORDER.index(key)+1}/{len(ORDER)} • Use {config.PREFIX}ajuda a qualquer momento"
    e.set_footer(text=footer)
    return e


class HelpView(discord.ui.View):
    def __init__(self, owner_id: int, bot=None, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.bot = bot
        self.key = "inicio"
        self.todos_page = 0
        options = [discord.SelectOption(label=LABELS[k], value=k, default=(k == self.key)) for k in ORDER]
        self.selector = discord.ui.Select(placeholder="📖 Escolha uma página...", options=options, row=0)
        self.selector.callback = self.select_callback
        self.add_item(self.selector)
        self.prev_button = discord.ui.Button(label="Anterior", emoji="◀️", style=discord.ButtonStyle.secondary, row=1)
        self.prev_button.callback = self.prev_callback
        self.add_item(self.prev_button)
        self.home_button = discord.ui.Button(label="Início", emoji="🏠", style=discord.ButtonStyle.primary, row=1)
        self.home_button.callback = self.home_callback
        self.add_item(self.home_button)
        self.next_button = discord.ui.Button(label="Próxima", emoji="▶️", style=discord.ButtonStyle.secondary, row=1)
        self.next_button.callback = self.next_callback
        self.add_item(self.next_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("👀 Essa central é da pessoa que abriu ela. Manda `K!ajuda` pra abrir a sua.", ephemeral=True)
            return False
        return True

    async def _update(self, interaction: discord.Interaction):
        for option in self.selector.options:
            option.default = option.value == self.key
        await interaction.response.edit_message(
            embed=make_help_embed(self.key, self.bot, self.todos_page),
            view=self,
        )

    async def select_callback(self, interaction: discord.Interaction):
        self.key = self.selector.values[0]
        self.todos_page = 0
        await self._update(interaction)

    async def prev_callback(self, interaction: discord.Interaction):
        if self.key == "todos":
            total = len(_build_todos_pages(self.bot)) if self.bot is not None else 1
            self.todos_page = (self.todos_page - 1) % max(1, total)
        else:
            self.key = ORDER[(ORDER.index(self.key) - 1) % len(ORDER)]
        await self._update(interaction)

    async def next_callback(self, interaction: discord.Interaction):
        if self.key == "todos":
            total = len(_build_todos_pages(self.bot)) if self.bot is not None else 1
            self.todos_page = (self.todos_page + 1) % max(1, total)
        else:
            self.key = ORDER[(ORDER.index(self.key) + 1) % len(ORDER)]
        await self._update(interaction)

    async def home_callback(self, interaction: discord.Interaction):
        self.key = "inicio"
        self.todos_page = 0
        await self._update(interaction)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
