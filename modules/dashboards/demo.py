"""Scénario de démonstration des 9 KPI : mémoire uniquement, jamais en base.

Références DEMO-KPI-*/SIM-KPI-* explicites pour éviter toute confusion avec
un document, montant fiscal, salarié ou justificatif réel. Aucune connexion
externe, aucun chargement de clé, aucune écriture Supabase.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

SCENARIO_VERSION = "DEMO-KPI-20261107-01"


def _day(value: date) -> str:
    return value.isoformat()


def build_demo_dataset(today: date | datetime) -> dict[str, list[dict]]:
    """Jeu déterministe ancré à la date du rendu, 9 onglets cohérents.

    Les scénarios sont fictifs ; taux de change et montants TTC ne constituent
    aucune qualification fiscale ou cotation de marché.
    """
    if isinstance(today, datetime):
        today = today.date()
    if not isinstance(today, date):
        raise TypeError("Date de référence requise")

    first = today.replace(day=1)
    previous = first - timedelta(days=1)
    long_overdue = today - timedelta(days=65)
    dates_mois = [today - timedelta(days=d)
                  for d in range(0, min(today.day - 1, 16) + 1, 2)]
    dates_mois.sort()

    invoices, lines = [], []
    for i, day in enumerate(dates_mois, 1):
        ht = 65000 + (i % 4) * 12000
        invoices.append({
            "facture_id": f"DEMO-KPI-FAC-{i:02d}",
            "type_facture": "FactureClient", "statut": "VALIDE",
            "date": _day(day), "date_echeance": _day(day + timedelta(days=25)),
            "client_id": f"DEMO-KPI-CLI-{(i % 3) + 1}",
            "montant_ht": ht, "montant_ttc": ht + 9500,
            "montant_paye": 0 if i % 3 else 12000, "montant_timbre": 0,
        })
        lines.append({
            "facture_id": f"DEMO-KPI-FAC-{i:02d}",
            "sku_id": f"DEMO-KPI-SKU-{(i % 2) + 1}",
            "quantite": 20 + i,
        })
    invoices.extend([
        {"facture_id": "DEMO-KPI-ANCIEN", "type_facture": "FactureClient",
         "statut": "VALIDE", "date": _day(long_overdue),
         "date_echeance": _day(today - timedelta(days=45)),
         "client_id": "DEMO-KPI-CLI-1", "montant_ht": 145000,
         "montant_ttc": 153000, "montant_paye": 0, "montant_timbre": 0},
        {"facture_id": "DEMO-KPI-BROUILLON", "type_facture": "FactureClient",
         "statut": "BROUILLON", "date": _day(today),
         "date_echeance": _day(today + timedelta(days=30)),
         "client_id": "DEMO-KPI-CLI-2", "montant_ht": 999999,
         "montant_ttc": 999999, "montant_paye": 0, "montant_timbre": 0},
    ])
    lines.append({"facture_id": "DEMO-KPI-ANCIEN", "sku_id": "DEMO-KPI-SKU-1",
                  "quantite": 30})

    purchases, purchase_lines = [], []
    for i, day in enumerate(dates_mois[:7], 1):
        eur = i % 3 == 0
        price = 5.5 + i if eur else 720 + i * 12
        fx = 143.0 if eur else 1.0  # Valeur purement fictive, non taux officiel.
        purchases.append({
            "commande_achat_id": f"DEMO-KPI-CMD-{i:02d}",
            "date_commande": _day(day), "date_voulue": _day(day + timedelta(days=6)),
            "fournisseur_id": "DEMO-KPI-F-MP",
            "devise": "EUR" if eur else "DZD", "taux_change": fx,
            "montant_total_local": 50 * price * fx,
            "statut": "RECEPTIONNE" if i % 3 == 0 else "EN_ATTENTE",
        })
        purchase_lines.append({
            "commande_achat_id": f"DEMO-KPI-CMD-{i:02d}",
            "mp_id": "DEMO-KPI-MP-CIMENT", "unite_cond": "KG",
            "prix_unitaire": price,
        })
    purchases.append({
        "commande_achat_id": "DEMO-KPI-CMD-RETARD",
        "date_commande": _day(previous - timedelta(days=12)),
        "date_voulue": _day(today - timedelta(days=10)),
        "fournisseur_id": "DEMO-KPI-F-MP", "devise": "DZD",
        "taux_change": 1, "montant_total_local": 80000, "statut": "EN_ATTENTE",
    })

    controls = []
    orders = []
    for i, day in enumerate(dates_mois[:8], 1):
        status = ("TERMINE", "TERMINE", "EN_COURS", "PLANIFIE", "REJETE")[i % 5]
        orders.append({"of_id": f"DEMO-KPI-OF-{i:02d}",
                       "date_planification": _day(day), "statut": status})
        if i % 4 != 0:
            controls.append({"qc_id": f"DEMO-KPI-CQ-{i:02d}",
                             "date": _day(day), "conforme": "NON" if i % 3 == 0 else "OUI"})

    payments = []
    for i, day in enumerate(dates_mois[:8], 1):
        incoming = i % 3 != 0
        amount = 25000 + 7500 * i
        payments.append({
            "reglement_id": f"DEMO-KPI-REG-{i:02d}", "statut": "VALIDE",
            "date_reglement": _day(day), "compte_id": "DEMO-KPI-BANQUE",
            "type_flux": "ENCAISSEMENT" if incoming else "DECAISSEMENT",
            "partenaire_id": "DEMO-KPI-CLI-1" if incoming else "DEMO-KPI-F-OPEX",
            "montant_total": amount,
            "montant_alloue": amount // 2 if incoming else 0,
        })
    payments.append({
        "reglement_id": "DEMO-KPI-REG-BROUILLON", "statut": "BROUILLON",
        "date_reglement": _day(today), "compte_id": "DEMO-KPI-BANQUE",
        "type_flux": "ENCAISSEMENT", "partenaire_id": "DEMO-KPI-CLI-1",
        "montant_total": 5000000, "montant_alloue": 0,
    })

    return {
        "factures": invoices,
        "lignes_facture": lines,
        "stock_actuel_pf": [
            {"sku_id": "DEMO-KPI-SKU-1", "quantite_disponible": 300,
             "cout_revient": 1200},
            {"sku_id": "DEMO-KPI-SKU-2", "quantite_disponible": 180,
             "cout_revient": 1700},
        ],
        "stock_actuel": [
            {"mp_id": "DEMO-KPI-MP-CIMENT", "quantite_disponible": 1200, "cmp_actuel": 80},
            {"mp_id": "DEMO-KPI-MP-ADJUVANT", "quantite_disponible": 35, "cmp_actuel": 380},
            {"mp_id": "DEMO-KPI-MP-SABLE", "quantite_disponible": 4200, "cmp_actuel": 30},
            {"mp_id": "DEMO-KPI-MP-EMBALLAGE", "quantite_disponible": 180,
             "cmp_actuel": 25},
        ],
        "matieres_premieres": [
            {"mp_id": "DEMO-KPI-MP-CIMENT", "stock_mini": 1500},
            {"mp_id": "DEMO-KPI-MP-ADJUVANT", "stock_mini": 70},
            {"mp_id": "DEMO-KPI-MP-SABLE", "stock_mini": 1000},
            {"mp_id": "DEMO-KPI-MP-EMBALLAGE", "stock_mini": None},
        ],
        "lots": [
            {"lot_id": "DEMO-KPI-LOT-EXPIRE", "quantite_restante": 8,
             "date_peremption": _day(today - timedelta(days=9))},
            {"lot_id": "DEMO-KPI-LOT-BIENTOT", "quantite_restante": 24,
             "date_peremption": _day(today + timedelta(days=15))},
            {"lot_id": "DEMO-KPI-LOT-LOINTAIN", "quantite_restante": 70,
             "date_peremption": _day(today + timedelta(days=250))},
            {"lot_id": "DEMO-KPI-LOT-SANS-DATE", "quantite_restante": 3,
             "date_peremption": None},
        ],
        "commandes_achats": purchases,
        "lignes_achats": purchase_lines,
        "fournisseurs": [
            {"fournisseur_id": "DEMO-KPI-F-MP", "categorie": "MATIERES"},
            {"fournisseur_id": "DEMO-KPI-F-OPEX", "categorie": "SERVICES OPEX"},
        ],
        "comptes": [
            {"compte_id": "DEMO-KPI-BANQUE", "nom_compte": "Banque DEMO",
             "type_compte": "Banque", "solde_initial": 600000},
            {"compte_id": "DEMO-KPI-CAISSE", "nom_compte": "Caisse DEMO",
             "type_compte": "Caisse", "solde_initial": 45000},
        ],
        "reglements": payments,
        "fiches_de_paie": [
            {"fiche_paie_id": "SIM-KPI-PAIE-01", "annee": today.year,
             "mois": today.month, "net_a_payer": 105000,
             "statut_paiement": "BROUILLON"},
        ],
        "ordres_fabrication": orders,
        "controle_qualite": controls,
        "pipeline": [
            {"opportunite_id": "DEMO-KPI-OP-1", "statut": "Nouveau",
             "valeur_estimee": 180000, "probabilite_pct": 20,
             "date_creation": _day(today), "commercial_id": "SIM-KPI-VENDEUR-1"},
            {"opportunite_id": "DEMO-KPI-OP-2", "statut": "En Négociation",
             "valeur_estimee": 450000, "probabilite_pct": 65,
             "date_creation": _day(today), "commercial_id": "SIM-KPI-VENDEUR-2"},
            {"opportunite_id": "DEMO-KPI-OP-3", "statut": "Gagné",
             "valeur_estimee": 120000, "probabilite_pct": 100,
             "date_creation": _day(today), "commercial_id": "SIM-KPI-VENDEUR-1"},
            {"opportunite_id": "DEMO-KPI-OP-4", "statut": "Perdu",
             "valeur_estimee": 105000, "probabilite_pct": 0,
             "date_creation": _day(today), "commercial_id": "SIM-KPI-VENDEUR-2"},
        ],
        "employes": [
            {"employe_id": "SIM-KPI-SAL-1", "actif": "OUI", "service": "Production"},
            {"employe_id": "SIM-KPI-SAL-2", "actif": "OUI", "service": "Production"},
            {"employe_id": "SIM-KPI-SAL-3", "actif": "OUI", "service": "Commercial"},
            {"employe_id": "SIM-KPI-SAL-4", "actif": "NON", "service": "Logistique"},
        ],
        "demandes_conges": [
            {"demande_conge_id": "SIM-KPI-CONGE-1", "statut": "EN_ATTENTE"},
            {"demande_conge_id": "SIM-KPI-CONGE-2", "statut": "VALIDE"},
        ],
    }
