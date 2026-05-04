"""
Agent Orchestrateur - coordonne l'exécution de tous les scrapers du projet.
Lance les scrapers, surveille les erreurs, et consolide les données en un seul fichier JSON.
Inclut une mémoire persistante : historique des runs, état des données, alertes de fraîcheur.

Usage:
    python agent_orchestrateur.py                  # lancer tous les scrapers
    python agent_orchestrateur.py --scraper carrefour
    python agent_orchestrateur.py --consolider      # consolider uniquement
    python agent_orchestrateur.py --memoire         # afficher la mémoire
"""

import subprocess
import sys
import json
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ── Configuration des scrapers ─────────────────────────────────────────────────

SCRAPERS = {
    "carrefour": {
        "script": "scraper_carrefour.py",
        "sortie": "carrefour.json",
        "description": "Carrefour Tunisie (GraphQL, ~7000 produits)",
    },
    "carrefour_simple": {
        "script": "car.py",
        "sortie": "carrefour.json",
        "description": "Carrefour Tunisie - version simplifiée",
    },
    "otrity": {
        "script": "scraper_otority.py",
        "sortie": "otrity.json",
        "description": "Otrity (WooCommerce)",
    },
    "mg": {
        "script": "mg.py",
        "sortie": "mg.json",
        "description": "MG Tunisie (PrestaShop)",
    },
}

FICHIER_CONSOLIDE = "tous_les_produits.json"
DOSSIER_MEMOIRE = Path("memory")
FICHIER_MEMOIRE = DOSSIER_MEMOIRE / "orchestrateur_memory.json"
FRAICHEUR_MAX_HEURES = 24  # Alerter si les données ont plus de 24h


# ── Mémoire persistante ────────────────────────────────────────────────────────

def _charger_memoire() -> dict:
    """Charge la mémoire depuis le disque. Si absente, analyse le projet et crée la mémoire."""
    if FICHIER_MEMOIRE.exists():
        try:
            with open(FICHIER_MEMOIRE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Mémoire absente → analyser le projet et créer la mémoire initiale
    log("Aucune mémoire trouvée — analyse du projet en cours...", "WARN")
    memoire = _creer_memoire_initiale()
    _sauvegarder_memoire(memoire)
    log(f"Mémoire créée: {FICHIER_MEMOIRE}")
    return memoire


def _creer_memoire_initiale() -> dict:
    """Analyse le projet et crée une mémoire initiale."""
    DOSSIER_MEMOIRE.mkdir(exist_ok=True)

    # Scanner les fichiers JSON existants
    etat_donnees = {}
    for nom, config in SCRAPERS.items():
        chemin = Path(config["sortie"])
        if chemin.exists():
            try:
                with open(chemin, encoding="utf-8") as f:
                    data = json.load(f)
                nb = len(data) if isinstance(data, list) else 0
                mtime = datetime.fromtimestamp(chemin.stat().st_mtime).isoformat()
                etat_donnees[nom] = {"nb_produits": nb, "derniere_mise_a_jour": mtime, "fichier": config["sortie"]}
            except Exception:
                etat_donnees[nom] = {"nb_produits": 0, "derniere_mise_a_jour": None, "fichier": config["sortie"]}
        else:
            etat_donnees[nom] = {"nb_produits": 0, "derniere_mise_a_jour": None, "fichier": config["sortie"]}

    # Vérifier quels scripts existent
    scripts_presents = {nom: Path(cfg["script"]).exists() for nom, cfg in SCRAPERS.items()}

    return {
        "version": "1.0",
        "cree_le": datetime.now().isoformat(),
        "description_projet": "Scrapers e-commerce Tunisie: Carrefour, Otrity, MG Tunisie",
        "scrapers_disponibles": scripts_presents,
        "etat_donnees": etat_donnees,
        "historique_runs": [],
        "statistiques_globales": {
            "total_runs": 0,
            "runs_reussis": 0,
            "runs_echoues": 0,
            "dernier_run": None,
        },
        "alertes": [],
    }


def _sauvegarder_memoire(memoire: dict):
    """Sauvegarde la mémoire sur le disque."""
    DOSSIER_MEMOIRE.mkdir(exist_ok=True)
    with open(FICHIER_MEMOIRE, "w", encoding="utf-8") as f:
        json.dump(memoire, f, ensure_ascii=False, indent=2)


def _mettre_a_jour_memoire(memoire: dict, rapports: list, nb_consolide: int):
    """Met à jour la mémoire après un run."""
    maintenant = datetime.now().isoformat()

    # Mettre à jour l'état des données
    for rapport in rapports:
        nom = rapport["nom"]
        if rapport["succes"] and nom in memoire["etat_donnees"]:
            memoire["etat_donnees"][nom]["nb_produits"] = rapport.get("nb_produits", 0)
            memoire["etat_donnees"][nom]["derniere_mise_a_jour"] = maintenant

    # Ajouter au journal
    entree_run = {
        "date": maintenant,
        "scrapers": [
            {"nom": r["nom"], "succes": r["succes"], "nb_produits": r.get("nb_produits", 0)}
            for r in rapports
        ],
        "total_consolide": nb_consolide,
    }
    memoire["historique_runs"].append(entree_run)
    # Conserver seulement les 50 derniers runs
    memoire["historique_runs"] = memoire["historique_runs"][-50:]

    # Statistiques globales
    stats = memoire["statistiques_globales"]
    stats["total_runs"] += 1
    stats["runs_reussis"] += sum(1 for r in rapports if r["succes"])
    stats["runs_echoues"] += sum(1 for r in rapports if not r["succes"])
    stats["dernier_run"] = maintenant

    # Générer des alertes
    memoire["alertes"] = _generer_alertes(memoire)

    _sauvegarder_memoire(memoire)


def _generer_alertes(memoire: dict) -> list:
    """Génère des alertes basées sur l'état des données."""
    alertes = []
    maintenant = datetime.now()

    for nom, etat in memoire["etat_donnees"].items():
        if etat.get("derniere_mise_a_jour"):
            derniere_maj = datetime.fromisoformat(etat["derniere_mise_a_jour"])
            age_heures = (maintenant - derniere_maj).total_seconds() / 3600
            if age_heures > FRAICHEUR_MAX_HEURES:
                alertes.append({
                    "type": "donnees_perimees",
                    "scraper": nom,
                    "age_heures": round(age_heures, 1),
                    "message": f"Les données de '{nom}' ont {round(age_heures)}h (seuil: {FRAICHEUR_MAX_HEURES}h)",
                })
        elif memoire.get("scrapers_disponibles", {}).get(nom):
            alertes.append({
                "type": "donnees_manquantes",
                "scraper": nom,
                "message": f"Aucune donnée pour '{nom}' — scraper disponible mais jamais exécuté",
            })

    return alertes


def afficher_memoire(memoire: dict):
    """Affiche le contenu de la mémoire de l'agent."""
    print("\n" + "═" * 60)
    print("  MÉMOIRE DE L'AGENT ORCHESTRATEUR")
    print("═" * 60)
    print(f"  Créée le  : {memoire.get('cree_le', 'N/A')[:19]}")

    stats = memoire.get("statistiques_globales", {})
    print(f"  Runs total: {stats.get('total_runs', 0)} ({stats.get('runs_reussis', 0)} réussis / {stats.get('runs_echoues', 0)} échoués)")
    print(f"  Dernier   : {(stats.get('dernier_run') or 'Jamais')[:19]}")

    print("\n  État des données:")
    for nom, etat in memoire.get("etat_donnees", {}).items():
        date = (etat.get("derniere_mise_a_jour") or "jamais")[:19]
        print(f"    {nom:22} {etat.get('nb_produits', 0):6} produits  (maj: {date})")

    alertes = memoire.get("alertes", [])
    if alertes:
        print(f"\n  Alertes ({len(alertes)}):")
        for a in alertes:
            print(f"    ⚠ {a['message']}")

    historique = memoire.get("historique_runs", [])
    if historique:
        print(f"\n  Derniers runs ({min(3, len(historique))}):")
        for run in historique[-3:]:
            date = run["date"][:19]
            consolide = run.get("total_consolide", 0)
            print(f"    {date}  →  {consolide} produits consolidés")

    print("═" * 60 + "\n")


# ── Utilitaires ────────────────────────────────────────────────────────────────

def log(message: str, niveau: str = "INFO"):
    horodatage = datetime.now().strftime("%H:%M:%S")
    prefixes = {"INFO": "✓", "ERREUR": "✗", "WARN": "⚠", "DEBUT": "▶"}
    print(f"[{horodatage}] {prefixes.get(niveau, '·')} {message}")


def charger_json(chemin: str) -> list:
    path = Path(chemin)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log(f"Impossible de lire {chemin}: {e}", "ERREUR")
        return []


def lancer_scraper(nom: str) -> dict:
    config = SCRAPERS.get(nom)
    if not config:
        return {"nom": nom, "succes": False, "erreur": "Scraper inconnu"}

    script = config["script"]
    if not Path(script).exists():
        return {"nom": nom, "succes": False, "erreur": f"Fichier '{script}' introuvable"}

    log(f"Lancement de {nom} ({config['description']})", "DEBUT")
    debut = datetime.now()

    try:
        resultat = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        duree = (datetime.now() - debut).seconds

        if resultat.returncode == 0:
            produits = charger_json(config["sortie"])
            log(f"{nom} terminé en {duree}s — {len(produits)} produits dans {config['sortie']}")
            return {"nom": nom, "succes": True, "duree_secondes": duree, "nb_produits": len(produits), "fichier_sortie": config["sortie"]}
        else:
            erreur = resultat.stderr[-500:] if resultat.stderr else "Erreur inconnue"
            log(f"{nom} a échoué après {duree}s: {erreur}", "ERREUR")
            return {"nom": nom, "succes": False, "duree_secondes": duree, "erreur": erreur}

    except subprocess.TimeoutExpired:
        log(f"{nom} dépassé le délai (1h)", "ERREUR")
        return {"nom": nom, "succes": False, "erreur": "Délai dépassé (1h)"}
    except Exception as e:
        log(f"{nom} erreur inattendue: {e}", "ERREUR")
        return {"nom": nom, "succes": False, "erreur": str(e)}


def consolider_donnees() -> int:
    tous = []
    for config in SCRAPERS.values():
        produits = charger_json(config["sortie"])
        if produits:
            log(f"  {config['sortie']}: {len(produits)} produits chargés")
            tous.extend(produits)

    if not tous:
        log("Aucun produit à consolider.", "WARN")
        return 0

    vus = set()
    dedupliques = []
    for p in tous:
        cle = (p.get("nom", ""), p.get("pointDeVente", ""))
        if cle not in vus:
            vus.add(cle)
            dedupliques.append(p)

    doublons = len(tous) - len(dedupliques)
    log(f"Consolidation: {len(tous)} → {len(dedupliques)} produits ({doublons} doublons supprimés)")

    with open(FICHIER_CONSOLIDE, "w", encoding="utf-8") as f:
        json.dump(dedupliques, f, ensure_ascii=False, indent=2)

    log(f"Fichier consolidé: {FICHIER_CONSOLIDE} ({len(dedupliques)} produits)")
    return len(dedupliques)


def afficher_rapport(rapports: list):
    print("\n" + "═" * 55)
    print("  RAPPORT D'EXÉCUTION")
    print("═" * 55)
    total_produits = 0
    for r in rapports:
        statut = "✓ OK" if r["succes"] else "✗ ÉCHEC"
        produits = r.get("nb_produits", 0)
        duree = r.get("duree_secondes", 0)
        total_produits += produits
        print(f"  {statut:8} | {r['nom']:20} | {produits:5} produits | {duree}s")
        if not r["succes"]:
            print(f"           Erreur: {r.get('erreur', '')[:60]}")
    print("═" * 55)
    print(f"  Total: {total_produits} produits")
    print("═" * 55 + "\n")


# ── Point d'entrée ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Agent Orchestrateur avec mémoire persistante")
    parser.add_argument("--scraper", choices=list(SCRAPERS.keys()), help="Lancer un scraper spécifique")
    parser.add_argument("--consolider", action="store_true", help="Consolider les JSON existants")
    parser.add_argument("--liste", action="store_true", help="Lister les scrapers disponibles")
    parser.add_argument("--memoire", action="store_true", help="Afficher la mémoire de l'agent")
    args = parser.parse_args()

    # Chargement de la mémoire (création si absente)
    memoire = _charger_memoire()

    # Afficher les alertes de fraîcheur
    alertes = memoire.get("alertes", [])
    if alertes:
        for alerte in alertes:
            log(alerte["message"], "WARN")

    if args.memoire:
        afficher_memoire(memoire)
        return

    if args.liste:
        print("\nScrapers disponibles:")
        for nom, cfg in SCRAPERS.items():
            etat = memoire["etat_donnees"].get(nom, {})
            nb = etat.get("nb_produits", 0)
            date = (etat.get("derniere_mise_a_jour") or "jamais")[:19]
            print(f"  {nom:22} → {cfg['description']} ({nb} produits, maj: {date})")
        return

    if args.consolider:
        log("Consolidation des données existantes...")
        nb = consolider_donnees()
        return

    scrapers_a_lancer = [args.scraper] if args.scraper else list(SCRAPERS.keys())
    if not args.scraper and "carrefour_simple" in scrapers_a_lancer:
        scrapers_a_lancer.remove("carrefour_simple")

    print(f"\n{'═'*55}")
    print(f"  AGENT ORCHESTRATEUR — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"  Scrapers: {', '.join(scrapers_a_lancer)}")
    print(f"{'═'*55}\n")

    rapports = []
    for nom in scrapers_a_lancer:
        rapport = lancer_scraper(nom)
        rapports.append(rapport)

    afficher_rapport(rapports)

    nb_consolide = 0
    if any(r["succes"] for r in rapports):
        log("Consolidation des données...")
        nb_consolide = consolider_donnees()
    else:
        log("Aucun scraper réussi — consolidation ignorée.", "WARN")

    # Mettre à jour la mémoire avec les résultats du run
    _mettre_a_jour_memoire(memoire, rapports, nb_consolide)
    log(f"Mémoire mise à jour: {FICHIER_MEMOIRE}")


if __name__ == "__main__":
    main()
