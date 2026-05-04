from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
import time
from bs4 import BeautifulSoup


from dataclasses import dataclass, asdict, field
from typing import Optional, Any, List, Dict
from datetime import datetime
import json

@dataclass
class Produit:
    nom: str
    categorie: str
    image: str
    prix: float
    marque: Optional[str] = None
    fournisseur: Optional[str] = None
    modele: Optional[str] = None
    sousCategorie: Optional[str] = None
    prixPromo: Optional[float] = None
    prixPack: Optional[float] = None
    enPromo: bool = False
    enPack: bool = False
    quantite: Optional[float] = None
    quantiteStock: Optional[int] = None
    marcheCible: Optional[str] = None
    pointDeVente: Optional[str] = None
    ville: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    source: str = "manuel"
    entrepriseId: Optional[int] = None
    contributeurId: Optional[int] = None
    actif: bool = True
    createdAt: datetime = field(default_factory=datetime.utcnow)
    updatedAt: datetime = field(default_factory=datetime.utcnow)
    sourcesDetails: Optional[Dict[str, Any]] = None
    baseInitiales: Optional[List[Any]] = None  # Replace Any with a proper type if defined

    def to_json(self) -> str:
        def serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        return json.dumps(asdict(self), default=serializer, ensure_ascii=False, indent=2)

options = Options()
options.add_experimental_option('excludeSwitches', ['enable-logging'])

# ←←← Change ce chemin avec le tien !!!
service = Service(r"C:\Users\21654\OneDrive\Bureau\web scrapping\msedgedriver.exe")

driver = webdriver.Edge(service=service, options=options)

driver.maximize_window()


driver.get("https://www.carrefour.tn/le-marche.html?page=1")

wait_large = WebDriverWait(driver, 500)
wait_mini = WebDriverWait(driver, 5)


time.sleep(5)

shadow_host = wait_large.until(EC.presence_of_element_located((By.XPATH, "//aside[@id='usercentrics-cmp-ui']")))

shadow_root = shadow_host.shadow_root
button_close = shadow_root.find_element(By.CSS_SELECTOR, "button#deny")

button_close.click()

elements = driver.find_elements(By.XPATH, "//div[@class='category-categoryItem-7pb grid gap-y-2xs']")

links_to_items = []

for element in elements:
    tag_element = element.find_element(By.TAG_NAME, "a")
    link = tag_element.get_attribute("href")
    links_to_items.append(link)

def parse_item_link(driver, link):
    driver.get(link)
    time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Nom
    nom = soup.select_one("h1.productFullDetail-productName-Qe1")
    nom = nom.get_text(strip=True) if nom else ""

    # Prix fractionné
    prix_entier = soup.select_one("span.price-integer-tLc")
    prix_decimal = soup.select_one("span.price-decimal-soS")
    prix_entier = prix_entier.get_text(strip=True) if prix_entier else "0"
    prix_decimal = prix_decimal.get_text(strip=True) if prix_decimal else "0"
    try:
        prix = float(f"{prix_entier}.{prix_decimal}")
    except:
        prix = 0.0

    # Image
    image = soup.select_one("div.pswp-gallery a")
    image_url = image["href"] if image else ""

    # Catégorie / sous-catégorie
    categorie, sousCategorie = "", ""
    breadcrumb = soup.select_one("a#allProducts")
    if breadcrumb:
        href = breadcrumb.get("href", "")
        if "legumes" in href:
            categorie = "Légumes"
        if "legumes-de-saison" in href:
            sousCategorie = "Légumes de saison"

    # Description
    description = soup.select_one("div#description")
    description = description.get_text(strip=True) if description else ""

    produit = Produit(
        nom=nom,
        categorie=categorie,
        sousCategorie=sousCategorie,
        image=image_url,
        prix=prix,
        marcheCible="Marche",
        pointDeVente="Carrefour Tunisie",
        ville="Tunisie",
        specifications={"description": description},
        sourcesDetails={"url": link}
    )

    return produit




liste_produit = []
for link in links_to_items:
    produit = parse_item_link(driver=driver, link=link)
    if produit:
        liste_produit.append(produit)
        print(produit.to_json())  # affichage JSON pour vérifier




#element_close = wait_large.until(EC.element_to_be_clickable((By.XPATH, "//button[@id='deny']")))

#element_close.click()

time.sleep(3)



# driver.quit()