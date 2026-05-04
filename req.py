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

    def to_json(self) -> str:
        def serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        return json.dumps(asdict(self), default=serializer, ensure_ascii=False, indent=2)


prduit1 = Produit(nom="water", categorie="water", image="https;...", prix=1.0)
prduit2 = Produit(nom="fromage", categorie="fromage", image="https;...", prix=1.0)
prduit3 = Produit(nom="onion", categorie="onion", image="https;...", prix=1.0)

liste= [prduit1, prduit2, prduit3]

json_ = []
for produit in liste:
    json_.append(produit.to_json())

with open("file.json", "r+") as f:
    data = json.loads(f.read())
    print(data)


