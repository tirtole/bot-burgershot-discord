import asyncio
import re

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    ROLE_PATRON,
    ROLE_MANAGER,
    ROLE_EMPLOYE,
    CHANNEL_COMMANDES
)entreprise

from utils.menu_utils import load_menu
from utils.logger import log_action
from utils.client_blacklist import is_user_blacklisted, get_blacklist_entry
from utils.permissions import is_staff
from utils.invoice_xlsx import create_invoice_xlsx, format_euro, MAX_ITEMS


def has_burgershot_role(member: discord.Member):
    allowed_roles = {ROLE_PATRON, ROLE_MANAGER, ROLE_EMPLOYE}
    return any(role.name in allowed_roles for role in member.roles)


def clean_price(value):
    value = str(value)
    value = value.replace("€", "")
    value = value.replace("$", "")
    value = value.replace(" ", "")
    value = value.replace(",", ".")

    try:
        number = float(value)

        if number.is_integer():
            return int(number)

        return number

    except Exception:
        return 0


def format_select_item_description(article: dict):
    prix = article.get("prix", "0€")
    description = article.get("description", "")

    if description:
        text = f"{prix} • {description}"
    else:
        text = f"Prix : {prix}"

    if len(text) > 100:
        text = text[:97] + "..."

    return text


def get_commandes_channel(guild: discord.Guild):
    return discord.utils.get(
        guild.text_channels,
        name=CHANNEL_COMMANDES
    )


def extract_client_id_from_embed(embed: discord.Embed):
    footer_text = ""

    try:
        footer_text = embed.footer.text or ""
    except Exception:
        footer_text = ""

    footer_match = re.search(r"Client ID\s*:\s*(\d+)", footer_text)

    if footer_match:
        return int(footer_match.group(1))

    description = embed.description or ""
    lines = description.split("\n")

    for index, line in enumerate(lines):
        if line.strip() == "## 👤 Client":
            for next_line in lines[index + 1:index + 8]:
                match = re.search(r"<@!?(\d+)>", next_line)

                if match:
                    return int(match.group(1))

    match = re.search(r"<@!?(\d+)>", description)

    if match:
        return int(match.group(1))

    return None

def build_status_dm_embed(status: str, order_message: discord.Message):
    embed = discord.Embed(
        description=(
            "# 🍔 Mise à jour de ta commande BurgerShot\n\n"

            "## 📌 Nouveau statut\n"
            f"`{status}`\n\n"

            "## 📦 Information\n"
            "Ta commande a été mise à jour par un employé BurgerShot.\n"
            "Tu recevras un nouveau message privé si le statut change encore."
        ),
        color=discord.Color.orange()
    )

    embed.set_footer(text="BurgerShot Sud RP • Suivi commande")
    return embed

def build_order_embed(
    client_text,
    staff_text,
    items_text,
    total_text,
    invoice_number=None,
    invoice_info=None,
    client_id=None,
    status="Nouvelle commande",
    status_user=None,
    color=discord.Color.orange()
):
    status_line = f"`{status}`"

    if status_user:
        status_line += f"\nModifié par {status_user}"

    invoice_text = "Facture en cours de génération."

    if invoice_number:
        invoice_text = f"Facture générée : `{invoice_number}`\nPDF joint à cette commande."

    invoice_details = ""

    if invoice_info:
        invoice_details = (
            "\n\n"
            "## 📋 Informations facture\n"
            f"**Entreprise :** {invoice_info.get('entreprise', 'Non renseigné')}\n"
            f"**Adresse :** {invoice_info.get('adresse_entreprise', 'Non renseignée')}\n"
            f"**Mail :** {invoice_info.get('mail_entreprise', 'Non renseigné')}\n"
            f"**Destinataire :** {invoice_info.get('destinataire', 'Non renseigné')}\n"
            f"**Téléphone :** {invoice_info.get('numero', 'Non renseigné')}"
        )

    embed = discord.Embed(
        description=(
            "# 🧾 Nouvelle commande panier\n\n"

            "## 📌 Statut\n"
            f"{status_line}\n\n"

            "## 👤 Client\n"
            f"{client_text}\n\n"

            "## 👨‍🍳 Créée par\n"
            f"{staff_text}\n\n"

            "## 🍔 Articles\n"
            f"{items_text}\n\n"

            "## 💰 Total\n"
            f"`{total_text}`\n\n"

            "## 🧾 Facture\n"
            f"{invoice_text}"
            f"{invoice_details}"
        ),
        color=color
    )

    if client_id:
        embed.set_footer(
            text=f"BurgerShot Sud RP • Commande panier + facture • Client ID: {client_id}"
        )
    else:
        embed.set_footer(text="BurgerShot Sud RP • Commande panier + facture")

    return embed


class OrderStatusView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_status(
        self,
        interaction: discord.Interaction,
        status: str,
        color: discord.Color
    ):
        if not has_burgershot_role(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les employés BurgerShot peuvent modifier le statut.",
                ephemeral=True
            )
            return

        if not interaction.message.embeds:
            await interaction.response.send_message(
                "❌ Embed introuvable.",
                ephemeral=True
            )
            return

        old_embed = interaction.message.embeds[0]
        client_id = extract_client_id_from_embed(old_embed)

        description = old_embed.description or ""

        lines = description.split("\n")
        new_lines = []
        skip_status_lines = False

        for line in lines:
            if line.strip() == "## 📌 Statut":
                new_lines.append(line)
                new_lines.append(f"`{status}`")
                new_lines.append(f"Modifié par {interaction.user.mention}")
                skip_status_lines = True
                continue

            if skip_status_lines:
                if line.startswith("`") or line.startswith("Modifié par"):
                    continue

                skip_status_lines = False

            new_lines.append(line)

        old_embed.description = "\n".join(new_lines)
        old_embed.color = color

        await interaction.response.edit_message(
            embed=old_embed,
            view=self
        )

        mp_status = "Non envoyé"

        if client_id is not None:
            try:
                user = interaction.guild.get_member(client_id)

                if user is None:
                    user = await interaction.client.fetch_user(client_id)

                await user.send(
                    embed=build_status_dm_embed(
                        status=status,
                        order_message=interaction.message
                    )
                )

                mp_status = "Envoyé"

            except discord.Forbidden:
                mp_status = "MP fermés"

            except Exception as error:
                mp_status = f"Erreur : {error}"

        else:
            mp_status = "Client introuvable"

        await interaction.followup.send(
            f"📩 Statut modifié : `{status}`\n"
            f"**MP client :** `{mp_status}`",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📦 Statut commande panier modifié",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Statut :** `{status}`\n"
            f"**Client ID :** `{client_id if client_id else 'Introuvable'}`\n"
            f"**MP client :** `{mp_status}`\n"
            f"**Message :** {interaction.message.jump_url}",
            color
        )

    @discord.ui.button(
        label="En cours",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
        custom_id="panier_status_en_cours"
    )
    async def en_cours(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.update_status(
            interaction,
            "En cours",
            discord.Color.blurple()
        )

    @discord.ui.button(
        label="Attente livraison",
        emoji="🛵",
        style=discord.ButtonStyle.secondary,
        custom_id="panier_status_livraison"
    )
    async def livraison(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.update_status(
            interaction,
            "Attente livraison",
            discord.Color.gold()
        )

    @discord.ui.button(
        label="Fini",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="panier_status_fini"
    )
    async def fini(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await self.update_status(
            interaction,
            "Fini",
            discord.Color.green()
        )


class PanierInvoiceInfoModal(discord.ui.Modal, title="Informations pour la facture"):
    entreprise = discord.ui.TextInput(
        label="Entreprise",
        placeholder="Exemple : BurgerShot, BS, LTD...",
        required=True,
        max_length=100
    )

    adresse_entreprise = discord.ui.TextInput(
        label="Adresse",
        placeholder="Exemple : Avenue Felix Faure, Paris",
        required=True,
        max_length=150
    )

    mail_entreprise = discord.ui.TextInput(
        label="Mail / contact",
        placeholder="Exemple : contact@burgershot.fr",
        required=True,
        max_length=120
    )

    destinataire = discord.ui.TextInput(
        label="Destinataire / payable à",
        placeholder="Exemple : John Smith",
        required=True,
        max_length=100
    )

    numero = discord.ui.TextInput(
        label="Téléphone",
        placeholder="Exemple : 075010017",
        required=True,
        max_length=50
    )

    def __init__(
        self,
        client: discord.Member | discord.User | None = None,
        public_order: bool = False
    ):
        super().__init__()
        self.client = client
        self.public_order = public_order

        if client is not None:
            self.destinataire.default = client.display_name

    async def on_submit(self, interaction: discord.Interaction):
        invoice_info = {
            "entreprise": self.entreprise.value,
            "adresse_entreprise": self.adresse_entreprise.value,
            "mail_entreprise": self.mail_entreprise.value,
            "destinataire": self.destinataire.value,
            "numero": self.numero.value,
        }

        view = PanierView(
            author_id=interaction.user.id,
            client=self.client or interaction.user,
            public_order=self.public_order,
            invoice_info=invoice_info
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
            ephemeral=True
        )


class QuantityModal(discord.ui.Modal, title="Ajouter au panier"):
    quantite = discord.ui.TextInput(
        label="Quantité",
        placeholder="Exemple : 2",
        required=True,
        max_length=5
    )

    def __init__(self, panier_view, item: dict):
        super().__init__()
        self.panier_view = panier_view
        self.item = item

    async def on_submit(self, interaction: discord.Interaction):
        if len(self.panier_view.items) >= MAX_ITEMS:
            await interaction.response.send_message(
                f"❌ Tu peux ajouter maximum {MAX_ITEMS} articles par facture.",
                ephemeral=True
            )
            return

        try:
            quantite = int(str(self.quantite.value).strip())
        except Exception:
            await interaction.response.send_message(
                "❌ Quantité invalide.",
                ephemeral=True
            )
            return

        if quantite <= 0:
            await interaction.response.send_message(
                "❌ La quantité doit être supérieure à 0.",
                ephemeral=True
            )
            return

        prix = clean_price(self.item.get("prix", "0"))

        self.panier_view.items.append({
            "nom": self.item.get("nom", "Article"),
            "prix": prix,
            "quantite": quantite,
            "total": prix * quantite
        })

        await interaction.response.edit_message(
            embed=self.panier_view.build_embed(),
            view=self.panier_view
        )


class CategorySelect(discord.ui.Select):
    def __init__(self, panier_view):
        self.panier_view = panier_view
        menu = load_menu()

        options = []

        for categorie in menu.keys():
            options.append(
                discord.SelectOption(
                    label=categorie[:100],
                    value=categorie[:100],
                    emoji="📁",
                    default=categorie == panier_view.selected_category
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="Aucune catégorie",
                    value="none",
                    emoji="❌"
                )
            )

        if panier_view.selected_category:
            placeholder = f"Catégorie sélectionnée : {panier_view.selected_category}"
        else:
            placeholder = "Choisis une catégorie..."

        super().__init__(
            placeholder=placeholder[:150],
            min_values=1,
            max_values=1,
            options=options[:25],
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        categorie = self.values[0]

        if categorie == "none":
            await interaction.response.send_message(
                "❌ Aucune catégorie dans le menu.",
                ephemeral=True
            )
            return

        self.panier_view.selected_category = categorie
        self.panier_view.refresh_items()

        await interaction.response.edit_message(
            embed=self.panier_view.build_embed(),
            view=self.panier_view
        )


class ItemSelect(discord.ui.Select):
    def __init__(self, panier_view):
        self.panier_view = panier_view
        menu = load_menu()
        categorie = panier_view.selected_category
        articles = menu.get(categorie, [])

        options = []

        for index, article in enumerate(articles):
            nom = article.get("nom", "Article")

            options.append(
                discord.SelectOption(
                    label=nom[:100],
                    description=format_select_item_description(article),
                    value=str(index),
                    emoji="🍔"
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="Aucun article",
                    value="none",
                    description="Aucun article disponible dans cette catégorie.",
                    emoji="❌"
                )
            )

        if panier_view.selected_category:
            placeholder = f"Choisis un article dans {panier_view.selected_category}..."
        else:
            placeholder = "Choisis un article..."

        super().__init__(
            placeholder=placeholder[:150],
            min_values=1,
            max_values=1,
            options=options[:25],
            row=1
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "❌ Aucun article dans cette catégorie.",
                ephemeral=True
            )
            return

        index = int(self.values[0])
        menu = load_menu()
        article = menu[self.panier_view.selected_category][index]

        await interaction.response.send_modal(
            QuantityModal(self.panier_view, article)
        )


class PanierView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        client: discord.Member | discord.User | None = None,
        public_order: bool = False,
        invoice_info: dict | None = None
    ):
        super().__init__(timeout=600)
        self.author_id = author_id
        self.client = client
        self.public_order = public_order
        self.invoice_info = invoice_info or {}
        self.items = []
        self.selected_category = None

        self.refresh_items()

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Ce panier ne t’appartient pas.",
                ephemeral=True
            )
            return False

        return True

    def refresh_items(self):
        self.clear_items()

        self.add_item(CategorySelect(self))

        if self.selected_category:
            self.add_item(ItemSelect(self))

        self.add_item(self.remove_last_item)
        self.add_item(self.validate_order)
        self.add_item(self.cancel_order)

    def calculate_total(self):
        return sum(item["total"] for item in self.items)

    def build_items_text(self):
        if not self.items:
            return "Aucun article ajouté."

        text = ""

        for item in self.items:
            text += (
                f"• **{item['nom']}** — "
                f"`{item['quantite']} x {format_euro(item['prix'])}` "
                f"= `{format_euro(item['total'])}`\n"
            )

        return text

    def build_invoice_text(self):
        if not self.invoice_info:
            return "Informations facture non renseignées."

        return (
            f"**Entreprise :** {self.invoice_info.get('entreprise', 'Non renseigné')}\n"
            f"**Adresse :** {self.invoice_info.get('adresse_entreprise', 'Non renseignée')}\n"
            f"**Mail :** {self.invoice_info.get('mail_entreprise', 'Non renseigné')}\n"
            f"**Destinataire :** {self.invoice_info.get('destinataire', 'Non renseigné')}\n"
            f"**Téléphone :** {self.invoice_info.get('numero', 'Non renseigné')}"
        )

    def build_embed(self):
        if self.client:
            client_text = self.client.mention
        else:
            client_text = self.invoice_info.get("entreprise", "Non renseigné")

        if self.public_order:
            title = "# 🧺 Votre commande BurgerShot"
            subtitle = "Choisis tes articles tranquillement, puis valide ta commande."
        else:
            title = "# 🧺 Panier BurgerShot"
            subtitle = "Choisis une catégorie, puis un article à ajouter au panier."

        embed = discord.Embed(
            description=(
                f"{title}\n\n"
                f"{subtitle}\n\n"

                "## 👤 Client\n"
                f"{client_text}\n\n"

                "## 🧾 Informations facture\n"
                f"{self.build_invoice_text()}\n\n"

                "## 🍔 Articles\n"
                f"{self.build_items_text()}\n\n"

                "## 💰 Total actuel\n"
                f"`{format_euro(self.calculate_total())}`\n\n"

                "## 📦 Limite\n"
                f"`{len(self.items)}/{MAX_ITEMS}` articles ajoutés"
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(text="BurgerShot Sud RP • Panier commande + facture")
        return embed

    def get_invoice_items(self):
        invoice_items = []

        for item in self.items:
            invoice_items.append({
                "nom": item["nom"],
                "quantite": item["quantite"],
                "prix": item["prix"]
            })

        return invoice_items

    @discord.ui.button(
        label="Retirer dernier item",
        emoji="➖",
        style=discord.ButtonStyle.secondary,
        row=3
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
        label="Valider commande + facture",
        emoji="✅",
        style=discord.ButtonStyle.success,
        row=3
    )
    async def validate_order(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not self.items:
            await interaction.response.send_message(
                "❌ Tu dois ajouter au moins un article.",
                ephemeral=True
            )
            return

        if not self.invoice_info:
            await interaction.response.send_message(
                "❌ Les informations de facture sont manquantes.",
                ephemeral=True
            )
            return

        if self.client and is_user_blacklisted(interaction.guild.id, self.client.id):
            entry = get_blacklist_entry(interaction.guild.id, self.client.id)

            await interaction.response.send_message(
                f"❌ Tu ne peux pas passer commande.\n"
                f"**Raison :** {entry.get('reason', 'Aucune raison.')}",
                ephemeral=True
            )
            return

        channel = get_commandes_channel(interaction.guild)

        if channel is None:
            await interaction.response.send_message(
                f"❌ Salon `{CHANNEL_COMMANDES}` introuvable.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            result = await asyncio.to_thread(
                create_invoice_xlsx,
                entreprise=self.invoice_info["entreprise"],
                adresse_entreprise=self.invoice_info["adresse_entreprise"],
                mail_entreprise=self.invoice_info["mail_entreprise"],
                destinataire=self.invoice_info["destinataire"],
                numero=self.invoice_info["numero"],
                items=self.get_invoice_items(),
                note="Commande générée automatiquement depuis le panel panier BurgerShot."
            )

            if self.client:
                client_text = self.client.mention
                client_id = self.client.id
            else:
                client_text = self.invoice_info.get("entreprise", interaction.user.mention)
                client_id = interaction.user.id

            total_text = format_euro(self.calculate_total())

            if self.public_order:
                staff_text = "Commande passée par le client via le panel public"
            else:
                staff_text = interaction.user.mention

            embed = build_order_embed(
                client_text=client_text,
                staff_text=staff_text,
                items_text=self.build_items_text(),
                total_text=total_text,
                invoice_number=result["numero_facture"],
                invoice_info=self.invoice_info,
                client_id=client_id,
                status="Nouvelle commande",
                color=discord.Color.orange()
            )

            facture_file = discord.File(
                str(result["pdf_path"]),
                filename=result["pdf_path"].name
            )

            message = await channel.send(
                content="@here Nouvelle commande BurgerShot avec facture !",
                embed=embed,
                file=facture_file,
                view=OrderStatusView()
            )

            user_file = discord.File(
                str(result["pdf_path"]),
                filename=result["pdf_path"].name
            )

            await interaction.edit_original_response(
                content=(
                    "✅ Ta commande a bien été envoyée au BurgerShot !\n"
                    "🧾 La facture PDF a aussi été générée.\n"
                    "Un employé va prendre ta commande en charge dès que possible."
                    if self.public_order
                    else f"✅ Commande envoyée dans {channel.mention} avec facture PDF."
                ),
                embed=None,
                view=None
            )

            await interaction.followup.send(
                content="📎 Voici ta facture PDF :",
                file=user_file,
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "🧺 Commande panier + facture créée",
                f"**Créée par :** {interaction.user.mention}\n"
                f"**Client :** {client_text}\n"
                f"**Client ID :** `{client_id}`\n"
                f"**Type :** {'Panel public client' if self.public_order else 'Commande staff'}\n"
                f"**Facture :** `{result['numero_facture']}`\n"
                f"**Total :** `{format_euro(result['total'])}`\n"
                f"**Message :** {message.jump_url}",
                discord.Color.orange()
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant la génération de la commande/facture :\n```txt\n{error}\n```",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "❌ Erreur commande panier + facture",
                f"**Utilisateur :** {interaction.user.mention}\n"
                f"**Erreur :** `{error}`",
                discord.Color.red()
            )

    @discord.ui.button(
        label="Annuler",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        row=3
    )
    async def cancel_order(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="❌ Panier annulé.",
            embed=None,
            view=None
        )


class PublicPanierPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Passer commande",
        emoji="🧺",
        style=discord.ButtonStyle.success,
        custom_id="burgershot_public_panier_create"
    )
    async def create_public_order(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if is_user_blacklisted(interaction.guild.id, interaction.user.id):
            entry = get_blacklist_entry(interaction.guild.id, interaction.user.id)

            await interaction.response.send_message(
                f"❌ Tu ne peux pas passer commande.\n"
                f"**Raison :** {entry.get('reason', 'Aucune raison.')}",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            PanierInvoiceInfoModal(
                client=interaction.user,
                public_order=True
            )
        )


class PanierCommandes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.add_view(OrderStatusView())
        self.bot.add_view(PublicPanierPanelView())

    def build_public_panel_embed(self):
        embed = discord.Embed(
            description=(
                "# 🧺 Commander au BurgerShot\n\n"
                "Clique sur le bouton ci-dessous pour passer ta commande tranquillement.\n\n"

                "## 📌 Fonctionnement\n"
                "- Remplis les informations nécessaires pour la facture.\n"
                "- Choisis une catégorie du menu.\n"
                "- Choisis tes articles.\n"
                "- La composition des articles est visible dans la sélection.\n"
                "- Indique les quantités.\n"
                "- Valide ta commande.\n\n"

                "## 🧾 Facture automatique\n"
                "À la validation, le bot génère automatiquement une facture PDF.\n"
                "La facture est envoyée avec la commande et reste sauvegardée dans le dossier `factures/`.\n\n"

                "## 🔔 Suivi de commande\n"
                "Quand un employé change le statut de ta commande, tu reçois un message privé.\n\n"

                "## 📦 Après validation\n"
                f"Ta commande sera envoyée dans `#{CHANNEL_COMMANDES}` et un employé la prendra en charge.\n\n"

                "## ⛔ Attention\n"
                "Les abus peuvent entraîner une blacklist client."
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(text="BurgerShot Sud RP • Panel commande client + facture")
        return embed

    @app_commands.command(
        name="panier",
        description="Créer une commande avec un panier et une facture"
    )
    async def panier(
        self,
        interaction: discord.Interaction,
        client: discord.Member | None = None
    ):
        if not has_burgershot_role(interaction.user):
            await interaction.response.send_message(
                "❌ Cette commande est réservée aux employés BurgerShot.\n"
                "Pour passer commande, utilise le panel public de commande.",
                ephemeral=True
            )
            return

        if client and is_user_blacklisted(interaction.guild.id, client.id):
            entry = get_blacklist_entry(interaction.guild.id, client.id)

            await interaction.response.send_message(
                f"❌ Ce client est blacklist.\n"
                f"**Raison :** {entry.get('reason', 'Aucune raison.')}",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            PanierInvoiceInfoModal(
                client=client or interaction.user,
                public_order=False
            )
        )

    @app_commands.command(
        name="panel_panier",
        description="Créer le panel public de commande panier"
    )
    @app_commands.describe(
        salon="Salon où envoyer le panel public de commande"
    )
    async def panel_panier(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel | None = None
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            if not is_staff(interaction.user):
                await interaction.followup.send(
                    "❌ Seuls les managers ou patrons peuvent créer le panel panier.",
                    ephemeral=True
                )
                return

            if salon is None:
                salon = interaction.channel

            await salon.send(
                embed=self.build_public_panel_embed(),
                view=PublicPanierPanelView()
            )

            await interaction.followup.send(
                f"✅ Panel panier créé dans {salon.mention}.",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "🧺 Panel panier public créé",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Salon :** {salon.mention}",
                discord.Color.orange()
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant la création du panel panier :\n```txt\n{error}\n```",
                ephemeral=True
            )

            try:
                await log_action(
                    interaction.guild,
                    "❌ Erreur panel panier",
                    f"**Staff :** {interaction.user.mention}\n"
                    f"**Erreur :** `{error}`",
                    discord.Color.red()
                )
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(PanierCommandes(bot))
