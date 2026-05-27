import discord

from config import ROLE_EMPLOYE, ROLE_MANAGER, ROLE_PATRON


def has_burgershot_role(member: discord.Member):
    allowed_roles = [
        ROLE_EMPLOYE,
        ROLE_MANAGER,
        ROLE_PATRON
    ]

    return any(role.name in allowed_roles for role in getattr(member, "roles", []))


def is_staff(member: discord.Member):
    allowed_roles = [
        ROLE_MANAGER,
        ROLE_PATRON
    ]

    return any(role.name in allowed_roles for role in getattr(member, "roles", []))