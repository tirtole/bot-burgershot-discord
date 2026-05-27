import discord
from discord.ext import commands

from config import ROLE_ARRIVANT
from utils.logger import log_action


class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild

        role = discord.utils.get(guild.roles, name=ROLE_ARRIVANT)

        if role is None:
            print(f"[AUTOROLE] Rôle introuvable : {ROLE_ARRIVANT}")

            await log_action(
                guild,
                "❌ Autorole impossible",
                f"Le rôle `{ROLE_ARRIVANT}` est introuvable pour {member.mention}.",
                discord.Color.red()
            )
            return

        try:
            await member.add_roles(
                role,
                reason="Autorole BurgerShot à l'arrivée sur le serveur"
            )

            await log_action(
                guild,
                "✅ Autorole ajouté",
                f"{member.mention} a rejoint le serveur et a reçu le rôle {role.mention}.",
                discord.Color.green()
            )

        except discord.Forbidden:
            print("[AUTOROLE] Permission insuffisante pour donner le rôle.")

            await log_action(
                guild,
                "❌ Autorole refusé",
                f"Impossible de donner le rôle {role.mention} à {member.mention}.\n"
                f"Vérifie que le rôle du bot est au-dessus du rôle `{ROLE_ARRIVANT}`.",
                discord.Color.red()
            )

        except discord.HTTPException as error:
            print(f"[AUTOROLE] Erreur Discord : {error}")

            await log_action(
                guild,
                "❌ Erreur autorole",
                f"Erreur pendant l'ajout du rôle {role.mention} à {member.mention}.\n"
                f"Erreur : `{error}`",
                discord.Color.red()
            )


async def setup(bot):
    await bot.add_cog(AutoRole(bot))