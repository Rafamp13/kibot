"""Kibot Web — site + dashboard backend.

Run with: uvicorn web_api:app --host 0.0.0.0 --port 8080
This is intentionally dependency-light and keeps Discord OAuth/session handling in this service.
"""

import os
import secrets
import urllib.parse
import json
import logging
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from database import db
import httpx


BASE = Path(__file__).resolve().parent
WEB = BASE / "web"

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")

PUBLIC_URL = os.getenv(
    "WEB_PUBLIC_URL",
    "http://localhost:8080"
).rstrip("/")

SESSION_SECRET = os.getenv(
    "WEB_SESSION_SECRET",
    secrets.token_urlsafe(32)
)

BOT_INVITE_URL = os.getenv("BOT_INVITE_URL", "")

logger = logging.getLogger("kibot")


app = FastAPI(
    title="Kibot Web API",
    version="1.0.0"
)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=PUBLIC_URL.startswith("https://")
)


@app.get("/")
async def home():
    return FileResponse(
        WEB / "static" / "index.html"
    )


@app.get("/comandos")
async def commands_page():
    return FileResponse(
        WEB / "static" / "commands.html"
    )


@app.get("/dashboard")
async def dashboard():
    return FileResponse(
        WEB / "static" / "dashboard.html"
    )


@app.get("/static/{path:path}")
async def static_files(path: str):
    file = WEB / "static" / path

    if not file.exists() or not file.is_file():
        return JSONResponse(
            {"error": "not_found"},
            status_code=404
        )

    return FileResponse(file)


# ============================================================
# DISCORD OAUTH
# ============================================================

@app.get("/login")
async def login(request: Request):

    if not CLIENT_ID or not CLIENT_SECRET:
        return JSONResponse(
            {
                "error": (
                    "Configure DISCORD_CLIENT_ID e "
                    "DISCORD_CLIENT_SECRET no .env"
                )
            },
            status_code=503
        )

    state = secrets.token_urlsafe(32)

    request.session["oauth_state"] = state

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": f"{PUBLIC_URL}/oauth/callback",
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    }

    return RedirectResponse(
        "https://discord.com/oauth2/authorize?"
        + urllib.parse.urlencode(params)
    )


@app.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None
):

    if error:
        return RedirectResponse(
            "/dashboard?login=cancelled"
        )

    expected_state = request.session.pop(
        "oauth_state",
        None
    )

    if (
        not state
        or not expected_state
        or not secrets.compare_digest(
            state,
            expected_state
        )
    ):
        return RedirectResponse(
            "/dashboard?login=state_error"
        )

    if not code or not CLIENT_ID or not CLIENT_SECRET:
        return RedirectResponse(
            "/dashboard?login=error"
        )

    async with httpx.AsyncClient(timeout=15) as client:

        token_resp = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": (
                    f"{PUBLIC_URL}/oauth/callback"
                ),
            },
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            }
        )

        if token_resp.status_code >= 400:

            logger.error(
                "OAuth token error: HTTP %s - %s",
                token_resp.status_code,
                token_resp.text[:1000]
            )

            return RedirectResponse(
                "/dashboard?login=token_error"
            )

        token = token_resp.json().get(
            "access_token"
        )

        if not token:
            return RedirectResponse(
                "/dashboard?login=token_error"
            )

        user_resp = await client.get(
            "https://discord.com/api/users/@me",
            headers={
                "Authorization":
                    f"Bearer {token}"
            }
        )

        guild_resp = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={
                "Authorization":
                    f"Bearer {token}"
            }
        )

    # ========================================================
    # SESSION
    # ========================================================
    #
    # Não salvamos o token OAuth nem dados gigantes na sessão.
    # Isso evita ultrapassar o limite de tamanho do cookie
    # utilizado pelo SessionMiddleware.
    #

    user = user_resp.json()

    guilds = (
        guild_resp.json()
        if guild_resp.status_code < 400
        else []
    )

    request.session.clear()

    request.session["user"] = {
        "id": user.get("id"),
        "username": user.get("username"),
        "global_name": user.get("global_name"),
        "avatar": user.get("avatar"),
        "discriminator": user.get("discriminator"),
    }

    request.session["guilds"] = [
        {
            "id": guild.get("id"),
            "name": guild.get("name"),
            "owner": bool(guild.get("owner")),
            "permissions": guild.get(
                "permissions",
                "0"
            ),
        }
        for guild in guilds
    ]

    return RedirectResponse(
        "/dashboard"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.get("/logout")
async def logout(request: Request):

    request.session.clear()

    return RedirectResponse("/")


# ============================================================
# USER / SESSION
# ============================================================

@app.get("/api/me")
async def me(request: Request):

    user = request.session.get("user")

    if not user:
        return JSONResponse(
            {
                "authenticated": False
            }
        )

    return {
        "authenticated": True,
        "user": user,
        "guilds": request.session.get(
            "guilds",
            []
        )
    }


# ============================================================
# STATS
# ============================================================

@app.get("/api/stats")
async def stats(request: Request):

    guilds = request.session.get(
        "guilds",
        []
    )

    try:

        conn = await db.get_connection()

        async with conn.execute(
            "SELECT COUNT(*) FROM users"
        ) as cur:

            users = int(
                (await cur.fetchone())[0]
            )

    except Exception:

        users = 0

    return {
        "servers": len(guilds),
        "users": users,
        "commands": 0,
        "status": "online"
    }


# ============================================================
# MANAGED GUILD
# ============================================================

def _managed_guild(
    request: Request,
    guild_id: int
):

    for guild in request.session.get(
        "guilds",
        []
    ):

        if int(
            guild.get("id", 0)
        ) != int(guild_id):
            continue

        permissions = int(
            guild.get(
                "permissions",
                0
            )
        )

        if (
            guild.get("owner")
            or (permissions & 0x8)
        ):
            return guild

    raise HTTPException(
        status_code=403,
        detail=(
            "Você não administra este servidor."
        )
    )


# ============================================================
# GUILD CONFIG
# ============================================================

@app.get(
    "/api/guilds/{guild_id}/config"
)
async def guild_config(
    request: Request,
    guild_id: int
):

    _managed_guild(
        request,
        guild_id
    )

    row = await db.get_guild_config(
        guild_id
    )

    return {
        "guild_id": guild_id,

        "log_channel_id":
            row["log_channel_id"],

        "mute_role_id":
            row["mute_role_id"],

        "welcome_channel_id":
            row["welcome_channel_id"],

        "welcome_message":
            row["welcome_message"],

        "welcome_style":
            row["welcome_style"],

        "auto_ban_bets_channel_id":
            row["auto_ban_bets_channel_id"],

        "auto_ban_bets_enabled":
            bool(
                row["auto_ban_bets_enabled"]
            ),

        "xp_enabled":
            bool(
                row["xp_enabled"]
            ),

        "moderation_confirmations_enabled":
            bool(
                row[
                    "moderation_confirmations_enabled"
                ]
            ),
    }


@app.patch(
    "/api/guilds/{guild_id}/config"
)
async def update_guild_config(
    request: Request,
    guild_id: int
):

    _managed_guild(
        request,
        guild_id
    )

    payload = await request.json()

    allowed_bool = {
        "auto_ban_bets_enabled",
        "xp_enabled",
        "moderation_confirmations_enabled",
    }

    allowed_int = {
        "log_channel_id",
        "mute_role_id",
        "welcome_channel_id",
        "auto_ban_bets_channel_id",
    }

    allowed_text = {
        "welcome_message",
        "welcome_style",
    }

    clean = {}

    for key, value in payload.items():

        if key in allowed_bool:

            clean[key] = (
                1 if bool(value) else 0
            )

        elif key in allowed_int:

            clean[key] = (
                int(value)
                if value not in (None, "")
                else None
            )

        elif key in allowed_text:

            clean[key] = str(value)[:1000]

    if not clean:

        raise HTTPException(
            status_code=400,
            detail=(
                "Nenhuma configuração válida "
                "foi enviada."
            )
        )

    await db.set_guild_config(
        guild_id,
        **clean
    )

    return await guild_config(
        request,
        guild_id
    )


# ============================================================
# COMMAND CATALOG
# ============================================================

@app.get("/api/commands")
async def command_catalog():

    return {
        "commands": [

            {
                "name": "ajuda",
                "category": "Utilidade",
                "description":
                    "Abre a central de ajuda do Kibot."
            },

            {
                "name": "perfil",
                "category": "Níveis",
                "description":
                    "Mostra seu perfil e progresso."
            },

            {
                "name": "daily",
                "category": "Economia",
                "description":
                    "Resgata sua recompensa diária."
            },

            {
                "name": "rotina",
                "category": "Social",
                "description":
                    "Mostra as tarefas sociais do dia."
            },

            {
                "name": "mines",
                "category": "Arcade",
                "description":
                    "Jogue Mines com quantidade "
                    "de bombas configurável."
            },

            {
                "name": "8ball",
                "category": "Diversão",
                "description":
                    "Pergunte ao oráculo do caos."
            },

            {
                "name": "namorar",
                "category": "Relacionamentos",
                "description":
                    "Faça uma proposta de namoro."
            },

            {
                "name": "casamento",
                "category": "Relacionamentos",
                "description":
                    "Tente transformar namoro "
                    "em casamento."
            },

            {
                "name": "divorciar",
                "category": "Relacionamentos",
                "description":
                    "Encerra seu relacionamento atual."
            },

            {
                "name": "addemoji",
                "category": "Servidor",
                "description":
                    "Adiciona um emoji ao servidor."
            },

            {
                "name": "addfigurinha",
                "category": "Servidor",
                "description":
                    "Adiciona uma figurinha ao servidor."
            },

            {
                "name": "automodstatus",
                "category": "Moderação",
                "description":
                    "Mostra o status do AutoMod."
            },

            {
                "name": "configmoderacao",
                "category": "Moderação",
                "description":
                    "Configura confirmações de moderação."
            },

            {
                "name": "ia",
                "category": "IA",
                "description":
                    "Conversa com a IA do Kibot."
            },
        ]
    }


# ============================================================
# BOT INVITE
# ============================================================

@app.get("/api/invite")
async def invite():

    if BOT_INVITE_URL:
        return RedirectResponse(
            BOT_INVITE_URL
        )

    return JSONResponse(
        {
            "error":
                "Configure BOT_INVITE_URL no .env"
        },
        status_code=503
    )
