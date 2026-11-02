"""Comparaison d'exemples fictifs, limitée à huit lignes de la table DGI 2022.

Aucune lecture/écriture, aucun remplacement du moteur réglementaire.
"""
from decimal import Decimal

# Lignes cas général pour les huit assiettes ; source : table DGI 2022.
_TABLE = {
    'SIM-RH-001': ('41000', '37310', '2481.30'),
    'SIM-RH-002': ('42000', '38220', '2690.60'),
    'SIM-RH-003': ('43000', '39130', '2899.90'),
    'SIM-RH-004': ('44000', '40040', '3110.80'),
    'SIM-RH-005': ('45000', '40950', '3356.50'),
    'SIM-RH-006': ('46000', '41860', '3602.20'),
    'SIM-RH-007': ('47000', '42770', '3847.90'),
    'SIM-RH-008': ('48000', '43680', '4093.60'),
}


def comparaison_dgi_2022(employe_id: str) -> dict:
    if employe_id not in _TABLE:
        raise ValueError("Employé hors du jeu fictif")
    brut, assiette, irg = map(Decimal, _TABLE[employe_id])
    cotisation = brut * Decimal('0.09')
    if brut - cotisation != assiette:
        raise ValueError("Assiette de l'exemple incohérente")
    return {'brut': brut, 'cotisation_salarie': cotisation, 'assiette_irg': assiette,
            'irg_table': irg, 'net': assiette - irg,
            'cotisation_employeur': brut * Decimal('0.25')}
