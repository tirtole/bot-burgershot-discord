import discord
from discord.ext import commands
import asyncio
from config import TOKEN, GUILD_ID
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class BurgerShotBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents
        )
    async def setup_hook(self):
        extensions = [
            "cogs.burgershot_commandes",
            "cogs.burgershot_services",
            "cogs.burgershot_menu",
            "cogs.tickets",
            "cogs.annonces",
            "cogs.moderation",
            "cogs.aide",
            "cogs.autorole",
            "cogs.dev_reload",
            "cogs.factures",
            "cogs.facture_history",
            "cogs.panier_commandes",
            "cogs.absences",
            "cogs.blacklist_clients",
            "cogs.dashboard_bot"
        ]

        for extension in extensions:
            await self.load_extension(extension)

        guild = discord.Object(id=GUILD_ID)

        self.tree.copy_global_to(guild=guild)
        synced_guild = await self.tree.sync(guild=guild)
        print(f"{len(synced_guild)} commandes synchronisées sur le serveur.")

        self.tree.clear_commands(guild=None)
        synced_global = await self.tree.sync()
        print(f"{len(synced_global)} commandes globales restantes.")
    async def on_ready(self):
        print(f"Connecté en tant que {self.user}")
        await self.change_presence(
            activity=discord.Game(name="BurgerShot RP FiveM")
        )

bot = BurgerShotBot()

keep_alive()

async def main():
    async with bot:
        await bot.start(TOKEN)


asyncio.run(main())
