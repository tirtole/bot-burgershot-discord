import discord
from discord import app_commands
from discord.ext import commands
from config import ROLE_MANAGER, ROLE_PATRON

def can_moderate(member: discord.Member):
    return any(role.name in [ROLE_MANAGER, ROLE_PATRON] for role in member.roles)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="clear", description="Supprimer des messages")
    async def clear(self, interaction: discord.Interaction, nombre: int):
        if not can_moderate(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        if nombre < 1 or nombre > 100:
            await interaction.response.send_message(
                "❌ Choisis un nombre entre 1 et 100.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=nombre)

        await interaction.followup.send(
            f"✅ {len(deleted)} messages supprimés.",
            ephemeral=True
        )

    @app_commands.command(name="say", description="Faire parler le bot")
    async def say(self, interaction: discord.Interaction, message: str):
        if not can_moderate(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.channel.send(message)
        await interaction.response.send_message("✅ Message envoyé.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))