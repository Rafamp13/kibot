from cogs.embed_style import KibotEmbed
import random, time, re
import discord
from discord.ext import commands, tasks
from discord import app_commands
from database import db
import config
from cogs.utils import send, boosted_xp, set_anime_gif

class LevelRoleModal(discord.ui.Modal, title="Configurar cargo por nível"):
    nivel=discord.ui.TextInput(label="Nível",placeholder="Ex.: 1, 5, 10",max_length=5)
    cargo=discord.ui.TextInput(label="Cargo",placeholder="@Cargo ou ID do cargo",max_length=100)
    def __init__(self,cog): super().__init__(); self.cog=cog
    async def on_submit(self,interaction):
        try: level=int(str(self.nivel).strip()); assert 1<=level<=1000
        except (ValueError,AssertionError): return await interaction.response.send_message("❌ O nível deve ser um número entre **1 e 1000**.",ephemeral=True)
        raw=str(self.cargo).strip(); m=re.fullmatch(r"<@&(\d+)>",raw) or re.fullmatch(r"(\d+)",raw)
        role=interaction.guild.get_role(int(m.group(1))) if m else discord.utils.get(interaction.guild.roles,name=raw.lstrip('@'))
        if not role: return await interaction.response.send_message("❌ Cargo não encontrado. Use uma menção `@Cargo` ou o ID.",ephemeral=True)
        me=interaction.guild.me
        if role.is_default() or role.managed or (me and role>=me.top_role): return await interaction.response.send_message("❌ Não consigo gerenciar esse cargo. Deixe o cargo do Kibot acima dele.",ephemeral=True)
        await db.set_xp_level_role(interaction.guild_id,level,role.id)
        await self.cog.sync_all_level_roles(interaction.guild)
        await interaction.response.send_message(f"✅ Nível **{level}** → {role.mention}. Membros sincronizados.",ephemeral=True)

class RemoveLevelRoleModal(discord.ui.Modal, title="Remover cargo por nível"):
    nivel=discord.ui.TextInput(label="Nível",placeholder="Ex.: 10",max_length=5)
    def __init__(self,cog): super().__init__(); self.cog=cog
    async def on_submit(self,interaction):
        try: level=int(str(self.nivel).strip()); assert level>=1
        except (ValueError,AssertionError): return await interaction.response.send_message("❌ Nível inválido.",ephemeral=True)
        await db.remove_xp_level_role(interaction.guild_id,level); await self.cog.sync_all_level_roles(interaction.guild)
        await interaction.response.send_message(f"🗑️ Configuração do nível **{level}** removida.",ephemeral=True)

class LevelRolePanel(discord.ui.View):
    def __init__(self,cog): super().__init__(timeout=600); self.cog=cog
    async def admin(self,i):
        if not i.user.guild_permissions.administrator: await i.response.send_message("❌ Só Administradores podem usar este painel.",ephemeral=True); return False
        return True
    @discord.ui.button(label="Configurar cargo",emoji="🎖️",style=discord.ButtonStyle.primary)
    async def configure(self,i,b):
        if await self.admin(i): await i.response.send_modal(LevelRoleModal(self.cog))
    @discord.ui.button(label="Remover",emoji="🗑️",style=discord.ButtonStyle.danger)
    async def remove(self,i,b):
        if await self.admin(i): await i.response.send_modal(RemoveLevelRoleModal(self.cog))
    @discord.ui.button(label="Atualizar",emoji="🔄",style=discord.ButtonStyle.secondary)
    async def refresh(self,i,b):
        if await self.admin(i): await self.cog.send_panel(i,True)
    @discord.ui.button(label="Sincronizar",emoji="⚡",style=discord.ButtonStyle.success)
    async def sync(self,i,b):
        if not await self.admin(i): return
        await i.response.defer(ephemeral=True); n=await self.cog.sync_all_level_roles(i.guild); await i.followup.send(f"✅ {n} membro(s) atualizado(s).",ephemeral=True)

class Levels(commands.Cog):
    """XP por atividade e cargos automáticos por nível."""
    def __init__(self,bot):
        self.bot=bot
        self.message_cooldown={}
        self.voice_started={}
        self.voice_loop.start()
    def cog_unload(self): self.voice_loop.cancel()

    async def sync_member_level_roles(self,member):
        configs=await db.get_xp_level_roles(member.guild.id)
        if not configs or member.bot: return False
        row=await db.get_user(member.id,member.guild.id); eligible=[r for r in configs if r["level"]<=row["level"]]
        target=eligible[-1]["role_id"] if eligible else None; ids={r["role_id"] for r in configs}; changed=False
        me=member.guild.me
        for rid in ids:
            role=member.guild.get_role(rid)
            if not role or role.managed or (me and role>=me.top_role): continue
            try:
                if rid==target and role not in member.roles: await member.add_roles(role,reason=f"Kibot XP nível {row['level']}"); changed=True
                elif rid!=target and role in member.roles: await member.remove_roles(role,reason="Kibot XP atualização de cargo"); changed=True
            except discord.HTTPException: pass
        return changed

    async def sync_all_level_roles(self,guild):
        n=0
        for m in guild.members:
            if await self.sync_member_level_roles(m): n+=1
        return n

    async def send_panel(self,target,edit=False):
        guild=target.guild; rows=await db.get_xp_level_roles(guild.id)
        lines=[]
        for r in rows:
            role=guild.get_role(r["role_id"]); lines.append(f"**Nível {r['level']}** → {role.mention if role else '`cargo removido`'}")
        desc="Configure um cargo para cada marco de nível. O Kibot mantém apenas o cargo de nível mais alto atingido.\n\n**Configurações:**\n"+("\n".join(lines) if lines else "Nenhuma ainda.")
        e=KibotEmbed(title="🎖️ Cargos automáticos por nível",description=desc,color=discord.Color.gold()); e.set_footer(text="Administrador • O cargo do Kibot precisa estar acima dos cargos configurados")
        view=LevelRolePanel(self)
        if edit: await target.response.edit_message(embed=e,view=view)
        else: await target.send(embed=e,view=view)

    @commands.Cog.listener()
    async def on_message(self,message):
        if message.author.bot or not message.guild:return
        cfg=await db.get_guild_config(message.guild.id)
        if not cfg["xp_enabled"]:return
        now=time.time(); key=(message.guild.id,message.author.id)
        if now-self.message_cooldown.get(key,0)<config.XP_MESSAGE_COOLDOWN:return
        self.message_cooldown[key]=now
        amount=random.randint(config.XP_MESSAGE_MIN,config.XP_MESSAGE_MAX)
        new,old,xp=await db.add_xp(message.author.id,message.guild.id,boosted_xp(message.author,amount))
        if new>old:
            await self.sync_member_level_roles(message.author)
            try: await message.channel.send(f"⭐ {message.author.mention} subiu pro **nível {new}**! Aí sim 😎",delete_after=8)
            except discord.HTTPException: pass

    @commands.Cog.listener()
    async def on_voice_state_update(self,member,before,after):
        if member.bot:return
        key=(member.guild.id,member.id)
        if before.channel is None and after.channel is not None:
            self.voice_started[key]=time.time()
        elif before.channel is not None and after.channel is None:
            self.voice_started.pop(key,None)
        elif before.channel!=after.channel and after.channel is not None:
            self.voice_started[key]=time.time()

    @tasks.loop(minutes=5)
    async def voice_loop(self):
        now=time.time()
        for (guild_id,user_id),started in list(self.voice_started.items()):
            if now-started>=300:
                guild=self.bot.get_guild(guild_id)
                if not guild: continue
                cfg=await db.get_guild_config(guild_id)
                if cfg["xp_enabled"]:
                    member=guild.get_member(user_id)
                    awarded=boosted_xp(member, config.XP_VOICE_PER_5_MIN)
                    new,old,xp=await db.add_xp(user_id,guild_id,awarded)
                    if new>old:
                        if member:
                            await self.sync_member_level_roles(member)
                            try:
                                level_embed=KibotEmbed(title="⭐ LEVEL UP!",description=f"Você chegou no **nível {new}** em **{guild.name}**! Tá farmando hein 👀",color=discord.Color.gold())
                                await set_anime_gif(level_embed,"dance")
                                await member.send(embed=level_embed)
                            except discord.HTTPException: pass
                self.voice_started[(guild_id,user_id)]=now
    @voice_loop.before_loop
    async def before_voice(self): await self.bot.wait_until_ready()

    async def _profile(self,ctx,member=None):
        m=member or (ctx.user if isinstance(ctx,discord.Interaction) else ctx.author)
        r=await db.get_user(m.id,ctx.guild.id)
        badge_count=await db.count_earned_badges(m.id,ctx.guild.id)
        total_crw=int(r["balance"])+int(r["bank"])
        dirty_money=int(r["dirty_money"] or 0)
        level_roles=await db.get_xp_level_roles(ctx.guild.id)
        eligible_roles=[x for x in level_roles if int(x["level"]) <= int(r["level"])]
        next_role_cfg=next((x for x in level_roles if int(x["level"]) > int(r["level"])), None)
        current_role_cfg=eligible_roles[-1] if eligible_roles else None
        current_role=ctx.guild.get_role(int(current_role_cfg["role_id"])) if current_role_cfg else None
        next_role=ctx.guild.get_role(int(next_role_cfg["role_id"])) if next_role_cfg else None
        need=max(1,100*r["level"])
        progress=max(0,min(20,int((r["xp"]/need)*20)))

        # Busca o User completo para obter banner mesmo quando o membro não o expõe em cache.
        try:
            user=await self.bot.fetch_user(m.id)
        except discord.HTTPException:
            user=m

        # Com cache de membros/presenças habilitado, status vem do Presence Intent.
        # Também consideramos os status por dispositivo para evitar falso offline.
        raw_status = getattr(self.bot, "presence_cache", {}).get((ctx.guild.id, m.id), None)
        if raw_status is None:
            raw_status = m.status
        if raw_status == discord.Status.offline:
            for device_status in (getattr(m, "desktop_status", None), getattr(m, "mobile_status", None), getattr(m, "web_status", None)):
                if device_status and device_status != discord.Status.offline:
                    raw_status = device_status
                    break
        # Conversão explícita por nome: evita qualquer ambiguidade com Enum/estado vindo do Gateway.
        status_name = getattr(raw_status, "name", str(raw_status).split(".")[-1]).lower()
        status = {
            "online": "🟢 Online",
            "idle": "🌙 Ausente",
            "dnd": "⛔ Não Perturbe",
            "offline": "⚫ Offline",
            "invisible": "⚫ Invisível",
        }.get(status_name, "⚫ Offline")
        roles=[role.mention for role in reversed(m.roles[1:]) if not role.is_default()]
        roles_text=" ".join(roles[:8]) if roles else "Nenhum cargo"
        if len(roles)>8: roles_text += f" +{len(roles)-8}"

        # PERFIL — layout em blocos, não em dezenas de fields.
        # Discord mobile tende a empilhar inline fields; por isso o perfil
        # concentra os dados em poucos blocos largos e previsíveis.
        identity_lines = [
            f"🟢 **Status:** {status}",
            f"🆔 **ID:** `{m.id}`",
            f"📅 **Conta criada:** {discord.utils.format_dt(m.created_at, 'D')}",
        ]
        if m.joined_at:
            identity_lines.append(f"📥 **Entrou no servidor:** {discord.utils.format_dt(m.joined_at, 'D')}")

        e=KibotEmbed(
            title=f"🐦 PERFIL • {m.display_name}",
            description=f"{m.mention}\n\n" + "\n".join(identity_lines),
            color=discord.Color.purple(),
        )
        e.set_thumbnail(url=m.display_avatar.url)
        if getattr(user,"banner",None):
            e.set_image(url=user.banner.url)

        # Um field = um cartão. Assim o Discord não quebra cada métrica em
        # uma coluna própria no celular.
        e.add_field(
            name="📈 PROGRESSO",
            value=(
                f"⭐ **Nível {r['level']}**  •  ✨ **{r['xp']:,} XP**  •  🏆 **{badge_count}/29 badges**".replace(",", ".")
                + f"\n📊 `{'█'*progress}{'░'*(20-progress)}` **{r['xp']}/{need} XP** para o próximo nível"
            ),
            inline=False,
        )

        e.add_field(
            name="💰 ECONOMIA",
            value=(
                f"🪶 **CRW total:** {total_crw:,} CRW  •  👛 **Carteira:** {r['balance']:,} CRW\n"
                f"🏦 **Banco:** {r['bank']:,} CRW  •  🕳️ **Dinheiro sujo:** {dirty_money:,} CRW"
            ).replace(",", "."),
            inline=False,
        )

        reward_text = "🏆 Todos os cargos de nível configurados já foram alcançados." if not next_role_cfg else f"**Nível {next_role_cfg['level']}** → {next_role.mention if next_role else '`cargo removido`'}"
        current_text = f"**Nível {current_role_cfg['level']}** → {current_role.mention}" if current_role_cfg and current_role else "Nenhum cargo de nível alcançado ainda."
        e.add_field(
            name="🎁 RECOMPENSAS",
            value=(
                f"🎖️ **Patamar atual:** {current_text}\n"
                f"🎁 **Próxima recompensa:** {reward_text}"
            ),
            inline=False,
        )

        e.add_field(
            name="🎭 CARGOS",
            value=roles_text,
            inline=False,
        )

        e.set_footer(text=f"Kibot • {badge_count} conquista(s) desbloqueada(s)")
        await send(ctx,embed=e)

    @commands.command(name="nivel",aliases=["lv", "level", "xp", "perfil"])
    async def p_profile(self,ctx,member:discord.Member=None): await self._profile(ctx,member)
    @app_commands.command(name="nivel",description="Vê seu nível, XP e o quanto falta pra subir")
    async def profile(self,interaction,member:discord.Member=None):
        await self._profile(interaction,member)

    @commands.command(name="topxp",aliases=["rankxp", "xptop"])
    async def p_top(self,ctx):
        rows=await db.get_xp_leaderboard(ctx.guild.id,10)
        lines=[]
        for i,r in enumerate(rows,1):
            m=ctx.guild.get_member(r["user_id"]); lines.append(f"**{i}.** {m.display_name if m else r['user_id']} — Lv. {r['level']} ({r['xp']} XP)")
        await ctx.send(embed=KibotEmbed(title="🏆 Ranking de XP",description="\n".join(lines) or "Ainda não tem XP pra mostrar 👀",color=discord.Color.purple()))
    @app_commands.command(name="topxp",description="Vê quem tá farmando XP igual maluco")
    async def top(self,interaction):
        rows=await db.get_xp_leaderboard(interaction.guild_id,10)
        lines=[]
        for i,r in enumerate(rows,1):
            m=interaction.guild.get_member(r["user_id"]); lines.append(f"**{i}.** {m.display_name if m else r['user_id']} — Lv. {r['level']} ({r['xp']} XP)")
        await interaction.response.send_message(embed=KibotEmbed(title="🏆 Ranking de XP",description="\n".join(lines) or "Ainda não tem XP pra mostrar 👀",color=discord.Color.purple()))

    @commands.command(name="painel_niveis",aliases=["nivelcargos","cargos_nivel","nivelcargo","cargonivel"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def level_role_panel(self,ctx): await self.send_panel(ctx)

    @app_commands.command(name="painel_niveis",description="Configura cargos automáticos por nível")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def level_role_panel_slash(self,interaction): await self.send_panel(interaction)

    @app_commands.command(name="config_xp",description="Liga ou desliga o XP das atividades")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def config_xp(self,interaction,ativo:bool):
        await db.set_guild_config(interaction.guild_id,xp_enabled=int(ativo)); await interaction.response.send_message(f"✅ Fechou! XP {'ligado' if ativo else 'desligado'}.")

async def setup(bot): await bot.add_cog(Levels(bot))
