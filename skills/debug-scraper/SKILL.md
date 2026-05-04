# Skill : Déboguer un scraper défaillant

Diagnostiquer et corriger les problèmes courants dans les scrapers Playwright du projet.

## Arbre de décision rapide

```
Scraper plante ?
├── Le script plante immédiatement
│   ├── ImportError → pip install manquant
│   ├── TimeoutError au goto() → site lent, augmenter timeout
│   └── "Executable not found" → playwright install chromium
│
├── Le scraper tourne mais récupère 0 produit
│   ├── Scraper HTML → les sélecteurs CSS ont changé → inspecter le HTML
│   ├── Scraper GraphQL → l'URL de l'API a changé → inspecter Network
│   └── Pagination cassée → le site a changé sa structure d'URL
│
└── Le scraper récupère des données corrompues
    ├── Prix None ou 0 → regex prix à ajuster
    ├── Images manquantes → sélecteur image changé ou lazy-load non géré
    └── Catégories vides → breadcrumb ou meta changé
```

---

## Diagnostic 1 — Sélecteurs CSS obsolètes (HTML scrapers)

Quand `page.query_selector_all("article.product")` retourne une liste vide :

```python
# AJOUTER TEMPORAIREMENT pour inspecter le HTML réel
page.goto(url, wait_until="domcontentloaded")
time.sleep(3)
html = page.content()
with open("debug_page.html", "w", encoding="utf-8") as f:
    f.write(html)
# Ouvrir debug_page.html dans le navigateur et inspecter l'élément "Produit"
```

**Sélecteurs à essayer selon la plateforme :**

| Plateforme | Sélecteurs alternatifs |
|-----------|----------------------|
| WooCommerce | `li.product`, `article.type-product`, `.wc-block-grid__product`, `[data-product_id]` |
| PrestaShop | `.product-miniature`, `li.ajax_block_product`, `article.product-miniature`, `.js-product` |
| Carrefour TN | Pas de sélecteur CSS — utiliser l'interception GraphQL |

```python
# Essai de sélecteurs en cascade
for selecteur in ["article.product", "li.product", ".product-miniature", "[data-product-id]"]:
    cartes = page.query_selector_all(selecteur)
    if cartes:
        print(f"Sélecteur fonctionnel: {selecteur} ({len(cartes)} éléments)")
        break
```

---

## Diagnostic 2 — Interception GraphQL qui ne reçoit rien

Quand `produits` reste vide dans les scrapers Carrefour :

```python
# 1. Vérifier que l'interception est bien enregistrée AVANT goto()
page.on("response", handle_response)  # ← doit être avant page.goto()
page.goto(url, ...)

# 2. Logger TOUTES les réponses pour trouver la bonne URL
def debug_response(response):
    if response.status == 200 and "json" in response.headers.get("content-type", ""):
        print(f"[RÉSEAU] {response.url[:100]}")
page.on("response", debug_response)

# 3. Vérifier que la réponse est bien parseable
def handle_response(response):
    try:
        data = response.json()
    except Exception as e:
        print(f"JSON non parseable: {e} — {response.url[:80]}")
        return
    # continuer...
```

---

## Diagnostic 3 — Pagination s'arrête trop tôt

```python
# Pour WooCommerce : vérifier le sélecteur "page suivante"
bouton_suivant = page.query_selector("a.next.page-numbers, .next.page-numbers, [rel='next']")
print(f"Bouton suivant: {bouton_suivant}")

# Pour PrestaShop : vérifier l'URL de la page suivante
lien_suivant = page.query_selector("a[rel='next'], .next.js-search-link")
if lien_suivant:
    print(f"URL suivante: {lien_suivant.get_attribute('href')}")

# Tester manuellement en naviguant directement vers page 2
page.goto(f"{base_url}?page=2", wait_until="domcontentloaded")
cartes = page.query_selector_all("article.product")
print(f"Page 2 : {len(cartes)} cartes trouvées")
```

---

## Diagnostic 4 — Prix None ou 0

```python
# Récupérer le texte brut pour inspecter
prix_element = carte.query_selector(".price, .woocommerce-Price-amount, span.product-price")
if prix_element:
    texte_brut = prix_element.inner_text()
    print(f"Prix brut: '{texte_brut}'")
    # Tester le regex manuellement
    import re
    propre = re.sub(r'[^\d,\.]', '', texte_brut).replace(',', '.')
    print(f"Prix nettoyé: '{propre}'")
```

**Formats de prix courants en Tunisie :**
```
"12,500 TND"  → propre = "12.500" → float = 12.5 ✓
"12.500 DT"   → propre = "12.500" → float = 12.5 ✓
"12 500 TND"  → propre = "12 500" → PROBLÈME : contient espace
"TND 12,500"  → propre = "12.500" → float = 12.5 ✓
```

Pour le cas avec espace (séparateur de milliers) :
```python
propre = re.sub(r'[^\d,\.]', '', texte_brut.replace('\xa0', '').replace(' ', '')).replace(',', '.')
```

---

## Diagnostic 5 — Images manquantes ou URL cassée

```python
# WooCommerce : vérifier src vs data-src (lazy-load)
img = carte.query_selector("img")
if img:
    src = img.get_attribute("src") or img.get_attribute("data-src") or img.get_attribute("data-lazy-src")
    print(f"Image src: {src}")

# PrestaShop : image dans balise <a> ou <img>
img = carte.query_selector("a img, .thumbnail img, .product-thumbnail img")

# Carrefour GraphQL : chercher dans extra_data
image_url = item.get("small_image", {}).get("url") or item.get("extraData", {}).get("image", "")
```

---

## Diagnostic 6 — Lazy-loading : les images ne se chargent pas

```python
# Forcer le chargement des images en scrollant
def scroll_pour_lazy_load(page):
    hauteur = page.evaluate("document.body.scrollHeight")
    for i in range(4):
        page.evaluate(f"window.scrollBy(0, {hauteur // 4})")
        time.sleep(0.8)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)
```

---

## Diagnostic 7 — Timeout ou site trop lent

```python
# Augmenter les timeouts
page.goto(url, wait_until="domcontentloaded", timeout=90000)  # 90s au lieu de 60s

# Utiliser "domcontentloaded" au lieu de "networkidle" (plus robuste)
# "networkidle" attend que toutes les requêtes XHR se terminent — peut bloquer

# Si le site a une popup de cookies qui bloque
try:
    page.click("button#accept-all, button.cookie-accept, #onetrust-accept-btn-handler", timeout=5000)
except Exception:
    pass  # pas de popup, continuer
```

---

## Mode debug rapide

Ajouter en haut du fichier pour activer les logs Playwright :

```python
import os
os.environ["DEBUG"] = "pw:api"  # logs réseau détaillés
```

Ou lancer avec Playwright Inspector (interface visuelle) :

```python
browser = p.chromium.launch(headless=False, slow_mo=500)
page = browser.new_page()
page.pause()  # ouvre l'inspecteur Playwright — naviguer manuellement et tester des sélecteurs
```

---

## Checklist de vérification avant de conclure qu'un scraper est cassé

- [ ] Le site est-il accessible manuellement dans le navigateur ?
- [ ] Y a-t-il une protection anti-bot (Cloudflare, reCAPTCHA) ?
- [ ] Les sélecteurs CSS correspondent-ils encore au HTML actuel ?
- [ ] L'URL GraphQL a-t-elle changé ? (inspecter l'onglet Network)
- [ ] Le `slow_mo` est-il suffisant pour que le JS se charge ?
- [ ] La déduplication `seen_skus` est-elle réinitialisée entre les catégories ?
