"""Dados recentes para o Kibot: futebol, clima e notícias."""
import asyncio
import json
import logging
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger("kibot.realtime")

WEATHER_CODES = {
    0: "céu limpo", 1: "principalmente limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina congelante", 51: "garoa leve", 53: "garoa moderada",
    55: "garoa intensa", 56: "garoa congelante leve", 57: "garoa congelante intensa",
    61: "chuva leve", 63: "chuva moderada", 65: "chuva forte", 66: "chuva congelante leve",
    67: "chuva congelante forte", 71: "neve leve", 73: "neve moderada", 75: "neve forte",
    77: "grãos de neve", 80: "pancadas leves", 81: "pancadas moderadas", 82: "pancadas fortes",
    85: "pancadas de neve leves", 86: "pancadas de neve fortes", 95: "trovoada",
    96: "trovoada com granizo leve", 99: "trovoada com granizo forte",
}

class RealtimeData(commands.Cog):
    """Integra APIs externas sem bloquear o loop do Discord."""
    def __init__(self, bot):
        self.bot = bot
        self.football_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
        self.news_key = os.getenv("GNEWS_API_KEY", "").strip()
        self.football_competitions = [x.strip().upper() for x in os.getenv(
            "FOOTBALL_COMPETITIONS", "PL,PD,SA,BL1,FL1,CL,BR1"
        ).split(",") if x.strip()]
        self.cache = {}
        self.cache_seconds = max(15, int(os.getenv("REALTIME_CACHE_SECONDS", "60")))

    async def _get_json(self, url, headers=None, timeout=12):
        def request():
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "Kibot/33"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        return await asyncio.to_thread(request)

    async def _cached(self, key, loader):
        now = asyncio.get_running_loop().time()
        cached = self.cache.get(key)
        if cached and now - cached[0] < self.cache_seconds:
            return cached[1]
        value = await loader()
        self.cache[key] = (now, value)
        return value

    async def weather(self, city):
        city = city.strip()
        if not city:
            raise ValueError("Informe uma cidade.")
        async def load():
            params = urllib.parse.urlencode({"name": city, "count": 1, "language": "pt", "format": "json"})
            geo = await self._get_json(f"https://geocoding-api.open-meteo.com/v1/search?{params}")
            places = geo.get("results") or []
            if not places:
                raise ValueError(f"Não achei a cidade **{city}**.")
            place = places[0]
            query = urllib.parse.urlencode({
                "latitude": place["latitude"], "longitude": place["longitude"],
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            })
            data = await self._get_json(f"https://api.open-meteo.com/v1/forecast?{query}")
            current = data.get("current", {})
            return {
                "city": place.get("name", city), "region": place.get("admin1", ""),
                "country": place.get("country", ""), "timezone": data.get("timezone", ""),
                "temperature": current.get("temperature_2m"),
                "feels_like": current.get("apparent_temperature"),
                "humidity": current.get("relative_humidity_2m"),
                "wind": current.get("wind_speed_10m"),
                "condition": WEATHER_CODES.get(current.get("weather_code"), "condição desconhecida"),
            }
        return await self._cached(("weather", city.lower()), load)

    async def football(self):
        if not self.football_key:
            raise RuntimeError("FOOTBALL_DATA_API_KEY não configurada")
        today = datetime.now(timezone.utc).date().isoformat()
        async def load():
            params = urllib.parse.urlencode({
                "dateFrom": today, "dateTo": today,
                "competitions": ",".join(self.football_competitions),
            })
            data = await self._get_json(
                f"https://api.football-data.org/v4/matches?{params}",
                headers={"X-Auth-Token": self.football_key, "User-Agent": "Kibot/33"},
            )
            matches = []
            for m in data.get("matches", [])[:20]:
                matches.append({
                    "id": m.get("id"), "competition": m.get("competition", {}).get("name", "Competição"),
                    "home": m.get("homeTeam", {}).get("name", "Casa"),
                    "away": m.get("awayTeam", {}).get("name", "Fora"),
                    "status": m.get("status", "UNKNOWN"), "utc": m.get("utcDate"),
                    "home_score": (m.get("score") or {}).get("fullTime", {}).get("home"),
                    "away_score": (m.get("score") or {}).get("fullTime", {}).get("away"),
                })
            return matches
        return await self._cached(("football", today), load)

    async def news(self, query=""):
        """Busca notícias reais. Usa GNews quando há chave e Google News RSS como fallback.

        O fallback evita que a IA fique sem fontes apenas porque o servidor ainda não
        configurou uma chave paga/externa. As matérias continuam vindo de veículos reais.
        """
        query = (query or "Brasil").strip()

        async def load_gnews():
            params = {"lang": "pt", "country": "br", "max": 5, "apikey": self.news_key}
            generic = query.casefold() in {"brasil", "geral", "últimas", "ultimas", "notícias", "noticias", ""}
            if not generic:
                params["q"] = query
                endpoint = "search"
            else:
                endpoint = "top-headlines"
            url = "https://gnews.io/api/v4/" + endpoint + "?" + urllib.parse.urlencode(params)
            data = await self._get_json(url, headers={"User-Agent": "Kibot/37 News/1.0"})
            return [{
                "title": a.get("title", "Sem título"),
                "description": a.get("description", ""),
                "url": a.get("url", ""),
                "source": (a.get("source") or {}).get("name", "Fonte desconhecida"),
                "published": a.get("publishedAt", ""),
                "provider": "GNews",
            } for a in (data.get("articles") or [])[:5] if a.get("url")]

        async def load_rss():
            params = {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}
            if query and query.casefold() not in {"brasil", "geral", "últimas", "ultimas", "notícias", "noticias"}:
                params["q"] = query
            url = "https://news.google.com/rss?" + urllib.parse.urlencode(params)
            raw = await asyncio.to_thread(lambda: urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Kibot/37 News/1.0"}), timeout=12).read())
            root = ET.fromstring(raw)
            articles = []
            for item in root.findall("./channel/item")[:8]:
                title = (item.findtext("title") or "Sem título").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                desc = (item.findtext("description") or "").strip()
                # Google News RSS normalmente traz "Veículo - manchete" no título.
                source = (item.findtext("source") or "Google News").strip()
                if " - " in title:
                    possible_title, possible_source = title.rsplit(" - ", 1)
                    if possible_source.strip():
                        title, source = possible_title.strip(), possible_source.strip()
                if link:
                    articles.append({"title": title, "description": desc, "url": link, "source": source, "published": pub, "provider": "Google News RSS"})
            return articles[:5]

        async def load():
            if self.news_key:
                try:
                    articles = await load_gnews()
                    if articles:
                        return articles
                    logger.warning("GNews respondeu sem artigos; usando Google News RSS.")
                except Exception as exc:
                    logger.warning("GNews falhou (%r); usando Google News RSS.", exc)
            return await load_rss()

        return await self._cached(("news", query.casefold()), load)

    async def _resolve_news_url(self, url):
        """Tenta trocar o link de redirecionamento do Google News pela URL final do veículo."""
        if not url or not url.startswith("http"):
            return url
        if "news.google.com/rss/articles/" not in url:
            return url
        try:
            def resolve():
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Kibot/37 News/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    return resp.geturl() or url
            final = await asyncio.to_thread(resolve)
            return final or url
        except Exception:
            return url

    async def news_sources_for_prompt(self, prompt):
        """Retorna fontes estruturadas para o rodapé da resposta da IA."""
        text = (prompt or "").casefold()
        news_words = ("notícia", "noticias", "notícias", "news", "manchete", "manchetes",
                      "últimas", "ultimas", "aconteceu hoje", "hoje no mundo")
        if not any(w in text for w in news_words):
            return []
        query = (prompt or "Brasil").strip()
        if len(query) > 120:
            query = "Brasil"
        try:
            articles = await self.news(query)
            result = []
            for article in articles[:5]:
                url = await self._resolve_news_url(article.get("url", ""))
                if url:
                    result.append((url, article.get("source", "Fonte desconhecida"), article.get("title", "Sem título")))
            return result
        except Exception as exc:
            logger.warning("Não consegui obter fontes para o rodapé de notícias: %r", exc)
            return []

    async def context_for_prompt(self, prompt):
        """Busca dados recentes e, para notícias, entrega um pacote fechado de fontes reais.

        O Gemini deve resumir somente o conteúdo recebido aqui; ele não é a fonte dos
        fatos atuais. As URLs são preservadas para que a resposta possa mostrar as fontes.
        """
        text = (prompt or "").lower()
        chunks = []
        weather_words = ("clima", "tempo", "temperatura", "vai chover", "chuva", "previsão", "previsao")
        football_words = ("futebol", "jogo", "jogos", "partida", "placar", "resultado", "campeonato", "brasileirão", "brasileirao")
        news_words = ("notícia", "noticias", "notícias", "ultimas notícias", "últimas notícias", "aconteceu hoje", "hoje no mundo", "manchetes", "notícia de hoje", "notícias de hoje", "news", "manchete", "manchetes", "últimas", "ultimas")
        if any(w in text for w in weather_words):
            city = "São Paulo"
            marker = text.find(" em ")
            if marker >= 0:
                raw = prompt[marker + 4:].strip(" ?!.,")
                if raw:
                    city = raw[:60]
            try:
                w = await self.weather(city)
                chunks.append(f"DADO RECENTE — CLIMA ({w['city']}): {w['condition']}; temperatura {w['temperature']}°C; sensação {w['feels_like']}°C; umidade {w['humidity']}%; vento {w['wind']} km/h. FONTE: Open-Meteo (https://open-meteo.com/)")
            except Exception as exc:
                logger.warning("Falha ao buscar clima: %r", exc)
        if any(w in text for w in football_words):
            try:
                matches = await self.football()
                if matches:
                    lines = []
                    for m in matches[:10]:
                        score = ""
                        if m["home_score"] is not None or m["away_score"] is not None:
                            score = f" — placar {m['home_score']}-{m['away_score']}"
                        lines.append(f"{m['competition']}: {m['home']} x {m['away']} ({m['status']}){score}")
                    chunks.append("DADOS RECENTES — FUTEBOL HOJE:\n" + "\n".join(lines) + "\nFONTE: football-data.org (https://www.football-data.org/)")
            except Exception as exc:
                logger.warning("Falha ao buscar futebol: %r", exc)
        if any(w in text for w in news_words):
            try:
                # Para notícias, nunca passe a pergunta inteira como se fosse conhecimento:
                # primeiro buscamos artigos reais e depois o modelo recebe somente esse pacote.
                query = prompt if len(prompt) < 120 and not any(x in text for x in weather_words + football_words) else "Brasil"
                articles = await self.news(query)
                if articles:
                    lines = []
                    for i, a in enumerate(articles, 1):
                        lines.append(
                            f"[FONTE {i}] TÍTULO: {a['title']} | VEÍCULO: {a['source']} | "
                            f"PUBLICADO: {a['published']} | RESUMO: {a['description']} | URL: {a['url']} | PROVEDOR: {a.get('provider', 'fonte externa')}"
                        )
                    chunks.append(
                        "PACOTE DE NOTÍCIAS VERIFICADAS — GNEWS\n"
                        + "\n".join(lines)
                        + "\nREGRA: só afirme fatos atuais que possam ser sustentados por estas fontes. "
                          "Se a fonte não responder à pergunta, diga que não há informação suficiente. "
                          "Não invente títulos, veículos, datas, números, pessoas, eventos ou URLs."
                    )
                else:
                    chunks.append("PACOTE DE NOTÍCIAS VERIFICADAS: nenhuma fonte encontrada. Não invente notícias.")
            except Exception as exc:
                logger.warning("Falha ao buscar notícias: %r", exc)
                chunks.append("PACOTE DE NOTÍCIAS VERIFICADAS: falha na consulta. Não invente notícias nem apresente fatos atuais como confirmados.")
        return "\n\n".join(chunks)

    @commands.command(name="clima", aliases=["tempo", "previsao"])
    @commands.guild_only()
    async def clima(self, ctx, *, cidade: str = "São Paulo"):
        try:
            w = await self.weather(cidade)
            await ctx.send(
                f"🌤️ **{w['city']}**{', ' + w['region'] if w['region'] else ''}\n"
                f"{w['condition'].capitalize()} • **{w['temperature']}°C** (sensação {w['feels_like']}°C)\n"
                f"💧 Umidade: {w['humidity']}% • 💨 Vento: {w['wind']} km/h"
            )
        except Exception as exc:
            await ctx.send(f"❌ Não consegui consultar o clima: {exc}")

    @app_commands.command(name="clima", description="Consulta o clima atual de uma cidade")
    @app_commands.describe(cidade="Cidade para consultar")
    async def clima_slash(self, interaction: discord.Interaction, cidade: str = "São Paulo"):
        await interaction.response.defer()
        try:
            w = await self.weather(cidade)
            await interaction.followup.send(f"🌤️ **{w['city']}** — {w['condition'].capitalize()} • **{w['temperature']}°C** • sensação **{w['feels_like']}°C** • umidade **{w['humidity']}%**")
        except Exception as exc:
            await interaction.followup.send(f"❌ Não consegui consultar o clima: {exc}")

    @commands.command(name="futebol", aliases=["partidas"])
    @commands.guild_only()
    async def futebol(self, ctx):
        try:
            matches = await self.football()
            if not matches:
                return await ctx.send("⚽ Hoje a bola tá de folga nas competições configuradas.")
            lines = []
            for m in matches[:12]:
                score = f"**{m['home_score']}-{m['away_score']}**" if m['home_score'] is not None else "vs"
                lines.append(f"• **{m['home']}** {score} **{m['away']}** — {m['competition']} (`{m['status']}`)")
            await ctx.send("⚽ **Futebol de hoje**\n" + "\n".join(lines))
        except Exception:
            await ctx.send("⚠️ Não consegui consultar os jogos agora. Verifique `FOOTBALL_DATA_API_KEY` no `.env`.")

    @app_commands.command(name="futebol", description="Consulta jogos de futebol de hoje")
    async def futebol_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            matches = await self.football()
            if not matches:
                return await interaction.followup.send("⚽ Hoje a bola tá de folga nas competições configuradas.")
            lines = [f"• **{m['home']}** {m['home_score'] if m['home_score'] is not None else 'vs'}-{m['away_score'] if m['away_score'] is not None else ''} **{m['away']}** — {m['competition']} (`{m['status']}`)" for m in matches[:12]]
            await interaction.followup.send("⚽ **Futebol de hoje**\n" + "\n".join(lines))
        except Exception:
            await interaction.followup.send("⚠️ Não consegui consultar os jogos. Configure `FOOTBALL_DATA_API_KEY`.")

    @commands.command(name="noticias", aliases=["noticia", "news"])
    @commands.guild_only()
    async def noticias(self, ctx, *, tema: str = ""):
        try:
            articles = await self.news(tema)
            if not articles:
                return await ctx.send("📰 Nenhuma notícia encontrada agora.")
            lines = [f"• **{a['title']}** — {a['source']}\n{a['url']}" for a in articles]
            await ctx.send("📰 **Notícias recentes**\n" + "\n".join(lines))
        except Exception:
            await ctx.send("⚠️ Não consegui consultar as notícias. Configure `GNEWS_API_KEY`.")

    @app_commands.command(name="noticias", description="Busca notícias recentes")
    @app_commands.describe(tema="Tema da notícia; deixe vazio para manchetes do Brasil")
    async def noticias_slash(self, interaction: discord.Interaction, tema: str = ""):
        await interaction.response.defer()
        try:
            articles = await self.news(tema)
            if not articles:
                return await interaction.followup.send("📰 Nenhuma notícia encontrada agora.")
            lines = [f"• **{a['title']}** — {a['source']}\n{a['url']}" for a in articles]
            await interaction.followup.send("📰 **Notícias recentes**\n" + "\n".join(lines))
        except Exception:
            await interaction.followup.send("⚠️ Não consegui consultar as notícias. Configure `GNEWS_API_KEY`.")

async def setup(bot):
    await bot.add_cog(RealtimeData(bot))
