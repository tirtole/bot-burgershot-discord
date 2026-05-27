import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    ROLE_PATRON,
    ROLE_MANAGER,
    ROLE_EMPLOYE,
    ROLE_ARRIVANT,
    CHANNEL_ANNONCES,
    CHANNEL_COMMANDES,
    CHANNEL_MENUS,
    CHANNEL_LOGS,
    CHANNEL_SERVICES,
    CATEGORY_TICKETS,
)

from utils.logger import log_action
from utils.permissions import is_staff


HELP_RESET_DELAY = 120  # secondes avant retour automatique à l'accueil


def format_reset_time(seconds: int):
    minutes = seconds // 60
    secondes = seconds % 60

    if minutes > 0:
        return f"{minutes}m {secondes}s"

    return f"{secondes}s"


def get_help_pages():
    return [
        {
            "label": "Accueil",
            "emoji": "🍔",
            "description": (
                "# 🍔 Aide complète — Bot BurgerShot\n\n"
                "Bienvenue sur le bot officiel du **BurgerShot Sud RP**.\n\n"
                "Ce bot sert à gérer l’entreprise BurgerShot sur votre serveur RP FiveM :\n"
                "- commandes clients classiques\n"
                "- commandes avec panier\n"
                "- services employés\n"
                "- menu permanent\n"
                "- tickets\n"
                "- annonces IA\n"
                "- factures PDF\n"
                "- historique des factures\n"
                "- absences employés\n"
                "- blacklist clients\n"
                "- dashboard santé du bot\n"
                "- logs\n"
                "- outils staff et développeur\n\n"
                "___Utilise le menu déroulant ci-dessous pour choisir une page.___\n\n"
                f"Après **{format_reset_time(HELP_RESET_DELAY)} sans interaction**, "
                "le panel revient automatiquement ici."
            )
        },
        {
            "label": "Commandes",
            "emoji": "🧾",
            "description": (
                "## 🧾 Commandes BurgerShot\n\n"

                "`/commande`\n"
                "Ouvre un formulaire pour créer une commande client classique.\n"
                f"La commande est envoyée dans `#{CHANNEL_COMMANDES}` avec un ping `@here`.\n\n"

                "### 📦 Gestion des commandes\n"
                "Sous chaque commande, le bot ajoute des boutons de statut :\n\n"

                "`🔄 En cours`\n"
                "Passe la commande en statut **en cours**.\n\n"

                "`🛵 Attente livraison`\n"
                "Passe la commande en **attente de livraison**.\n\n"

                "`✅ Fini`\n"
                "Marque la commande comme **terminée**.\n\n"

                "Chaque changement de statut est envoyé dans les logs."
            )
        },
        {
            "label": "Panier",
            "emoji": "🧺",
            "description": (
                "## 🧺 Commandes avec panier\n\n"

                "`/panier`\n"
                "Ouvre un panel privé pour créer une commande avec le menu BurgerShot.\n\n"

                "### 📌 Fonctionnement\n"
                "- Tu choisis une catégorie du menu.\n"
                "- Tu choisis ensuite un article.\n"
                "- Un formulaire te demande la quantité.\n"
                "- Le bot calcule automatiquement le total.\n"
                "- Tu peux valider ou annuler la commande.\n\n"

                "### 🔘 Boutons du panier\n"

                "`➖ Retirer dernier item`\n"
                "Retire le dernier article ajouté au panier.\n\n"

                "`✅ Valider la commande`\n"
                f"Envoie la commande dans `#{CHANNEL_COMMANDES}` avec un ping `@here`.\n\n"

                "`❌ Annuler`\n"
                "Annule la création du panier.\n\n"

                "### ⛔ Blacklist\n"
                "Si un client est blacklist, le bot bloque la création de commande panier pour ce client."
            )
        },
        {
            "label": "Services",
            "emoji": "🟢",
            "description": (
                "## 🟢 Services BurgerShot\n\n"

                "`/service`\n"
                "Permet à un employé de prendre son service.\n\n"

                "`/finservice`\n"
                "Permet à un employé de terminer son service.\n"
                "Le bot calcule automatiquement le temps total effectué.\n\n"

                "`/services`\n"
                "Affiche en éphémère la liste actuelle des employés en service.\n\n"

                "`/panel_services`\n"
                f"Crée le panel permanent des services dans `#{CHANNEL_SERVICES}`.\n\n"

                "### 📋 Panel permanent\n"
                "Le panel affiche toujours l’état actuel du service.\n"
                "Quand personne n’est en service, le message est modifié automatiquement.\n"
                "Quand un employé prend son service, le même panel se met à jour.\n\n"

                "### 🔘 Boutons du panel services\n"

                "`🟢 Prendre son service`\n"
                "Prendre son service directement avec un bouton.\n\n"

                "`🔴 Finir son service`\n"
                "Terminer son service directement avec un bouton.\n\n"

                "`🔄 Actualiser`\n"
                "Force l’actualisation du panel en cas de bug."
            )
        },
        {
            "label": "Menu",
            "emoji": "📇",
            "description": (
                "## 📇 Menu BurgerShot\n\n"

                "`/menu afficher`\n"
                "Affiche le menu actuel du BurgerShot en **éphémère**.\n\n"

                "`/menu poster`\n"
                f"Poste ou met à jour l’embed permanent du menu dans `#{CHANNEL_MENUS}`.\n\n"

                "### 🔄 Menu permanent automatique\n"
                "Quand une catégorie, un article, un prix, un nom ou une description est modifié, "
                "l’embed permanent du menu se met à jour automatiquement.\n\n"

                "### 📁 Catégories\n"

                "`/menu categorie_ajouter`\n"
                "Ajoute une nouvelle catégorie au menu.\n\n"

                "`/menu categorie_supprimer`\n"
                "Supprime une catégorie existante avec autocomplete."
            )
        },
        {
            "label": "Articles",
            "emoji": "🍟",
            "description": (
                "## 🍟 Articles du menu\n\n"

                "`/menu article_ajouter`\n"
                "Ajoute un article dans une catégorie avec son prix et une description optionnelle.\n"
                "La description peut servir à mettre les ingrédients nécessaires.\n"
                "Le prix se formate automatiquement en `€`.\n\n"

                "`/menu article_supprimer`\n"
                "Supprime un article existant.\n"
                "Les articles disponibles apparaissent selon la catégorie choisie.\n\n"

                "`/menu article_renommer`\n"
                "Renomme un article sans supprimer son prix ni sa description.\n\n"

                "`/menu prix_modifier`\n"
                "Modifie le prix d’un article.\n"
                "Tu mets seulement le chiffre, le bot ajoute automatiquement `€`.\n\n"

                "`/menu description_modifier`\n"
                "Modifie la description ou la liste des ingrédients d’un article."
            )
        },
        {
            "label": "Tickets",
            "emoji": "🎫",
            "description": (
                "## 🎫 Tickets BurgerShot\n\n"

                "`/panel_ticket`\n"
                "Crée un panel avec un bouton pour ouvrir un ticket.\n\n"

                "### 📝 Formulaire ticket\n"
                "Quand un joueur clique sur le bouton, un formulaire s’ouvre pour demander la raison.\n\n"

                "### 🛎️ Format du salon\n"
                "Le bot crée ensuite un salon privé avec ce format :\n"
                "`🛎️︱pseudo-raison`\n\n"

                "### 📁 Catégorie ticket\n"
                f"Les tickets sont créés dans la catégorie `{CATEGORY_TICKETS}`.\n\n"

                "### 🔒 Fermeture\n"
                "Un bouton permet au staff de fermer le ticket quand la demande est terminée.\n\n"

                "### 🔁 Important\n"
                "Si un ancien panel ticket affiche `Échec de l’interaction`, recrée le panel avec `/panel_ticket`."
            )
        },
        {
            "label": "Annonces",
            "emoji": "📢",
            "description": (
                "## 📢 Annonces BurgerShot\n\n"

                "`/annonce`\n"
                f"Permet aux responsables de faire une annonce BurgerShot dans `#{CHANNEL_ANNONCES}`.\n\n"

                "### 🤖 Annonce avec IA\n"
                "Quand tu mets un petit texte dans `/annonce`, le bot peut utiliser l’IA "
                "pour générer un gros embed propre avec une belle mise en forme Discord.\n\n"

                "### ⚠️ Important\n"
                "La génération IA utilise une clé API OpenAI.\n"
                "Si le compte API n’a plus de crédit, l’annonce IA peut échouer."
            )
        },
        {
            "label": "Factures",
            "emoji": "🧾",
            "description": (
                "## 🧾 Factures BurgerShot\n\n"

                "`/facture`\n"
                "Permet de créer une facture PDF avec le template Excel BurgerShot.\n"
                "Le bot génère d’abord une facture `.xlsx`, puis la convertit automatiquement en `.pdf`.\n\n"

                "`/panel_factures`\n"
                "Crée un panel public avec un bouton **Créer une facture**.\n"
                "Ce panel permet aux managers ou patrons de créer des factures plus rapidement.\n\n"

                "### 📌 Options de `/panel_factures`\n"

                "`salon_panel`\n"
                "Salon où le panel des factures sera envoyé.\n\n"

                "`salon_sortie`\n"
                "Salon où les factures PDF créées depuis le panel seront envoyées.\n"
                "Si aucun salon de sortie n’est choisi, la facture est envoyée uniquement en éphémère "
                "à la personne qui la crée.\n\n"

                "### 📝 Formulaire facture\n"
                "Le premier formulaire demande :\n"
                "- entreprise\n"
                "- adresse entreprise\n"
                "- mail entreprise\n"
                "- destinataire\n"
                "- numéro de téléphone\n\n"

                "### 🍔 Gestion des items\n"
                "Après le formulaire, le bot ouvre un panel privé avec plusieurs boutons :\n\n"

                "`➕ Ajouter un item`\n"
                "Ajoute un article à la facture avec son nom, sa quantité et son prix unitaire.\n\n"

                "`➖ Retirer le dernier item`\n"
                "Retire le dernier item ajouté.\n\n"

                "`📝 Modifier la note`\n"
                "Permet d’ajouter ou modifier la note affichée en bas de la facture.\n\n"

                "`✅ Valider la facture`\n"
                "Génère la facture PDF et l’envoie sur Discord.\n\n"

                "`❌ Annuler`\n"
                "Annule la création de la facture.\n\n"

                "### 💾 Sauvegarde\n"
                "Les fichiers générés restent sauvegardés dans le dossier `factures/` du bot."
            )
        },
        {
            "label": "Historique factures",
            "emoji": "📂",
            "description": (
                "## 📂 Historique des factures\n\n"

                "`/factures liste`\n"
                "Affiche les dernières factures PDF présentes dans le dossier `factures/`.\n\n"

                "`/factures rechercher`\n"
                "Recherche une facture avec son numéro.\n"
                "Exemple : `0016`, `16`, ou `#0016`.\n\n"

                "`/factures renvoyer`\n"
                "Renvoie une facture PDF sauvegardée.\n\n"

                "### 📌 Option de `/factures renvoyer`\n"

                "`salon`\n"
                "Si un salon est donné, la facture est envoyée dans ce salon.\n"
                "Sinon, elle est envoyée uniquement en éphémère à la personne qui lance la commande."
            )
        },
        {
            "label": "Absences",
            "emoji": "📅",
            "description": (
                "## 📅 Absences BurgerShot\n\n"

                "`/absence poser`\n"
                "Permet à un employé de déclarer une absence avec un formulaire.\n\n"

                "`/absence panel`\n"
                "Crée un panel public pour déclarer des absences avec un bouton.\n\n"

                "### 📌 Options de `/absence panel`\n"

                "`salon_panel`\n"
                "Salon où le panel d’absence sera envoyé.\n\n"

                "`salon_validation`\n"
                "Salon où les demandes d’absence seront envoyées pour validation staff.\n\n"

                "### 🔘 Boutons du panel absence\n"

                "`📅 Déclarer une absence`\n"
                "Ouvre un formulaire pour indiquer :\n"
                "- date de début\n"
                "- date de fin\n"
                "- raison\n\n"

                "### ✅ Validation staff\n"
                "Dans le salon de validation, le staff peut utiliser les boutons :\n\n"

                "`✅ Accepter`\n"
                "Accepte l’absence.\n\n"

                "`❌ Refuser`\n"
                "Ouvre un formulaire pour donner la raison du refus.\n\n"

                "### 📢 Réponse publique\n"
                "Quand une absence est acceptée ou refusée, la réponse est aussi postée "
                "dans le salon du panel absence.\n\n"

                "### 📋 Gestion manuelle\n"

                "`/absence liste`\n"
                "Affiche les absences enregistrées.\n\n"

                "`/absence accepter`\n"
                "Accepte une absence avec son ID.\n\n"

                "`/absence refuser`\n"
                "Refuse une absence avec son ID et une raison."
            )
        },
        {
            "label": "Blacklist",
            "emoji": "⛔",
            "description": (
                "## ⛔ Blacklist clients\n\n"

                "`/blacklist ajouter`\n"
                "Ajoute un client à la blacklist avec une raison.\n\n"

                "`/blacklist retirer`\n"
                "Retire un client de la blacklist.\n"
                "L’option utilise un autocomplete avec uniquement les clients actuellement blacklistés.\n\n"

                "`/blacklist voir`\n"
                "Permet de vérifier si un client est blacklist.\n\n"

                "`/blacklist liste`\n"
                "Affiche la liste des clients blacklistés.\n\n"

                "### 📌 Effet de la blacklist\n"
                "Les commandes panier peuvent être bloquées si le client choisi est blacklist."
            )
        },
        {
            "label": "Dashboard",
            "emoji": "📊",
            "description": (
                "## 📊 Dashboard santé du bot\n\n"

                "`/dashboard_bot`\n"
                "Affiche en éphémère l’état du bot.\n\n"

                "`/panel_dashboard`\n"
                "Crée un panel public avec l’état du bot et des boutons de gestion.\n\n"

                "### 📌 Informations affichées\n"
                "- ping du bot\n"
                "- uptime\n"
                "- nombre de serveurs\n"
                "- utilisateurs visibles\n"
                "- cogs chargés\n"
                "- commandes slash\n"
                "- CPU\n"
                "- RAM du bot\n"
                "- RAM système\n\n"

                "### 🔘 Boutons du dashboard\n"

                "`🔄 Actualiser`\n"
                "Actualise les informations du dashboard.\n\n"

                "`♻️ Reload all`\n"
                "Recharge les cogs du bot depuis le panel.\n"
                "Le cog dashboard est ignoré pour éviter que le bouton se casse pendant l’action.\n\n"

                "`🔁 Sync`\n"
                "Synchronise les commandes slash sur le serveur."
            )
        },
        {
            "label": "Staff",
            "emoji": "🛡️",
            "description": (
                "## 🛡️ Commandes staff\n\n"

                "`/clear`\n"
                "Supprime un nombre de messages dans un salon.\n\n"

                "`/say`\n"
                "Permet de faire parler le bot dans un salon.\n\n"

                "### 👥 Autorole\n"
                "Quand une personne rejoint le serveur, le bot lui donne automatiquement "
                f"le rôle `{ROLE_ARRIVANT}`.\n\n"

                "### 📌 Rôles utilisés\n"

                f"`{ROLE_EMPLOYE}`\n"
                "Peut utiliser les commandes de service, commande, panier et absence.\n\n"

                f"`{ROLE_MANAGER}`\n"
                "Peut gérer les menus, annonces, tickets, factures, absences, blacklist et commandes staff.\n\n"

                f"`{ROLE_PATRON}`\n"
                "A accès à toutes les commandes BurgerShot."
            )
        },
        {
            "label": "Développeur",
            "emoji": "🔧",
            "description": (
                "## 🔧 Commandes développeur\n\n"

                "`/dev cogs`\n"
                "Affiche la liste des cogs chargés.\n\n"

                "`/dev utils`\n"
                "Affiche la liste des fichiers utils disponibles.\n\n"

                "`/dev reload`\n"
                "Recharge un cog sans redémarrer le bot.\n\n"

                "`/dev load`\n"
                "Charge un cog.\n\n"

                "`/dev unload`\n"
                "Décharge un cog.\n\n"

                "`/dev reload_utils`\n"
                "Recharge un fichier utils comme `menu_utils`, `logger`, `permissions`, `invoice_xlsx`, etc.\n\n"

                "`/dev reload_all`\n"
                "Recharge tous les utils et tous les cogs.\n\n"

                "`/dev sync`\n"
                "Synchronise les commandes slash sur le serveur.\n\n"

                "### 🔁 Autre méthode\n"
                "Le panel dashboard possède aussi des boutons `Reload all` et `Sync`.\n\n"

                "### 🔁 Quand utiliser `/dev sync` ?\n"
                "Utilise `/dev sync` quand tu ajoutes, supprimes ou renommes une commande slash.\n"
                "Après ça, fais `CTRL + R` dans Discord si les commandes ne s’affichent pas."
            )
        },
        {
            "label": "Salons & Logs",
            "emoji": "📁",
            "description": (
                "## 📁 Salons utilisés\n\n"

                f"`#{CHANNEL_COMMANDES}`\n"
                "Reçoit les commandes clients classiques et les commandes panier.\n\n"

                f"`#{CHANNEL_MENUS}`\n"
                "Reçoit l’embed permanent du menu.\n\n"

                f"`#{CHANNEL_SERVICES}`\n"
                "Reçoit le panel permanent des services.\n\n"

                f"`#{CHANNEL_ANNONCES}`\n"
                "Reçoit les annonces BurgerShot.\n\n"

                f"`#{CHANNEL_LOGS}`\n"
                "Reçoit les logs de toutes les actions importantes.\n\n"

                "### 🧾 Factures\n"
                "Les factures peuvent être envoyées dans un salon choisi avec `/facture salon:` "
                "ou avec `/panel_factures salon_sortie:`.\n\n"

                "### 📅 Absences\n"
                "Les absences utilisent deux salons configurables :\n"
                "- salon du panel absence\n"
                "- salon de validation staff\n\n"
                "Quand une absence est acceptée ou refusée, la réponse est postée dans le salon du panel.\n\n"

                "## 📝 Logs automatiques\n"
                "Le bot log automatiquement :\n"
                "- les commandes créées\n"
                "- les commandes panier\n"
                "- les changements de statut des commandes\n"
                "- les prises de service\n"
                "- les fins de service\n"
                "- les actualisations du panel service\n"
                "- les modifications du menu\n"
                "- les annonces\n"
                "- les tickets\n"
                "- les factures PDF générées\n"
                "- les panels de factures créés\n"
                "- les absences déposées, acceptées ou refusées\n"
                "- les clients blacklistés ou retirés de blacklist\n"
                "- les panels dashboard\n"
                "- les autoroles\n"
                "- les actions staff\n"
                "- les reloads développeur\n\n"

                "### 🕒 Date et heure\n"
                "Les logs affichent la date et l’heure dans le footer."
            )
        }
    ]


def build_help_embed(page_index: int = 0, reset_remaining: int | None = None):
    pages = get_help_pages()

    if page_index < 0 or page_index >= len(pages):
        page_index = 0

    page = pages[page_index]

    embed = discord.Embed(
        description=page["description"],
        color=discord.Color.red()
    )

    footer = f"BurgerShot Sud RP • Bot entreprise • Page {page_index + 1}/{len(pages)}"

    if reset_remaining is not None and page_index != 0:
        footer += f" • Retour accueil dans {format_reset_time(reset_remaining)}"

    embed.set_footer(text=footer)

    return embed


async def reset_panel_to_home(message: discord.Message, selected_index: int):
    try:
        remaining = HELP_RESET_DELAY

        while remaining > 0:
            await asyncio.sleep(10)
            remaining -= 10

            if remaining <= 0:
                break

            await message.edit(
                embed=build_help_embed(
                    selected_index,
                    reset_remaining=remaining
                ),
                view=HelpPanelView(selected_index=selected_index)
            )

        await message.edit(
            embed=build_help_embed(0),
            view=HelpPanelView(selected_index=0)
        )

        HelpPanelView.cancel_reset(message)

    except asyncio.CancelledError:
        pass

    except discord.NotFound:
        pass

    except discord.Forbidden:
        print("[HELP] Permissions insuffisantes pour réinitialiser le panel help.")

    except discord.HTTPException as error:
        print(f"[HELP] Erreur pendant la réinitialisation du panel help : {error}")


class HelpSelect(discord.ui.Select):
    def __init__(self, selected_index: int = 0):
        pages = get_help_pages()
        options = []

        for index, page in enumerate(pages):
            options.append(
                discord.SelectOption(
                    label=page["label"],
                    value=str(index),
                    emoji=page["emoji"],
                    description=f"Afficher la page {page['label']}"[:100],
                    default=index == selected_index
                )
            )

        super().__init__(
            placeholder="Choisis une page d’aide...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="burgershot_help_select"
        )

    async def callback(self, interaction: discord.Interaction):
        page_index = int(self.values[0])

        await interaction.response.edit_message(
            embed=build_help_embed(
                page_index,
                reset_remaining=HELP_RESET_DELAY if page_index != 0 else None
            ),
            view=HelpPanelView(selected_index=page_index)
        )

        if page_index == 0:
            HelpPanelView.cancel_reset(interaction.message)
        else:
            HelpPanelView.schedule_reset(
                interaction.message,
                selected_index=page_index
            )


class HelpPanelView(discord.ui.View):
    reset_tasks = {}

    def __init__(self, selected_index: int = 0):
        super().__init__(timeout=None)
        self.add_item(HelpSelect(selected_index=selected_index))

    @classmethod
    def cancel_reset(cls, message: discord.Message):
        if message is None:
            return

        old_task = cls.reset_tasks.get(message.id)

        if old_task is not None and not old_task.done():
            old_task.cancel()

        cls.reset_tasks.pop(message.id, None)

    @classmethod
    def schedule_reset(cls, message: discord.Message, selected_index: int):
        if message is None:
            return

        old_task = cls.reset_tasks.get(message.id)

        if old_task is not None and not old_task.done():
            old_task.cancel()

        task = asyncio.create_task(
            reset_panel_to_home(message, selected_index)
        )

        cls.reset_tasks[message.id] = task


class HelpButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.pages = get_help_pages()
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.pages) - 1

    @discord.ui.button(label="Précédent", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()

        await interaction.response.edit_message(
            embed=build_help_embed(self.current_page),
            view=self
        )

    @discord.ui.button(label="Suivant", style=discord.ButtonStyle.secondary, emoji="➡️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()

        await interaction.response.edit_message(
            embed=build_help_embed(self.current_page),
            view=self
        )

    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger, emoji="❌")
    async def close_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ Menu d’aide fermé.",
            embed=None,
            view=None
        )


class Aide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Permet au menu déroulant du panel public de continuer à fonctionner après redémarrage.
        self.bot.add_view(HelpPanelView(selected_index=0))

    @app_commands.command(name="help", description="Afficher l'aide complète du bot BurgerShot")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=build_help_embed(0),
            view=HelpButtonView(),
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📖 Commande help utilisée",
            f"{interaction.user.mention} a utilisé la commande `/help`.",
            discord.Color.blurple()
        )

    @app_commands.command(name="panel_help", description="Créer un panel d'aide public BurgerShot")
    async def panel_help(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent créer le panel d’aide.",
                ephemeral=True
            )
            return

        if salon is None:
            salon = interaction.channel

        message = await salon.send(
            embed=build_help_embed(0),
            view=HelpPanelView(selected_index=0)
        )

        HelpPanelView.cancel_reset(message)

        await interaction.response.send_message(
            f"✅ Panel d’aide créé dans {salon.mention}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📖 Panel help créé",
            f"{interaction.user.mention} a créé un panel d’aide public dans {salon.mention}.",
            discord.Color.blurple()
        )


async def setup(bot):
    await bot.add_cog(Aide(bot))