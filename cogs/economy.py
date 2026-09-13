from cogs.embed_style import KibotEmbed
import time, random
import discord
from discord.ext import commands
from discord import app_commands
import config
from database import db
from cogs.utils import async_boosted_crw
from cogs.utils import parse_amount, boosted_xp

def format_money(amount:int)->str:
    """Formata a moeda oficial do Kibot: 🪶 CRW 1.000."""
    return f"{config.CURRENCY_SYMBOL} {config.CURRENCY_CODE} {amount:,}".replace(",",".")

JOBS = {
    "entregador": {"name": "Entregador", "level": 1, "min": 50, "max": 140, "emoji": "📦", "desc": "Corre pra lá e pra cá entregando encomenda."},
    "barista": {"name": "Barista", "level": 3, "min": 90, "max": 190, "emoji": "☕", "desc": "Faz café, aguenta cliente e junta uma graninha."},
    "programador": {"name": "Programador", "level": 5, "min": 160, "max": 300, "emoji": "💻", "desc": "Codifica até o teclado pedir arrego."},
    "designer": {"name": "Designer", "level": 8, "min": 220, "max": 400, "emoji": "🎨", "desc": "Transforma ideia torta em coisa bonita."},
    "gerente": {"name": "Gerente", "level": 12, "min": 350, "max": 600, "emoji": "📋", "desc": "Resolve pepino e manda a equipe correr."},
    "empresario": {"name": "Empresário", "level": 16, "min": 500, "max": 850, "emoji": "💼", "desc": "Faz negócio enquanto o resto tá no café."},
    "magnata": {"name": "Magnata", "level": 20, "min": 750, "max": 1200, "emoji": "👑", "desc": "Dinheiro fazendo dinheiro. Vida fácil, né?"},
}

COMPANY_COST=500_000_000
COMPANY_COOLDOWN=86400
COMPANIES={
    "tecnologia":{"name":"Tecnologia","emoji":"💻","profit":8_000_000,"tax":15,"desc":"Software, IA, servidores e contratos corporativos."},
    "restaurante":{"name":"Restaurante","emoji":"🍽️","profit":5_000_000,"tax":10,"desc":"Comida, delivery e caos na cozinha."},
    "transportadora":{"name":"Transportadora","emoji":"🚚","profit":6_500_000,"tax":12,"desc":"Fretes, entregas e caminhão trabalhando sem parar."},
    "entretenimento":{"name":"Entretenimento","emoji":"🎬","profit":9_000_000,"tax":20,"desc":"Shows, filmes, eventos e conteúdo."},
    "mineradora":{"name":"Mineradora","emoji":"⛏️","profit":12_000_000,"tax":25,"desc":"Alto lucro, alto imposto e muito buraco no chão."},
    "estudio":{"name":"Estúdio Criativo","emoji":"🎨","profit":7_500_000,"tax":14,"desc":"Jogos, arte, música e projetos criativos."},
}

class Economy(commands.Cog):
    def __init__(self,bot): self.bot=bot
    async def _send(self,ctx,content=None,embed=None,ephemeral=False):
        if isinstance(ctx,discord.Interaction):
            if ctx.response.is_done(): return await ctx.followup.send(content=content,embed=embed,ephemeral=ephemeral)
            return await ctx.response.send_message(content=content,embed=embed,ephemeral=ephemeral)
        return await ctx.send(content=content,embed=embed)
    group=app_commands.Group(name="economia",description="Tudo que mexe nos seus CRW kkkkk")
    shop_group=app_commands.Group(name="loja",description="A lojinha pra torrar seus CRW")

    async def _saldo(self,ctx,alvo):
        row=await db.get_user(alvo.id,ctx.guild.id)
        e=KibotEmbed(title=f"💰 Carteira de {alvo.display_name}",color=discord.Color.gold())
        e.add_field(name="Carteira",value=format_money(row["balance"]),inline=True)
        e.add_field(name="Banco",value=format_money(row["bank"]),inline=True)
        e.add_field(name="🕳️ Dinheiro Sujo",value=format_money(row["dirty_money"]),inline=True)
        e.add_field(name="Total",value=format_money(row["balance"]+row["bank"]),inline=False)
        e.add_field(name="🐦‍⬛ Fichas Corvo",value=f"**{row['corvo_chips']:,}**".replace(",","."),inline=False)
        e.set_thumbnail(url=alvo.display_avatar.url)
        return e

    @group.command(name="saldo",description="Vê quanta grana você tem na carteira e no banco")
    async def saldo(self,interaction,usuario:discord.Member=None):
        await interaction.response.send_message(embed=await self._saldo(interaction,usuario or interaction.user))
    @group.command(name="daily",description="Pega seus CRW grátis do dia, porque de graça até injeção")
    async def daily(self,interaction):
        await self._daily(interaction)
    async def _daily(self,ctx):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        # Recompensa diária atômica: evita corrida entre duas chamadas simultâneas.
        daily_amount=await async_boosted_crw(user,config.DAILY_AMOUNT)
        claimed, remaining = await db.claim_daily(user.id, ctx.guild.id, daily_amount, config.DAILY_COOLDOWN_SECONDS)
        if not claimed:
            await self._send(ctx, f"⏳ Calma kkkkk, seu daily volta em **{remaining//3600}h {remaining%3600//60}m**.", ephemeral=isinstance(ctx,discord.Interaction))
            return
        badges=self.bot.get_cog("Badges")
        if badges: await badges.record(user.id,ctx.guild.id,"dailies",1,user)
        new_level,old_level,_=await db.add_xp(user.id,ctx.guild.id,boosted_xp(user,config.XP_DAILY))
        if new_level>old_level:
            levels=self.bot.get_cog("Levels")
            if levels: await levels.sync_member_level_roles(user)
        level_msg=f"\n⭐ +**{boosted_xp(user,config.XP_DAILY)} XP**" + (f" • 🎖️ Você subiu para o **nível {new_level}**!" if new_level>old_level else "")
        await self._send(ctx,f"🐦 BOA! Caiu **{format_money(daily_amount)}** de CRW pra você.{level_msg}",ephemeral=isinstance(ctx,discord.Interaction))
    @group.command(name="trabalhar",description="Bate o ponto no seu trampo e ganha uns CRW")
    async def trabalhar(self,interaction): await self._trabalhar(interaction)

    @group.command(name="trabalhos",description="Mostra os trampos liberados pelo seu nível")
    async def trabalhos(self,interaction): await self._trabalhos(interaction)

    @group.command(name="escolher_trabalho",description="Escolhe qual trampo você quer fazer")
    @app_commands.describe(trabalho="ID do trampo, tipo entregador ou programador")
    async def escolher_trabalho(self,interaction,trabalho:str): await self._escolher_trabalho(interaction,trabalho)

    async def _trabalhos(self,ctx):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        row=await db.get_user(user.id,ctx.guild.id)
        lines=[]
        for key,j in JOBS.items():
            status = "🔓" if row["level"] >= j["level"] else "🔒"
            selected = " ← seu trampo" if row["selected_job"] == key else ""
            lines.append(f"{status} **{j['emoji']} {j['name']}** — Lv. {j['level']} • {format_money(j['min'])}–{format_money(j['max'])}{selected}\n`{key}` — {j['desc']}")
        e=KibotEmbed(title="💼 Seus trampos",description=f"Você tá no **nível {row['level']}**. Escolhe um liberado e manda `K! escolher_trabalho ID`.",color=discord.Color.blurple())
        e.add_field(name="Lista",value="\n\n".join(lines),inline=False)
        await self._send(ctx,embed=e,ephemeral=isinstance(ctx,discord.Interaction))

    async def _escolher_trabalho(self,ctx,trabalho):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        key=trabalho.lower().strip().replace(" ","_")
        j=JOBS.get(key)
        row=await db.get_user(user.id,ctx.guild.id)
        if not j:
            await self._send(ctx,"❌ Esse trampo nem existe kkkkk. Manda `K! trabalhos` pra ver os que tem.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if row["level"] < j["level"]:
            await self._send(ctx,f"🔒 Calma, chefe kkkkk. **{j['name']}** só libera no **nível {j['level']}**. Você tá no {row['level']}.",ephemeral=isinstance(ctx,discord.Interaction)); return
        await db.set_selected_job(user.id,ctx.guild.id,key)
        await self._send(ctx,f"✅ Fechou! Agora seu trampo é **{j['emoji']} {j['name']}**. Manda `K! trabalhar` quando quiser bater o ponto.",ephemeral=isinstance(ctx,discord.Interaction))

    async def _trabalhar(self,ctx):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        row=await db.get_user(user.id,ctx.guild.id); elapsed=int(time.time())-row["last_work"]
        if elapsed<config.WORK_COOLDOWN_SECONDS:
            await self._send(ctx,f"⏳ Folga aí kkkkk. Faltam **{(config.WORK_COOLDOWN_SECONDS-elapsed)//60}m** pra bater o ponto de novo.",ephemeral=isinstance(ctx,discord.Interaction)); return
        j=JOBS.get(row["selected_job"],JOBS["entregador"])
        if row["level"] < j["level"]:
            await db.set_selected_job(user.id,ctx.guild.id,"entregador"); j=JOBS["entregador"]
        ganho=random.randint(j["min"],j["max"])
        ganho=await async_boosted_crw(user,ganho)
        await db.update_balance(user.id,ctx.guild.id,ganho); await db.set_last_work(user.id,ctx.guild.id)
        badges=self.bot.get_cog("Badges")
        if badges: await badges.record(user.id,ctx.guild.id,"works",1,user)
        new_level,old_level,_=await db.add_xp(user.id,ctx.guild.id,boosted_xp(user,config.XP_WORK))
        if new_level>old_level:
            levels=self.bot.get_cog("Levels")
            if levels: await levels.sync_member_level_roles(user)
        level_msg=f" • ⭐ +**{boosted_xp(user,config.XP_WORK)} XP**" + (f"\n🎖️ Você subiu para o **nível {new_level}**!" if new_level>old_level else "")

        await self._send(ctx,f"{j['emoji']} Turno encerrado! Você trabalhou de **{j['name']}** e embolsou **{format_money(ganho)}**. Tá pago kkkkk.{level_msg}",ephemeral=isinstance(ctx,discord.Interaction))
    @group.command(name="roubar",description="Tenta roubar metade da carteira de outro membro")
    @app_commands.describe(usuario="Quem vai ter a carteira mexida")
    async def roubar(self,interaction,usuario:discord.Member): await self._roubar(interaction,usuario)

    async def _roubar(self,ctx,usuario):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if usuario.bot or usuario.id==actor.id:
            await self._send(ctx,"❌ Aí não kkkkk. Escolhe uma pessoa de verdade e não tenta se roubar.",ephemeral=isinstance(ctx,discord.Interaction)); return
        row=await db.get_user(actor.id,ctx.guild.id); elapsed=int(time.time())-row["last_rob"]
        cooldown=2*3600
        if elapsed<cooldown:
            await self._send(ctx,f"🕵️ Calma aí, profissional. Você precisa esperar **{(cooldown-elapsed)//60}m** pra tentar outro roubo.",ephemeral=isinstance(ctx,discord.Interaction)); return
        target=await db.get_user(usuario.id,ctx.guild.id)
        amount=target["balance"]//2
        if amount<=0:
            await self._send(ctx,f"🫤 Fui olhar a carteira de {usuario.mention} e tá zerada. Não tem o que levar kkkkk.",ephemeral=isinstance(ctx,discord.Interaction)); return
        amount=await db.steal_half_wallet(actor.id,usuario.id,ctx.guild.id)
        await db.set_last_rob(actor.id,ctx.guild.id)
        if amount<=0:
            await self._send(ctx,"❌ Ih, a carteira mudou enquanto você tentava. O roubo não rolou.",ephemeral=isinstance(ctx,discord.Interaction)); return
        e=KibotEmbed(title="🕵️‍♂️ ROUBO FEITO",description=f"Você passou a mão em **50% da carteira** de {usuario.mention} kkkkk.\n\n💰 Você levou **{format_money(amount)}**.\n😈 A vítima ficou com a outra metade.",color=discord.Color.red())
        e.set_footer(text="É tudo CRW virtual, relaxa 😂")
        await self._send(ctx,embed=e)

    @group.command(name="transferir",description="Manda uns CRW pra outro membro")
    async def transferir(self,interaction,usuario:discord.Member,quantidade:str): await self._transferir(interaction,usuario,quantidade)
    async def _transferir(self,ctx,usuario,quantidade):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        row=await db.get_user(actor.id,ctx.guild.id)
        quantidade=parse_amount(quantidade, row["balance"])
        if quantidade is None or usuario.bot or usuario.id==actor.id or quantidade<=0: await self._send(ctx,"❌ Aí não kkkkk. Essa transferência não rola.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if row["balance"]<quantidade: await self._send(ctx,"❌ Ih, faltou CRW aí kkkkk.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if not await db.transfer_balance(actor.id, usuario.id, ctx.guild.id, quantidade):
            return await self._send(ctx,"❌ A transferência falhou ou seu saldo mudou enquanto você confirmava. Tenta de novo.",ephemeral=isinstance(ctx,discord.Interaction))
        await self._send(ctx,f"✅ Você enviou **{format_money(quantidade)}** para {usuario.mention}.")
    @group.command(name="depositar",description="Joga seus CRW no banco pra não ficar dando sopa")
    async def depositar(self,interaction,quantidade:str): await self._depositar(interaction,quantidade)
    async def _depositar(self,ctx,q):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author; row=await db.get_user(actor.id,ctx.guild.id)
        q=parse_amount(q, row["balance"])
        if q is None or q<=0 or row["balance"]<q: await self._send(ctx,"❌ Essa quantidade tá errada ou você não tem CRW suficiente.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if not await db.move_balance_to_bank(actor.id, ctx.guild.id, q):
            return await self._send(ctx,"❌ O depósito falhou porque seu saldo mudou enquanto você confirmava. Tenta de novo.",ephemeral=isinstance(ctx,discord.Interaction))
        await self._send(ctx,f"🏦 Depositado **{format_money(q)}**.")
    @group.command(name="sacar",description="Puxa seus CRW de volta do banco")
    async def sacar(self,interaction,quantidade:str): await self._sacar(interaction,quantidade)
    async def _sacar(self,ctx,q):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author; row=await db.get_user(actor.id,ctx.guild.id)
        q=parse_amount(q, row["bank"])
        if q is None or q<=0 or row["bank"]<q: await self._send(ctx,"❌ Essa quantidade tá errada ou seu banco não tem CRW suficiente.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if not await db.move_bank_to_balance(actor.id, ctx.guild.id, q):
            return await self._send(ctx,"❌ O saque falhou porque seu Banco mudou enquanto você confirmava. Tenta de novo.",ephemeral=isinstance(ctx,discord.Interaction))
        await self._send(ctx,f"💵 Sacado **{format_money(q)}**.")
    @group.command(name="ranking",description="Vê quem tá nadando em CRW por aqui")
    async def ranking(self,interaction):
        rows=await db.get_leaderboard(interaction.guild_id,10); lines=[]
        for i,r in enumerate(rows,1):
            m=interaction.guild.get_member(r["user_id"]) or await self._fetch_member(interaction.guild,r["user_id"])
            lines.append(f"**{i}.** {m.display_name if m else r['user_id']} — {format_money(r['total'])}")
        await interaction.response.send_message(embed=KibotEmbed(title="🏆 Ranking de Crowins",description="\n".join(lines) or "Ainda não tem ninguém aqui kkkkk.",color=discord.Color.gold()))
    async def _fetch_member(self,gid,uid):
        try:return await gid.fetch_member(uid)
        except discord.HTTPException:return None

    # Loja: cargos puramente cosméticos.
    @shop_group.command(name="listar",description="Dá uma olhada no que tem na lojinha")
    async def shop(self,interaction):
        await self._shop(interaction)
    async def _shop(self,ctx):
        items=await db.get_shop_items(ctx.guild.id); e=KibotEmbed(title="🛍️ Loja de Crowins",color=discord.Color.gold())
        if not items:e.description="A lojinha tá vazia por enquanto 👀"
        for x in items:
            role=f"<@&{x['role_id']}>" if x["role_id"] else "Cosmético"
            e.add_field(name=f"{x['emoji']} {x['name']} • #{x['id']}",value=f"{x['description'] or 'Sem descrição'}\n**{format_money(x['price'])}** • {role}",inline=False)
        await self._send(ctx,embed=e)
    @shop_group.command(name="comprar",description="Compra um item da lojinha pelo ID")
    async def comprar(self,interaction,item_id:int): await self._comprar(interaction,item_id)
    async def _comprar(self,ctx,item_id):
        item=await db.get_shop_item(ctx.guild.id,item_id)
        if not item: await self._send(ctx,"❌ Esse item sumiu da lojinha kkkkk.",ephemeral=isinstance(ctx,discord.Interaction)); return
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        if await db.has_item(actor.id,ctx.guild.id,item_id): await self._send(ctx,"❌ Você já tem esse item kkkkk.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if item["role_id"]:
            role=ctx.guild.get_role(item["role_id"])
            if not role: await self._send(ctx,"❌ Esse cargo já era, não existe mais.",ephemeral=isinstance(ctx,discord.Interaction)); return
            if role>=ctx.guild.me.top_role: await self._send(ctx,"❌ Esse cargo tá acima do Kibot, aí não consigo mexer nele.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if not await db.purchase_item(actor.id,ctx.guild.id,item_id,item["price"]):
            await self._send(ctx,"❌ Você não tem CRW suficiente pra comprar isso.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if item["role_id"]: await actor.add_roles(ctx.guild.get_role(item["role_id"]),reason="Compra na loja do Kibot")
        await self._send(ctx,f"🛍️ Fechou! Você comprou **{item['name']}** por {format_money(item['price'])}.")

    @shop_group.command(name="adicionar",description="Bota mais um cargo na lojinha")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def shop_add(self,interaction,nome:str,preco:int,cargo:discord.Role,descricao:str="Cargo cosmético",emoji:str="🎟️"):
        if preco<=0: await interaction.response.send_message("❌ Esse preço não faz sentido kkkkk.",ephemeral=True); return
        await db.add_shop_item(interaction.guild_id,nome,descricao,preco,cargo.id,emoji)
        await interaction.response.send_message(f"✅ **{nome}** adicionado à loja por {format_money(preco)}.")

    async def _fichas(self,ctx):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        row=await db.get_user(actor.id,ctx.guild.id)
        e=KibotEmbed(title="🐦‍⬛ Fichas Corvo",description=f"Você possui **{row['corvo_chips']:,} Fichas Corvo**.".replace(",","."),color=0xC9A227)
        e.add_field(name="Como farmar",value="Joga no Arcade e vai juntando. Essas fichas não entram nas apostas e não valem grana de verdade.",inline=False)
        e.add_field(name="Onde gastar",value="Manda `K! loja` pra ver a lojinha e `K! comprar_corvo ID` pra gastar as fichas.",inline=False)
        await self._send(ctx,embed=e,ephemeral=isinstance(ctx,discord.Interaction))

    async def _corvo_shop(self,ctx):
        items=await db.get_corvo_shop_items(ctx.guild.id)
        e=KibotEmbed(title="🐦‍⬛ Loja das Fichas Corvo",description="Junta as 10 relíquias do Bando. Cada uma dá pra comprar só uma vez 👀",color=0xC9A227)
        for x in items:
            e.add_field(name=f"{x['emoji']} {x['name']} • #{x['id']}",value=f"{x['description']}\n**{x['price']:,} Fichas Corvo**".replace(",","."),inline=False)
        await self._send(ctx,embed=e)

    async def _comprar_corvo(self,ctx,item_id):
        actor=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        item=await db.get_corvo_shop_item(ctx.guild.id,item_id)
        if not item:
            await self._send(ctx,"❌ Não achei esse item de Fichas Corvo.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if await db.has_corvo_item(actor.id,ctx.guild.id,item_id):
            await self._send(ctx,"❌ Você já tem esse item kkkkk.",ephemeral=isinstance(ctx,discord.Interaction)); return
        if not await db.purchase_corvo_item(actor.id,ctx.guild.id,item_id,item["price"]):
            await self._send(ctx,"❌ Faltam Fichas Corvo pra isso.",ephemeral=isinstance(ctx,discord.Interaction)); return
        await self._send(ctx,f"🐦‍⬛ Compra concluída: **{item['name']}** por **{item['price']:,} Fichas Corvo**.".replace(",","."))

    @group.command(name="fichas",description="Vê quantas Fichas Corvo você juntou")
    async def fichas_slash(self,interaction): await self._fichas(interaction)
    @group.command(name="ranking_fichas",description="Vê quem tá lotado de Fichas Corvo")
    async def ranking_fichas_slash(self,interaction):
        rows=await db.get_corvo_leaderboard(interaction.guild_id,10); lines=[]
        for i,r in enumerate(rows,1):
            m=interaction.guild.get_member(r["user_id"])
            lines.append(f"**{i}.** {m.display_name if m else r['user_id']} — **{r['corvo_chips']:,}** 🐦‍⬛".replace(",","."))
        await interaction.response.send_message(embed=KibotEmbed(title="🏆 Ranking de Fichas Corvo",description="\n".join(lines) or "Ainda não tem ninguém aqui kkkkk.",color=0xC9A227))
    @shop_group.command(name="corvo",description="Abre a lojinha das Fichas Corvo")
    async def corvo_shop_slash(self,interaction): await self._corvo_shop(interaction)
    @shop_group.command(name="comprar_corvo",description="Torra suas Fichas Corvo em um item")
    async def comprar_corvo_slash(self,interaction,item_id:int): await self._comprar_corvo(interaction,item_id)

    @group.command(name="empresa",description="Veja sua empresa e os tipos disponíveis")
    async def empresa_slash(self,interaction): await self._empresa(interaction)
    @group.command(name="criar_empresa",description="Cria uma empresa por 500 milhões de CRW")
    @app_commands.describe(tipo="Tipo de empresa",nome="Nome da sua empresa")
    async def criar_empresa_slash(self,interaction,tipo:str,nome:str): await self._criar_empresa(interaction,tipo,nome)
    @group.command(name="lucro_empresa",description="Recebe o lucro da sua empresa e paga os impostos")
    async def lucro_empresa_slash(self,interaction): await self._lucro_empresa(interaction)
    @group.command(name="vender_empresa",description="Vende sua empresa por parte do investimento")
    async def vender_empresa_slash(self,interaction): await self._vender_empresa(interaction)

    async def _empresa(self,ctx):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        row=await db.get_company(user.id,ctx.guild.id)
        if not row:
            text="🏢 Você ainda não tem empresa.\n\nCriar uma custa **🪶 CRW 500.000.000** e o investimento sai do **Banco**.\nUse `K! criar_empresa` e escolha um tipo."
            return await self._send(ctx,text,ephemeral=isinstance(ctx,discord.Interaction))
        info=COMPANIES.get(row["company_type"],{})
        elapsed=max(0,int(time.time())-row["last_collect"])
        ready=max(0,COMPANY_COOLDOWN-elapsed)
        e=KibotEmbed(title=f"🏢 {row['name']}",description=f"{info.get('emoji','🏢')} **{info.get('name',row['company_type'])}**\n{info.get('desc','')}",color=discord.Color.gold())
        e.add_field(name="Investimento",value=format_money(row["invested"]))
        e.add_field(name="Lucro bruto diário",value=f"{format_money(info.get('profit',0))}")
        e.add_field(name="Imposto",value=f"{info.get('tax',0)}%")
        e.add_field(name="Lucro líquido",value=format_money(int(info.get('profit',0)*(1-info.get('tax',0)/100))))
        e.add_field(name="Próximo lucro",value="**Disponível agora!**" if ready==0 else f"em **{ready//3600}h {(ready%3600)//60}m**")
        e.add_field(name="Histórico",value=f"Bruto: {format_money(row['total_gross'])}\nImpostos: {format_money(row['total_tax'])}\nLíquido: {format_money(row['total_net'])}",inline=False)
        return await self._send(ctx,embed=e,ephemeral=isinstance(ctx,discord.Interaction))

    async def _criar_empresa(self,ctx,tipo,nome):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        key=tipo.lower().strip().replace(" ","_")
        info=COMPANIES.get(key)
        if not info:
            lista="\n".join(f"`{k}` — {v['name']} • lucro {format_money(v['profit'])}/dia • imposto {v['tax']}%" for k,v in COMPANIES.items())
            return await self._send(ctx,f"❌ Tipo inválido. Os tipos são:\n{lista}",ephemeral=isinstance(ctx,discord.Interaction))
        nome=" ".join(str(nome).split())[:40]
        if len(nome)<2:
            return await self._send(ctx,"❌ Dá um nome decente pra empresa kkkkk.",ephemeral=isinstance(ctx,discord.Interaction))
        if await db.get_company(user.id,ctx.guild.id):
            return await self._send(ctx,"❌ Você já é dono de uma empresa. Vende a atual antes de abrir outra.",ephemeral=isinstance(ctx,discord.Interaction))
        ok=await db.create_company(user.id,ctx.guild.id,nome,key,COMPANY_COST)
        if not ok:
            row=await db.get_user(user.id,ctx.guild.id)
            return await self._send(ctx,f"❌ Faltou dinheiro no **Banco**.\nVocê precisa de **{format_money(COMPANY_COST)}** no banco e tem **{format_money(row['bank'])}**.",ephemeral=isinstance(ctx,discord.Interaction))
        badges=self.bot.get_cog("Badges")
        if badges: await badges.record(user.id,ctx.guild.id,"companies",1,user)
        new_level,old_level,_=await db.add_xp(user.id,ctx.guild.id,boosted_xp(user,config.XP_COMPANY_CREATE))
        if new_level>old_level:
            levels=self.bot.get_cog("Levels")
            if levels: await levels.sync_member_level_roles(user)
        level_msg=f"\n⭐ +**{boosted_xp(user,config.XP_COMPANY_CREATE)} XP**" + (f" • 🎖️ Você subiu para o **nível {new_level}**!" if new_level>old_level else "")
        return await self._send(ctx,f"🏢 **EMPRESA CRIADA!**\n\n{info['emoji']} **{nome}** agora é sua empresa de **{info['name']}**.\n💸 Investimento: **{format_money(COMPANY_COST)}**\n📈 Lucro bruto: **{format_money(info['profit'])}/24h**\n🏛️ Imposto: **{info['tax']}%**\n💰 Lucro líquido estimado: **{format_money(int(info['profit']*(1-info['tax']/100)))}**{level_msg}\n\nUse `K! lucro_empresa` quando o lucro estiver disponível.",ephemeral=isinstance(ctx,discord.Interaction))

    async def _lucro_empresa(self,ctx):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        row=await db.get_company(user.id,ctx.guild.id)
        if not row: return await self._send(ctx,"❌ Você não tem empresa ainda.",ephemeral=isinstance(ctx,discord.Interaction))
        info=COMPANIES[row['company_type']]; elapsed=int(time.time())-row['last_collect']
        if elapsed<COMPANY_COOLDOWN:
            left=COMPANY_COOLDOWN-elapsed
            return await self._send(ctx,f"⏳ Sua empresa ainda está trabalhando. Volta em **{left//3600}h {(left%3600)//60}m**.",ephemeral=isinstance(ctx,discord.Interaction))
        # Pequena variação de mercado para não deixar todas as empresas idênticas.
        gross=random.randint(int(info['profit']*0.85),int(info['profit']*1.15))
        tax=int(gross*info['tax']/100); net=gross-tax
        net=await async_boosted_crw(user,net)
        tax=max(0,gross-net)
        ok=await db.collect_company(user.id,ctx.guild.id,gross,tax)
        if not ok: return await self._send(ctx,"❌ O fechamento da empresa falhou. Tenta novamente.",ephemeral=isinstance(ctx,discord.Interaction))
        badges=self.bot.get_cog("Badges")
        if badges: await badges.record(user.id,ctx.guild.id,"company_profits",1,user)
        new_level,old_level,_=await db.add_xp(user.id,ctx.guild.id,boosted_xp(user,config.XP_COMPANY_PROFIT))
        if new_level>old_level:
            levels=self.bot.get_cog("Levels")
            if levels: await levels.sync_member_level_roles(user)
        level_msg=f"\n⭐ +**{boosted_xp(user,config.XP_COMPANY_PROFIT)} XP**" + (f" • 🎖️ Você subiu para o **nível {new_level}**!" if new_level>old_level else "")
        return await self._send(ctx,f"📊 **BALANÇO DA EMPRESA**\n\n💵 Lucro bruto: **{format_money(gross)}**\n🏛️ Imposto ({info['tax']}%): **-{format_money(tax)}**\n🏦 Caiu no Banco: **+{format_money(net)}**{level_msg}\n\nA Receita Federal do Corvo agradece. 🐦‍⬛",ephemeral=isinstance(ctx,discord.Interaction))

    async def _vender_empresa(self,ctx):
        user=ctx.user if isinstance(ctx,discord.Interaction) else ctx.author
        row=await db.get_company(user.id,ctx.guild.id)
        if not row: return await self._send(ctx,"❌ Você não tem empresa pra vender.",ephemeral=isinstance(ctx,discord.Interaction))
        refund=int(row['invested']*0.70)
        if not await db.delete_company(user.id,ctx.guild.id): return await self._send(ctx,"❌ Não consegui concluir a venda.",ephemeral=isinstance(ctx,discord.Interaction))
        await db.update_bank(user.id,ctx.guild.id,refund)
        return await self._send(ctx,f"🏷️ Empresa vendida. Você recuperou **{format_money(refund)}** no Banco (**70%** do investimento inicial).",ephemeral=isinstance(ctx,discord.Interaction))

    @commands.command(name="empresa",aliases=["business","negocio"])
    async def p_empresa(self,ctx): await self._empresa(ctx)
    @commands.command(name="criar_empresa",aliases=["criarnempresa","abrirempresa"])
    async def p_criar_empresa(self,ctx,tipo:str,nome:str): await self._criar_empresa(ctx,tipo,nome)
    @commands.command(name="lucro_empresa",aliases=["lucro","empresa_lucro"])
    async def p_lucro_empresa(self,ctx): await self._lucro_empresa(ctx)
    @commands.command(name="vender_empresa",aliases=["venderempresa"])
    async def p_vender_empresa(self,ctx): await self._vender_empresa(ctx)

    # Prefix aliases simples
    @commands.command(name="saldo", aliases=["bal", "balance"])
    async def p_saldo(self,ctx,usuario:discord.Member=None): await self._send(ctx,embed=await self._saldo(ctx,usuario or ctx.author))
    @commands.command(name="daily", aliases=["day"])
    async def p_daily(self,ctx): await self._daily(ctx)
    @commands.command(name="trabalhar",aliases=["work"])
    async def p_work(self,ctx): await self._trabalhar(ctx)
    @commands.command(name="trabalhos",aliases=["jobs", "empregos"])
    async def p_jobs(self,ctx): await self._trabalhos(ctx)
    @commands.command(name="escolher_trabalho",aliases=["escolhertrabalho", "escolherjob"])
    async def p_choose_job(self,ctx,trabalho:str): await self._escolher_trabalho(ctx,trabalho)
    @commands.command(name="roubar",aliases=["steal", "assaltar_carteira"])
    async def p_rob(self,ctx,usuario:discord.Member): await self._roubar(ctx,usuario)
    @commands.command(name="transferir",aliases=["pay", "give"])
    async def p_pay(self,ctx,usuario:discord.Member,quantidade:str): await self._transferir(ctx,usuario,quantidade)
    @commands.command(name="depositar", aliases=["dep"])
    async def p_dep(self,ctx,quantidade:str): await self._depositar(ctx,quantidade)
    @commands.command(name="sacar", aliases=["withdraw", "wd"])
    async def p_sacar(self,ctx,quantidade:str): await self._sacar(ctx,quantidade)
    @commands.command(name="ranking", aliases=["rank", "top"])
    async def p_rank(self,ctx):
        rows=await db.get_leaderboard(ctx.guild.id,10)
        lines=[]
        for i,r in enumerate(rows,1):
            m=ctx.guild.get_member(r["user_id"]); lines.append(f"**{i}.** {m.display_name if m else r['user_id']} — {format_money(r['total'])}")
        await self._send(ctx,embed=KibotEmbed(title="🏆 Ranking",description="\n".join(lines) or "Ainda não tem ninguém aqui kkkkk.",color=discord.Color.gold()))
    @commands.command(name="fichas", aliases=["corvo", "crowchips"])
    async def p_fichas(self,ctx): await self._fichas(ctx)
    @commands.command(name="ranking_fichas", aliases=["rankfichas", "topfichas"])
    async def p_rank_fichas(self,ctx):
        rows=await db.get_corvo_leaderboard(ctx.guild.id,10); lines=[]
        for i,r in enumerate(rows,1):
            m=ctx.guild.get_member(r["user_id"])
            lines.append(f"**{i}.** {m.display_name if m else r['user_id']} — **{r['corvo_chips']:,}** 🐦‍⬛".replace(",","."))
        await ctx.send(embed=KibotEmbed(title="🏆 Ranking de Fichas Corvo",description="\n".join(lines) or "Ainda não tem ninguém aqui kkkkk.",color=0xC9A227))
    @commands.command(name="loja_corvo", aliases=["corvoloja", "fichasloja"])
    async def p_corvo_shop(self,ctx): await self._corvo_shop(ctx)
    @commands.command(name="comprar_corvo", aliases=["buycorvo", "comprarficha"])
    async def p_buy_corvo(self,ctx,item_id:int): await self._comprar_corvo(ctx,item_id)
    @commands.command(name="loja", aliases=["shop"])
    async def p_shop(self,ctx):
        await self._shop(ctx)
        await self._corvo_shop(ctx)
    @commands.command(name="comprar", aliases=["buy"])
    async def p_buy(self,ctx,item_id:int): await self._comprar(ctx,item_id)


async def setup(bot): await bot.add_cog(Economy(bot))
