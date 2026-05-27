import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
FACTURE_SHEET_NAME = os.getenv("FACTURE_SHEET_NAME", "Facture")

ROLE_PATRON = "👔︱PDG"
ROLE_MANAGER = "🥼︱Manager"
ROLE_EMPLOYE = "🍔︱Employé"
ROLE_ARRIVANT = "🗼︱Parisien"

CHANNEL_ANNONCES = "📢︱annonce"
CHANNEL_COMMANDES = "📰︱commandes"
CHANNEL_MENUS = "📇︱menu"
CHANNEL_LOGS = "🔗︱logs"
CHANNEL_SERVICES = "📟︱service"

CATEGORY_TICKETS = "Convocations"