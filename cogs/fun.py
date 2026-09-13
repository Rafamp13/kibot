from cogs.embed_style import KibotEmbed
import random
import re
import discord
from discord.ext import commands
from discord import app_commands
from database import db
import config
from cogs.utils import set_anime_gif

RESPOSTAS_8BALL=[
    "Com certeza sim.", "Sem dúvida.", "Provavelmente.", "Perspectiva boa.",
    "Pergunte novamente mais tarde.", "Resposta nebulosa.", "Melhor não contar agora.",
    "Não conte com isso.", "Minha resposta é não.", "Muito duvidoso."
]

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _media(self, channel, guild=None, category="happy"):
        e = KibotEmbed()
        if await set_anime_gif(e, category):
            await channel.send(embed=e)
        stickers = list(guild.stickers) if guild else []
        if stickers:
            try:
                await channel.send(stickers=[random.choice(stickers)])
            except discord.HTTPException:
                pass

    @app_commands.command(name="8ball", description="Pergunta aí pro 8ball")
    async def oitobola(self, interaction: discord.Interaction, pergunta: str):
        e = KibotEmbed(color=discord.Color.purple())
        e.add_field(name="🎱 Pergunta", value=pergunta, inline=False)
        e.add_field(name="Resposta", value=random.choice(RESPOSTAS_8BALL), inline=False)
        await interaction.response.send_message(embed=e)
        await self._media(interaction.channel, interaction.guild, "think")

    @commands.command(name="8ball", aliases=["bola", "8b"])
    async def p_8ball(self, ctx: commands.Context, *, pergunta: str):
        await ctx.send(f"🎱 **{random.choice(RESPOSTAS_8BALL)}**")
        await self._media(ctx.channel, ctx.guild, "think")

    @app_commands.command(name="moeda", description="Joga uma moedinha")
    async def moeda(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 Deu **{random.choice(['Cara','Coroa'])}**!")
        await self._media(interaction.channel, interaction.guild, "spin")

    @commands.command(name="moeda", aliases=["coin", "flip"])
    async def p_moeda(self, ctx: commands.Context):
        await ctx.send(f"🪙 Deu **{random.choice(['Cara','Coroa'])}**!")
        await self._media(ctx.channel, ctx.guild, "spin")


    @app_commands.command(name="ship", description="Descobre o nível de química entre duas pessoas")
    async def ship(self, interaction: discord.Interaction, pessoa1: discord.Member, pessoa2: discord.Member):
        rng = random.Random(pessoa1.id + pessoa2.id)
        p = rng.randint(0, 100)
        full = "❤️" * (p // 10)
        empty = "🖤" * (10 - p // 10)
        e=KibotEmbed(title="💘 Compatibilidade", description=f"{pessoa1.mention} + {pessoa2.mention}\n{full}{empty}\n**{p}%**", color=discord.Color.pink())
        await set_anime_gif(e, "blush" if p >= 50 else "nope")
        await interaction.response.send_message(embed=e)

    @commands.command(name="ship", aliases=["compat", "shipar"])
    async def p_ship(self, ctx: commands.Context, pessoa1: discord.Member, pessoa2: discord.Member):
        rng = random.Random(pessoa1.id + pessoa2.id)
        p = rng.randint(0, 100)
        e=KibotEmbed(title="💘 Compatibilidade",description=f"{pessoa1.mention} + {pessoa2.mention} = **{p}%**",color=discord.Color.pink())
        await set_anime_gif(e, "blush" if p >= 50 else "nope")
        await ctx.send(embed=e)

    @app_commands.command(name="avatar", description="Dá uma olhada no avatar de alguém")
    async def avatar(self, interaction: discord.Interaction, usuario: discord.Member = None):
        alvo = usuario or interaction.user
        e = KibotEmbed(title=f"Avatar de {alvo.display_name}", color=discord.Color.blurple())
        e.set_image(url=alvo.display_avatar.url)
        await interaction.response.send_message(embed=e)

    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def p_avatar(self, ctx: commands.Context, usuario: discord.Member = None):
        alvo = usuario or ctx.author
        e = KibotEmbed(title=f"Avatar de {alvo.display_name}", color=discord.Color.blurple())
        e.set_image(url=alvo.display_avatar.url)
        await ctx.send(embed=e)

    @app_commands.command(name="enquete", description="Monta uma enquete rapidinha")
    async def enquete(self, interaction: discord.Interaction, pergunta: str):
        e = KibotEmbed(title="📊 Enquete", description=pergunta, color=discord.Color.blue())
        e.set_footer(text=f"Criada por {interaction.user.display_name}")
        await interaction.response.send_message(embed=e)
        msg = await interaction.original_response()
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

    @commands.command(name="enquete", aliases=["poll", "votar"])
    async def p_poll(self, ctx: commands.Context, *, pergunta: str):
        msg = await ctx.send(embed=KibotEmbed(title="📊 Enquete", description=pergunta, color=discord.Color.blue()))
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")




    async def _social(self,ctx,target,action,verb,emoji):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if target.bot or target.id==actor.id:
            msg="❌ Escolhe outra pessoa. Eu me recuso a validar esse caos kkkkk."
            return await (ctx.response.send_message(msg,ephemeral=True) if isinstance(ctx,discord.Interaction) else ctx.send(msg))
        rewards={"beijar":(50,10),"abracar":(50,10),"cafune":(75,15),"tapa":(75,15),"socar":(100,20)}
        failures={
            "beijar":["💋 **Eita! Beijo no vácuo!** A pessoa virou o rosto na última hora e tu beijou o puro ar, betinha!!!","💋 **RECUSADO!** O alvo colocou a mão na frente. Hoje não tem beijinho pra tu."],
            "abracar":["🤗 **Eita! Abraço fantasma!** A pessoa saiu andando e tu abraçou o vento. Que fase, betinha!!!","🤗 **DESVIADA ÉPICA!** O guri escapou do teu abraço e não sobrou nem um tapinha nas costas."],
            "cafune":["🫳 **Eita! Cabeça protegida!** O alvo abaixou a cabeça e teu cafuné encontrou o nada.","🫳 **FALHA CRÍTICA!** Tu tentou fazer cafuné e a pessoa simplesmente se afastou. Trágico."],
            "tapa":["🖐️ **Eita! Desviada Épica!** O guri desviou de tu e não sobrou nada, betinha!!!","🖐️ **QUE VERGONHA!** Tu armou o tapa, mas acertou foi o vento. O alvo saiu ileso."],
            "socar":["👊 **Eita! Esquivada Lendária!** O alvo desviou do soco e tu ficou socando o ar, campeão.","👊 **FALHOU FEIO!** O golpe passou longe. Hoje o boxe ficou para amanhã."],
        }
        success_chance={"beijar":0.80,"abracar":0.82,"cafune":0.78,"tapa":0.70,"socar":0.65}
        gif_success={"beijar":"kiss","abracar":"hug","cafune":"pat","tapa":"slap","socar":"punch"}
        first=await db.record_routine_action(actor.id,ctx.guild.id,action)
        if first and random.random() > success_chance.get(action,0.75):
            fail=random.choice(failures[action])
            e=KibotEmbed(title=f"{emoji} {action.upper()} — FALHOU",description=f"{fail}\n📋 **Rotina:** tentativa registrada, mas **sem recompensa** desta vez.",color=discord.Color.red())
            await set_anime_gif(e,"run" if action in {"tapa","socar"} else "nope")
            return await (ctx.response.send_message(embed=e) if isinstance(ctx,discord.Interaction) else ctx.send(embed=e))
        if first:
            crw,xp=rewards[action]
            from cogs.utils import async_boosted_crw
            crw=await async_boosted_crw(actor,crw); await db.update_balance(actor.id,ctx.guild.id,crw); await db.add_xp(actor.id,ctx.guild.id,xp)
            extra=f"\n📋 **Rotina concluída:** +**{crw} CRW** • +**{xp} XP**"
        else:
            extra="\n📋 Essa tarefa da rotina **já foi tentada hoje**. Sem recompensa extra."
        e=KibotEmbed(title=f"{emoji} {action.upper()}",description=f"{actor.mention} {verb} {target.mention}!{extra}",color=discord.Color.purple())
        await set_anime_gif(e,gif_success[action])
        return await (ctx.response.send_message(embed=e) if isinstance(ctx,discord.Interaction) else ctx.send(embed=e))

    async def _proposal(self,ctx,target,relation):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if target.bot or target.id==actor.id: return await (ctx.response.send_message("❌ Escolhe outra pessoa.",ephemeral=True) if isinstance(ctx,discord.Interaction) else ctx.send("❌ Escolhe outra pessoa."))
        existing=await db.get_relationship(ctx.guild.id,actor.id)
        if existing: return await (ctx.response.send_message("❌ Você já está em um relacionamento.",ephemeral=True) if isinstance(ctx,discord.Interaction) else ctx.send("❌ Você já está em um relacionamento."))
        if await db.get_relationship(ctx.guild.id,target.id): return await (ctx.response.send_message("❌ Essa pessoa já está em um relacionamento.",ephemeral=True) if isinstance(ctx,discord.Interaction) else ctx.send("❌ Essa pessoa já está em um relacionamento."))
        relation_word="casamento" if relation=="married" else "namoro"
        cog=self
        class Proposal(discord.ui.View):
            def __init__(self): super().__init__(timeout=60); self.message=None
            @discord.ui.button(label="Aceitar",style=discord.ButtonStyle.success,emoji="💚")
            async def yes(self,interaction,button):
                if interaction.user.id!=target.id: return await interaction.response.send_message("🔒 Só a pessoa convidada pode responder.",ephemeral=True)
                await db.set_relationship(ctx.guild.id,actor.id,target.id,relation)
                for b in self.children: b.disabled=True
                await interaction.response.edit_message(content=f"💞 **ACEITO!** {actor.mention} e {target.mention} agora estão em **{relation_word}**!",view=self)
            @discord.ui.button(label="Recusar",style=discord.ButtonStyle.danger,emoji="💔")
            async def no(self,interaction,button):
                if interaction.user.id!=target.id: return await interaction.response.send_message("🔒 Só a pessoa convidada pode responder.",ephemeral=True)
                for b in self.children: b.disabled=True
                await interaction.response.edit_message(content=f"💔 {target.mention} recusou o pedido de {relation_word}.",view=self)
        msg=f"💌 {target.mention}, **{actor.display_name}** quer entrar em **{relation_word}** com você!"
        result = await (ctx.response.send_message(msg,view=Proposal()) if isinstance(ctx,discord.Interaction) else ctx.send(msg,view=Proposal()))
        try:
            channel = ctx.channel
            e = KibotEmbed()
            await set_anime_gif(e, "blush")
            await channel.send(embed=e)
        except discord.HTTPException:
            pass
        return result

    @app_commands.command(name="namorar",description="Faz uma proposta de namoro")
    async def namorar(self,interaction,target:discord.Member): await self._proposal(interaction,target,"dating")
    @commands.command(name="namorar",aliases=["namoro"])
    async def p_namorar(self,ctx,target:discord.Member): await self._proposal(ctx,target,"dating")

    @app_commands.command(name="casamento",description="Faz uma proposta de casamento")
    async def casamento(self,interaction,target:discord.Member):
        rel=await db.get_relationship(interaction.guild.id,interaction.user.id)
        if not rel or rel["relation_type"]!="dating": return await interaction.response.send_message("💍 Primeiro vocês precisam estar namorando.",ephemeral=True)
        # Proposal only to current partner, then upgrades to married.
        partner=rel["user2_id"] if int(rel["user1_id"])==interaction.user.id else rel["user1_id"]
        if target.id!=int(partner): return await interaction.response.send_message("💍 O casamento precisa ser com seu atual parceiro.",ephemeral=True)
        await db.delete_relationship(interaction.guild.id,interaction.user.id,target.id); await self._proposal(interaction,target,"married")
    @commands.command(name="casamento",aliases=["casar"])
    async def p_casamento(self,ctx,target:discord.Member):
        rel=await db.get_relationship(ctx.guild.id,ctx.author.id)
        if not rel or rel["relation_type"]!="dating": return await ctx.send("💍 Primeiro vocês precisam estar namorando.")
        partner=rel["user2_id"] if int(rel["user1_id"])==ctx.author.id else rel["user1_id"]
        if target.id!=int(partner): return await ctx.send("💍 O casamento precisa ser com seu atual parceiro.")
        await db.delete_relationship(ctx.guild.id,ctx.author.id,target.id); await self._proposal(ctx,target,"married")

    @app_commands.command(name="beijar",description="Dá um beijo em alguém")
    async def beijar(self,interaction,target:discord.Member): await self._social(interaction,target,"beijar","deu um beijo em","💋")
    @commands.command(name="beijar")
    async def p_beijar(self,ctx,target:discord.Member): await self._social(ctx,target,"beijar","deu um beijo em","💋")

    @app_commands.command(name="abracar",description="Abraça alguém")
    async def abracar(self,interaction,target:discord.Member): await self._social(interaction,target,"abracar","abraçou","🤗")
    @commands.command(name="abracar",aliases=["abraçar"])
    async def p_abracar(self,ctx,target:discord.Member): await self._social(ctx,target,"abracar","abraçou","🤗")

    @app_commands.command(name="cafune",description="Faz cafuné em alguém")
    async def cafune(self,interaction,target:discord.Member): await self._social(interaction,target,"cafune","fez cafuné em","🫳")
    @commands.command(name="cafune",aliases=["cafuné"])
    async def p_cafune(self,ctx,target:discord.Member): await self._social(ctx,target,"cafune","fez cafuné em","🫳")

    @app_commands.command(name="tapa",description="Dá um tapa em alguém")
    async def tapa(self,interaction,target:discord.Member): await self._social(interaction,target,"tapa","deu um tapa em","🖐️")
    @commands.command(name="tapa")
    async def p_tapa(self,ctx,target:discord.Member): await self._social(ctx,target,"tapa","deu um tapa em","🖐️")

    @app_commands.command(name="socar",description="Dá um soco em alguém")
    async def socar(self,interaction,target:discord.Member): await self._social(interaction,target,"socar","deu um soco em","👊")
    @commands.command(name="socar",aliases=["soco"])
    async def p_socar(self,ctx,target:discord.Member): await self._social(ctx,target,"socar","deu um soco em","👊")

    async def _divorce(self,ctx):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author; rel=await db.get_relationship(ctx.guild.id,actor.id)
        if not rel: return await (ctx.response.send_message("❌ Você não está em um relacionamento.",ephemeral=True) if isinstance(ctx,discord.Interaction) else ctx.send("❌ Você não está em um relacionamento."))
        partner=rel["user2_id"] if int(rel["user1_id"])==actor.id else rel["user1_id"]; await db.delete_relationship(ctx.guild.id,actor.id,partner)
        msg="💔 Relacionamento encerrado. O advogado do divórcio já foi chamado."
        e=KibotEmbed(description=msg,color=discord.Color.red()); await set_anime_gif(e,"cry")
        return await (ctx.response.send_message(embed=e) if isinstance(ctx,discord.Interaction) else ctx.send(embed=e))
    @app_commands.command(name="divorciar",description="Encerra seu relacionamento")
    async def divorciar(self,interaction): await self._divorce(interaction)
    @commands.command(name="divorciar",aliases=["divorcio"])
    async def p_divorciar(self,ctx): await self._divorce(ctx)

    ROUTINE=[("beijar","💋 Beijar alguém",50,10),("abracar","🤗 Abraçar alguém",50,10),("cafune","🫳 Fazer cafuné",75,15),("tapa","🖐️ Dar um tapa",75,15),("socar","👊 Dar um soco",100,20)]
    async def _routine(self,ctx):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author; done=await db.routine_actions(actor.id,ctx.guild.id)
        lines=[f"{'✅' if k in done else '⬜'} {label} — **+{crw} CRW / +{xp} XP**" for k,label,crw,xp in self.ROUTINE]
        e=KibotEmbed(title="📋 ROTINA DIÁRIA",description="Complete cada interação uma vez por dia. **Cada tarefa tem chance de falhar**, e uma falha consome a tentativa do dia sem pagar CRW/XP.\n\n"+'\n'.join(lines),color=discord.Color.purple())
        e.add_field(name="Progresso",value=f"**{len(done & {x[0] for x in self.ROUTINE})}/{len(self.ROUTINE)}** concluídas hoje.",inline=False)
        return await (ctx.response.send_message(embed=e,ephemeral=True) if isinstance(ctx,discord.Interaction) else ctx.send(embed=e))
    @app_commands.command(name="rotina",description="Mostra sua rotina diária")
    async def rotina(self,interaction): await self._routine(interaction)
    @commands.command(name="rotina",aliases=["dailyrotina"])
    async def p_rotina(self,ctx): await self._routine(ctx)

async def setup(bot):
    await bot.add_cog(Fun(bot))
