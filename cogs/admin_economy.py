from cogs.embed_style import KibotEmbed
import discord
from discord.ext import commands
from database import db
from cogs.economy import format_money
from cogs.utils import parse_amount

class AdminEconomy(commands.Cog):
    """Comandos administrativos de economia e progresso. Somente Administrador."""
    def __init__(self, bot): self.bot = bot

    async def _sync_level(self, member):
        cog = self.bot.get_cog("Levels")
        if cog: await cog.sync_member_level_roles(member)

    @staticmethod
    def _source(origem):
        origem=(origem or "carteira").lower().strip()
        if origem in {"banco","bank","🏦"}: return "bank"
        if origem in {"carteira","wallet","cash","👛"}: return "balance"
        return None

    @commands.command(name="setcrowings", aliases=["setcrw", "setmoney"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def setcrowings(self, ctx, usuario: discord.Member, quantidade: str, origem: str = "carteira"):
        source=self._source(origem)
        if not source: return await ctx.send("❌ Origem inválida. Use `carteira` ou `banco`.")
        row=await db.get_user(usuario.id,ctx.guild.id); base=row[source]
        quantidade=parse_amount(quantidade,base)
        if quantidade is None or quantidade < 0: return await ctx.send("❌ Valor não pode ser negativo, chefe kkkkk.")
        if source=="bank": await db.set_bank(usuario.id,ctx.guild.id,quantidade)
        else: await db.set_balance(usuario.id,ctx.guild.id,quantidade)
        label="Banco" if source=="bank" else "carteira"
        await ctx.send(f"👑 **Crowings alterados!**\n{usuario.mention} agora tem **{format_money(quantidade)}** no **{label}**.")

    @commands.command(name="retirarcrowings", aliases=["retirarcrw", "removecrw", "removecrowings"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def retirarcrowings(self, ctx, usuario: discord.Member, quantidade: str, origem: str = "carteira"):
        source=self._source(origem)
        if not source: return await ctx.send("❌ Origem inválida. Use `carteira` ou `banco`.")
        row=await db.get_user(usuario.id,ctx.guild.id); base=row[source]
        quantidade=parse_amount(quantidade,base)
        if quantidade is None or quantidade < 0: return await ctx.send("❌ Valor inválido.")
        novo=await (db.remove_bank(usuario.id,ctx.guild.id,quantidade) if source=="bank" else db.remove_balance(usuario.id,ctx.guild.id,quantidade))
        label="Banco" if source=="bank" else "carteira"
        await ctx.send(f"💸 **Crowings retirados!** {usuario.mention} agora tem **{format_money(novo)}** no **{label}**.")

    @commands.command(name="setfichas", aliases=["setfichascorvo", "setchips"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def setfichas(self, ctx, usuario: discord.Member, quantidade: int):
        if quantidade < 0: return await ctx.send("❌ Valor não pode ser negativo kkkkk.")
        await db.set_corvo_chips(usuario.id,ctx.guild.id,quantidade)
        await ctx.send(f"🐦‍⬛ **Fichas Corvo alteradas!**\n{usuario.mention} agora tem **{quantidade:,} Fichas Corvo**.".replace(",","."))

    @commands.command(name="retirarfichas", aliases=["retirarfichascorvo", "removechips"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def retirarfichas(self, ctx, usuario: discord.Member, quantidade: int):
        if quantidade < 0: return await ctx.send("❌ Valor não pode ser negativo.")
        novo=await db.remove_corvo_chips(usuario.id,ctx.guild.id,quantidade)
        await ctx.send(f"💸 **Fichas retiradas!** {usuario.mention} agora tem **{novo:,} Fichas Corvo**.".replace(",","."))

    @commands.command(name="setxp", aliases=["setlevelxp"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def setxp(self, ctx, usuario: discord.Member, quantidade: int):
        if quantidade < 0: return await ctx.send("❌ XP não pode ser negativo kkkkk.")
        level,remaining=await db.set_xp(usuario.id,ctx.guild.id,quantidade); await self._sync_level(usuario)
        await ctx.send(f"⭐ **XP alterado!**\n{usuario.mention} agora está com **{quantidade:,} XP total** → **nível {level}**, com **{remaining} XP** no nível atual.".replace(",","."))

    @commands.command(name="retirarxp", aliases=["removexp"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def retirarxp(self, ctx, usuario: discord.Member, quantidade: int):
        if quantidade < 0: return await ctx.send("❌ XP não pode ser negativo.")
        level,remaining=await db.remove_xp(usuario.id,ctx.guild.id,quantidade); await self._sync_level(usuario)
        total=sum(100*i for i in range(1,level))+remaining
        await ctx.send(f"📉 **XP retirado!** {usuario.mention} agora tem **{total:,} XP total** → **nível {level}**, com **{remaining} XP** no nível atual.".replace(",","."))

    @commands.command(name="setnivel", aliases=["setlevel", "setnivelxp"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def setnivel(self, ctx, usuario: discord.Member, nivel: int):
        if nivel < 1: return await ctx.send("❌ O nível mínimo é 1.")
        level,remaining=await db.set_level(usuario.id,ctx.guild.id,nivel); await self._sync_level(usuario)
        await ctx.send(f"🏆 **Nível definido!** {usuario.mention} agora está no **nível {level}** com **{remaining} XP** no nível atual.")

    @commands.command(name="automodspam", aliases=["spampermitido", "spampermitir"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def automodspam(self, ctx, acao: str = None, canal: discord.TextChannel = None):
        """Gerencia canais onde flood e mensagens repetidas do AutoMod são permitidos."""
        if not acao:
            return await ctx.send("❌ Use `K! automodspam adicionar #canal`, `remover #canal` ou `listar`.")
        acao = acao.casefold()
        if acao in {"listar", "lista", "list"}:
            ids = await db.get_automod_spam_exempt_channels(ctx.guild.id)
            canais = [ctx.guild.get_channel(cid) for cid in ids]
            canais = [c.mention for c in canais if c is not None]
            texto = ", ".join(canais) if canais else "nenhum canal configurado"
            return await ctx.send(f"🛡️ **Canais com spam permitido:** {texto}")
        if canal is None:
            return await ctx.send("❌ Informe o canal. Ex.: `K! automodspam adicionar #mudae`.")
        if acao in {"adicionar", "add", "permitir", "on", "ativar"}:
            await db.set_automod_spam_exempt(ctx.guild.id, canal.id, True)
            return await ctx.send(f"✅ Spam/flood liberado no canal {canal.mention}.\n**Importante:** convites, menções em massa, caps abusivo e palavras bloqueadas continuam protegidos.")
        if acao in {"remover", "remove", "tirar", "off", "desativar"}:
            await db.set_automod_spam_exempt(ctx.guild.id, canal.id, False)
            return await ctx.send(f"🔒 Spam/flood voltou a ser monitorado no canal {canal.mention}.")
        return await ctx.send("❌ Ação inválida. Use `adicionar`, `remover` ou `listar`.")

    @commands.command(name="automodstatus")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def automodstatus(self,ctx):
        cog=self.bot.get_cog("Security"); me=ctx.guild.me; perms=me.guild_permissions; log=await db.get_guild_config(ctx.guild.id); log_id=log["log_channel_id"] if log else None; log_channel=ctx.guild.get_channel(log_id) if log_id else None
        role_ok=bool(me.top_role and me.top_role.position>ctx.author.top_role.position) if ctx.author!=me else True; chperms=ctx.channel.permissions_for(me); author_has_bypass=cog.has_automod_role(ctx.author) if cog else False; event_count=getattr(cog,"event_count",0) if cog else 0; last_event=getattr(cog,"last_event",None) if cog else None; last_rule=getattr(cog,"last_rule",None) if cog else None; content_len=last_event.get("content_len",0) if last_event else 0
        from main import BUILD_ID
        lines=[f"**Build:** `{BUILD_ID}`",f"**Cog Security carregada:** {'✅ SIM' if cog else '❌ NÃO'}",f"**Eventos de mensagem recebidos:** **{event_count}**",f"**Último conteúdo recebido pelo bot:** **{content_len} caracteres**",f"**Message Content Intent no código:** {'✅ ON' if self.bot.intents.message_content else '❌ OFF'}",f"**Manage Messages (servidor):** {'✅' if perms.manage_messages else '❌'}",f"**Moderate Members (servidor):** {'✅' if perms.moderate_members else '❌'}",f"**Manage Messages (este canal):** {'✅' if chperms.manage_messages else '❌'}",f"**Enviar mensagens (este canal):** {'✅' if chperms.send_messages else '❌'}",f"**Ler histórico (este canal):** {'✅' if chperms.read_message_history else '❌'}",f"**Cargo do Kibot acima do seu:** {'✅' if role_ok else '⚠️ NÃO (isso afeta testes contra você)'}",f"**Seu cargo tem bypass 'automod':** {'⚠️ SIM — você está isento' if author_has_bypass else '✅ NÃO'}",f"**Última regra acionada:** `{last_rule or 'nenhuma'}`",f"**Canal de logs:** {log_channel.mention if log_channel else '❌ não configurado'}"]
        await ctx.send(embed=KibotEmbed(title="🧪 Diagnóstico do Kibot — AutoMod V2",description="\n".join(lines),color=discord.Color.blurple()))

    @commands.command(name="automodtest")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def automodtest(self,ctx):
        cog=self.bot.get_cog("Security")
        if not cog: return await ctx.send("❌ A cog **Security** não está carregada. O AutoMod não tem como funcionar.")
        await ctx.send("🧪 **Teste do AutoMod:** mande agora **6 mensagens seguidas** neste canal. Se o Kibot não apagar a 6ª, use `K! automodstatus` e me mande o resultado.")

    @setcrowings.error
    @retirarcrowings.error
    @setfichas.error
    @retirarfichas.error
    @setxp.error
    @retirarxp.error
    @setnivel.error
    @automodspam.error
    @automodstatus.error
    @automodtest.error
    async def prefix_error(self,ctx,error):
        if isinstance(error,commands.MissingPermissions): await ctx.send("🚫 Só quem tem **Administrador** pode usar esse comando.")
        elif isinstance(error,commands.MissingRequiredArgument): await ctx.send("❌ Faltou argumento. Ex.: `K! setnivel @Kiba 10`")
        elif isinstance(error,commands.BadArgument): await ctx.send("❌ Não consegui entender o usuário ou o valor. Ex.: `K! setxp @Kiba 5000`")
        else: raise error

async def setup(bot): await bot.add_cog(AdminEconomy(bot))
