"""Sistema visual global dos embeds do Kibot.

Layout adaptativo: campos inline continuam em colunas quando o comando
explicitamente pede isso; campos longos continuam ocupando a largura inteira.
"""
import discord


class KibotEmbed(discord.Embed):
    DEFAULT_FOOTER = "Kibot • Sistema do servidor"
    FIELD_PADDING = "\n{value}\n"
    SECTION_NAME = "──────────────"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("timestamp", discord.utils.utcnow())
        description = kwargs.get("description")
        if isinstance(description, str) and description.strip():
            kwargs["description"] = description.strip()
        super().__init__(*args, **kwargs)
        if not getattr(self.footer, "text", None):
            self.set_footer(text=self.DEFAULT_FOOTER)

    def add_field(self, *, name, value, inline=False):
        """Mantém a intenção de layout de cada comando, com respiro.

        V39 forçava TODOS os campos para uma coluna. Isso destruía embeds
        como perfil, saldo, tickets e status, que foram escritos para usar
        2/3 colunas. A V40 respeita inline=True e apenas melhora o espaçamento.
        """
        name = name.strip() if isinstance(name, str) else name
        if isinstance(value, str):
            value = value.strip() or "\u200b"
            value = self.FIELD_PADDING.format(value=value)
        return super().add_field(name=name, value=value, inline=bool(inline))

    def add_section(self, title, *, emoji="", color=None):
        """Adiciona um cabeçalho visual de seção sem conteúdo apertado."""
        label = f"{emoji} {title}".strip()
        self.add_field(name=label, value="\u200b", inline=False)
        return self

    def add_spacer(self):
        """Adiciona uma pequena separação vertical entre blocos."""
        self.add_field(name="\u200b", value="\u200b", inline=False)
        return self

    def set_footer(self, *, text=None, icon_url=None):
        return super().set_footer(text=text, icon_url=icon_url)
