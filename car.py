from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import time

products = []
seen_skus = set()
current_category = ""

pages_to_scrape = [
    

    # ── Le marché ──────────────────────────────────────────────────────────────
    ("Le marché", "Légumes",                      "https://www.carrefour.tn/le-marche/legumes.html?page=1"),
    ("Le marché", "Fruits de saison",             "https://www.carrefour.tn/le-marche/fruits-de-saison.html?page=1"),
    ("Le marché", "Fruits secs et séchés",        "https://www.carrefour.tn/le-marche/fruits-secs-et-seches.html?page=1"),
    ("Le marché", "Volaille",                     "https://www.carrefour.tn/le-marche/volaille.html?page=1"),
    ("Le marché", "Boucherie",                    "https://www.carrefour.tn/le-marche/boucherie.html?page=1"),
    ("Le marché", "Poissons",                     "https://www.carrefour.tn/le-marche/poissons.html?page=1"),
    ("Le marché", "Boulangerie et Pâtisserie",    "https://www.carrefour.tn/le-marche/boulangerie-et-patisserie.html?page=1"),
    ("Le marché", "Œufs",                         "https://www.carrefour.tn/le-marche/oeufs.html?page=1"),
    ("Le marché", "Épices, Olives et Condiments", "https://www.carrefour.tn/le-marche/epices-olives-et-condiments.html?page=1"),
    ("Le marché", "Charcuterie",                  "https://www.carrefour.tn/le-marche/charcuterie.html?page=1"),
    ("Le marché", "Traiteur",                     "https://www.carrefour.tn/le-marche/traiteur.html?page=1"),

    # ── Crèmerie et Produits Laitiers ──────────────────────────────────────────
    ("Crèmerie et Produits Laitiers", "Lait",                              "https://www.carrefour.tn/cremerie-et-produits-laitiers/lait.html?page=1"),
    ("Crèmerie et Produits Laitiers", "Les Œufs",                         "https://www.carrefour.tn/cremerie-et-produits-laitiers/les-oeufs.html?page=1"),
    ("Crèmerie et Produits Laitiers", "Yaourts et Fromages blancs",       "https://www.carrefour.tn/cremerie-et-produits-laitiers/yaourts-et-fromages-blancs.html?page=1"),
    ("Crèmerie et Produits Laitiers", "Beurre, Crèmes Fraîches et Chantilly", "https://www.carrefour.tn/cremerie-et-produits-laitiers/beurre-cremes-fraiches-et-chantilly.html?page=1"),
    ("Crèmerie et Produits Laitiers", "Fromages",                         "https://www.carrefour.tn/cremerie-et-produits-laitiers/fromages.html?page=1"),
    ("Crèmerie et Produits Laitiers", "Fromages à la coupe",              "https://www.carrefour.tn/cremerie-et-produits-laitiers/fromages-a-la-coupe.html?page=1"),

    # ── Boissons ───────────────────────────────────────────────────────────────
    ("Boissons", "Eaux",                               "https://www.carrefour.tn/boissons/eaux.html?page=1"),
    ("Boissons", "Boissons Gazeuses",                  "https://www.carrefour.tn/boissons/boissons-gazeuses.html?page=1"),
    ("Boissons", "Boissons Aromatisées et Ice Tea",    "https://www.carrefour.tn/boissons/boissons-aromatisees-et-ice-tea.html?page=1"),
    ("Boissons", "Jus, Sirops et Boissons Végétales",  "https://www.carrefour.tn/boissons/jus-sirops-et-boissons-vegetales.html?page=1"),
    ("Boissons", "Énergétiques et Bière Sans Alcool",  "https://www.carrefour.tn/boissons/energetiques-et-biere-sans-alcool.html?page=1"),

    # ── Épicerie Sucrée ────────────────────────────────────────────────────────
    ("Épicerie Sucrée", "Café",                                  "https://www.carrefour.tn/epicerie-sucree/cafe.html?page=1"),
    ("Épicerie Sucrée", "Thés et Infusions",                     "https://www.carrefour.tn/epicerie-sucree/thes-et-infusions.html?page=1"),
    ("Épicerie Sucrée", "Petit Déjeuner",                        "https://www.carrefour.tn/epicerie-sucree/petit-dejeuner.html?page=1"),
    ("Épicerie Sucrée", "Gâteaux Moelleux",                      "https://www.carrefour.tn/epicerie-sucree/gateaux-moelleux.html?page=1"),
    ("Épicerie Sucrée", "Biscuits",                              "https://www.carrefour.tn/epicerie-sucree/biscuits.html?page=1"),
    ("Épicerie Sucrée", "Bonbons et Chocolats",                  "https://www.carrefour.tn/epicerie-sucree/bonbons-et-chocolats.html?page=1"),
    ("Épicerie Sucrée", "Sucre, Farine et Préparation Pâtisserie","https://www.carrefour.tn/epicerie-sucree/sucre-farine-et-preparation-patisserie.html?page=1"),
    ("Épicerie Sucrée", "Conserves de Fruits",                   "https://www.carrefour.tn/epicerie-sucree/conserves-de-fruits.html?page=1"),

    # ── Épicerie Salée ─────────────────────────────────────────────────────────
    ("Épicerie Salée", "Huiles",                        "https://www.carrefour.tn/epicerie-salee/huiles.html?page=1"),
    ("Épicerie Salée", "Thon et Sardine",               "https://www.carrefour.tn/epicerie-salee/thon-et-sardine.html?page=1"),
    ("Épicerie Salée", "Conserves et Plats Cuisinés",   "https://www.carrefour.tn/epicerie-salee/conserves-et-plats-cuisines.html?page=1"),
    ("Épicerie Salée", "Sauces et Assaisonnements",     "https://www.carrefour.tn/epicerie-salee/sauces-et-assaisonnements.html?page=1"),
    ("Épicerie Salée", "Pâtes Couscous et Riz",         "https://www.carrefour.tn/epicerie-salee/pates-couscous-et-riz.html?page=1"),
    ("Épicerie Salée", "Blé et Semoule",                "https://www.carrefour.tn/epicerie-salee/ble-et-semoule.html?page=1"),
    ("Épicerie Salée", "Barquettes à garnir",           "https://www.carrefour.tn/epicerie-salee/barquettes-a-garnir.html?page=1"),
    ("Épicerie Salée", "Feuilles de Bricks",            "https://www.carrefour.tn/epicerie-salee/feuilles-de-bricks.html?page=1"),
    ("Épicerie Salée", "Snack et Apéritif",             "https://www.carrefour.tn/epicerie-salee/snack-et-aperitif.html?page=1"),
    ("Épicerie Salée", "Produits Asiatiques",           "https://www.carrefour.tn/epicerie-salee/produits-asiatiques.html?page=1"),

    # ── Surgelés ───────────────────────────────────────────────────────────────
    ("Surgelés", "Pâtes Surgelées",          "https://www.carrefour.tn/surgeles/pates-surgelees.html?page=1"),
    ("Surgelés", "Légumes et Fruits",        "https://www.carrefour.tn/surgeles/legumes-et-fruits.html?page=1"),
    ("Surgelés", "Viandes surgelées",        "https://www.carrefour.tn/surgeles/viandes-surgelees.html?page=1"),
    ("Surgelés", "Poissons et Fruits de Mer","https://www.carrefour.tn/surgeles/poissons-et-fruits-de-mer.html?page=1"),
    ("Surgelés", "Glaces et Gâteaux glacés", "https://www.carrefour.tn/surgeles/glaces-et-gateaux-glaces.html?page=1"),
]



def safe_dict(obj):
    if isinstance(obj, dict): return obj
    if isinstance(obj, list) and obj and isinstance(obj[0], dict): return obj[0]
    return {}

def extract_product(p, categorie):
    if not isinstance(p, dict) or not p.get("name"):
        return None

    # ── Prix ──────────────────────────────────────────
    price_range = safe_dict(p.get("price_range"))
    max_price   = safe_dict(price_range.get("maximum_price"))
    final       = safe_dict(max_price.get("final_price")).get("value")
    regular     = safe_dict(max_price.get("regular_price")).get("value")
    is_promo    = bool(final and regular and final < regular)

    # ── Extra data ────────────────────────────────────
    extra = safe_dict(p.get("extraData"))
    brand = safe_dict(extra.get("brand")).get("title")
    image = safe_dict(p.get("small_image")).get("url") or extra.get("image", "")

    # ── Sous-catégorie automatique ────────────────────
    categories     = p.get("categories", [])
    sous_categorie = categories[-1].get("name") if categories else None

    # ── Quantité ──────────────────────────────────────
    quantite_raw = extra.get("weight_per_unit_attribute") or extra.get("large_size")
    try:
        quantite = float(quantite_raw) if quantite_raw else None
    except:
        quantite = None

    now = datetime.utcnow().isoformat()

    return {
        # ✅ Champs obligatoires
        "nom":             p.get("name", ""),
        "categorie":       categorie,
        "image":           image,
        "prix":            regular or final or 0.0,

        # ✅ Champs optionnels
        "marque":          brand,
        "fournisseur":     None,                        # pas dispo sur Carrefour                        # pas dispo sur Carrefour
        "sousCategorie":   sous_categorie,
        "prixPromo":       final if is_promo else None,
        "prixPack":        None,                        # pas dispo sur Carrefour
        "enPromo":         is_promo,
        "enPack":          False,
        "quantite":        quantite,
        "quantiteStock":   None,                        # pas dispo sur Carrefour
        "marcheCible":     "B2C",
        "pointDeVente":    "Carrefour Tunisie",
        "ville":           "Tunis",
        "specifications":  {
            "description": p.get("short_description", {}).get("html", ""),
            "sku":         p.get("sku"),
        },
        "source":          "carrefour.tn",
        "entrepriseId":    None,
        "contributeurId":  None,
        "actif":           True,
        "createdAt":       now,
        "updatedAt":       now,
        "sourcesDetails":  {
            "url":         f"https://www.carrefour.tn/{p.get('url_key', '')}.html",
            "sku":         p.get("sku"),
            "site":        "carrefour.tn",
        },
        "baseInitiales":   None,
    }

def scrape():
    global current_category

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()

        def handle_response(response):
            try:
                if "graphql" in response.url and "products" in response.url:
                    data = response.json()
                    items = []

                    def find_items(d):
                        if isinstance(d, dict):
                            if "items" in d and isinstance(d["items"], list):
                                items.extend(d["items"])
                            for v in d.values(): find_items(v)
                        elif isinstance(d, list):
                            for i in d: find_items(i)

                    find_items(data)

                    for item in items:
                        sku = item.get("sku")
                        if not sku or sku in seen_skus:
                            continue
                        prod = extract_product(item, current_category)
                        if prod:
                            seen_skus.add(sku)
                            products.append(prod)
                            print(f"✅ {prod['categorie']:<30} | {prod['sousCategorie'] or '---':<25} | {prod['nom'][:35]:<35} | {prod['prix']} DT")
            except:
                pass

        page.on("response", handle_response)

        for cat_name, url in pages_to_scrape:
            current_category = cat_name
            print(f"\n🔥 Scraping : {cat_name}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(4)

            for i in range(20):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2.5)

        browser.close()

    print(f"\n🎉 TERMINÉ → {len(products)} produits récupérés")

    with open("carrefour.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    print("✅ Sauvegardé : carrefour.json")

if __name__ == "__main__":
    scrape()