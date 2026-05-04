from playwright.sync_api import sync_playwright
import json
import time
import re

PAGES = [
    # ── Épicerie ───────────────────────────────────────────────────────────────
    ("Épicerie Sucrée",  "Biscuits",                                "https://otrity.com/categorie-produit/epicerie/biscuits-et-gateaux/"),
    ("Épicerie Sucrée",  "Bonbons et Chocolats",                    "https://otrity.com/categorie-produit/epicerie/chocolats-et-bonbons/"),
    ("Épicerie Salée",   "Conserves et Plats Cuisinés",             "https://otrity.com/categorie-produit/epicerie/conserves-de-legumes-et-tomates/"),
    ("Épicerie Salée",   "Thon et Sardine",                         "https://otrity.com/categorie-produit/epicerie/conserves-de-poissons-et-viandes/"),
    ("Épicerie Salée",   "Pâtes Couscous et Riz",                   "https://otrity.com/categorie-produit/epicerie/pates-riz-semoules-chorba-et-graines/"),
    ("Épicerie Sucrée",  "Petit Déjeuner",                          "https://otrity.com/categorie-produit/epicerie/petit-dejeuner/"),
    ("Épicerie Salée",   "Sauces et Assaisonnements",               "https://otrity.com/categorie-produit/epicerie/salades/"),
    ("Épicerie Sucrée",  "Sucre, Farine et Préparation Pâtisserie", "https://otrity.com/categorie-produit/epicerie/sucres-farines-et-aides-a-la-patisserie/"),
    ("Épicerie Salée",   "Snack et Apéritif",                       "https://otrity.com/categorie-produit/epicerie/aperitifs/"),

    # ── Crèmerie ──────────────────────────────────────────────────────────────
    ("Crèmerie et Produits Laitiers", "Beurre, Crèmes Fraîches et Chantilly", "https://otrity.com/categorie-produit/cremerie/beurres-margarines-et-cremes-fraiches/"),
    ("Crèmerie et Produits Laitiers", "Fromages",                             "https://otrity.com/categorie-produit/cremerie/fromages/"),

    # ── Boissons ──────────────────────────────────────────────────────────────
    ("Boissons", "Boissons Gazeuses",                  "https://otrity.com/categorie-produit/boissons/boissons-gazeuses/"),
    ("Boissons", "Eaux",                               "https://otrity.com/categorie-produit/boissons/eaux/"),
    ("Boissons", "Jus, Sirops et Boissons Végétales",  "https://otrity.com/categorie-produit/boissons/jus/"),

    # ── Produits Locaux ───────────────────────────────────────────────────────
    ("Le marché", "Épices, Olives et Condiments",  "https://otrity.com/categorie-produit/produits-locaux/epice/"),
    ("Le marché", "Épices, Olives et Condiments",  "https://otrity.com/categorie-produit/produits-locaux/harissa/"),
    ("Le marché", "Épices, Olives et Condiments",  "https://otrity.com/categorie-produit/produits-locaux/herbes/"),
    ("Le marché", "Fruits secs et séchés",         "https://otrity.com/categorie-produit/produits-locaux/fruit-et-legumes-secs/"),
    ("Le marché", "Légumes",                       "https://otrity.com/categorie-produit/produits-locaux/variantes-de-legumes/"),
    ("Épicerie Salée", "Légumineuses",             "https://otrity.com/categorie-produit/produits-locaux/legumineuses/"),
    ("Le marché", "Boulangerie et Pâtisserie",     "https://otrity.com/categorie-produit/produits-locaux/pain-tartes-et-quiches/"),
    ("Le marché", "Fruits secs et séchés",         "https://otrity.com/categorie-produit/produits-locaux/cereale/"),
]

seen_urls = set()


# ─────────────────────────────────────────────────────────────────────────────
# PRIX  "1,961 DT" → 1.961
# ─────────────────────────────────────────────────────────────────────────────
def parse_prix(text: str):
    if not text:
        return None
    cleaned = re.sub(r'[^\d,\.]', '', text.strip()).replace(',', '.')
    try:
        return round(float(cleaned), 3)
    except:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# NOM + QUANTITÉ
# "Biscuits Sablito fourrés aux figue 140gr"
#   → nom      = "Biscuits Sablito fourrés aux figue"
#   → quantite = 140.0
# ─────────────────────────────────────────────────────────────────────────────
def parse_nom_quantite(nom_raw: str):
    pattern = r'\b(\d+[\.,]?\d*)\s*(kg|gr?|mg|cl|ml|[lL]|pcs|un|unités?|pièces?|sachets?)\b'
    match   = re.search(pattern, nom_raw, re.IGNORECASE)
    if match:
        valeur    = float(match.group(1).replace(',', '.'))
        nom_clean = nom_raw[:match.start()] + nom_raw[match.end():]
        nom_clean = re.sub(r'[/\\]\s*', ' ', nom_clean)
        nom_clean = re.sub(r'\s+', ' ', nom_clean).strip(' -–')
        return nom_clean, valeur
    return nom_raw.strip(), None


# ─────────────────────────────────────────────────────────────────────────────
# NOM NORMALISÉ → stocké dans specifications (pas de colonne dédiée en Prisma)
# "Biscuits OXO Saida" → "biscuits oxo saida"
# ─────────────────────────────────────────────────────────────────────────────
def normalise_nom(nom: str) -> str:
    import unicodedata
    nom = nom.lower().strip()
    nom = unicodedata.normalize("NFD", nom)
    nom = nom.encode("ascii", "ignore").decode()
    nom = re.sub(r'[^a-z0-9\s]', ' ', nom)
    return re.sub(r'\s+', ' ', nom).strip()


# ─────────────────────────────────────────────────────────────────────────────
# DEBUG
# ─────────────────────────────────────────────────────────────────────────────
def debug_page(page):
    print(f"   🔍 Titre : {page.title()}")
    print(f"   🔍 li.product={len(page.query_selector_all('li.product'))} "
          f"| li.mainproduct={len(page.query_selector_all('li.mainproduct'))} "
          f"| article.product={len(page.query_selector_all('article.product'))}")


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPER UNE PAGE — RETOURNE DES DICTS 100% COMPATIBLES PRISMA
# ─────────────────────────────────────────────────────────────────────────────
def scrape_page(page, categorie: str, sous_categorie: str):
    local = []

    cards = (
        page.query_selector_all("li.mainproduct") or
        page.query_selector_all("li.product")     or
        page.query_selector_all("article.product")
    )

    if not cards:
        debug_page(page)
        return local

    print(f"   🔍 {len(cards)} cartes trouvées")

    for card in cards:
        try:
            # URL
            link_el  = card.query_selector("a.woocommerce-LoopProduct-link")
            prod_url = link_el.get_attribute("href") if link_el else None
            if not prod_url or prod_url in seen_urls:
                continue
            seen_urls.add(prod_url)

            # Nom brut → nettoyé + quantité
            nom_el  = (
                card.query_selector(".woocommerce-loop-product_title a") or
                card.query_selector(".woocommerce-loop-product__title")  or
                card.query_selector("h2 a")
            )
            nom_raw = nom_el.inner_text().strip() if nom_el else None
            if not nom_raw:
                continue

            nom, quantite = parse_nom_quantite(nom_raw)

            # Image
            img_el = card.query_selector("img")
            image  = ""
            if img_el:
                image = img_el.get_attribute("data-src") or img_el.get_attribute("src") or ""

            # Marque
            brand_el = card.query_selector(".yith-wcbr-brands a")
            marque   = brand_el.inner_text().strip() if brand_el else None

            # Prix
            ins_el    = card.query_selector("span.price ins .woocommerce-Price-amount")
            del_el    = card.query_selector("span.price del .woocommerce-Price-amount")
            simple_el = card.query_selector("span.price > .woocommerce-Price-amount")

            if ins_el and del_el:
                prix       = parse_prix(del_el.inner_text())   # prix normal (barré)
                prix_promo = parse_prix(ins_el.inner_text())   # prix soldé
                en_promo   = True
            elif simple_el:
                prix       = parse_prix(simple_el.inner_text())
                prix_promo = None
                en_promo   = False
            else:
                prix       = None
                prix_promo = None
                en_promo   = False

            sku = prod_url.rstrip("/").split("/")[-1]

            # ✅ STRUCTURE 100% COMPATIBLE PRISMA
            # - pas de createdAt/updatedAt  (Prisma les gère automatiquement)
            # - pas de id                   (Prisma autoincrement)
            # - pas de baseInitiales        (relation Prisma)
            # - nomNormalise → dans specifications (pas de colonne dédiée)
            local.append({
                "nom":           nom,                    # String  ✅
                "marque":        marque,                 # String? ✅
                "fournisseur":   None,                   # String? ✅
                "categorie":     categorie,              # String  ✅
                "sousCategorie": sous_categorie,         # String? ✅
                "image":         image,                  # String  ✅
                "prix":          prix or 0.0,            # Float   ✅
                "prixPromo":     prix_promo,             # Float?  ✅
                "prixPack":      None,                   # Float?  ✅
                "enPromo":       en_promo,               # Boolean ✅
                "enPack":        False,                  # Boolean ✅
                "contenuPack":   None,                   # String? ✅
                "quantite":      quantite,               # Float?  ✅ extrait du nom
                "quantiteStock": None,                   # Int?    ✅
                "marcheCible":   "B2C",                  # String? ✅
                "pointDeVente":  "Otrity",               # String? ✅
                "ville":         "Tunis",                # String? ✅
                "specifications": {                      # Json?   ✅
                    "description":  None,
                    "nomNormalise": normalise_nom(nom),  # ← stocké ici
                },
                "source":          "otrity.com",         # String  ✅
                "statut":          "valide",             # String  ✅
                "entrepriseId":    None,                 # Int?    ✅
                "contributeurId":  None,                 # Int?    ✅
                "sourcesDetails": {                      # Json?   ✅
                    "url":  prod_url,
                    "sku":  sku,
                    "site": "otrity.com",
                },
            })

        except Exception as e:
            print(f"   ⚠️ Erreur : {e}")

    return local


# ─────────────────────────────────────────────────────────────────────────────
# PAGINATION WOOCOMMERCE
# ─────────────────────────────────────────────────────────────────────────────
def scrape_category(page, base_url: str, categorie: str, sous_categorie: str):
    all_prods = []
    page_num  = 1

    while True:
        url = base_url if page_num == 1 else f"{base_url.rstrip('/')}/page/{page_num}/"
        print(f"\n   📄 Page {page_num} → {url}")

        try:
            resp = page.goto(url, wait_until="networkidle", timeout=45000)
            if resp and resp.status == 404:
                print("   ✅ Fin pagination")
                break
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            break

        time.sleep(4)
        for _ in range(4):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(0.8)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(1)

        prods = scrape_page(page, categorie, sous_categorie)
        if not prods:
            print("   ⚠️ Aucun produit → stop")
            break

        all_prods.extend(prods)

        for p in prods:
            q = f"{p['quantite']}g" if p['quantite'] else "---"
            print(
                f"   ✅ {p['categorie']:<22}"
                f"| {p['sousCategorie']:<28}"
                f"| {p['marque'] or '---':<12}"
                f"| {p['nom'][:32]:<32}"
                f"| {q:<8}"
                f"| {p['prix']} DT"
            )

        if not page.query_selector("a.next.page-numbers"):
            print("   ✅ Dernière page")
            break

        page_num += 1
        time.sleep(2)

    return all_prods


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def scrape():
    all_products = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        pg      = browser.new_page()
        pg.route("**/*.{mp4,webm,ogg}", lambda r: r.abort())

        print("🚀 Scraping Otrity.com → format Prisma\n")

        for (categorie, sous_categorie, url) in PAGES:
            print(f"\n{'='*75}")
            print(f"🏷️  {categorie}  →  {sous_categorie}")
            print(f"{'='*75}")
            prods = scrape_category(pg, url, categorie, sous_categorie)
            all_products.extend(prods)
            print(f"\n   → {len(prods)} produits pour '{sous_categorie}'")
            time.sleep(2)

        browser.close()

    # Dédoublonnage
    unique       = {p["sourcesDetails"]["url"]: p for p in all_products}
    all_products = list(unique.values())

    print(f"\n{'='*75}")
    print(f"🎉 TOTAL : {len(all_products)} produits uniques")
    print(f"{'='*75}")

    with open("otrity.json", "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)
    print("✅ Sauvegardé : otrity.json")

    from collections import Counter
    stats = Counter(f"{p['categorie']} / {p['sousCategorie']}" for p in all_products)
    print("\n📊 Répartition :")
    for k, v in sorted(stats.items()):
        print(f"  {k:<55} → {v:>4} produits")

    avec_q = sum(1 for p in all_products if p['quantite'])
    print(f"\n📦 Avec quantité : {avec_q}/{len(all_products)} produits")


if __name__ == "__main__":
    scrape()
