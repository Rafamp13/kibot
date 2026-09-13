from cogs.embed_style import KibotEmbed
import random
import re
import discord
from discord.ext import commands
from discord import app_commands

DICE_RE = re.compile(r'^(?P<count>\d*)d(?P<sides>\d+)(?P<kd>(?:k[hl]?\d+|d[hl]?\d+)?)?(?P<mods>(?:[+-]\d+)*)$', re.I)
REPEAT_RE = re.compile(r'^(?P<n>\d+)#(?P<expr>.+)$', re.I)
MAX_DICE, MAX_SIDES, MAX_TERMS, MAX_REPEAT = 100, 1000, 20, 20

SYSTEMS = {
    'd20': ('🎲 Sistema D20', discord.Color.blurple(), 'Rolagem padrão de dados poliédricos.'),
    'dnd': ('⚔️ D&D', discord.Color.gold(), 'Rolagem d20 com leitura de crítico natural e falha crítica.'),
    'coc': ('🐙 Call of Cthulhu', discord.Color.dark_teal(), 'Rolagem percentual com sucesso regular, difícil, extremo e falha crítica.'),
    'cthulhu': ('🐙 Call of Cthulhu', discord.Color.dark_teal(), 'Rolagem percentual com sucesso regular, difícil, extremo e falha crítica.'),
    'percentil': ('🎯 Percentual', discord.Color.orange(), 'Rolagem percentual contra um valor-alvo.'),
    'percentile': ('🎯 Percentual', discord.Color.orange(), 'Rolagem percentual contra um valor-alvo.'),
}

def _mods(text):
    vals=[]; pos=0
    for m in re.finditer(r'[+-]\d+', text or ''):
        if m.start()!=pos: raise ValueError('Modificador inválido.')
        vals.append(int(m.group())); pos=m.end()
    if pos != len(text or ''): raise ValueError('Modificador inválido.')
    return sum(vals)

def roll_expression(expr):
    expr=re.sub(r'\s+', '', expr or '')
    repeat=1
    rm=REPEAT_RE.fullmatch(expr)
    if rm:
        repeat=int(rm.group('n')); expr=rm.group('expr')
        if not 1<=repeat<=MAX_REPEAT: raise ValueError(f'Repetição entre 1 e {MAX_REPEAT}.')
    m=DICE_RE.fullmatch(expr)
    if not m: raise ValueError('Use `1d20+5`, `2d20kh1`, `4d6dl1` ou `6#4d6dl1`.')
    count=int(m.group('count') or 1); sides=int(m.group('sides'))
    if not 1<=count<=MAX_DICE: raise ValueError(f'Quantidade de dados entre 1 e {MAX_DICE}.')
    if not 2<=sides<=MAX_SIDES: raise ValueError(f'Dado entre 2 e {MAX_SIDES} lados.')
    modifier=_mods(m.group('mods'))
    kd=m.group('kd') or ''; mode=None; amount=0
    if kd:
        mode=kd[0].lower()
        if len(kd)>=2 and kd[1].lower() in ('h','l'):
            direction=kd[1].lower(); amount=int(kd[2:])
        else:
            direction='h' if mode=='k' else 'l'; amount=int(kd[1:])
        mode += direction
        if not 1<=amount<=count: raise ValueError('Quantidade keep/drop inválida.')
    results=[]
    for _ in range(repeat):
        rolls=[random.randint(1,sides) for _ in range(count)]
        kept=list(rolls); dropped=[]
        if mode=='kh': kept=sorted(rolls, reverse=True)[:amount]; dropped=sorted(rolls)[:count-amount]
        elif mode=='kl': kept=sorted(rolls)[:amount]; dropped=sorted(rolls, reverse=True)[:count-amount]
        elif mode=='dl':
            dropped=sorted(rolls)[:amount]; kept=list(rolls)
            for v in dropped: kept.remove(v)
        elif mode=='dh':
            dropped=sorted(rolls, reverse=True)[:amount]; kept=list(rolls)
            for v in dropped: kept.remove(v)
        results.append({'rolls':rolls,'kept':kept,'dropped':dropped,'total':sum(kept)+modifier})
    return {'expression':expr,'modifier':modifier,'repeat':repeat,'results':results,'sides':sides}

def _critical_status(result, sides):
    if sides == 20 and len(result['rolls']) == 1:
        n=result['rolls'][0]
        if n == 20: return 'critical'
        if n == 1: return 'fumble'
    return None

def _roll_embed(title, description, color, data, system='d20'):
    e=KibotEmbed(title=title, description=description, color=color)
    e.set_author(name='Kibot • Sistema de Dados')
    for i,r in enumerate(data['results'],1):
        status=_critical_status(r,data['sides'])
        shown=[]; dropped=list(r['dropped'])
        for v in r['rolls']:
            if v in dropped: shown.append(f'~~{v}~~'); dropped.remove(v)
            else: shown.append(str(v))
        value=f"**Total:** `{r['total']}`\n**Dados:** `[{', '.join(shown)}]`"
        if data['modifier']: value += f"\n**Modificador:** `{data['modifier']:+d}`"
        if status=='critical': value += '\n\n🔥 **CRÍTICO! — SUCESSO NATURAL** 🔥'
        elif status=='fumble': value += '\n\n💀 **FALHA CRÍTICA! — FALHA NATURAL** 💀'
        name=f"Resultado {i}" if data['repeat']>1 else 'Resultado'
        e.add_field(name=name, value=value, inline=False)
    e.set_footer(text=f"Expressão: {data['expression']} • {system.upper()}")
    return e

def coc_roll(skill):
    if not 1<=skill<=100: raise ValueError('A perícia deve estar entre 1 e 100.')
    roll=random.randint(1,100)
    hard=max(1, skill//2); extreme=max(1, skill//5)
    if roll==1: result='CRÍTICO'
    elif roll >= 96 and skill < 50: result='FALHA CRÍTICA'
    elif roll == 100: result='FALHA CRÍTICA'
    elif roll <= extreme: result='SUCESSO EXTREMO'
    elif roll <= hard: result='SUCESSO DIFÍCIL'
    elif roll <= skill: result='SUCESSO REGULAR'
    else: result='FALHA'
    return roll, hard, extreme, result

def coc_embed(skill, label=None):
    roll, hard, extreme, result=coc_roll(skill)
    if 'CRÍTICO' in result:
        color=discord.Color.red(); icon='💀' if 'FALHA' in result else '🔥'; headline=f'{icon} **{result}!** {icon}'
    elif 'EXTREMO' in result: color=discord.Color.dark_green(); headline='🟢 **SUCESSO EXTREMO**'
    elif 'DIFÍCIL' in result: color=discord.Color.green(); headline='🟢 **SUCESSO DIFÍCIL**'
    elif result=='SUCESSO REGULAR': color=discord.Color.teal(); headline='🟢 **SUCESSO REGULAR**'
    else: color=discord.Color.dark_red(); headline='🔻 **FALHA**'
    e=KibotEmbed(title='🐙 Call of Cthulhu • Rolagem Percentual', color=color)
    e.set_author(name='Kibot • Investigação Paranormal')
    if label: e.description=f'**Perícia:** {label}'
    e.add_field(name='🎯 Resultado', value=f'`{roll:02d}`', inline=True)
    e.add_field(name='📜 Perícia', value=f'`{skill}`', inline=True)
    e.add_field(name='⚙️ Limiares', value=f'Normal: `{skill}`\nDifícil: `{hard}`\nExtremo: `{extreme}`', inline=True)
    e.add_field(name='🕯️ Julgamento', value=headline, inline=False)
    e.set_footer(text='Call of Cthulhu • 1–100 • 01 = crítico • 100 = falha crítica')
    return e

class DiceEngine(commands.Cog):
    def __init__(self, bot): self.bot=bot

    async def _send_expr(self, target, expr):
        data=roll_expression(expr)
        e=_roll_embed('🎲 Rolagem de Dados', 'Resultado da rolagem.', discord.Color.blurple(), data)
        await target.send(embed=e)

    @app_commands.command(name='dado', description='Rola dados: 1d20+5, 2d20kh1, 4d6dl1 ou 6#4d6dl1')
    async def slash_dado(self, interaction: discord.Interaction, expressao: str='1d6'):
        try: data=roll_expression(expressao)
        except ValueError as ex: await interaction.response.send_message(f'❌ {ex}', ephemeral=True); return
        await interaction.response.send_message(embed=_roll_embed('🎲 Rolagem de Dados','Resultado da rolagem.',discord.Color.blurple(),data))

    @app_commands.command(name='coc', description='Call of Cthulhu: role 1d100 contra uma perícia')
    async def slash_coc(self, interaction: discord.Interaction, pericia: int, nome: str=''):
        try: e=coc_embed(pericia, nome.strip() or None)
        except ValueError as ex: await interaction.response.send_message(f'❌ {ex}', ephemeral=True); return
        await interaction.response.send_message(embed=e)

    @commands.command(name='coc', aliases=['cthulhu','percentil'])
    async def cmd_coc(self, ctx, pericia: int, *, nome=''):
        try: e=coc_embed(pericia, nome.strip() or None)
        except ValueError as ex: await ctx.send(f'❌ {ex}'); return
        await ctx.send(embed=e)

    @commands.command(name='dado', aliases=['d','roll','rolar'])
    async def cmd_dado(self, ctx, *, expressao='1d6'):
        try: data=roll_expression(expressao)
        except ValueError as ex: await ctx.send(f'❌ {ex}'); return
        await ctx.send(embed=_roll_embed('🎲 Rolagem de Dados','Resultado da rolagem.',discord.Color.blurple(),data))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild: return
        content=message.content.strip()
        if not content or content.startswith(('/', '<@')): return
        # Nunca intercepta comandos prefixados.
        if content.startswith('K!') or content.startswith('k!'): return
        # Atalhos CoC sem prefixo: "coc 65" / "cthulhu 55" / "percentil 70"
        m=re.fullmatch(r'(?:coc|cthulhu|percentil|percentile)\s+(\d{1,3})(?:\s+(.+))?', content, re.I)
        if m:
            try: await message.channel.send(embed=coc_embed(int(m.group(1)), m.group(2)))
            except ValueError: pass
            return
        # Blocos [1d20+5 ataque] e expressões separadas por espaço, vírgula ou ;.
        blocks=re.findall(r'\[([^\]]+)\]', content)
        if blocks:
            parsed=[]
            for block in blocks:
                p=block.strip().split(maxsplit=1)
                try: parsed.append((p[1] if len(p)>1 else None, roll_expression(p[0])))
                except ValueError: pass
            if parsed:
                for label,data in parsed:
                    e=_roll_embed('🎲 Rolagem de Dados', f'**{label}**' if label else 'Resultado da rolagem.', discord.Color.blurple(), data)
                    await message.channel.send(embed=e)
                return
        parts=[p for p in re.split(r'[;,\s]+',content) if p]
        if not parts or len(parts)>MAX_TERMS: return
        parsed=[]
        for p in parts:
            try: parsed.append(roll_expression(p))
            except ValueError: return
        for data in parsed:
            await message.channel.send(embed=_roll_embed('🎲 Rolagem de Dados','Resultado da rolagem.',discord.Color.blurple(),data))

async def setup(bot): await bot.add_cog(DiceEngine(bot))
