from pathlib import Path

import discord

from utils.storage import load_json, save_json


MENU_FILE = Path("data/menu.json")


DEFAULT_MENU = {
    "Burgers": [
        {
            "nom": "Burger Classic",
            "prix": "50€",
            "description": "Pain burger, steak, salade, tomate, cheddar, sauce BurgerShot"
        }
    ],
    "Accompagnements": [
        {
            "nom": "Frites",
            "prix": "25€",
            "description": "Pommes de terre, sel, huile"
        }
    ],
    "Boissons": [
        {
            "nom": "Soda",
            "prix": "20€",
            "description": "Boisson fraîche au choix"
        }
    ],
    "Menus": [
        {
            "nom": "Menu Complet",
            "prix": "85€",
            "description": "Burger Classic, frites, soda"
        }
    ]
}


def load_menu():
    return load_json(MENU_FILE, DEFAULT_MENU)


def save_menu(menu_data):
    save_json(MENU_FILE, menu_data)


def format_article(article):
    nom = article.get("nom", "Article inconnu")
    prix = article.get("prix", "0€")
    description = article.get("description", "")

    text = f"- **{nom}** — `{prix}`"

    if description:
        text += f"\n> {description}"

    return text


def split_text(text: str, max_length: int = 3900):
    chunks = []
    current = ""

    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_length:
            chunks.append(current)
            current = ""

        current += line + "\n"

    if current.strip():
        chunks.append(current)

    return chunks

def build_menu_embed():
    menu_data = load_menu()

    menu_text = "# 🍔 Menu BurgerShot :\n\n"
    menu_text += "___Voici le menu officiel du BurgerShot.___\n\n"

    for categorie, articles in menu_data.items():
        menu_text += f"## 📌 {categorie}\n"

        if not articles:
            menu_text += "Aucun article.\n\n"
            continue

        for article in articles:
            menu_text += format_article(article) + "\n\n"

    chunks = split_text(menu_text)

    embed = discord.Embed(
        description=chunks[0] if chunks else "# 🍔 Menu BurgerShot\n\nAucun article dans le menu.",
        color=discord.Color.red()
    )

    for chunk in chunks[1:]:
        embed.add_field(
            name="‎",
            value=chunk[:1024],
            inline=False
        )

    embed.set_footer(text="BurgerShot Sud RP")
    return embed