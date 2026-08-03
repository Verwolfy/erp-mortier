"""
Service de journalisation (Logs).
Enregistre la traçabilité des actions et les erreurs dans ERP_Logs.
Conforme au schéma docs/schema_reference.md.
"""
import traceback
from core.sheets_service import append_rows_batch
from core.utils import get_local_now


def log_audit(user_id: str, module: str, action: str, detail: str):
    """
    Enregistre une action utilisateur dans l'onglet AuditTrail.
    Colonnes : timestamp, user_id, module, action, detail
    """
    try:
        timestamp = get_local_now().strftime("%Y-%m-%d %H:%M:%S")
        ligne_audit = [timestamp, user_id, module, action, detail]
        append_rows_batch("logs", "AuditTrail", [ligne_audit])
    except Exception as e:
        # On print l'erreur dans la console du serveur pour ne pas bloquer l'application
        print(f"Erreur lors de l'enregistrement de l'audit : {e}")


def log_error(module: str, message: str, contexte: str = ""):
    """
    Enregistre une erreur système ou un crash dans l'onglet Erreurs.
    Colonnes : timestamp, module, message, contexte
    """
    try:
        timestamp = get_local_now().strftime("%Y-%m-%d %H:%M:%S")

        # Si aucun contexte n'est fourni, on tente de capturer la pile d'exécution
        if not contexte:
            contexte = traceback.format_exc()
            if contexte == "NoneType: None\n":
                contexte = "Aucune trace disponible."

        ligne_erreur = [timestamp, module, message, contexte]
        append_rows_batch("logs", "Erreurs", [ligne_erreur])
    except Exception as e:
        print(f"Erreur critique lors de l'enregistrement du log d'erreur : {e}")