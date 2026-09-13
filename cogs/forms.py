from cogs.embed_style import KibotEmbed
import json
import re
import discord
from discord.ext import commands
from discord import app_commands
from database import db


def clean_text(value, limit):
    return " ".join(str(value or "").split())[:limit]


# A page is represented by:
# {"title": "...", "description": "...", "fields": [
#   {"id":"nome","label":"Seu nome","type":"text","required":true},
#   {"id":"area","label":"Área","type":"choice","options":["Staff","Gestão"]}
# ]}
#
# Legacy forms stored ["pergunta", "..."]. They are transparently converted
# into one page of text fields when opened.
def normalize_pages(raw):
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        data = []

    if not isinstance(data, list):
        data = []

    # Legacy format: ["Pergunta 1", "Pergunta 2", ...]
    if data and all(isinstance(x, str) for x in data):
        return [{
            "title": "Formulário",
            "description": "Responda aos campos abaixo.",
            "fields": [
                {"id": f"q{i}", "label": clean_text(q, 45),
                 "type": "text", "required": True}
                for i, q in enumerate(data[:5])
            ]
        }]

    pages = []
    for pi, page in enumerate(data[:10]):
        if not isinstance(page, dict):
            continue
        fields = []
        for fi, field in enumerate(page.get("fields", [])[:5]):
            if not isinstance(field, dict):
                continue
            ftype = str(field.get("type", "text")).lower()
            if ftype not in {"text", "choice", "multi", "yesno", "number"}:
                ftype = "text"
            label = clean_text(field.get("label", f"Campo {fi+1}"), 45)
            fid = re.sub(r"[^a-zA-Z0-9_-]", "_", str(field.get("id", f"p{pi}f{fi}")))[:40]
            options = [clean_text(x, 100) for x in field.get("options", []) if clean_text(x, 100)]
            if ftype == "choice" and len(options) < 2:
                ftype = "text"
            if ftype == "multi" and len(options) < 2:
                ftype = "text"
            if ftype in {"choice", "multi"}:
                options = options[:10]
            fields.append({
                "id": fid or f"p{pi}f{fi}",
                "label": label or f"Campo {fi+1}",
                "type": ftype,
                "required": bool(field.get("required", True)),
                "options": options
            })
        if fields:
            pages.append({
                "title": clean_text(page.get("title", f"Página {pi+1}"), 45),
                "description": str(page.get("description", "") or "")[:1000],
                "fields": fields
            })

    return pages or [{
        "title": "Formulário",
        "description": "Este formulário ainda não possui campos.",
        "fields": []
    }]


def page_embed(form, pages, page_index, answers=None, closed=False):
    page = pages[page_index]
    status = "🔴 FECHADO" if closed else "🟢 ABERTO"
    desc = str(page.get("description", "") or "")
    e = KibotEmbed(
        title=f"📋 {form['title']} • {page.get('title', f'Página {page_index+1}')}",
        description=(desc + "\n\n" if desc else "") + f"**Status:** {status}\n**Página:** {page_index+1}/{len(pages)}",
        color=discord.Color.red() if closed else discord.Color.gold()
    )
    for field in page.get("fields", []):
        ftype = field.get("type", "text")
        label = field.get("label", "Campo")
        if ftype in {"choice", "multi", "yesno"}:
            opts = field.get("options", []) or (["Sim", "Não"] if ftype == "yesno" else [])
            text = " • ".join(opts[:10])
            if not text:
                text = "Use o botão abaixo para responder."
            e.add_field(name=f"🔘 {label}", value=text[:1024], inline=False)
        else:
            value = (answers or {}).get(field.get("id"))
            e.add_field(name=f"📝 {label}", value=(str(value)[:1024] if value else "Aguardando resposta…"), inline=False)
    e.set_footer(text=f"Formulário #{form['id']}")
    return e


class TextPageModal(discord.ui.Modal):
    def __init__(self, session_view, page):
        self.session_view = session_view
        self.page = page
        super().__init__(title=clean_text(page.get("title", "Responder"), 45))
        for field in page.get("fields", []):
            if field.get("type") not in {"text", "number"}:
                continue
            self.add_item(discord.ui.TextInput(
                label=clean_text(field.get("label", "Campo"), 45),
                custom_id=field.get("id", "field")[:100],
                style=discord.TextStyle.paragraph if field.get("type") == "text" else discord.TextStyle.short,
                required=bool(field.get("required", True)),
                max_length=1000,
                placeholder="Digite sua resposta..."
            ))

    async def on_submit(self, interaction: discord.Interaction):
        for child in self.children:
            value = str(child.value or "").strip()
            self.session_view.answers[child.custom_id] = value
        await interaction.response.edit_message(
            embed=page_embed(
                self.session_view.form,
                self.session_view.pages,
                self.session_view.page_index,
                self.session_view.answers
            ),
            view=self.session_view
        )


class ChoiceSelect(discord.ui.Select):
    def __init__(self, session_view, field):
        self.session_view = session_view
        self.field_id = field["id"]
        options = [
            discord.SelectOption(label=str(x)[:100], value=str(x)[:100])
            for x in field.get("options", [])[:10]
        ]
        super().__init__(
            placeholder=clean_text(field.get("label", "Escolha uma opção"), 150),
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"kibot:form:choice:{session_view.form['id']}:{field['id']}"
        )

    async def callback(self, interaction):
        self.session_view.answers[self.field_id] = self.values[0]
        await interaction.response.edit_message(
            embed=page_embed(
                self.session_view.form,
                self.session_view.pages,
                self.session_view.page_index,
                self.session_view.answers
            ),
            view=self.session_view
        )


class MultiChoiceSelect(discord.ui.Select):
    def __init__(self, session_view, field):
        self.session_view = session_view
        self.field_id = field["id"]
        options = [
            discord.SelectOption(label=str(x)[:100], value=str(x)[:100])
            for x in field.get("options", [])[:10]
        ]
        super().__init__(
            placeholder=clean_text(field.get("label", "Selecione as opções"), 150),
            min_values=1,
            max_values=min(10, len(options)),
            options=options,
            custom_id=f"kibot:form:multi:{session_view.form['id']}:{field['id']}"
        )

    async def callback(self, interaction):
        self.session_view.answers[self.field_id] = ", ".join(self.values)
        await interaction.response.edit_message(
            embed=page_embed(
                self.session_view.form,
                self.session_view.pages,
                self.session_view.page_index,
                self.session_view.answers
            ),
            view=self.session_view
        )


class YesNoSelect(discord.ui.Select):
    def __init__(self, session_view, field):
        self.session_view = session_view
        self.field_id = field["id"]
        super().__init__(
            placeholder=clean_text(field.get("label", "Sim ou não"), 150),
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Sim", value="Sim", emoji="✅"),
                discord.SelectOption(label="Não", value="Não", emoji="❌")
            ],
            custom_id=f"kibot:form:yesno:{session_view.form['id']}:{field['id']}"
        )

    async def callback(self, interaction):
        self.session_view.answers[self.field_id] = self.values[0]
        await interaction.response.edit_message(
            embed=page_embed(
                self.session_view.form,
                self.session_view.pages,
                self.session_view.page_index,
                self.session_view.answers
            ),
            view=self.session_view
        )


class FormSessionView(discord.ui.View):
    def __init__(self, cog, form, pages, user_id, page_index=0, answers=None):
        super().__init__(timeout=900)
        self.cog = cog
        self.form = form
        self.pages = pages
        self.user_id = user_id
        self.page_index = page_index
        self.answers = dict(answers or {})

        page = pages[page_index]
        text_fields = [f for f in page.get("fields", []) if f.get("type") in {"text", "number"}]
        if text_fields:
            b = discord.ui.Button(label="📝 Responder textos", style=discord.ButtonStyle.primary, row=0)
            b.callback = self.open_text_modal
            self.add_item(b)

        row = 1
        for field in page.get("fields", []):
            if field.get("type") == "choice":
                self.add_item(ChoiceSelect(self, field))
            elif field.get("type") == "multi":
                self.add_item(MultiChoiceSelect(self, field))
            elif field.get("type") == "yesno":
                self.add_item(YesNoSelect(self, field))

        if page_index > 0:
            b = discord.ui.Button(label="⬅️ Voltar", style=discord.ButtonStyle.secondary, row=4)
            b.callback = self.back_page
            self.add_item(b)

        if page_index < len(pages) - 1:
            b = discord.ui.Button(label="➡️ Próxima", style=discord.ButtonStyle.primary, row=4)
            b.callback = self.next_page
            self.add_item(b)
        else:
            b = discord.ui.Button(label="✅ Finalizar formulário", style=discord.ButtonStyle.success, row=4)
            b.callback = self.finish
            self.add_item(b)

        cancel = discord.ui.Button(label="✖️ Cancelar", style=discord.ButtonStyle.danger, row=4)
        cancel.callback = self.cancel
        self.add_item(cancel)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("🚫 Esse formulário pertence a outra pessoa.", ephemeral=True)
            return False
        form = await db.get_form(self.form["id"])
        if not form or not form["active"]:
            await interaction.response.send_message("🔒 Este formulário foi fechado pela administração.", ephemeral=True)
            return False
        return True

    async def open_text_modal(self, interaction):
        await interaction.response.send_modal(TextPageModal(self, self.pages[self.page_index]))

    def _missing_required(self):
        missing = []
        for field in self.pages[self.page_index].get("fields", []):
            if field.get("required", True) and not str(self.answers.get(field.get("id"), "")).strip():
                missing.append(field.get("label", "Campo"))
        return missing

    async def next_page(self, interaction):
        missing = self._missing_required()
        if missing:
            return await interaction.response.send_message(
                "❌ Preencha os campos obrigatórios desta página:\n• " + "\n• ".join(missing[:10]),
                ephemeral=True
            )
        self.page_index += 1
        new_view = FormSessionView(self.cog, self.form, self.pages, self.user_id, self.page_index, self.answers)
        await interaction.response.edit_message(
            embed=page_embed(self.form, self.pages, self.page_index, self.answers),
            view=new_view
        )

    async def back_page(self, interaction):
        self.page_index -= 1
        new_view = FormSessionView(self.cog, self.form, self.pages, self.user_id, self.page_index, self.answers)
        await interaction.response.edit_message(
            embed=page_embed(self.form, self.pages, self.page_index, self.answers),
            view=new_view
        )

    async def finish(self, interaction):
        all_missing = []
        for page in self.pages:
            for field in page.get("fields", []):
                if field.get("required", True) and not str(self.answers.get(field.get("id"), "")).strip():
                    all_missing.append(field.get("label", "Campo"))
        if all_missing:
            return await interaction.response.send_message(
                "❌ Ainda faltam campos obrigatórios:\n• " + "\n• ".join(all_missing[:15]),
                ephemeral=True
            )

        cfg = await db.get_form_config(interaction.guild_id)
        if not cfg or not cfg["review_channel_id"]:
            return await interaction.response.send_message(
                "❌ O canal de análise deste formulário ainda não foi configurado.",
                ephemeral=True
            )
        channel = interaction.guild.get_channel(cfg["review_channel_id"])
        if not channel:
            return await interaction.response.send_message("❌ O canal de análise não existe mais.", ephemeral=True)

        packed = []
        for pi, page in enumerate(self.pages, 1):
            for field in page.get("fields", []):
                packed.append({
                    "page": pi,
                    "field_id": field.get("id"),
                    "question": field.get("label"),
                    "type": field.get("type"),
                    "answer": self.answers.get(field.get("id"), "")
                })

        submission_id = await db.create_submission(
            self.form["id"], interaction.guild_id, interaction.user.id,
            json.dumps(packed, ensure_ascii=False)
        )
        embed = KibotEmbed(
            title=f"📨 Nova inscrição — {self.form['title']}",
            description=self.form["description"],
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="Candidato",
            value=f"{interaction.user.mention}\n`{interaction.user}` • `{interaction.user.id}`",
            inline=False
        )
        for item in packed:
            answer = str(item["answer"] or "—")[:1024]
            embed.add_field(
                name=f"P{item['page']} • {clean_text(item['question'], 230)}",
                value=answer, inline=False
            )
        embed.set_footer(text=f"Formulário #{self.form['id']} • Inscrição #{submission_id} • Aguardando análise")

        try:
            await channel.send(embed=embed, view=ReviewView(self.cog, submission_id))
        except discord.HTTPException:
            await db.review_submission(submission_id, self.cog.bot.user.id, "rejected")
            return await interaction.response.send_message(
                "❌ Não consegui enviar sua inscrição para análise. Avise a administração.",
                ephemeral=True
            )
        await interaction.response.edit_message(
            embed=KibotEmbed(
                title="✅ Formulário enviado!",
                description="Sua inscrição foi encaminhada para a equipe responsável.",
                color=discord.Color.green()
            ),
            view=None
        )

    async def cancel(self, interaction):
        await interaction.response.edit_message(
            embed=KibotEmbed(title="✖️ Formulário cancelado", color=discord.Color.red()),
            view=None
        )


class FormButton(discord.ui.Button):
    def __init__(self, cog, form_id):
        super().__init__(
            label="📝 Preencher formulário",
            style=discord.ButtonStyle.primary,
            custom_id=f"kibot:form:{form_id}"
        )
        self.cog = cog
        self.form_id = form_id

    async def callback(self, interaction):
        form = await db.get_form(self.form_id)
        if not form or not form["active"] or form["guild_id"] != interaction.guild_id:
            return await interaction.response.send_message("🔒 Esse formulário está fechado ou indisponível.", ephemeral=True)
        pages = normalize_pages(form["questions"])
        await interaction.response.send_message(
            embed=page_embed(form, pages, 0, {}),
            view=FormSessionView(self.cog, form, pages, interaction.user.id),
            ephemeral=True
        )


class FormPanelView(discord.ui.View):
    def __init__(self, cog, form_id):
        super().__init__(timeout=None)
        self.add_item(FormButton(cog, form_id))


class ReviewView(discord.ui.View):
    def __init__(self, cog, submission_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.submission_id = submission_id
        approve = discord.ui.Button(
            label="✅ Aprovar", style=discord.ButtonStyle.success,
            custom_id=f"kibot:form:approve:{submission_id}"
        )
        reject = discord.ui.Button(
            label="❌ Rejeitar", style=discord.ButtonStyle.danger,
            custom_id=f"kibot:form:reject:{submission_id}"
        )
        approve.callback = self._approve
        reject.callback = self._reject
        self.add_item(approve)
        self.add_item(reject)

    async def _finish_review(self, interaction, status):
        ok = await db.review_submission(self.submission_id, interaction.user.id, status)
        if not ok:
            return await interaction.response.send_message(
                "⚠️ Essa inscrição já foi analisada por outra pessoa.", ephemeral=True
            )
        color = discord.Color.green() if status == "approved" else discord.Color.red()
        label = "APROVADA" if status == "approved" else "REJEITADA"
        for child in self.children:
            child.disabled = True
        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0].copy()
            embed.color = color
            embed.set_footer(text=f"{embed.footer.text or ''} • {label} por {interaction.user.display_name}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(f"✅ Inscrição {label.lower()}.", ephemeral=True)
        row = await db.get_submission(self.submission_id)
        if row:
            member = interaction.guild.get_member(row["user_id"])
            if member:
                try:
                    await member.send(
                        f"📋 Sua inscrição **{row['form_id']}** no servidor "
                        f"**{interaction.guild.name}** foi **{label.lower()}**."
                    )
                except discord.HTTPException:
                    pass

    async def _approve(self, interaction): await self._finish_review(interaction, "approved")
    async def _reject(self, interaction): await self._finish_review(interaction, "rejected")

    async def interaction_check(self, interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "🚫 Só a equipe com **Gerenciar Servidor** pode analisar formulários.", ephemeral=True
            )
            return False
        return True


# ========================= TEMPLATES =========================

def template_pages(kind):
    templates = {
        "staff": {
            "name": "staff",
            "title": "Recrutamento — Equipe Staff",
            "description": "Inscrição para fazer parte da equipe de Staff do servidor.",
            "pages": [
                {"title": "Apresentação", "description": "Conte um pouco sobre você.", "fields": [
                    {"id":"nome","label":"Como devemos te chamar?","type":"text","required":True},
                    {"id":"idade","label":"Qual sua idade?","type":"number","required":True},
                    {"id":"fuso","label":"Qual seu fuso/horário habitual?","type":"text","required":True},
                ]},
                {"title": "Experiência", "description": "Queremos conhecer sua experiência.", "fields": [
                    {"id":"experiencia","label":"Você já foi Staff em outro servidor?","type":"yesno","required":True},
                    {"id":"areas","label":"Quais áreas você domina?","type":"multi","options":["Moderação","Atendimento","Eventos","RPG","Bots","Organização"],"required":True},
                    {"id":"detalhes","label":"Conte sobre sua experiência.","type":"text","required":True},
                ]},
                {"title": "Situações", "description": "Avaliação de postura e tomada de decisão.", "fields": [
                    {"id":"conflito","label":"Como lidaria com uma discussão entre membros?","type":"text","required":True},
                    {"id":"regra","label":"O que faria se um amigo quebrasse uma regra?","type":"text","required":True},
                    {"id":"pressao","label":"Como age quando precisa tomar uma decisão sob pressão?","type":"text","required":True},
                ]},
                {"title": "Disponibilidade", "description": "Últimas informações.", "fields": [
                    {"id":"horarios","label":"Quanto tempo costuma ter disponível por dia?","type":"choice","options":["Menos de 1h","1–2h","2–4h","4h+"],"required":True},
                    {"id":"cargo","label":"Qual área deseja atuar?","type":"choice","options":["Moderação","Atendimento","Eventos","RPG","Outro"],"required":True},
                    {"id":"motivacao","label":"Por que quer entrar para a Staff?","type":"text","required":True},
                ]}
            ]
        },
        "gestao": {
            "name": "gestao",
            "title": "Recrutamento — Gestão",
            "description": "Inscrição para cargos de gestão e liderança.",
            "pages": [
                {"title":"Perfil","description":"Informações básicas.", "fields":[
                    {"id":"nome","label":"Como devemos te chamar?","type":"text","required":True},
                    {"id":"idade","label":"Qual sua idade?","type":"number","required":True},
                    {"id":"area","label":"Qual área deseja gerir?","type":"choice","options":["Staff","Eventos","RPG","Comunidade","Projetos"],"required":True},
                ]},
                {"title":"Liderança","description":"Mostre como você pensa como gestor.", "fields":[
                    {"id":"lideranca","label":"Como define uma boa liderança?","type":"text","required":True},
                    {"id":"conflito","label":"Como resolveria um conflito entre dois membros da equipe?","type":"text","required":True},
                    {"id":"decisao","label":"Como tomaria uma decisão impopular, mas necessária?","type":"text","required":True},
                ]},
                {"title":"Planejamento","description":"Visão de futuro para o servidor.", "fields":[
                    {"id":"projeto","label":"Que projeto você gostaria de implementar?","type":"text","required":True},
                    {"id":"organizacao","label":"Como organizaria sua equipe?","type":"text","required":True},
                    {"id":"disponibilidade","label":"Qual sua disponibilidade?","type":"choice","options":["Baixa","Média","Alta","Muito alta"],"required":True},
                ]}
            ]
        },
        "parceria": {
            "name":"parceria","title":"Formulário de Parceria",
            "description":"Solicitação de parceria com o servidor.",
            "pages":[
                {"title":"Projeto","fields":[
                    {"id":"nome","label":"Nome do servidor/projeto","type":"text","required":True},
                    {"id":"tipo","label":"Tipo de projeto","type":"choice","options":["Servidor Discord","Criador","Comunidade","Projeto","Empresa"],"required":True},
                    {"id":"link","label":"Convite ou link público","type":"text","required":True},
                ]},
                {"title":"Proposta","fields":[
                    {"id":"publico","label":"Qual o público aproximado?","type":"number","required":True},
                    {"id":"proposta","label":"Explique a proposta de parceria.","type":"text","required":True},
                    {"id":"beneficio","label":"O que cada comunidade ganha com a parceria?","type":"text","required":True},
                ]}
            ]
        },
        "evento": {
            "name":"evento","title":"Proposta de Evento",
            "description":"Envie uma ideia de evento para o servidor.",
            "pages":[
                {"title":"Ideia","fields":[
                    {"id":"titulo","label":"Nome do evento","type":"text","required":True},
                    {"id":"tipo","label":"Categoria","type":"choice","options":["RPG","Competição","Comunidade","Música","Outro"],"required":True},
                    {"id":"descricao","label":"Descreva o evento.","type":"text","required":True},
                ]},
                {"title":"Execução","fields":[
                    {"id":"publico","label":"Público esperado","type":"number","required":True},
                    {"id":"equipe","label":"Você precisa de ajuda da equipe?","type":"yesno","required":True},
                    {"id":"planejamento","label":"Como pretende organizar o evento?","type":"text","required":True},
                ]}
            ]
        },
        "feedback": {
            "name":"feedback","title":"Feedback da Comunidade",
            "description":"Ajude a equipe a melhorar o servidor.",
            "pages":[
                {"title":"Avaliação","fields":[
                    {"id":"nota","label":"Como avalia o servidor?","type":"choice","options":["1","2","3","4","5"],"required":True},
                    {"id":"pontos","label":"O que está funcionando bem?","type":"text","required":False},
                    {"id":"melhoria","label":"O que deveríamos melhorar?","type":"text","required":True},
                ]}
            ]
        }
    }
    return templates.get(kind.lower())


class Forms(commands.Cog):
    """Formulários multi-página, campos de escolha, abertura/fechamento e templates."""

    def __init__(self, bot):
        self.bot = bot

    async def initialize_views(self):
        if getattr(self, "_views_registered", False):
            return
        self._views_registered = True
        for guild in self.bot.guilds:
            try:
                for form in await db.get_forms(guild.id):
                    self.bot.add_view(FormPanelView(self, form["id"]))
                pending = await db.get_pending_submissions(guild.id)
                for row in pending:
                    self.bot.add_view(ReviewView(self, row["id"]))
            except Exception:
                continue

    @staticmethod
    def is_admin(interaction):
        return interaction.user.guild_permissions.manage_guild

    async def _config(self, interaction, kind, channel):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        if kind == "painel":
            await db.set_form_config(interaction.guild_id, panel_channel_id=channel.id)
        else:
            await db.set_form_config(interaction.guild_id, review_channel_id=channel.id)
        await interaction.response.send_message(f"✅ Canal de **{kind}** configurado em {channel.mention}.", ephemeral=True)

    form_group = app_commands.Group(name="formulario", description="Cria e administra formulários do servidor")

    @form_group.command(name="painel", description="Define o canal dos painéis")
    async def painel(self, interaction, canal: discord.TextChannel):
        await self._config(interaction, "painel", canal)

    @form_group.command(name="destino", description="Define o canal de análise")
    async def destino(self, interaction, canal: discord.TextChannel):
        await self._config(interaction, "destino", canal)

    @form_group.command(name="criar", description="Cria um formulário simples ou avançado")
    @app_commands.describe(
        nome="Identificador",
        titulo="Título",
        descricao="Descrição",
        perguntas="Perguntas separadas por | (compatibilidade; até 5)"
    )
    async def criar(self, interaction, nome: str, titulo: str, descricao: str, perguntas: str):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        qs = [clean_text(x, 45) for x in perguntas.split("|") if clean_text(x, 45)]
        if not qs or len(qs) > 5:
            return await interaction.response.send_message("❌ Informe de 1 a 5 perguntas, separadas por `|`.", ephemeral=True)
        pages = [{"title":"Página 1","description":descricao[:1000],
                  "fields":[{"id":f"q{i}","label":q,"type":"text","required":True} for i,q in enumerate(qs)]}]
        form_id = await db.create_form(
            interaction.guild_id, clean_text(nome.lower(),50), clean_text(titulo,45),
            str(descricao).strip()[:1000], json.dumps(pages, ensure_ascii=False)
        )
        self.bot.add_view(FormPanelView(self, form_id))
        await interaction.response.send_message(
            f"✅ Formulário **{titulo[:45]}** criado com ID `{form_id}`.\n"
            f"Use `/formulario publicar {form_id}`.", ephemeral=True
        )

    @form_group.command(name="modelo", description="Cria um formulário pronto")
    @app_commands.describe(tipo="staff, gestao, parceria, evento ou feedback")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Staff", value="staff"),
        app_commands.Choice(name="Gestão", value="gestao"),
        app_commands.Choice(name="Parceria", value="parceria"),
        app_commands.Choice(name="Evento", value="evento"),
        app_commands.Choice(name="Feedback", value="feedback"),
    ])
    async def modelo(self, interaction, tipo: app_commands.Choice[str]):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        tpl = template_pages(tipo.value)
        form_id = await db.create_form(
            interaction.guild_id, tpl["name"], tpl["title"], tpl["description"],
            json.dumps(tpl["pages"], ensure_ascii=False)
        )
        self.bot.add_view(FormPanelView(self, form_id))
        await interaction.response.send_message(
            f"✅ Modelo **{tpl['title']}** criado com ID `{form_id}`.\n"
            f"Use `/formulario publicar {form_id}` para colocar o painel no canal configurado.",
            ephemeral=True
        )

    @form_group.command(name="abrir", description="Abre um formulário para novas respostas")
    async def abrir(self, interaction, formulario_id: int):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        if await db.set_form_active(formulario_id, interaction.guild_id, True):
            await interaction.response.send_message(f"🟢 Formulário `{formulario_id}` **aberto**.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Formulário não encontrado neste servidor.", ephemeral=True)

    @form_group.command(name="fechar", description="Fecha um formulário para novas respostas")
    async def fechar(self, interaction, formulario_id: int):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        if await db.set_form_active(formulario_id, interaction.guild_id, False):
            await interaction.response.send_message(f"🔴 Formulário `{formulario_id}` **fechado**. Respostas pendentes continuam disponíveis para análise.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Formulário não encontrado neste servidor.", ephemeral=True)

    @form_group.command(name="status", description="Mostra o estado de um formulário")
    async def status(self, interaction, formulario_id: int):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        form = await db.get_form(formulario_id)
        if not form or form["guild_id"] != interaction.guild_id:
            return await interaction.response.send_message("❌ Formulário não encontrado.", ephemeral=True)
        pages = normalize_pages(form["questions"])
        await interaction.response.send_message(
            f"📋 **{form['title']}**\n"
            f"ID: `{form['id']}`\n"
            f"Estado: {'🟢 Aberto' if form['active'] else '🔴 Fechado'}\n"
            f"Páginas: **{len(pages)}**\n"
            f"Campos: **{sum(len(p.get('fields',[])) for p in pages)}**",
            ephemeral=True
        )

    @form_group.command(name="publicar", description="Publica o painel")
    async def publicar(self, interaction, formulario_id: int):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        form = await db.get_form(formulario_id)
        cfg = await db.get_form_config(interaction.guild_id)
        if not form or form["guild_id"] != interaction.guild_id:
            return await interaction.response.send_message("❌ Formulário não encontrado.", ephemeral=True)
        if not cfg or not cfg["panel_channel_id"]:
            return await interaction.response.send_message("❌ Configure primeiro o canal com `/formulario painel #canal`.", ephemeral=True)
        channel = interaction.guild.get_channel(cfg["panel_channel_id"])
        if not channel:
            return await interaction.response.send_message("❌ O canal do painel não existe mais.", ephemeral=True)
        pages = normalize_pages(form["questions"])
        e = KibotEmbed(
            title=f"📋 {form['title']}",
            description=(form["description"] + "\n\n" if form["description"] else "") +
                        ("🟢 **Aberto para respostas.**" if form["active"] else "🔴 **Fechado para respostas.**"),
            color=discord.Color.gold() if form["active"] else discord.Color.red()
        )
        e.add_field(
            name="Estrutura",
            value="\n".join(
                f"**Página {i}.** {p.get('title','Página')} — {len(p.get('fields',[]))} campo(s)"
                for i,p in enumerate(pages,1)
            )[:1024],
            inline=False
        )
        await channel.send(embed=e, view=FormPanelView(self, form["id"]))
        await interaction.response.send_message(f"✅ Painel publicado em {channel.mention}.", ephemeral=True)

    @form_group.command(name="listar", description="Lista os formulários")
    async def listar(self, interaction):
        if not self.is_admin(interaction):
            return await interaction.response.send_message("🚫 Você precisa de **Gerenciar Servidor**.", ephemeral=True)
        forms = await db.get_forms(interaction.guild_id)
        text = "\n".join(
            f"`{f['id']}` • **{f['title']}** — {'🟢 aberto' if f['active'] else '🔴 fechado'}"
            for f in forms
        ) or "Nenhum formulário criado."
        await interaction.response.send_message(text, ephemeral=True)

    # ---------------- PREFIX COMMANDS ----------------
    @commands.group(name="formulario", aliases=["form","forms"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def p_formulario(self, ctx):
        await ctx.send(
            "📋 **Formulários Avançados**\n"
            "`K! formulario painel #canal`\n"
            "`K! formulario destino #canal`\n"
            "`K! formulario criar nome | Título | Descrição | Pergunta 1 | ...`\n"
            "`K! formulario modelo staff|gestao|parceria|evento|feedback`\n"
            "`K! formulario abrir ID`\n"
            "`K! formulario fechar ID`\n"
            "`K! formulario status ID`\n"
            "`K! formulario publicar ID`\n"
            "`K! formulario listar`"
        )

    @p_formulario.command(name="painel")
    async def p_painel(self, ctx, canal: discord.TextChannel):
        await db.set_form_config(ctx.guild.id, panel_channel_id=canal.id)
        await ctx.send(f"✅ Canal do painel: {canal.mention}")

    @p_formulario.command(name="destino")
    async def p_destino(self, ctx, canal: discord.TextChannel):
        await db.set_form_config(ctx.guild.id, review_channel_id=canal.id)
        await ctx.send(f"✅ Canal de análise: {canal.mention}")

    @p_formulario.command(name="criar")
    async def p_criar(self, ctx, *, dados: str):
        parts = [x.strip() for x in dados.split("|")]
        if len(parts) < 4 or len(parts) > 8:
            return await ctx.send("❌ Use: `K! formulario criar nome | título | descrição | pergunta 1 | ... | pergunta 5`.")
        name, title, desc = parts[:3]
        qs = [clean_text(x,45) for x in parts[3:] if clean_text(x,45)]
        pages = [{"title":"Página 1","description":desc[:1000],
                  "fields":[{"id":f"q{i}","label":q,"type":"text","required":True} for i,q in enumerate(qs)]}]
        form_id = await db.create_form(
            ctx.guild.id, clean_text(name.lower(),50), clean_text(title,45), desc[:1000],
            json.dumps(pages, ensure_ascii=False)
        )
        self.bot.add_view(FormPanelView(self, form_id))
        await ctx.send(f"✅ Formulário criado com ID `{form_id}`. Use `K! formulario publicar {form_id}`.")

    @p_formulario.command(name="modelo")
    async def p_modelo(self, ctx, tipo: str):
        tpl = template_pages(tipo.lower())
        if not tpl:
            return await ctx.send("❌ Modelos: `staff`, `gestao`, `parceria`, `evento`, `feedback`.")
        form_id = await db.create_form(
            ctx.guild.id, tpl["name"], tpl["title"], tpl["description"],
            json.dumps(tpl["pages"], ensure_ascii=False)
        )
        self.bot.add_view(FormPanelView(self, form_id))
        await ctx.send(f"✅ Modelo **{tpl['title']}** criado com ID `{form_id}`. Use `K! formulario publicar {form_id}`.")

    @p_formulario.command(name="abrir")
    async def p_abrir(self, ctx, formulario_id: int):
        if await db.set_form_active(formulario_id, ctx.guild.id, True):
            await ctx.send(f"🟢 Formulário `{formulario_id}` aberto.")
        else:
            await ctx.send("❌ Formulário não encontrado neste servidor.")

    @p_formulario.command(name="fechar")
    async def p_fechar(self, ctx, formulario_id: int):
        if await db.set_form_active(formulario_id, ctx.guild.id, False):
            await ctx.send(f"🔴 Formulário `{formulario_id}` fechado. Inscrições pendentes continuam para análise.")
        else:
            await ctx.send("❌ Formulário não encontrado neste servidor.")

    @p_formulario.command(name="status")
    async def p_status(self, ctx, formulario_id: int):
        form = await db.get_form(formulario_id)
        if not form or form["guild_id"] != ctx.guild.id:
            return await ctx.send("❌ Formulário não encontrado.")
        pages = normalize_pages(form["questions"])
        await ctx.send(
            f"📋 **{form['title']}** • `{form['id']}`\n"
            f"Estado: {'🟢 aberto' if form['active'] else '🔴 fechado'}\n"
            f"Páginas: **{len(pages)}** • Campos: **{sum(len(p.get('fields',[])) for p in pages)}**"
        )

    @p_formulario.command(name="publicar")
    async def p_publicar(self, ctx, formulario_id: int):
        form = await db.get_form(formulario_id)
        cfg = await db.get_form_config(ctx.guild.id)
        if not form or form["guild_id"] != ctx.guild.id:
            return await ctx.send("❌ Formulário não encontrado.")
        if not cfg or not cfg["panel_channel_id"]:
            return await ctx.send("❌ Configure `K! formulario painel #canal` primeiro.")
        channel = ctx.guild.get_channel(cfg["panel_channel_id"])
        if not channel:
            return await ctx.send("❌ O canal do painel não existe mais.")
        pages = normalize_pages(form["questions"])
        e = KibotEmbed(
            title=f"📋 {form['title']}",
            description=(form["description"] + "\n\n" if form["description"] else "") +
                        ("🟢 **Aberto para respostas.**" if form["active"] else "🔴 **Fechado para respostas.**"),
            color=discord.Color.gold() if form["active"] else discord.Color.red()
        )
        e.add_field(
            name="Estrutura",
            value="\n".join(
                f"**Página {i}.** {p.get('title','Página')} — {len(p.get('fields',[]))} campo(s)"
                for i,p in enumerate(pages,1)
            )[:1024], inline=False
        )
        await channel.send(embed=e, view=FormPanelView(self, form["id"]))
        await ctx.send(f"✅ Painel publicado em {channel.mention}.")

    @p_formulario.command(name="listar")
    async def p_listar(self, ctx):
        forms = await db.get_forms(ctx.guild.id)
        await ctx.send(
            "\n".join(
                f"`{f['id']}` • **{f['title']}** — {'🟢 aberto' if f['active'] else '🔴 fechado'}"
                for f in forms
            ) or "Nenhum formulário criado."
        )


async def setup(bot):
    await bot.add_cog(Forms(bot))
