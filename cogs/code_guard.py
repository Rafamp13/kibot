"""Autodiagnóstico e assistência de código do Kibot.

O módulo monitora erros, identifica o arquivo/linha envolvidos, coleta um pequeno
contexto do código sem expor segredos e pede ao Gemini uma análise técnica.
O resultado é enviado por DM aos donos configurados.
"""
import ast
import asyncio
import hashlib
import logging
import os
import re
import traceback
from pathlib import Path

import discord
from discord.ext import commands

import config

logger = logging.getLogger("kibot.code_guard")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_SOURCE_LINES = 80

SECRET_PATTERNS = [
    re.compile(r"(?i)(DISCORD_TOKEN|GEMINI_API_KEY|GNEWS_API_KEY|FOOTBALL_DATA_API_KEY)\s*=\s*[^\n]+"),
    re.compile(r"(?i)(token|api[_-]?key|authorization|password|secret)\s*[:=]\s*['\"][^'\"]+['\"]"),
]

class CodeGuard(commands.Cog):
    """Guardião técnico: diagnóstico estático + análise assistida por Gemini."""
    def __init__(self, bot):
        self.bot = bot
        self._last_alert = {}
        self._lock = asyncio.Lock()
        self._startup_task = None

    async def cog_load(self):
        self._startup_task = asyncio.create_task(self._startup_scan())

    def cog_unload(self):
        if self._startup_task:
            self._startup_task.cancel()

    def _owners(self, guild=None):
        ids = set(getattr(config, "OWNER_IDS", []) or [])
        if guild and getattr(guild, "owner_id", None):
            ids.add(int(guild.owner_id))
        return ids

    def _redact(self, text):
        value = text or ""
        for pattern in SECRET_PATTERNS:
            value = pattern.sub(lambda m: m.group(1) + "=[REDACTED]", value)
        return value

    def _safe_source(self, filename, lineno=None):
        try:
            path = Path(filename).resolve()
            if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
                return ""
            if not path.exists() or path.suffix != ".py":
                return ""
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not lines:
                return ""
            center = max(1, int(lineno or 1))
            start = max(1, center - 18)
            end = min(len(lines), center + 25)
            out = []
            for number in range(start, end + 1):
                out.append(f"{number:4}: {self._redact(lines[number - 1])}")
            return "\n".join(out)[:12000]
        except Exception:
            return ""

    def _static_scan(self):
        problems = []
        for path in PROJECT_ROOT.rglob("*.py"):
            if any(part in {".git", "__pycache__", ".venv", "venv"} for part in path.parts):
                continue
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                compile(source, str(path), "exec")
                ast.parse(source, filename=str(path))
            except SyntaxError as exc:
                problems.append((str(path.relative_to(PROJECT_ROOT)), exc.lineno or 1, str(exc)))
            except Exception as exc:
                problems.append((str(path.relative_to(PROJECT_ROOT)), 1, f"{type(exc).__name__}: {exc}"))
        return problems

    async def _startup_scan(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(3)
        problems = await asyncio.to_thread(self._static_scan)
        if problems:
            text = "\n".join(f"• `{p}` linha {line}: {err}" for p, line, err in problems[:8])
            await self._notify_owners(
                "🚨 **Kibot — falha encontrada no código**\n\n"
                "A varredura estática encontrou problema(s) antes mesmo de considerar o comportamento do Discord:\n"
                + text
            , guild=None, fingerprint="startup:" + hashlib.sha1(text.encode()).hexdigest())

    async def _notify_owners(self, text, guild=None, fingerprint=None):
        if fingerprint:
            now = asyncio.get_running_loop().time()
            if now - self._last_alert.get(fingerprint, 0) < 600:
                return
            self._last_alert[fingerprint] = now
        for owner_id in self._owners(guild):
            try:
                user = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
                if not user:
                    continue
                payload = text[:1900]
                await user.send(payload)
            except (discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("Não consegui enviar diagnóstico por DM para %s: %r", owner_id, exc)
            except Exception:
                logger.exception("Falha ao enviar diagnóstico por DM")

    def _error_payload(self, error, command_name="desconhecido"):
        original = getattr(error, "original", error)
        tb = original.__traceback__
        frames = traceback.extract_tb(tb) if tb else []
        frame = None
        for candidate in reversed(frames):
            try:
                if PROJECT_ROOT in Path(candidate.filename).resolve().parents:
                    frame = candidate
                    break
            except Exception:
                continue
        if frame is None and frames:
            frame = frames[-1]
        filename = frame.filename if frame else "desconhecido"
        lineno = frame.lineno if frame else 0
        relative = str(Path(filename).resolve().relative_to(PROJECT_ROOT)) if frame and Path(filename).resolve().is_relative_to(PROJECT_ROOT) else filename
        source = self._safe_source(filename, lineno) if frame else ""
        tb_text = "".join(traceback.format_exception(type(original), original, original.__traceback__))
        tb_text = self._redact(tb_text)[-10000:]
        return original, relative, lineno, source, tb_text, command_name

    async def _ask_coder(self, original, relative, lineno, source, tb_text, command_name):
        ai = self.bot.get_cog("AIChat")
        client = getattr(ai, "_client", None) if ai else None
        model = getattr(ai, "model", "gemini-3.5-flash-lite") if ai else "gemini-3.5-flash-lite"
        fallbacks = getattr(ai, "_model_fallbacks", ["gemini-3.5-flash-lite", "gemini-3.6-flash"]) if ai else ["gemini-3.5-flash-lite", "gemini-3.6-flash"]
        if client is None:
            return "⚠️ Não consegui chamar o cérebro de código: GEMINI_API_KEY/cliente Gemini indisponível."
        try:
            from google.genai import types
            prompt = f"""Você é o engenheiro de software do Kibot. Faça um diagnóstico técnico objetivo.

ERRO:
{type(original).__name__}: {original}

COMANDO/EVENTO: {command_name}
ARQUIVO: {relative}
LINHA: {lineno}

TRACEBACK:
{tb_text}

CONTEXTO DO CÓDIGO (já sanitizado):
```python
{source}
```

Entregue em português:
1. Causa raiz provável.
2. Correção exata, incluindo código quando necessário.
3. Outros pontos do projeto que precisam ser ajustados para não repetir o erro.
4. Testes que devem ser executados.
Não invente APIs do Discord. Não peça nem revele tokens, senhas ou chaves. Se faltar contexto, diga exatamente o que falta.
"""
            cfg = types.GenerateContentConfig(
                system_instruction="Você é um especialista sênior em Python, discord.py 2.x, asyncio, SQLite e APIs REST. Priorize correções robustas e verificáveis.",
                temperature=0.2,
                max_output_tokens=900,
            )
            candidates = [model] + [m for m in fallbacks if m != model]
            last = None
            for candidate in candidates:
                try:
                    response = await asyncio.to_thread(client.models.generate_content, model=candidate, contents=prompt, config=cfg)
                    text = (getattr(response, "text", None) or "").strip()
                    if text:
                        return text[:6000]
                except Exception as exc:
                    last = exc
                    if not any(x in str(exc).lower() for x in ("404", "not found", "not_found", "no longer available")):
                        break
            return f"⚠️ A análise automática de código falhou: {type(last).__name__}: {last}" if last else "⚠️ A análise automática não retornou diagnóstico."
        except Exception as exc:
            return f"⚠️ Falha ao preparar o diagnóstico de código: {type(exc).__name__}: {exc}"

    async def diagnose_exception(self, error, guild=None, command_name="desconhecido"):
        original, relative, lineno, source, tb_text, command_name = self._error_payload(error, command_name)
        fingerprint = hashlib.sha1(f"{relative}:{lineno}:{type(original).__name__}:{original}".encode()).hexdigest()
        async with self._lock:
            now = asyncio.get_running_loop().time()
            if now - self._last_alert.get(fingerprint, 0) < 600:
                return
            self._last_alert[fingerprint] = now
        analysis = await self._ask_coder(original, relative, lineno, source, tb_text, command_name)
        msg = (
            "🛠️ **Kibot — diagnóstico automático de código**\n\n"
            f"**Local:** `{relative}:{lineno}`\n"
            f"**Erro:** `{type(original).__name__}: {str(original)[:500]}`\n\n"
            f"{analysis}\n\n"
            "_Diagnóstico gerado automaticamente; confirme a correção antes de alterar produção._"
        )
        await self._notify_owners(msg, guild=guild)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, (commands.CommandNotFound, commands.MissingPermissions, commands.BotMissingPermissions, commands.CheckFailure)):
            return
        await self.diagnose_exception(error, guild=getattr(ctx, "guild", None), command_name=getattr(getattr(ctx, "command", None), "qualified_name", "prefix"))

    @commands.Cog.listener()
    async def on_error(self, event_method, *args, **kwargs):
        exc = traceback.format_exc()
        if exc and exc.strip() != "NoneType: None\n":
            # on_error não fornece a exceção como objeto de forma confiável; registre para
            # não causar uma segunda falha. O tratamento principal fica em command errors.
            logger.error("Erro não tratado no evento %s: %s", event_method, exc)

    @commands.command(name="diagnostico", aliases=["diagnosticar", "codecheck"])
    @commands.is_owner()
    async def diagnostico(self, ctx):
        """Executa uma varredura estática do projeto e envia resultado por DM."""
        problems = await asyncio.to_thread(self._static_scan)
        if not problems:
            text = "🟢 **Varredura concluída:** não encontrei erros de sintaxe/compilação estática nos arquivos Python."
        else:
            text = "🔴 **Problemas encontrados:**\n" + "\n".join(f"• `{p}` linha {line}: {err}" for p, line, err in problems[:20])
        try:
            await ctx.author.send(text[:1900])
            await ctx.send("📬 Te mandei o diagnóstico por DM, chefe.")
        except discord.HTTPException:
            await ctx.send("⚠️ Não consegui abrir sua DM. Verifique se suas mensagens diretas estão habilitadas.")

async def setup(bot):
    await bot.add_cog(CodeGuard(bot))
