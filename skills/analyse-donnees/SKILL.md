# Skill : Analyser les données produits

Interroger, filtrer, comparer et exporter les données scraped des JSON du projet.

## Structure des fichiers de données

```
carrefour.json     → liste de dicts (schéma Produit)
otrity.json        → liste de dicts (schéma Produit)
mg.json            → liste de dicts (schéma Produit)
tous_les_produits.json  → consolidation des 3 sources (généré par agent_orchestrateur.py)
```

Charger les données :
```python
import json
from pathlib import Path

def charger(fichier: str) -> list[dict]:
    path = Path(fichier)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))

carrefour = charger("carrefour.json")
tous = charger("tous_les_produits.json")
```

---

## Recettes d'analyse courantes

### Rechercher un produit par mot-clé
```python
def rechercher(produits, query):
    q = query.lower()
    return [p for p in produits if q in p.get("nom", "").lower()
            or q in p.get("categorie", "").lower()
            or q in str(p.get("marque", "")).lower()]

resultats = rechercher(tous, "lait")
for p in resultats[:10]:
    print(f"{p['nom']:40} {p.get('prix', '?'):>8} TND  — {p.get('pointDeVente', '?')}")
```

### Comparer les prix entre magasins
```python
def comparer_prix(produits, terme):
    mots = terme.lower().split()
    matches = [p for p in produits if all(m in p.get("nom", "").lower() for m in mots)]

    par_magasin = {}
    for p in matches:
        mag = p.get("pointDeVente", "?")
        prix_eff = p.get("prixPromo") or p.get("prix")
        if prix_eff:
            par_magasin.setdefault(mag, []).append((prix_eff, p["nom"]))

    for mag, items in sorted(par_magasin.items()):
        items.sort()
        print(f"\n{mag}:")
        for prix, nom in items[:5]:
            print(f"  {nom:45} {prix:.3f} TND")

comparer_prix(tous, "eau safia")
```

### Statistiques par catégorie
```python
from collections import Counter

categories = Counter(p.get("categorie", "?") for p in tous)
for cat, nb in categories.most_common(15):
    print(f"  {cat:40} {nb:5} produits")
```

### Produits en promotion
```python
en_promo = [p for p in tous if p.get("enPromo")]
print(f"{len(en_promo)} produits en promo sur {len(tous)} ({len(en_promo)/len(tous)*100:.1f}%)")

# Trier par économie absolue
def economie(p):
    if p.get("prix") and p.get("prixPromo"):
        return p["prix"] - p["prixPromo"]
    return 0

top_promos = sorted(en_promo, key=economie, reverse=True)[:10]
for p in top_promos:
    eco = economie(p)
    print(f"  {p['nom']:45} -{eco:.3f} TND ({p.get('pointDeVente', '?')})")
```

### Prix moyen par catégorie et par magasin
```python
from collections import defaultdict
import statistics

prix_par_cat_mag = defaultdict(list)
for p in tous:
    prix = p.get("prix")
    if prix and prix > 0:
        cle = (p.get("categorie", "?"), p.get("pointDeVente", "?"))
        prix_par_cat_mag[cle].append(prix)

for (cat, mag), prix_list in sorted(prix_par_cat_mag.items()):
    print(f"  {cat:30} {mag:25} moy={statistics.mean(prix_list):.3f} TND  n={len(prix_list)}")
```

---

## Analyser l'état des données (fraîcheur)

```python
from datetime import datetime
from pathlib import Path

for fichier in ["carrefour.json", "otrity.json", "mg.json", "tous_les_produits.json"]:
    p = Path(fichier)
    if p.exists():
        age = (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime))
        data = json.loads(p.read_text(encoding="utf-8"))
        print(f"  {fichier:30} {len(data):5} produits  (modifié il y a {age.seconds // 3600}h {(age.seconds % 3600) // 60}m)")
    else:
        print(f"  {fichier:30} ABSENT")
```

---

## Exporter les résultats

### Vers CSV (pour Excel)
```python
import csv

def exporter_csv(produits, fichier_sortie, champs=None):
    if not produits:
        return
    if champs is None:
        champs = ["nom", "categorie", "sousCategorie", "marque", "prix", "prixPromo", "enPromo", "quantite", "pointDeVente", "ville"]

    with open(fichier_sortie, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig pour Excel
        writer = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(produits)
    print(f"Exporté: {fichier_sortie} ({len(produits)} lignes)")

exporter_csv(tous, "export_produits.csv")
exporter_csv(en_promo, "export_promos.csv")
```

### Vers JSON filtré
```python
def exporter_json(produits, fichier_sortie):
    with open(fichier_sortie, "w", encoding="utf-8") as f:
        json.dump(produits, f, ensure_ascii=False, indent=2)
    print(f"Exporté: {fichier_sortie} ({len(produits)} produits)")
```

---

## Vérifier la qualité des données

```python
def rapport_qualite(produits, source=""):
    print(f"\n{'='*50}")
    print(f"Rapport qualité: {source or 'données'} ({len(produits)} produits)")
    print(f"{'='*50}")

    sans_prix = [p for p in produits if not p.get("prix")]
    sans_image = [p for p in produits if not p.get("image")]
    sans_categorie = [p for p in produits if not p.get("categorie")]
    prix_suspects = [p for p in produits if p.get("prix", 0) > 1000 or p.get("prix", 0) <= 0]

    print(f"  Sans prix     : {len(sans_prix):5} ({len(sans_prix)/len(produits)*100:.1f}%)")
    print(f"  Sans image    : {len(sans_image):5} ({len(sans_image)/len(produits)*100:.1f}%)")
    print(f"  Sans catégorie: {len(sans_categorie):5} ({len(sans_categorie)/len(produits)*100:.1f}%)")
    print(f"  Prix suspects : {len(prix_suspects):5} (≤0 ou >1000 TND)")

    magasins = Counter(p.get("pointDeVente", "?") for p in produits)
    print(f"\n  Répartition par magasin:")
    for mag, nb in magasins.most_common():
        print(f"    {mag:30} {nb:5}")

rapport_qualite(tous, "tous_les_produits.json")
```

---

## Utiliser l'agent IA pour l'analyse interactive

Pour une analyse conversationnelle, utiliser `agent_ia.py` :
```bash
set ANTHROPIC_API_KEY=votre_clé
python agent_ia.py
```

L'agent IA dispose des outils `rechercher_produits`, `comparer_prix`, `statistiques` et peut répondre à des questions en langage naturel sur les données.
