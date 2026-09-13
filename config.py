import os
from dotenv import load_dotenv
load_dotenv()
TOKEN=os.getenv("DISCORD_TOKEN")
OWNER_IDS=[int(x) for x in os.getenv("OWNER_IDS","").split(",") if x.strip().isdigit()]
GUILD_IDS=[int(x) for x in os.getenv("GUILD_IDS","").split(",") if x.strip().isdigit()]
# Prefixo principal: K! — evita conflito com mensagens como "Kkkkk".
# Aceita "K! saldo" e "K!saldo".
PREFIX="K!"
DATABASE_PATH=os.getenv("DATABASE_PATH","kibot.db")
_db_parent=os.path.dirname(os.path.abspath(DATABASE_PATH))
os.makedirs(_db_parent, exist_ok=True)
CURRENCY_NAME="Crowings"; CURRENCY_CODE="CRW"; CURRENCY_SYMBOL="🪶"
DAILY_AMOUNT=200; WORK_MIN=50; WORK_MAX=250
WORK_COOLDOWN_SECONDS=3600; DAILY_COOLDOWN_SECONDS=86400
STARTING_BALANCE=100
XP_MESSAGE_MIN=5; XP_MESSAGE_MAX=15; XP_MESSAGE_COOLDOWN=60
XP_VOICE_PER_5_MIN=10
# GIFs podem ser trocados sem alterar código. URLs diretas de GIF/Discord CDN funcionam.
GIF_URLS=[x.strip() for x in os.getenv("GIF_URLS","").split(",") if x.strip()]


# XP por atividades de economia
XP_DAILY=25
XP_WORK=20
XP_BICO=15
XP_COMPANY_CREATE=100
XP_COMPANY_PROFIT=50

# Bônus global de XP para o dono do bot e apoiadores/Boosters.
XP_BOOST_MULTIPLIER=2
XP_BOOSTER_ROLE_ID=int(os.getenv("XP_BOOSTER_ROLE_ID","1541152198325575690"))

# Cassino: jackpot especial. Quando uma rodada vencedora acerta o jackpot,
# o pagamento final é exatamente 3x a aposta, em CRW ou XP.
JACKPOT_CHANCE=0.05
JACKPOT_MULTIPLIER=3
