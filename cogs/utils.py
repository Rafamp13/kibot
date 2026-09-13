from cogs.embed_style import KibotEmbed
import random
import asyncio
import json
import urllib.request
import config
import discord
from database import db

async def send(ctx, content=None, embed=None, ephemeral=False):
    if isinstance(ctx, discord.Interaction):
        if ctx.response.is_done():
            return await ctx.followup.send(content=content, embed=embed, ephemeral=ephemeral)
        return await ctx.response.send_message(content=content, embed=embed, ephemeral=ephemeral)
    return await ctx.send(content=content, embed=embed)

async def log_action(guild, title, description, color=discord.Color.dark_gray()):
    if not guild:
        return False
    cfg = await db.get_guild_config(guild.id)
    cid = cfg["log_channel_id"]
    if not cid:
        return False
    channel = guild.get_channel(cid)
    if not channel:
        try:
            channel = await guild.fetch_channel(cid)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            channel = None
    if not channel:
        return False
    embed = KibotEmbed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
    embed.set_footer(text="Kibot • Log de moderação")
    try:
        await channel.send(embed=embed)
        return True
    except discord.HTTPException:
        import logging
        logging.getLogger("kibot.logs").exception("Não consegui enviar log no canal %s", cid)
        return False


ANIME_GIF_BASE = "https://nekos.best/api/v2"
_ANIME_GIF_CACHE = {}

async def anime_gif(category):
    """Busca um GIF anime SFW no NekosBest e retorna a URL direta.

    O serviço é sem chave de API e fornece GIFs anime por categoria.
    Há um cache curto por categoria para evitar chamadas excessivas.
    """
    category = str(category).strip().lower()
    allowed = {
        "angry","baka","blowkiss","blush","bonk","carry","clap","confused",
        "cry","cuddle","dance","facepalm","feed","happy","handhold","handshake",
        "highfive","hug","kick","kiss","laugh","lappillow","nod","nope","nya",
        "pat","peck","poke","pout","punch","run","salute","shake","shoot",
        "shocked","shrug","slap","sleep","smile","smug","spin","stare",
        "tableflip","teehee","think","thumbsup","tickle","wag","wave","wink",
        "yawn","yeet"
    }
    if category not in allowed:
        category = "happy"
    now = asyncio.get_running_loop().time()
    cached = _ANIME_GIF_CACHE.get(category)
    if cached and now - cached[0] < 15:
        return cached[1]

    def fetch():
        req = urllib.request.Request(
            f"{ANIME_GIF_BASE}/{category}",
            headers={"User-Agent": "Kibot (Discord bot; anime GIF decoration)"},
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        results = data.get("results") or []
        return results[0].get("url") if results else None

    try:
        url = await asyncio.to_thread(fetch)
    except Exception:
        url = None
    if url:
        _ANIME_GIF_CACHE[category] = (now, url)
    return url

async def set_anime_gif(embed, category):
    url = await anime_gif(category)
    if url:
        embed.set_image(url=url)
    return embed


async def media(ctx, text=None, gif=True, sticker=True, gif_category="happy"):
    """Responde com GIF anime SFW e, se disponível, uma figurinha do servidor."""
    await send(ctx,text)
    if gif:
        e=KibotEmbed(); await set_anime_gif(e, gif_category)
        if e.image and e.image.url:
            await ctx.channel.send(embed=e)
    guild=ctx.guild
    if sticker and guild:
        stickers=list(guild.stickers)
        if stickers:
            try: await ctx.channel.send(stickers=[random.choice(stickers)])
            except discord.HTTPException: pass
    return

AMOUNT_SUFFIXES = {
    "k": 10**3,
    "mil": 10**3,
    "m": 10**6,
    "mi": 10**6,
    "kk": 10**6,
    "b": 10**9,
    "bi": 10**9,
    "t": 10**12,
    "tri": 10**12,
    "q": 10**15,
}

def parse_amount(value, base=None):
    """Aceita números/sufixos e, quando base é informado, `all` e `half`."""
    if isinstance(value, int):
        return value
    text = str(value).strip().lower().replace(" ", "")
    if not text:
        return None
    if text in {"all", "tudo", "total"}:
        return int(base) if base is not None else None
    if text in {"half", "metade"}:
        return int(base) // 2 if base is not None else None
    for suffix in sorted(AMOUNT_SUFFIXES, key=len, reverse=True):
        if text.endswith(suffix):
            number = text[:-len(suffix)].replace(",", ".")
            try:
                result = float(number) * AMOUNT_SUFFIXES[suffix]
                if result.is_integer():
                    return int(result)
            except ValueError:
                return None
            return None
    try:
        # Permite separador de milhar brasileiro: 1.000.000
        if text.count(".") > 1 and "," not in text:
            text = text.replace(".", "")
        elif text.isdigit():
            pass
        return int(text)
    except ValueError:
        return None

def format_amount_short(amount):
    amount = int(amount)
    for suffix, divisor in (("q",10**15),("t",10**12),("b",10**9),("m",10**6),("k",10**3)):
        if amount >= divisor and amount % divisor == 0:
            return f"{amount//divisor}{suffix}"
    return str(amount)


def xp_multiplier(member):
    """Retorna o multiplicador de XP do membro. Dono e Booster recebem 2x."""
    if not member:
        return 1
    try:
        if int(getattr(member, "id", 0)) in {int(x) for x in (getattr(config, "OWNER_IDS", []) or [])}:
            return int(getattr(config, "XP_BOOST_MULTIPLIER", 2))
    except (TypeError, ValueError):
        pass
    booster_role_id = int(getattr(config, "XP_BOOSTER_ROLE_ID", 0) or 0)
    if booster_role_id and any(int(getattr(role, "id", 0)) == booster_role_id for role in getattr(member, "roles", [])):
        return int(getattr(config, "XP_BOOST_MULTIPLIER", 2))
    return 1


def relationship_crw_multiplier(relation_type):
    return {"dating":1.05,"married":1.15}.get(str(relation_type or ""),1.0)

async def async_boosted_crw(member,amount):
    amount=max(0,int(amount))
    if not member or not getattr(member,"guild",None): return amount
    rel=await db.get_relationship(member.guild.id,member.id)
    return max(amount,int(round(amount*relationship_crw_multiplier(rel["relation_type"] if rel else None))))

def boosted_xp(member, amount):
    """Aplica o bônus de XP sem alterar o valor base exibido pela configuração."""
    return max(0, int(amount)) * xp_multiplier(member)
