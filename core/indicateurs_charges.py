"""Agrégats de gestion des données enregistrées, sans règle de paie ou fiscale."""
import pandas as pd
from core.indicateurs_factures import numeric_values
from core.strict_reads import DataReadError


def payroll_net_for_period(frame, start, end):
    """Nets enregistrés sur les mois complets sélectionnés, tous statuts de paiement.

    Le statut de paiement ne prouve ni validation de paie ni coût employeur.
    Aucun prorata n'est déduit des seuls champs mois/année.
    """
    if frame.empty:
        return 0.0
    years, months = numeric_values(frame, 'annee'), numeric_values(frame, 'mois')
    if ((years % 1 != 0) | (months % 1 != 0) | ~years.between(1, 9999)
            | ~months.between(1, 12)).any():
        raise DataReadError('Période de paie invalide')
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if start > end:
        raise DataReadError('Période inversée')
    month_index = years * 12 + months
    selected = frame.loc[month_index.between(start.year * 12 + start.month,
                                             end.year * 12 + end.month)]
    if selected.empty:
        return 0.0
    if start.day != 1 or not end.is_month_end:
        raise DataReadError('Paie mensuelle : sélectionner des mois complets')
    values = numeric_values(selected, 'net_a_payer')
    if (values < 0).any():
        raise DataReadError('Net enregistré négatif')
    return values.sum()


def supplier_operating_payments(payments, suppliers):
    """Décaissements VALIDE dont la catégorie fournisseur contient OPEX.

    Convention existante de classement, pas des charges comptables calculées.
    Une référence manquante ne doit pas disparaître dans une jointure interne.
    """
    if payments.empty:
        return 0.0
    if not {'type_flux', 'statut'}.issubset(payments):
        raise DataReadError('Qualification de règlement absente')
    if not payments['type_flux'].isin(['ENCAISSEMENT', 'DECAISSEMENT']).all():
        raise DataReadError('Flux non reconnu')
    outgoing = payments.loc[payments['type_flux'] == 'DECAISSEMENT'].copy()
    if outgoing.empty:
        return 0.0
    if not outgoing['statut'].isin(['VALIDE', 'BROUILLON', 'ANNULE']).all():
        raise DataReadError('Statut de décaissement non reconnu')
    outgoing = outgoing.loc[outgoing['statut'] == 'VALIDE'].copy()
    if outgoing.empty:
        return 0.0
    if 'partenaire_id' not in outgoing or not {'fournisseur_id', 'categorie'}.issubset(suppliers):
        raise DataReadError('Référentiel fournisseur incomplet')
    if not outgoing['partenaire_id'].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
        raise DataReadError('Partenaire manquant')
    relevant = suppliers.loc[suppliers['fournisseur_id'].isin(outgoing['partenaire_id'])]
    if relevant['fournisseur_id'].duplicated().any():
        raise DataReadError('Fournisseur ambigu')
    merged = outgoing.merge(relevant[['fournisseur_id', 'categorie']],
                            left_on='partenaire_id', right_on='fournisseur_id', how='left')
    if not merged['categorie'].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
        raise DataReadError('Fournisseur absent ou catégorie non renseignée')
    amounts = numeric_values(merged, 'montant_total')
    if (amounts < 0).any():
        raise DataReadError('Décaissement négatif')
    return amounts[merged['categorie'].str.upper().str.contains('OPEX', regex=False)].sum()
