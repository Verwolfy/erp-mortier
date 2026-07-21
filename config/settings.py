"""
Configuration globale de l'application.
Contient les IDs des Google Sheets et les constantes métier.
"""

# ID des 7 fichiers Google Sheets (à remplir une fois créés sur le Drive partagé)
# L'ID se trouve dans l'URL : https://docs.google.com/spreadsheets/d/CET_ID_ICI/edit
SHEETS_IDS = {
    "referentiels": "A_REMPLIR_ID_REFERENTIELS",
    "achats": "A_REMPLIR_ID_ACHATS",
    "stocks": "A_REMPLIR_ID_STOCKS",
    "production": "A_REMPLIR_ID_PRODUCTION",
    "ventes": "A_REMPLIR_ID_VENTES",
    "crm": "A_REMPLIR_ID_CRM",
    "logs": "A_REMPLIR_ID_LOGS"
}

# Configuration de l'application
APP_NAME = "ERP Mortier, Adjuvants & Peinture"
APP_VERSION = "0.1.0"
TIMEZONE = "Africa/Algiers" # Important pour l'horodatage et le verrouillage optimiste

# Paramètres de l'API Google Sheets (Limites et Retry)
GSPREAD_MAX_RETRIES = 5
GSPREAD_BACKOFF_FACTOR = 2