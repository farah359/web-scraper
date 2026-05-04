from playwright.sync_api import sync_playwright
import json
import time
import re
from collections import Counter

# ─────────────────────────────────────────────────────────────
# MAPPING URL → catégorie
# La catégorie est déduite de l'URL qu'on scrape,
# puisque le site MG ne l'expose pas clairement dans les cards.
# ─────────────────────────────────────────────────────────────
CATEGORIES_URLS = {
    "Alimentaire":        "https://www.mg.tn/alimentaire",
    "Boissons":           "https://www.mg.tn/boissons",
    "Crèmerie & Fromage": "https://www.mg.tn/cremerie-fromage",
    "Épicerie":           "https://www.mg.tn/epicerie",
    "Hygiène & Beauté":   "https://www.mg.tn/hygiene-beaute",
    "Entretien":          "https://www.mg.tn/entretien",
    "Bébé":               "https://www.mg.tn/bebe",
}

OUTPUT_FILE = "mg_tunisie_produits.json"
products = []
seen_skus = set()


# ─────────────────────────────────────────────────────────────
# PARSING NOM → nom propre + marque + quantité
# Exemple : "Ail en poudre 70 gr MG J'AIME"
#   → nom      = "Ail en poudre"
#   → marque   = "MG J'AIME"
#   → quantite = "70 gr"
# ─────────────────────────────────────────────────────────────
def parse_nom_produit(raw: str):
    raw = raw.strip()

    # 1. Extraire la quantité
    quantite = None
    q_match = re.search(
        r'\b(\d+[\.,]?\d*\s*(g|gr|kg|ml|cl|l|L|pcs|sachets?))\b',
        raw, re.IGNORECASE
    )
    if q_match:
        quantite = q_match.group(0).strip()

    # 2. Détecter la marque MG (toujours en fin de nom)
    marque = None
    nom_clean = raw
    for pat in [r"MG\s+J[''']AIME", r"MG\s+ENFANTS", r"\bMG\b"]:
        m = re.search(pat, raw, re.IGNORECASE)
        if m:
            marque = m.group(0).strip().upper()
            nom_clean = raw[:m.start()].strip()
            break

    # 3. Supprimer la quantité du nom
    if quantite and quantite in nom_clean:
        nom_clean = nom_clean.replace(quantite, "").strip()

    # 4. Nettoyage final
    nom_clean = re.sub(r'[-–\s]+$', '', nom_clean).strip()
    nom_clean = re.sub(r'\s+', ' ', nom_clean)

    return nom_clean or raw, marque or "MG", quantite


# ─────────────────────────────────────────────────────────────
# PARSER LE PRIX TUNISIEN : "5,250 DT" → 5.250
# ─────────────────────────────────────────────────────────────
def parse_prix(text: str):
    if not text:
        return None
    cleaned = re.sub(r'[^\d,\.]', '', text.replace(",", "."))
    try:
        return round(float(cleaned), 3)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────
# EXTRAIRE UN PRODUIT DEPUIS UNE CARTE DE LISTING
# ─────────────────────────────────────────────────────────────
def extract_from_card(card, categorie: str):
    try:
        # Nom du produit
        nom_el = card.query_selector(".product-title a, h2 a, .product-name a, h3 a")
        if not nom_el:
            return None
        raw_nom = nom_el.inner_text().strip()
        if not raw_nom:
            return None

        nom, marque, quantite = parse_nom_produit(raw_nom)

        # URL et SKU
        href = nom_el.get_attribute("href") or ""
        sku = href.split("/")[-1].replace(".html", "") if href else None

        # Dédoublonnage
        if sku and sku in seen_skus:
            return None
        if sku:
            seen_skus.add(sku)

        # Image
        img_el = card.query_selector("img[data-src], img[src]")
        image = ""
        if img_el:
            image = img_el.get_attribute("data-src") or img_el.get_attribute("src") or ""

        # Prix courant
        prix_el = card.query_selector(".price.product-price, .current-price .price, .product-price-and-shipping .price")
        prix = parse_prix(prix_el.inner_text()) if prix_el else None

        # Prix barré (promo)
        promo_el = card.query_selector(".regular-price .price, del .price, .price.regular-price")
        prix_promo = parse_prix(promo_el.inner_text()) if promo_el else None

        en_promo = bool(prix_promo and prix_promo > (prix or 0))

        return {
            "nom":           nom,
            "marque":        marque,
            "fournisseur":   None,
            "categorie":     categorie,       # ← déduit de l'URL
            "sousCategorie": None,
            "image":         image,
            "prix":          prix,
            "prixPromo":     prix_promo if en_promo else None,
            "prixPack":      None,
            "enPromo":       en_promo,
            "enPack":        False,
            "contenuPack":   None,
            "quantite":      quantite,
            "quantiteStock": None,
            "marcheCible":   None,
            "pointDeVente":  "MG Tunisie",
            "ville":         "Tunis",
            "specifications": {"description": None},
            "source":        "mg.tn",
            "statut":        "valide",
            "sourcesDetails": {
                "sourceRefId": sku,
                "url":         href,
            },
        }
    except Exception as e:
        print(f"   ⚠️ Erreur carte : {e}")
        return None


# ─────────────────────────────────────────────────────────────
# SCRAPER UNE CATÉGORIE (avec pagination)
# ─────────────────────────────────────────────────────────────
def scrape_category(page, base_url: str, categorie: str):
    local = []
    page_num = 1

    while True:
        url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
        print(f"\n   📄 Page {page_num} → {url}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"   ❌ Erreur chargement : {e}")
            break

        time.sleep(3)

        # Scroll pour déclencher le lazy-loading des images
        for _ in range(4):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(0.8)

        # Sélecteurs PrestaShop (mg.tn tourne sur PrestaShop)
        cards = page.query_selector_all(
            "article.product-miniature, .product-miniature, li.ajax_block_product"
        )

        if not cards:
            print("   ⚠️ Aucune carte trouvée → stop")
            break

        count = 0
        for card in cards:
            prod = extract_from_card(card, categorie)
            if prod and prod["prix"] is not None:
                local.append(prod)
                count += 1
                print(f"   ✅ {prod['marque']:<15} | {prod['nom'][:38]:<38} | {prod['prix']} DT")

        print(f"   → {count} produits sur cette page")

        if count == 0:
            break

        # Page suivante ?
        next_btn = page.query_selector("a[rel='next'], .next.js-search-link, li.next a")
        if not next_btn:
            print("   ✅ Dernière page")
            break

        page_num += 1
        time.sleep(2)

    return local


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    global products
    products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()

        # Bloquer vidéos pour accélérer
        page.route("**/*.{mp4,webm,ogg}", lambda r: r.abort())

        print("🚀 Scraping MG Tunisie...\n")

        for categorie, url in CATEGORIES_URLS.items():
            print(f"\n{'='*60}")
            print(f"🏷️  {categorie}")
            print(f"{'='*60}")

            prods = scrape_category(page, url, categorie)
            products.extend(prods)
            print(f"\n   ✅ {len(prods)} produits pour '{categorie}'")
            time.sleep(2)

        browser.close()

    # Dédoublonnage final
    unique = {}
    for prod in products:
        key = f"{prod['nom']}|{prod['marque']}"
        if key not in unique:
            unique[key] = prod
    products = list(unique.values())

    # Stats
    print(f"\n{'='*60}")
    print(f"🎉 TOTAL : {len(products)} produits uniques")
    print(f"{'='*60}")
    stats = Counter(p["categorie"] for p in products)
    for cat, n in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"   {cat:<30} → {n} produits")

    # Sauvegarde
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Sauvegardé : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()