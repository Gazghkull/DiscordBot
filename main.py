import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Tuple, List
import os
from dotenv import load_dotenv
import json
import threading
import requests
import random

load_dotenv()

# ----------------- FACTIONS -----------------
FACTIONS = ["Envahisseur", "Défenseur", "Pirate"]


# ----------------- PLANETES & SYSTEMS -----------------
def create_planet_stats():
  return {f: {"points": 0, "batailles": 0, "choix": 0} for f in FACTIONS}


SYSTEMS = {
    "Memlock": {
        "Iliar II": create_planet_stats(),
        "Memlock": create_planet_stats(),
        "Udesore": create_planet_stats(),
        "Station Ivius": create_planet_stats(),
        "Telock": create_planet_stats()
    },
    "Hovot": {
        "Maben": create_planet_stats(),
        "Vivim": create_planet_stats(),
        "Station d'ancrage des Navigateurs de l'Obscure":
        create_planet_stats(),
        "Hebda": create_planet_stats()
    },
    "Acraelon": {
        "Meggdal": create_planet_stats(),
        "Sumemnal": create_planet_stats(),
        "Station Bénédiction du champ Gleecer": create_planet_stats(),
        "Arrabal": create_planet_stats(),
        "Maeron": create_planet_stats()
    },
    "Umnal": {
        "Takfor": create_planet_stats(),
        "Umnal Silva": create_planet_stats(),
        "Umnalis": create_planet_stats()
    },
    "Makravor": {
        "Atar Oblitus": create_planet_stats(),
        "Atar Secundus": create_planet_stats(),
        "Atar Prime": create_planet_stats(),
        "Twi’tai": create_planet_stats(),
        "Makravor": create_planet_stats(),
        "Vint": create_planet_stats()
    },
    "Arar": {
        "Arar I": create_planet_stats(),
        "Berlag": create_planet_stats()
    }
}

# ----------------- PHASES -----------------
CURRENT_PHASE = 1  # Phase en cours
TOTAL_PARTIES = {f: 0 for f in FACTIONS}  # Batailles phase en cours
PHASES_HISTORY = {}  # Historique des phases

DATA_FILE = "data.json"


# ----------------- HONNEUR FORUMS IDS -----------------
FORUM_IDS = [
    1424007352348049598,  # ID de ton premier forum
    1424806344417873960   # ID du deuxième forum
]

# ----------------- LOAD/SAVE DATA -----------------
def load_data():
    global SYSTEMS, CURRENT_PHASE, TOTAL_PARTIES, PHASES_HISTORY, HonneurKeyWords
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            SYSTEMS = data.get("systems", SYSTEMS)
            CURRENT_PHASE = data.get("current_phase", 1)
            TOTAL_PARTIES = data.get("total_parties", {f: 0 for f in FACTIONS})
            PHASES_HISTORY = data.get("phases_history", {})
            HonneurKeyWords = data.get("HonneurKeyWords", [])
            print("✅ Données chargées depuis data.json")
    except FileNotFoundError:
        print("⚠️ data.json introuvable, démarrage avec les données par défaut")
    except Exception as e:
        print(f"❌ Erreur lors du chargement des données : {e}")


def save_data():
    data = {
        "systems": SYSTEMS,
        "current_phase": CURRENT_PHASE,
        "total_parties": TOTAL_PARTIES,
        "phases_history": PHASES_HISTORY,
        "HonneurKeyWords": HonneurKeyWords
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"❌ Erreur lors de l'enregistrement des données : {e}")


# ----------------- CONFIG -----------------
GUILD_ID = 1384163146050048092  # Remplace par ton serveur
guild = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
load_data()
tree = bot.tree


# ----------------- UTILITAIRES -----------------
def find_planet(planet_name: str) -> Optional[Tuple[str, str]]:
  """Retourne (systeme, planet_name) ou None si pas trouvé"""
  for systeme, planets in SYSTEMS.items():
    if planet_name in planets:
      return systeme, planet_name
  return None


def all_planets() -> List[str]:
  return [p for planets in SYSTEMS.values() for p in planets.keys()]


# ----------------- AUTOCOMPLETION -----------------
async def autocomplete_planete(interaction: discord.Interaction, current: str):
  return [
      app_commands.Choice(name=p, value=p) for p in all_planets()
      if current.lower() in p.lower()
  ][:25]


async def autocomplete_faction(interaction: discord.Interaction, current: str):
  return [
      app_commands.Choice(name=f, value=f) for f in FACTIONS
      if current.lower() in f.lower()
  ][:25]


async def autocomplete_numbers(interaction: discord.Interaction, current: str):
  numbers = [str(i) for i in range(0, 21)]
  return [
      app_commands.Choice(name=n, value=n) for n in numbers if current in n
  ][:25]


async def autocomplete_systeme(interaction: discord.Interaction, current: str):
  return [
      app_commands.Choice(name=s, value=s) for s in SYSTEMS.keys()
      if current.lower() in s.lower()
  ][:25]


async def autocomplete_phase(interaction: discord.Interaction, current: str):
  phases = [str(i) for i in range(1, CURRENT_PHASE + 1)]
  return [
      app_commands.Choice(name=p, value=p) for p in phases if current in p
  ][:25]

async def autocomplete_honneur(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=kw, value=kw)
        for kw in HonneurKeyWords
        if current.lower() in kw.lower()
    ][:25]

# ----------------- COMMANDES -----------------
@tree.command(name="ajouter_partie",
              description="Ajouter une partie/bataille",
              guild=guild)
@app_commands.describe(
    planete="Nom de la planète",
    gagnant="Faction gagnante ou 'Egalite'",
    choix_planete="Faction qui a choisi la planète",
    participant1="Premier participant",
    participant2="Deuxième participant",
    participant3="Troisième participant (facultatif)",
    phase="Phase dans laquelle ajouter la partie (optionnel)")
@app_commands.autocomplete(planete=autocomplete_planete,
                           gagnant=autocomplete_faction,
                           choix_planete=autocomplete_faction,
                           participant1=autocomplete_faction,
                           participant2=autocomplete_faction,
                           participant3=autocomplete_faction,
                           phase=autocomplete_phase)
async def ajouter_partie(interaction: discord.Interaction,
                         planete: str,
                         gagnant: str,
                         choix_planete: str,
                         participant1: str,
                         participant2: str,
                         participant3: Optional[str] = None,
                         phase: Optional[int] = None):
  global CURRENT_PHASE, TOTAL_PARTIES, PHASES_HISTORY

  participants_list = [
      p for p in [participant1, participant2, participant3] if p
  ]
  planet_info = find_planet(planete)
  if planet_info is None:
    await interaction.response.send_message(f"❌ Planète inconnue : {planete}",
                                            ephemeral=True)
    return
  systeme, planete_found = planet_info

  gagnant = gagnant.capitalize()
  choix_planete = choix_planete.capitalize()

  # Validation participants
  for f in participants_list:
    if f not in FACTIONS:
      await interaction.response.send_message(f"❌ Faction inconnue : {f}",
                                              ephemeral=True)
      return
  if gagnant != "Egalite" and gagnant not in participants_list:
    await interaction.response.send_message(
        "❌ Le gagnant doit être parmi les participants ou 'Egalite'",
        ephemeral=True)
    return
  if choix_planete not in participants_list:
    await interaction.response.send_message(
        "❌ La faction qui choisit la planète doit être parmi les participants",
        ephemeral=True)
    return

  # Déterminer la phase
  target_phase = phase if phase is not None else CURRENT_PHASE

  # Si on ajoute dans la phase en cours, on incrémente TOTAL_PARTIES
  if target_phase == CURRENT_PHASE:
    for f in participants_list:
      TOTAL_PARTIES[f] += 1

  # Attribution des points et choix pour la planète
  for f in participants_list:
    # Points (conservés entre les phases)
    if f == gagnant:
      SYSTEMS[systeme][planete_found][f]["points"] += 3
    elif gagnant == "Egalite":
      SYSTEMS[systeme][planete_found][f]["points"] += 2
    else:
      SYSTEMS[systeme][planete_found][f]["points"] += 1

    # Batailles & choix (par phase)
    if target_phase == CURRENT_PHASE:
      SYSTEMS[systeme][planete_found][f]["batailles"] += 1
      if f == choix_planete:
        SYSTEMS[systeme][planete_found][f]["choix"] += 1
    else:
      # Si ajout dans une phase antérieure
      if target_phase not in PHASES_HISTORY:
        PHASES_HISTORY[target_phase] = {
            "total_parties": {
                f: 0
                for f in FACTIONS
            },
            "choix_planete": {
                f: 0
                for f in FACTIONS
            }
        }
      PHASES_HISTORY[target_phase]["total_parties"][f] += 1
      if f == choix_planete:
        PHASES_HISTORY[target_phase]["choix_planete"][f] += 1

  await interaction.response.send_message(
      f"✅ Partie ajoutée sur **{planete_found} ({systeme})** dans la phase {target_phase} !\n"
      f"Gagnant : **{gagnant}**, choix de la planète : **{choix_planete}**, participants : {', '.join(participants_list)}"
  )
  save_data()


# ----------------- Clôturer phase -----------------
@tree.command(name="cloturer_phase",
              description="Clôturer la phase en cours",
              guild=guild)
async def cloturer_phase(interaction: discord.Interaction):
  global CURRENT_PHASE, TOTAL_PARTIES, PHASES_HISTORY

  # Sauvegarder stats de la phase
  phase_data = {
      "total_parties": TOTAL_PARTIES.copy(),
      "choix_planete": {
          f: 0
          for f in FACTIONS
      }
  }
  for systeme, planets in SYSTEMS.items():
    for planet, data in planets.items():
      for f, stats in data.items():
        phase_data["choix_planete"][f] += stats["choix"]

  PHASES_HISTORY[CURRENT_PHASE] = phase_data

  # Réinitialiser compteurs de la phase
  TOTAL_PARTIES = {f: 0 for f in FACTIONS}
  for systeme, planets in SYSTEMS.items():
    for planet, data in planets.items():
      for f in data:
        data[f]["batailles"] = 0
        data[f]["choix"] = 0

  CURRENT_PHASE += 1

  await interaction.response.send_message(
      f"✅ Phase {CURRENT_PHASE - 1} clôturée ! Passage à la phase {CURRENT_PHASE}."
  )
  save_data()


# ----------------- Commande phase actuelle -----------------
@tree.command(name="phase_actuelle",
              description="Afficher la phase en cours",
              guild=guild)
async def phase_actuelle(interaction: discord.Interaction):
  await interaction.response.send_message(
      f"📌 Phase actuelle : **{CURRENT_PHASE}**")


# ----------------- Commande stats phase -----------------
@tree.command(name="stats_phase",
              description="Afficher les stats d'une phase précédente",
              guild=guild)
@app_commands.describe(phase="Numéro de la phase")
@app_commands.autocomplete(phase=autocomplete_phase)
async def stats_phase(interaction: discord.Interaction, phase: int):
  if phase not in PHASES_HISTORY:
    await interaction.response.send_message(f"❌ Phase {phase} inconnue",
                                            ephemeral=True)
    return

  data = PHASES_HISTORY[phase]
  embed = discord.Embed(title=f"📊 Stats Phase {phase}",
                        color=discord.Color.blue())

  for f in FACTIONS:
    total_parties = data["total_parties"].get(f, 0)
    choix_planete = data["choix_planete"].get(f, 0)
    embed.add_field(
        name=f,
        value=
        f"Parties disputées : {total_parties}\nChoix de planète : {choix_planete}",
        inline=False)

  await interaction.response.send_message(embed=embed)


# ----------------- STATS PLANETE -----------------
@tree.command(name="stats_planete",
              description="Afficher les stats d’une planète",
              guild=guild)
@app_commands.describe(planete="Nom de la planète")
@app_commands.autocomplete(planete=autocomplete_planete)
async def stats_planete(interaction: discord.Interaction, planete: str):
  planet_info = find_planet(planete)
  if planet_info is None:
    await interaction.response.send_message(f"❌ Planète inconnue : {planete}",
                                            ephemeral=True)
    return
  systeme, planete_found = planet_info

  embed = discord.Embed(title=f"🪐 {planete_found} ({systeme})",
                        color=discord.Color.green())

  # Crée une seule string avec une ligne vide entre chaque faction
  value = ""
  for f, data in SYSTEMS[systeme][planete_found].items():
    value += f"**{f.upper()}**\n**Points : {data['points']}**\n`Batailles : {data['batailles']}`\n\n"

  embed.add_field(name="", value=value, inline=False)
  await interaction.response.send_message(embed=embed)


# ----------------- AUTRES COMMANDES -----------------
@tree.command(
    name="stats_factions",
    description="Afficher le total des parties et choix de planète par faction",
    guild=guild)
async def stats_factions(interaction: discord.Interaction):
  embed = discord.Embed(title=f"📊 Stats Factions - Phase {CURRENT_PHASE}",
                        color=discord.Color.blue())

  # Compter le nombre de choix de planète dans la phase en cours
  choix_par_faction = {f: 0 for f in FACTIONS}
  for systeme, planets in SYSTEMS.items():
    for planet, data in planets.items():
      for f, stats in data.items():
        choix_par_faction[f] += stats["choix"]

  for f in FACTIONS:
    embed.add_field(
        name=f,
        value=
        f"Parties disputées : {TOTAL_PARTIES[f]}\nChoix de planète : {choix_par_faction[f]}",
        inline=False)

  await interaction.response.send_message(embed=embed)


# ----------------- SYSTEMES -----------------
@tree.command(name="systemes",
              description="Afficher la liste des systèmes et leurs planètes",
              guild=guild)
async def systemes(interaction: discord.Interaction):
  desc = ""
  for systeme, planets in SYSTEMS.items():
    desc += f"**{systeme}** : {', '.join(planets.keys())}\n"
  await interaction.response.send_message(f"📜 Systèmes et planètes :\n{desc}")


# ----------------- STATS SYSTEME -----------------
@tree.command(
    name="stats_systeme",
    description=
    "Afficher les stats d’un système précis avec toutes ses planètes",
    guild=guild)
@app_commands.describe(systeme="Nom du système")
@app_commands.autocomplete(systeme=autocomplete_systeme)
async def stats_systeme(interaction: discord.Interaction, systeme: str):
  systeme = systeme.capitalize()
  if systeme not in SYSTEMS:
    await interaction.response.send_message(f"❌ Système inconnu : {systeme}",
                                            ephemeral=True)
    return

  embed = discord.Embed(title=f"🪐{systeme.upper()}",
                        color=discord.Color.green())

  for planet, data in SYSTEMS[systeme].items():
    desc = ""
    # Ligne invisible pour forcer l'indentation de la première ligne
    for f, v in data.items():
      desc += f"▪️\u2003{f} : **{v['points']} pts** | `{v['batailles']} batailles`\n"
    embed.add_field(name=f"🌏 {planet}", value=desc, inline=False)

  await interaction.response.send_message(embed=embed)


# ----------------- STATS TOUT -----------------
@tree.command(name="stats_tout",
              description=
              "Afficher les stats de toutes les planètes de tous les systèmes",
              guild=guild)
async def stats_tout(interaction: discord.Interaction):
  embed = discord.Embed(title="⚔️ Statistiques de toutes les planètes",
                        color=discord.Color.green())

  for systeme, planets in SYSTEMS.items():
    desc = ""
    for planet, data in planets.items():
      desc += f"▪️\u2003🌏 **{planet}**\n"
      for f, v in data.items():
        desc += f"▪️\u2003 \u2003{f} : **{v['points']} pts** | `{v['batailles']} batailles`\n"
      desc += "\n"
    embed.add_field(name=f"🪐 {systeme.upper()}", value=desc, inline=False)

  await interaction.response.send_message(embed=embed)


# ----------------- MODIFIER STATS -----------------
@tree.command(
    name="modifier_stats",
    description=
    "Modifier directement les points ou batailles d’une faction sur une planète",
    guild=guild)
@app_commands.describe(planete="Nom de la planète",
                       faction="Faction à modifier",
                       points="Points de victoire (optionnel, 0-20)",
                       batailles="Nombre de batailles (optionnel, 0-20)")
@app_commands.autocomplete(planete=autocomplete_planete,
                           faction=autocomplete_faction,
                           points=autocomplete_numbers,
                           batailles=autocomplete_numbers)
async def modifier_stats(interaction: discord.Interaction,
                         planete: str,
                         faction: str,
                         points: Optional[int] = None,
                         batailles: Optional[int] = None):
  faction = faction.capitalize()
  planet_info = find_planet(planete)
  if planet_info is None:
    await interaction.response.send_message(f"❌ Planète inconnue : {planete}",
                                            ephemeral=True)
    return

  systeme_found, planete_found = planet_info
  if faction not in FACTIONS:
    await interaction.response.send_message(f"❌ Faction inconnue : {faction}",
                                            ephemeral=True)
    return

  # Mise à jour des stats
  if points is not None:
    SYSTEMS[systeme_found][planete_found][faction]["points"] = points

  if batailles is not None:
    delta = batailles - SYSTEMS[systeme_found][planete_found][faction][
        "batailles"]
    SYSTEMS[systeme_found][planete_found][faction]["batailles"] = batailles
    TOTAL_PARTIES[faction] += delta

  await interaction.response.send_message(
      f"✅ Stats modifiées pour **{faction}** sur **{planete_found}** ({systeme_found}) : points={points} batailles={batailles}"
  )
  save_data()


# ----------------- AJOUTER SYSTEME -----------------
@tree.command(
    name="ajouter_systeme",
    description="Ajouter un nouveau système avec au moins une planète",
    guild=guild)
@app_commands.describe(
    systeme="Nom du système à créer",
    premiere_planete="Nom de la première planète du système")
async def ajouter_systeme(interaction: discord.Interaction, systeme: str,
                          premiere_planete: str):
  systeme = systeme.capitalize()
  premiere_planete = premiere_planete.capitalize()

  if systeme in SYSTEMS:
    await interaction.response.send_message(
        f"❌ Le système **{systeme}** existe déjà !", ephemeral=True)
    return

  SYSTEMS[systeme] = {premiere_planete: create_planet_stats()}
  await interaction.response.send_message(
      f"✅ Nouveau système **{systeme}** créé avec la planète **{premiere_planete}** !"
  )
  save_data()


# ----------------- AJOUTER PLANETE -----------------
@tree.command(name="ajouter_planete",
              description="Ajouter une planète à un système existant",
              guild=guild)
@app_commands.describe(systeme="Nom du système où ajouter la planète",
                       planete="Nom de la nouvelle planète")
@app_commands.autocomplete(systeme=autocomplete_systeme)
async def ajouter_planete(interaction: discord.Interaction, systeme: str,
                          planete: str):
  systeme = systeme.capitalize()
  planete = planete.capitalize()

  if systeme not in SYSTEMS:
    await interaction.response.send_message(
        f"❌ Le système **{systeme}** n'existe pas !", ephemeral=True)
    return

  if planete in SYSTEMS[systeme]:
    await interaction.response.send_message(
        f"❌ La planète **{planete}** existe déjà dans le système {systeme} !",
        ephemeral=True)
    return

  SYSTEMS[systeme][planete] = create_planet_stats()
  await interaction.response.send_message(
      f"✅ Planète **{planete}** ajoutée au système **{systeme}** !")
  save_data()


# -------- Commande tirage au sort d'honneur  --------
@tree.command(
    name="rollhonneur",
    description="Rechercher des posts contenant au moins un tag parmi les mots-clés donnés.",
    guild=guild
)
@app_commands.describe(
    mot1="Mot-clé obligatoire",
    mot2="Mot-clé optionnel",
    mot3="Mot-clé optionnel",
    mot4="Mot-clé optionnel",
    mot5="Mot-clé optionnel",
    mot6="Mot-clé optionnel"
)
@app_commands.autocomplete(
    mot1=autocomplete_honneur,
    mot2=autocomplete_honneur,
    mot3=autocomplete_honneur,
    mot4=autocomplete_honneur,
    mot5=autocomplete_honneur,
    mot6=autocomplete_honneur
)
async def rollhonneur(
    interaction: discord.Interaction,
    mot1: str,
    mot2: Optional[str] = None,
    mot3: Optional[str] = None,
    mot4: Optional[str] = None,
    mot5: Optional[str] = None,
    mot6: Optional[str] = None
):
    await interaction.response.defer(thinking=True, ephemeral=False)

    keywords = [m.lower() for m in [mot1, mot2, mot3, mot4, mot5, mot6] if m]
    matched_threads = []

    for forum_id in FORUM_IDS:
        forum = bot.get_channel(forum_id)
        if not forum:
            print(f"⚠️ Forum introuvable : {forum_id}")
            continue

        try:
            active_threads = list(forum.threads)

            archived_threads = []
            async for t in forum.archived_threads(limit=None):
                archived_threads.append(t)

            threads = active_threads + archived_threads

            for thread in threads:
                if not thread.applied_tags:
                    continue

                tag_names = [tag.name.lower() for tag in thread.applied_tags]
                if any(k in tag_names for k in keywords):
                    matched_threads.append(thread)

        except Exception as e:
            print(f"⚠️ Erreur lors de la lecture du forum {forum_id}: {e}")

    # Vérifie le nombre de threads trouvés
    if len(matched_threads) < 3:
        await interaction.followup.send(
            "⚠️ Moins de 3 honneurs trouvés, veuillez vérifier les tableaux d'honneur ou bien contacter un admin."
        )
        return

    # Tire un thread au hasard
    chosen_thread = random.choice(matched_threads)
    thread_url = f"https://discord.com/channels/{interaction.guild_id}/{chosen_thread.id}"

    # Crée l’embed de résultat
    embed = discord.Embed(
        title=f"🎖️ Honneur sélectionné au hasard parmi {len(matched_threads)} résultats",
        color=discord.Color.gold()
    )
    embed.add_field(name="Nom du post", value=chosen_thread.name, inline=False)
    embed.add_field(name="Lien", value=f"[Ouvrir le post]({thread_url})", inline=False)

    # Affiche les tags du thread s’ils existent
    if chosen_thread.applied_tags:
        tags_str = ", ".join(tag.name for tag in chosen_thread.applied_tags)
        embed.add_field(name="Tags", value=tags_str, inline=False)

    await interaction.followup.send(embed=embed)

# ----------------- maj honneur tags -----------------
@tree.command(
    name="maj_honneurs",
    description="Met à jour la liste HonneurKeyWords dans data.json à partir des tags présents dans les forums.",
    guild=guild
)
async def maj_honneurs(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    all_tags = set()

    for forum_id in FORUM_IDS:
        forum = bot.get_channel(forum_id)
        if not forum:
            print(f"⚠️ Forum introuvable : {forum_id}")
            continue

        try:
            for tag in forum.available_tags:
                all_tags.add(tag.name)
        except Exception as e:
            print(f"⚠️ Erreur forum {forum_id} : {e}")

    if not all_tags:
        await interaction.followup.send("❌ Aucun tag trouvé dans les forums configurés.")
        return

    global HonneurKeyWords
    HonneurKeyWords = sorted(list(all_tags))
    save_data()

    await interaction.followup.send(
        f"✅ Liste des Honneurs mise à jour avec {len(HonneurKeyWords)} tags :\n"
        f"```{', '.join(HonneurKeyWords)}```"
    )
# ----------------- HELP -----------------
@tree.command(name="help",
              description="Afficher la liste des commandes",
              guild=guild)
async def help(interaction: discord.Interaction):
  desc = (
      "/ajouter_partie <Planète> <Gagnant> <ChoixPlanète> <Participants...> : Ajouter une partie\n"
      "/stats_planete <Planète> : Stats d’une planète\n"
      "/stats_systeme <Système> : Stats d’un système\n"
      "/stats_tout : Stats de toutes les planètes\n"
      "/stats_factions : Total de parties par faction\n"
      "/modifier_stats <Système> <Planète> <Faction> points=<valeur> batailles=<valeur> : Modifier stats d’une faction\n"
      "/systemes : Liste des systèmes et planètes\n"
      "/ajouter_systeme : Ajoute un système\n"
      "/ajouter_planete : Ajoute une planète à un système")
  await interaction.response.send_message(desc)

# ----------------- EVENT -----------------
@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")

    # Charger le cog
    try:
        await bot.load_extension("forum_recherche")
        print("✅ Extension forum_recherche chargée")
    except Exception as e:
        print(f"⚠️ Impossible de charger forum_recherche : {e}")

    # Synchroniser les commandes pour le serveur
    try:
        guild_obj = discord.Object(id=GUILD_ID)
        await bot.tree.sync(guild=guild_obj)
        print(f"🌍 Slash commands synchronisées sur le serveur {GUILD_ID}")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation des commandes : {e}")


# ----------------- RUN BOT -----------------
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("❌ DISCORD_BOT_TOKEN not found in environment variables!")
    exit(1)

load_data()
bot.run(token)