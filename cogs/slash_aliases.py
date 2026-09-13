from cogs.embed_style import KibotEmbed
import discord
from discord.ext import commands
from discord import app_commands
from cogs.utils import parse_amount
from cogs.help_center import HelpView, make_help_embed

class SlashAliases(commands.Cog):
    """Comandos slash diretos para espelhar os comandos prefixo do Kibot."""
    def __init__(self, bot): self.bot = bot
    def cog(self, name): return self.bot.get_cog(name)

    @app_commands.command(name='ajuda', description='Mostra a lista completa de comandos do Kibot')
    async def ajuda(self, interaction):
        await self._help_embed(interaction)

    @app_commands.command(name='comandos', description='Mostra a lista completa de comandos do Kibot')
    async def comandos(self, interaction):
        await self._help_embed(interaction)

    async def _help_embed(self, interaction):
        await interaction.response.send_message(embed=make_help_embed("inicio", self.bot), view=HelpView(interaction.user.id, self.bot), ephemeral=True)

    @app_commands.command(name='perfil', description='Mostra seu perfil, nível e XP')
    @app_commands.describe(membro='Membro que você quer consultar')
    async def perfil(self, interaction, membro: discord.Member = None):
        cog=self.cog('Levels'); await cog._profile(interaction, membro or interaction.user)

    # Economia direta (além de /economia ...)
    @app_commands.command(name='saldo', description='Vê sua carteira, banco e Fichas Corvo')
    @app_commands.describe(usuario='Usuário para consultar')
    async def saldo(self, interaction, usuario: discord.Member = None):
        cog=self.cog('Economy'); await interaction.response.send_message(embed=await cog._saldo(interaction, usuario or interaction.user))

    @app_commands.command(name='daily', description='Recebe seu pagamento diário em CRW')
    async def daily(self, interaction): await self.cog('Economy')._daily(interaction)
    @app_commands.command(name='trabalhar', description='Trabalha no emprego escolhido')
    async def trabalhar(self, interaction): await self.cog('Economy')._trabalhar(interaction)
    @app_commands.command(name='trabalhos', description='Lista os empregos liberados pelo seu nível')
    async def trabalhos(self, interaction): await self.cog('Economy')._trabalhos(interaction)
    @app_commands.command(name='escolher_trabalho', description='Escolhe seu emprego')
    @app_commands.describe(trabalho='ID do trabalho')
    async def escolher_trabalho(self, interaction, trabalho: str): await self.cog('Economy')._escolher_trabalho(interaction, trabalho)
    @app_commands.command(name='roubar', description='Tenta roubar 50% da carteira de outro membro')
    @app_commands.describe(usuario='Membro alvo')
    async def roubar(self, interaction, usuario: discord.Member): await self.cog('Economy')._roubar(interaction, usuario)
    @app_commands.command(name='transferir', description='Transfere CRW da sua carteira para outro membro')
    @app_commands.describe(usuario='Quem receberá', quantidade='Valor: 10000, 10k, 1m, all ou half')
    async def transferir(self, interaction, usuario: discord.Member, quantidade: str): await self.cog('Economy')._transferir(interaction, usuario, quantidade)
    @app_commands.command(name='depositar', description='Deposita CRW da carteira no Banco')
    @app_commands.describe(quantidade='Valor: 10000, 10k, 1m, all ou half')
    async def depositar(self, interaction, quantidade: str): await self.cog('Economy')._depositar(interaction, quantidade)
    @app_commands.command(name='sacar', description='Saca CRW do Banco para a carteira')
    @app_commands.describe(quantidade='Valor: 10000, 10k, 1m, all ou half')
    async def sacar(self, interaction, quantidade: str): await self.cog('Economy')._sacar(interaction, quantidade)
    @app_commands.command(name='ranking', description='Mostra o ranking de Crowings')
    async def ranking(self, interaction):
        cog=self.cog('Economy'); await cog.ranking.callback(cog, interaction)

    # `/loja` já existe como grupo nativo no Economy (`/loja listar`, `/loja comprar`, etc.).
    # Não criar um comando direto com o mesmo nome, pois o Discord considera o grupo
    # e o comando `/loja` o mesmo registro e causa CommandAlreadyRegistered.
    @app_commands.command(name='comprar', description='Compra um item da loja')
    @app_commands.describe(item_id='ID do item')
    async def comprar(self, interaction, item_id: int): await self.cog('Economy')._comprar(interaction, item_id)
    @app_commands.command(name='fichas', description='Vê suas Fichas Corvo')
    async def fichas(self, interaction): await self.cog('Economy')._fichas(interaction)
    @app_commands.command(name='ranking_fichas', description='Ranking de Fichas Corvo')
    async def ranking_fichas(self, interaction):
        cog=self.cog('Economy'); await cog.ranking_fichas_slash.callback(cog, interaction)
    @app_commands.command(name='loja_corvo', description='Abre a loja de Fichas Corvo')
    async def loja_corvo(self, interaction): await self.cog('Economy')._corvo_shop(interaction)
    @app_commands.command(name='comprar_corvo', description='Compra um item com Fichas Corvo')
    @app_commands.describe(item_id='ID do item')
    async def comprar_corvo(self, interaction, item_id: int): await self.cog('Economy')._comprar_corvo(interaction, item_id)
    @app_commands.command(name='empresa', description='Mostra sua empresa e os tipos disponíveis')
    async def empresa(self, interaction): await self.cog('Economy')._empresa(interaction)
    @app_commands.command(name='criar_empresa', description='Cria sua empresa')
    @app_commands.describe(tipo='Tipo da empresa', nome='Nome da empresa')
    async def criar_empresa(self, interaction, tipo: str, nome: str): await self.cog('Economy')._criar_empresa(interaction,tipo,nome)
    @app_commands.command(name='lucro_empresa', description='Coleta o lucro da sua empresa')
    async def lucro_empresa(self, interaction): await self.cog('Economy')._lucro_empresa(interaction)
    @app_commands.command(name='vender_empresa', description='Vende sua empresa')
    async def vender_empresa(self, interaction): await self.cog('Economy')._vender_empresa(interaction)

    # Administração que faltava no slash
    @app_commands.command(name='configlog', description='Configura o canal de logs')
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(canal='Canal onde os logs serão enviados')
    async def configlog(self, interaction, canal: discord.TextChannel):
        await __import__('database.db',fromlist=['set_guild_config']).set_guild_config(interaction.guild_id,log_channel_id=canal.id)
        await interaction.response.send_message(f'✅ Logs configurados em {canal.mention}.',ephemeral=True)

    @app_commands.command(name='up', description='Promove um membro para o próximo cargo gerenciável')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def up(self, interaction, membro: discord.Member):
        await self._promote(interaction,membro,1)
    @app_commands.command(name='demote', description='Rebaixa um membro para o cargo gerenciável abaixo')
    @app_commands.checks.has_permissions(manage_roles=True)
    async def demote(self, interaction, membro: discord.Member):
        await self._promote(interaction,membro,-1)
    async def _promote(self, interaction, membro, direction):
        cog=self.cog('Management'); actor=interaction.user; g=interaction.guild; me=g.me
        if membro==actor or (membro.bot and membro==self.bot.user): return await interaction.response.send_message('❌ Não consigo mexer nesse membro.',ephemeral=True)
        if actor.id!=g.owner_id and membro.top_role>=actor.top_role: return await interaction.response.send_message('❌ O cargo dessa pessoa é igual ou maior que o seu.',ephemeral=True)
        manageable=[r for r in g.roles if not r.is_default() and not r.managed and r<me.top_role]
        candidates=[r for r in manageable if r>membro.top_role] if direction>0 else [r for r in manageable if r<membro.top_role]
        target=min(candidates,key=lambda r:r.position) if direction>0 and candidates else (max(candidates,key=lambda r:r.position) if candidates else None)
        if not target: return await interaction.response.send_message('❌ Não existe um cargo gerenciável nessa direção.',ephemeral=True)
        if membro.top_role != g.default_role and membro.top_role < me.top_role: await membro.remove_roles(membro.top_role,reason=f'Kibot {"promote" if direction>0 else "demote"}')
        await membro.add_roles(target,reason=f'Kibot {"promote" if direction>0 else "demote"}')
        await interaction.response.send_message(f'✅ {membro.mention} foi **{"promovido" if direction>0 else "rebaixado"}** para {target.mention}.')

    @app_commands.command(name='automodstatus', description='Mostra o diagnóstico do AutoMod')
    @app_commands.checks.has_permissions(administrator=True)
    async def automodstatus(self, interaction):
        from database import db
        cog=self.cog('Security'); me=interaction.guild.me; perms=me.guild_permissions; cfg=await db.get_guild_config(interaction.guild_id)
        ch=interaction.channel; cp=ch.permissions_for(me)
        lines=[f'**Build:** `{getattr(__import__("main"), "BUILD_ID", "desconhecida")}`',f'**Cog Security:** {"✅ SIM" if cog else "❌ NÃO"}',f'**Message Content:** {"✅ ON" if self.bot.intents.message_content else "❌ OFF"}',f'**Manage Messages:** {"✅" if perms.manage_messages else "❌"}',f'**Moderate Members:** {"✅" if perms.moderate_members else "❌"}',f'**Logs:** {ch.guild.get_channel(cfg["log_channel_id"]).mention if cfg and cfg["log_channel_id"] and ch.guild.get_channel(cfg["log_channel_id"]) else "❌ não configurado"}']
        await interaction.response.send_message(embed=KibotEmbed(title='🧪 Diagnóstico do Kibot — AutoMod',description='\n'.join(lines),color=discord.Color.blurple()),ephemeral=True)
    @app_commands.command(name='automodtest', description='Inicia o teste do AutoMod')
    @app_commands.checks.has_permissions(administrator=True)
    async def automodtest(self, interaction):
        await interaction.response.send_message('🧪 Mande 6 mensagens seguidas neste canal e depois confira `/automodstatus`.',ephemeral=True)

async def setup(bot): await bot.add_cog(SlashAliases(bot))
