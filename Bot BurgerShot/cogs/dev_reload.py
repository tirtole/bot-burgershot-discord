import sys
import importlib
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID
from utils.permissions import is_staff
from utils.logger import log_action


COG_ALIASES = {
    "menu": "cogs.burgershot_menu",
    "burgershot_menu": "cogs.burgershot_menu",

    "services": "cogs.burgershot_services",
    "burgershot_services": "cogs.burgershot_services",

    "commandes": "cogs.burgershot_commandes",
    "burgershot_commandes": "cogs.burgershot_commandes",

    "tickets": "cogs.tickets",
    "annonces": "cogs.annonces",
    "moderation": "cogs.moderation",
    "aide": "cogs.aide",
    "help": "cogs.aide",
    "autorole": "cogs.autorole",
    "dev": "cogs.dev_reload",
    "dev_reload": "cogs.dev_reload",
}


UTIL_ALIASES = {
    "logger": "utils.logger",
    "permissions": "utils.permissions",
    "storage": "utils.storage",
    "menu_utils": "utils.menu_utils",
    "ai_annonce": "utils.ai_annonce",
}


def get_available_cogs(bot: commands.Bot):
    cogs = set()

    for extension in bot.extensions.keys():
        cogs.add(extension)

    cogs_folder = Path("cogs")
    if cogs_folder.exists():
        for file in cogs_folder.glob("*.py"):
            if file.name.startswith("__"):
                continue

            cogs.add(f"cogs.{file.stem}")
            cogs.add(file.stem)

    for alias in COG_ALIASES.keys():
        cogs.add(alias)

    return sorted(cogs)


def get_available_utils():
    utils = set()

    utils_folder = Path("utils")
    if utils_folder.exists():
        for file in utils_folder.glob("*.py"):
            if file.name.startswith("__"):
                continue

            utils.add(f"utils.{file.stem}")
            utils.add(file.stem)

    for alias in UTIL_ALIASES.keys():
        utils.add(alias)

    return sorted(utils)


async def cog_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    available_cogs = get_available_cogs(interaction.client)
    choices = []

    for cog in available_cogs:
        if current.lower() in cog.lower():
            choices.append(
                app_commands.Choice(
                    name=cog[:100],
                    value=cog[:100]
                )
            )

    return choices[:25]


async def util_autocomplete(
    interaction: discord.Interaction,
    current: str
):
    available_utils = get_available_utils()
    choices = []

    for util in available_utils:
        if current.lower() in util.lower():
            choices.append(
                app_commands.Choice(
                    name=util[:100],
                    value=util[:100]
                )
            )

    return choices[:25]


class DevReload(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    dev_group = app_commands.Group(
        name="dev",
        description="Commandes développeur du bot"
    )

    def resolve_cog_name(self, name: str):
        name = name.strip()

        if name in COG_ALIASES:
            return COG_ALIASES[name]

        if name.startswith("cogs."):
            return name

        return f"cogs.{name}"

    def resolve_util_name(self, name: str):
        name = name.strip()

        if name in UTIL_ALIASES:
            return UTIL_ALIASES[name]

        if name.startswith("utils."):
            return name

        return f"utils.{name}"

    def reload_python_module(self, module_name: str):
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        else:
            importlib.import_module(module_name)

    async def reload_all_cogs_after_utils(self):
        reloaded = []
        failed = []

        for extension in list(self.bot.extensions.keys()):
            if extension == "cogs.dev_reload":
                continue

            try:
                await self.bot.reload_extension(extension)
                reloaded.append(extension)
            except Exception as error:
                failed.append({
                    "extension": extension,
                    "error": str(error)
                })

        return reloaded, failed

    @dev_group.command(name="cogs", description="Afficher tous les cogs chargés")
    async def list_cogs(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        loaded = sorted(self.bot.extensions.keys())

        description = "\n".join(f"• `{cog}`" for cog in loaded)

        embed = discord.Embed(
            title="🧩 Cogs chargés",
            description=description or "Aucun cog chargé.",
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dev_group.command(name="utils", description="Afficher tous les utils disponibles")
    async def list_utils(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        utils = get_available_utils()
        description = "\n".join(f"• `{util}`" for util in utils)

        embed = discord.Embed(
            title="🔧 Utils disponibles",
            description=description or "Aucun utils trouvé.",
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @dev_group.command(name="reload", description="Recharger un cog sans redémarrer le bot")
    @app_commands.autocomplete(cog=cog_autocomplete)
    async def reload_cog(
        self,
        interaction: discord.Interaction,
        cog: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        extension = self.resolve_cog_name(cog)

        await interaction.response.defer(ephemeral=True)

        try:
            await self.bot.reload_extension(extension)

            await interaction.followup.send(
                f"✅ Cog rechargé : `{extension}`",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "🔄 Cog rechargé",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Cog :** `{extension}`",
                discord.Color.blurple()
            )

        except commands.ExtensionNotLoaded:
            await interaction.followup.send(
                f"❌ Le cog `{extension}` n’est pas chargé.",
                ephemeral=True
            )

        except commands.ExtensionNotFound:
            await interaction.followup.send(
                f"❌ Le cog `{extension}` est introuvable.",
                ephemeral=True
            )

        except commands.ExtensionFailed as error:
            await interaction.followup.send(
                f"❌ Erreur dans le cog `{extension}` :\n```py\n{error}\n```",
                ephemeral=True
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur inconnue :\n```py\n{error}\n```",
                ephemeral=True
            )

    @dev_group.command(name="load", description="Charger un cog")
    @app_commands.autocomplete(cog=cog_autocomplete)
    async def load_cog(
        self,
        interaction: discord.Interaction,
        cog: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        extension = self.resolve_cog_name(cog)

        await interaction.response.defer(ephemeral=True)

        try:
            await self.bot.load_extension(extension)

            await interaction.followup.send(
                f"✅ Cog chargé : `{extension}`",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "➕ Cog chargé",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Cog :** `{extension}`",
                discord.Color.green()
            )

        except commands.ExtensionAlreadyLoaded:
            await interaction.followup.send(
                f"❌ Le cog `{extension}` est déjà chargé.",
                ephemeral=True
            )

        except commands.ExtensionNotFound:
            await interaction.followup.send(
                f"❌ Le cog `{extension}` est introuvable.",
                ephemeral=True
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Impossible de charger `{extension}` :\n```py\n{error}\n```",
                ephemeral=True
            )

    @dev_group.command(name="unload", description="Décharger un cog")
    @app_commands.autocomplete(cog=cog_autocomplete)
    async def unload_cog(
        self,
        interaction: discord.Interaction,
        cog: str
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        extension = self.resolve_cog_name(cog)

        if extension == "cogs.dev_reload":
            await interaction.response.send_message(
                "❌ Tu ne peux pas décharger le cog dev depuis lui-même.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await self.bot.unload_extension(extension)

            await interaction.followup.send(
                f"✅ Cog déchargé : `{extension}`",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "➖ Cog déchargé",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Cog :** `{extension}`",
                discord.Color.red()
            )

        except commands.ExtensionNotLoaded:
            await interaction.followup.send(
                f"❌ Le cog `{extension}` n’est pas chargé.",
                ephemeral=True
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Impossible de décharger `{extension}` :\n```py\n{error}\n```",
                ephemeral=True
            )

    @dev_group.command(name="reload_utils", description="Recharger un fichier utils")
    @app_commands.autocomplete(util=util_autocomplete)
    async def reload_utils(
        self,
        interaction: discord.Interaction,
        util: str,
        reload_cogs: bool = True
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        module_name = self.resolve_util_name(util)

        try:
            self.reload_python_module(module_name)

            reloaded_cogs = []
            failed_cogs = []

            if reload_cogs:
                reloaded_cogs, failed_cogs = await self.reload_all_cogs_after_utils()

            message = f"✅ Utils rechargé : `{module_name}`"

            if reload_cogs:
                message += f"\n✅ `{len(reloaded_cogs)}` cogs rechargés pour appliquer les changements."

            if failed_cogs:
                message += f"\n⚠️ `{len(failed_cogs)}` cog(s) n’ont pas pu être rechargés."

            await interaction.followup.send(
                message,
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "🔧 Utils rechargé",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Utils :** `{module_name}`\n"
                f"**Cogs rechargés :** `{len(reloaded_cogs)}`\n"
                f"**Cogs en erreur :** `{len(failed_cogs)}`",
                discord.Color.blurple()
            )

        except ModuleNotFoundError:
            await interaction.followup.send(
                f"❌ Utils introuvable : `{module_name}`",
                ephemeral=True
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant le reload de `{module_name}` :\n```py\n{error}\n```",
                ephemeral=True
            )

    @dev_group.command(name="reload_all", description="Recharger tous les utils et tous les cogs")
    async def reload_all(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            reloaded_utils = []
            failed_utils = []

            unique_utils = set()

            for util in get_available_utils():
                module_name = self.resolve_util_name(util)
                unique_utils.add(module_name)

            for module_name in sorted(unique_utils):
                try:
                    self.reload_python_module(module_name)
                    reloaded_utils.append(module_name)
                except Exception as error:
                    failed_utils.append({
                        "module": module_name,
                        "error": str(error)
                    })

            reloaded_cogs, failed_cogs = await self.reload_all_cogs_after_utils()

            message = (
                f"✅ `{len(reloaded_utils)}` utils rechargés.\n"
                f"✅ `{len(reloaded_cogs)}` cogs rechargés."
            )

            if failed_utils:
                message += f"\n⚠️ `{len(failed_utils)}` utils en erreur."

            if failed_cogs:
                message += f"\n⚠️ `{len(failed_cogs)}` cogs en erreur."

            await interaction.followup.send(
                message,
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "🔁 Reload complet effectué",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Utils rechargés :** `{len(reloaded_utils)}`\n"
                f"**Utils en erreur :** `{len(failed_utils)}`\n"
                f"**Cogs rechargés :** `{len(reloaded_cogs)}`\n"
                f"**Cogs en erreur :** `{len(failed_cogs)}`",
                discord.Color.green()
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant le reload complet :\n```py\n{error}\n```",
                ephemeral=True
            )

    @dev_group.command(name="sync", description="Synchroniser les commandes slash")
    async def sync_commands(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            guild = discord.Object(id=GUILD_ID)

            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)

            await interaction.followup.send(
                f"✅ `{len(synced)}` commandes slash synchronisées sur ce serveur.",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "🔁 Commandes slash synchronisées",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Commandes synchronisées :** `{len(synced)}`",
                discord.Color.green()
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant la synchronisation :\n```py\n{error}\n```",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(DevReload(bot))