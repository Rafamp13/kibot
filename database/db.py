"""Camada SQLite do Kibot."""
import time
import json
import asyncio
import aiosqlite
from config import DATABASE_PATH, STARTING_BALANCE

_connection: aiosqlite.Connection | None = None
_db_lock = asyncio.Lock()

async def get_connection():
    """Retorna a conexão SQLite ativa e a recria se ela tiver sido fechada.

    O Kibot mantém uma conexão compartilhada durante toda a vida do processo.
    Algumas rotinas antigas fechavam essa conexão global ao terminar uma operação,
    deixando todos os listeners seguintes com "ValueError: no active connection".
    """
    global _connection
    async with _db_lock:
        if _connection is not None:
            try:
                # Uma operação simples detecta conexões que foram fechadas.
                await _connection.execute("SELECT 1")
                return _connection
            except (ValueError, RuntimeError):
                try:
                    await _connection.close()
                except Exception:
                    pass
                _connection = None

        _connection = await aiosqlite.connect(DATABASE_PATH)
        _connection.row_factory = aiosqlite.Row
        return _connection

async def init_db():
    conn = await get_connection()

    # Migração robusta da tabela users. Versões antigas do Kibot chegaram a usar
    # uma chave primária somente em user_id; nesse caso INSERT OR IGNORE podia
    # ignorar um usuário em um segundo servidor e get_user() retornava None.
    cur = await conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    users_exists = await cur.fetchone() is not None
    if not users_exists:
        await conn.execute("""
            CREATE TABLE users (
                user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0, bank INTEGER NOT NULL DEFAULT 0, dirty_money INTEGER NOT NULL DEFAULT 0,
                corvo_chips INTEGER NOT NULL DEFAULT 0, last_daily INTEGER NOT NULL DEFAULT 0,
                last_work INTEGER NOT NULL DEFAULT 0, xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1, selected_job TEXT NOT NULL DEFAULT 'entregador',
                crime_rep INTEGER NOT NULL DEFAULT 0, last_rob INTEGER NOT NULL DEFAULT 0,
                last_crime INTEGER NOT NULL DEFAULT 0, last_bico_accept INTEGER NOT NULL DEFAULT 0,
                active_bico TEXT, active_bico_payout INTEGER NOT NULL DEFAULT 0,
                bico_ends_at INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, guild_id)
            )
        """)
    else:
        cur = await conn.execute("PRAGMA table_info(users)")
        info = await cur.fetchall()
        cols = {row["name"] for row in info}
        pk_cols = [row["name"] for row in sorted(info, key=lambda r: r["pk"]) if row["pk"]]
        required = {"user_id", "guild_id", "balance", "bank", "dirty_money", "corvo_chips", "last_daily", "last_work", "xp", "level", "selected_job", "crime_rep", "last_rob", "last_crime", "last_bico_accept", "active_bico", "active_bico_payout", "bico_ends_at"}
        if pk_cols != ["user_id", "guild_id"] or not required.issubset(cols):
            await conn.execute("ALTER TABLE users RENAME TO users_legacy")
            await conn.execute("""
                CREATE TABLE users (
                    user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
                    balance INTEGER NOT NULL DEFAULT 0, bank INTEGER NOT NULL DEFAULT 0, dirty_money INTEGER NOT NULL DEFAULT 0,
                    corvo_chips INTEGER NOT NULL DEFAULT 0, last_daily INTEGER NOT NULL DEFAULT 0,
                    last_work INTEGER NOT NULL DEFAULT 0, xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1, selected_job TEXT NOT NULL DEFAULT 'entregador',
                    crime_rep INTEGER NOT NULL DEFAULT 0, last_rob INTEGER NOT NULL DEFAULT 0,
                    last_crime INTEGER NOT NULL DEFAULT 0, last_bico_accept INTEGER NOT NULL DEFAULT 0,
                    active_bico TEXT, active_bico_payout INTEGER NOT NULL DEFAULT 0,
                    bico_ends_at INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            legacy_cols = {row["name"] for row in info}
            defaults = {
                "balance": "0", "bank": "0", "dirty_money": "0", "corvo_chips": "0", "last_daily": "0",
                "last_work": "0", "xp": "0", "level": "1", "selected_job": "'entregador'",
                "crime_rep": "0", "last_rob": "0", "last_crime": "0", "last_bico_accept": "0",
                "active_bico": "NULL", "active_bico_payout": "0", "bico_ends_at": "0"
            }
            expr = []
            for col in ["user_id", "guild_id", "balance", "bank", "dirty_money", "corvo_chips", "last_daily", "last_work", "xp", "level", "selected_job", "crime_rep", "last_rob", "last_crime", "last_bico_accept", "active_bico", "active_bico_payout", "bico_ends_at"]:
                if col in legacy_cols:
                    expr.append(col)
                elif col == "guild_id":
                    expr.append("0")
                elif col == "user_id":
                    raise RuntimeError("A tabela users existente não possui user_id; não é possível migrar com segurança.")
                else:
                    expr.append(defaults[col])
            # Evita perder dados quando a tabela antiga não tinha guild_id:
            # nesse caso 0 identifica os registros antigos; novos servidores
            # receberão sua própria linha normalmente.
            await conn.execute(
                "INSERT OR IGNORE INTO users (user_id,guild_id,balance,bank,dirty_money,corvo_chips,last_daily,last_work,xp,level,selected_job,crime_rep,last_rob,last_crime,last_bico_accept,active_bico,active_bico_payout,bico_ends_at) SELECT " + ",".join(expr) + " FROM users_legacy"
            )
            await conn.execute("DROP TABLE users_legacy")


    # Estado temporário do suborno para o sistema criminal expandido.
    # As colunas são adicionadas sem quebrar bancos existentes.
    user_cols_cur = await conn.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in await user_cols_cur.fetchall()}
    for col, definition in (("dirty_money", "INTEGER NOT NULL DEFAULT 0"), ("crime_boost_until", "INTEGER NOT NULL DEFAULT 0"), ("crime_boost_amount", "INTEGER NOT NULL DEFAULT 0")):
        if col not in user_cols:
            await conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

    # Tabelas legadas usadas pelos módulos econômicos, XP, moderação, tags e AFK.
    # Elas são criadas aqui para que uma instalação nova do Kibot não quebre
    # antes de qualquer comando ser usado.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER, mute_role_id INTEGER, welcome_channel_id INTEGER,
            welcome_message TEXT DEFAULT 'Bem-vindo(a), {membro}! 🎉', welcome_style TEXT NOT NULL DEFAULT 'kiba', auto_ban_bets_channel_id INTEGER, auto_ban_bets_enabled INTEGER NOT NULL DEFAULT 0, xp_enabled INTEGER NOT NULL DEFAULT 1, moderation_confirmations_enabled INTEGER NOT NULL DEFAULT 1
        )
    """)
    # Compatibilidade com bancos que já possuíam guild_config antes desta revisão.
    guild_cols_cur = await conn.execute("PRAGMA table_info(guild_config)")
    guild_cols = {row[1] for row in await guild_cols_cur.fetchall()}
    for col, definition in (("log_channel_id", "INTEGER"), ("mute_role_id", "INTEGER"), ("welcome_channel_id", "INTEGER"), ("welcome_message", "TEXT DEFAULT 'Bem-vindo(a), {membro}! 🎉'"), ("welcome_style", "TEXT NOT NULL DEFAULT 'kiba'"), ("auto_ban_bets_channel_id", "INTEGER"), ("auto_ban_bets_enabled", "INTEGER NOT NULL DEFAULT 0"), ("xp_enabled", "INTEGER NOT NULL DEFAULT 1"), ("moderation_confirmations_enabled", "INTEGER NOT NULL DEFAULT 1")):
        if col not in guild_cols:
            await conn.execute(f"ALTER TABLE guild_config ADD COLUMN {col} {definition}")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS relationships (guild_id INTEGER NOT NULL, user1_id INTEGER NOT NULL, user2_id INTEGER NOT NULL, relation_type TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY (guild_id,user1_id,user2_id))
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS routine_daily (user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, day TEXT NOT NULL, action TEXT NOT NULL, completed_at INTEGER NOT NULL, PRIMARY KEY (user_id,guild_id,day,action))
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL, reason TEXT NOT NULL, created_at INTEGER NOT NULL
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_stats (
            user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, activity TEXT NOT NULL, value INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, guild_id, activity)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS earned_badges (
            user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, badge_key TEXT NOT NULL, earned_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, guild_id, badge_key)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS xp_level_roles (
            guild_id INTEGER NOT NULL, level INTEGER NOT NULL, role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, level)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
            name TEXT NOT NULL, company_type TEXT NOT NULL, invested INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL DEFAULT 0, last_collect INTEGER NOT NULL DEFAULT 0,
            total_gross INTEGER NOT NULL DEFAULT 0, total_tax INTEGER NOT NULL DEFAULT 0, total_net INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, guild_id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', price INTEGER NOT NULL, role_id INTEGER, emoji TEXT NOT NULL DEFAULT '🛍️',
            UNIQUE(guild_id, name)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, item_id INTEGER NOT NULL, purchased_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, guild_id, item_id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS corvo_shop_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', price INTEGER NOT NULL, emoji TEXT NOT NULL DEFAULT '🪶',
            UNIQUE(guild_id, name)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS corvo_inventory (
            user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, item_id INTEGER NOT NULL, purchased_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, guild_id, item_id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS afk (
            user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, original_nick TEXT, reason TEXT, since INTEGER NOT NULL,
            PRIMARY KEY (user_id, guild_id)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            guild_id INTEGER NOT NULL, name TEXT NOT NULL, response TEXT NOT NULL, created_at INTEGER NOT NULL,
            PRIMARY KEY (guild_id, name)
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS automod_spam_exempt_channels (
            guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, PRIMARY KEY (guild_id, channel_id)
        )
    """)
    # Tickets: configuração persistente + histórico de atendimento.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ticket_config (
            guild_id INTEGER PRIMARY KEY, category_id INTEGER, panel_channel_id INTEGER,
            log_channel_id INTEGER, staff_role_id INTEGER, evaluation_channel_id INTEGER, report_log_channel_id INTEGER
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL, ticket_type TEXT NOT NULL, reason TEXT NOT NULL DEFAULT 'Não informado', status TEXT NOT NULL DEFAULT 'open',
            claimed_by INTEGER, created_at INTEGER NOT NULL, closed_at INTEGER, closed_by INTEGER, close_reason TEXT
        )
    """)
    # Migração de tickets: versões anteriores não armazenavam o motivo da abertura.
    cur = await conn.execute("PRAGMA table_info(tickets)")
    ticket_cols = {row["name"] for row in await cur.fetchall()}
    if "reason" not in ticket_cols:
        await conn.execute("ALTER TABLE tickets ADD COLUMN reason TEXT NOT NULL DEFAULT 'Não informado'")

    # Migração da configuração de tickets: versões anteriores não tinham
    # canal separado para avaliações.
    cur = await conn.execute("PRAGMA table_info(ticket_config)")
    ticket_config_cols = {row["name"] for row in await cur.fetchall()}
    if "evaluation_channel_id" not in ticket_config_cols:
        await conn.execute("ALTER TABLE ticket_config ADD COLUMN evaluation_channel_id INTEGER")
    if "report_log_channel_id" not in ticket_config_cols:
        await conn.execute("ALTER TABLE ticket_config ADD COLUMN report_log_channel_id INTEGER")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ticket_evaluations (
            ticket_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            claimed_by INTEGER, dm_message_id INTEGER, stars INTEGER, description TEXT,
            status TEXT NOT NULL DEFAULT 'pending', created_at INTEGER NOT NULL, answered_at INTEGER
        )
    """)

    # Formulários: esquema persistente e compatível com versões anteriores.
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS form_config (
            guild_id INTEGER PRIMARY KEY,
            panel_channel_id INTEGER,
            review_channel_id INTEGER
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            questions TEXT NOT NULL DEFAULT '[]',
            active INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS form_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            answers TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            reviewer_id INTEGER,
            reviewed_at INTEGER,
            created_at INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tempvoice_config (
            guild_id INTEGER PRIMARY KEY,
            category_id INTEGER,
            lobby_channel_id INTEGER,
            panel_channel_id INTEGER
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS tempvoice_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            text_channel_id INTEGER,
            created_at INTEGER NOT NULL DEFAULT 0
        )
    """)
    cols = await conn.execute("PRAGMA table_info(tempvoice_channels)")
    col_names = [row[1] for row in await cols.fetchall()]
    if "text_channel_id" not in col_names:
        await conn.execute("ALTER TABLE tempvoice_channels ADD COLUMN text_channel_id INTEGER")

    await conn.commit()

async def _ensure_user(user_id, guild_id):
    conn = await get_connection()
    async with conn.execute("SELECT 1 FROM users WHERE user_id=? AND guild_id=?", (int(user_id), int(guild_id))) as cur:
        if await cur.fetchone() is not None:
            return
    await conn.execute(
        """INSERT INTO users
           (user_id,guild_id,balance,bank,corvo_chips,last_daily,last_work,xp,level,selected_job,crime_rep,last_rob,last_crime,last_bico_accept,active_bico,active_bico_payout,bico_ends_at)
           VALUES (?,?,?,0,0,0,0,0,1,'entregador',0,0,0,0,NULL,0,0)
           ON CONFLICT(user_id,guild_id) DO NOTHING""",
        (int(user_id), int(guild_id), STARTING_BALANCE))
    await conn.commit()


async def set_automod_spam_exempt(guild_id, channel_id, exempt=True):
    conn = await get_connection()
    if exempt:
        await conn.execute("INSERT OR IGNORE INTO automod_spam_exempt_channels (guild_id, channel_id) VALUES (?, ?)", (guild_id, channel_id))
    else:
        await conn.execute("DELETE FROM automod_spam_exempt_channels WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
    await conn.commit()

async def is_automod_spam_exempt(guild_id, channel_id):
    conn = await get_connection()
    async with conn.execute("SELECT 1 FROM automod_spam_exempt_channels WHERE guild_id=? AND channel_id=?", (guild_id, channel_id)) as c:
        return await c.fetchone() is not None

async def get_automod_spam_exempt_channels(guild_id):
    conn = await get_connection()
    async with conn.execute("SELECT channel_id FROM automod_spam_exempt_channels WHERE guild_id=? ORDER BY channel_id", (guild_id,)) as c:
        return [int(row["channel_id"]) for row in await c.fetchall()]

async def get_user(user_id, guild_id):
    user_id, guild_id = int(user_id), int(guild_id)
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    async with conn.execute("SELECT * FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id)) as c:
        row = await c.fetchone()
    if row is not None:
        return row
    # Última defesa: se a instalação tiver um banco extremamente antigo,
    # cria a linha explicitamente e nunca deixa saldo/perfil receber None.
    await conn.execute(
        "INSERT OR IGNORE INTO users (user_id,guild_id,balance,bank,dirty_money,corvo_chips,last_daily,last_work,xp,level,selected_job,crime_rep,last_rob,last_crime,last_bico_accept,active_bico,active_bico_payout,bico_ends_at) VALUES (?,?,?,0,0,0,0,0,1,'entregador',0,0,0,0,NULL,0,0)",
        (user_id, guild_id, STARTING_BALANCE))
    await conn.commit()
    async with conn.execute("SELECT * FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id)) as c:
        return await c.fetchone()

async def add_dirty_money(user_id, guild_id, amount):
    """Adiciona Dinheiro Sujo virtual ao usuário."""
    amount = max(0, int(amount))
    if amount <= 0: return 0
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    await conn.execute("UPDATE users SET dirty_money=dirty_money+? WHERE user_id=? AND guild_id=?", (amount, user_id, guild_id))
    await conn.commit()
    async with conn.execute("SELECT dirty_money FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id)) as c:
        row = await c.fetchone()
    return int(row["dirty_money"])

async def spend_dirty_money(user_id, guild_id, amount):
    """Debita Dinheiro Sujo de forma atômica."""
    amount = int(amount)
    if amount <= 0: return False
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    cur = await conn.execute("UPDATE users SET dirty_money=dirty_money-? WHERE user_id=? AND guild_id=? AND dirty_money>=?", (amount, user_id, guild_id, amount))
    await conn.commit()
    return cur.rowcount > 0

async def launder_dirty_money(user_id, guild_id, amount, fee):
    """Converte Dinheiro Sujo em CRW atomicamente, cobrando uma taxa fixa."""
    amount, fee = int(amount), int(fee)
    if amount <= fee or fee < 0: return False, 0
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    clean = amount - fee
    cur = await conn.execute("UPDATE users SET dirty_money=dirty_money-?, balance=balance+? WHERE user_id=? AND guild_id=? AND dirty_money>=?", (amount, clean, user_id, guild_id, amount))
    await conn.commit()
    return cur.rowcount > 0, clean

async def spend_bank(user_id,guild_id,amount):
    """Debita CRW exclusivamente do Banco de forma atômica."""
    if amount <= 0: return False
    # A operação SQL já é atômica por si só (o saldo é condicionado no UPDATE).
    # Não envolva get_connection() em _db_lock: get_connection() usa o mesmo
    # lock para recuperar/recriar a conexão e isso causaria deadlock.
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    cur=await conn.execute("UPDATE users SET bank=bank-? WHERE user_id=? AND guild_id=? AND bank>=?", (amount,user_id,guild_id,amount))
    await conn.commit()
    return cur.rowcount > 0

async def spend_balance(user_id,guild_id,amount):
    """Debita Crowins de forma atômica, evitando saldo negativo em apostas simultâneas."""
    if amount <= 0:
        return False
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    cur=await conn.execute(
        "UPDATE users SET balance=balance-? WHERE user_id=? AND guild_id=? AND balance>=?",
        (amount,user_id,guild_id,amount))
    await conn.commit()
    return cur.rowcount > 0

async def transfer_balance(from_user_id, to_user_id, guild_id, amount):
    """Transfere CRW entre carteiras de forma atômica."""
    amount = int(amount)
    if amount <= 0 or int(from_user_id) == int(to_user_id):
        return False
    await _ensure_user(from_user_id, guild_id)
    await _ensure_user(to_user_id, guild_id)
    conn = await get_connection()
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cur = await conn.execute(
                "UPDATE users SET balance=balance-? WHERE user_id=? AND guild_id=? AND balance>=?",
                (amount, from_user_id, guild_id, amount),
            )
            if cur.rowcount != 1:
                await conn.rollback()
                return False
            await conn.execute(
                "UPDATE users SET balance=balance+? WHERE user_id=? AND guild_id=?",
                (amount, to_user_id, guild_id),
            )
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

async def move_balance_to_bank(user_id, guild_id, amount):
    """Move CRW da carteira para o Banco sem permitir saldo negativo."""
    amount = int(amount)
    if amount <= 0:
        return False
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cur = await conn.execute(
                "UPDATE users SET balance=balance-?, bank=bank+? WHERE user_id=? AND guild_id=? AND balance>=?",
                (amount, amount, user_id, guild_id, amount),
            )
            if cur.rowcount != 1:
                await conn.rollback()
                return False
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

async def move_bank_to_balance(user_id, guild_id, amount):
    """Move CRW do Banco para a carteira sem permitir Banco negativo."""
    amount = int(amount)
    if amount <= 0:
        return False
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cur = await conn.execute(
                "UPDATE users SET bank=bank-?, balance=balance+? WHERE user_id=? AND guild_id=? AND bank>=?",
                (amount, amount, user_id, guild_id, amount),
            )
            if cur.rowcount != 1:
                await conn.rollback()
                return False
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

async def update_balance(user_id,guild_id,amount):
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET balance=balance+? WHERE user_id=? AND guild_id=?", (amount,user_id,guild_id))
    await conn.commit()

async def update_bank(user_id,guild_id,amount):
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET bank=bank+? WHERE user_id=? AND guild_id=?", (amount,user_id,guild_id))
    await conn.commit()

async def add_corvo_chips(user_id,guild_id,amount):
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET corvo_chips=corvo_chips+? WHERE user_id=? AND guild_id=?", (amount,user_id,guild_id))
    await conn.commit()

async def spend_corvo_chips(user_id,guild_id,amount):
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    cur=await conn.execute("UPDATE users SET corvo_chips=corvo_chips-? WHERE user_id=? AND guild_id=? AND corvo_chips>=?", (amount,user_id,guild_id,amount))
    await conn.commit()
    return cur.rowcount > 0

async def claim_daily(user_id, guild_id, amount, cooldown, timestamp=None):
    """Tenta conceder o daily uma única vez, de forma atômica."""
    amount=max(0,int(amount)); cooldown=max(0,int(cooldown)); now=int(timestamp or time.time())
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    async with conn.execute("SELECT last_daily FROM users WHERE user_id=? AND guild_id=?",(user_id,guild_id)) as c:
        row=await c.fetchone()
    last=int(row["last_daily"] or 0) if row else 0
    elapsed=max(0,now-last)
    if elapsed<cooldown:
        return False, cooldown-elapsed
    # A condição last_daily=? torna a concessão concorrente segura: apenas uma
    # chamada consegue atualizar a mesma versão do timestamp.
    cur=await conn.execute("UPDATE users SET balance=balance+?, last_daily=? WHERE user_id=? AND guild_id=? AND last_daily=?",(amount,now,user_id,guild_id,last))
    await conn.commit()
    if cur.rowcount!=1:
        return False, cooldown
    return True, 0

async def set_last_daily(user_id,guild_id,timestamp=None):
    await _ensure_user(user_id,guild_id); timestamp=timestamp or int(time.time())
    conn=await get_connection(); await conn.execute("UPDATE users SET last_daily=? WHERE user_id=? AND guild_id=?", (timestamp,user_id,guild_id)); await conn.commit()

async def set_last_work(user_id,guild_id,timestamp=None):
    await _ensure_user(user_id,guild_id); timestamp=timestamp or int(time.time())
    conn=await get_connection(); await conn.execute("UPDATE users SET last_work=? WHERE user_id=? AND guild_id=?", (timestamp,user_id,guild_id)); await conn.commit()

async def set_selected_job(user_id, guild_id, job_id):
    await _ensure_user(user_id, guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET selected_job=? WHERE user_id=? AND guild_id=?", (job_id,user_id,guild_id))
    await conn.commit()

async def add_crime_rep(user_id, guild_id, amount):
    await _ensure_user(user_id, guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET crime_rep=crime_rep+? WHERE user_id=? AND guild_id=?", (amount,user_id,guild_id))
    await conn.commit()

async def set_last_rob(user_id, guild_id, timestamp=None):
    await _ensure_user(user_id, guild_id); timestamp=timestamp or int(time.time())
    conn=await get_connection(); await conn.execute("UPDATE users SET last_rob=? WHERE user_id=? AND guild_id=?", (timestamp,user_id,guild_id)); await conn.commit()

async def set_last_crime(user_id, guild_id, timestamp=None):
    await _ensure_user(user_id, guild_id); timestamp=timestamp or int(time.time())
    conn=await get_connection(); await conn.execute("UPDATE users SET last_crime=? WHERE user_id=? AND guild_id=?", (timestamp,user_id,guild_id)); await conn.commit()


async def set_crime_boost(user_id, guild_id, amount, until):
    await _ensure_user(user_id, guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET crime_boost_amount=?, crime_boost_until=? WHERE user_id=? AND guild_id=?", (amount, until, user_id, guild_id))
    await conn.commit()

async def clear_crime_boost(user_id, guild_id):
    await _ensure_user(user_id, guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET crime_boost_amount=0, crime_boost_until=0 WHERE user_id=? AND guild_id=?", (user_id, guild_id))
    await conn.commit()

async def steal_half_wallet(thief_id, target_id, guild_id):
    """Tira exatamente 50% da carteira do alvo e passa para o ladrão de forma atômica."""
    if thief_id == target_id:
        return 0
    await _ensure_user(thief_id, guild_id)
    await _ensure_user(target_id, guild_id)
    conn = await get_connection()
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute(
                "SELECT balance FROM users WHERE user_id=? AND guild_id=?",
                (target_id, guild_id),
            ) as c:
                row = await c.fetchone()
            amount = (row[0] // 2) if row else 0
            if amount <= 0:
                await conn.rollback()
                return 0
            cur = await conn.execute(
                "UPDATE users SET balance=balance-? WHERE user_id=? AND guild_id=? AND balance>=?",
                (amount, target_id, guild_id, amount),
            )
            if cur.rowcount != 1:
                await conn.rollback()
                return 0
            await conn.execute(
                "UPDATE users SET balance=balance+? WHERE user_id=? AND guild_id=?",
                (amount, thief_id, guild_id),
            )
            await conn.commit()
            return amount
        except Exception:
            await conn.rollback()
            raise

async def start_bico(user_id,guild_id,name,payout,ends_at):
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    now=int(time.time())
    cur=await conn.execute("UPDATE users SET active_bico=?,active_bico_payout=?,bico_ends_at=?,last_bico_accept=? WHERE user_id=? AND guild_id=? AND active_bico IS NULL AND last_bico_accept<=?", (name,payout,ends_at,now,user_id,guild_id,now-3600))
    await conn.commit()
    return cur.rowcount == 1

async def claim_bico_completion(user_id,guild_id):
    """Finaliza um bico pronto e credita o pagamento numa única operação."""
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    now=int(time.time())
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute("SELECT active_bico,active_bico_payout,bico_ends_at FROM users WHERE user_id=? AND guild_id=?", (user_id,guild_id)) as c:
                row=await c.fetchone()
            if not row or not row[0] or now < row[2]:
                await conn.rollback()
                return None
            name,payout=row[0],row[1]
            cur=await conn.execute("UPDATE users SET active_bico=NULL,active_bico_payout=0,bico_ends_at=0,balance=balance+? WHERE user_id=? AND guild_id=? AND active_bico=?", (payout,user_id,guild_id,name))
            if cur.rowcount != 1:
                await conn.rollback()
                return None
            await conn.commit()
            return name,payout
        except Exception:
            await conn.rollback()
            raise

async def get_company(user_id, guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM companies WHERE user_id=? AND guild_id=?", (user_id,guild_id)) as c:
        return await c.fetchone()

async def create_company(user_id, guild_id, name, company_type, cost):
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    now=int(time.time())
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute("SELECT bank FROM users WHERE user_id=? AND guild_id=?", (user_id,guild_id)) as c:
                row=await c.fetchone()
            if not row or row[0] < cost:
                await conn.rollback(); return False
            cur=await conn.execute("UPDATE users SET bank=bank-? WHERE user_id=? AND guild_id=? AND bank>=?", (cost,user_id,guild_id,cost))
            if cur.rowcount != 1:
                await conn.rollback(); return False
            try:
                await conn.execute("INSERT INTO companies(user_id,guild_id,name,company_type,invested,created_at) VALUES(?,?,?,?,?,?)", (user_id,guild_id,name,company_type,cost,now))
            except Exception:
                await conn.rollback(); return False
            await conn.commit(); return True
        except Exception:
            await conn.rollback(); raise

async def collect_company(user_id, guild_id, gross, tax):
    conn=await get_connection(); now=int(time.time()); net=max(0,gross-tax)
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute("SELECT id,last_collect FROM companies WHERE user_id=? AND guild_id=?", (user_id,guild_id)) as c:
                row=await c.fetchone()
            if not row:
                await conn.rollback(); return False
            cur=await conn.execute("UPDATE companies SET last_collect=?,total_gross=total_gross+?,total_tax=total_tax+?,total_net=total_net+? WHERE id=?", (now,gross,tax,net,row[0]))
            if cur.rowcount != 1:
                await conn.rollback(); return False
            await conn.execute("UPDATE users SET bank=bank+? WHERE user_id=? AND guild_id=?", (net,user_id,guild_id))
            await conn.commit(); return True
        except Exception:
            await conn.rollback(); raise

async def delete_company(user_id, guild_id):
    conn=await get_connection()
    cur=await conn.execute("DELETE FROM companies WHERE user_id=? AND guild_id=?", (user_id,guild_id))
    await conn.commit(); return cur.rowcount == 1

async def get_leaderboard(guild_id,limit=10):
    conn=await get_connection()
    async with conn.execute("SELECT user_id,(balance+bank) total FROM users WHERE guild_id=? ORDER BY total DESC LIMIT ?",(guild_id,limit)) as c:return await c.fetchall()

async def get_corvo_leaderboard(guild_id,limit=10):
    conn=await get_connection()
    async with conn.execute("SELECT user_id,corvo_chips FROM users WHERE guild_id=? ORDER BY corvo_chips DESC LIMIT ?",(guild_id,limit)) as c:return await c.fetchall()

async def add_xp(user_id,guild_id,amount):
    await _ensure_user(user_id,guild_id)
    row=await get_user(user_id,guild_id)
    old_level=row["level"]; new_xp=row["xp"]+amount; new_level=old_level
    while new_xp >= 100 * new_level:
        new_xp -= 100 * new_level; new_level += 1
    conn=await get_connection(); await conn.execute("UPDATE users SET xp=?, level=? WHERE user_id=? AND guild_id=?", (new_xp,new_level,user_id,guild_id)); await conn.commit()
    return new_level, old_level, new_xp

async def set_balance(user_id, guild_id, amount):
    amount = max(0, int(amount))
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    await conn.execute("UPDATE users SET balance=? WHERE user_id=? AND guild_id=?", (amount, user_id, guild_id))
    await conn.commit()

async def set_corvo_chips(user_id, guild_id, amount):
    amount = max(0, int(amount))
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    await conn.execute("UPDATE users SET corvo_chips=? WHERE user_id=? AND guild_id=?", (amount, user_id, guild_id))
    await conn.commit()

async def spend_xp(user_id, guild_id, amount):
    """Debita XP total de forma atômica, mantendo nível + XP restante consistentes."""
    amount = int(amount)
    if amount <= 0:
        return False
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute("SELECT xp, level FROM users WHERE user_id=? AND guild_id=?", (user_id, guild_id)) as cur:
                row = await cur.fetchone()
            if not row:
                await conn.rollback()
                return False
            level = max(1, int(row["level"]))
            total = sum(100 * i for i in range(1, level)) + int(row["xp"])
            if total < amount:
                await conn.rollback()
                return False
            remaining = total - amount
            new_level = 1
            while remaining >= 100 * new_level:
                remaining -= 100 * new_level
                new_level += 1
            await conn.execute("UPDATE users SET xp=?, level=? WHERE user_id=? AND guild_id=?", (remaining, new_level, user_id, guild_id))
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

async def set_xp(user_id, guild_id, total_xp):
    """Define XP total e converte automaticamente para nível + XP restante."""
    total_xp = max(0, int(total_xp))
    level = 1
    remaining = total_xp
    while remaining >= 100 * level:
        remaining -= 100 * level
        level += 1
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    await conn.execute("UPDATE users SET xp=?, level=? WHERE user_id=? AND guild_id=?", (remaining, level, user_id, guild_id))
    await conn.commit()
    return level, remaining

async def set_bank(user_id, guild_id, amount):
    amount=max(0,int(amount))
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET bank=? WHERE user_id=? AND guild_id=?",(amount,user_id,guild_id))
    await conn.commit()
    return amount

async def remove_bank(user_id, guild_id, amount):
    amount=max(0,int(amount))
    await _ensure_user(user_id,guild_id)
    conn=await get_connection()
    await conn.execute("UPDATE users SET bank=MAX(0,bank-?) WHERE user_id=? AND guild_id=?",(amount,user_id,guild_id))
    await conn.commit()
    async with conn.execute("SELECT bank FROM users WHERE user_id=? AND guild_id=?",(user_id,guild_id)) as c:
        row=await c.fetchone()
    return int(row["bank"] if row else 0)

async def remove_balance(user_id, guild_id, amount):
    amount = max(0, int(amount))
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    await conn.execute("UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=? AND guild_id=?", (amount, user_id, guild_id))
    await conn.commit()
    row = await get_user(user_id, guild_id)
    return row["balance"]

async def remove_corvo_chips(user_id, guild_id, amount):
    amount = max(0, int(amount))
    await _ensure_user(user_id, guild_id)
    conn = await get_connection()
    await conn.execute("UPDATE users SET corvo_chips=MAX(0,corvo_chips-?) WHERE user_id=? AND guild_id=?", (amount, user_id, guild_id))
    await conn.commit()
    row = await get_user(user_id, guild_id)
    return row["corvo_chips"]

async def get_total_xp(user_id, guild_id):
    row = await get_user(user_id, guild_id)
    level = max(1, int(row["level"]))
    return sum(100 * i for i in range(1, level)) + int(row["xp"])

async def remove_xp(user_id, guild_id, amount):
    total = await get_total_xp(user_id, guild_id)
    new_total = max(0, total - max(0, int(amount)))
    return await set_xp(user_id, guild_id, new_total)

async def set_level(user_id, guild_id, level):
    level = max(1, int(level))
    total_xp = sum(100 * i for i in range(1, level))
    return await set_xp(user_id, guild_id, total_xp)

async def get_xp_level_roles(guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT guild_id,level,role_id FROM xp_level_roles WHERE guild_id=? ORDER BY level ASC",(guild_id,)) as c:
        return await c.fetchall()

async def get_xp_level_role(guild_id, level):
    conn=await get_connection()
    async with conn.execute("SELECT guild_id,level,role_id FROM xp_level_roles WHERE guild_id=? AND level=?",(guild_id,level)) as c:
        return await c.fetchone()

async def set_xp_level_role(guild_id, level, role_id):
    conn=await get_connection()
    await conn.execute("DELETE FROM xp_level_roles WHERE guild_id=? AND role_id=?",(guild_id,role_id))
    await conn.execute("INSERT INTO xp_level_roles(guild_id,level,role_id) VALUES(?,?,?) ON CONFLICT(guild_id,level) DO UPDATE SET role_id=excluded.role_id",(guild_id,level,role_id))
    await conn.commit()

async def remove_xp_level_role(guild_id, level):
    conn=await get_connection(); await conn.execute("DELETE FROM xp_level_roles WHERE guild_id=? AND level=?",(guild_id,level)); await conn.commit()

async def get_xp_leaderboard(guild_id,limit=10):
    conn=await get_connection()
    async with conn.execute("SELECT user_id,level,xp FROM users WHERE guild_id=? ORDER BY level DESC,xp DESC LIMIT ?",(guild_id,limit)) as c:return await c.fetchall()

async def add_warning(user_id,guild_id,moderator_id,reason):
    conn=await get_connection(); await conn.execute("INSERT INTO warnings(user_id,guild_id,moderator_id,reason,created_at) VALUES(?,?,?,?,?)",(user_id,guild_id,moderator_id,reason,int(time.time()))); await conn.commit()

async def get_warnings(user_id,guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM warnings WHERE user_id=? AND guild_id=? ORDER BY created_at DESC",(user_id,guild_id)) as c:return await c.fetchall()

async def clear_warnings(user_id,guild_id):
    conn=await get_connection(); await conn.execute("DELETE FROM warnings WHERE user_id=? AND guild_id=?",(user_id,guild_id)); await conn.commit()

async def increment_activity(user_id, guild_id, activity, amount=1):
    await _ensure_user(user_id, guild_id)
    conn=await get_connection()
    await conn.execute("INSERT INTO activity_stats(user_id,guild_id,activity,value) VALUES(?,?,?,?) ON CONFLICT(user_id,guild_id,activity) DO UPDATE SET value=value+excluded.value", (user_id,guild_id,activity,amount))
    await conn.commit()

async def get_activity(user_id, guild_id, activity):
    conn=await get_connection()
    async with conn.execute("SELECT value FROM activity_stats WHERE user_id=? AND guild_id=? AND activity=?", (user_id,guild_id,activity)) as c:
        row=await c.fetchone()
    return int(row[0]) if row else 0

async def has_badge(user_id, guild_id, badge_key):
    conn=await get_connection()
    async with conn.execute("SELECT 1 FROM earned_badges WHERE user_id=? AND guild_id=? AND badge_key=?", (user_id,guild_id,badge_key)) as c:
        return await c.fetchone() is not None

async def award_badge(user_id, guild_id, badge_key):
    await _ensure_user(user_id, guild_id)
    conn=await get_connection()
    cur=await conn.execute("INSERT OR IGNORE INTO earned_badges(user_id,guild_id,badge_key,earned_at) VALUES(?,?,?,?)", (user_id,guild_id,badge_key,int(time.time())))
    await conn.commit()
    return cur.rowcount == 1

async def count_earned_badges(user_id, guild_id):
    conn = await get_connection()
    async with conn.execute("SELECT COUNT(*) AS total FROM earned_badges WHERE user_id=? AND guild_id=?", (user_id, guild_id)) as c:
        row = await c.fetchone()
    return int(row["total"] or 0)

async def get_earned_badges(user_id, guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT badge_key,earned_at FROM earned_badges WHERE user_id=? AND guild_id=? ORDER BY earned_at ASC", (user_id,guild_id)) as c:
        return await c.fetchall()

async def get_relationship(guild_id,user_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM relationships WHERE guild_id=? AND (user1_id=? OR user2_id=?)", (int(guild_id), int(user_id), int(user_id))) as c:
        return await c.fetchone()

async def get_relationship_between(guild_id,user1_id,user2_id):
    a,b=sorted((int(user1_id),int(user2_id))); conn=await get_connection()
    async with conn.execute("SELECT * FROM relationships WHERE guild_id=? AND user1_id=? AND user2_id=?",(int(guild_id),a,b)) as c: return await c.fetchone()

async def set_relationship(guild_id,user1_id,user2_id,relation_type):
    a,b=sorted((int(user1_id),int(user2_id))); conn=await get_connection()
    await conn.execute("INSERT OR REPLACE INTO relationships(guild_id,user1_id,user2_id,relation_type,created_at) VALUES(?,?,?,?,?)",(int(guild_id),a,b,str(relation_type),int(time.time()))); await conn.commit()

async def delete_relationship(guild_id,user1_id,user2_id):
    a,b=sorted((int(user1_id),int(user2_id))); conn=await get_connection(); cur=await conn.execute("DELETE FROM relationships WHERE guild_id=? AND user1_id=? AND user2_id=?",(int(guild_id),a,b)); await conn.commit(); return cur.rowcount>0

async def record_routine_action(user_id,guild_id,action,day=None):
    from datetime import datetime,timezone
    day=day or datetime.now(timezone.utc).strftime("%Y-%m-%d"); conn=await get_connection(); cur=await conn.execute("INSERT OR IGNORE INTO routine_daily(user_id,guild_id,day,action,completed_at) VALUES(?,?,?,?,?)",(int(user_id),int(guild_id),day,str(action),int(time.time()))); await conn.commit(); return cur.rowcount==1

async def routine_actions(user_id,guild_id,day=None):
    from datetime import datetime,timezone
    day=day or datetime.now(timezone.utc).strftime("%Y-%m-%d"); conn=await get_connection()
    async with conn.execute("SELECT action FROM routine_daily WHERE user_id=? AND guild_id=? AND day=?",(int(user_id),int(guild_id),day)) as c: return {str(r[0]) for r in await c.fetchall()}

async def get_guild_config(guild_id):
    conn=await get_connection(); await conn.execute("INSERT OR IGNORE INTO guild_config(guild_id) VALUES(?)",(guild_id,)); await conn.commit()
    async with conn.execute("SELECT * FROM guild_config WHERE guild_id=?",(guild_id,)) as c:return await c.fetchone()

async def set_guild_config(guild_id,**fields):
    if not fields:return
    await get_guild_config(guild_id)
    allowed={"log_channel_id","mute_role_id","welcome_channel_id","welcome_message","welcome_style","auto_ban_bets_channel_id","auto_ban_bets_enabled","xp_enabled","moderation_confirmations_enabled"}
    fields={k:v for k,v in fields.items() if k in allowed}
    if not fields:return
    conn=await get_connection(); cols=", ".join(f"{k}=?" for k in fields); await conn.execute(f"UPDATE guild_config SET {cols} WHERE guild_id=?",(*fields.values(),guild_id)); await conn.commit()


async def set_ticket_config(guild_id, category_id=None, panel_channel_id=None, log_channel_id=None, staff_role_id=None, evaluation_channel_id=None, report_log_channel_id=None):
    conn = await get_connection()
    await conn.execute("INSERT OR IGNORE INTO ticket_config(guild_id) VALUES(?)", (int(guild_id),))
    fields, values = [], []
    for name, value in (("category_id", category_id), ("panel_channel_id", panel_channel_id), ("log_channel_id", log_channel_id), ("staff_role_id", staff_role_id), ("evaluation_channel_id", evaluation_channel_id), ("report_log_channel_id", report_log_channel_id)):
        if value is not None:
            fields.append(f"{name}=?"); values.append(int(value))
    if fields:
        values.append(int(guild_id))
        await conn.execute("UPDATE ticket_config SET " + ",".join(fields) + " WHERE guild_id=?", tuple(values))
    await conn.commit()

async def get_ticket_config(guild_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM ticket_config WHERE guild_id=?", (int(guild_id),)) as c:
        return await c.fetchone()

async def create_ticket(guild_id, channel_id, user_id, ticket_type, created_by, reason="Não informado"):
    conn = await get_connection()
    cur = await conn.execute(
        "INSERT INTO tickets(guild_id,channel_id,user_id,ticket_type,reason,status,created_at) VALUES(?,?,?,?,?,?,?)",
        (int(guild_id), int(channel_id), int(user_id), ticket_type, str(reason), "open", int(time.time()))
    )
    await conn.commit()
    return cur.lastrowid

async def get_ticket_by_channel(channel_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (int(channel_id),)) as c:
        return await c.fetchone()

async def get_open_ticket_for_user(guild_id, user_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open' ORDER BY id DESC LIMIT 1", (int(guild_id), int(user_id))) as c:
        return await c.fetchone()

async def claim_ticket_record(ticket_id, user_id):
    conn = await get_connection()
    await conn.execute("UPDATE tickets SET claimed_by=? WHERE id=? AND status='open'", (int(user_id), int(ticket_id)))
    await conn.commit()

async def close_ticket_record(ticket_id, closed_by, reason):
    conn = await get_connection()
    await conn.execute("UPDATE tickets SET status='closed', closed_at=?, closed_by=?, close_reason=? WHERE id=? AND status='open'", (int(time.time()), int(closed_by) if closed_by else None, reason, int(ticket_id)))
    await conn.commit()

async def create_ticket_evaluation(ticket_id, guild_id, user_id, claimed_by, dm_message_id):
    conn = await get_connection()
    await conn.execute(
        "INSERT OR REPLACE INTO ticket_evaluations(ticket_id,guild_id,user_id,claimed_by,dm_message_id,status,created_at) VALUES(?,?,?,?,?,?,?)",
        (int(ticket_id), int(guild_id), int(user_id), int(claimed_by) if claimed_by else None, int(dm_message_id), "pending", int(time.time()))
    )
    await conn.commit()

async def get_ticket_evaluation(ticket_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM ticket_evaluations WHERE ticket_id=?", (int(ticket_id),)) as c:
        return await c.fetchone()

async def get_pending_ticket_evaluations():
    conn = await get_connection()
    async with conn.execute("SELECT * FROM ticket_evaluations WHERE status='pending'") as c:
        return await c.fetchall()

async def complete_ticket_evaluation(ticket_id, stars, description):
    conn = await get_connection()
    await conn.execute(
        "UPDATE ticket_evaluations SET stars=?, description=?, status='answered', answered_at=? WHERE ticket_id=? AND status='pending'",
        (int(stars), str(description), int(time.time()), int(ticket_id))
    )
    await conn.commit()

async def get_pending_submissions(guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT id FROM form_submissions WHERE guild_id=? AND status='pending' ORDER BY id", (guild_id,)) as c:return await c.fetchall()

async def add_shop_item(guild_id,name,description,price,role_id=None,emoji="🛍️"):
    conn=await get_connection(); cur=await conn.execute("INSERT OR REPLACE INTO shop_items(guild_id,name,description,price,role_id,emoji) VALUES(?,?,?,?,?,?)",(guild_id,name,description,price,role_id,emoji)); await conn.commit(); return cur.lastrowid

async def get_shop_items(guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM shop_items WHERE guild_id=? ORDER BY price ASC",(guild_id,)) as c:return await c.fetchall()

async def get_shop_item(guild_id,item_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM shop_items WHERE guild_id=? AND id=?",(guild_id,item_id)) as c:return await c.fetchone()

async def has_item(user_id,guild_id,item_id):
    conn=await get_connection()
    async with conn.execute("SELECT 1 FROM inventory WHERE user_id=? AND guild_id=? AND item_id=?",(user_id,guild_id,item_id)) as c:return await c.fetchone() is not None

async def purchase_item(user_id,guild_id,item_id,price):
    await _ensure_user(user_id,guild_id)
    conn = await get_connection()
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute(
                "SELECT balance FROM users WHERE user_id=? AND guild_id=?",
                (user_id, guild_id),
            ) as c:
                row = await c.fetchone()
            if not row or row["balance"] < price:
                await conn.rollback()
                return False
            async with conn.execute(
                "SELECT 1 FROM inventory WHERE user_id=? AND guild_id=? AND item_id=?",
                (user_id, guild_id, item_id),
            ) as c:
                if await c.fetchone() is not None:
                    await conn.rollback()
                    return False
            cur = await conn.execute(
                "UPDATE users SET balance=balance-? WHERE user_id=? AND guild_id=? AND balance>=?",
                (price, user_id, guild_id, price),
            )
            if cur.rowcount != 1:
                await conn.rollback()
                return False
            await conn.execute(
                "INSERT INTO inventory(user_id,guild_id,item_id,purchased_at) VALUES(?,?,?,?)",
                (user_id,guild_id,item_id,int(time.time())),
            )
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

DEFAULT_CORVO_ITEMS = [
    ("Pena de Bronze", "Uma pena simples do Corvo, símbolo de veterano do arcade.", 100, "🪶"),
    ("Selo do Bando", "Um selo virtual para quem começou a colecionar Fichas Corvo.", 250, "🔖"),
    ("Ticket Sombrio", "Um ticket colecionável de uma noite no arcade.", 500, "🎟️"),
    ("Medalha Corvo", "Medalha virtual de progresso no bando.", 900, "🏅"),
    ("Olho de Ônix", "Relíquia negra e rara da coleção do Corvo.", 1500, "👁️"),
    ("Cartola do Corvo", "Uma cartola virtual para seu inventário.", 2500, "🎩"),
    ("Relógio de Prata", "Relógio colecionável com estética de estúdio antigo.", 4000, "⌚"),
    ("Coroa de Ouro", "Uma coroa virtual para colecionadores avançados.", 6500, "👑"),
    ("Relíquia do Estúdio", "Peça rara inspirada no antigo estúdio do Corvo.", 10000, "🏛️"),
    ("Cofre do Corvo", "O item mais valioso da loja: um troféu máximo de coleção.", 25000, "🗝️"),
]

async def ensure_default_corvo_shop(guild_id):
    conn=await get_connection()
    for name,description,price,emoji in DEFAULT_CORVO_ITEMS:
        await conn.execute("INSERT OR IGNORE INTO corvo_shop_items(guild_id,name,description,price,emoji) VALUES(?,?,?,?,?)",(guild_id,name,description,price,emoji))
    await conn.commit()

async def get_corvo_shop_items(guild_id):
    await ensure_default_corvo_shop(guild_id)
    conn=await get_connection()
    async with conn.execute("SELECT * FROM corvo_shop_items WHERE guild_id=? ORDER BY price ASC",(guild_id,)) as c:return await c.fetchall()

async def get_corvo_shop_item(guild_id,item_id):
    await ensure_default_corvo_shop(guild_id)
    conn=await get_connection()
    async with conn.execute("SELECT * FROM corvo_shop_items WHERE guild_id=? AND id=?",(guild_id,item_id)) as c:return await c.fetchone()

async def has_corvo_item(user_id,guild_id,item_id):
    conn=await get_connection()
    async with conn.execute("SELECT 1 FROM corvo_inventory WHERE user_id=? AND guild_id=? AND item_id=?",(user_id,guild_id,item_id)) as c:return await c.fetchone() is not None

async def purchase_corvo_item(user_id,guild_id,item_id,price):
    await _ensure_user(user_id,guild_id)
    conn = await get_connection()
    async with _db_lock:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            async with conn.execute(
                "SELECT 1 FROM corvo_inventory WHERE user_id=? AND guild_id=? AND item_id=?",
                (user_id, guild_id, item_id),
            ) as c:
                if await c.fetchone() is not None:
                    await conn.rollback()
                    return False
            cur = await conn.execute(
                "UPDATE users SET corvo_chips=corvo_chips-? WHERE user_id=? AND guild_id=? AND corvo_chips>=?",
                (price, user_id, guild_id, price),
            )
            if cur.rowcount != 1:
                await conn.rollback()
                return False
            await conn.execute(
                "INSERT INTO corvo_inventory(user_id,guild_id,item_id,purchased_at) VALUES(?,?,?,?)",
                (user_id,guild_id,item_id,int(time.time())),
            )
            await conn.commit()
            return True
        except Exception:
            await conn.rollback()
            raise

async def set_afk(user_id,guild_id,original_nick,reason):
    conn=await get_connection(); await conn.execute("INSERT OR REPLACE INTO afk(user_id,guild_id,original_nick,reason,since) VALUES(?,?,?,?,?)",(user_id,guild_id,original_nick,reason,int(time.time()))); await conn.commit()

async def get_afk(user_id,guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM afk WHERE user_id=? AND guild_id=?",(user_id,guild_id)) as c:return await c.fetchone()

async def clear_afk(user_id,guild_id):
    conn=await get_connection(); await conn.execute("DELETE FROM afk WHERE user_id=? AND guild_id=?",(user_id,guild_id)); await conn.commit()

# ===================== TAGS E FORMULÁRIOS =====================
async def upsert_tag(guild_id, name, response):
    conn = await get_connection()
    await conn.execute("INSERT INTO tags(guild_id,name,response,created_at) VALUES(?,?,?,?) ON CONFLICT(guild_id,name) DO UPDATE SET response=excluded.response", (guild_id,name,response,int(time.time())))
    await conn.commit()

async def delete_tag(guild_id, name):
    conn = await get_connection()
    cur = await conn.execute("DELETE FROM tags WHERE guild_id=? AND name=?", (guild_id,name.lower()))
    await conn.commit()
    return cur.rowcount == 1

async def get_tags(guild_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM tags WHERE guild_id=? ORDER BY name", (guild_id,)) as c:
        return await c.fetchall()

async def set_form_config(guild_id, panel_channel_id=None, review_channel_id=None):
    conn = await get_connection()
    await conn.execute("INSERT OR IGNORE INTO form_config(guild_id,panel_channel_id,review_channel_id) VALUES(?,?,?)", (guild_id,panel_channel_id,review_channel_id))
    fields=[]; values=[]
    if panel_channel_id is not None: fields.append("panel_channel_id=?"); values.append(panel_channel_id)
    if review_channel_id is not None: fields.append("review_channel_id=?"); values.append(review_channel_id)
    if fields:
        await conn.execute("UPDATE form_config SET " + ",".join(fields) + " WHERE guild_id=?", (*values,guild_id))
    await conn.commit()

async def get_form_config(guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM form_config WHERE guild_id=?", (guild_id,)) as c:
        return await c.fetchone()

async def create_form(guild_id, name, title, description, questions):
    conn=await get_connection()
    cur=await conn.execute("INSERT INTO forms(guild_id,name,title,description,questions,created_at) VALUES(?,?,?,?,?,?)", (guild_id,name,title,description,questions,int(time.time())))
    await conn.commit()
    return cur.lastrowid

async def get_forms(guild_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM forms WHERE guild_id=? AND active=1 ORDER BY id", (guild_id,)) as c:return await c.fetchall()

async def get_form(form_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM forms WHERE id=?", (form_id,)) as c:return await c.fetchone()

async def create_submission(form_id,guild_id,user_id,answers):
    conn=await get_connection()
    cur=await conn.execute("INSERT INTO form_submissions(form_id,guild_id,user_id,answers,status,created_at) VALUES(?,?,?,?,?,?)", (form_id,guild_id,user_id,answers,"pending",int(time.time())))
    await conn.commit(); return cur.lastrowid

async def get_submission(submission_id):
    conn=await get_connection()
    async with conn.execute("SELECT * FROM form_submissions WHERE id=?", (submission_id,)) as c:return await c.fetchone()

async def review_submission(submission_id, reviewer_id, status):
    if status not in ("approved","rejected"): return False
    conn=await get_connection()
    cur=await conn.execute("UPDATE form_submissions SET status=?,reviewer_id=?,reviewed_at=? WHERE id=? AND status='pending'", (status,reviewer_id,int(time.time()),submission_id))
    await conn.commit(); return cur.rowcount == 1


# ========================= FORMULÁRIOS AVANÇADOS =========================

async def set_form_active(form_id, guild_id, active):
    conn = await get_connection()
    cur = await conn.execute(
        "UPDATE forms SET active=? WHERE id=? AND guild_id=?",
        (1 if active else 0, int(form_id), int(guild_id))
    )
    await conn.commit()
    return cur.rowcount == 1

async def update_form_definition(form_id, guild_id, title=None, description=None, pages=None):
    conn = await get_connection()
    fields, values = [], []
    if title is not None:
        fields.append("title=?"); values.append(str(title)[:45])
    if description is not None:
        fields.append("description=?"); values.append(str(description)[:1000])
    if pages is not None:
        fields.append("questions=?"); values.append(json.dumps(pages, ensure_ascii=False))
    if not fields:
        return False
    values.extend([int(form_id), int(guild_id)])
    cur = await conn.execute(
        "UPDATE forms SET " + ",".join(fields) + " WHERE id=? AND guild_id=?",
        tuple(values)
    )
    await conn.commit()
    return cur.rowcount == 1



# ========================= TEMPVOICE =========================

async def set_tempvoice_config(guild_id, category_id=None, lobby_channel_id=None, panel_channel_id=None):
    conn = await get_connection()
    await conn.execute(
        "INSERT OR IGNORE INTO tempvoice_config(guild_id,category_id,lobby_channel_id,panel_channel_id) VALUES(?,?,?,?)",
        (guild_id, category_id, lobby_channel_id, panel_channel_id)
    )
    fields, values = [], []
    for name, value in (("category_id", category_id), ("lobby_channel_id", lobby_channel_id), ("panel_channel_id", panel_channel_id)):
        if value is not None:
            fields.append(f"{name}=?")
            values.append(int(value))
    if fields:
        values.append(int(guild_id))
        await conn.execute("UPDATE tempvoice_config SET " + ",".join(fields) + " WHERE guild_id=?", tuple(values))
    await conn.commit()

async def get_tempvoice_config(guild_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM tempvoice_config WHERE guild_id=?", (int(guild_id),)) as c:
        return await c.fetchone()

async def register_tempvoice_channel(guild_id, channel_id, owner_id, text_channel_id=None):
    conn = await get_connection()
    await conn.execute(
        "INSERT OR REPLACE INTO tempvoice_channels(guild_id,channel_id,owner_id,text_channel_id,created_at) VALUES(?,?,?,?,?)",
        (int(guild_id), int(channel_id), int(owner_id), int(text_channel_id) if text_channel_id else None, int(time.time()))
    )
    await conn.commit()

async def get_tempvoice_channel(channel_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM tempvoice_channels WHERE channel_id=?", (int(channel_id),)) as c:
        return await c.fetchone()

async def get_tempvoice_channels(guild_id):
    conn = await get_connection()
    async with conn.execute("SELECT * FROM tempvoice_channels WHERE guild_id=?", (int(guild_id),)) as c:
        return await c.fetchall()

async def unregister_tempvoice_channel(channel_id):
    conn = await get_connection()
    await conn.execute("DELETE FROM tempvoice_channels WHERE channel_id=?", (int(channel_id),))
    await conn.commit()

async def set_tempvoice_owner(channel_id, owner_id):
    conn = await get_connection()
    await conn.execute("UPDATE tempvoice_channels SET owner_id=? WHERE channel_id=?", (int(owner_id), int(channel_id)))
    await conn.commit()

# -------------------- Memória da IA --------------------
async def init_ai_memory():
    conn = await get_connection()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_ai_memory_context ON ai_memory(guild_id, channel_id, created_at)")
    await conn.commit()

async def add_ai_memory(guild_id, channel_id, user_id, role, content):
    conn = await get_connection()
    await conn.execute(
        "INSERT INTO ai_memory(guild_id, channel_id, user_id, role, content) VALUES (?,?,?,?,?)",
        (guild_id, channel_id, user_id, role, content[:4000]),
    )
    # Mantém apenas as 30 mensagens mais recentes por canal/guild para não deixar
    # a memória crescer indefinidamente.
    await conn.execute("""
        DELETE FROM ai_memory
        WHERE guild_id=? AND channel_id=? AND id NOT IN (
            SELECT id FROM ai_memory WHERE guild_id=? AND channel_id=? ORDER BY id DESC LIMIT 30
        )
    """, (guild_id, channel_id, guild_id, channel_id))
    await conn.commit()

async def get_ai_memory(guild_id, channel_id, limit=12):
    conn = await get_connection()
    cur = await conn.execute(
        "SELECT user_id, role, content FROM ai_memory WHERE guild_id=? AND channel_id=? ORDER BY id DESC LIMIT ?",
        (guild_id, channel_id, limit),
    )
    rows = await cur.fetchall()
    return list(reversed(rows))

async def clear_ai_memory(guild_id, channel_id=None):
    conn = await get_connection()
    if channel_id is None:
        await conn.execute("DELETE FROM ai_memory WHERE guild_id=?", (guild_id,))
    else:
        await conn.execute("DELETE FROM ai_memory WHERE guild_id=? AND channel_id=?", (guild_id, channel_id))
    await conn.commit()
