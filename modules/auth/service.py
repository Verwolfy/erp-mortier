"""
Logique métier de l'authentification.
Vérification des accès via l'onglet Users.
"""
import bcrypt
from core.sheets_service import get_all_records

def hash_password(password: str) -> str:
    """
    Génère un hash bcrypt à partir d'un mot de passe en clair.
    Utile si vous devez créer un script pour initialiser vos premiers utilisateurs.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def authenticate_user(login: str, password_attempt: str) -> dict:
    """
    Vérifie les identifiants de l'utilisateur.
    Retourne le dictionnaire de l'utilisateur si succès, sinon None.
    """
    users = get_all_records("referentiels", "Users")

    if not users:
        return None

    for u in users:
        if str(u.get("login", "")) == login and str(u.get("actif", "")).upper() == "OUI":
            # Le hash stocké dans la colonne hash_mdp de Google Sheets
            stored_hash = str(u.get("hash_mdp", "")).encode('utf-8')

            # Comparaison sécurisée avec bcrypt
            if bcrypt.checkpw(password_attempt.encode('utf-8'), stored_hash):
                return {
                    "user_id": u.get("user_id"),
                    "nom": u.get("nom"),
                    "role": u.get("role")
                }
    return None