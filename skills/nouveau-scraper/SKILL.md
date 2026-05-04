# Skill : Créer un nouveau scraper

Ajouter un scraper pour un site e-commerce tunisien non encore couvert. Suivre l'architecture du projet et les patterns établis.

## Étape 1 — Identifier la technologie du site cible

Avant d'écrire une ligne de code, ouvrir les DevTools du site et observer :

| Signal | Plateforme | Approche à adopter |
|--------|-----------|-------------------|
| Requêtes `graphql` dans l'onglet Network | GraphQL (comme Carrefour) | Intercepter les réponses réseau avec `page.on("response", ...)` |
| URLs avec `?page=` ou `/page/2/` | WooCommerce / PrestaShop | Pagination URL classique |
| Attributs `data-product-id` dans le HTML | PrestaShop | Sélecteurs CSS + BeautifulSoup |
| Bouton "Charger plus" ou scroll infini | SPA / React | Scroll automatisé |

---

## Étape 2 — Démarrer le fichier scraper

Créer `scraper_<nomsite>.py` en reprenant ce squelette :

```python
from playwright.sync_api import sync_playwright
from datetime import datetime
import json, re, time

produits = []
vus = set()  # pour la déduplication

# ── Catégories à scraper ──────────────────────────────────────
PAGES = [
    ("Catégorie principale", "Sous-catégorie", "https://..."),
]

# ── Parsing du prix ───────────────────────────────────────────
def parse_prix(texte: str) -> float | None:
    """Extrait le prix numérique depuis une chaîne comme '12,500 TND'."""
    if not texte:
        return None
    propre = re.sub(r'[^\d,\.]', '', texte).replace(',', '.')
    try:
        return round(float(propre), 3)
    except ValueError:
        return None

# ── Extraction de la quantité ─────────────────────────────────
def parse_quantite(nom: str) -> float | None:
    """Extrait le poids/volume depuis le nom du produit."""
    m = re.search(r'(\d+[\.,]?\d*)\s*(g|gr|kg|ml|cl|l|L)\b', nom, re.IGNORECASE)
    if not m:
        return None
    valeur = float(m.group(1).replace(',', '.'))
    unite = m.group(2).lower()
    # Normaliser en grammes/millilitres
    if unite in ('kg',):
        return valeur * 1000
    if unite in ('cl',):
        return valeur * 10
    if unite in ('l',):
        return valeur * 1000
    return valeur

def scraper_page(page, url, categorie, sous_categorie):
    """Scraper une page de catégorie."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    # TODO: implémenter selon la plateforme
    pass

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        page.route("**/*.{mp4,webm,ogg}", lambda r: r.abort())

        for categorie, sous_categorie, url in PAGES:
            scraper_page(page, url, categorie, sous_categorie)

        browser.close()

    # Déduplication finale
    final = list({p["sourcesDetails"]["url"]: p for p in produits}.values())
    with open("<nomsite>.json", "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"{len(final)} produits sauvegardés.")

if __name__ == "__main__":
    main()
```

---

## Étape 3 — Choisir et implémenter la stratégie selon la plateforme

### Stratégie A : GraphQL (Carrefour)
```python
current_cat = {"nom": "", "sous": ""}

def handle_response(response):
    if "graphql" not in response.url:
        return
    try:
        data = response.json()
    except Exception:
        return
    items = trouver_items(data)  # chercher récursivement la clé "items"
    for item in items:
        sku = item.get("sku")
        if not sku or sku in vus:
            continue
        vus.add(sku)
        prix_range = item.get("price_range", {}).get("maximum_price", {})
        prix = prix_range.get("final_price", {}).get("value")
        # ... construire le dict produit et l'ajouter à `produits`

page.on("response", handle_response)
page.goto(url, wait_until="domcontentloaded")
for _ in range(20):  # scroll infini
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2.5)
```

### Stratégie B : HTML + pagination URL (WooCommerce / PrestaShop)
```python
page_num = 1
while True:
    url_page = f"{base_url}/page/{page_num}/" if page_num > 1 else base_url
    response = page.goto(url_page, wait_until="networkidle", timeout=45000)
    if response and response.status == 404:
        break
    # Scroll pour lazy-load
    for _ in range(4):
        page.evaluate("window.scrollBy(0, window.innerHeight)")
        time.sleep(0.8)
    # Extraire les cartes produits
    cartes = page.query_selector_all("article.product, li.product, .product-miniature")
    if not cartes:
        break
    for carte in cartes:
        # extraire nom, prix, url, image...
        pass
    page_num += 1
    time.sleep(2)
```

---

## Étape 4 — Construire le dictionnaire produit (schéma standard)

Chaque produit **doit** respecter ce schéma (issu du dataclass `Produit` dans `aziza.py`) :

```python
produit = {
    "nom": str,                      # OBLIGATOIRE — nom nettoyé
    "categorie": str,                # OBLIGATOIRE
    "sousCategorie": str | None,
    "marque": str | None,
    "prix": float,                   # OBLIGATOIRE — en TND
    "prixPromo": float | None,       # prix promo si en promotion
    "enPromo": bool,                 # True si prixPromo < prix
    "enPack": bool,                  # False par défaut
    "quantite": float | None,        # en grammes ou millilitres
    "image": str,                    # URL de l'image
    "pointDeVente": str,             # ex: "Monoprix Tunisie"
    "ville": str,                    # ex: "Tunis"
    "marcheCible": str,              # "B2C" ou "B2B"
    "source": str,                   # domaine ex: "monoprix.com.tn"
    "statut": str,                   # "disponible" ou "rupture"
    "specifications": dict | None,   # données supplémentaires libres
    "sourcesDetails": {"url": str},  # URL de la page produit
    "createdAt": datetime.utcnow().isoformat(),
    "updatedAt": datetime.utcnow().isoformat(),
}
```

---

## Étape 5 — Déduplication et enregistrement

```python
# Par URL (WooCommerce / PrestaShop)
final = list({p["sourcesDetails"]["url"]: p for p in produits}.values())

# Par SKU (GraphQL / Carrefour)
# La déduplication se fait pendant l'interception avec seen_skus

# Par nom|marque (quand pas d'URL unique)
final = list({f"{p['nom']}|{p.get('marque','')}": p for p in produits}.values())
```

---

## Étape 6 — Référencer le nouveau scraper

1. Ajouter dans `agent_orchestrateur.py → SCRAPERS` :
```python
"monsite": {
    "script": "scraper_monsite.py",
    "sortie": "monsite.json",
    "description": "MonSite Tunisie (plateforme)",
},
```

2. Ajouter dans `agent_ia.py → FICHIERS_JSON et SCRAPERS` :
```python
FICHIERS_JSON["monsite"] = "monsite.json"
SCRAPERS["monsite"] = "scraper_monsite.py"
```

3. Supprimer `memory/projet.md` pour forcer la régénération de la mémoire à la prochaine session.

---

## Règles importantes
- Les commentaires dans le code sont en **français**
- Ne jamais hardcoder de `time.sleep` > 5s sauf dans le scroll infini
- Toujours bloquer les vidéos : `page.route("**/*.{mp4,webm,ogg}", lambda r: r.abort())`
- `headless=False` pendant le développement, passer à `True` en production
- Tester avec 1-2 catégories avant de lancer le scraping complet
