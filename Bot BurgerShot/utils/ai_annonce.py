import json
import asyncio
from openai import OpenAI

from config import OPENAI_MODEL


client = OpenAI()


SYSTEM_PROMPT = """
Tu es un assistant qui écrit des annonces Discord RP FiveM pour une entreprise BurgerShot FR.

Tu dois transformer un petit message brouillon en une annonce propre, professionnelle et RP.

Réponds UNIQUEMENT en JSON valide, sans markdown autour.

Format obligatoire :
{
  "title": "Titre court avec emoji",
  "description": "Texte principal avec mise en forme Discord",
  "fields": [
    {
      "name": "## Titre de section",
      "value": "Contenu de la section",
      "inline": false
    }
  ],
  "footer": "Texte court de footer" (comme direction burgershot etc...)
}

Règles :
- Utilise du français.
- Style BurgerShot / restauration / RP FiveM.
- Mets des emojis sans en abusé.
- Utilise la mise en forme Discord : ##, >, •, `code`, __souligné__, **gras**, *italic*.
- Ne fais pas trop long.
- Ne mets pas de ping @everyone ou @here.
- Ne promets rien d'illégal ou HRP (pas de "annonce burgershot rp fivem" juste un truc carré sans allusion comme IRL).
- Les fields doivent avoir des titres qui commencent par ##.
"""


def fallback_announcement(message: str):
    return {
        "title": "🍔 Annonce BurgerShot",
        "description": (
            "## 📢 Information importante\n"
            f"> {message}\n\n"
            "Merci de prendre en compte cette annonce."
        ),
        "fields": [
            {
                "name": "## 📌 Détails",
                "value": "• Restez attentifs aux informations données par la direction.\n• Merci de respecter les consignes RP.",
                "inline": False
            }
        ],
        "footer": "BurgerShot Sud RP"
    }


def parse_ai_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")

        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                return None

    return None


def generate_announcement_sync(message: str):
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=f"Message brouillon à transformer en annonce Discord : {message}"
    )

    data = parse_ai_json(response.output_text)

    if data is None:
        return fallback_announcement(message)

    if "title" not in data or "description" not in data:
        return fallback_announcement(message)

    if "fields" not in data or not isinstance(data["fields"], list):
        data["fields"] = []

    if "footer" not in data:
        data["footer"] = "BurgerShot Sud RP"

    return data


async def generate_announcement(message: str):
    return await asyncio.to_thread(generate_announcement_sync, message)