"""
Agent IA - interface intelligente pour analyser les données de scraping.
Utilise l'API Claude avec outils + mémoire persistante.

Mémoire persistante (memory/):
  - projet.md       : description du projet analysée automatiquement
  - historique.json : requêtes passées et résultats mémorisés

Au démarrage: si la mémoire est absente, Claude analyse le code source et crée la mémoire.
En fin de session: la mémoire est mise à jour avec les nouvelles connaissances.

Prérequis:
    pip install anthropic
    set ANTHROPIC_API_KEY=votre_clé

Usage:
    python agent_ia.py
"""

import anthropic
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────────

MODEL = "claude-opus-4-7"
DOSSIER_MEMOIRE = Path("memory")
FICHIER_MEMOIRE_PROJET = DOSSIER_MEMOIRE / "projet.md"
FICHIER_MEMOIRE_HISTORIQUE = DOSSIER_MEMOIRE / "historique.json"

FICHIERS_JSON = {
    "carrefour": "carrefour.json",
    "otrity": "otrity.json",
    "mg": "mg.json",
    "tous": "tous_les_produits.json",
}

SCRAPERS = {
    "carrefour": "scraper_carrefour.py",
    "otrity": "scraper_otority.py",
    "mg": "mg.py",
}

# ── Gestion de la mémoire ──────────────────────────────────────────────────────

def _lire_code_projet() -> str:
    """Lit le contenu des fichiers clés du projet pour analyse."""
    contenu = []
    fichiers_a_lire = ["scraper_carrefour.py", "scraper_otority.py", "mg.py", "aziza.py"]
    for fichier in fichiers_a_lire:
        path = Path(fichier)
        if path.exists():
            try:
                texte = path.read_text(encoding="utf-8")[:3000]
                contenu.append(f"=== {fichier} ===\n{texte}\n")
            except Exception:
                pass
    return "\n".join(contenu)


def creer_memoire_projet(client: anthropic.Anthropic) -> str:
    """Claude analyse le code source et génère la mémoire du projet."""
    print("  Analyse du code source en cours...")
    code = _lire_code_projet()

    # Collecter l'état des fichiers JSON
    etat_donnees = []
    for nom, fichier in FICHIERS_JSON.items():
        path = Path(fichier)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                nb = len(data) if isinstance(data, list) else 0
                mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
                etat_donnees.append(f"- {fichier}: {nb} produits (modifié le {mtime})")
            except Exception:
                etat_donnees.append(f"- {fichier}: présent mais illisible")
        else:
            etat_donnees.append(f"- {fichier}: absent")

    prompt = f"""Tu es un assistant expert en scraping. Analyse ce projet Python de scraping e-commerce tunisien.

FICHIERS JSON DISPONIBLES:
{chr(10).join(etat_donnees)}

CODE SOURCE (extraits):
{code}

Génère une mémoire structurée en Markdown contenant:
1. **Résumé du projet** (2-3 phrases)
2. **Scrapers disponibles** (nom, site cible, technologie, fichier de sortie)
3. **Schéma des données** (champs clés du modèle Produit)
4. **État des données** (quels fichiers JSON sont disponibles)
5. **Points importants** (techniques spécifiques, déduplications, formats de prix)

Sois concis et précis. Cette mémoire sera injectée dans le contexte à chaque session."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def charger_ou_creer_memoire(client: anthropic.Anthropic) -> tuple[str, list]:
    """
    Charge la mémoire existante ou crée une nouvelle si absente.
    Retourne (contenu_projet_md, historique_requetes).
    """
    DOSSIER_MEMOIRE.mkdir(exist_ok=True)

    # Charger l'historique des requêtes
    historique_requetes = []
    if FICHIER_MEMOIRE_HISTORIQUE.exists():
        try:
            historique_requetes = json.loads(FICHIER_MEMOIRE_HISTORIQUE.read_text(encoding="utf-8"))
        except Exception:
            historique_requetes = []

    # Charger ou créer la mémoire projet
    if FICHIER_MEMOIRE_PROJET.exists():
        memoire_projet = FICHIER_MEMOIRE_PROJET.read_text(encoding="utf-8")
        print(f"  Mémoire chargée depuis {FICHIER_MEMOIRE_PROJET}")
    else:
        print(f"  Aucune mémoire trouvée — création en cours...")
        memoire_projet = creer_memoire_projet(client)
        FICHIER_MEMOIRE_PROJET.write_text(memoire_projet, encoding="utf-8")
        print(f"  Mémoire créée: {FICHIER_MEMOIRE_PROJET}")

    return memoire_projet, historique_requetes


def sauvegarder_memoire(session_requetes: list, historique_requetes: list, client: anthropic.Anthropic):
    """
    Sauvegarde la mémoire à la fin de la session.
    Met à jour l'historique et rafraîchit la mémoire projet si les données ont changé.
    """
    DOSSIER_MEMOIRE.mkdir(exist_ok=True)

    # Ajouter les requêtes de la session à l'historique
    for req in session_requetes:
        historique_requetes.append({
            "date": datetime.now().isoformat(),
            "requete": req,
        })
    # Conserver les 100 dernières requêtes
    historique_requetes = historique_requetes[-100:]
    FICHIER_MEMOIRE_HISTORIQUE.write_text(
        json.dumps(historique_requetes, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Vérifier si les fichiers JSON ont été modifiés pendant la session
    # (ex: un scraper a été lancé) → régénérer la mémoire projet
    if FICHIER_MEMOIRE_PROJET.exists():
        mtime_memoire = FICHIER_MEMOIRE_PROJET.stat().st_mtime
        donnees_plus_recentes = any(
            Path(f).exists() and Path(f).stat().st_mtime > mtime_memoire
            for f in FICHIERS_JSON.values()
        )
        if donnees_plus_recentes:
            print("  Données mises à jour — régénération de la mémoire projet...")
            memoire_projet = creer_memoire_projet(client)
            FICHIER_MEMOIRE_PROJET.write_text(memoire_projet, encoding="utf-8")

    print(f"  Mémoire sauvegardée ({len(session_requetes)} requêtes cette session)")


# ── Fonctions outils ───────────────────────────────────────────────────────────

def _charger_produits(source: str) -> list:
    fichier = FICHIERS_JSON.get(source, source)
    path = Path(fichier)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def rechercher_produits(query: str, source: str = "tous", max_resultats: int = 10) -> str:
    """Recherche des produits par nom, catégorie ou marque."""
    produits = _charger_produits(source)
    if not produits:
        return json.dumps({"erreur": f"Aucune donnée pour '{source}'. Lancez d'abord le scraper."})

    query_lower = query.lower()
    resultats = []
    for p in produits:
        champs = [str(p.get(k, "")) for k in ("nom", "categorie", "sousCategorie", "marque")]
        if any(query_lower in c.lower() for c in champs):
            resultats.append({
                "nom": p.get("nom", ""),
                "prix": p.get("prix"),
                "prixPromo": p.get("prixPromo"),
                "enPromo": p.get("enPromo", False),
                "marque": p.get("marque", ""),
                "categorie": p.get("categorie", ""),
                "sousCategorie": p.get("sousCategorie", ""),
                "pointDeVente": p.get("pointDeVente", ""),
                "quantite": p.get("quantite"),
            })

    return json.dumps({
        "query": query,
        "source": source,
        "total_trouve": len(resultats),
        "resultats": resultats[:max_resultats],
    }, ensure_ascii=False, indent=2)


def comparer_prix(nom_produit: str) -> str:
    """Compare le prix d'un produit entre tous les magasins disponibles."""
    tous = _charger_produits("tous")
    if not tous:
        tous = []
        for source in ("carrefour", "otrity", "mg"):
            tous.extend(_charger_produits(source))

    if not tous:
        return json.dumps({"erreur": "Aucune donnée disponible. Lancez les scrapers d'abord."})

    mots = nom_produit.lower().split()
    par_magasin: dict = {}

    for p in tous:
        nom = str(p.get("nom", "")).lower()
        if all(mot in nom for mot in mots):
            magasin = p.get("pointDeVente", "Inconnu")
            prix = p.get("prix")
            if prix is None:
                continue
            par_magasin.setdefault(magasin, []).append({
                "nom": p.get("nom", ""),
                "prix": prix,
                "prixPromo": p.get("prixPromo"),
                "enPromo": p.get("enPromo", False),
                "marque": p.get("marque", ""),
                "quantite": p.get("quantite"),
            })

    if not par_magasin:
        return json.dumps({"message": f"Aucun produit trouvé pour '{nom_produit}'"})

    tous_prix = []
    for magasin, prods in par_magasin.items():
        for p in prods:
            prix_eff = p.get("prixPromo") or p.get("prix")
            tous_prix.append((prix_eff, magasin, p["nom"]))
    tous_prix.sort()

    return json.dumps({
        "produit_recherche": nom_produit,
        "comparaison_par_magasin": par_magasin,
        "meilleure_offre": {
            "prix": tous_prix[0][0],
            "magasin": tous_prix[0][1],
            "nom_exact": tous_prix[0][2],
        } if tous_prix else None,
    }, ensure_ascii=False, indent=2)


def statistiques(source: str = "tous") -> str:
    """Retourne des statistiques sur les produits disponibles."""
    produits = _charger_produits(source)
    if not produits:
        return json.dumps({"erreur": f"Aucune donnée pour '{source}'"})

    prix_valides = [p.get("prix") for p in produits if isinstance(p.get("prix"), (int, float)) and p.get("prix", 0) > 0]
    categories: dict = {}
    magasins: dict = {}
    en_promo = 0

    for p in produits:
        categories[p.get("categorie", "Inconnue")] = categories.get(p.get("categorie", "Inconnue"), 0) + 1
        magasins[p.get("pointDeVente", "Inconnu")] = magasins.get(p.get("pointDeVente", "Inconnu"), 0) + 1
        if p.get("enPromo"):
            en_promo += 1

    top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]
    fichier = FICHIERS_JSON.get(source, source)

    return json.dumps({
        "source": source,
        "total_produits": len(produits),
        "produits_en_promo": en_promo,
        "pourcentage_promo": round(en_promo / len(produits) * 100, 1) if produits else 0,
        "prix": {
            "min": min(prix_valides) if prix_valides else None,
            "max": max(prix_valides) if prix_valides else None,
            "moyen": round(sum(prix_valides) / len(prix_valides), 2) if prix_valides else None,
        },
        "par_magasin": magasins,
        "top_categories": dict(top_categories),
        "derniere_modification": datetime.fromtimestamp(
            Path(fichier).stat().st_mtime
        ).strftime("%d/%m/%Y %H:%M") if Path(fichier).exists() else "N/A",
    }, ensure_ascii=False, indent=2)


def lancer_scraper(nom_scraper: str) -> str:
    """Lance un scraper pour mettre à jour les données."""
    import subprocess
    if nom_scraper == "tous":
        resultats = [json.loads(lancer_scraper(n)) for n in SCRAPERS]
        return json.dumps({"resultats": resultats}, ensure_ascii=False, indent=2)

    script = SCRAPERS.get(nom_scraper)
    if not script:
        return json.dumps({"erreur": f"Scraper '{nom_scraper}' inconnu. Disponibles: {list(SCRAPERS.keys())}"})
    if not Path(script).exists():
        return json.dumps({"erreur": f"Fichier '{script}' introuvable"})

    debut = datetime.now()
    try:
        res = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=3600)
        duree = (datetime.now() - debut).seconds
        if res.returncode == 0:
            nb = len(_charger_produits(nom_scraper))
            return json.dumps({"succes": True, "scraper": nom_scraper, "duree_secondes": duree, "nb_produits": nb})
        else:
            return json.dumps({"succes": False, "scraper": nom_scraper, "erreur": res.stderr[-300:] or "Erreur inconnue"})
    except subprocess.TimeoutExpired:
        return json.dumps({"succes": False, "scraper": nom_scraper, "erreur": "Délai dépassé (1h)"})
    except Exception as e:
        return json.dumps({"succes": False, "scraper": nom_scraper, "erreur": str(e)})


def lire_memoire() -> str:
    """Lit le contenu de la mémoire projet."""
    if FICHIER_MEMOIRE_PROJET.exists():
        return FICHIER_MEMOIRE_PROJET.read_text(encoding="utf-8")
    return "Mémoire non disponible."


def mettre_a_jour_memoire(contenu: str) -> str:
    """Met à jour la mémoire projet avec de nouvelles informations."""
    DOSSIER_MEMOIRE.mkdir(exist_ok=True)
    existing = ""
    if FICHIER_MEMOIRE_PROJET.exists():
        existing = FICHIER_MEMOIRE_PROJET.read_text(encoding="utf-8")
    nouveau = existing + "\n\n## Mise à jour " + datetime.now().strftime("%d/%m/%Y %H:%M") + "\n" + contenu
    FICHIER_MEMOIRE_PROJET.write_text(nouveau, encoding="utf-8")
    return json.dumps({"succes": True, "message": "Mémoire mise à jour"})


# ── Définitions des outils pour Claude ────────────────────────────────────────

TOOLS = [
    {
        "name": "rechercher_produits",
        "description": "Recherche des produits par nom, catégorie ou marque dans les données scraped.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Terme de recherche: nom, catégorie ou marque"},
                "source": {"type": "string", "enum": ["carrefour", "otrity", "mg", "tous"], "description": "Source des données (défaut: 'tous')"},
                "max_resultats": {"type": "integer", "description": "Nombre maximum de résultats (défaut: 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "comparer_prix",
        "description": "Compare le prix d'un produit entre Carrefour, Otrity et MG Tunisie.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nom_produit": {"type": "string", "description": "Nom ou mots-clés du produit à comparer"},
            },
            "required": ["nom_produit"],
        },
    },
    {
        "name": "statistiques",
        "description": "Retourne des statistiques sur les produits disponibles (total, prix moyen, catégories...).",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "enum": ["carrefour", "otrity", "mg", "tous"], "description": "Source des données"},
            },
        },
    },
    {
        "name": "lancer_scraper",
        "description": "Lance un scraper pour mettre à jour les données. Prend quelques minutes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nom_scraper": {"type": "string", "enum": ["carrefour", "otrity", "mg", "tous"]},
            },
            "required": ["nom_scraper"],
        },
    },
    {
        "name": "lire_memoire",
        "description": "Lit la mémoire persistante du projet (structure, scrapers, historique).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "mettre_a_jour_memoire",
        "description": "Ajoute une note ou mise à jour à la mémoire persistante du projet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contenu": {"type": "string", "description": "Contenu à ajouter à la mémoire"},
            },
            "required": ["contenu"],
        },
    },
]

FONCTIONS_OUTILS = {
    "rechercher_produits": rechercher_produits,
    "comparer_prix": comparer_prix,
    "statistiques": statistiques,
    "lancer_scraper": lancer_scraper,
    "lire_memoire": lire_memoire,
    "mettre_a_jour_memoire": mettre_a_jour_memoire,
}


# ── Boucle agent ───────────────────────────────────────────────────────────────

def executer_outil(nom: str, parametres: dict) -> str:
    fn = FONCTIONS_OUTILS.get(nom)
    if not fn:
        return json.dumps({"erreur": f"Outil '{nom}' inconnu"})
    return fn(**parametres)


def construire_system_prompt(memoire_projet: str, historique_requetes: list) -> str:
    """Construit le prompt système avec la mémoire injectée."""
    requetes_recentes = ""
    if historique_requetes:
        recentes = historique_requetes[-5:]
        requetes_recentes = "\n\n## Requêtes récentes de l'utilisateur\n" + "\n".join(
            f"- {r['requete']}" for r in recentes
        )

    return f"""Tu es un assistant expert en analyse de produits de la grande distribution tunisienne.
Tu as accès à des données scraped de Carrefour Tunisie, Otrity et MG Tunisie.

## Mémoire du projet
{memoire_projet}
{requetes_recentes}

## Tes capacités
- Rechercher des produits par nom, catégorie ou marque
- Comparer les prix d'un même produit entre les différents magasins
- Obtenir des statistiques sur les données disponibles
- Lancer les scrapers pour mettre à jour les données
- Lire et mettre à jour ta mémoire persistante

## Instructions
- Réponds toujours en français
- Sois précis sur les prix (en TND) et les noms des magasins
- Quand tu affiches des produits, utilise un format clair avec le nom, le prix et le magasin
- Si tu découvres une information importante sur le projet, mets à jour ta mémoire avec l'outil dédié"""


def chat(client: anthropic.Anthropic, historique_messages: list, message_utilisateur: str, system_prompt: str) -> str:
    """Envoie un message et gère la boucle d'outils jusqu'à la réponse finale."""
    historique_messages.append({"role": "user", "content": message_utilisateur})

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=historique_messages,
        ) as stream:
            reponse = stream.get_final_message()

        historique_messages.append({"role": "assistant", "content": reponse.content})

        if reponse.stop_reason == "end_turn":
            return next((b.text for b in reponse.content if hasattr(b, "text")), "")

        if reponse.stop_reason == "tool_use":
            appels = [b for b in reponse.content if b.type == "tool_use"]
            resultats = []
            for appel in appels:
                print(f"  [outil] {appel.name}({json.dumps(appel.input, ensure_ascii=False)[:80]})")
                resultat = executer_outil(appel.name, appel.input)
                resultats.append({"type": "tool_result", "tool_use_id": appel.id, "content": resultat})
            historique_messages.append({"role": "user", "content": resultats})
            continue

        return next((b.text for b in reponse.content if hasattr(b, "text")), "")


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Erreur: définissez la variable d'environnement ANTHROPIC_API_KEY")
        print("  Windows: set ANTHROPIC_API_KEY=votre_clé")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("╔══════════════════════════════════════════════════════╗")
    print("║         AGENT IA — Analyse de Produits Tunisiens      ║")
    print("╚══════════════════════════════════════════════════════╝")
    print("Initialisation de la mémoire...")

    # Chargement ou création de la mémoire
    memoire_projet, historique_requetes = charger_ou_creer_memoire(client)
    system_prompt = construire_system_prompt(memoire_projet, historique_requetes)

    historique_messages = []
    session_requetes = []

    print("\nPrêt. Tapez votre question ou 'quitter' pour terminer.\n")
    print("Exemples:")
    print("  • Quels produits lait sont disponibles chez Carrefour ?")
    print("  • Compare le prix de l'eau Safia entre les magasins")
    print("  • Donne-moi les statistiques globales")
    print("  • Que sais-tu de ce projet ? (consulte la mémoire)\n")

    while True:
        try:
            entree = input("Vous: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            break

        if not entree:
            continue
        if entree.lower() in ("quitter", "exit", "quit", "q"):
            break

        session_requetes.append(entree)
        print("Agent: ", end="", flush=True)

        try:
            reponse = chat(client, historique_messages, entree, system_prompt)
            print(reponse)
        except anthropic.APIStatusError as e:
            print(f"\nErreur API: {e.status_code} — {e.message}")
        except Exception as e:
            print(f"\nErreur inattendue: {e}")
        print()

    # Sauvegarde de la mémoire en fin de session
    if session_requetes:
        print("Sauvegarde de la mémoire...")
        sauvegarder_memoire(session_requetes, historique_requetes, client)

    print("Au revoir !")


if __name__ == "__main__":
    main()
