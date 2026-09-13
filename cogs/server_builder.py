from cogs.embed_style import KibotEmbed
import discord
from discord.ext import commands
from discord import app_commands


# Templates base. Cada módulo opcional acrescenta canais/categorias sem apagar a estrutura existente.
TEMPLATES = {
    "game": {
        "label": "Game", "emoji": "🎮",
        "description": "Estrutura para comunidades de jogos, partidas, eventos e jogadores.",
        "roles": [
            ("👑 Dono", 0xF1C40F, {"manage_guild": True, "manage_channels": True, "manage_roles": True, "manage_messages": True, "moderate_members": True, "kick_members": True, "ban_members": True}),
            ("🛡️ Administrador", 0xE74C3C, {"manage_channels": True, "manage_roles": True, "manage_messages": True, "moderate_members": True, "kick_members": True, "ban_members": True}),
            ("🔨 Moderador", 0xE67E22, {"manage_messages": True, "moderate_members": True, "kick_members": True}),
            ("🎮 Player", 0x3498DB, {}), ("🤖 Bots", 0x95A5A6, {"manage_messages": True}),
        ],
        "categories": [
            ("📌・INFORMAÇÕES", [("📜・regras", "text", "read_only"), ("📢・anúncios", "text", "read_only"), ("👋・boas-vindas", "text", "read_only")]),
            ("💬・COMUNIDADE", [("💬・chat-geral", "text", "public"), ("🎮・games", "text", "public"), ("🤝・encontre-jogadores", "text", "public"), ("🔊・Sala Geral", "voice", "public"), ("🎧・Sala 2", "voice", "public")]),
            ("🏆・EVENTOS", [("🏆・eventos", "text", "public"), ("🎁・sorteios", "text", "public")]),
            ("🛡️・STAFF", [("🛡️・staff-chat", "text", "staff"), ("📋・logs", "text", "staff"), ("🔊・staff", "voice", "staff")]),
        ],
    },
    "rpg": {
        "label": "RPG", "emoji": "🎲",
        "description": "Estrutura para mesas, campanhas, fichas, sessões, lore e mestraria.",
        "roles": [
            ("👑 Mestre", 0xF1C40F, {"manage_guild": True, "manage_channels": True, "manage_roles": True, "manage_messages": True, "moderate_members": True}),
            ("📖 Narrador", 0x9B59B6, {"manage_channels": True, "manage_messages": True}),
            ("🛡️ Moderador", 0xE67E22, {"manage_messages": True, "moderate_members": True}),
            ("🎲 Jogador", 0x3498DB, {}), ("👤 Visitante", 0x95A5A6, {}), ("🤖 Bots", 0x7F8C8D, {"manage_messages": True}),
        ],
        "categories": [
            ("📜・CENTRAL", [("📜・regras", "text", "read_only"), ("📢・anúncios", "text", "read_only"), ("🗓️・sessões", "text", "read_only")]),
            ("🎲・RPG", [("💬・chat-rpg", "text", "public"), ("📖・lore", "text", "public"), ("📂・arquivos", "text", "public"), ("🧾・fichas", "text", "public"), ("🎵・músicas", "text", "public"), ("🔊・Call Principal", "voice", "public"), ("🔊・Call Off-Topic", "voice", "public")]),
            ("🧙・MESTRARIA", [("📚・mestre-chat", "text", "staff"), ("🗺️・planejamento", "text", "staff"), ("🔒・segredos", "text", "staff")]),
            ("🛡️・STAFF", [("🛡️・staff-chat", "text", "staff"), ("📋・logs", "text", "staff")]),
        ],
    },
    "comunidade": {
        "label": "Comunidade", "emoji": "🌐",
        "description": "Estrutura social para conversa, amizades, eventos, cinema e convivência.",
        "roles": [
            ("👑 Imperador", 0xF1C40F, {"manage_guild": True, "manage_channels": True, "manage_roles": True, "manage_messages": True, "moderate_members": True, "kick_members": True, "ban_members": True}),
            ("🛡️ Gestão", 0xE74C3C, {"manage_channels": True, "manage_roles": True, "manage_messages": True, "moderate_members": True}),
            ("🔨 Moderador", 0xE67E22, {"manage_messages": True, "moderate_members": True}),
            ("🤝 Membro", 0x3498DB, {}), ("🌱 Novato", 0x2ECC71, {}), ("🤖 Bots", 0x95A5A6, {"manage_messages": True}),
        ],
        "categories": [
            ("📌・CENTRAL", [("📜・regras", "text", "read_only"), ("📢・anúncios", "text", "read_only"), ("👋・boas-vindas", "text", "read_only"), ("🗺️・informações", "text", "read_only")]),
            ("💬・CONVIVÊNCIA", [("💬・chat-geral", "text", "public"), ("😂・memes", "text", "public"), ("🎨・galeria", "text", "public"), ("🎵・música", "text", "public"), ("🔊・Sala Geral", "voice", "public"), ("🎧・Sala Social", "voice", "public")]),
            ("🎉・EVENTOS", [("🎉・eventos", "text", "public"), ("🎬・cinema", "text", "public")]),
            ("🛡️・STAFF", [("🛡️・gestão", "text", "staff"), ("📋・logs", "text", "staff"), ("🔊・staff", "voice", "staff")]),
        ],
    },
}

MODULES = {
    "tempvoice": ("🔊 TempVoice", "Salas de voz temporárias + painel de controle."),
    "economia": ("💰 Economia", "Canais para Crowings, trabalho, loja e ranking financeiro."),
    "xp": ("⭐ XP & Níveis", "Ranking e progressão da comunidade."),
    "logs": ("📋 Logs", "Área privada dedicada aos registros do servidor."),
    "tickets": ("🎫 Tickets", "Central privada para atendimento e suporte."),
    "rpg_extra": ("📚 RPG Avançado", "Campanhas, NPCs, bestiário, mapas e arquivos extras."),
}

MODULE_CHANNELS = {
    "economia": ("💰・ECONOMIA", [("💰・economia", "text", "public"), ("💼・trabalho", "text", "public"), ("🏦・ranking", "text", "public")]),
    "xp": ("⭐・PROGRESSÃO", [("⭐・ranking-xp", "text", "public"), ("🏆・níveis", "text", "public")]),
    "logs": ("📋・REGISTROS", [("📋・logs", "text", "staff"), ("🛡️・mod-logs", "text", "staff")]),
    "tickets": ("🎫・ATENDIMENTO", [("🎫・abrir-ticket", "text", "public"), ("📨・atendimento", "text", "staff"), ("📋・ticket-logs", "text", "staff")]),
    "rpg_extra": ("🗺️・ARQUIVO RPG", [("🧙・npc", "text", "public"), ("👹・bestiário", "text", "public"), ("🗺️・mapas", "text", "public"), ("📜・documentos", "text", "public")]),
}


def perms_from_dict(data):
    return discord.Permissions(**data)


class SetupModal(discord.ui.Modal, title="Configuração do Servidor"):
    server_name = discord.ui.TextInput(label="Nome do servidor", placeholder="Deixe vazio para manter o nome atual", required=False, max_length=100)
    theme = discord.ui.TextInput(label="Tema / identidade", placeholder="Ex.: Kiba, medieval, cyberpunk...", required=False, max_length=100)

    def __init__(self, view):
        super().__init__()
        self.parent_view = view

    async def on_submit(self, interaction):
        self.parent_view.server_name = str(self.server_name).strip() or None
        self.parent_view.theme = str(self.theme).strip() or None
        await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)


class BuilderView(discord.ui.View):
    def __init__(self, cog, owner_id, guild, preset=None):
        super().__init__(timeout=300)
        self.cog, self.owner_id, self.guild = cog, owner_id, guild
        self.template = preset if preset in TEMPLATES else "comunidade"
        self.modules = {"tempvoice", "logs"}
        self.server_name = None
        self.theme = None
        self.confirmed = False
        self.template_select = TemplateSelect(self)
        self.module_select = ModuleSelect(self)
        self.add_item(self.template_select)
        self.add_item(self.module_select)

    def build_embed(self):
        t = TEMPLATES[self.template]
        module_text = "\n".join(f"• {MODULES[m][0]} — {MODULES[m][1]}" for m in sorted(self.modules)) or "• Nenhum módulo opcional"
        role_count = len(t["roles"])
        base_channels = sum(len(ch) for _, ch in t["categories"])
        extra_channels = sum(len(MODULE_CHANNELS[m][1]) for m in self.modules if m in MODULE_CHANNELS)
        e = KibotEmbed(title=f"🏗️ Kibot Server Builder", color=discord.Color.blurple())
        e.description = f"**{t['emoji']} {t['label']}**\n{t['description']}\n\nEscolha o template, módulos e configurações abaixo. Nada será criado até você confirmar."
        e.add_field(name="📛 Identidade", value=f"**Nome:** {self.server_name or self.guild.name}\n**Tema:** {self.theme or 'Padrão'}", inline=False)
        e.add_field(name="🏗️ Estrutura", value=f"• 🏷️ {role_count} cargos base\n• 📁 {len(t['categories']) + sum(1 for m in self.modules if m in MODULE_CHANNELS)} categorias\n• 📺 até {base_channels + extra_channels} canais", inline=True)
        e.add_field(name="🧩 Módulos", value=module_text[:1024], inline=True)
        e.add_field(name="🔐 Segurança", value="Somente o dono do Kibot pode confirmar. O modo padrão é **não destrutivo**: canais/cargos existentes não são apagados.", inline=False)
        e.set_footer(text="Configure tudo e depois clique em Revisar & Confirmar.")
        return e

    @discord.ui.button(label="Configurar nome", emoji="⚙️", style=discord.ButtonStyle.secondary, row=2)
    async def config(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Somente o dono do Kibot pode configurar esta operação.", ephemeral=True)
        await interaction.response.send_modal(SetupModal(self))

    @discord.ui.button(label="Revisar & Confirmar", emoji="🏗️", style=discord.ButtonStyle.success, row=2)
    async def review(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Somente o dono do Kibot pode confirmar esta operação.", ephemeral=True)
        confirm = ConfirmBuildView(self)
        e = self.build_embed()
        e.title = "⚠️ Revisão final — construir servidor?"
        e.description = (e.description or "") + "\n\n**Esta é a última etapa.** O Kibot usará as permissões concedidas no servidor e executará a configuração." 
        await interaction.response.edit_message(embed=e, view=confirm)

    @discord.ui.button(label="Cancelar", emoji="✖️", style=discord.ButtonStyle.danger, row=2)
    async def cancel(self, interaction, button):
        if interaction.user.id != self.owner_id:
            return await interaction.response.send_message("❌ Somente o dono do Kibot pode cancelar esta operação.", ephemeral=True)
        await interaction.response.edit_message(content="🛑 **Construção cancelada.** Nada foi alterado pelo Kibot.", embed=None, view=None)


class TemplateSelect(discord.ui.Select):
    def __init__(self, parent):
        self.parent_view = parent
        super().__init__(placeholder="1️⃣ Escolha o tipo de servidor", min_values=1, max_values=1, row=0, options=[
            discord.SelectOption(label="Game", value="game", emoji="🎮", description="Jogos, partidas e eventos"),
            discord.SelectOption(label="RPG", value="rpg", emoji="🎲", description="Campanhas, fichas e mestraria"),
            discord.SelectOption(label="Comunidade", value="comunidade", emoji="🌐", description="Conversa, eventos e convivência"),
        ])
    async def callback(self, interaction):
        if interaction.user.id != self.parent_view.owner_id:
            return await interaction.response.send_message("❌ Somente o dono do Kibot pode configurar.", ephemeral=True)
        self.parent_view.template = self.values[0]
        if self.parent_view.template != "rpg":
            self.parent_view.modules.discard("rpg_extra")
        await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)


class ModuleSelect(discord.ui.Select):
    def __init__(self, parent):
        self.parent_view = parent
        options = [discord.SelectOption(label=v[0].replace("🔊 ", "").replace("💰 ", "").replace("⭐ ", "").replace("📋 ", "").replace("🎫 ", "").replace("📚 ", ""), value=k, emoji=v[0].split()[0], description=v[1]) for k, v in MODULES.items()]
        super().__init__(placeholder="2️⃣ Escolha os módulos extras (pode selecionar vários)", min_values=0, max_values=len(options), options=options, row=1)
    async def callback(self, interaction):
        if interaction.user.id != self.parent_view.owner_id:
            return await interaction.response.send_message("❌ Somente o dono do Kibot pode configurar.", ephemeral=True)
        self.parent_view.modules = set(self.values)
        if "logs" not in self.parent_view.modules:
            # logs não é obrigatório; o template base ainda pode ter um canal staff se já possuir.
            pass
        await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)


class ConfirmBuildView(discord.ui.View):
    def __init__(self, builder):
        super().__init__(timeout=120)
        self.builder = builder

    async def interaction_check(self, interaction):
        if interaction.user.id != self.builder.owner_id:
            await interaction.response.send_message("❌ Somente o dono do Kibot pode confirmar esta construção.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="SIM, CONSTRUIR", emoji="🏗️", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        if self.builder.confirmed:
            return
        self.builder.confirmed = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="⏳ **Construindo o servidor...**\nO Kibot está criando cargos, categorias, canais e permissões. Aguarde.", embed=None, view=self)
        try:
            result = await self.builder.cog.build_server(self.builder.guild, self.builder.template, self.builder.modules, self.builder.server_name, self.builder.theme)
            await interaction.edit_original_response(content=result, view=None)
        except Exception as exc:
            await interaction.edit_original_response(content=f"❌ **Falha durante a construção:** `{type(exc).__name__}: {exc}`", view=None)

    @discord.ui.button(label="Voltar", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        await interaction.response.edit_message(content=None, embed=self.builder.build_embed(), view=self.builder)

    @discord.ui.button(label="Cancelar", emoji="✖️", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content="🛑 **Construção cancelada.** Nenhuma alteração foi feita pelo Kibot.", embed=None, view=None)


class ServerBuilder(commands.Cog):
    """Wizard de criação de servidores controlado exclusivamente pelo dono do Kibot."""
    def __init__(self, bot):
        self.bot = bot

    async def _owner_only(self, interaction_or_ctx):
        user = interaction_or_ctx.user if isinstance(interaction_or_ctx, discord.Interaction) else interaction_or_ctx.author
        return await self.bot.is_owner(user)

    async def build_server(self, guild, key, modules=None, server_name=None, theme=None):
        modules = set(modules or [])
        template = TEMPLATES[key]
        me = guild.me or (guild.get_member(self.bot.user.id) if self.bot.user else None)
        if not me:
            raise RuntimeError("Não consegui localizar o Kibot neste servidor.")
        required = ["manage_guild", "manage_channels", "manage_roles"]
        missing = [p for p in required if not getattr(me.guild_permissions, p, False)]
        if missing:
            raise RuntimeError("O Kibot precisa destas permissões: " + ", ".join(missing))

        if server_name and server_name != guild.name:
            await guild.edit(name=server_name, reason="Kibot Server Builder — nome confirmado pelo dono")

        created_roles = {}
        for name, color, perm_data in template["roles"]:
            role = discord.utils.get(guild.roles, name=name)
            if role is None:
                role = await guild.create_role(name=name, colour=discord.Colour(color), permissions=perms_from_dict(perm_data), reason=f"Kibot Server Builder — {key}")
            created_roles[name] = role

        # O cargo mais alto criado fica abaixo do maior cargo do bot; o bot nunca tenta assumir a propriedade do servidor.
        ordered = [created_roles[n] for n, _, _ in template["roles"] if n in created_roles]
        try:
            base = max(1, me.top_role.position - 1)
            for idx, role in enumerate(reversed(ordered)):
                if role < me.top_role:
                    await role.edit(position=max(1, base - idx), reason="Kibot Server Builder — hierarquia")
        except (discord.Forbidden, discord.HTTPException):
            pass

        staff_roles = [r for r in created_roles.values() if any(x in r.name.lower() for x in ("dono", "imperador", "administrador", "gestão", "mestre", "narrador", "moderador"))]
        everyone = guild.default_role
        staff_overwrites = {everyone: discord.PermissionOverwrite(view_channel=False)}
        for role in staff_roles:
            staff_overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, connect=True, speak=True)

        categories_new = 0; channels_new = 0
        all_categories = list(template["categories"])
        for module in modules:
            if module in MODULE_CHANNELS:
                all_categories.append(MODULE_CHANNELS[module])

        for category_name, channels in all_categories:
            category = discord.utils.get(guild.categories, name=category_name)
            if category is None:
                category = await guild.create_category(category_name, reason=f"Kibot Server Builder — {key}")
                categories_new += 1
            is_staff_category = any(token in category_name.upper() for token in ("STAFF", "MESTRARIA", "REGISTROS"))
            if is_staff_category:
                await category.edit(overwrites=staff_overwrites, reason="Kibot: área privada")
            for channel_name, kind, visibility in channels:
                existing = discord.utils.get(category.channels, name=channel_name)
                if existing is not None:
                    continue
                overwrites = None
                if is_staff_category or visibility == "staff":
                    overwrites = staff_overwrites
                elif visibility == "read_only":
                    overwrites = {everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=True, read_message_history=True)}
                # discord.py exige que `overwrites`, quando informado, seja um dict.
                # Não passe `None`: simplesmente omita o argumento quando não há regras especiais.
                channel_kwargs = {"category": category, "reason": f"Kibot Server Builder — {key}"}
                if overwrites is not None:
                    channel_kwargs["overwrites"] = overwrites
                if kind == "voice":
                    await guild.create_voice_channel(channel_name, **channel_kwargs)
                else:
                    await guild.create_text_channel(channel_name, **channel_kwargs)
                channels_new += 1

        if "tempvoice" in modules:
            # O cog TempVoice já possui bootstrap automático e detectará esta configuração/estrutura.
            temp_category = discord.utils.get(guild.categories, name="TEMPVOICE")
            if temp_category is None:
                temp_category = await guild.create_category("TEMPVOICE", reason="Kibot Server Builder — TempVoice")
                categories_new += 1
            lobby = discord.utils.get(temp_category.voice_channels, name="Lobby")
            if lobby is None:
                await guild.create_voice_channel("Lobby", category=temp_category, reason="Kibot Server Builder — TempVoice")
                channels_new += 1
            panel = discord.utils.get(temp_category.text_channels, name="🎛️・tempvoice")
            if panel is None:
                ow = {everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False), me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)}
                await guild.create_text_channel("🎛️・tempvoice", category=temp_category, overwrites=ow, reason="Kibot Server Builder — TempVoice")
                channels_new += 1

        summary = [
            "✅ **Servidor construído com sucesso!**",
            f"{template['emoji']} Template: **{template['label']}**",
            f"📛 Nome: **{guild.name}**",
            f"🏷️ Cargos verificados/criados: **{len(created_roles)}**",
            f"📁 Categorias novas: **{categories_new}**",
            f"📺 Canais novos: **{channels_new}**",
            f"🧩 Módulos: **{', '.join(MODULES[m][0] for m in modules) if modules else 'nenhum'}**",
            "🔐 Permissões e áreas privadas foram configuradas.",
        ]
        if theme:
            summary.append(f"🎨 Identidade registrada: **{theme}**")
        summary.append("\n⚠️ O Kibot não apaga canais/cargos existentes e não transforma o bot em dono do servidor.")
        return "\n".join(summary)

    async def start_wizard(self, ctx_or_interaction, preset=None):
        if not await self._owner_only(ctx_or_interaction):
            msg = "❌ **Acesso negado.** O Server Builder é exclusivo do dono configurado do Kibot."
            if isinstance(ctx_or_interaction, discord.Interaction):
                return await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            return await ctx_or_interaction.send(msg)
        guild = ctx_or_interaction.guild
        if guild is None:
            msg = "❌ Esse comando só pode ser usado dentro de um servidor."
            if isinstance(ctx_or_interaction, discord.Interaction):
                return await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            return await ctx_or_interaction.send(msg)
        view = BuilderView(self, ctx_or_interaction.user.id if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author.id, guild, preset)
        embed = view.build_embed()
        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await ctx_or_interaction.send(embed=embed, view=view)

    @commands.command(name="criarservidor", aliases=["servidor", "serverbuilder", "builder"])
    @commands.is_owner()
    async def criarservidor(self, ctx, tipo: str = None):
        aliases = {"jogo": "game", "games": "game", "game": "game", "rpg": "rpg", "comunidade": "comunidade", "community": "comunidade", "social": "comunidade"}
        key = aliases.get((tipo or "").lower().strip()) if tipo else None
        await self.start_wizard(ctx, key)

    @app_commands.command(name="criarservidor", description="Abre o assistente completo de criação de servidor")
    @app_commands.describe(tipo="Opcional: já iniciar com um template")
    @app_commands.choices(tipo=[app_commands.Choice(name="🎮 Game", value="game"), app_commands.Choice(name="🎲 RPG", value="rpg"), app_commands.Choice(name="🌐 Comunidade", value="comunidade")])
    async def criarservidor_slash(self, interaction: discord.Interaction, tipo: app_commands.Choice[str] | None = None):
        await self.start_wizard(interaction, tipo.value if tipo else None)


async def setup(bot):
    await bot.add_cog(ServerBuilder(bot))
