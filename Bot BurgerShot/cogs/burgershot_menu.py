from typing import Optional
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import CHANNEL_MENUS
from utils.logger import log_action
from utils.menu_utils import build_menu_embed, load_menu, save_menu
from utils.permissions import is_staff
from utils.storage import load_json, save_json


MENU_PANEL_FILE = Path("data/menu_panel.json")


def format_price(prix: str):
    prix = str(prix).strip()
    prix = prix.replace("€", "").replace("$", "").strip()

    if not prix:
        return "0€"

    return f"{prix}€"


def clean_description(description: Optional[str]):
    if description is None:
        return ""

    description = str(description).strip()

    if not description:
        return ""

    return description[:900]


def load_menu_panel():
    return load_json(MENU_PANEL_FILE, {})


def save_menu_panel(panel_data):
    save_json(MENU_PANEL_FILE, panel_data)


async def categorie_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    menu_data = load_menu()
    choices = []

    for categorie in menu_data.keys():
        if current.lower() in categorie.lower():
            choices.append(
                app_commands.Choice(
                    name=categorie[:100],
                    value=categorie[:100]
                )
            )

    return choices[:25]


async def article_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    menu_data = load_menu()
    categorie = getattr(interaction.namespace, "categorie", None)

    choices = []

    if categorie and categorie in menu_data:
        articles = menu_data[categorie]

        for article in articles:
            nom = article.get("nom", "Article")
            prix = article.get("prix", "0€")

            if current.lower() in nom.lower():
                choices.append(
                    app_commands.Choice(
                        name=f"{nom} — {prix}"[:100],
                        value=nom[:100]
                    )
                )
    else:
        for cat_name, articles in menu_data.items():
            for article in articles:
                nom = article.get("nom", "Article")
                prix = article.get("prix", "0€")

                if current.lower() in nom.lower():
                    choices.append(
                        app_commands.Choice(
                            name=f"{nom} — {prix} ({cat_name})"[:100],
                            value=nom[:100]
                        )
                    )

    return choices[:25]


class BurgerShotMenu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    menu_group = app_commands.Group(
        name="menu",
        description="Gestion du menu BurgerShot"
    )

    async def get_menu_panel_message(self, guild: discord.Guild):
        panel_data = load_menu_panel()
        guild_id = str(guild.id)

        if guild_id not in panel_data:
            return None, None

        channel_id = panel_data[guild_id].get("channel_id")
        message_id = panel_data[guild_id].get("message_id")

        channel = guild.get_channel(channel_id)

        if channel is None:
            return None, None

        try:
            message = await channel.fetch_message(message_id)
            return channel, message

        except discord.NotFound:
            return channel, None

        except discord.Forbidden:
            print("[MENU] Permissions insuffisantes pour lire/modifier le panel menu.")
            return channel, None

        except discord.HTTPException as error:
            print(f"[MENU] Erreur HTTP panel menu : {error}")
            return channel, None

    async def update_menu_panel(
        self,
        guild: discord.Guild,
        salon: Optional[discord.TextChannel] = None
    ):
        if guild is None:
            return None

        panel_data = load_menu_panel()
        guild_id = str(guild.id)

        old_channel, old_message = await self.get_menu_panel_message(guild)

        if salon is None:
            salon = old_channel

        if salon is None:
            salon = discord.utils.get(guild.text_channels, name=CHANNEL_MENUS)

        if salon is None:
            print(f"[MENU] Salon introuvable : {CHANNEL_MENUS}")
            return None

        embed = build_menu_embed()

        if old_message is not None and old_channel is not None:
            if old_channel.id == salon.id:
                await old_message.edit(embed=embed)

                panel_data[guild_id] = {
                    "channel_id": old_channel.id,
                    "message_id": old_message.id
                }

                save_menu_panel(panel_data)
                return old_message

            try:
                await old_message.delete()
            except Exception:
                pass

        new_message = await salon.send(embed=embed)

        panel_data[guild_id] = {
            "channel_id": salon.id,
            "message_id": new_message.id
        }

        save_menu_panel(panel_data)
        return new_message

    @menu_group.command(name="afficher", description="Afficher le menu BurgerShot")
    async def menu_afficher(self, interaction: discord.Interaction):
        embed = build_menu_embed()

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🍔 Menu affiché",
            f"{interaction.user.mention} a affiché le menu en éphémère.",
            discord.Color.red()
        )

    @menu_group.command(name="poster", description="Poster ou mettre à jour l'embed permanent du menu")
    async def menu_poster(
        self,
        interaction: discord.Interaction,
        salon: Optional[discord.TextChannel] = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent poster le menu.",
                ephemeral=True
            )
            return

        if salon is None:
            salon = discord.utils.get(interaction.guild.text_channels, name=CHANNEL_MENUS)

        if salon is None:
            await interaction.response.send_message(
                f"❌ Salon `{CHANNEL_MENUS}` introuvable.",
                ephemeral=True
            )
            return

        message = await self.update_menu_panel(interaction.guild, salon)

        if message is None:
            await interaction.response.send_message(
                "❌ Impossible de créer ou mettre à jour le menu.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Menu permanent créé / mis à jour dans {salon.mention}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📋 Menu permanent mis à jour",
            f"{interaction.user.mention} a créé ou mis à jour le menu permanent dans {salon.mention}.",
            discord.Color.red()
        )

    @menu_group.command(name="categorie_ajouter", description="Ajouter une catégorie au menu")
    async def categorie_ajouter(
        self,
        interaction: discord.Interaction,
        nom: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        menu_data = load_menu()

        if nom in menu_data:
            await interaction.response.send_message(
                "❌ Cette catégorie existe déjà.",
                ephemeral=True
            )
            return

        menu_data[nom] = []
        save_menu(menu_data)

        await self.update_menu_panel(interaction.guild)

        await interaction.response.send_message(
            f"✅ Catégorie `{nom}` ajoutée. Le menu permanent a été mis à jour.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "➕ Catégorie menu ajoutée",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Catégorie :** {nom}",
            discord.Color.green()
        )

    @menu_group.command(name="categorie_supprimer", description="Supprimer une catégorie du menu")
    @app_commands.autocomplete(nom=categorie_autocomplete)
    async def categorie_supprimer(
        self,
        interaction: discord.Interaction,
        nom: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        menu_data = load_menu()

        if nom not in menu_data:
            await interaction.response.send_message(
                "❌ Catégorie introuvable.",
                ephemeral=True
            )
            return

        del menu_data[nom]
        save_menu(menu_data)

        await self.update_menu_panel(interaction.guild)

        await interaction.response.send_message(
            f"✅ Catégorie `{nom}` supprimée. Le menu permanent a été mis à jour.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "➖ Catégorie menu supprimée",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Catégorie :** {nom}",
            discord.Color.red()
        )

    @menu_group.command(name="article_ajouter", description="Ajouter un article au menu")
    @app_commands.autocomplete(categorie=categorie_autocomplete)
    async def article_ajouter(
        self,
        interaction: discord.Interaction,
        categorie: str,
        nom: str,
        prix: str,
        description: Optional[str] = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        menu_data = load_menu()

        if categorie not in menu_data:
            await interaction.response.send_message(
                "❌ Catégorie introuvable.",
                ephemeral=True
            )
            return

        for item in menu_data[categorie]:
            if item.get("nom", "").lower() == nom.lower():
                await interaction.response.send_message(
                    "❌ Cet article existe déjà dans cette catégorie.",
                    ephemeral=True
                )
                return

        prix_formate = format_price(prix)
        description_formatee = clean_description(description)

        menu_data[categorie].append({
            "nom": nom,
            "prix": prix_formate,
            "description": description_formatee
        })

        save_menu(menu_data)

        await self.update_menu_panel(interaction.guild)

        await interaction.response.send_message(
            f"✅ Article `{nom}` ajouté dans `{categorie}` au prix de `{prix_formate}`. Le menu permanent a été mis à jour.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "➕ Article menu ajouté",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Catégorie :** {categorie}\n"
            f"**Article :** {nom}\n"
            f"**Prix :** {prix_formate}\n"
            f"**Description :** {description_formatee or 'Aucune'}",
            discord.Color.green()
        )

    @menu_group.command(name="article_supprimer", description="Supprimer un article du menu")
    @app_commands.autocomplete(
        categorie=categorie_autocomplete,
        article=article_autocomplete
    )
    async def article_supprimer(
        self,
        interaction: discord.Interaction,
        categorie: str,
        article: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        menu_data = load_menu()

        if categorie not in menu_data:
            await interaction.response.send_message(
                "❌ Catégorie introuvable.",
                ephemeral=True
            )
            return

        old_len = len(menu_data[categorie])

        menu_data[categorie] = [
            item for item in menu_data[categorie]
            if item.get("nom", "").lower() != article.lower()
        ]

        if len(menu_data[categorie]) == old_len:
            await interaction.response.send_message(
                "❌ Article introuvable dans cette catégorie.",
                ephemeral=True
            )
            return

        save_menu(menu_data)

        await self.update_menu_panel(interaction.guild)

        await interaction.response.send_message(
            f"✅ Article `{article}` supprimé de `{categorie}`. Le menu permanent a été mis à jour.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "➖ Article menu supprimé",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Catégorie :** {categorie}\n"
            f"**Article :** {article}",
            discord.Color.red()
        )

    @menu_group.command(name="article_renommer", description="Renommer un article du menu")
    @app_commands.autocomplete(
        categorie=categorie_autocomplete,
        article=article_autocomplete
    )
    async def article_renommer(
        self,
        interaction: discord.Interaction,
        categorie: str,
        article: str,
        nouveau_nom: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        menu_data = load_menu()

        if categorie not in menu_data:
            await interaction.response.send_message(
                "❌ Catégorie introuvable.",
                ephemeral=True
            )
            return

        nouveau_nom = nouveau_nom.strip()

        if not nouveau_nom:
            await interaction.response.send_message(
                "❌ Le nouveau nom ne peut pas être vide.",
                ephemeral=True
            )
            return

        for item in menu_data[categorie]:
            if item.get("nom", "").lower() == nouveau_nom.lower():
                await interaction.response.send_message(
                    "❌ Un article avec ce nom existe déjà dans cette catégorie.",
                    ephemeral=True
                )
                return

        for item in menu_data[categorie]:
            if item.get("nom", "").lower() == article.lower():
                ancien_nom = item.get("nom", article)

                item["nom"] = nouveau_nom
                save_menu(menu_data)

                await self.update_menu_panel(interaction.guild)

                await interaction.response.send_message(
                    f"✅ Article renommé : `{ancien_nom}` → `{nouveau_nom}`. Le menu permanent a été mis à jour.",
                    ephemeral=True
                )

                await log_action(
                    interaction.guild,
                    "✏️ Article menu renommé",
                    f"**Staff :** {interaction.user.mention}\n"
                    f"**Catégorie :** {categorie}\n"
                    f"**Ancien nom :** {ancien_nom}\n"
                    f"**Nouveau nom :** {nouveau_nom}",
                    discord.Color.blurple()
                )
                return

        await interaction.response.send_message(
            "❌ Article introuvable dans cette catégorie.",
            ephemeral=True
        )

    @menu_group.command(name="prix_modifier", description="Modifier le prix d'un article")
    @app_commands.autocomplete(
        categorie=categorie_autocomplete,
        article=article_autocomplete
    )
    async def prix_modifier(
        self,
        interaction: discord.Interaction,
        categorie: str,
        article: str,
        nouveau_prix: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        menu_data = load_menu()

        if categorie not in menu_data:
            await interaction.response.send_message(
                "❌ Catégorie introuvable.",
                ephemeral=True
            )
            return

        for item in menu_data[categorie]:
            if item.get("nom", "").lower() == article.lower():
                ancien_prix = item.get("prix", "0€")
                nouveau_prix_formate = format_price(nouveau_prix)

                item["prix"] = nouveau_prix_formate
                save_menu(menu_data)

                await self.update_menu_panel(interaction.guild)

                await interaction.response.send_message(
                    f"✅ Prix de `{article}` modifié : `{ancien_prix}` → `{nouveau_prix_formate}`. Le menu permanent a été mis à jour.",
                    ephemeral=True
                )

                await log_action(
                    interaction.guild,
                    "💰 Prix menu modifié",
                    f"**Staff :** {interaction.user.mention}\n"
                    f"**Catégorie :** {categorie}\n"
                    f"**Article :** {article}\n"
                    f"**Ancien prix :** {ancien_prix}\n"
                    f"**Nouveau prix :** {nouveau_prix_formate}",
                    discord.Color.gold()
                )
                return

        await interaction.response.send_message(
            "❌ Article introuvable dans cette catégorie.",
            ephemeral=True
        )

    @menu_group.command(name="description_modifier", description="Modifier la description / ingrédients d'un article")
    @app_commands.autocomplete(
        categorie=categorie_autocomplete,
        article=article_autocomplete
    )
    async def description_modifier(
        self,
        interaction: discord.Interaction,
        categorie: str,
        article: str,
        description: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        menu_data = load_menu()

        if categorie not in menu_data:
            await interaction.response.send_message(
                "❌ Catégorie introuvable.",
                ephemeral=True
            )
            return

        description_formatee = clean_description(description)

        for item in menu_data[categorie]:
            if item.get("nom", "").lower() == article.lower():
                ancienne_description = item.get("description", "Aucune")

                item["description"] = description_formatee
                save_menu(menu_data)

                await self.update_menu_panel(interaction.guild)

                await interaction.response.send_message(
                    f"✅ Description de `{article}` modifiée. Le menu permanent a été mis à jour.",
                    ephemeral=True
                )

                await log_action(
                    interaction.guild,
                    "📝 Description menu modifiée",
                    f"**Staff :** {interaction.user.mention}\n"
                    f"**Catégorie :** {categorie}\n"
                    f"**Article :** {article}\n"
                    f"**Ancienne description :** {ancienne_description or 'Aucune'}\n"
                    f"**Nouvelle description :** {description_formatee or 'Aucune'}",
                    discord.Color.blurple()
                )
                return

        await interaction.response.send_message(
            "❌ Article introuvable dans cette catégorie.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(BurgerShotMenu(bot))