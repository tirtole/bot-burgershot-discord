import re
import discord
from discord import app_commands
from discord.ext import commands

from config import CATEGORY_TICKETS, ROLE_PATRON, ROLE_MANAGER
from utils.logger import log_action
from utils.permissions import is_staff


def slugify_channel_name(text: str):
    text = text.lower()
    text = re.sub(r"[^a-z0-9À-ÿ-]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")
    return text[:40] or "ticket"


def get_ticket_category(guild: discord.Guild):
    category = discord.utils.get(guild.categories, name=CATEGORY_TICKETS)

    if category is None:
        return None

    return category


def get_staff_roles(guild: discord.Guild):
    roles = []

    for role_name in [ROLE_PATRON, ROLE_MANAGER]:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            roles.append(role)

    return roles


class TicketReasonModal(discord.ui.Modal, title="Ouvrir un ticket BurgerShot"):
    raison = discord.ui.TextInput(
        label="Raison du ticket",
        placeholder="Explique rapidement la raison du ticket...",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild

        category = get_ticket_category(guild)

        if category is None:
            await interaction.response.send_message(
                f"❌ Catégorie `{CATEGORY_TICKETS}` introuvable.",
                ephemeral=True
            )
            return

        nickname = interaction.user.display_name
        reason_slug = slugify_channel_name(self.raison.value)
        nickname_slug = slugify_channel_name(nickname)

        channel_name = f"🛎️︱{nickname_slug}-{reason_slug}"[:90]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            )
        }

        for role in get_staff_roles(guild):
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket ouvert par {interaction.user}"
        )

        embed = discord.Embed(
            description=(
                "# 🎫 Ticket BurgerShot\n\n"
                "## 👤 Auteur\n"
                f"{interaction.user.mention}\n\n"
                "## 📝 Raison\n"
                f"{self.raison.value}\n\n"
                "Un membre du staff va te répondre dès que possible."
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(text="BurgerShot Sud RP • Ticket")

        await channel.send(
            content=f"{interaction.user.mention}",
            embed=embed,
            view=TicketCloseView()
        )

        await interaction.response.send_message(
            f"✅ Ticket créé : {channel.mention}",
            ephemeral=True
        )

        await log_action(
            guild,
            "🎫 Ticket ouvert",
            f"**Auteur :** {interaction.user.mention}\n"
            f"**Salon :** {channel.mention}\n"
            f"**Raison :** {self.raison.value}",
            discord.Color.orange()
        )


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Ouvrir un ticket",
        emoji="🎫",
        style=discord.ButtonStyle.success,
        custom_id="burgershot_ticket_open"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketReasonModal())


class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fermer le ticket",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="burgershot_ticket_close"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent fermer un ticket.",
                ephemeral=True
            )
            return

        channel = interaction.channel

        await interaction.response.send_message(
            "🔒 Fermeture du ticket dans 5 secondes...",
            ephemeral=False
        )

        await log_action(
            interaction.guild,
            "🔒 Ticket fermé",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Salon :** `{channel.name}`",
            discord.Color.red()
        )

        await channel.delete(reason=f"Ticket fermé par {interaction.user}")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketCloseView())

    @app_commands.command(name="panel_ticket", description="Créer le panel de ticket BurgerShot")
    async def panel_ticket(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent créer le panel ticket.",
                ephemeral=True
            )
            return

        if salon is None:
            salon = interaction.channel

        embed = discord.Embed(
            description=(
                "# 🎫 Support BurgerShot\n\n"
                "Clique sur le bouton ci-dessous pour ouvrir un ticket.\n\n"
                "Un formulaire s’ouvrira pour demander la raison de ta demande."
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(text="BurgerShot Sud RP • Support")

        await salon.send(
            embed=embed,
            view=TicketPanelView()
        )

        await interaction.response.send_message(
            f"✅ Panel ticket créé dans {salon.mention}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🎫 Panel ticket créé",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Salon :** {salon.mention}",
            discord.Color.orange()
        )


async def setup(bot):
    await bot.add_cog(Tickets(bot))