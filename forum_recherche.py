# forum_recherche.py
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

# Liste des forums à surveiller
FORUM_IDS = [
    1424007352348049598,  # ID de ton premier forum
    1424806344417873960   # ID du deuxième forum
]

class ForumRecherche(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_all_tags(self) -> List[discord.ForumTag]:
        """Récupère tous les tags disponibles dans les forums configurés"""
        tags = []
        for forum_id in FORUM_IDS:
            forum = self.bot.get_channel(forum_id)
            if isinstance(forum, discord.ForumChannel):
                tags.extend(forum.available_tags)
        return tags

    async def autocomplete_tags(self, interaction: discord.Interaction, current: str):
        """Autocomplétion basée sur le texte saisi"""
        tags = await self.get_all_tags()
        return [
            app_commands.Choice(name=t.name, value=t.name)
            for t in tags if current.lower() in t.name.lower()
        ][:25]

    # ---------------------- COMMANDE SLASH ----------------------
    @app_commands.command(
        name="recherche_forum",
        description="Recherche des threads dans les forums selon les tags sélectionnés"
    )
    @app_commands.describe(
        tag1="Tag principal (obligatoire)",
        tag2="Tag optionnel",
        tag3="Tag optionnel",
        tag4="Tag optionnel",
        tag5="Tag optionnel",
        tag6="Tag optionnel"
    )
    @app_commands.autocomplete(
        tag1=autocomplete_tags,
        tag2=autocomplete_tags,
        tag3=autocomplete_tags,
        tag4=autocomplete_tags,
        tag5=autocomplete_tags,
        tag6=autocomplete_tags,
    )
    async def recherche_forum(
        self,
        interaction: discord.Interaction,
        tag1: str,
        tag2: Optional[str] = None,
        tag3: Optional[str] = None,
        tag4: Optional[str] = None,
        tag5: Optional[str] = None,
        tag6: Optional[str] = None,
    ):
        await interaction.response.defer(thinking=True)

        all_tags = [t for t in [tag1, tag2, tag3, tag4, tag5, tag6] if t]
        matched_threads = []

        # Parcourt les forums configurés
        for forum_id in FORUM_IDS:
            forum = self.bot.get_channel(forum_id)
            if not isinstance(forum, discord.ForumChannel):
                continue

            # Récupère tous les threads actifs
            async for thread in forum.threads:
                if any(tag.name in all_tags for tag in thread.applied_tags):
                    matched_threads.append(thread)

        if not matched_threads:
            await interaction.followup.send("❌ Aucun thread trouvé avec ces tags.")
            return

        # Limite à 25 threads pour ne pas spammer Discord
        matched_threads = matched_threads[:25]

        result_text = "\n".join(f"🧵 [{t.name}]({t.jump_url})" for t in matched_threads)
        await interaction.followup.send(f"✅ Threads trouvés :\n{result_text}")

# ---------------------- SETUP DU COG ----------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(ForumRecherche(bot))