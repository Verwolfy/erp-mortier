"""
Configuration globale de l'application ERP.
Contient les IDs des Google Sheets et les constantes métier.
"""

# ID des fichiers Google Sheets (à remplir avec vos vrais IDs Drive)
SHEETS_IDS = {
    "referentiels": "1cOHpokuDEqFtp6SWE-PU9F99fpNJ5vDQgZr6Uly9bg0",
    "achats": "1QwfKpOMXf8Jl3DGIDSD0LLOCBT8VrDDzS8D3rMrYXfg",
    "stocks": "109zOLr1LBLmATCRyfViIqQsFTImB3TgEdsYOG3zbUqE",
    "production": "125h970ptpIQB-iaQJ4dBLrLdtGcNoCqgR8dT2Ift-FA",
    "ventes": "1R02zaBs1LPzKX12mx4NEYXF2-Ydmul9HHyfaK8yzLi0",
    "crm": "1sRAB9aDx4OJQbi3hEXepamjhglmg82ChAtEXCxT_MZY",
    "rh": "1pxMLio5QW3IAG8o1Tn7V79bbrVi5NQppBXo3z_1-ncg",
    "logs": "1FM55VjF04b4lQinlIwByMIMIUsRlUnlb_lZi84Bsy4c",
    "finance": "1LsIv4jbv7gSr-T8qyBqc0186ep1miRxkNS2-UexMh-I"
}

# Configuration de l'application
APP_NAME = "ERP Mortier, Adjuvants & Peinture"
APP_VERSION = "1.0.0" # Passage en v1 suite à la refonte complète !

# Fuseau horaire (Critique pour la synchronisation des données et la création d'IDs)
TIMEZONE = "Africa/Algiers"