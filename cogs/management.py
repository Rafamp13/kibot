from cogs.embed_style import KibotEmbed
import discord
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.utils import send, log_action

class Management(commands.Cog):
    def __init__(self,bot): self.bot=bot
    config_group=app_commands.Group(name="config",description="Configura as paradas do servidor")

    WELCOME_PRESETS = {
        "kiba": {
            "title": "🪶 Uma nova presença surgiu...",
            "description": "Bem-vindo(a), **{membro}**!\n\nVocê acaba de entrar em **{servidor}**. Leia as regras, conheça a comunidade e fique à vontade para explorar.\n\n> **Membros no servidor:** {contagem}",
            "color": discord.Color.from_rgb(103, 55, 170),
        },
        "elegante": {
            "title": "✦ Seja muito bem-vindo(a)",
            "description": "É um prazer receber **{membro}** em **{servidor}**.\n\nEsperamos que sua estadia seja agradável. Explore os canais, participe das conversas e faça parte da comunidade.\n\n**Agora somos {contagem} membros.**",
            "color": discord.Color.from_rgb(70, 75, 95),
        },
        "rpg": {
            "title": "🎲 Um novo aventureiro chegou!",
            "description": "**{membro}** entrou em **{servidor}**!\n\nPegue seus dados, escolha seu caminho e prepare-se para as próximas histórias.\n\n⚔️ **Membros atuais:** {contagem}",
            "color": discord.Color.from_rgb(137, 78, 42),
        },
        "caos": {
            "title": "🚨 ATENÇÃO: CHEGOU GENTE NOVA",
            "description": "**{membro}** acaba de invadir **{servidor}**.\n\nNinguém sabe o que essa pessoa vai aprontar. A administração recomenda: **observem de longe.**\n\n👁️ Somos **{contagem}** agora.",
            "color": discord.Color.from_rgb(180, 45, 55),
        },
        "minimalista": {
            "title": "👋 Bem-vindo(a)",
            "description": "Olá, **{membro}**.\n\nSeja bem-vindo(a) a **{servidor}**.\n\nMembros: **{contagem}**",
            "color": discord.Color.from_rgb(52, 152, 219),
        },
    }

    @config_group.command(name="boasvindas",description="Configura uma embed bonita de boas-vindas")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(canal="Canal que receberá as boas-vindas", estilo="Modelo visual da embed", mensagem="Texto opcional; use {membro}, {servidor} e {contagem}")
    @app_commands.choices(estilo=[
        app_commands.Choice(name="Kiba Sombrio", value="kiba"),
        app_commands.Choice(name="Elegante", value="elegante"),
        app_commands.Choice(name="RPG / Aventura", value="rpg"),
        app_commands.Choice(name="Caos", value="caos"),
        app_commands.Choice(name="Minimalista", value="minimalista"),
    ])
    async def boasvindas(self,interaction,canal:discord.TextChannel,estilo:app_commands.Choice[str]=None,mensagem:str=None):
        style = estilo.value if estilo else "kiba"
        preset = self.WELCOME_PRESETS[style]
        await db.set_guild_config(
            interaction.guild_id, welcome_channel_id=canal.id, welcome_style=style,
            welcome_message=mensagem if mensagem is not None else preset["description"]
        )
        e = self._build_welcome_embed(interaction.guild, interaction.user, style, mensagem)
        await interaction.response.send_message(f"✅ Boas-vindas configuradas em {canal.mention} com o estilo **{style}**.", embed=e, ephemeral=True)

    @config_group.command(name="boasvindas_desativar",description="Desativa as mensagens automáticas de boas-vindas")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def boasvindas_desativar(self,interaction):
        await db.set_guild_config(interaction.guild_id,welcome_channel_id=None)
        await interaction.response.send_message("🔕 Boas-vindas automáticas desativadas.",ephemeral=True)

    def _build_welcome_embed(self, guild, member, style, custom_message=None):
        preset = self.WELCOME_PRESETS.get(style, self.WELCOME_PRESETS["kiba"])
        raw = custom_message if custom_message is not None else preset["description"]
        try:
            description = raw.format(membro=member.mention, servidor=guild.name, contagem=guild.member_count or "?")
        except (KeyError, ValueError):
            description = raw.replace("{membro}", member.mention).replace("{servidor}", guild.name).replace("{contagem}", str(guild.member_count or "?"))
        e = KibotEmbed(title=preset["title"], description=description, color=preset["color"], timestamp=discord.utils.utcnow())
        if guild.icon:
            e.set_author(name=f"Novo membro • {guild.name}", icon_url=guild.icon.url)
        else:
            e.set_author(name=f"Novo membro • {guild.name}")
        e.set_thumbnail(url=member.display_avatar.url)
        if guild.icon:
            e.set_footer(text=f"{guild.name} • Obrigado por entrar!", icon_url=guild.icon.url)
        else:
            e.set_footer(text=f"{guild.name} • Obrigado por entrar!")
        return e

    @commands.command(name="boasvindas", aliases=["welcome"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def p_boasvindas(self,ctx,canal:discord.TextChannel,estilo="kiba",*,mensagem=None):
        estilo = estilo.casefold()
        if estilo not in self.WELCOME_PRESETS:
            return await ctx.send("❌ Estilo inválido. Use: `kiba`, `elegante`, `rpg`, `caos` ou `minimalista`.")
        preset=self.WELCOME_PRESETS[estilo]
        await db.set_guild_config(ctx.guild.id,welcome_channel_id=canal.id,welcome_style=estilo,welcome_message=mensagem if mensagem is not None else preset["description"])
        await ctx.send(f"✅ Boas-vindas configuradas em {canal.mention} com o estilo **{estilo}**.", embed=self._build_welcome_embed(ctx.guild,ctx.author,estilo,mensagem))
    @config_group.command(name="autoban_bets",description="Ativa/desativa o ban automático no canal anti-BetSpam")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(canal="Canal de quarentena: qualquer mensagem ou arquivo gera ban automático", ativado="Ativa ou desativa a proteção")
    async def autoban_bets(self,interaction,canal:discord.TextChannel,ativado:bool=True):
        await db.set_guild_config(interaction.guild_id,auto_ban_bets_channel_id=canal.id,auto_ban_bets_enabled=int(ativado))
        if ativado:
            await interaction.response.send_message(
                f"🚨 **Anti-BetSpam ATIVADO** em {canal.mention}.\n"
                "Qualquer mensagem ou arquivo enviado por um usuário comum nesse canal dispara **ban automático** e limpeza do histórico acessível dele no servidor.\n"
                "⚠️ Administradores e quem possui **Gerenciar Servidor** ficam protegidos contra falsos positivos.\n"
                "O Kibot precisa de **Banir membros**, **Gerenciar mensagens** e **Ler histórico** nos canais que deseja limpar.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(f"🔕 Anti-BetSpam desativado para {canal.mention}.",ephemeral=True)

    @config_group.command(name="autoban_bets_off",description="Desativa completamente o Anti-BetSpam")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def autoban_bets_off(self,interaction):
        await db.set_guild_config(interaction.guild_id,auto_ban_bets_enabled=0,auto_ban_bets_channel_id=None)
        await interaction.response.send_message("🔕 **Anti-BetSpam desativado.** Nenhum canal será usado como gatilho de ban automático.",ephemeral=True)

    @commands.command(name="autobanbets",aliases=["antibetspam","betguard"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def p_autoban_bets(self,ctx,canal:discord.TextChannel=None,acao="on"):
        if canal is None:
            cfg=await db.get_guild_config(ctx.guild.id)
            current=ctx.guild.get_channel(cfg["auto_ban_bets_channel_id"]) if cfg["auto_ban_bets_channel_id"] else None
            return await ctx.send(f"🚨 Anti-BetSpam: **{'ATIVO' if cfg['auto_ban_bets_enabled'] else 'INATIVO'}** | Canal: {current.mention if current else 'não configurado'}")
        acao=acao.casefold()
        enabled=acao not in {"off","desativar","desligar","0","false"}
        await db.set_guild_config(ctx.guild.id,auto_ban_bets_channel_id=canal.id,auto_ban_bets_enabled=int(enabled))
        await ctx.send(f"{'🚨 Anti-BetSpam ATIVADO' if enabled else '🔕 Anti-BetSpam desativado'} {'em '+canal.mention if enabled else 'para '+canal.mention}.")

    @config_group.command(name="log",description="Escolhe onde vão cair os logs")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def log(self,interaction,canal:discord.TextChannel):
        await db.set_guild_config(interaction.guild_id,log_channel_id=canal.id)
        await interaction.response.send_message(f"✅ Logs automáticos configurados em {canal.mention}.")
    @commands.command(name="configlog", aliases=["log"])
    @commands.has_permissions(manage_guild=True)
    async def p_log(self,ctx,canal:discord.TextChannel):
        await db.set_guild_config(ctx.guild.id,log_channel_id=canal.id); await ctx.send(f"✅ Logs configurados em {canal.mention}.")

    @config_group.command(name="confirmacao_moderacao",description="Ativa ou desativa confirmações nas ações de moderação")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def confirmacao_moderacao(self,interaction,ativado:bool):
        await db.set_guild_config(interaction.guild_id,moderation_confirmations_enabled=int(ativado))
        await interaction.response.send_message(f"🛡️ Confirmações de moderação **{'ativadas' if ativado else 'desativadas'}**.",ephemeral=True)

    @commands.command(name="configmoderacao",aliases=["confirmarmod","confirmacao"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def p_confirmacao_moderacao(self,ctx,acao="on"):
        ativado=str(acao).lower() not in {"off","desativar","desligar","0","false"}
        await db.set_guild_config(ctx.guild.id,moderation_confirmations_enabled=int(ativado))
        await ctx.send(f"🛡️ Confirmações de moderação **{'ativadas' if ativado else 'desativadas'}**.")

    @config_group.command(name="cargo_mute",description="Escolhe o cargo usado no mute")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def cargo_mute(self,interaction,cargo:discord.Role):
        await db.set_guild_config(interaction.guild_id,mute_role_id=cargo.id); await interaction.response.send_message(f"✅ Cargo de mute: {cargo.mention}.")

    @app_commands.command(name="trancar",description="Tranca ou destranca um canal de texto")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def trancar(self,interaction,canal:discord.TextChannel=None):
        canal=canal or interaction.channel
        everyone=interaction.guild.default_role
        current=canal.permissions_for(everyone).send_messages
        novo=False if current else True
        await canal.set_permissions(everyone,send_messages=novo,reason=f"Trancar/destrancar por {interaction.user}")
        if novo:
            await interaction.response.send_message(f"🔒 {canal.mention} foi **trancado**. Só quem tiver permissão poderá falar.")
        else:
            await interaction.response.send_message(f"🔓 {canal.mention} foi **destrancado**. O canal voltou ao normal.")

    @commands.command(name="trancar",aliases=["lock","travar"])
    @commands.has_permissions(manage_channels=True)
    async def p_trancar(self,ctx,canal:discord.TextChannel=None):
        canal=canal or ctx.channel
        everyone=ctx.guild.default_role
        current=canal.permissions_for(everyone).send_messages
        novo=False if current else True
        await canal.set_permissions(everyone,send_messages=novo,reason=f"Trancar/destrancar por {ctx.author}")
        await ctx.send(f"{'🔒' if novo else '🔓'} {canal.mention} foi **{'trancado' if novo else 'destrancado'}**.")

    @app_commands.command(name="criar_canal",description="Manda criar um canal novo")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def criar_canal(self,interaction,nome:str,categoria:discord.CategoryChannel=None):
        canal=await interaction.guild.create_text_channel(nome,category=categoria); await interaction.response.send_message(f"✅ Canal {canal.mention} criado.")
    @commands.command(name="criar_canal", aliases=["canal", "ccanal"])
    @commands.has_permissions(manage_channels=True)
    async def p_criar_canal(self,ctx,nome):
        canal=await ctx.guild.create_text_channel(nome); await ctx.send(f"✅ Canal {canal.mention} criado.")

    @app_commands.command(name="criar_cargo",description="Manda criar um cargo novo")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def criar_cargo(self,interaction,nome:str,cor_hex:str=None):
        cor=discord.Color.default()
        if cor_hex:
            try: cor=discord.Color(int(cor_hex.replace("#",""),16))
            except ValueError: await interaction.response.send_message("❌ Essa cor aí não tá no formato certo.",ephemeral=True); return
        cargo=await interaction.guild.create_role(name=nome,color=cor); await interaction.response.send_message(f"✅ Cargo {cargo.mention} criado.")
    @commands.command(name="criar_cargo", aliases=["cargo", "ccargo"])
    @commands.has_permissions(manage_roles=True)
    async def p_criar_cargo(self,ctx,nome,cor_hex=None):
        cor=discord.Color.default()
        if cor_hex:
            try: cor=discord.Color(int(cor_hex.replace("#",""),16))
            except ValueError: await ctx.send("❌ Essa cor aí não tá no formato certo."); return
        cargo=await ctx.guild.create_role(name=nome,color=cor); await ctx.send(f"✅ Cargo {cargo.mention} criado.")

    @app_commands.command(name="cargo_add",description="Dá um cargo pra alguém")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def cargo_add(self,interaction,membro:discord.Member,cargo:discord.Role,cargo2:discord.Role=None,cargo3:discord.Role=None,cargo4:discord.Role=None,cargo5:discord.Role=None):
        roles=tuple(r for r in (cargo,cargo2,cargo3,cargo4,cargo5) if r is not None)
        me=interaction.guild.me
        invalid=[r for r in roles if r.is_default() or r.managed or r>=me.top_role]
        if invalid:
            return await interaction.response.send_message("❌ Não consigo gerenciar um ou mais desses cargos. Deixe o cargo do Kibot acima deles.",ephemeral=True)
        await membro.add_roles(*roles,reason=f"Cargo(s) adicionado(s) por {interaction.user}")
        await interaction.response.send_message(f"✅ {len(roles)} cargo(s) adicionado(s) a {membro.mention}: {' '.join(r.mention for r in roles)}")
    @commands.command(name="cargo_add", aliases=["addcargo", "addrole"])
    @commands.has_permissions(manage_roles=True)
    async def p_cargo_add(self,ctx,membro:discord.Member,cargos:commands.Greedy[discord.Role]):
        if not cargos:
            await ctx.send("❌ Informe pelo menos um cargo. Ex.: `K! cargo_add @Membro @Cargo1 @Cargo2`")
            return
        me=ctx.guild.me
        invalid=[r for r in cargos if r.is_default() or r.managed or r>=me.top_role]
        if invalid:
            await ctx.send("❌ Não consigo gerenciar um ou mais desses cargos. Deixe o cargo do Kibot acima deles.")
            return
        await membro.add_roles(*cargos,reason=f"Cargo(s) adicionado(s) por {ctx.author}")
        await ctx.send(f"✅ {len(cargos)} cargo(s) adicionado(s) a {membro.mention}: {' '.join(r.mention for r in cargos)}")

    @app_commands.command(name="cargo_remover",description="Tira um cargo de alguém")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def cargo_remover(self,interaction,membro:discord.Member,cargo:discord.Role,cargo2:discord.Role=None,cargo3:discord.Role=None,cargo4:discord.Role=None,cargo5:discord.Role=None):
        roles=tuple(r for r in (cargo,cargo2,cargo3,cargo4,cargo5) if r is not None)
        me=interaction.guild.me
        invalid=[r for r in roles if r.is_default() or r.managed or r>=me.top_role]
        if invalid:
            return await interaction.response.send_message("❌ Não consigo gerenciar um ou mais desses cargos. Deixe o cargo do Kibot acima deles.",ephemeral=True)
        await membro.remove_roles(*roles,reason=f"Cargo(s) removido(s) por {interaction.user}")
        await interaction.response.send_message(f"✅ {len(roles)} cargo(s) removido(s) de {membro.mention}: {' '.join(r.mention for r in roles)}")
    @commands.command(name="cargo_remover", aliases=["rmcargo", "delcargo", "delrole"])
    @commands.has_permissions(manage_roles=True)
    async def p_cargo_remover(self,ctx,membro:discord.Member,cargos:commands.Greedy[discord.Role]):
        if not cargos:
            await ctx.send("❌ Informe pelo menos um cargo. Ex.: `K! cargo_remover @Membro @Cargo1 @Cargo2`")
            return
        await membro.remove_roles(*cargos,reason=f"Cargo(s) removido(s) por {ctx.author}")
        await ctx.send(f"✅ {len(cargos)} cargo(s) removido(s) de {membro.mention}: {' '.join(r.mention for r in cargos)}")

    async def _promote(self, ctx, membro: discord.Member, direction: int):
        actor = ctx.author
        if membro == actor or membro.bot and membro == self.bot.user:
            await ctx.send("❌ Não consigo mexer nesse membro.")
            return
        if actor.id != ctx.guild.owner_id and membro.top_role >= actor.top_role:
            await ctx.send("❌ O cargo dessa pessoa é igual ou maior que o seu, aí não rola.")
            return
        me = ctx.guild.me
        manageable = [r for r in ctx.guild.roles if not r.is_default() and not r.managed and r < me.top_role]
        if direction > 0:
            candidates = [r for r in manageable if r > membro.top_role]
            target = min(candidates, key=lambda r: r.position) if candidates else None
            action = "promovido"
        else:
            candidates = [r for r in manageable if r < membro.top_role]
            target = max(candidates, key=lambda r: r.position) if candidates else None
            action = "rebaixado"
        if target is None:
            await ctx.send("❌ Não existe um cargo gerenciável acima/abaixo do cargo atual.")
            return
        old = membro.top_role if membro.top_role != ctx.guild.default_role else None
        if old and old < me.top_role and old in membro.roles:
            await membro.remove_roles(old, reason=f"{action} por {actor}")
        await membro.add_roles(target, reason=f"{action} por {actor}")
        await ctx.send(f"✅ {membro.mention} foi **{action}** para {target.mention}.")
        await log_action(ctx.guild, f"📈 Membro {action}", f"**Membro:** {membro.mention}\n**Moderador:** {actor.mention}\n**Cargo:** {target.mention}", discord.Color.green() if direction > 0 else discord.Color.orange())

    @commands.command(name="up", aliases=["promote", "promover"])
    @commands.has_permissions(manage_roles=True)
    async def p_up(self, ctx, membro: discord.Member):
        await self._promote(ctx, membro, 1)

    @commands.command(name="demote", aliases=["down", "rebaixar"])
    @commands.has_permissions(manage_roles=True)
    async def p_demote(self, ctx, membro: discord.Member):
        await self._promote(ctx, membro, -1)

    @app_commands.command(name="anunciar",description="Manda um anúncio no canal")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def anunciar(self,interaction,canal:discord.TextChannel,mensagem:str):
        e=KibotEmbed(description=mensagem,color=discord.Color.blurple()); e.set_author(name=f"Anúncio de {interaction.user.display_name}",icon_url=interaction.user.display_avatar.url)
        await canal.send(embed=e); await interaction.response.send_message(f"✅ Anúncio enviado em {canal.mention}.",ephemeral=True)

    @app_commands.command(name="info_servidor",description="Dá umas infos do servidor")
    async def info_servidor(self,interaction):
        g=interaction.guild; e=KibotEmbed(title=g.name,color=discord.Color.blurple())
        if g.icon:e.set_thumbnail(url=g.icon.url)
        e.add_field(name="Dono",value=str(g.owner),inline=True); e.add_field(name="Membros",value=str(g.member_count),inline=True)
        e.add_field(name="Cargos",value=str(len(g.roles)),inline=True); e.add_field(name="Texto",value=str(len(g.text_channels)),inline=True); e.add_field(name="Voz",value=str(len(g.voice_channels)),inline=True)
        await interaction.response.send_message(embed=e)

    @commands.Cog.listener()
    async def on_member_join(self,member):
        cfg=await db.get_guild_config(member.guild.id)
        if cfg["welcome_channel_id"]:
            canal=member.guild.get_channel(cfg["welcome_channel_id"])
            if canal:
                style=cfg["welcome_style"] or "kiba"
                try:
                    e=self._build_welcome_embed(member.guild,member,style,cfg["welcome_message"])
                    await canal.send(embed=e)
                except discord.HTTPException:
                    # Fallback para configurações antigas ou embeds bloqueadas.
                    try:
                        await canal.send((cfg["welcome_message"] or "Bem-vindo(a), {membro}! 🎉").format(membro=member.mention,servidor=member.guild.name,contagem=member.guild.member_count or "?"))
                    except discord.HTTPException:
                        pass
    @commands.Cog.listener()
    async def on_member_remove(self,member):
        await log_action(member.guild,"👋 Membro saiu","**Membro:** %s (`%s`)"%(member,member.id),discord.Color.dark_gray())

async def setup(bot): await bot.add_cog(Management(bot))
