from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
import psutil

from utils.permissions import is_staff
from utils.logger import log_action


try:
    from utils.panel_refresh import refresh_all_panels, format_refresh_results
except Exception:
    async def refresh_all_panels(bot):
        return {
            "panel_refresh": {
                "status": "error",
                "count": 0,
                "error": "utils.panel_refresh introuvable ou invalide."
            }
        }

    def format_refresh_results(results: dict):
        lines = []

        for name, result in results.items():
            status = result.get("status", "error")
            count = result.get("count", 0)
            error = result.get("error")

            emoji = "✅" if status == "ok" else "❌"
            line = f"{emoji} `{name}` : `{count}` embed(s)"

            if error:
                line += f"\n> {str(error)[:180]}"

            lines.append(line)

        return "\n".join(lines)


BOT_START_TIME = datetime.now()


def format_uptime():
    delta = datetime.now() - BOT_START_TIME

    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{days}j {hours}h {minutes}m"

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"

    return f"{minutes}m {seconds}s"


def count_commands(bot: commands.Bot):
    count = 0

    for command in bot.tree.get_commands():
        count += 1

        if hasattr(command, "commands"):
            count += len(command.commands)

    return count


def build_dashboard_embed(bot: commands.Bot):
    process = psutil.Process()

    ram_bot = process.memory_info().rss / 1024 / 1024
    ram_total = psutil.virtual_memory().total / 1024 / 1024 / 1024
    ram_percent = psutil.virtual_memory().percent

    cpu_percent = psutil.cpu_percent(interval=None)
    latency = round(bot.latency * 1000)

    guilds = len(bot.guilds)
    users = sum(guild.member_count or 0 for guild in bot.guilds)

    embed = discord.Embed(
        description=(
            "# 📊 Dashboard santé du bot\n\n"

            "## 🤖 Bot\n"
            f"**Ping :** `{latency} ms`\n"
            f"**Uptime :** `{format_uptime()}`\n"
            f"**Serveurs :** `{guilds}`\n"
            f"**Utilisateurs visibles :** `{users}`\n\n"

            "## 🧩 Extensions\n"
            f"**Cogs chargés :** `{len(bot.extensions)}`\n"
            f"**Commandes slash :** `{count_commands(bot)}`\n\n"

            "## 💻 Machine\n"
            f"**CPU :** `{cpu_percent}%`\n"
            f"**RAM bot :** `{ram_bot:.1f} MB`\n"
            f"**RAM système :** `{ram_percent}% / {ram_total:.1f} GB`\n\n"

            "## 📌 Statut\n"
            "✅ Le bot est en ligne."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text=f"BurgerShot Sud RP • Dashboard • {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

    return embed


async def reload_all_extensions(bot: commands.Bot):
    loaded_extensions = list(bot.extensions.keys())

    success = []
    failed = []

    skipped = [
        "cogs.dashboard_bot"
    ]

    for extension in loaded_extensions:
        if extension in skipped:
            continue

        try:
            await bot.reload_extension(extension)
            success.append(extension)

        except Exception as error:
            failed.append((extension, error))

    return success, failed, skipped


async def sync_commands(bot: commands.Bot, guild: discord.Guild | None):
    if guild is None:
        synced = await bot.tree.sync()
        return len(synced), "global"

    guild_object = discord.Object(id=guild.id)

    bot.tree.copy_global_to(guild=guild_object)
    synced = await bot.tree.sync(guild=guild_object)

    return len(synced), guild.name


def build_reload_result_embed(
    success: list[str],
    failed: list[tuple[str, Exception]],
    skipped: list[str],
    panel_text: str
):
    success_text = "\n".join(
        f"✅ `{extension}`"
        for extension in success
    ) or "Aucun cog rechargé."

    failed_text = "\n".join(
        f"❌ `{extension}` : `{str(error)[:120]}`"
        for extension, error in failed
    ) or "Aucune erreur."

    skipped_text = "\n".join(
        f"⏭️ `{extension}`"
        for extension in skipped
    ) or "Aucun."

    embed = discord.Embed(
        description=(
            "# ♻️ Reload all terminé\n\n"

            "## ✅ Cogs rechargés\n"
            f"{success_text}\n\n"

            "## ⏭️ Ignorés pour sécurité\n"
            f"{skipped_text}\n\n"

            "## 🧩 Panels / embeds refresh\n"
            f"{panel_text}\n\n"

            "## ❌ Erreurs\n"
            f"{failed_text}"
        ),
        color=discord.Color.green() if not failed else discord.Color.orange()
    )

    embed.set_footer(
        text=f"BurgerShot Sud RP • Reload all • {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

    return embed


class DashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Actualiser",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
        custom_id="burgershot_dashboard_refresh"
    )
    async def refresh_dashboard(
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

        await interaction.response.edit_message(
            embed=build_dashboard_embed(interaction.client),
            view=DashboardView()
        )

    @discord.ui.button(
        label="Reload all",
        emoji="♻️",
        style=discord.ButtonStyle.secondary,
        custom_id="burgershot_dashboard_reload_all"
    )
    async def reload_all_button(
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

        await interaction.response.defer(ephemeral=True)

        success, failed, skipped = await reload_all_extensions(interaction.client)

        panel_results = await refresh_all_panels(interaction.client)
        panel_text = format_refresh_results(panel_results)

        result_embed = build_reload_result_embed(
            success=success,
            failed=failed,
            skipped=skipped,
            panel_text=panel_text
        )

        try:
            await interaction.message.edit(
                embed=build_dashboard_embed(interaction.client),
                view=DashboardView()
            )
        except Exception:
            pass

        await interaction.followup.send(
            embed=result_embed,
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "♻️ Reload all depuis dashboard",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Cogs rechargés :** `{len(success)}`\n"
            f"**Erreurs :** `{len(failed)}`\n"
            f"**Ignorés :** `{', '.join(skipped)}`\n\n"
            f"**Panels refresh :**\n{panel_text}",
            discord.Color.orange()
        )

    @discord.ui.button(
        label="Sync",
        emoji="🔁",
        style=discord.ButtonStyle.success,
        custom_id="burgershot_dashboard_sync"
    )
    async def sync_button(
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

        await interaction.response.defer(ephemeral=True)

        try:
            synced_count, target = await sync_commands(
                interaction.client,
                interaction.guild
            )

            embed = discord.Embed(
                description=(
                    "# 🔁 Sync terminé\n\n"
                    f"**Commandes synchronisées :** `{synced_count}`\n"
                    f"**Cible :** `{target}`\n\n"
                    "Si les commandes ne s’affichent pas directement, fais `CTRL + R` dans Discord."
                ),
                color=discord.Color.green()
            )

            embed.set_footer(
                text=f"BurgerShot Sud RP • Sync • {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )

            try:
                await interaction.message.edit(
                    embed=build_dashboard_embed(interaction.client),
                    view=DashboardView()
                )
            except Exception:
                pass

            await interaction.followup.send(
                embed=embed,
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "🔁 Sync depuis dashboard",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Commandes :** `{synced_count}`\n"
                f"**Cible :** `{target}`",
                discord.Color.green()
            )

        except Exception as error:
            await interaction.followup.send(
                f"❌ Erreur pendant le sync :\n```txt\n{error}\n```",
                ephemeral=True
            )

            await log_action(
                interaction.guild,
                "❌ Erreur sync dashboard",
                f"**Staff :** {interaction.user.mention}\n"
                f"**Erreur :** `{error}`",
                discord.Color.red()
            )

    @discord.ui.button(
        label="Refresh panels",
        emoji="🧩",
        style=discord.ButtonStyle.primary,
        custom_id="burgershot_dashboard_refresh_panels"
    )
    async def refresh_panels_button(
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

        await interaction.response.defer(ephemeral=True)

        panel_results = await refresh_all_panels(interaction.client)
        panel_text = format_refresh_results(panel_results)

        embed = discord.Embed(
            description=(
                "# 🧩 Refresh panels terminé\n\n"
                f"{panel_text}"
            ),
            color=discord.Color.blurple()
        )

        embed.set_footer(
            text=f"BurgerShot Sud RP • Refresh panels • {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        )

        try:
            await interaction.message.edit(
                embed=build_dashboard_embed(interaction.client),
                view=DashboardView()
            )
        except Exception:
            pass

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🧩 Refresh panels depuis dashboard",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Résultat :**\n{panel_text}",
            discord.Color.blurple()
        )


class DashboardBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Boutons persistants après redémarrage.
        self.bot.add_view(DashboardView())

    @app_commands.command(
        name="dashboard_bot",
        description="Afficher la santé du bot"
    )
    async def dashboard_bot(
        self,
        interaction: discord.Interaction
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=build_dashboard_embed(self.bot),
            view=DashboardView(),
            ephemeral=True
        )

    @app_commands.command(
        name="panel_dashboard",
        description="Créer un panel dashboard public"
    )
    async def panel_dashboard(
        self,
        interaction: discord.Interaction,
        salon: discord.TextChannel | None = None
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        if salon is None:
            salon = interaction.channel

        await salon.send(
            embed=build_dashboard_embed(self.bot),
            view=DashboardView()
        )

        await interaction.response.send_message(
            f"✅ Panel dashboard créé dans {salon.mention}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📊 Panel dashboard créé",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Salon :** {salon.mention}",
            discord.Color.blurple()
        )


async def setup(bot):
    await bot.add_cog(DashboardBot(bot))