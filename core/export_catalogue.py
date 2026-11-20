"""Catalogue explicite des rapports ERP autorisés.

Pas de service_role, aucune table de secrets, comptes utilisateurs, fiches de
paie, journaux de sécurité ni registre fiscal de qualification dans l'export
générique. Les lectures restent soumises aux permissions par TABLE.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class ReportSpec:
    family: str
    title: str
    table: str
    columns: tuple[str, ...]
    date_column: str | None = None
    warning: str = "rapport de consultation, non signé et non certifié"


def _spec(family, title, table, columns, date_column=None, warning=None):
    return ReportSpec(
        family=family, title=title, table=table,
        columns=tuple(columns.split()),
        date_column=date_column,
        warning=warning or "rapport de consultation, non signé et non certifié",
    )


REPORTS: dict[str, ReportSpec] = {
    # Administration : colonne de contact, identifiants fiscaux, hashes,
    # mots de passe et données personnelles détaillées volontairement exclus.
    "referentiel_mp": _spec("Référentiels", "Matières premières et emballages",
        "matieres_premieres", "mp_id nom categorie_mp unite_stock actif cmp_actuel stock_mini stock_maxi"),
    "referentiel_pf": _spec("Référentiels", "Produits finis",
        "produits", "pf_id nom categorie_pf unite_production actif"),
    "referentiel_sku": _spec("Référentiels", "Conditionnements et tarifs catalogue",
        "sku_conditionnement", "sku_id pf_id format unite_vente poids_net facteur_conversion prix_vente_defaut actif"),
    "referentiel_clients": _spec("Référentiels", "Répertoire clients (restreint)",
        "clients", "client_id nom categorie_client type_client pays wilaya actif"),
    "referentiel_fournisseurs": _spec("Référentiels", "Répertoire fournisseurs (restreint)",
        "fournisseurs", "fournisseur_id nom categorie type_entreprise pays wilaya actif"),
    "grilles_tarifaires": _spec("Référentiels", "Grilles tarifaires contractuelles",
        "grilles_tarifaires", "grille_id client_id_ou_categorie sku_id prix_negocie remise_pct date_debut date_fin"),
    "contrats": _spec("Référentiels", "Contrats commerciaux",
        "contrats", "contrat_id client_id date_debut date_fin grille_tarifaire_id renouvellement_auto actif"),
    # Achats.
    "commandes_achats": _spec("Achats", "Commandes fournisseurs",
        "commandes_achats", "commande_achat_id date_commande fournisseur_id type_achat devise taux_change montant_total_devise montant_total_local statut", "date_commande"),
    "lignes_achats": _spec("Achats", "Lignes de commandes fournisseurs",
        "lignes_achats", "ligne_achat_id commande_achat_id mp_id unite_cond qte_cond qte_totale prix_unitaire total_devise"),
    "bons_reception": _spec("Achats", "Bons de réception",
        "bons_reception", "bon_reception_id commande_achat_id date_reception controle_conformite remarques", "date_reception"),
    "lignes_reception": _spec("Achats", "Lignes des bons de réception",
        "lignes_bons_reception", "ligne_br_id bon_reception_id mp_id quantite_recue lot_attribue_id"),
    "factures_fournisseurs": _spec("Achats", "Factures fournisseurs — consultation",
        "factures_fournisseurs", "facture_fournisseur_id commande_achat_id fournisseur_id reference_facture_fournisseur date montant_ht taux_tva montant_tva montant_ttc statut_paiement", "date",
        "copie de consultation, sans certification comptable ou fiscale"),
    "appels_offres": _spec("Achats", "Appels d'offres",
        "appels_offres", "ao_id besoin_description mp_id date_limite statut", "date_limite"),
    "reponses_appels_offres": _spec("Achats", "Réponses aux appels d'offres",
        "reponses_appels_offres", "reponse_ao_id ao_id fournisseur_id prix_propose delai_propose date_reponse", "date_reponse"),
    # Stocks : distingue PMP actuel et valeur historique.
    "stock_mp": _spec("Stocks", "Stock MP et PMP courant",
        "stock_actuel", "mp_id quantite_disponible cmp_actuel derniere_maj"),
    "stock_pf": _spec("Stocks", "Stock PF et PMP courant par SKU",
        "stock_actuel_pf", "sku_id quantite_disponible cout_revient derniere_maj"),
    "lots": _spec("Stocks", "Traçabilité des lots",
        "lots", "lot_id item_id type_item date_creation date_peremption quantite_initiale quantite_restante statut", "date_creation"),
    "mouvements_mp": _spec("Stocks", "Journal des mouvements MP",
        "mouvements", "mouvement_id date type_mouvement mp_id quantite reference lot_id prix_entree", "date",
        "état des mouvements non certifié SCF, coûts historiques tels qu'enregistrés"),
    "mouvements_pf": _spec("Stocks", "Journal des mouvements PF",
        "mouvements_pf", "mouvement_pf_id date type_mouvement sku_id quantite reference lot_id cout_unitaire", "date",
        "état des mouvements non certifié SCF, coûts historiques tels qu'enregistrés"),
    # Production : recettes à protéger par permission Production, à ne pas
    # confondre avec des formules industriellement approuvées.
    "ordres_fabrication": _spec("Production", "Ordres de fabrication",
        "ordres_fabrication", "of_id pf_id recette_id sku_id quantite_prevue quantite_produite date_planification date_debut date_fin statut cout_total notes", "date_planification"),
    "recettes": _spec("Production", "Recettes et versions",
        "recettes", "recette_id pf_id version rendement_unite date_effet actif", "date_effet",
        "recette de consultation, non homologuée industriellement"),
    "lignes_recette": _spec("Production", "Composants des recettes",
        "lignes_recette", "ligne_recette_id recette_id mp_id quantite_par_unite", None,
        "nomenclature de consultation, non homologuée industriellement"),
    "consommations_of": _spec("Production", "Consommations par OF",
        "consommations_of", "consommation_id of_id mp_id lot_id quantite_consommee"),
    "controle_qualite": _spec("Production", "Contrôles qualité",
        "controle_qualite", "qc_id of_id date conforme remarques controleur", "date",
        "contrôles qualité enregistrés, sans signature électronique"),
    # Ventes : AUCUNE émission de facture depuis le centre.
    "devis": _spec("Ventes", "Devis clients — registres",
        "devis", "devis_id client_id date validite statut commercial_id", "date"),
    "lignes_devis": _spec("Ventes", "Lignes de devis",
        "lignes_devis", "ligne_devis_id devis_id sku_id quantite prix_unitaire remise_pct"),
    "commandes_ventes": _spec("Ventes", "Commandes clients",
        "commandes_ventes", "commande_vente_id devis_id client_id date statut", "date"),
    "lignes_commande_ventes": _spec("Ventes", "Lignes commandes clients",
        "lignes_commande_ventes", "ligne_commande_vente_id commande_vente_id sku_id quantite prix_unitaire"),
    "bons_livraison": _spec("Ventes", "Bons de livraison — registres",
        "bons_livraison", "bl_id commande_vente_id date transporteur zone statut", "date"),
    "lignes_bons_livraison": _spec("Ventes", "Lignes des bons de livraison",
        "lignes_bons_livraison", "ligne_bl_id bl_id sku_id quantite_livree lot_id"),
    "factures": _spec("Ventes", "Factures clients — données enregistrées",
        "factures", "facture_id commande_vente_id client_id date montant_ht montant_tva montant_ttc montant_paye statut montant_timbre type_facture facture_origine_id", "date",
        "données historiques, NON VALABLES fiscalement et NON ÉMISES"),
    "lignes_facture": _spec("Ventes", "Lignes des factures enregistrées",
        "lignes_facture", "ligne_facture_id facture_id sku_id quantite prix_unitaire remise_ligne total_ligne_ht",
        None, "lignes de consultation, sans qualification fiscale SKU validée"),
    # Finance : consultation uniquement, non SCF signé.
    "comptes": _spec("Finance", "Plan des comptes (sans numéro bancaire)",
        "comptes", "compte_id nom_compte type_compte solde_initial statut"),
    "reglements": _spec("Finance", "Règlements",
        "reglements", "reglement_id date_reglement type_flux partenaire_id compte_id mode_paiement reference_trace montant_total montant_alloue statut", "date_reglement",
        "rapport de gestion, sans certification des écritures SCF"),
    "lettrage": _spec("Finance", "Lettrage",
        "lettrage", "lettrage_id date reglement_id document_id type_document montant_applique", "date",
        "rapport de gestion, sans certification des écritures SCF"),
    # CRM : contact personnel non inclus dans les exports génériques.
    "pipeline": _spec("CRM", "Pipeline commercial",
        "pipeline", "opportunite_id prospect_nom statut commercial_id valeur_estimee probabilite_pct date_creation date_derniere_action", "date_creation"),
    "interactions": _spec("CRM", "Interactions commerciales",
        "interactions", "interaction_id client_id date_creation type_action date_rappel statut_rappel", "date_creation"),
    # RH : sorties limitées aux champs ordinaires, jamais fiche de paie.
    "employes": _spec("RH", "Répertoire du personnel (restreint)",
        "employes", "employe_id nom poste service manager_id date_embauche actif", "date_embauche"),
    "conges": _spec("RH", "Suivi des congés",
        "demandes_conges", "demande_conge_id employe_id date_debut date_fin statut", "date_debut"),
    "projets": _spec("RH", "Projets",
        "projets", "projet_id nom client_id date_debut date_fin_prevue statut", "date_debut"),
    "taches": _spec("RH", "Tâches",
        "taches", "tache_id projet_id assigne_a statut date_echeance", "date_echeance"),
    "temps": _spec("RH", "Feuilles de temps",
        "feuilles_de_temps", "feuille_temps_id employe_id tache_id date heures", "date"),
}


def report_choices(family: str) -> dict[str, str]:
    return {key: item.title for key, item in REPORTS.items() if item.family == family}


def read_report(
    key: str, *, start_date: str | None = None,
    end_date: str | None = None, reader=None,
) -> tuple[ReportSpec, list[dict]]:
    """Validation explicite avant lecture RBAC/pagination strictes."""
    if key not in REPORTS:
        raise ValueError("Rapport inconnu")
    spec = REPORTS[key]
    if (start_date is None) != (end_date is None):
        raise ValueError("Période incomplète")
    if start_date is not None:
        if spec.date_column is None:
            raise ValueError("Ce registre ne porte pas de date filtrable")
        try:
            a, b = date.fromisoformat(start_date), date.fromisoformat(end_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("Dates invalides") from exc
        if a > b or b > date.today():
            raise ValueError("Période incohérente")
    if reader is None:
        from core.strict_reads import fetch_data_strict
        reader = fetch_data_strict
    # Les dates ERP historiques sont au format TEXT et peuvent contenir une
    # heure. Un filtre SQL <= YYYY-MM-DD exclurait les lignes de la dernière
    # journée. Lire tout le périmètre borné puis filtrer par jour civil ici :
    # pas de troncature silencieuse ni d'erreur au dernier jour.
    rows = reader(spec.table, page_size=500, max_rows=10000)
    if not isinstance(rows, list):
        raise ValueError("Lecture de registre incomplète")
    for row in rows:
        if not isinstance(row, dict) or any(col not in row for col in spec.columns):
            raise ValueError("Projection ERP incomplète")
    if start_date is not None:
        filtered = []
        for row in rows:
            raw = row.get(spec.date_column)
            if not isinstance(raw, str) or len(raw) < 10:
                raise ValueError("Date du registre manquante")
            try:
                current = date.fromisoformat(raw[:10])
            except ValueError as exc:
                raise ValueError("Date du registre incorrecte") from exc
            if a <= current <= b:
                filtered.append(row)
        rows = filtered
    # Colonnes explicitement listées, même si la table contient plus de données.
    return spec, [{col: row[col] for col in spec.columns} for row in rows]
