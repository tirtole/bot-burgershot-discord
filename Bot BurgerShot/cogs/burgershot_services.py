import time
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import CHANNEL_SERVICES
from utils.logger import log_action
from utils.permissions import has_burgershot_role, is_staff
from utils.storage import load_json, save_json


SERVICES_FILE = Path("data/services.json")
SERVICES_PANEL_FILE = Path("data/services_panel.json")


def load_services():
    return load_json(SERVICES_FILE, {})


def save_services(services_data):
    save_json(SERVICES_FILE, services_data)


def load_panel_data():
    return load_json(SERVICES_PANEL_FILE, {})


def save_panel_data(panel_data):
    save_json(SERVICES_PANEL_FILE, panel_data)


def format_duration(seconds: int):
    heures = seconds // 3600
    minutes = (seconds % 3600) // 60
    secondes = seconds % 60

    if heures > 0:
        return f"{heures}h {minutes}m {secondes}s"

    if minutes > 0:
        return f"{minutes}m {secondes}s"

    return f"{secondes}s"


def build_empty_services_embed():
    embed = discord.Embed(
        title="🔴 Aucun employé en service",
        description=(
            "Aucun employé n’est actuellement en service.\n\n"
            "Clique sur le bouton **Prendre son service** pour commencer."
        ),
        color=discord.Color.red()
    )

    embed.set_footer(text="BurgerShot Sud RP • Panel service permanent")
    return embed


def build_services_list_embed():
    services_data = load_services()

    embed = discord.Embed(
        title="🟢 Employés actuellement en service",
        color=discord.Color.green()
    )

    if not services_data:
        return build_empty_services_embed()

    description = ""

    for user_id, data in services_data.items():
        start_timestamp = data["start_timestamp"]

        description += (
            f"👤 {data['mention']}\n"
            f"Début : <t:{start_timestamp}:F>\n"
            f"Depuis : <t:{start_timestamp}:R>\n\n"
        )

    embed.description = description
    embed.set_footer(text="BurgerShot Sud RP • Temps mis à jour automatiquement")
    return embed


class ServicesPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Prendre son service",
        style=discord.ButtonStyle.success,
        emoji="🟢",
        custom_id="burgershot_service_start"
    )
    async def start_service_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        cog = interaction.client.get_cog("BurgerShotServices")

        if cog is None:
            await interaction.response.send_message(
                "❌ Le module service n’est pas chargé.",
                ephemeral=True
            )
            return

        await cog.start_service(interaction)

    @discord.ui.button(
        label="Finir son service",
        style=discord.ButtonStyle.danger,
        emoji="🔴",
        custom_id="burgershot_service_end"
    )
    async def end_service_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        cog = interaction.client.get_cog("BurgerShotServices")

        if cog is None:
            await interaction.response.send_message(
                "❌ Le module service n’est pas chargé.",
                ephemeral=True
            )
            return

        await cog.end_service(interaction)

    @discord.ui.button(
        label="Actualiser",
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        custom_id="burgershot_service_refresh"
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        cog = interaction.client.get_cog("BurgerShotServices")

        if cog is None:
            await interaction.response.send_message(
                "❌ Le module service n’est pas chargé.",
                ephemeral=True
            )
            return

        await cog.update_services_panel(interaction.guild)

        await interaction.response.send_message(
            "✅ Panel des services actualisé.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🔄 Panel services actualisé",
            f"{interaction.user.mention} a actualisé le panel des services.",
            discord.Color.blurple()
        )


class BurgerShotServices(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ready_done = False

        # Important : boutons persistants même après redémarrage du bot
        self.bot.add_view(ServicesPanelView())

    async def get_panel_message(self, guild: discord.Guild):
        panel_data = load_panel_data()
        guild_id = str(guild.id)

        if guild_id not in panel_data:
            return None, None

        channel_id = panel_data[guild_id].get("channel_id")
        message_id = panel_data[guild_id].get("message_id")

        channel = guild.get_channel(channel_id)

        if channel is None:
            return None, None

        try:
            message = await channel.fetch_message(message_id)
            return channel, message
        except discord.NotFound:
            return channel, None
        except discord.Forbidden:
            print("[SERVICES] Permissions insuffisantes pour lire/modifier le panel.")
            return channel, None
        except discord.HTTPException as error:
            print(f"[SERVICES] Erreur HTTP panel : {error}")
            return channel, None

    async def update_services_panel(self, guild: discord.Guild):
        if guild is None:
            return

        services_data = load_services()

        if services_data:
            embed = build_services_list_embed()
        else:
            embed = build_empty_services_embed()

        panel_data = load_panel_data()
        guild_id = str(guild.id)

        channel, message = await self.get_panel_message(guild)

        if channel is None:
            channel = discord.utils.get(guild.text_channels, name=CHANNEL_SERVICES)

        if channel is None:
            print(f"[SERVICES] Salon introuvable : {CHANNEL_SERVICES}")
            return

        if message is None:
            try:
                message = await channel.send(
                    embed=embed,
                    view=ServicesPanelView()
                )

                panel_data[guild_id] = {
                    "channel_id": channel.id,
                    "message_id": message.id
                }

                save_panel_data(panel_data)

            except discord.Forbidden:
                print("[SERVICES] Permissions insuffisantes pour envoyer le panel.")
            except discord.HTTPException as error:
                print(f"[SERVICES] Impossible d'envoyer le panel : {error}")

            return

        try:
            await message.edit(
                embed=embed,
                view=ServicesPanelView()
            )

            panel_data[guild_id] = {
                "channel_id": channel.id,
                "message_id": message.id
            }

            save_panel_data(panel_data)

        except discord.Forbidden:
            print("[SERVICES] Permissions insuffisantes pour modifier le panel.")
        except discord.HTTPException as error:
            print(f"[SERVICES] Impossible de modifier le panel : {error}")

    async def start_service(self, interaction: discord.Interaction):
        if not has_burgershot_role(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’es pas employé BurgerShot.",
                ephemeral=True
            )
            return

        services = load_services()
        user_id = str(interaction.user.id)

        if user_id in services:
            start_timestamp = services[user_id]["start_timestamp"]

            await interaction.response.send_message(
                f"❌ Tu es déjà en service depuis <t:{start_timestamp}:R>.",
                ephemeral=True
            )
            return

        start_timestamp = int(time.time())

        services[user_id] = {
            "name": interaction.user.display_name,
            "mention": interaction.user.mention,
            "start_timestamp": start_timestamp
        }

        save_services(services)

        await self.update_services_panel(interaction.guild)

        await interaction.response.send_message(
            f"✅ Tu as pris ton service.\nDébut : <t:{start_timestamp}:F>",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🟢 Prise de service",
            f"{interaction.user.mention} a pris son service.\n"
            f"Début : <t:{start_timestamp}:F>",
            discord.Color.green()
        )

    async def end_service(self, interaction: discord.Interaction):
        if not has_burgershot_role(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’es pas employé BurgerShot.",
                ephemeral=True
            )
            return

        services = load_services()
        user_id = str(interaction.user.id)

        if user_id not in services:
            await interaction.response.send_message(
                "❌ Tu n’es pas actuellement en service.",
                ephemeral=True
            )
            return

        start_timestamp = services[user_id]["start_timestamp"]
        end_timestamp = int(time.time())
        total_seconds = end_timestamp - start_timestamp
        duration = format_duration(total_seconds)

        del services[user_id]
        save_services(services)

        await self.update_services_panel(interaction.guild)

        await interaction.response.send_message(
            f"✅ Tu as terminé ton service.\nTemps total : `{duration}`",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🔴 Fin de service",
            f"{interaction.user.mention} a terminé son service.\n"
            f"Temps total : `{duration}`",
            discord.Color.red()
        )

    @commands.Cog.listener()
    async def on_ready(self):
        if self.ready_done:
            return

        self.ready_done = True

        for guild in self.bot.guilds:
            await self.update_services_panel(guild)

    @app_commands.command(name="panel_services", description="Créer ou mettre à jour le panel permanent des services")
    async def panel_services(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Seuls les managers ou patrons peuvent créer le panel des services.",
                ephemeral=True
            )
            return

        if salon is None:
            salon = discord.utils.get(interaction.guild.text_channels, name=CHANNEL_SERVICES)

        if salon is None:
            await interaction.response.send_message(
                f"❌ Salon `{CHANNEL_SERVICES}` introuvable.",
                ephemeral=True
            )
            return

        panel_data = load_panel_data()

        old_channel, old_message = await self.get_panel_message(interaction.guild)

        if old_message is not None:
            try:
                await old_message.delete()
            except Exception:
                pass

        services_data = load_services()
        embed = build_services_list_embed() if services_data else build_empty_services_embed()

        message = await salon.send(
            embed=embed,
            view=ServicesPanelView()
        )

        panel_data[str(interaction.guild.id)] = {
            "channel_id": salon.id,
            "message_id": message.id
        }

        save_panel_data(panel_data)

        await interaction.response.send_message(
            f"✅ Panel des services créé dans {salon.mention}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📋 Panel services créé",
            f"{interaction.user.mention} a créé le panel permanent des services dans {salon.mention}.",
            discord.Color.green()
        )

    @app_commands.command(name="service", description="Prendre son service BurgerShot")
    async def service(self, interaction: discord.Interaction):
        await self.start_service(interaction)

    @app_commands.command(name="finservice", description="Terminer son service BurgerShot")
    async def finservice(self, interaction: discord.Interaction):
        await self.end_service(interaction)

    @app_commands.command(name="services", description="Afficher les employés actuellement en service")
    async def services(self, interaction: discord.Interaction):
        services_data = load_services()
        embed = build_services_list_embed() if services_data else build_empty_services_embed()

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📋 Liste des services consultée",
            f"{interaction.user.mention} a consulté la liste des employés en service.",
            discord.Color.blurple()
        )


async def setup(bot):
    await bot.add_cog(BurgerShotServices(bot))