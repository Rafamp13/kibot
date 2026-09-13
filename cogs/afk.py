from cogs.embed_style import KibotEmbed
import discord
from discord import app_commands
from discord.ext import commands
from database import db

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_delete_delay = 5  # segundos

    async def _send_temp(self, channel, *, embed):
        """Envia uma mensagem do AFK e apaga automaticamente depois de alguns segundos."""
        try:
            sent = await channel.send(embed=embed)
            await sent.delete(delay=self.message_delete_delay)
        except (discord.Forbidden, discord.HTTPException):
            # Se o bot não puder apagar a mensagem, ela continua visível normalmente.
            pass

    async def _activate(self, member, reason):
        old_nick = member.nick
        await db.set_afk(member.id, member.guild.id, old_nick, reason)
        new_nick = f"[AFK] {member.display_name}"
        if len(new_nick)>32: new_nick=new_nick[:32]
        changed=True
        try:
            await member.edit(nick=new_nick, reason="Kibot: AFK ativado")
        except (discord.Forbidden, discord.HTTPException):
            changed=False
        return changed

    async def _deactivate(self, member):
        row=await db.get_afk(member.id,member.guild.id)
        if not row:return False
        try:
            await member.edit(nick=row["original_nick"],reason="Kibot: AFK encerrado")
        except (discord.Forbidden, discord.HTTPException):
            pass
        await db.clear_afk(member.id,member.guild.id)
        return True

    async def _activate_command(self, member, channel, motivo):
        row=await db.get_afk(member.id,member.guild.id)
        if row:
            await self._send_temp(channel, embed=KibotEmbed(
                title="💤 Você já tá AFK kkkkk",
                description="Você já tá AFK. Manda uma mensagem quando voltar que eu tiro.",
                color=discord.Color.gold()
            ))
            return
        changed=await self._activate(member,motivo)
        desc=f"💤 **{member.display_name}** entrou em AFK.\n**Motivo:** {motivo}\n\nQuando alguém mencionar você, o Kibot avisará que você está AFK."
        if not changed:
            desc += "\n\n⚠️ Não consegui alterar seu apelido porque a hierarquia/permissão do Discord não permite. O AFK continua funcionando normalmente."
        await self._send_temp(channel, embed=KibotEmbed(
            title="💤 AFK ligado",
            description=desc,
            color=discord.Color.gold()
        ))

    @commands.command(name="afk", aliases=["ausente"])
    async def afk(self,ctx,*,motivo="Não informado"):
        await self._activate_command(ctx.author, ctx.channel, motivo)

    @app_commands.command(name="afk", description="Ativa seu AFK e deixa o motivo")
    @app_commands.describe(motivo="Motivo da ausência (opcional)")
    async def afk_slash(self, interaction: discord.Interaction, motivo: str = "Não informado"):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Esse comando só funciona dentro de um servidor, chefia.", ephemeral=True)
            return
        # A resposta da interação é apenas o Embed temporário enviado pelo helper.
        await self._activate_command(interaction.user, interaction.channel, motivo)

    @commands.Cog.listener("on_message")
    async def on_message(self,message):
        if message.author.bot or not message.guild:return
        # Qualquer mensagem do próprio usuário encerra o AFK.
        own=await db.get_afk(message.author.id,message.guild.id)
        if own:
            await self._deactivate(message.author)
            await self._send_temp(message.channel, embed=KibotEmbed(
                title="👋 Voltou, né? AFK desligado",
                description=f"{message.author.mention} voltou e saiu do modo AFK.",
                color=discord.Color.green()
            ))
        # Avise quem mencionou usuários AFK.
        afks=[]
        for member in message.mentions:
            row=await db.get_afk(member.id,message.guild.id)
            if row: afks.append((member,row))
        if afks:
            lines=[]
            for member,row in afks:
                reason=row["reason"] or "Não informado"
                lines.append(f"💤 {member.mention} está **AFK** — {reason}")
            await self._send_temp(message.channel, embed=KibotEmbed(
                title="💤 Tem gente AFK aqui",
                description="\n".join(lines),
                color=discord.Color.gold()
            ))

async def setup(bot): await bot.add_cog(AFK(bot))
