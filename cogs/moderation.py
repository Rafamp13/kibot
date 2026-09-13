from cogs.embed_style import KibotEmbed
from datetime import timedelta
import discord
from discord.ext import commands
from discord import app_commands
from database import db
from cogs.utils import send, log_action


class ModerationConfirmView(discord.ui.View):
    def __init__(self, author_id, timeout=30):
        super().__init__(timeout=timeout); self.author_id=author_id; self.confirmed=False
    async def interaction_check(self,interaction):
        if interaction.user.id!=self.author_id:
            await interaction.response.send_message("🔒 Essa confirmação não é sua.",ephemeral=True); return False
        return True
    @discord.ui.button(label="Confirmar",style=discord.ButtonStyle.danger,emoji="⚠️")
    async def confirm(self,interaction,button):
        self.confirmed=True
        for b in self.children: b.disabled=True
        await interaction.response.edit_message(content="⏳ Confirmado. Executando a ação...",view=self); self.stop()
    @discord.ui.button(label="Cancelar",style=discord.ButtonStyle.secondary,emoji="✖️")
    async def cancel(self,interaction,button):
        self.confirmed=False
        for b in self.children: b.disabled=True
        await interaction.response.edit_message(content="❌ Ação cancelada.",view=self); self.stop()

async def confirm_moderation(ctx,prompt):
    cfg=await db.get_guild_config(ctx.guild.id)
    if not bool(cfg["moderation_confirmations_enabled"]): return True
    actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
    view=ModerationConfirmView(actor.id)
    if isinstance(ctx,discord.Interaction): await ctx.response.send_message(prompt,view=view,ephemeral=True)
    else: await ctx.send(prompt,view=view)
    await view.wait(); return view.confirmed

class Moderation(commands.Cog):
    def __init__(self,bot): self.bot=bot

    async def _kick(self,ctx,membro,motivo):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if not await confirm_moderation(ctx,f"⚠️ Confirmar **EXPULSÃO** de {membro.mention}?\nMotivo: {motivo}"): return
        if membro.top_role>=actor.top_role and actor.id!=ctx.guild.owner_id:
            await send(ctx,"❌ Não dá pra expulsar essa pessoa com sua permissão/cargo.",ephemeral=True); return
        await membro.kick(reason=f"{motivo} | Por: {actor}")
        await send(ctx,f"👢 {membro.mention} foi expulso. Motivo: {motivo}")
        await log_action(ctx.guild,"👢 Membro expulso",f"**Membro:** {membro} (`{membro.id}`)\n**Moderador:** {actor.mention}\n**Motivo:** {motivo}",discord.Color.orange())

    @app_commands.command(name="kick",description="Expulsa alguém do servidor")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self,interaction,membro:discord.Member,motivo:str="Não especificado"): await self._kick(interaction,membro,motivo)

    @commands.command(name="kick",aliases=["k", "expulsar"])
    @commands.has_permissions(kick_members=True)
    async def p_kick(self,ctx,membro:discord.Member,*,motivo="Não especificado"): await self._kick(ctx,membro,motivo)

    async def _ban(self,ctx,membro,motivo):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if not await confirm_moderation(ctx,f"⚠️ Confirmar **BANIMENTO** de {membro.mention}?\nMotivo: {motivo}"): return
        if membro.top_role>=actor.top_role and actor.id!=ctx.guild.owner_id:
            await send(ctx,"❌ Não dá pra banir essa pessoa com seu cargo.",ephemeral=True); return
        await membro.ban(reason=f"{motivo} | Por: {actor}")
        await send(ctx,f"🔨 {membro.mention} foi banido. Motivo: {motivo}")
        await log_action(ctx.guild,"🔨 Membro banido",f"**Membro:** {membro} (`{membro.id}`)\n**Moderador:** {actor.mention}\n**Motivo:** {motivo}",discord.Color.red())

    @app_commands.command(name="ban",description="Manda alguém pro ban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self,interaction,membro:discord.Member,motivo:str="Não especificado"): await self._ban(interaction,membro,motivo)
    @commands.command(name="ban",aliases=["b"])
    @commands.has_permissions(ban_members=True)
    async def p_ban(self,ctx,membro:discord.Member,*,motivo="Não especificado"): await self._ban(ctx,membro,motivo)

    async def _unban(self,ctx,user_id):
        if not await confirm_moderation(ctx,f"⚠️ Confirmar **DESBANIMENTO** do ID `{user_id}`?"): return
        try:
            uid=int(user_id); await ctx.guild.unban(discord.Object(id=uid))
            await send(ctx,f"✅ Usuário `{uid}` foi desbanido.")
            await log_action(ctx.guild,"🔓 Usuário desbanido",f"**Usuário ID:** `{uid}`\n**Moderador:** {(ctx.user if isinstance(ctx,discord.Interaction) else ctx.author).mention}",discord.Color.green())
        except (ValueError,discord.NotFound): await send(ctx,"❌ Esse ID tá errado ou a pessoa nem tá banida.",ephemeral=True)
    @app_commands.command(name="unban",description="Tira o ban usando o ID")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self,interaction,user_id:str): await self._unban(interaction,user_id)
    @commands.command(name="unban",aliases=["ub"])
    @commands.has_permissions(ban_members=True)
    async def p_unban(self,ctx,user_id:str): await self._unban(ctx,user_id)

    async def _timeout(self,ctx,membro,minutos,motivo):
        if minutos<=0 or minutos>40320: await send(ctx,"❌ Usa um tempo entre 1 e 40320 minutos, chefia.",ephemeral=True); return
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if not await confirm_moderation(ctx,f"⚠️ Confirmar **TIMEOUT** de {membro.mention} por {minutos} min?\nMotivo: {motivo}"): return
        await membro.timeout(discord.utils.utcnow()+timedelta(minutes=minutos),reason=motivo)
        await send(ctx,f"🔇 {membro.mention} foi silenciado por **{minutos} min**. Motivo: {motivo}")
        await log_action(ctx.guild,"🔇 Timeout aplicado",f"**Membro:** {membro.mention}\n**Moderador:** {actor.mention}\n**Duração:** {minutos} min\n**Motivo:** {motivo}",discord.Color.orange())
    @app_commands.command(name="mutar",description="Dá mute em alguém")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def mutar(self,interaction,membro:discord.Member,minutos:int,motivo:str="Não especificado"): await self._timeout(interaction,membro,minutos,motivo)
    @commands.command(name="mutar",aliases=["mute", "timeout"])
    @commands.has_permissions(moderate_members=True)
    async def p_mute(self,ctx,membro:discord.Member,minutos:int,*,motivo="Não especificado"): await self._timeout(ctx,membro,minutos,motivo)

    async def _unmute(self,ctx,membro):
        if not await confirm_moderation(ctx,f"⚠️ Confirmar **REMOÇÃO DO TIMEOUT** de {membro.mention}?"): return
        await membro.timeout(None)
        await send(ctx,f"🔊 {membro.mention} não está mais silenciado.")
        await log_action(ctx.guild,"🔊 Timeout removido",f"**Membro:** {membro.mention}\n**Moderador:** {(ctx.user if isinstance(ctx,discord.Interaction) else ctx.author).mention}",discord.Color.green())
    @app_commands.command(name="desmutar",description="Tira o mute/timeout de alguém")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def desmutar(self,interaction,membro:discord.Member): await self._unmute(interaction,membro)
    @commands.command(name="desmutar",aliases=["unmute", "untimeout"])
    @commands.has_permissions(moderate_members=True)
    async def p_unmute(self,ctx,membro:discord.Member): await self._unmute(ctx,membro)

    async def _warn(self,ctx,membro,motivo):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if not await confirm_moderation(ctx,f"⚠️ Confirmar **ADVERTÊNCIA** para {membro.mention}?\nMotivo: {motivo}"): return
        await db.add_warning(membro.id,ctx.guild.id,actor.id,motivo)
        total=len(await db.get_warnings(membro.id,ctx.guild.id))
        await send(ctx,f"⚠️ {membro.mention} recebeu uma advertência (**{total}** no total). Motivo: {motivo}")
        await log_action(ctx.guild,"⚠️ Advertência",f"**Membro:** {membro.mention}\n**Moderador:** {actor.mention}\n**Motivo:** {motivo}",discord.Color.yellow())
    @app_commands.command(name="advertir",description="Dá uma advertência pra alguém")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def advertir(self,interaction,membro:discord.Member,motivo:str): await self._warn(interaction,membro,motivo)
    @commands.command(name="advertir",aliases=["warn", "w"])
    @commands.has_permissions(moderate_members=True)
    async def p_warn(self,ctx,membro:discord.Member,*,motivo): await self._warn(ctx,membro,motivo)

    async def _show_warnings(self,ctx,membro):
        guild_id=ctx.guild_id if isinstance(ctx,discord.Interaction) else ctx.guild.id
        avisos=await db.get_warnings(membro.id,guild_id)
        e=KibotEmbed(title=f"Advertências de {membro.display_name}",color=discord.Color.orange())
        for i,a in enumerate(avisos,1):
            e.add_field(name=f"#{i}",value=f"Motivo: {a['reason']}\nModerador: <@{a['moderator_id']}>",inline=False)
        if isinstance(ctx,discord.Interaction):
            await ctx.response.send_message(embed=e if avisos else KibotEmbed(description=f"{membro.mention} não tem advertências."))
        else:
            await ctx.send(embed=e if avisos else KibotEmbed(description=f"{membro.mention} não tem advertências."))

    @app_commands.command(name="advertencias",description="Vê as advertências de alguém")
    async def advertencias(self,interaction,membro:discord.Member):
        await self._show_warnings(interaction,membro)

    @commands.command(name="advertencias",aliases=["advertencia","avisos","warnings","warns"])
    async def p_advertencias(self,ctx,membro:discord.Member):
        await self._show_warnings(ctx,membro)

    @app_commands.command(name="limpar_advertencias",description="Apaga todas as advertências de alguém")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def limpar_advertencias(self,interaction,membro:discord.Member):
        if not await confirm_moderation(interaction,f"⚠️ Confirmar **LIMPEZA DE ADVERTÊNCIAS** de {membro.mention}?"): return
        await db.clear_warnings(membro.id,interaction.guild_id); await interaction.response.send_message(f"🧹 Advertências de {membro.mention} foram limpas.")
        await log_action(interaction.guild,"🧹 Advertências limpas",f"**Membro:** {membro.mention}\n**Moderador:** {interaction.user.mention}",discord.Color.orange())

    @commands.command(name="limpar_advertencias",aliases=["limparadvertencias", "clearwarnings", "clearwarns"])
    @commands.guild_only()
    @commands.has_permissions(moderate_members=True)
    async def p_limpar_advertencias(self,ctx,membro:discord.Member):
        if not await confirm_moderation(ctx,f"⚠️ Confirmar **LIMPEZA DE ADVERTÊNCIAS** de {membro.mention}?"): return
        await db.clear_warnings(membro.id,ctx.guild.id)
        await ctx.send(f"🧹 Advertências de {membro.mention} foram limpas.")
        await log_action(ctx.guild,"🧹 Advertências limpas",f"**Membro:** {membro.mention}\n**Moderador:** {ctx.author.mention}",discord.Color.orange())

    @app_commands.command(name="limpar",description="Apaga até 100 mensagens de uma vez")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def limpar(self,interaction,quantidade:app_commands.Range[int,1,100]):
        if not await confirm_moderation(interaction,f"⚠️ Confirmar exclusão de **{quantidade} mensagens** neste canal?"): return
        apagadas=await interaction.channel.purge(limit=quantidade)
        await interaction.followup.send(f"🧹 {len(apagadas)} mensagens apagadas.",ephemeral=True)
        await log_action(interaction.guild,"🧹 Mensagens apagadas",f"**Moderador:** {interaction.user.mention}\n**Canal:** {interaction.channel.mention}\n**Quantidade:** {len(apagadas)}",discord.Color.orange())
    @commands.command(name="limpar",aliases=["clear", "clean", "purge"])
    @commands.has_permissions(manage_messages=True)
    async def p_clear(self,ctx,quantidade:int):
        quantidade=max(1,min(100,quantidade));
        if not await confirm_moderation(ctx,f"⚠️ Confirmar exclusão de **{quantidade} mensagens** neste canal?"): return
        apagadas=await ctx.channel.purge(limit=quantidade); await ctx.send(f"🧹 {len(apagadas)} mensagens apagadas.")
        await log_action(ctx.guild,"🧹 Mensagens apagadas",f"**Moderador:** {ctx.author.mention}\n**Canal:** {ctx.channel.mention}\n**Quantidade:** {len(apagadas)}",discord.Color.orange())

    @app_commands.command(name="slowmode",description="Liga, desliga ou muda o slowmode")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self,interaction,segundos:app_commands.Range[int,0,21600]):
        if not await confirm_moderation(interaction,f"⚠️ Confirmar alteração do **slowmode** para {segundos}s?"): return
        await interaction.channel.edit(slowmode_delay=segundos); await send(interaction,"✅ Modo lento desativado." if segundos==0 else f"🐌 Modo lento: {segundos}s.")
        await log_action(interaction.guild,"🐌 Slowmode alterado",f"**Moderador:** {interaction.user.mention}\n**Canal:** {interaction.channel.mention}\n**Valor:** {segundos}s",discord.Color.blurple())
    @commands.command(name="slowmode",aliases=["slow"])
    @commands.has_permissions(manage_channels=True)
    async def p_slowmode(self,ctx,segundos:int):
        segundos=max(0,min(21600,segundos));
        if not await confirm_moderation(ctx,f"⚠️ Confirmar alteração do **slowmode** para {segundos}s?"): return
        await ctx.channel.edit(slowmode_delay=segundos); await ctx.send("✅ Modo lento atualizado.")

async def setup(bot): await bot.add_cog(Moderation(bot))
