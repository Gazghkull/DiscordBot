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

# ----------------- SECTEURS, SOUS-SECTEURS, SYSTEMS & PLANETS -----------------
SECTORS = {}  # sera chargé depuis le JSON

def create_planet_stats():
    return {f: {"points": 0, "batailles": 0, "choix": 0} for f in FACTIONS}

def find_planet(planete: str) -> Optional[Tuple[str, str, str, str]]:
    """
    Retourne : secteur, sous_secteur, système, planète
    """
    for secteur_name, sous_secteurs in SECTORS.items():
        for sous_secteur_name, systems in sous_secteurs.items():
            for system_name, planets in systems.items():
                if planete in planets:
                    return secteur_name, sous_secteur_name, system_name, planete
    return None

def all_planets() -> List[str]:
    return [
        p
        for sous_secteurs in SECTORS.values()
        for systems in sous_secteurs.values()
        for planets in systems.values()
        for p in planets.keys()
    ]

def all_systems() -> List[str]:
    return [
        s
        for sous_secteurs in SECTORS.values()
        for systems in sous_secteurs.values()
        for s in systems.keys()
    ]

def get_planet_data(planete: str):
    info = find_planet(planete)
    if not info:
        return None
    secteur, sous_secteur, systeme, planete_name = info
    return SECTORS[secteur][sous_secteur][systeme][planete_name]

def get_system_planets(systeme: str):
    for secteur, sous_secteurs in SECTORS.items():
        for sous_secteur, systems in sous_secteurs.items():
            if systeme in systems:
                return systems[systeme]
    return None

def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        # Vérifie si l'utilisateur est administrateur
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

# ----------------- SYSTEM RULES -----------------
SYSTEM_RULES = {}  # sera chargé depuis le JSON

# ----------------- PHASES -----------------
CURRENT_PHASE = {}
TOTAL_PARTIES = {f: 0 for f in FACTIONS}
PHASES_HISTORY = {}
DATA_FILE = "data.json"

PLANET_VALUE_ICONS = {
    1: "⭐",
    2: "⭐⭐"
}

# ----------------- HONNEUR -----------------
HonneurKeyWords = []

ACTIVE_SYSTEMS = {}  # sera chargé depuis le JSON

# ----------------- LOAD/SAVE DATA -----------------
def load_data():
    global SECTORS, SYSTEM_RULES, ACTIVE_SYSTEMS, CURRENT_PHASE, TOTAL_PARTIES, PHASES_HISTORY, HonneurKeyWords
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            SECTORS = data.get("sectors", SECTORS)
            SYSTEM_RULES = data.get("system_rules", SYSTEM_RULES)
            ACTIVE_SYSTEMS = data.get("active_systems", ACTIVE_SYSTEMS)
            CURRENT_PHASE = data.get("phase_courante", {"phase": 1, "secteur": "Eguedine"})
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
                "sectors": SECTORS,
                "system_rules": SYSTEM_RULES,
                "active_systems": ACTIVE_SYSTEMS,
                "phase_courante": CURRENT_PHASE,
                "total_parties": TOTAL_PARTIES,
                "phases_history": PHASES_HISTORY,
                "HonneurKeyWords": HonneurKeyWords
            }, f, indent=4, ensure_ascii=False)
            print("💾 Données sauvegardées dans data.json")
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde des données : {e}")

# ----------------- CONFIG -----------------
# Lecture des IDs depuis .env
GUILD_ID = int(os.getenv("GUILD_ID"))
FORUM_IDS = [int(fid.strip()) for fid in os.getenv("FORUM_IDS", "").split(",") if fid.strip()]

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

# ----------------- AUTOCOMPLETION -----------------
async def autocomplete_planete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=p, value=p) for p in all_planets() if current.lower() in p.lower()][:25]

async def autocomplete_faction(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=f, value=f) for f in FACTIONS if current.lower() in f.lower()][:25]

async def autocomplete_numbers(interaction: discord.Interaction, current: str):
    numbers = [str(i) for i in range(0, 21)]
    return [app_commands.Choice(name=n, value=n) for n in numbers if current in n][:25]

async def autocomplete_systeme(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=s, value=s) for s in all_systems() if current.lower() in s.lower()][:25]

async def autocomplete_phase(interaction: discord.Interaction, current: str):
    current_phase_number = CURRENT_PHASE.get("phase", 1)
    phases = [str(i) for i in range(1, current_phase_number + 1)]
    return [app_commands.Choice(name=p, value=p) for p in phases if current in p][:25]

async def autocomplete_honneur(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=kw, value=kw) for kw in HonneurKeyWords if current.lower() in kw.lower()][:25]

async def autocomplete_sous_secteur(interaction: discord.Interaction, current: str):
    secteur_courant = CURRENT_PHASE.get("secteur")
    if not secteur_courant or secteur_courant not in SECTORS:
        return []

    # Liste des sous-secteurs disponibles dans le secteur courant
    sous_secteurs = [ss for ss in SECTORS[secteur_courant].keys() if current.lower() in ss.lower()]

    # Limiter à 25 choix comme Discord l'impose
    return [app_commands.Choice(name=ss, value=ss) for ss in sous_secteurs][:25]

# --- Autocomplétion des numéros de phase ---
async def autocomplete_phase(interaction: discord.Interaction, current: str):
    phases = [str(i) for i in range(1, 16)]
    return [
        app_commands.Choice(name=p, value=int(p))
        for p in phases if current in p
    ][:25]

# --- Autocompletion pour activer les systèmes ---
async def completer_activer(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    secteur_nom = list(ACTIVE_SYSTEMS.keys())[0]
    choices = []
    for ss, systemes in ACTIVE_SYSTEMS[secteur_nom].items():
        for sys, actif in systemes.items():
            if not actif and current.lower() in sys.lower():
                choices.append(app_commands.Choice(name=f"{sys} ({ss})", value=sys))
    return choices[:25]  # Discord limite à 25 choix max

# --- Autocompletion pour désactiver les systèmes ---
async def completer_desactiver(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    secteur_nom = list(ACTIVE_SYSTEMS.keys())[0]
    choices = []
    for ss, systemes in ACTIVE_SYSTEMS[secteur_nom].items():
        for sys, actif in systemes.items():
            if actif and current.lower() in sys.lower():
                choices.append(app_commands.Choice(name=f"{sys} ({ss})", value=sys))
    return choices[:25]

# ---------------------------------------------
# ---------------------------------------------
# ----------------- COMMANDES -----------------

# ----------------- COMMANDE /ajout -----------
@tree.command(name="ajout", description="Ajouter une partie/bataille", guild=guild)
@app_commands.describe(
    planete="Nom de la planète",
    gagnant="Faction gagnante ou 'Egalite'",
    choix_planete="Faction qui a choisi la planète",
    participant1="Premier participant",
    participant2="Deuxième participant",
    participant3="Troisième participant (facultatif)",
    phase="Phase dans laquelle ajouter la partie (optionnel)"
)
@app_commands.autocomplete(planete=autocomplete_planete, gagnant=autocomplete_faction,
                           choix_planete=autocomplete_faction, participant1=autocomplete_faction,
                           participant2=autocomplete_faction, participant3=autocomplete_faction,
                           phase=autocomplete_phase)
@admin_only()
async def ajout(interaction: discord.Interaction, planete: str, gagnant: str, choix_planete: str,
                participant1: str, participant2: str, participant3: Optional[str] = None,
                phase: Optional[int] = None):
    global CURRENT_PHASE, TOTAL_PARTIES, PHASES_HISTORY

    participants_list = [p for p in [participant1, participant2, participant3] if p]

    # --- Recherche de la planète dans la nouvelle hiérarchie ---
    systeme_found = None
    sous_secteur_found = None
    secteur_found = None

    for secteur, sous_secteurs in SECTORS.items():
        for sous_secteur, systemes in sous_secteurs.items():
            for systeme, planets in systemes.items():
                if planete in planets:
                    systeme_found = systeme
                    sous_secteur_found = sous_secteur
                    secteur_found = secteur
                    planet_info = planets[planete]
                    break
            if systeme_found:
                break
        if systeme_found:
            break

    if not systeme_found:
        await interaction.response.send_message(f"❌ Planète inconnue : {planete}", ephemeral=True)
        return

    gagnant = gagnant.capitalize()
    choix_planete = choix_planete.capitalize()

    # Validation participants
    for f in participants_list:
        if f not in FACTIONS:
            await interaction.response.send_message(f"❌ Faction inconnue : {f}", ephemeral=True)
            return
    if gagnant != "Egalite" and gagnant not in participants_list:
        await interaction.response.send_message(
            "❌ Le gagnant doit être parmi les participants ou 'Egalite'", ephemeral=True
        )
        return
    if choix_planete not in participants_list:
        await interaction.response.send_message(
            "❌ La faction qui choisit la planète doit être parmi les participants", ephemeral=True
        )
        return

    # Déterminer la phase
    target_phase = phase if phase is not None else CURRENT_PHASE["phase"]

    # Si on ajoute dans la phase en cours, on incrémente TOTAL_PARTIES
    if target_phase == CURRENT_PHASE["phase"]:
        for f in participants_list:
            TOTAL_PARTIES[f] += 1

    # Attribution des points et choix pour la planète
    for f in participants_list:
        # Points (conservés entre les phases)
        if f == gagnant:
            planet_info[f]["points"] += 3
        elif gagnant == "Egalite":
            planet_info[f]["points"] += 2
        else:
            planet_info[f]["points"] += 1

        # Batailles & choix (par phase)
        if target_phase == CURRENT_PHASE["phase"]:
            planet_info[f]["batailles"] += 1
            if f == choix_planete:
                planet_info[f]["choix"] += 1
        else:
            if target_phase not in PHASES_HISTORY:
                PHASES_HISTORY[target_phase] = {
                    "total_parties": {f: 0 for f in FACTIONS},
                    "choix_planete": {f: 0 for f in FACTIONS}
                }
            PHASES_HISTORY[target_phase]["total_parties"][f] += 1
            if f == choix_planete:
                PHASES_HISTORY[target_phase]["choix_planete"][f] += 1

    await interaction.response.send_message(
        f"✅ Partie ajoutée sur **{planete} ({systeme_found})** dans la phase {target_phase} !\n"
        f"Gagnant : **{gagnant}**, choix de la planète : **{choix_planete}**, participants : {', '.join(participants_list)}"
    )
    save_data()


# ----------------- Clôturer phase -----------------
@tree.command(
    name="cloture",
    description="Clôturer la phase en cours",
    guild=guild
)
@app_commands.describe(
    nouveau_sous_secteur="Nouveau sous-secteur (obligatoire si la phase locale est multiple de 3)"
)
@app_commands.autocomplete(nouveau_sous_secteur=autocomplete_sous_secteur)
@admin_only()
async def cloture(interaction: discord.Interaction, nouveau_sous_secteur: Optional[str] = None):
    global CURRENT_PHASE, TOTAL_PARTIES, PHASES_HISTORY, ACTIVE_SYSTEMS

    secteur = CURRENT_PHASE.get("secteur")
    ancien_ss = CURRENT_PHASE.get("sous_secteur")

    if not secteur or not ancien_ss:
        await interaction.response.send_message(
            "❌ Impossible de déterminer le secteur ou le sous-secteur courant.",
            ephemeral=True
        )
        return

    # --- Déterminer la phase locale actuelle ---
    local_history = PHASES_HISTORY.get(ancien_ss, {})
    if local_history:
        phase_local = max(int(k) for k in local_history.keys()) + 1
    else:
        phase_local = 1

    # --- Vérifier changement de sous-secteur ---
    if phase_local % 3 == 0:
        if not nouveau_sous_secteur:
            await interaction.response.send_message(
                "⚠️ Fin de phase 3 (guerre totale) : vous devez indiquer un nouveau sous-secteur.",
                ephemeral=True
            )
            return
        if nouveau_sous_secteur not in SECTORS.get(secteur, {}):
            await interaction.response.send_message(
                f"❌ Sous-secteur inconnu dans le secteur {secteur}.",
                ephemeral=True
            )
            return
    else:
        if nouveau_sous_secteur:
            await interaction.response.send_message(
                "⚠️ Vous ne pouvez pas changer de sous-secteur maintenant : la phase locale n'est pas multiple de 3.",
                ephemeral=True
            )
            return

    # --- Sauvegarde ordonnée des statistiques ---
    ordre_factions = ["Défenseur", "Envahisseur", "Pirate"]

    phase_data = {
        "total_parties": {f: TOTAL_PARTIES.get(f, 0) for f in ordre_factions},
        "choix_planete": {f: 0 for f in ordre_factions}
    }

    for systeme, planets in SECTORS[secteur][ancien_ss].items():
        for planet, data in planets.items():
            for f, stats in data.items():
                if f in phase_data["choix_planete"]:
                    phase_data["choix_planete"][f] += stats.get("choix", 0)

    # Créer le sous-secteur s'il n'existe pas encore
    if ancien_ss not in PHASES_HISTORY:
        PHASES_HISTORY[ancien_ss] = {}

    PHASES_HISTORY[ancien_ss][str(phase_local)] = phase_data

    # --- Réinitialiser compteurs ---
    TOTAL_PARTIES = {f: 0 for f in ordre_factions}
    for systeme, planets in SECTORS[secteur][ancien_ss].items():
        for planet, data in planets.items():
            for f in data:
                data[f]["batailles"] = 0
                data[f]["choix"] = 0

    # --- Si changement de sous-secteur ---
    if phase_local % 3 == 0 and nouveau_sous_secteur:
        # Désactivation ancien sous-secteur
        if secteur in ACTIVE_SYSTEMS and ancien_ss in ACTIVE_SYSTEMS[secteur]:
            for systeme in ACTIVE_SYSTEMS[secteur][ancien_ss]:
                ACTIVE_SYSTEMS[secteur][ancien_ss][systeme] = False

        # Activation nouveau sous-secteur
        if secteur not in ACTIVE_SYSTEMS:
            ACTIVE_SYSTEMS[secteur] = {}
        if nouveau_sous_secteur not in ACTIVE_SYSTEMS[secteur]:
            ACTIVE_SYSTEMS[secteur][nouveau_sous_secteur] = {}
        for systeme in SECTORS[secteur][nouveau_sous_secteur]:
            ACTIVE_SYSTEMS[secteur][nouveau_sous_secteur][systeme] = True

        CURRENT_PHASE["sous_secteur"] = nouveau_sous_secteur

        # Calculer la nouvelle phase pour le nouveau sous-secteur
        new_hist = PHASES_HISTORY.get(nouveau_sous_secteur, {})
        next_phase = max((int(k) for k in new_hist.keys()), default=0) + 1
        CURRENT_PHASE["phase"] = next_phase

        save_data()
        await interaction.response.send_message(
            f"✅ Phase {phase_local} clôturée dans **{ancien_ss}**.\n"
            f"➡️ Changement vers **{nouveau_sous_secteur}**, début de la **phase {next_phase}**."
        )
        return

    # --- Sinon, même sous-secteur ---
    CURRENT_PHASE["phase"] = phase_local + 1

    save_data()
    await interaction.response.send_message(
        f"✅ Phase {phase_local} clôturée. Nouvelle phase : **{CURRENT_PHASE['phase']}** "
        f"(Sous-secteur : **{ancien_ss}**)."
    )

# ----------------- Commande phase actuelle -----------------
@tree.command(
    name="phase",
    description="Afficher la phase en cours",
    guild=guild
)
async def phase(interaction: discord.Interaction):
    phase_num = CURRENT_PHASE.get("phase", 1)
    secteur = CURRENT_PHASE.get("secteur", "Inconnu")
    sous_secteur = CURRENT_PHASE.get("sous_secteur", "Inconnu")

    await interaction.response.send_message(
        f"📌 Phase actuelle : **{phase_num}**\n"
        f"🏛️ Secteur : **{secteur}**\n"
        f"🌌 Sous-secteur : **{sous_secteur}**"
    )


# ----------------- Commande stats phase -----------------
# --- Commande /phase_stats ---
@tree.command(
    name="phase_stats",
    description="Afficher les statistiques d'une phase spécifique dans un sous-secteur",
    guild=guild
)
@app_commands.describe(
    phase="Numéro de la phase (1 à 15)",
    sous_secteur="Sous-secteur à consulter"
)
@app_commands.autocomplete(
    phase=autocomplete_phase,
    sous_secteur=autocomplete_sous_secteur  # ✅ on réutilise ton autocomplete existant
)
async def phase_stats(interaction: discord.Interaction, phase: int, sous_secteur: str):
    # Vérification du sous-secteur
    if sous_secteur not in PHASES_HISTORY:
        await interaction.response.send_message(
            f"❌ Aucun historique trouvé pour le sous-secteur **{sous_secteur}**.",
            ephemeral=True
        )
        return

    # Vérification de la phase dans le sous-secteur
    if str(phase) not in PHASES_HISTORY[sous_secteur]:
        await interaction.response.send_message(
            f"❌ Phase {phase} inconnue dans le sous-secteur **{sous_secteur}**.",
            ephemeral=True
        )
        return

    data = PHASES_HISTORY[sous_secteur][str(phase)]

    # Création de l'embed
    embed = discord.Embed(
        title=f"📊 Statistiques - Phase {phase} ({sous_secteur})",
        color=discord.Color.blue()
    )

    # Ordre fixe : Défenseur → Envahisseur → Pirate
    ordered_factions = ["Défenseur", "Envahisseur", "Pirate"]
    for f in ordered_factions:
        total_parties = data["total_parties"].get(f, 0)
        choix_planete = data["choix_planete"].get(f, 0)
        embed.add_field(
            name=f"**{f}**",
            value=f"🎯 Parties disputées : **{total_parties}**\n🌍 Choix de planète : **{choix_planete}**",
            inline=False
        )

    await interaction.response.send_message(embed=embed)

# ----------------- STATS PLANETE -----------------
@tree.command(name="planete",
              description="Afficher les stats d’une planète",
              guild=guild)
@app_commands.describe(planete="Nom de la planète")
@app_commands.autocomplete(planete=autocomplete_planete)
async def planete(interaction: discord.Interaction, planete: str):
    # Parcours hiérarchique secteur → sous_secteur → système → planète
    planet_data = None
    systeme_found = None

    for secteur, sous_secteurs in SECTORS.items():
        for sous_secteur, systemes in sous_secteurs.items():
            for systeme, planets in systemes.items():
                if planete in planets:
                    planet_data = planets[planete]
                    systeme_found = systeme
                    break
            if planet_data:
                break
        if planet_data:
            break

    if planet_data is None:
        await interaction.response.send_message(f"❌ Planète inconnue : {planete}", ephemeral=True)
        return

    embed = discord.Embed(title=f"🪐 {systeme_found.upper()}", color=discord.Color.green())
    ICONS = {"Défenseur": "🛡️", "Envahisseur": "⚔️", "Pirate": "💀"}

    value = f"▪️\u2003🌏 **{planete}**\n"
    scores = {f: planet_data[f]["points"] for f in FACTIONS}
    max_score = max(scores.values())
    leaders = [f for f, pts in scores.items() if pts == max_score and pts > 0]

    for f in ["Défenseur", "Envahisseur", "Pirate"]:
        v = planet_data[f]
        suffix = " 🏆" if f in leaders and len(leaders) == 1 else " ⚖️" if f in leaders else ""
        value += f"▪️\u2003 \u2003{ICONS.get(f,'')}{suffix} {f} : **{v['points']} pts** | `{v['batailles']} batailles`\n"

    embed.add_field(name="", value=value, inline=False)
    await interaction.response.send_message(embed=embed)

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

    # Recherche du système
    system_data = None
    secteur_courant = None
    sous_secteur_courant = None
    for secteur, sous_secteurs in SECTORS.items():
        for sous_secteur, systemes in sous_secteurs.items():
            if systeme in systemes:
                system_data = systemes[systeme]
                secteur_courant = secteur
                sous_secteur_courant = sous_secteur
                break
        if system_data:
            break

    if not system_data:
        await interaction.response.send_message(f"❌ Système inconnu : {systeme}", ephemeral=True)
        return

    embed = discord.Embed(title=f"🪐 {systeme.upper()}", color=discord.Color.green())

    ICONS = {"Défenseur": "🛡️", "Envahisseur": "⚔️", "Pirate": "💀"}
    CASE_EMPTY = "▫️"
    CASE_PV = "🏅"
    CASE_BONUS = "🚩"
    SPACE = " "

    # Règles du système
    rules = SYSTEM_RULES.get(systeme, {})
    if not rules:
        rules = SYSTEM_RULES.get(secteur_courant, {}).get(sous_secteur_courant, {}).get(systeme, {})
    pv_thresholds = rules.get("pv_thresholds", [5])
    bonus_threshold = rules.get("bonus_threshold", 3)
    planet_values = rules.get("planets", {})
    max_points = max(pv_thresholds + [bonus_threshold])

    # --- Calcul de l'avancement par contrôle de planète ---
    total_pv = {f: 0 for f in ICONS.keys()}
    for planet, data in system_data.items():
        if planet not in planet_values:
            continue
        scores = {f: data[f]["points"] for f in ICONS.keys()}
        max_score = max(scores.values())
        leaders = [f for f, pts in scores.items() if pts == max_score]
        # Une planète est contrôlée seulement si un leader absolu
        if len(leaders) == 1:
            faction = leaders[0]
            total_pv[faction] += planet_values[planet]

    # Construction ligne des seuils
    alignment_prefix = " " * len(f"{ICONS['Défenseur']} : ")
    line_thresholds = alignment_prefix + CASE_EMPTY + SPACE
    for pos in range(1, max_points + 1):
        if pos in pv_thresholds:
            line_thresholds += CASE_PV + SPACE
        elif pos == bonus_threshold:
            line_thresholds += CASE_BONUS + SPACE
        else:
            line_thresholds += CASE_EMPTY + SPACE

    # Construction ligne des factions
    faction_lines = []
    for f, pts in total_pv.items():
        pos_line = [CASE_EMPTY] * (max_points + 1)
        pos_index = min(max(pts, 0), max_points)
        pos_line[pos_index] = ICONS[f]
        faction_lines.append(SPACE.join(pos_line))

    avancement_block = "**Avancement :**\n" + line_thresholds.strip() + "\n" + "\n".join(faction_lines)
    embed.add_field(name="", value=avancement_block, inline=False)

    # --- Détails des planètes ---
    lines = []
    for planet, data in system_data.items():
        value_icon = PLANET_VALUE_ICONS.get(planet_values.get(planet, 0), "")
        lines.append(f"▪️ 🌏 **{planet}** {value_icon}")
        scores = {f: data[f]["points"] for f in ICONS.keys()}
        max_score = max(scores.values())
        leaders = [f for f, pts in scores.items() if pts == max_score and pts > 0]
        for f in ICONS.keys():
            v = data[f]
            suffix = " 🏆" if f in leaders and len(leaders) == 1 else " ⚖️" if f in leaders else ""
            lines.append(f"▪️  {ICONS[f]}{suffix} {f} : **{v['points']} pts** | `{v['batailles']} batailles`")
        lines.append("")

    # Découpage en chunks
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

    ICONS = {"Défenseur": "🛡️", "Envahisseur": "⚔️", "Pirate": "💀"}
    CASE_EMPTY = "▫️"
    CASE_PV = "🏅"
    CASE_BONUS = "🚩"
    SPACE = " "
    MAX_FIELD_LEN = 1000
    MAX_FIELDS = 25
    systems_displayed = 0

    # Parcours hiérarchique secteurs → sous_secteurs → systèmes
    for secteur, sous_secteurs in SECTORS.items():
        for sous_secteur, systemes in sous_secteurs.items():
            for systeme, system_data in systemes.items():
                if not ACTIVE_SYSTEMS.get(secteur, {}).get(sous_secteur, {}).get(systeme, True):
                    continue

                rules = SYSTEM_RULES.get(secteur, {}).get(sous_secteur, {}).get(systeme, {})
                pv_thresholds = rules.get("pv_thresholds", [5])
                bonus_threshold = rules.get("bonus_threshold", 3)
                planet_values = rules.get("planets", {})
                max_points = max(pv_thresholds + [bonus_threshold])

                # --- Avancement ---
                total_pv = {f: 0 for f in ICONS.keys()}
                for planet, data in system_data.items():
                    if planet not in planet_values:
                        continue
                    scores = {f: data[f]["points"] for f in ICONS.keys()}
                    max_score = max(scores.values())
                    if max_score <= 0:
                        continue
                    leaders = [f for f, pts in scores.items() if pts == max_score]
                    if len(leaders) == 1:
                        total_pv[leaders[0]] += planet_values[planet]

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

                avancement_block = "**Avancement :**\n" + line_avancement.strip() + "\n" + "\n".join(faction_lines)

                # --- Ajout embed ---
                if len(embed.fields) < MAX_FIELDS:
                    embed.add_field(name=f"🪐 {systeme.upper()}", value=avancement_block, inline=False)
                    systems_displayed += 1

                # --- Lignes planètes ---
                planet_lines = []
                for planet, data in system_data.items():
                    value_icon = PLANET_VALUE_ICONS.get(planet_values.get(planet, 0), "")
                    planet_lines.append(f"▪️ 🌏 **{planet}** {value_icon}")
                    scores = {f: data[f]["points"] for f in data.keys()}
                    max_score = max(scores.values())
                    leaders = [f for f, pts in scores.items() if pts == max_score and pts > 0]

                    for f in ["Défenseur", "Envahisseur", "Pirate"]:
                        v = data[f]
                        suffix = " 🏆" if f in leaders and len(leaders) == 1 else " ⚖️" if f in leaders else ""
                        planet_lines.append(f"▪️  {ICONS[f]}{suffix} {f} : **{v['points']} pts** | `{v['batailles']} batailles`")
                    planet_lines.append("")

                # --- Découpage en chunks ---
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
    description="Modifier directement les points ou batailles d’une faction sur une planète",
    guild=guild
)
@app_commands.describe(
    planete="Nom de la planète",
    faction="Faction à modifier",
    points="Points de victoire (optionnel, 0-20)",
    batailles="Nombre de batailles (optionnel, 0-20)"
)
@app_commands.autocomplete(
    planete=autocomplete_planete,
    faction=autocomplete_faction,
    points=autocomplete_numbers,
    batailles=autocomplete_numbers
)
@admin_only()
async def modif(interaction: discord.Interaction,
                planete: str,
                faction: str,
                points: Optional[int] = None,
                batailles: Optional[int] = None):
    faction = faction.capitalize()
    
    # Recherche de la planète dans la hiérarchie
    planet_info = None
    for secteur, sous_secteurs in SECTORS.items():
        for sous_secteur, systemes in sous_secteurs.items():
            for systeme_name, planets in systemes.items():
                if planete in planets:
                    planet_info = (secteur, sous_secteur, systeme_name, planets[planete])
                    break
            if planet_info:
                break
        if planet_info:
            break

    if planet_info is None:
        await interaction.response.send_message(f"❌ Planète inconnue : {planete}", ephemeral=True)
        return

    secteur_found, sous_secteur_found, systeme_found, planet_data = planet_info

    if faction not in FACTIONS:
        await interaction.response.send_message(f"❌ Faction inconnue : {faction}", ephemeral=True)
        return

    # Mise à jour des stats
    if points is not None:
        planet_data[faction]["points"] = points

    if batailles is not None:
        delta = batailles - planet_data[faction]["batailles"]
        planet_data[faction]["batailles"] = batailles
        TOTAL_PARTIES[faction] += delta

    await interaction.response.send_message(
        f"✅ Stats modifiées pour **{faction}** sur **{planete}** ({systeme_found}) : points={points} batailles={batailles}"
    )
    save_data()


# ----------------- AUTRES COMMANDES -----------------
ICONS = {"Défenseur": "🛡️", "Envahisseur": "⚔️", "Pirate": "💀"}

@tree.command(
    name="faction",
    description="Afficher les statistiques de toutes les factions ou d'une faction précise",
    guild=guild
)
@app_commands.describe(faction="Nom de la faction (Défenseur, Envahisseur, Pirate)")
@app_commands.choices(faction=[
    app_commands.Choice(name="Défenseur", value="Défenseur"),
    app_commands.Choice(name="Envahisseur", value="Envahisseur"),
    app_commands.Choice(name="Pirate", value="Pirate")
])
async def faction(interaction: discord.Interaction, faction: Optional[app_commands.Choice[str]] = None):
    # Déterminer quelles factions afficher
    factions_to_show = [faction.value] if faction else ["Défenseur", "Envahisseur", "Pirate"]

    secteur_courant = CURRENT_PHASE.get("secteur", "Inconnu")
    sous_secteur_courant = CURRENT_PHASE.get("sous_secteur", "Inconnu")
    phase_courante = CURRENT_PHASE.get("phase", 1)

    # --- Embed principal ---
    embed = discord.Embed(title="📊 Rapport stratégique", color=discord.Color.dark_blue())

    # Champ unique pour secteur / sous-secteur / phase
    embed.add_field(
        name="",
        value=(
            f"    🌌 Secteur : {secteur_courant}\n"
            f"    🗺️ Sous-secteur : {sous_secteur_courant}\n"
            f"    🕹️ Phase actuelle : {phase_courante}"
        ),
        inline=False
    )

    for faction_nom in factions_to_show:
        total_batailles = 0
        batailles_cette_phase = 0
        choix_planete = 0
        planètes_gagnées = 0
        systèmes_domines = {}

        # --- Total batailles historique ---
        for ss, phases in PHASES_HISTORY.items():
            for phase_data in phases.values():
                total_batailles += phase_data["total_parties"].get(faction_nom, 0)

        # --- Batailles et choix en cours ---
        if secteur_courant in SECTORS and sous_secteur_courant in SECTORS[secteur_courant]:
            for systeme, planets in SECTORS[secteur_courant][sous_secteur_courant].items():
                system_points = 0
                for planete, data in planets.items():
                    # Batailles cette phase
                    batailles_cette_phase += data[faction_nom]["batailles"]
                    total_batailles += data[faction_nom]["batailles"]

                    # Choix de planète cette phase
                    choix_planete += data[faction_nom]["choix"]

                    # Vérification planète contrôlée
                    max_points = max(fdata["points"] for fdata in data.values())
                    leaders = [f for f, fdata in data.items() if fdata["points"] == max_points]
                    if len(leaders) == 1 and leaders[0] == faction_nom:
                        planètes_gagnées += 1
                        system_points += 1

                if system_points > 0:
                    systèmes_domines[f"{systeme} ({sous_secteur_courant})"] = system_points

        # --- Embed par faction ---
        color = discord.Color.blue() if faction_nom == "Défenseur" else \
                discord.Color.red() if faction_nom == "Envahisseur" else \
                discord.Color.dark_gold()

        value = (
            f"    {ICONS[faction_nom]} **{faction_nom}**\n"
            f"        💥 Total batailles : {total_batailles}\n"
            f"        ⚡ Batailles cette phase : {batailles_cette_phase}\n"
            f"        🎯  Choix de planète cette phase : {choix_planete}"
        )

        # Planètes contrôlées et influence par système seulement si faction spécifique
        if faction:
            value += f"\n        🏆 Planètes contrôlées : {planètes_gagnées}"
            if systèmes_domines:
                desc = "\n".join([f"        • {sys} ({pts} planètes gagnées)" for sys, pts in systèmes_domines.items()])
            else:
                desc = "        Aucun système dominé actuellement."
            value += f"\n        🌌 Influence par système:\n{desc}"

        embed.add_field(name="\u200b", value=value, inline=False)
        embed.color = color  # Mettre la couleur de la faction si c'est une seule

    await interaction.response.send_message(embed=embed)



# ----------------- TIRAGE AU SORT D'HONNEUR -----------------
@tree.command(
    name="honneur",
    description="Tirer un post d'honneur parmi les mots-clés donnés",
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
    mot6: Optional[str] = None):
    
    await interaction.response.defer(thinking=True, ephemeral=False)

    # --- Préparer la liste des mots-clés ---
    keywords = [kw.lower() for kw in [mot1, mot2, mot3, mot4, mot5, mot6] if kw]
    if not keywords:
        await interaction.followup.send("⚠️ Vous devez fournir au moins un mot-clé.")
        return

    matched_threads = []

    # --- Parcours des forums ---
    for forum_id in FORUM_IDS:
        forum = bot.get_channel(forum_id)
        if not forum:
            print(f"⚠️ Forum introuvable : {forum_id}")
            continue
        try:
            active_threads = list(forum.threads)
            archived_threads = [t async for t in forum.archived_threads(limit=None)]
            threads = active_threads + archived_threads

            for thread in threads:
                if not thread.applied_tags:
                    continue
                thread_tags = set(tag.name.lower() for tag in thread.applied_tags)

                # Vérification stricte selon la règle :
                # - tous les tags du thread doivent être dans les keywords fournis
                # - au moins un tag du thread doit correspondre à un keyword
                if thread_tags and thread_tags.issubset(set(keywords)) and thread_tags.intersection(keywords):
                    matched_threads.append(thread)

        except Exception as e:
            print(f"⚠️ Erreur lors de la lecture du forum {forum_id} : {e}")

    # --- Vérification nombre minimal de résultats ---
    if len(matched_threads) < 3:
        await interaction.followup.send(
            "⚠️ Moins de 3 honneurs trouvés. Vérifiez les tableaux d'honneur ou contactez un admin."
        )
        return

    # --- Tirage aléatoire ---
    chosen_thread = random.choice(matched_threads)
    thread_url = f"https://discord.com/channels/{interaction.guild_id}/{chosen_thread.id}"

    # --- Création de l'embed ---
    embed = discord.Embed(
        title=f"🎖️ Honneur tiré au hasard parmi {len(matched_threads)} traits",
        color=discord.Color.gold()
    )
    embed.add_field(name="Nom du post", value=chosen_thread.name, inline=False)
    embed.add_field(name="Lien", value=f"[Ouvrir le post]({thread_url})", inline=False)
    if chosen_thread.applied_tags:
        embed.add_field(name="Tags", value=", ".join(tag.name for tag in chosen_thread.applied_tags), inline=False)

    await interaction.followup.send(embed=embed)


# ----------------- MISE À JOUR DES TAGS D’HONNEUR -----------------
@tree.command(
    name="maj_honneurs",
    description="Met à jour la liste des mots-clés d'honneur depuis les tags des forums",
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


# ----------------- LISTE DES SYSTÈMES Actifs-----------------
@tree.command(
    name="liste_sys",
    description="Liste les systèmes actifs d'un secteur",
    guild=guild
)
@app_commands.describe(
    affichage="Choisir l'affichage des systèmes"
)
@app_commands.choices(
    affichage=[
        app_commands.Choice(name="ActifSeul", value=0),
        app_commands.Choice(name="Actifs/Inactifs", value=1)
    ]
)
async def liste_sys(
    interaction: discord.Interaction, 
    affichage: Optional[app_commands.Choice[int]] = None):

    # Par défaut, ActifSeul
    inactifs = bool(affichage.value) if affichage else False

    # Secteur actif
    secteur_nom = list(ACTIVE_SYSTEMS.keys())[0]

    # Filtrer les sous-secteurs
    sous_secteurs_actifs = {
        ss: {s: a for s, a in systemes.items() if a or inactifs}
        for ss, systemes in ACTIVE_SYSTEMS[secteur_nom].items()
    }
    # Supprimer les sous-secteurs vides
    sous_secteurs_actifs = {ss: sys for ss, sys in sous_secteurs_actifs.items() if sys}

    # Vérification d'erreur
    if len(sous_secteurs_actifs) > 1:
        message = f"⚠️ **Erreur : plusieurs sous-secteurs détectés dans le secteur {secteur_nom}.**\n"
        message += "Voici la liste complète des systèmes pour diagnostic :\n\n"
        for ss, systemes in sous_secteurs_actifs.items():
            message += f"📂 Sous-secteur : {ss}\n"
            for systeme, actif in systemes.items():
                etat = "🟢 actif" if actif else "🔴 inactif"
                message += f" 🪐 {systeme} ({etat})\n"
            message += "\n"
        await interaction.response.send_message(message)
        return

    # Cas normal : un seul sous-secteur
    sous_secteur = list(sous_secteurs_actifs.keys())[0]
    systemes = sous_secteurs_actifs[sous_secteur]

    message = f"🌌 **Secteur : {secteur_nom}**\n\n"
    message += f"📂 **Sous-secteur : {sous_secteur}**\n"
    for systeme, actif in systemes.items():
        etat = "🟢 actif" if actif else "🔴 inactif"
        message += f" 🪐 {systeme} ({etat})\n"

    await interaction.response.send_message(message)

# --- Commande activer ---
@tree.command(
    name="activer_sys",
    description="Activer un système",
    guild=guild
)
@app_commands.describe(
    systeme="Nom du système à activer"
)
@app_commands.autocomplete(systeme=completer_activer)
@admin_only()
async def activer_sys(interaction: discord.Interaction, systeme: str):
    secteur_nom = list(ACTIVE_SYSTEMS.keys())[0]
    for ss, systemes in ACTIVE_SYSTEMS[secteur_nom].items():
        if systeme in systemes:
            if systemes[systeme]:
                await interaction.response.send_message(f"🟢 Le système **{systeme}** est déjà activé.")
            else:
                systemes[systeme] = True
                await interaction.response.send_message(f"🟢 Le système **{systeme}** a été activé dans le sous-secteur **{ss}**.")
            return
    await interaction.response.send_message(f"❌ Le système **{systeme}** n'a pas été trouvé dans le secteur {secteur_nom}.")

# --- Commande désactiver ---
@tree.command(
    name="desactiver_sys",
    description="Désactiver un système",
    guild=guild
)
@app_commands.describe(
    systeme="Nom du système à désactiver"
)
@app_commands.autocomplete(systeme=completer_desactiver)
@admin_only()
async def desactiver_sys(interaction: discord.Interaction, systeme: str):
    secteur_nom = list(ACTIVE_SYSTEMS.keys())[0]
    for ss, systemes in ACTIVE_SYSTEMS[secteur_nom].items():
        if systeme in systemes:
            if not systemes[systeme]:
                await interaction.response.send_message(f"🔴 Le système **{systeme}** est déjà désactivé.")
            else:
                systemes[systeme] = False
                await interaction.response.send_message(f"🔴 Le système **{systeme}** a été désactivé dans le sous-secteur **{ss}**.")
            return
    await interaction.response.send_message(f"❌ Le système **{systeme}** n'a pas été trouvé dans le secteur {secteur_nom}.")

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
            "🟣 **`/ajout`** — Ajouter une partie ou bataille.\n"
            "🟣 **`/cloture`** — Clôturer la phase en cours et passer à la suivante.\n"
            "🟢 **`/phase`** — Afficher la phase en cours.\n"
            "🟢 **`/phase_stats`** — Voir les statistiques d’une phase précédente."
        ),
        inline=False
    )

    # --- Statistiques ---
    embed.add_field(
        name="📊 Statistiques",
        value=(
            "🟢 **`/planete`** — Afficher les stats détaillées d’une planète.\n"
            "🟢 **`/systeme`** — Afficher les stats de toutes les planètes d’un système.\n"
            "🟢 **`/stats`** — Afficher les stats de toutes les planètes de tous les systèmes.\n"
            "🟢 **`/factions`** — Voir les totaux des batailles et choix de planète par faction."
        ),
        inline=False
    )

    # --- Gestion manuelle et systèmes ---
    embed.add_field(
        name="🛠️ Gestion et modifications",
        value=(
            "🟣 **`/modif`** — Modifier manuellement les points ou batailles d’une faction.\n"
            "🟢 **`/liste_sys`** — Liste tous les systèmes et leurs planètes.\n"
            "🟣 **`/activer_sys`** — Activer un système\n"
            "🟣 **`/desactiver_sys`** — Désactiver un système"
        ),
        inline=False
    )

    # --- Honneurs ---
    embed.add_field(
        name="🏅 Tableau d'Honneur",
        value=(
            "🟢 **`/honneur`** — Tire au hasard un post d'honneur parmi les mots-clés donnés.\n"
            "🟢 **`/maj_honneurs`** — Met à jour la liste des mots-clés d’honneur à partir des tags des forums."
        ),
        inline=False
    )

    # --- Divers ---
    embed.add_field(
        name="ℹ️ Divers",
        value="🟢 **`/h`** — Afficher cette liste de commandes.",
        inline=False
    )

    # Footer avec lexique de couleurs
    embed.set_footer(
        text="🟢 Vert = commandes actives pour tout le monde.\n🟣 Violet = commandes réservées aux admins",
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
