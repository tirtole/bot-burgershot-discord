import discord
from discord import app_commands
from discord.ext import commands

from config import ROLE_MANAGER, ROLE_PATRON, CHANNEL_ANNONCES
from utils.logger import log_action
from utils.ai_annonce import generate_announcement


def is_manager(member: discord.Member):
    return any(role.name in [ROLE_MANAGER, ROLE_PATRON] for role in member.roles)


class Annonces(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="annonce",
        description="Créer une belle annonce BurgerShot avec l'IA"
    )
    async def annonce(self, interaction: discord.Interaction, message: str):
        if not is_manager(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent faire une annonce.",
                ephemeral=True
            )
            return

        channel = discord.utils.get(
            interaction.guild.text_channels,
            name=CHANNEL_ANNONCES
        )

        if channel is None:
            await interaction.response.send_message(
                f"❌ Salon `{CHANNEL_ANNONCES}` introuvable.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            ai_data = await generate_announcement(message)

            embed = discord.Embed(
                title=ai_data.get("title", "🍔 Annonce BurgerShot"),
                description=ai_data.get("description", message),
                color=discord.Color.red()
            )

            fields = ai_data.get("fields", [])

            for field in fields[:8]:
                name = str(field.get("name", "## Information"))[:256]
                value = str(field.get("value", "Aucun détail."))[:1024]
                inline = bool(field.get("inline", False))

                embed.add_field(
                    name=name,
                    value=value,
                    inline=inline
                )

            embed.set_footer(
                text=ai_data.get("footer", "BurgerShot Sud RP")
            )

            embed.set_author(
                name=f"Annonce par {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            await channel.send(embed=embed)

            await interaction.followup.send(
                f"✅ Annonce IA envoyée dans {channel.mention}.",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "📢 Annonce IA envoyée",
                f"**Auteur :** {interaction.user.mention}\n"
                f"**Salon :** {channel.mention}\n"
                f"**Message original :** {message}",
                discord.Color.red()
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant la génération IA : `{error}`",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "❌ Erreur annonce IA",
                f"**Auteur :** {interaction.user.mention}\n"
                f"**Erreur :** `{error}`\n"
                f"**Message original :** {message}",
                discord.Color.red()
            )


async def setup(bot):
    await bot.add_cog(Annonces(bot))