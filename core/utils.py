"""
Utilitaires globaux de l'application.
Gestion des dates et génération stricte des identifiants (séquentiels vs techniques).
"""
import uuid
from datetime import datetime
import pytz
from config.settings import TIMEZONE

def get_local_now() -> datetime:
    """Retourne la date et l'heure actuelles selon le fuseau horaire configuré."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz)

def generate_unique_id(prefix: str, existing_ids: list) -> str:
    """
    Génère un identifiant SÉQUENTIEL LISIBLE (ex: PREFIXE-0001).
    Réservé aux entités à faible volume (Fournisseurs, Clients, Produits, etc.).
    """
    if not existing_ids:
        return f"{prefix}-0001"

    max_num = 0
    for current_id in existing_ids:
        if current_id.startswith(f"{prefix}-"):
            try:
                # Extrait la partie numérique après le tiret
                num = int(current_id.split("-")[1])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue

    next_num = max_num + 1
    return f"{prefix}-{str(next_num).zfill(4)}"

def generate_technical_id(prefix: str) -> str:
    """
    Génère un identifiant TECHNIQUE UUID (ex: PREFIXE-A1B2C3D4E5).
    Réservé aux entités à haut volume où la lecture préalable créerait un goulot d'étranglement
    (LignesAchats, Mouvements, LignesFacture, etc.).
    """
    unique_hash = uuid.uuid4().hex[:10].upper()
    return f"{prefix}-{unique_hash}"