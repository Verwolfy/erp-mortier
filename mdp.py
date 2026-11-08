"""Utilitaire local de génération bcrypt, sans mot de passe intégré.

Usage : python mdp.py
Saisie masquée, sans écriture sur disque, sans modification du compte ERP.
Ne jamais coller le résultat dans un dépôt, une issue ou un journal public.
"""
from __future__ import annotations

from getpass import getpass


def hash_password(password: str) -> str:
    """Produit un hachage bcrypt ; refuse la troncature silencieuse à 72 octets."""
    if not isinstance(password, str):
        raise TypeError("Mot de passe invalide")
    data = password.encode("utf-8")
    if not data or len(data) > 72:
        raise ValueError("Mot de passe requis : de 1 à 72 octets UTF-8")
    import bcrypt

    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("ascii")


def main() -> int:
    try:
        password = getpass("Nouveau mot de passe (saisie masquée) : ")
        confirmation = getpass("Confirmation (saisie masquée) : ")
        if password != confirmation:
            print("Erreur : les saisies ne correspondent pas")
            return 2
        hashed = hash_password(password)
    except (KeyboardInterrupt, EOFError, ValueError, TypeError):
        print("Erreur : saisie interrompue ou mot de passe invalide")
        return 2
    finally:
        password = ""
        confirmation = ""
    print("Hachage bcrypt : ne pas publier dans Git ou les journaux.")
    print(hashed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
