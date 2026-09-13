# Kibot V44 Audit Report

- Base: KIBOT_V43_ASSETS_MINES
- Fix: Help Center / Todos
- Root project structure preserved.
- `cogs/help_center.py` compiled successfully.
- Todos uses at most 4 embed fields per rendered page and paginates with the existing navigation buttons.
- Field values are chunked below 900 characters.


## V47
- Corrigido `CommandLimitReached` causado por 98 comandos Slash globais + 10 comandos Slash administrativos duplicados.
- Os comandos administrativos de economia/progresso continuam disponíveis como comandos de prefixo (`K!setcrowings`, `K!retirarcrowings`, `K!setfichas`, `K!retirarfichas`, `K!setxp`, `K!retirarxp`, `K!setnivel`, `K!automodspam`, `K!automodstatus`, `K!automodtest`).
- Corrigida a whitelist de `set_guild_config` para aceitar `moderation_confirmations_enabled`.


## V49 — Anime GIFs
- Added centralized NekosBest anime/SFW GIF resolver with short cache and User-Agent.
- Fun/social actions, relationship proposals/divorce, ship, Arcade games, crime, badges and level-up use themed anime categories.
- Removed arbitrary GIF_URLS from the active media fallback so decorative GIFs remain anime-only.
