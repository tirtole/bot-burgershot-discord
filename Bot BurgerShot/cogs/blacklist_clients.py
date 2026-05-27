import discord
from discord import app_commands
from discord.ext import commands

from utils.client_blacklist import (
    blacklist_user,
    unblacklist_user,
    get_blacklist_entry,
    get_guild_blacklist
)
from utils.logger import log_action
from utils.permissions import is_staff


async def blacklist_remove_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    if interaction.guild is None:
        return []

    blacklist = get_guild_blacklist(interaction.guild.id)
    choices = []

    current = current.lower()

    for user_id, entry in blacklist.items():
        member = interaction.guild.get_member(int(user_id))

        if member is not None:
            display_name = member.display_name
            choice_name = f"{display_name} • {entry.get('reason', 'Aucune raison.')}"
        else:
            display_name = f"Utilisateur inconnu"
            choice_name = f"{display_name} ({user_id}) • {entry.get('reason', 'Aucune raison.')}"

        search_text = f"{display_name} {user_id} {entry.get('reason', '')}".lower()

        if current and current not in search_text:
            continue

        choices.append(
            app_commands.Choice(
                name=choice_name[:100],
                value=str(user_id)
            )
        )

        if len(choices) >= 25:
            break

    return choices


class BlacklistClients(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    blacklist_group = app_commands.Group(
        name="blacklist",
        description="Gestion de la blacklist client BurgerShot"
    )

    @blacklist_group.command(
        name="ajouter",
        description="Ajouter un client à la blacklist"
    )
    async def blacklist_ajouter(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.User,
        raison: str = "Aucune raison."
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        blacklist_user(
            interaction.guild.id,
            utilisateur.id,
            raison,
            interaction.user.id
        )

        await interaction.response.send_message(
            f"✅ {utilisateur.mention} a été ajouté à la blacklist.\n"
            f"**Raison :** {raison}",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "⛔ Client blacklisté",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Client :** {utilisateur.mention}\n"
            f"**Raison :** {raison}",
            discord.Color.red()
        )

    @blacklist_group.command(
        name="retirer",
        description="Retirer un client de la blacklist"
    )
    @app_commands.autocomplete(utilisateur=blacklist_remove_autocomplete)
    async def blacklist_retirer(
        self,
        interaction: discord.Interaction,
        utilisateur: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        try:
            user_id = int(utilisateur)
        except ValueError:
            await interaction.response.send_message(
                "❌ Utilisateur invalide.",
                ephemeral=True
            )
            return

        entry = get_blacklist_entry(interaction.guild.id, user_id)

        if not entry:
            await interaction.response.send_message(
                "❌ Ce client n’est pas blacklist.",
                ephemeral=True
            )
            return

        removed = unblacklist_user(interaction.guild.id, user_id)

        if not removed:
            await interaction.response.send_message(
                "❌ Impossible de retirer ce client de la blacklist.",
                ephemeral=True
            )
            return

        member = interaction.guild.get_member(user_id)

        if member is not None:
            client_text = member.mention
        else:
            client_text = f"`{user_id}`"

        await interaction.response.send_message(
            f"✅ {client_text} a été retiré de la blacklist.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "✅ Client retiré de la blacklist",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Client :** {client_text}\n"
            f"**Ancienne raison :** {entry.get('reason', 'Aucune raison.')}",
            discord.Color.green()
        )

    @blacklist_group.command(
        name="voir",
        description="Voir si un client est blacklist"
    )
    async def blacklist_voir(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.User
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        entry = get_blacklist_entry(interaction.guild.id, utilisateur.id)

        if not entry:
            await interaction.response.send_message(
                f"✅ {utilisateur.mention} n’est pas blacklist.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            description=(
                "# ⛔ Client blacklisté\n\n"
                f"**Client :** {utilisateur.mention}\n"
                f"**Raison :** {entry.get('reason', 'Aucune raison.')}\n"
                f"**Date :** `{entry.get('date', 'Inconnue')}`\n"
                f"**Staff ID :** `{entry.get('staff_id', 'Inconnu')}`"
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @blacklist_group.command(
        name="liste",
        description="Afficher la liste des clients blacklist"
    )
    async def blacklist_liste(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        blacklist = get_guild_blacklist(interaction.guild.id)

        if not blacklist:
            await interaction.response.send_message(
                "✅ Aucun client blacklist.",
                ephemeral=True
            )
            return

        text = ""

        for user_id, entry in list(blacklist.items())[:25]:
            member = interaction.guild.get_member(int(user_id))

            if member is not None:
                client_text = member.mention
            else:
                client_text = f"`{user_id}`"

            text += (
                f"### {client_text}\n"
                f"**Raison :** {entry.get('reason', 'Aucune raison.')}\n"
                f"**Date :** `{entry.get('date', 'Inconnue')}`\n\n"
            )

        embed = discord.Embed(
            description=f"# ⛔ Blacklist clients\n\n{text}",
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(BlacklistClients(bot))