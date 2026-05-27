import discord
from datetime import datetime

from config import CHANNEL_LOGS


async def log_action(
    guild: discord.Guild,
    title: str,
    description: str,
    color=discord.Color.blurple()
):
    try:
        if guild is None:
            print("[LOGS] Guild introuvable.")
            return

        channel = discord.utils.get(guild.text_channels, name=CHANNEL_LOGS)

        if channel is None:
            print(f"[LOGS] Salon introuvable : {CHANNEL_LOGS}")
            return

        now = datetime.now()
        date_heure = now.strftime("%d/%m/%Y à %H:%M:%S")

        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )

        embed.set_footer(text=f"Logs BurgerShot • {date_heure}")

        await channel.send(embed=embed)

    except Exception as error:
        print(f"[LOGS] Erreur pendant l'envoi d'un log : {error}")