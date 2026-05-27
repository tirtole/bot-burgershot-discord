import asyncio
from pathlib import Path
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.invoice_xlsx import create_invoice_xlsx, MAX_ITEMS, format_euro
from utils.logger import log_action
from utils.permissions import is_staff
from utils.storage import load_json, save_json


FACTURES_PANEL_FILE = Path("data/factures_panel.json")
FACTURES_DIR = Path("factures")


def load_factures_panel():
    return load_json(FACTURES_PANEL_FILE, {})


def save_factures_panel(data):
    save_json(FACTURES_PANEL_FILE, data)


def get_output_channel(guild: discord.Guild):
    panel_data = load_factures_panel()
    guild_id = str(guild.id)

    if guild_id not in panel_data:
        return None

    output_channel_id = panel_data[guild_id].get("output_channel_id")

    if output_channel_id is None:
        return None

    return guild.get_channel(output_channel_id)


def get_recent_facture_files(limit: int = 15):
    FACTURES_DIR.mkdir(parents=True, exist_ok=True)

    files = [
        file for file in FACTURES_DIR.glob("*.pdf")
        if file.is_file()
    ]

    files.sort(
        key=lambda file: file.stat().st_mtime,
        reverse=True
    )

    return files[:limit]


def build_facture_list_embed():
    files = get_recent_facture_files()

    if not files:
        description = (
            "# 📂 Liste des factures\n\n"
            "Aucune facture PDF trouvée dans le dossier `factures/`."
        )
    else:
        text = ""

        for file in files:
            size_kb = round(file.stat().st_size / 1024, 1)
            date = datetime.fromtimestamp(file.stat().st_mtime).strftime("%d/%m/%Y %H:%M")

            text += (
                f"• `{file.name}`\n"
                f"  Taille : `{size_kb} KB` • Date : `{date}`\n\n"
            )

        description = (
            "# 📂 Liste des factures\n\n"
            f"{text}"
            "## 🔎 Recherche\n"
            "Utilise `/factures rechercher numero:` pour voir les détails d’une facture.\n\n"
            "## 📎 Renvoyer\n"
            "Utilise `/factures renvoyer numero:` pour renvoyer une facture PDF."
        )

    embed = discord.Embed(
        description=description[:4096],
        color=discord.Color.orange()
    )

    embed.set_footer(text="BurgerShot Sud RP • Liste des factures")
    return embed


class FactureInfoModal(discord.ui.Modal, title="Informations de la facture"):
    entreprise = discord.ui.TextInput(
        label="Entreprise",
        placeholder="Exemple : BurgerShot",
        required=True,
        max_length=100
    )

    adresse_entreprise = discord.ui.TextInput(
        label="Adresse entreprise",
        placeholder="Exemple : Avenue Felix Faure, Paris",
        required=True,
        max_length=150
    )

    mail_entreprise = discord.ui.TextInput(
        label="Mail entreprise",
        placeholder="Exemple : contact@burgershot.fr",
        required=True,
        max_length=120
    )

    destinataire = discord.ui.TextInput(
        label="Destinataire",
        placeholder="Exemple : John Smith",
        required=True,
        max_length=100
    )

    numero = discord.ui.TextInput(
        label="Numéro de téléphone",
        placeholder="Exemple : 75010017",
        required=True,
        max_length=50
    )

    def __init__(
        self,
        note: str | None = None,
        salon: discord.TextChannel | None = None
    ):
        super().__init__()
        self.note = note
        self.salon = salon

    async def on_submit(self, interaction: discord.Interaction):
        view = FactureSessionView(
            author_id=interaction.user.id,
            info={
                "entreprise": self.entreprise.value,
                "adresse_entreprise": self.adresse_entreprise.value,
                "mail_entreprise": self.mail_entreprise.value,
                "destinataire": self.destinataire.value,
                "numero": self.numero.value,
            },
            note=self.note,
            salon=self.salon
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True
        )


class ItemModal(discord.ui.Modal):
    nom = discord.ui.TextInput(
        label="Nom de l'item",
        placeholder="Exemple : Menu Classic",
        required=True,
        max_length=100
    )

    quantite = discord.ui.TextInput(
        label="Quantité",
        placeholder="Exemple : 2",
        required=True,
        max_length=10
    )

    prix = discord.ui.TextInput(
        label="Prix unitaire",
        placeholder="Exemple : 50",
        required=True,
        max_length=10
    )

    def __init__(self, session_view):
        super().__init__(
            title=f"Ajouter item {len(session_view.items) + 1}/{MAX_ITEMS}"
        )
        self.session_view = session_view

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.session_view.author_id:
            await interaction.response.send_message(
                "❌ Ce panel de facture ne t’appartient pas.",
                ephemeral=True
            )
            return

        if len(self.session_view.items) >= MAX_ITEMS:
            await interaction.response.send_message(
                f"❌ Tu peux mettre maximum {MAX_ITEMS} items.",
                ephemeral=True
            )
            return

        self.session_view.items.append({
            "nom": self.nom.value,
            "quantite": self.quantite.value,
            "prix": self.prix.value
        })

        await interaction.response.edit_message(
            embed=self.session_view.build_embed(),
            view=self.session_view
        )


class NoteModal(discord.ui.Modal, title="Modifier la note"):
    note = discord.ui.TextInput(
        label="Note de la facture",
        placeholder="Exemple : Contrat entreprise, commande spéciale, réduction, etc.",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    def __init__(self, session_view):
        super().__init__()
        self.session_view = session_view

        if self.session_view.note:
            self.note.default = self.session_view.note

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.session_view.author_id:
            await interaction.response.send_message(
                "❌ Ce panel de facture ne t’appartient pas.",
                ephemeral=True
            )
            return

        new_note = self.note.value.strip()

        if new_note:
            self.session_view.note = new_note
        else:
            self.session_view.note = None

        await interaction.response.edit_message(
            embed=self.session_view.build_embed(),
            view=self.session_view
        )


class FactureSessionView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        info: dict,
        note: str | None = None,
        salon: discord.TextChannel | None = None
    ):
        super().__init__(timeout=600)
        self.author_id = author_id
        self.info = info
        self.note = note
        self.salon = salon
        self.items = []

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Ce panel de facture ne t’appartient pas.",
                ephemeral=True
            )
            return False

        return True

    def calculate_total(self):
        total = 0

        for item in self.items:
            try:
                quantite = float(str(item["quantite"]).replace(",", "."))
                prix = float(
                    str(item["prix"])
                    .replace(",", ".")
                    .replace("€", "")
                    .replace(" ", "")
                )

                total += quantite * prix

            except Exception:
                pass

        return total

    def build_items_text(self):
        if not self.items:
            return "Aucun item ajouté pour le moment."

        text = ""

        for index, item in enumerate(self.items, start=1):
            try:
                quantite = float(str(item["quantite"]).replace(",", "."))
                prix = float(
                    str(item["prix"])
                    .replace(",", ".")
                    .replace("€", "")
                    .replace(" ", "")
                )

                item_total = quantite * prix
                item_total_display = format_euro(item_total)

            except Exception:
                item_total_display = "calcul impossible"

            text += (
                f"### Item {index}\n"
                f"**Nom :** {item['nom']}\n"
                f"**Quantité :** `{item['quantite']}`\n"
                f"**Prix unitaire :** `{item['prix']}€`\n"
                f"**Total item :** `{item_total_display}`\n\n"
            )

        return text

    def build_embed(self):
        total = self.calculate_total()

        if self.salon is not None:
            destination = self.salon.mention
        else:
            destination = "Message privé éphémère"

        description = (
            "# 🧾 Création de facture BurgerShot\n\n"
            "Ajoute les items un par un avec le bouton ci-dessous.\n"
            f"Tu peux ajouter maximum `{MAX_ITEMS}` items.\n\n"

            "## 📌 Informations\n"
            f"**Entreprise :** {self.info['entreprise']}\n"
            f"**Adresse :** {self.info['adresse_entreprise']}\n"
            f"**Mail :** {self.info['mail_entreprise']}\n"
            f"**Destinataire :** {self.info['destinataire']}\n"
            f"**Téléphone :** {self.info['numero']}\n\n"

            "## 🍔 Items\n"
            f"{self.build_items_text()}\n"

            "## 💰 Total actuel\n"
            f"`{format_euro(total)}`\n\n"

            "## 📝 Note\n"
            f"{self.note or 'Aucune note.'}\n\n"

            "## 📤 Destination\n"
            f"{destination}"
        )

        embed = discord.Embed(
            description=description[:4096],
            color=discord.Color.orange()
        )

        embed.set_footer(text="BurgerShot Sud RP • Facturation")
        return embed

    @discord.ui.button(
        label="Ajouter un item",
        style=discord.ButtonStyle.success,
        emoji="➕",
        row=0
    )
    async def add_item(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if len(self.items) >= MAX_ITEMS:
            await interaction.response.send_message(
                f"❌ Tu peux mettre maximum {MAX_ITEMS} items.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(ItemModal(self))

    @discord.ui.button(
        label="Retirer le dernier item",
        style=discord.ButtonStyle.secondary,
        emoji="➖",
        row=0
    )
    async def remove_last_item(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.items:
            await interaction.response.send_message(
                "❌ Aucun item à retirer.",
                ephemeral=True
            )
            return

        removed = self.items.pop()

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

        await interaction.followup.send(
            f"✅ Dernier item retiré : `{removed['nom']}`",
            ephemeral=True
        )

    @discord.ui.button(
        label="Modifier la note",
        style=discord.ButtonStyle.secondary,
        emoji="📝",
        row=1
    )
    async def edit_note(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(NoteModal(self))

    @discord.ui.button(
        label="Valider la facture",
        style=discord.ButtonStyle.primary,
        emoji="✅",
        row=1
    )
    async def validate_facture(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.items:
            await interaction.response.send_message(
                "❌ Tu dois ajouter au moins 1 item avant de valider.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            result = await asyncio.to_thread(
                create_invoice_xlsx,
                entreprise=self.info["entreprise"],
                adresse_entreprise=self.info["adresse_entreprise"],
                mail_entreprise=self.info["mail_entreprise"],
                destinataire=self.info["destinataire"],
                numero=self.info["numero"],
                items=self.items,
                note=self.note
            )

            items_text = ""

            for item in result["items"]:
                items_text += (
                    f"• **{item['nom']}** — "
                    f"`{item['quantite']} x {item['prix']}€` "
                    f"= `{format_euro(item['total'])}`\n"
                )

            description = (
                "# ✅ Facture générée\n\n"
                "La facture PDF a été générée avec ton template Excel.\n\n"

                "## 📌 Informations\n"
                f"**Entreprise :** {result['entreprise']}\n"
                f"**Destinataire :** {result['destinataire']}\n"
                f"**Téléphone :** {result['numero']}\n"
                f"**Numéro facture :** `{result['numero_facture']}`\n"
                f"**Date :** `{result['date']}`\n\n"

                "## 🍔 Items\n"
                f"{items_text or 'Aucun item.'}\n"

                "## 💰 Total\n"
                f"`{format_euro(result['total'])}`\n\n"

                "## 📝 Note\n"
                f"{result['note']}"
            )

            embed = discord.Embed(
                description=description[:4096],
                color=discord.Color.green()
            )

            embed.set_footer(text="BurgerShot Sud RP • Facturation")

            await interaction.edit_original_response(
                embed=embed,
                view=None
            )

            facture_file = discord.File(
                str(result["pdf_path"]),
                filename=result["pdf_path"].name
            )

            await interaction.followup.send(
                content="📎 Voici ta facture PDF :",
                file=facture_file,
                ephemeral=True
            )

            if self.salon is not None:
                public_file = discord.File(
                    str(result["pdf_path"]),
                    filename=result["pdf_path"].name
                )

                await self.salon.send(
                    content=(
                        f"🧾 Nouvelle facture créée par {interaction.user.mention}\n"
                        f"**Facture :** `{result['numero_facture']}`\n"
                        f"**Destinataire :** `{result['destinataire']}`\n"
                        f"**Total :** `{format_euro(result['total'])}`"
                    ),
                    file=public_file
                )

            await log_action(
                interaction.guild,
                "🧾 Facture PDF générée",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Facture :** `{result['numero_facture']}`\n"
                f"**Destinataire :** `{result['destinataire']}`\n"
                f"**Total :** `{format_euro(result['total'])}`\n"
                f"**Note :** {result['note']}",
                discord.Color.green()
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant la génération de la facture PDF :\n```txt\n{error}\n```",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "❌ Erreur facture PDF",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Erreur :** `{error}`",
                discord.Color.red()
            )

    @discord.ui.button(
        label="Annuler",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        row=1
    )
    async def cancel_facture(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="❌ Création de facture annulée.",
            embed=None,
            view=None
        )


class FacturePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Créer une facture",
        style=discord.ButtonStyle.primary,
        emoji="🧾",
        custom_id="burgershot_facture_create",
        row=0
    )
    async def create_facture(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent créer une facture.",
                ephemeral=True
            )
            return

        output_channel = get_output_channel(interaction.guild)

        await interaction.response.send_modal(
            FactureInfoModal(
                note=None,
                salon=output_channel
            )
        )

    @discord.ui.button(
        label="Liste des factures",
        style=discord.ButtonStyle.secondary,
        emoji="📂",
        custom_id="burgershot_facture_list",
        row=0
    )
    async def list_factures(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent voir la liste des factures.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=build_facture_list_embed(),
            ephemeral=True
        )


class Factures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Boutons persistants même après redémarrage du bot
        self.bot.add_view(FacturePanelView())

    def build_panel_embed(self, output_channel: discord.TextChannel | None = None):
        if output_channel is not None:
            destination = output_channel.mention
        else:
            destination = "La facture sera envoyée uniquement à la personne qui la crée."

        embed = discord.Embed(
            description=(
                "# 🧾 Panel des factures BurgerShot\n\n"
                "Clique sur le bouton ci-dessous pour créer une facture rapidement "
                "ou consulter la liste des factures sauvegardées.\n\n"

                "## 📌 Fonctionnement\n"
                "- Un formulaire s’ouvre pour les informations principales.\n"
                "- Ensuite, tu peux ajouter les items un par un.\n"
                "- Tu peux modifier la note avant de valider.\n"
                "- Le bot génère automatiquement la facture en PDF.\n"
                "- Les factures restent sauvegardées dans le dossier `factures/`.\n\n"

                "## 📤 Destination\n"
                f"{destination}"
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(text="BurgerShot Sud RP • Panel facturation")
        return embed

    @app_commands.command(
        name="facture",
        description="Créer une facture PDF avec le template BurgerShot"
    )
    @app_commands.describe(
        note="Note optionnelle pour la facture",
        salon="Salon où envoyer la facture publiquement"
    )
    async def facture(
        self,
        interaction: discord.Interaction,
        note: str | None = None,
        salon: discord.TextChannel | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent créer une facture.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            FactureInfoModal(
                note=note,
                salon=salon
            )
        )

    @app_commands.command(
        name="panel_factures",
        description="Créer le panel public de création de factures"
    )
    @app_commands.describe(
        salon_panel="Salon où envoyer le panel des factures",
        salon_sortie="Salon où envoyer les factures PDF créées depuis le panel"
    )
    async def panel_factures(
        self,
        interaction: discord.Interaction,
        salon_panel: discord.TextChannel | None = None,
        salon_sortie: discord.TextChannel | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent créer le panel des factures.",
                ephemeral=True
            )
            return

        if salon_panel is None:
            salon_panel = interaction.channel

        panel_data = load_factures_panel()
        guild_id = str(interaction.guild.id)

        old_message_id = panel_data.get(guild_id, {}).get("message_id")
        old_channel_id = panel_data.get(guild_id, {}).get("channel_id")

        old_channel = interaction.guild.get_channel(old_channel_id) if old_channel_id else None

        if old_channel is not None and old_message_id is not None:
            try:
                old_message = await old_channel.fetch_message(old_message_id)
                await old_message.delete()
            except Exception:
                pass

        embed = self.build_panel_embed(output_channel=salon_sortie)

        message = await salon_panel.send(
            embed=embed,
            view=FacturePanelView()
        )

        panel_data[guild_id] = {
            "channel_id": salon_panel.id,
            "message_id": message.id,
            "output_channel_id": salon_sortie.id if salon_sortie else None
        }

        save_factures_panel(panel_data)

        if salon_sortie is not None:
            destination_text = salon_sortie.mention
        else:
            destination_text = "en message privé éphémère"

        await interaction.response.send_message(
            f"✅ Panel des factures créé dans {salon_panel.mention}.\n"
            f"📤 Destination des factures : {destination_text}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🧾 Panel factures créé",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Panel :** {salon_panel.mention}\n"
            f"**Destination :** {destination_text}",
            discord.Color.orange()
        )


async def setup(bot):
    await bot.add_cog(Factures(bot))