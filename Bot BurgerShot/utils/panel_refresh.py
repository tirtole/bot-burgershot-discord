import inspect
import importlib

import discord

from config import (
    CHANNEL_MENUS,
    CHANNEL_SERVICES,
)


def get_channel_by_name(guild: discord.Guild, channel_name: str):
    clean_name = str(channel_name).replace("#", "")
    return discord.utils.get(guild.text_channels, name=clean_name)


def embed_full_text(embed: discord.Embed):
    parts = []

    if embed.title:
        parts.append(embed.title)

    if embed.description:
        parts.append(embed.description)

    if embed.footer and embed.footer.text:
        parts.append(embed.footer.text)

    for field in embed.fields:
        parts.append(field.name)
        parts.append(field.value)

    return "\n".join(parts)


def message_has_custom_id(message: discord.Message, custom_ids: set[str]):
    """
    Vérifie si un message contient un bouton/select avec un custom_id précis.
    Ça évite de confondre help, dashboard, tickets, absences, etc.
    """
    try:
        for row in message.components:
            for component in row.children:
                custom_id = getattr(component, "custom_id", None)

                if custom_id in custom_ids:
                    return True
    except Exception:
        pass

    return False


async def find_recent_bot_panel_by_custom_id(
    bot: discord.Client,
    channel: discord.TextChannel,
    custom_ids: set[str],
    limit: int = 100
):
    try:
        async for message in channel.history(limit=limit):
            if bot.user and message.author.id != bot.user.id:
                continue

            if message_has_custom_id(message, custom_ids):
                return message

    except Exception:
        return None

    return None


async def find_recent_bot_embed_by_keywords(
    bot: discord.Client,
    channel: discord.TextChannel,
    keywords: list[str],
    limit: int = 80
):
    try:
        async for message in channel.history(limit=limit):
            if bot.user and message.author.id != bot.user.id:
                continue

            if not message.embeds:
                continue

            text = embed_full_text(message.embeds[0])

            if any(keyword.lower() in text.lower() for keyword in keywords):
                return message

    except Exception:
        return None

    return None


async def safe_edit_message(message, embed=None, view=None):
    if message is None:
        return False

    try:
        await message.edit(embed=embed, view=view)
        return True
    except Exception:
        return False


async def refresh_help_panels(bot):
    count = 0

    try:
        aide = importlib.import_module("cogs.aide")
    except Exception as error:
        return {
            "status": "error",
            "count": 0,
            "error": str(error)
        }

    for guild in bot.guilds:
        for channel in guild.text_channels:
            message = await find_recent_bot_panel_by_custom_id(
                bot=bot,
                channel=channel,
                custom_ids={"burgershot_help_select"}
            )

            if message is None:
                continue

            success = await safe_edit_message(
                message,
                embed=aide.build_help_embed(0),
                view=aide.HelpPanelView(selected_index=0)
            )

            if success:
                count += 1

    return {
        "status": "ok",
        "count": count
    }


async def refresh_ticket_panels(bot):
    count = 0

    try:
        tickets = importlib.import_module("cogs.tickets")
    except Exception as error:
        return {
            "status": "error",
            "count": 0,
            "error": str(error)
        }

    embed = discord.Embed(
        description=(
            "# 🎫 Support BurgerShot\n\n"
            "Clique sur le bouton ci-dessous pour ouvrir un ticket.\n\n"
            "Un formulaire s’ouvrira pour demander la raison de ta demande."
        ),
        color=discord.Color.orange()
    )
    embed.set_footer(text="BurgerShot Sud RP • Support")

    for guild in bot.guilds:
        for channel in guild.text_channels:
            message = await find_recent_bot_panel_by_custom_id(
                bot=bot,
                channel=channel,
                custom_ids={"burgershot_ticket_open"}
            )

            if message is None:
                continue

            success = await safe_edit_message(
                message,
                embed=embed,
                view=tickets.TicketPanelView()
            )

            if success:
                count += 1

    return {
        "status": "ok",
        "count": count
    }


async def refresh_menu_panels(bot):
    count = 0

    try:
        menu_utils = importlib.import_module("utils.menu_utils")
        embed = menu_utils.build_menu_embed()
    except Exception as error:
        return {
            "status": "error",
            "count": 0,
            "error": str(error)
        }

    for guild in bot.guilds:
        channel = get_channel_by_name(guild, CHANNEL_MENUS)

        if channel is None:
            continue

        message = await find_recent_bot_embed_by_keywords(
            bot=bot,
            channel=channel,
            keywords=[
                "Menu BurgerShot",
                "Menu officiel du BurgerShot",
                "Voici le menu officiel du BurgerShot"
            ]
        )

        if message is None:
            continue

        success = await safe_edit_message(
            message,
            embed=embed,
            view=None
        )

        if success:
            count += 1

    return {
        "status": "ok",
        "count": count
    }


async def refresh_factures_panels(bot):
    count = 0

    try:
        factures = importlib.import_module("cogs.factures")
        panel_data = factures.load_factures_panel()
    except Exception as error:
        return {
            "status": "error",
            "count": 0,
            "error": str(error)
        }

    for guild in bot.guilds:
        guild_id = str(guild.id)
        data = panel_data.get(guild_id)

        if not data:
            continue

        channel = guild.get_channel(data.get("channel_id"))
        output_channel = guild.get_channel(data.get("output_channel_id"))

        if channel is None:
            continue

        message = None
        message_id = data.get("message_id")

        if message_id:
            try:
                message = await channel.fetch_message(message_id)
            except Exception:
                message = None

        if message is None:
            message = await find_recent_bot_panel_by_custom_id(
                bot=bot,
                channel=channel,
                custom_ids={"burgershot_facture_create"}
            )

        if message is None:
            continue

        cog = bot.get_cog("Factures")

        if cog and hasattr(cog, "build_panel_embed"):
            embed = cog.build_panel_embed(output_channel=output_channel)
        else:
            embed = discord.Embed(
                description=(
                    "# 🧾 Panel des factures BurgerShot\n\n"
                    "Clique sur le bouton ci-dessous pour créer une facture rapidement."
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="BurgerShot Sud RP • Panel facturation")

        success = await safe_edit_message(
            message,
            embed=embed,
            view=factures.FacturePanelView()
        )

        if success:
            count += 1

    return {
        "status": "ok",
        "count": count
    }


async def refresh_absence_panels(bot):
    count = 0

    try:
        absences = importlib.import_module("cogs.absences")
        panel_data = absences.load_absences_panel()
    except Exception as error:
        return {
            "status": "error",
            "count": 0,
            "error": str(error)
        }

    for guild in bot.guilds:
        guild_id = str(guild.id)
        data = panel_data.get(guild_id)

        if not data:
            continue

        panel_channel = guild.get_channel(data.get("panel_channel_id"))
        review_channel = guild.get_channel(data.get("review_channel_id"))

        if panel_channel is None:
            continue

        message = await find_recent_bot_panel_by_custom_id(
            bot=bot,
            channel=panel_channel,
            custom_ids={"burgershot_absence_create"}
        )

        if message is None:
            continue

        cog = bot.get_cog("Absences")

        if cog and hasattr(cog, "build_panel_embed"):
            embed = cog.build_panel_embed(review_channel)
        else:
            embed = discord.Embed(
                description=(
                    "# 📅 Panel des absences BurgerShot\n\n"
                    "Clique sur le bouton ci-dessous pour déclarer une absence."
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="BurgerShot Sud RP • Panel absences")

        success = await safe_edit_message(
            message,
            embed=embed,
            view=absences.AbsencePanelView()
        )

        if success:
            count += 1

    return {
        "status": "ok",
        "count": count
    }


async def refresh_dashboard_panels(bot):
    count = 0

    try:
        dashboard = importlib.import_module("cogs.dashboard_bot")
    except Exception as error:
        return {
            "status": "error",
            "count": 0,
            "error": str(error)
        }

    dashboard_custom_ids = {
        "burgershot_dashboard_refresh",
        "burgershot_dashboard_reload_all",
        "burgershot_dashboard_sync",
        "burgershot_dashboard_refresh_panels",
    }

    for guild in bot.guilds:
        for channel in guild.text_channels:
            message = await find_recent_bot_panel_by_custom_id(
                bot=bot,
                channel=channel,
                custom_ids=dashboard_custom_ids
            )

            if message is None:
                continue

            success = await safe_edit_message(
                message,
                embed=dashboard.build_dashboard_embed(bot),
                view=dashboard.DashboardView()
            )

            if success:
                count += 1

    return {
        "status": "ok",
        "count": count
    }


async def try_call_panel_method(method, guild):
    attempts = [
        (),
        (guild,),
    ]

    for args in attempts:
        try:
            result = method(*args)

            if inspect.isawaitable(result):
                await result

            return True, None

        except TypeError:
            continue

        except Exception as error:
            return False, error

    return False, None


async def refresh_service_panels(bot):
    count = 0
    errors = []

    possible_cog_names = [
        "Services",
        "BurgerShotServices",
        "BurgerShotService",
        "Service",
    ]

    possible_method_names = [
        "refresh_panel",
        "refresh_service_panel",
        "refresh_services_panel",
        "update_panel",
        "update_service_panel",
        "update_services_panel",
        "update_service_message",
        "update_panel_message",
    ]

    for guild in bot.guilds:
        updated = False

        for cog_name in possible_cog_names:
            cog = bot.get_cog(cog_name)

            if cog is None:
                continue

            for method_name in possible_method_names:
                method = getattr(cog, method_name, None)

                if method is None:
                    continue

                success, error = await try_call_panel_method(method, guild)

                if success:
                    count += 1
                    updated = True
                    break

                if error:
                    errors.append(f"{cog_name}.{method_name}: {error}")

            if updated:
                break

        if updated:
            continue

        channel = get_channel_by_name(guild, CHANNEL_SERVICES)

        if channel is None:
            continue

    if errors:
        return {
            "status": "partial",
            "count": count,
            "error": " | ".join(errors)[:300]
        }

    return {
        "status": "ok",
        "count": count
    }


async def refresh_all_panels(bot):
    results = {}

    refreshers = {
        "help": refresh_help_panels,
        "tickets": refresh_ticket_panels,
        "menu": refresh_menu_panels,
        "factures": refresh_factures_panels,
        "absences": refresh_absence_panels,
        "dashboard": refresh_dashboard_panels,
        "services": refresh_service_panels,
    }

    for name, refresher in refreshers.items():
        try:
            results[name] = await refresher(bot)
        except Exception as error:
            results[name] = {
                "status": "error",
                "count": 0,
                "error": str(error)
            }

    return results


def format_refresh_results(results: dict):
    lines = []

    for name, result in results.items():
        status = result.get("status")
        count = result.get("count", 0)
        error = result.get("error")

        if status == "ok":
            emoji = "✅"
        elif status == "partial":
            emoji = "⚠️"
        else:
            emoji = "❌"

        line = f"{emoji} `{name}` : `{count}` embed(s)"

        if error:
            line += f"\n> {str(error)[:180]}"

        lines.append(line)

    return "\n".join(lines) or "Aucun panel traité."