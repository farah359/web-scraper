# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python web scraping project targeting Tunisian e-commerce sites (Carrefour, Otrity, MG Tunisie). Each scraper extracts product data and serializes it to a standardized JSON format.

## Dependencies

There is no `requirements.txt`. Install manually:

```
pip install playwright beautifulsoup4 selenium anthropic
playwright install chromium
```

`msedgedriver.exe` in the root is the Edge WebDriver used by `aziza.py`.

## Running Scrapers

Each scraper is a standalone script with a `main()` function:

```bash
python scraper_carrefour.py         # Carrefour Tunisia (GraphQL, ~7000 products)
python scraper_otority.py           # Otrity (WooCommerce)
python car.py                       # Alternative Carrefour scraper (simpler)
python mg.py                        # MG Tunisie (PrestaShop)
python agent_orchestrateur.py       # Lance tous les scrapers + consolide
python agent_ia.py                  # Agent IA interactif (nécessite ANTHROPIC_API_KEY)
```

Output is written to JSON files in the project root (`carrefour.json`, `otrity.json`, etc.).

## Architecture

### Standardized Product Schema (`Produit` dataclass in `aziza.py`)

All scrapers output products with the same fields:

- Identity: `nom`, `categorie`, `sousCategorie`, `marque`, `fournisseur`
- Pricing: `prix`, `prixPromo`, `enPromo`
- Commerce: `pointDeVente`, `ville`, `marcheCible`, `enPack`, `quantite`
- Media/Meta: `image`, `source`, `statut`, `specifications`, `sourcesDetails`, `createdAt`, `updatedAt`

### Scraper Strategies by Platform

| File | Platform | Browser Tech | Key Technique |
|------|----------|--------------|---------------|
| `scraper_carrefour.py` | Carrefour TN | Playwright Chromium | GraphQL response interception |
| `car.py` | Carrefour TN | Playwright Chromium | GraphQL interception (simpler) |
| `scraper_otority.py` | Otrity (WooCommerce) | Playwright Chromium | HTML parsing + pagination |
| `mg.py` | MG Tunisie (PrestaShop) | Playwright Chromium | HTML parsing + lazy-load images |
| `aziza.py` | (data model) | Selenium Edge | Used for testing/prototyping |

### Agents

| File | Rôle | Mémoire |
|------|------|---------|
| `agent_orchestrateur.py` | Lance tous les scrapers, consolide les données | `memory/orchestrateur_memory.json` |
| `agent_ia.py` | Agent Claude interactif pour analyser les produits | `memory/projet.md` + `memory/historique.json` |

La mémoire est créée automatiquement au premier lancement si absente.

### Data Flow

1. Browser launches (headless or visible, configured per scraper)
2. Category pages are iterated with platform-specific pagination
3. Product data is extracted and normalized (regex for prices and quantities)
4. Deduplication runs (by SKU for Carrefour, by URL for Otrity, by `nom|marque` for MG)
5. Output serialized to JSON via `Produit.to_dict()`

### Key Implementation Details

- **GraphQL scrapers** (`scraper_carrefour.py`, `car.py`): Intercept network responses with `page.on("response", ...)` to capture product JSON before page render.
- **Price parsing**: Regex `r'[^\d,\.]'` strips currency symbols (TND/DT), commas converted to dots.
- **Quantity extraction**: Regex extracts weight/volume from product names (e.g., `500g`, `1L`, `2x200ml`).
- **Comments**: Code comments are in French.
- **Skills**: See `skills/` directory for reusable guides (nouveau-scraper, debug-scraper, analyse-donnees).

---

## Rules

### Code Style
- **Langue des commentaires** : toujours en **français**
- Ne pas ajouter de commentaires qui expliquent le "quoi" — seulement le "pourquoi" si non évident
- Ne pas créer de `requirements.txt` — les dépendances s'installent manuellement (voir ci-dessus)

### Playwright
- Utiliser `sync_playwright` (pas `async`) — tous les scrapers existants sont synchrones
- Toujours bloquer les fichiers vidéo : `page.route("**/*.{mp4,webm,ogg}", lambda r: r.abort())`
- Développement : `headless=False` — Production : `headless=True`
- Scroll pour lazy-load : 4 itérations de `window.scrollBy(0, window.innerHeight)` avec 0.8s de délai
- Timeout standard : `wait_until="domcontentloaded"` avec `timeout=60000` (60s)

### Schéma des données
- Tout nouveau scraper **doit** produire des dicts conformes au schéma `Produit` de `aziza.py`
- Les prix sont en **TND**, arrondis à 3 décimales : `round(float(prix), 3)`
- `pointDeVente` doit être le nom officiel du magasin (ex: `"Carrefour Tunisie"`, `"Otrity"`, `"MG Tunisie"`)
- `source` doit être le domaine du site (ex: `"carrefour.tn"`, `"otrity.com"`)
- `createdAt` et `updatedAt` : `datetime.utcnow().isoformat()`

### Déduplication
- Carrefour (GraphQL) : par `sku` — `seen_skus = set()`
- Otrity (WooCommerce) : par URL de la page produit
- MG Tunisie (PrestaShop) : par clé composite `f"{nom}|{marque}"`
- Consolidation finale (`tous_les_produits.json`) : par `(nom, pointDeVente)`

### Parsing des prix
```python
import re
def parse_prix(texte: str) -> float | None:
    if not texte:
        return None
    propre = re.sub(r'[^\d,\.]', '', texte).replace(',', '.')
    try:
        return round(float(propre), 3)
    except ValueError:
        return None
```

### Agents et mémoire
- Les agents stockent leur mémoire dans `memory/` — ne pas supprimer ce dossier manuellement
- Si les données JSON changent (nouveau scraper, mise à jour), supprimer `memory/projet.md` pour forcer la régénération
- L'agent IA nécessite la variable d'environnement `ANTHROPIC_API_KEY`
- Modèle Claude utilisé : `claude-opus-4-7`

### Ajouter un nouveau scraper
1. Créer `scraper_<site>.py` en suivant les patterns du projet (voir skill `skills/nouveau-scraper/`)
2. Ajouter l'entrée dans `agent_orchestrateur.py → SCRAPERS`
3. Ajouter dans `agent_ia.py → FICHIERS_JSON et SCRAPERS`
4. Supprimer `memory/projet.md` pour régénérer la mémoire

### Débogage
Consulter le skill `skills/debug-scraper/` pour les techniques de diagnostic.

### Ne pas faire
- Ne pas utiliser `requests` ou `httpx` pour scraper — utiliser Playwright
- Ne pas utiliser `async` Playwright — le projet est entièrement synchrone
- Ne pas modifier le schéma `Produit` dans `aziza.py` sans mettre à jour tous les scrapers
- Ne pas hardcoder des `time.sleep` > 5s (sauf scroll infini)
- Ne pas créer de fichiers `requirements.txt`, `setup.py`, `pyproject.toml`
