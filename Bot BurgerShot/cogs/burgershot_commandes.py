import discord
from discord import app_commands
from discord.ext import commands

from config import CHANNEL_COMMANDES
from utils.logger import log_action
from utils.permissions import has_burgershot_role


def set_embed_field(embed: discord.Embed, name: str, value: str, inline: bool = False):
    for index, field in enumerate(embed.fields):
        if field.name == name:
            embed.set_field_at(index, name=name, value=value, inline=inline)
            return

    embed.add_field(name=name, value=value, inline=inline)


class CommandeStatusView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def update_status(
        self,
        interaction: discord.Interaction,
        status: str,
        color: discord.Color
    ):
        if not has_burgershot_role(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission de modifier le statut d’une commande.",
                ephemeral=True
            )
            return

        if not interaction.message.embeds:
            await interaction.response.send_message(
                "❌ Impossible de modifier cette commande.",
                ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]
        embed.color = color

        set_embed_field(embed, "Statut", status, inline=False)
        set_embed_field(embed, "Dernière modification", interaction.user.mention, inline=False)

        await interaction.message.edit(embed=embed, view=self)

        await interaction.response.send_message(
            f"✅ Statut mis à jour : {status}",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "📦 Statut commande modifié",
            f"**Staff :** {interaction.user.mention}\n"
            f"**Nouveau statut :** {status}\n"
            f"**Salon :** {interaction.channel.mention}",
            color
        )

    @discord.ui.button(
        label="En cours",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="burgershot_commande_en_cours"
    )
    async def en_cours(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(
            interaction,
            "🔄 En cours",
            discord.Color.blue()
        )

    @discord.ui.button(
        label="Attente livraison",
        style=discord.ButtonStyle.secondary,
        emoji="🛵",
        custom_id="burgershot_commande_attente_livraison"
    )
    async def attente_livraison(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(
            interaction,
            "🛵 En attente de livraison",
            discord.Color.gold()
        )

    @discord.ui.button(
        label="Fini",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="burgershot_commande_fini"
    )
    async def fini(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.update_status(
            interaction,
            "✅ Fini",
            discord.Color.green()
        )


class CommandeModal(discord.ui.Modal, title="Nouvelle commande BurgerShot"):
    client = discord.ui.TextInput(
        label="Nom du client",
        placeholder="Exemple : Jean Dupont",
        required=True,
        max_length=50
    )

    contenu = discord.ui.TextInput(
        label="Commande",
        placeholder="Exemple : 2 menus Classic + 1 soda",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    prix = discord.ui.TextInput(
        label="Prix",
        placeholder="Exemple : 150",
        required=True,
        max_length=10
    )

    paiement = discord.ui.TextInput(
        label="Paiement",
        placeholder="cash / banque",
        required=True,
        max_length=30
    )

    remarque = discord.ui.TextInput(
        label="Remarque",
        placeholder="Optionnel",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        commandes_channel = discord.utils.get(
            interaction.guild.text_channels,
            name=CHANNEL_COMMANDES
        )

        if commandes_channel is None:
            await interaction.response.send_message(
                f"❌ Salon `{CHANNEL_COMMANDES}` introuvable.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🧾 Nouvelle commande BurgerShot",
            color=discord.Color.orange()
        )

        embed.add_field(name="Client", value=self.client.value, inline=False)
        embed.add_field(name="Commande", value=self.contenu.value, inline=False)
        embed.add_field(name="Prix", value=f"{self.prix.value}$", inline=True)
        embed.add_field(name="Paiement", value=self.paiement.value, inline=True)
        embed.add_field(name="Remarque", value=self.remarque.value or "Aucune", inline=False)
        embed.add_field(name="Employé", value=interaction.user.mention, inline=False)
        embed.add_field(name="Statut", value="🟡 En attente", inline=False)

        await commandes_channel.send(
            content="@here nouvelle commande BurgerShot !",
            embed=embed,
            view=CommandeStatusView(),
            allowed_mentions=discord.AllowedMentions(everyone=True)
        )

        await interaction.response.send_message(
            f"✅ Commande envoyée dans {commandes_channel.mention}.",
            ephemeral=True
        )

        await log_action(
            interaction.guild,
            "🧾 Commande créée",
            f"**Employé :** {interaction.user.mention}\n"
            f"**Client :** {self.client.value}\n"
            f"**Commande :** {self.contenu.value}\n"
            f"**Prix :** {self.prix.value}€\n"
            f"**Paiement :** {self.paiement.value}\n"
            f"**Salon :** {commandes_channel.mention}",
            discord.Color.orange()
        )


class BurgerShotCommandes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(CommandeStatusView())

    @app_commands.command(name="commande", description="Créer une commande BurgerShot")
    async def commande(self, interaction: discord.Interaction):
        if not has_burgershot_role(interaction.user):
            await interaction.response.send_message(
                "❌ Tu n’as pas la permission.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(CommandeModal())


async def setup(bot):
    await bot.add_cog(BurgerShotCommandes(bot))