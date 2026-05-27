from pathlib import Path
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from config import ROLE_PATRON, ROLE_MANAGER, ROLE_EMPLOYE
from utils.storage import load_json, save_json
from utils.logger import log_action
from utils.permissions import is_staff


ABSENCES_FILE = Path("data/absences.json")
ABSENCES_PANEL_FILE = Path("data/absences_panel.json")


def load_absences():
    return load_json(ABSENCES_FILE, {})


def save_absences(data):
    save_json(ABSENCES_FILE, data)


def load_absences_panel():
    return load_json(ABSENCES_PANEL_FILE, {})


def save_absences_panel(data):
    save_json(ABSENCES_PANEL_FILE, data)


def can_use_absence(member: discord.Member):
    allowed = {ROLE_PATRON, ROLE_MANAGER, ROLE_EMPLOYE}
    return any(role.name in allowed for role in member.roles)


def get_next_absence_id(guild_data):
    counter = guild_data.get("_counter", 0) + 1
    guild_data["_counter"] = counter
    return f"A{counter:04d}"


def get_review_channel(guild: discord.Guild):
    panel_data = load_absences_panel()
    guild_id = str(guild.id)

    if guild_id not in panel_data:
        return None

    channel_id = panel_data[guild_id].get("review_channel_id")

    if channel_id is None:
        return None

    return guild.get_channel(channel_id)


def get_panel_channel(guild: discord.Guild):
    panel_data = load_absences_panel()
    guild_id = str(guild.id)

    if guild_id not in panel_data:
        return None

    channel_id = panel_data[guild_id].get("panel_channel_id")

    if channel_id is None:
        return None

    return guild.get_channel(channel_id)


def build_absence_embed(guild: discord.Guild, absence_id: str, absence: dict):
    user_id = absence.get("user_id")
    status = absence.get("status", "En attente")

    if status == "Acceptée":
        color = discord.Color.green()
        status_emoji = "✅"
    elif status == "Refusée":
        color = discord.Color.red()
        status_emoji = "❌"
    else:
        color = discord.Color.orange()
        status_emoji = "⏳"

    reviewed_by = absence.get("reviewed_by")
    reviewed_text = f"<@{reviewed_by}>" if reviewed_by else "Pas encore traité"

    refus_reason = absence.get("refus_reason")
    refus_text = ""

    if refus_reason:
        refus_text = (
            "\n\n"
            "## 📝 Raison du refus\n"
            f"{refus_reason}"
        )

    embed = discord.Embed(
        description=(
            "# 📅 Demande d’absence BurgerShot\n\n"

            "## 📌 Statut\n"
            f"{status_emoji} `{status}`\n\n"

            "## 👤 Employé\n"
            f"<@{user_id}>\n\n"

            "## 🗓️ Dates\n"
            f"**Début :** `{absence.get('date_debut')}`\n"
            f"**Fin :** `{absence.get('date_fin')}`\n\n"

            "## 📝 Raison\n"
            f"{absence.get('raison')}\n\n"

            "## 🛡️ Traitée par\n"
            f"{reviewed_text}"
            f"{refus_text}"
        ),
        color=color
    )

    embed.set_footer(
        text=f"BurgerShot Sud RP • Absence {absence_id} • {absence.get('created_at', '')}"
    )

    return embed


def build_absence_result_embed(guild: discord.Guild, absence_id: str, absence: dict):
    status = absence.get("status", "En attente")

    if status == "Acceptée":
        color = discord.Color.green()
        title = "# ✅ Absence acceptée"
        result_text = "Ta demande d’absence a été acceptée."
    elif status == "Refusée":
        color = discord.Color.red()
        title = "# ❌ Absence refusée"
        result_text = "Ta demande d’absence a été refusée."
    else:
        color = discord.Color.orange()
        title = "# ⏳ Absence en attente"
        result_text = "Ta demande d’absence est en attente."

    reviewed_by = absence.get("reviewed_by")
    reviewed_text = f"<@{reviewed_by}>" if reviewed_by else "Non renseigné"

    refus_reason = absence.get("refus_reason")
    refus_text = ""

    if refus_reason:
        refus_text = (
            "\n\n"
            "## 📝 Raison du refus\n"
            f"{refus_reason}"
        )

    embed = discord.Embed(
        description=(
            f"{title}\n\n"
            f"{result_text}\n\n"

            "## 👤 Employé\n"
            f"<@{absence.get('user_id')}>\n\n"

            "## 🗓️ Dates\n"
            f"**Début :** `{absence.get('date_debut')}`\n"
            f"**Fin :** `{absence.get('date_fin')}`\n\n"

            "## 📝 Raison de la demande\n"
            f"{absence.get('raison')}\n\n"

            "## 🛡️ Réponse donnée par\n"
            f"{reviewed_text}"
            f"{refus_text}"
        ),
        color=color
    )

    embed.set_footer(
        text=f"BurgerShot Sud RP • Réponse absence {absence_id} • {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    return embed


async def send_absence_result_to_panel(guild: discord.Guild, absence_id: str, absence: dict):
    panel_channel = get_panel_channel(guild)

    if panel_channel is None:
        return

    try:
        await panel_channel.send(
            content=f"📢 Réponse pour l’absence de <@{absence.get('user_id')}>",
            embed=build_absence_result_embed(guild, absence_id, absence)
        )
    except Exception as error:
        print(f"[ABSENCES] Impossible d'envoyer la réponse dans le salon panel : {error}")


def save_absence_message(guild_id: int, absence_id: str, channel_id: int, message_id: int):
    data = load_absences()
    guild_key = str(guild_id)

    if guild_key in data and absence_id in data[guild_key]:
        data[guild_key][absence_id]["review_channel_id"] = channel_id
        data[guild_key][absence_id]["review_message_id"] = message_id
        save_absences(data)


async def update_absence_message(interaction: discord.Interaction, absence_id: str):
    data = load_absences()
    guild_key = str(interaction.guild.id)
    absence = data.get(guild_key, {}).get(absence_id)

    if not absence:
        return

    channel_id = absence.get("review_channel_id")
    message_id = absence.get("review_message_id")

    if not channel_id or not message_id:
        return

    channel = interaction.guild.get_channel(channel_id)

    if channel is None:
        return

    try:
        message = await channel.fetch_message(message_id)
        await message.edit(
            embed=build_absence_embed(interaction.guild, absence_id, absence),
            view=AbsenceReviewView(absence_id)
        )
    except Exception:
        pass


class RefuseAbsenceModal(discord.ui.Modal, title="Refuser une absence"):
    raison = discord.ui.TextInput(
        label="Raison du refus",
        placeholder="Exemple : période déjà complète, manque d'effectif...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    def __init__(self, absence_id: str):
        super().__init__()
        self.absence_id = absence_id

    async def on_submit(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        data = load_absences()
        guild_key = str(interaction.guild.id)

        if guild_key not in data or self.absence_id not in data[guild_key]:
            await interaction.response.send_message(
                "❌ Absence introuvable.",
                ephemeral=True
            )
            return

        absence = data[guild_key][self.absence_id]
        absence["status"] = "Refusée"
        absence["reviewed_by"] = interaction.user.id
        absence["refus_reason"] = self.raison.value
        save_absences(data)

        await interaction.response.edit_message(
            embed=build_absence_embed(interaction.guild, self.absence_id, absence),
            view=AbsenceReviewView(self.absence_id)
        )

        await send_absence_result_to_panel(
            interaction.guild,
            self.absence_id,
            absence
        )

        await log_action(
            interaction.guild,
            "❌ Absence refusée",
            f"**Staff :** {interaction.user.mention}\n"
            f"**ID :** `{self.absence_id}`\n"
            f"**Employé :** <@{absence.get('user_id')}>\n"
            f"**Raison :** {self.raison.value}",
            discord.Color.red()
        )


class AbsenceReviewView(discord.ui.View):
    def __init__(self, absence_id: str):
        super().__init__(timeout=None)
        self.absence_id = absence_id

    @discord.ui.button(
        label="Accepter",
        emoji="✅",
        style=discord.ButtonStyle.success
    )
    async def accept_absence(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        data = load_absences()
        guild_key = str(interaction.guild.id)

        if guild_key not in data or self.absence_id not in data[guild_key]:
            await interaction.response.send_message(
                "❌ Absence introuvable.",
                ephemeral=True
            )
            return

        absence = data[guild_key][self.absence_id]
        absence["status"] = "Acceptée"
        absence["reviewed_by"] = interaction.user.id
        absence["refus_reason"] = None
        save_absences(data)

        await interaction.response.edit_message(
            embed=build_absence_embed(interaction.guild, self.absence_id, absence),
            view=AbsenceReviewView(self.absence_id)
        )

        await send_absence_result_to_panel(
            interaction.guild,
            self.absence_id,
            absence
        )

        await log_action(
            interaction.guild,
            "✅ Absence acceptée",
            f"**Staff :** {interaction.user.mention}\n"
            f"**ID :** `{self.absence_id}`\n"
            f"**Employé :** <@{absence.get('user_id')}>",
            discord.Color.green()
        )

    @discord.ui.button(
        label="Refuser",
        emoji="❌",
        style=discord.ButtonStyle.danger
    )
    async def refuse_absence(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            RefuseAbsenceModal(self.absence_id)
        )


class AbsenceModal(discord.ui.Modal, title="Déclarer une absence"):
    date_debut = discord.ui.TextInput(
        label="Date de début",
        placeholder="Exemple : 25/05/2026",
        required=True,
        max_length=20
    )

    date_fin = discord.ui.TextInput(
        label="Date de fin",
        placeholder="Exemple : 28/05/2026",
        required=True,
        max_length=20
    )

    raison = discord.ui.TextInput(
        label="Raison",
        placeholder="Exemple : Vacances, problème personnel, indisponibilité...",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        data = load_absences()
        guild_id = str(interaction.guild.id)

        if guild_id not in data:
            data[guild_id] = {}

        absence_id = get_next_absence_id(data[guild_id])

        data[guild_id][absence_id] = {
            "user_id": interaction.user.id,
            "date_debut": self.date_debut.value,
            "date_fin": self.date_fin.value,
            "raison": self.raison.value,
            "status": "En attente",
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "reviewed_by": None,
            "refus_reason": None
        }

        save_absences(data)

        review_channel = get_review_channel(interaction.guild)

        if review_channel is not None:
            message = await review_channel.send(
                content=f"📅 Nouvelle demande d’absence de {interaction.user.mention}",
                embed=build_absence_embed(
                    interaction.guild,
                    absence_id,
                    data[guild_id][absence_id]
                ),
                view=AbsenceReviewView(absence_id)
            )

            save_absence_message(
                interaction.guild.id,
                absence_id,
                review_channel.id,
                message.id
            )

        await interaction.response.send_message(
            f"✅ Absence envoyée avec l’identifiant `{absence_id}`.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📅 Absence déposée",
            f"**Employé :** {interaction.user.mention}\n"
            f"**ID :** `{absence_id}`\n"
            f"**Début :** `{self.date_debut.value}`\n"
            f"**Fin :** `{self.date_fin.value}`\n"
            f"**Raison :** {self.raison.value}\n"
            f"**Salon validation :** {review_channel.mention if review_channel else 'Non configuré'}",
            discord.Color.orange()
        )


class AbsencePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Déclarer une absence",
        emoji="📅",
        style=discord.ButtonStyle.primary,
        custom_id="burgershot_absence_create"
    )
    async def create_absence(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not can_use_absence(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission de poser une absence.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(AbsenceModal())


class Absences(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(AbsencePanelView())

    absence_group = app_commands.Group(
        name="absence",
        description="Gestion des absences BurgerShot"
    )

    def build_panel_embed(self, review_channel: discord.TextChannel | None = None):
        if review_channel:
            destination = review_channel.mention
        else:
            destination = "Aucun salon de validation configuré."

        embed = discord.Embed(
            description=(
                "# 📅 Panel des absences BurgerShot\n\n"
                "Clique sur le bouton ci-dessous pour déclarer une absence.\n\n"

                "## 📌 Fonctionnement\n"
                "- L’employé remplit un formulaire.\n"
                "- La demande est envoyée dans le salon de validation.\n"
                "- Le staff peut accepter ou refuser avec les boutons.\n"
                "- La réponse est ensuite postée ici, dans le salon du panel.\n\n"

                "## 📤 Salon de validation\n"
                f"{destination}"
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(text="BurgerShot Sud RP • Panel absences")
        return embed

    @absence_group.command(
        name="poser",
        description="Déclarer une absence"
    )
    async def absence_poser(self, interaction: discord.Interaction):
        if not can_use_absence(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(AbsenceModal())

    @absence_group.command(
        name="panel",
        description="Créer le panel public des absences"
    )
    async def absence_panel(
        self,
        interaction: discord.Interaction,
        salon_panel: discord.TextChannel | None = None,
        salon_validation: discord.TextChannel | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        if salon_panel is None:
            salon_panel = interaction.channel

        panel_data = load_absences_panel()
        guild_id = str(interaction.guild.id)

        panel_data[guild_id] = {
            "panel_channel_id": salon_panel.id,
            "review_channel_id": salon_validation.id if salon_validation else None
        }

        save_absences_panel(panel_data)

        await salon_panel.send(
            embed=self.build_panel_embed(salon_validation),
            view=AbsencePanelView()
        )

        await interaction.response.send_message(
            f"✅ Panel absences créé dans {salon_panel.mention}.\n"
            f"📤 Validation : {salon_validation.mention if salon_validation else 'non configurée'}.\n"
            f"📢 Les réponses seront postées dans {salon_panel.mention}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📅 Panel absences créé",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Panel :** {salon_panel.mention}\n"
            f"**Validation :** {salon_validation.mention if salon_validation else 'Non configurée'}",
            discord.Color.orange()
        )

    @absence_group.command(
        name="liste",
        description="Afficher les absences"
    )
    async def absence_liste(
        self,
        interaction: discord.Interaction,
        statut: str | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        data = load_absences()
        guild_data = data.get(str(interaction.guild.id), {})

        absences = []

        for absence_id, absence in guild_data.items():
            if absence_id == "_counter":
                continue

            if statut and absence.get("status", "").lower() != statut.lower():
                continue

            absences.append((absence_id, absence))

        if not absences:
            await interaction.response.send_message(
                "✅ Aucune absence trouvée.",
                ephemeral=True
            )
            return

        text = ""

        for absence_id, absence in absences[-15:]:
            text += (
                f"### `{absence_id}` — {absence.get('status', 'Inconnu')}\n"
                f"**Employé :** <@{absence.get('user_id')}>\n"
                f"**Début :** `{absence.get('date_debut')}`\n"
                f"**Fin :** `{absence.get('date_fin')}`\n"
                f"**Raison :** {absence.get('raison')}\n\n"
            )

        embed = discord.Embed(
            description=f"# 📅 Absences BurgerShot\n\n{text}",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @absence_group.command(
        name="accepter",
        description="Accepter une absence"
    )
    async def absence_accepter(
        self,
        interaction: discord.Interaction,
        absence_id: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        data = load_absences()
        guild_data = data.get(str(interaction.guild.id), {})

        if absence_id not in guild_data:
            await interaction.response.send_message(
                "❌ Absence introuvable.",
                ephemeral=True
            )
            return

        absence = guild_data[absence_id]
        absence["status"] = "Acceptée"
        absence["reviewed_by"] = interaction.user.id
        absence["refus_reason"] = None
        save_absences(data)

        await interaction.response.send_message(
            f"✅ Absence `{absence_id}` acceptée.",
            ephemeral=True
        )

        await update_absence_message(interaction, absence_id)

        await send_absence_result_to_panel(
            interaction.guild,
            absence_id,
            absence
        )

        await log_action(
            interaction.guild,
            "✅ Absence acceptée",
            f"**Staff :** {interaction.user.mention}\n"
            f"**ID :** `{absence_id}`\n"
            f"**Employé :** <@{absence.get('user_id')}>",
            discord.Color.green()
        )

    @absence_group.command(
        name="refuser",
        description="Refuser une absence"
    )
    async def absence_refuser(
        self,
        interaction: discord.Interaction,
        absence_id: str,
        raison: str = "Aucune raison."
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        data = load_absences()
        guild_data = data.get(str(interaction.guild.id), {})

        if absence_id not in guild_data:
            await interaction.response.send_message(
                "❌ Absence introuvable.",
                ephemeral=True
            )
            return

        absence = guild_data[absence_id]
        absence["status"] = "Refusée"
        absence["reviewed_by"] = interaction.user.id
        absence["refus_reason"] = raison
        save_absences(data)

        await interaction.response.send_message(
            f"✅ Absence `{absence_id}` refusée.",
            ephemeral=True
        )

        await update_absence_message(interaction, absence_id)

        await send_absence_result_to_panel(
            interaction.guild,
            absence_id,
            absence
        )

        await log_action(
            interaction.guild,
            "❌ Absence refusée",
            f"**Staff :** {interaction.user.mention}\n"
            f"**ID :** `{absence_id}`\n"
            f"**Employé :** <@{absence.get('user_id')}>\n"
            f"**Raison :** {raison}",
            discord.Color.red()
        )


async def setup(bot):
    await bot.add_cog(Absences(bot))