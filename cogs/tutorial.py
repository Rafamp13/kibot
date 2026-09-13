from cogs.embed_style import KibotEmbed
import discord
from discord.ext import commands
from discord import app_commands


PAGES = [
    {
        "title": "🐦 Bem-vindo ao Kibot!",
        "description": (
            "Esse é o guia rápido para quem acabou de chegar.\n\n"
            "O Kibot usa **Crowings (CRW)** como moeda virtual e também possui XP, níveis, empregos, Banco, empresas e jogos.\n\n"
            "Use os botões abaixo para navegar pelo tutorial."
        ),
    },
    {
        "title": "⌨️ Como falar com o Kibot",
        "description": (
            "Você pode usar o Kibot de duas formas:\n\n"
            "**Prefixo:** `K! comando`\n"
            "Exemplo: `K! saldo`\n\n"
            "**Slash:** `/comando`\n"
            "Exemplo: `/saldo`\n\n"
            "Se você esquecer algum comando, use **`K! ajuda`** ou **`/ajuda`**."
        ),
    },
    {
        "title": "👤 Seu perfil e seu dinheiro",
        "description": (
            "Comece olhando seus dados:\n\n"
            "`K! perfil` ou `/perfil` — mostra nível, XP e informações do personagem.\n"
            "`K! saldo` ou `/saldo` — mostra sua carteira, Banco e Fichas Corvo.\n\n"
            "Os **Crowings** são sua moeda principal. A carteira serve para movimentações normais; o Banco é usado também para as apostas do Arcade."
        ),
    },
    {
        "title": "💰 Como ganhar seus primeiros CRW",
        "description": (
            "Os comandos mais importantes para começar são:\n\n"
            "`K! daily` — recebe seu pagamento diário.\n"
            "`K! trabalhos` — vê os empregos liberados pelo seu nível.\n"
            "`K! escolher_trabalho ID` — escolhe um emprego.\n"
            "`K! trabalhar` — trabalha e recebe CRW.\n"
            "`K! bico` — vê os bicos disponíveis.\n\n"
            "💡 Subir de nível libera novas opções de trabalho."
        ),
    },
    {
        "title": "🏦 Carteira, Banco, ALL e HALF",
        "description": (
            "Você pode mover seus CRW entre carteira e Banco:\n\n"
            "`K! depositar 10k`\n"
            "`K! sacar 5k`\n"
            "`K! transferir @pessoa 10k`\n\n"
            "Também existem dois atalhos especiais:\n"
            "`all` = usa **todo o saldo disponível** da origem.\n"
            "`half` = usa **metade do saldo disponível** da origem.\n\n"
            "Exemplo: `K! depositar all` ou `K! transferir @pessoa half`."
        ),
    },
    {
        "title": "🎮 Arcade",
        "description": (
            "O Arcade possui jogos que usam CRW. As apostas são retiradas do **Banco**.\n\n"
            "`K! arcade` — abre a central.\n"
            "`K! roleta 10k`\n"
            "`K! slots 10k`\n"
            "`K! blackjack 10k`\n"
            "`K! caraoucoroa 10k`\n"
            "`K! dados 10k`\n"
            "`K! crash 10k`\n"
            "`K! mines 10k 5` — 10k de aposta com 5 bombas\n\n"
            "Também dá para usar `all` ou `half` como aposta."
        ),
    },
    {
        "title": "🛠️ Emojis, figurinhas e Mines",
        "description": (
            "Administradores com a permissão **Gerenciar Expressões** podem usar os painéis:\n\n"
            "`K! addemoji` — importa emoji por arquivo, URL ou outro emoji personalizado.\n"
            "`K! addfigurinha` — importa figurinha por arquivo, URL ou outra figurinha.\n\n"
            "No Mines, escolha a quantidade de bombas: `K! mines 10k 5`. Você pode usar de **1 a 19 bombas** em 20 casas.\n"
        ),
    },
    {
        "title": "⭐ XP e Níveis",
        "description": (
            "Você ganha XP participando e usando o servidor.\n\n"
            "`K! nivel` — vê seu nível e XP.\n"
            "`K! topxp` — ranking de XP.\n"
            "`K! perfil` — visão geral do seu perfil.\n\n"
            "Dependendo da configuração do servidor, níveis também podem conceder **cargos automaticamente**."
        ),
    },
    {
        "title": "🏢 Empresas",
        "description": (
            "Quando tiver CRW suficiente, você pode abrir uma empresa:\n\n"
            "`K! empresa` — vê as opções e sua empresa.\n"
            "`K! criar_empresa tipo nome` — cria uma empresa.\n"
            "`K! lucro_empresa` — coleta o lucro quando estiver disponível.\n"
            "`K! vender_empresa` — vende sua empresa.\n\n"
            "💡 O lucro é depositado diretamente no **Banco**."
        ),
    },
    {
        "title": "🧭 E agora?",
        "description": (
            "Você já sabe o básico! 😎\n\n"
            "Comece por esta sequência:\n"
            "**1.** `K! perfil`\n"
            "**2.** `K! daily`\n"
            "**3.** `K! trabalhos`\n"
            "**4.** `K! escolher_trabalho ID`\n"
            "**5.** `K! trabalhar`\n"
            "**6.** `K! depositar all`\n"
            "**7.** Explore o `K! arcade` quando quiser.\n\n"
            "E lembre: se ficar perdido, **`K! ajuda`** é seu mapa. 🐦‍⬛"
        ),
    },
]


class TutorialView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=600)
        self.author_id = author_id
        self.page = 0
        self.message = None
        self._update_buttons()

    def _update_buttons(self):
        self.previous.disabled = self.page <= 0
        self.next.disabled = self.page >= len(PAGES) - 1

    def embed(self):
        data = PAGES[self.page]
        e = KibotEmbed(
            title=data["title"],
            description=data["description"],
            color=discord.Color.gold(),
        )
        e.set_footer(text=f"Tutorial do Kibot • Página {self.page + 1}/{len(PAGES)}")
        return e

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Esse tutorial foi aberto por outra pessoa. Use `K! tutorial` para abrir o seu.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="◀️ Voltar", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="▶️ Avançar", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="❌ Fechar", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


class Tutorial(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="tutorial", aliases=["tuto", "iniciante", "começar", "comecar"])
    async def tutorial(self, ctx: commands.Context):
        view = TutorialView(ctx.author.id)
        view.message = await ctx.send(embed=view.embed(), view=view)

    @app_commands.command(name="tutorial", description="Abre o tutorial interativo para iniciantes")
    async def tutorial_slash(self, interaction: discord.Interaction):
        view = TutorialView(interaction.user.id)
        await interaction.response.send_message(embed=view.embed(), view=view, ephemeral=True)
        try:
            view.message = await interaction.original_response()
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Tutorial(bot))
