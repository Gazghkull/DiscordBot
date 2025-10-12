import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Tuple, List
import os
from dotenv import load_dotenv
import json
import threading
import time
import random
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

load_dotenv()

# ----------------- FACTIONS -----------------
FACTIONS = ["Envahisseur", "Défenseur", "Pirate"]

# ----------------- PLANETES & SYSTEMS -----------------
def create_planet_stats():
    return {f: {"points": 0, "batailles": 0, "choix": 0} for f in FACTIONS}

# Exemple par défaut pour SYSTEMS
SYSTEMS = {
    "Memlock": {
        "Iliar II": create_planet_stats(),
        "Memlock": create_planet_stats(),
        "Udesore": create_planet_stats(),
        "Station Ivius": create_planet_stats(),
        "Telock": create_planet_stats()
    }
    # Les autres systèmes seront ajoutés par la suite
}

# Règles pour chaque système : PV et bonus système
SYSTEM_RULES = {
    "Memlock": {
        "pv_thresholds": [2, 5],  # PV à 2 et 5 points
        "bonus_threshold": 3,     # Bonus système au-dessus de 3 points
        "planets": {
            "Iliar II": 1,
            "Memlock": 2,
            "Udesore": 1,
            "Station Ivius": 1,
            "Telock": 2
        }
    },
    "Hovot": {
        "pv_thresholds": [2, 5],
        "bonus_threshold": 3,
        "planets": {
            "Maben": 1,
            "Vivim": 1,
            "Station d'ancrage des Navigateurs de l'Obscure": 2,
            "Hebda": 1
        }
    },
    "Acraelon": {
        "pv_thresholds": [2, 5],
        "bonus_threshold": 3,
        "planets": {
            "Meggdal": 2,
            "Sumemnal": 1,
            "Station Bénédiction du champ Gleecer": 2,
            "Arrabal": 2,
            "Maeron": 1
        }
    },
    "Umnal": {
        "pv_thresholds": [2],
        "bonus_threshold": 3,
        "planets": {
            "Takfor": 2,
            "Umnal Silva": 1,
            "Umnalis": 1
        }
    },
    "Makravor": {
        "pv_thresholds": [3, 6],
        "bonus_threshold": 4,
        "planets": {
            "Atar Oblitus": 1,
            "Atar Secundus": 2,
            "Atar Prime": 1,
            "Twi’tai": 2,
            "Makravor": 2,
            "Vint": 1
        }
    },
    "Arar": {
        "pv_thresholds": [2],
        "bonus_threshold": 3,
        "planets": {
            "Arar I": 1,
            "Berlag": 2
        }
    }
}

# ----------------- PHASES -----------------
CURRENT_PHASE = 1  # Phase en cours
TOTAL_PARTIES = {f: 0 for f in FACTIONS}  # Batailles phase en cours
PHASES_HISTORY = {}  # Historique des phases : PV et bonus système
DATA_FILE = "data.json"

# ----------------- HONNEUR FORUM IDS -----------------
FORUM_IDS = [1424007352348049598, 1424806344417873960]

HonneurKeyWords = []

ACTIVE_SYSTEMS = {system: True for system in SYSTEM_RULES.keys()}
# ----------------- LOAD/SAVE DATA -----------------
def load_data():
    global SYSTEMS, SYSTEM_RULES, ACTIVE_SYSTEMS, CURRENT_PHASE, TOTAL_PARTIES, PHASES_HISTORY, HonneurKeyWords
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            SYSTEMS = data.get("systems", SYSTEMS)
            SYSTEM_RULES = data.get("system_rules", SYSTEM_RULES)
            ACTIVE_SYSTEMS = data.get("active_systems", {s: True for s in SYSTEM_RULES.keys()})
            CURRENT_PHASE = data.get("current_phase", 1)
            TOTAL_PARTIES = data.get("total_parties", {f: 0 for f in FACTIONS})
            PHASES_HISTORY = data.get("phases_history", {})
            HonneurKeyWords = data.get("HonneurKeyWords", [])
            print("✅ Données chargées depuis data.json")
    except FileNotFoundError:
        print("⚠️ data.json introuvable, création du fichier par défaut")
        save_data()
    except Exception as e:
        print(f"❌ Erreur lors du chargement des données : {e}")

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "systems": SYSTEMS,
                "system_rules": SYSTEM_RULES,
                "active_systems": ACTIVE_SYSTEMS,
                "current_phase": CURRENT_PHASE,
                "total_parties": TOTAL_PARTIES,
                "phases_history": PHASES_HISTORY,
                "HonneurKeyWords": HonneurKeyWords
            }, f, indent=4, ensure_ascii=False)
            print("💾 Données sauvegardées dans data.json")
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde des données : {e}")

# ----------------- CONFIG -----------------
GUILD_ID = 1384163146050048092
guild = discord.Object(id=GUILD_ID)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
load_data()
tree = bot.tree

# ----------------- SURVEILLANCE DATA -----------------
class DataFileHandler(FileSystemEventHandler):
    def __init__(self, file_path, callback):
        self.file_path = file_path
        self.callback = callback
    def on_modified(self, event):
        if event.src_path.endswith(self.file_path):
            print(f"🔄 {self.file_path} modifié, rechargement des données...")
            self.callback()

def start_data_watch(file_path: str, callback):
    event_handler = DataFileHandler(file_path, callback)
    observer = Observer()
    observer.schedule(event_handler, ".", recursive=False)
    observer.start()
    def keep_alive():
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    threading.Thread(target=keep_alive, daemon=True).start()

# ----------------- UTILITAIRES -----------------
def find_planet(planet_name: str) -> Optional[Tuple[str, str]]:
    for systeme, planets in SYSTEMS.items():
        if planet_name in planets:
            return systeme, planet_name
    return None

def all_planets() -> List[str]:
    return [p for planets in SYSTEMS.values() for p in planets.keys()]

# ----------------- CALCUL PV ET BONUS -----------------
def calculate_system_scores(systeme: str, phase: Optional[int] = None):
    """
    Retourne pour le système donné :
        pv_scores : {faction: nb de PV acquis en phase précédente ou avancement}
        bonus_owner : faction ou None
    """
    rules = SYSTEM_RULES[systeme]
    planets_values = rules["planets"]
    pv_thresholds = rules["pv_thresholds"]
    bonus_threshold = rules["bonus_threshold"]

    # Somme des points de chaque faction
    faction_points = {f: 0 for f in FACTIONS}
    for planet, value in planets_values.items():
        for f in FACTIONS:
            faction_points[f] += SYSTEMS[systeme][planet][f]["points"]

    # Calcul des PV
    pv_scores = {f: 0 for f in FACTIONS}
    for threshold in pv_thresholds:
        for f in FACTIONS:
            if faction_points[f] >= threshold:
                pv_scores[f] += 1

    # Bonus système : seulement la faction la plus haute, sauf égalité
    max_pts = max(faction_points.values())
    owners = [f for f, pts in faction_points.items() if pts == max_pts and pts >= bonus_threshold]
    bonus_owner = owners[0] if len(owners) == 1 else None

    # Si phase passée, prendre PV/bonus du PHASES_HISTORY
    if phase is not None and phase in PHASES_HISTORY:
        phase_data = PHASES_HISTORY[phase].get("systems_scores", {})
        pv_scores = phase_data.get("pv_scores", pv_scores)
        bonus_owner = phase_data.get("bonus_owner", bonus_owner)

    return pv_scores, bonus_owner


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
@tree.command(name="ajout",
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
async def ajout(interaction: discord.Interaction,
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
@tree.command(name="cloture",
              description="Clôturer la phase en cours",
              guild=guild)
async def cloture(interaction: discord.Interaction):
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
@tree.command(name="phase",
              description="Afficher la phase en cours",
              guild=guild)
async def phase(interaction: discord.Interaction):
  await interaction.response.send_message(
      f"📌 Phase actuelle : **{CURRENT_PHASE}**")


# ----------------- Commande stats phase -----------------
@tree.command(name="phase_stats",
              description="Afficher les stats d'une phase précédente",
              guild=guild)
@app_commands.describe(phase="Numéro de la phase")
@app_commands.autocomplete(phase=autocomplete_phase)
async def phase_stats(interaction: discord.Interaction, phase: int):
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
@tree.command(name="planete",
              description="Afficher les stats d’une planète",
              guild=guild)
@app_commands.describe(planete="Nom de la planète")
@app_commands.autocomplete(planete=autocomplete_planete)
async def planete(interaction: discord.Interaction, planete: str):
    planet_info = find_planet(planete)
    if planet_info is None:
        await interaction.response.send_message(f"❌ Planète inconnue : {planete}",
                                                ephemeral=True)
        return
    systeme, planete_found = planet_info

    embed = discord.Embed(title=f"🪐 {systeme.upper()}",
                          color=discord.Color.green())

    ICONS = {
        "Défenseur": "🛡️",
        "Envahisseur": "⚔️",
        "Pirate": "💀"
    }

    value = f"▪️\u2003🌏 **{planete_found}**\n"

    # Récupère les points pour chaque faction
    scores = {f: SYSTEMS[systeme][planete_found][f]["points"] for f in FACTIONS}
    max_score = max(scores.values())
    leaders = [f for f, pts in scores.items() if pts == max_score and pts > 0]

    # Ordre forcé Défenseur → Envahisseur → Pirate
    for f in ["Défenseur", "Envahisseur", "Pirate"]:
        v = SYSTEMS[systeme][planete_found][f]
        suffix = ""
        if f in leaders:
            if len(leaders) == 1:
                suffix = " ➡️"
            else:
                suffix = " ⚖️"

        # Affichage : icône + suffixe + nom de la faction
        value += f"▪️\u2003 \u2003{ICONS.get(f,'')}{suffix} {f} : **{v['points']} pts** | `{v['batailles']} batailles`\n"

    embed.add_field(name="", value=value, inline=False)
    await interaction.response.send_message(embed=embed)


# ----------------- AUTRES COMMANDES -----------------
@tree.command(
    name="faction",
    description="Afficher les statistiques d’une faction précise",
    guild=guild
)
@app_commands.describe(faction="Nom de la faction (Défenseur, Envahisseur, Pirate)")
@app_commands.choices(faction=[
    app_commands.Choice(name="Défenseur", value="Défenseur"),
    app_commands.Choice(name="Envahisseur", value="Envahisseur"),
    app_commands.Choice(name="Pirate", value="Pirate")
])
async def faction(interaction: discord.Interaction, faction: app_commands.Choice[str]):
    faction_nom = faction.value
    total_points = 0
    total_batailles = 0
    planètes_gagnées = 0
    systèmes_domines = {}

    # --- Analyse de chaque planète ---
    for systeme, planets in SYSTEMS.items():
        system_points = 0
        for planete, data in planets.items():
            pts = data[faction_nom]["points"]
            total_points += pts
            total_batailles += data[faction_nom]["batailles"]

            # Leader unique sur cette planète ?
            max_points = max(fdata["points"] for fdata in data.values())
            leaders = [f for f, fdata in data.items() if fdata["points"] == max_points]
            if len(leaders) == 1 and leaders[0] == faction_nom:
                planètes_gagnées += 1
                system_points += 1

        if system_points > 0:
            systèmes_domines[systeme] = system_points

    embed = discord.Embed(
        title=f"🏳️ {faction_nom} – Rapport stratégique",
        color=discord.Color.blue() if faction_nom == "Défenseur"
        else discord.Color.red() if faction_nom == "Envahisseur"
        else discord.Color.dark_gold()
    )

    embed.add_field(name="🔢 Points totaux", value=f"**{total_points}**", inline=True)
    embed.add_field(name="⚔️ Batailles livrées", value=f"**{total_batailles}**", inline=True)
    embed.add_field(name="🏆 Planètes contrôlées", value=f"**{planètes_gagnées}**", inline=True)

    if systèmes_domines:
        desc = "\n".join([f"• {sys} ({pts} planètes gagnées)" for sys, pts in systèmes_domines.items()])
    else:
        desc = "Aucun système dominé actuellement."

    embed.add_field(name="🌌 Influence par système", value=desc, inline=False)
    embed.set_footer(text="Les chiffres sont mis à jour automatiquement après chaque bataille.")
    await interaction.response.send_message(embed=embed)

# ----------------- SYSTEMES -----------------
@tree.command(name="liste_sys",
              description="Afficher la liste des systèmes et leurs planètes",
              guild=guild)
async def liste_sys(interaction: discord.Interaction):
  desc = ""
  for systeme, planets in SYSTEMS.items():
    desc += f"**{systeme}** : {', '.join(planets.keys())}\n"
  await interaction.response.send_message(f"📜 Systèmes et planètes :\n{desc}")


# ----------------- STATS SYSTEME -----------------
@tree.command(
    name="systeme",
    description="Afficher les stats d’un système précis avec toutes ses planètes",
    guild=guild
)
@app_commands.describe(systeme="Nom du système")
@app_commands.autocomplete(systeme=autocomplete_systeme)
async def systeme(interaction: discord.Interaction, systeme: str):
    systeme = systeme.capitalize()
    if systeme not in SYSTEMS:
        await interaction.response.send_message(
            f"❌ Système inconnu : {systeme}", ephemeral=True
        )
        return

    embed = discord.Embed(title=f"🪐 {systeme.upper()}", color=discord.Color.green())

    ICONS = {
        "Défenseur": "🛡️",
        "Envahisseur": "⚔️",
        "Pirate": "💀"
    }

    CASE_EMPTY = "▫️"
    CASE_PV = "🏅"
    CASE_BONUS = "🚩"
    SPACE = " "

    rules = SYSTEM_RULES.get(systeme, {})
    pv_thresholds = rules.get("pv_thresholds", [5])
    bonus_threshold = rules.get("bonus_threshold", 3)
    planet_values = rules.get("planets", {})

    max_points = max(pv_thresholds + [bonus_threshold])

    # --- Calcul de l'avancement ---
    total_pv = {f: 0 for f in ICONS.keys()}
    for planet, data in SYSTEMS[systeme].items():
        if planet not in planet_values:
            continue
        scores = {f: data[f]["points"] for f in ICONS.keys()}
        max_score = max(scores.values())
        if max_score <= 0:
            continue
        leaders = [f for f, pts in scores.items() if pts == max_score]
        if len(leaders) == 1:
            gagnant = leaders[0]
            total_pv[gagnant] += planet_values[planet]

    # --- Tableau d’avancement ---
    alignment_prefix = " " * len(f"{ICONS['Défenseur']} : ")
    line_avancement = alignment_prefix + CASE_EMPTY + SPACE
    for pos in range(1, max_points + 1):
        if pos in pv_thresholds:
            line_avancement += CASE_PV + SPACE
        elif pos == bonus_threshold:
            line_avancement += CASE_BONUS + SPACE
        else:
            line_avancement += CASE_EMPTY + SPACE

    faction_lines = []
    for f, pts in total_pv.items():
        pos_line = [CASE_EMPTY] * (max_points + 1)
        pos_index = min(max(pts, 0), max_points)
        pos_line[pos_index] = ICONS[f]
        faction_lines.append(SPACE.join(pos_line))

    # --- Ajoute l’avancement juste après le nom du système ---
    avancement_block = "**Avancement :**\n" + line_avancement.strip() + "\n" + "\n".join(faction_lines)
    embed.add_field(name="", value=avancement_block, inline=False)

    # --- Détails des planètes ---
    lines = []
    for planet, data in SYSTEMS[systeme].items():
        lines.append(f"▪️ 🌏 **{planet}**")
        scores = {f: data[f]["points"] for f in ["Défenseur", "Envahisseur", "Pirate"]}
        max_score = max(scores.values())
        leaders = [f for f, pts in scores.items() if pts == max_score and pts > 0]

        for f in ["Défenseur", "Envahisseur", "Pirate"]:
            v = data[f]
            suffix = ""
            if f in leaders:
                suffix = " 🏆" if len(leaders) == 1 else " ⚖️"
            lines.append(f"▪️  {ICONS[f]}{suffix} {f} : **{v['points']} pts** | `{v['batailles']} batailles`")
        lines.append("")  # ligne vide entre planètes

    # --- Découpage en chunks sûrs ---
    MAX_FIELD_LEN = 1000
    chunks = []
    current = ""
    for ln in lines:
        if len(current) + len(ln) + 1 > MAX_FIELD_LEN:
            chunks.append(current.rstrip("\n"))
            current = ""
        current += ln + "\n"
    if current:
        chunks.append(current.rstrip("\n"))

    for chunk in chunks:
        embed.add_field(name="", value=chunk, inline=False)

    await interaction.response.send_message(embed=embed)

# ----------------- STATS TOUT -----------------
@tree.command(
    name="stats",
    description="Afficher les stats de toutes les planètes des systèmes actifs",
    guild=guild
)
async def stats(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚔️ Statistiques des systèmes actifs",
        color=discord.Color.green()
    )

    ICONS = {
        "Défenseur": "🛡️",
        "Envahisseur": "⚔️",
        "Pirate": "💀"
    }

    CASE_EMPTY = "▫️"
    CASE_PV = "🏅"
    CASE_BONUS = "🚩"
    SPACE = " "

    systems_displayed = 0
    MAX_FIELD_LEN = 1000
    MAX_FIELDS = 25

    active_systems = [s for s in SYSTEMS if ACTIVE_SYSTEMS.get(s, True)]

    for idx, systeme in enumerate(active_systems):
        # --- Ajoute une ligne de séparation avant ce système sauf pour le premier ---
        if idx > 0:
            if len(embed.fields) < MAX_FIELDS:
                embed.add_field(name="", value="――――――――――――――――――――――――", inline=False)

        rules = SYSTEM_RULES.get(systeme, {})
        pv_thresholds = rules.get("pv_thresholds", [5])
        bonus_threshold = rules.get("bonus_threshold", 3)
        planet_values = rules.get("planets", {})
        max_points = max(pv_thresholds + [bonus_threshold])

        # --- Calcul de l'avancement du système ---
        total_pv = {f: 0 for f in ICONS.keys()}
        for planet, data in SYSTEMS[systeme].items():
            if planet not in planet_values:
                continue
            scores = {f: data[f]["points"] for f in ICONS.keys()}
            max_score = max(scores.values())
            if max_score <= 0:
                continue
            leaders = [f for f, pts in scores.items() if pts == max_score]
            if len(leaders) == 1:
                gagnant = leaders[0]
                total_pv[gagnant] += planet_values[planet]

        # --- Ligne principale d’avancement ---
        alignment_prefix = " " * len(f"{ICONS['Défenseur']} : ")
        line_avancement = alignment_prefix + CASE_EMPTY + SPACE
        for pos in range(1, max_points + 1):
            if pos in pv_thresholds:
                line_avancement += CASE_PV + SPACE
            elif pos == bonus_threshold:
                line_avancement += CASE_BONUS + SPACE
            else:
                line_avancement += CASE_EMPTY + SPACE

        # Lignes factions
        faction_lines = []
        for f, pts in total_pv.items():
            pos_line = [CASE_EMPTY] * (max_points + 1)
            pos_index = min(max(pts, 0), max_points)
            pos_line[pos_index] = ICONS[f]
            faction_lines.append(SPACE.join(pos_line))

        # --- On ajoute le tableau d’avancement juste après le nom du système ---
        avancement_block = "**Avancement :**\n" + line_avancement.strip() + "\n" + "\n".join(faction_lines)
        field_name = f"🪐 {systeme.upper()}"
        if len(embed.fields) < MAX_FIELDS:
            embed.add_field(name=field_name, value=avancement_block, inline=False)
            systems_displayed += 1

        # --- Prépare les lignes pour les planètes ---
        planet_lines = []
        for planet, data in SYSTEMS[systeme].items():
            planet_lines.append(f"▪️ 🌏 **{planet}**")
            scores = {f: data[f]["points"] for f in data.keys()}
            max_score = max(scores.values())
            leaders = [f for f, pts in scores.items() if pts == max_score and pts > 0]

            for f in ["Défenseur", "Envahisseur", "Pirate"]:
                v = data[f]
                suffix = ""
                if f in leaders:
                    suffix = " 🏆" if len(leaders) == 1 else " ⚖️"
                planet_lines.append(f"▪️  {ICONS[f]}{suffix} {f} : **{v['points']} pts** | `{v['batailles']} batailles`")
            planet_lines.append("")

        # --- Découpe en chunks et ajout dans l'embed ---
        chunks = []
        current = ""
        for ln in planet_lines:
            if len(current) + len(ln) + 1 > MAX_FIELD_LEN:
                chunks.append(current.rstrip("\n"))
                current = ""
            current += ln + "\n"
        if current:
            chunks.append(current.rstrip("\n"))

        for chunk in chunks:
            if len(embed.fields) < MAX_FIELDS:
                embed.add_field(name="", value=chunk, inline=False)

    if systems_displayed == 0:
        embed.description = "❌ Aucun système actif pour cette phase."

    await interaction.response.send_message(embed=embed)
# ----------------- MODIFIER STATS -----------------
@tree.command(
    name="modif",
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
async def modif(interaction: discord.Interaction,
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
    name="ajout_sys",
    description="Ajouter un nouveau système avec au moins une planète",
    guild=guild)
@app_commands.describe(
    systeme="Nom du système à créer",
    premiere_planete="Nom de la première planète du système")
async def ajout_sys(interaction: discord.Interaction, systeme: str,
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
@tree.command(name="ajout_plan",
              description="Ajouter une planète à un système existant",
              guild=guild)
@app_commands.describe(systeme="Nom du système où ajouter la planète",
                       planete="Nom de la nouvelle planète")
@app_commands.autocomplete(systeme=autocomplete_systeme)
async def ajout_plan(interaction: discord.Interaction, systeme: str,
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
    name="honneur",
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
async def honneur(
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
@tree.command(name="h",
              description="Afficher la liste complète des commandes disponibles",
              guild=guild)
async def h(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📘 Commandes disponibles du Bot Galactique",
        description="Voici la liste des commandes classées par catégorie :",
        color=discord.Color.blurple()
    )

    # --- Phase & Batailles ---
    embed.add_field(
        name="⚔️ Gestion des batailles",
        value=(
            "• **/ajout** — Ajouter une partie ou bataille.\n"
            "• **/cloture** — Clôturer la phase en cours et passer à la suivante.\n"
            "• **/phase** — Afficher la phase en cours.\n"
            "• **/phase_stats** — Voir les statistiques d’une phase précédente."
        ),
        inline=False
    )

    # --- Statistiques ---
    embed.add_field(
        name="📊 Statistiques",
        value=(
            "• **/planete** — Afficher les stats détaillées d’une planète.\n"
            "• **/systeme** — Afficher les stats de toutes les planètes d’un système.\n"
            "• **/stats** — Afficher les stats de toutes les planètes de tous les systèmes.\n"
            "• **/factions** — Voir les totaux des batailles et choix de planète par faction."
        ),
        inline=False
    )

    # --- Gestion manuelle ---
    embed.add_field(
        name="🛠️ Gestion et modifications",
        value=(
            "• **/modif** — Modifier manuellement les points ou batailles d’une faction.\n"
            "• **/ajout_sys** — Créer un nouveau système avec une planète initiale.\n"
            "• **/ajout_plan** — Ajouter une planète dans un système existant.\n"
            "• **/liste_sys** — Liste tous les systèmes et leurs planètes."
        ),
        inline=False
    )

    # --- Honneurs ---
    embed.add_field(
        name="🏅 Tableau d'Honneur",
        value=(
            "• **/honneur** — Tire au hasard un post d'honneur parmi les mots-clés donnés.\n"
            "• **/maj_honneurs** — Met à jour la liste des mots-clés d’honneur à partir des tags des forums."
        ),
        inline=False
    )

    # --- Aide ---
    embed.add_field(
        name="ℹ️ Divers",
        value="• **/h** — Afficher cette liste de commandes.",
        inline=False
    )

    embed.set_footer(
        text="Bot développé pour la campagne galactique ⚙️",
        icon_url="https://cdn-icons-png.flaticon.com/512/4712/4712109.png"
    )

    await interaction.response.send_message(embed=embed)

# ----------------- EVENT -----------------
@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")

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
start_data_watch(DATA_FILE, load_data) #démarrage de la surveillance
bot.run(token)
