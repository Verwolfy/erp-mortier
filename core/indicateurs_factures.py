"""Périmètre documentaire des indicateurs, conforme aux RPC Ventes/Finance.

Facturation brute = factures clients VALIDE, hors avoirs (suivis séparément).
Aucune règle fiscale ni écriture comptable n'est créée par ce module.
"""
import math
import pandas as pd
from core.strict_reads import DataReadError

_COLUMNS = ['facture_id', 'type_facture', 'statut', 'date', 'date_echeance',
            'client_id', 'montant_ht', 'montant_ttc', 'montant_paye', 'montant_timbre']


def numeric_values(frame, column):
    if column not in frame:
        raise DataReadError('Colonne de montant absente')
    raw = frame[column]
    values = pd.to_numeric(raw, errors='coerce')
    if raw.map(lambda v: isinstance(v, bool)).any() or not values.map(
            lambda v: pd.notna(v) and math.isfinite(v)).all():
        raise DataReadError('Montant manquant ou invalide')
    return values


def dates(frame, column):
    if column not in frame:
        raise DataReadError('Date absente')
    try:
        values = pd.to_datetime(frame[column], errors='coerce', format='ISO8601')
        values = values.dt.tz_localize(None).dt.normalize()
    except (ValueError, TypeError, AttributeError):
        raise DataReadError('Date non exploitable') from None
    if values.isna().any():
        raise DataReadError('Date manquante ou invalide')
    return values


def validated_documents(frame):
    if frame.empty:
        return pd.DataFrame(columns=_COLUMNS)
    if not {'statut', 'facture_id'}.issubset(frame.columns):
        raise DataReadError('Statut ou identifiant documentaire absent')
    if not frame['statut'].isin(['BROUILLON', 'VALIDE', 'ANNULE']).all():
        raise DataReadError('Statut documentaire non reconnu')
    result = frame.loc[frame['statut'] == 'VALIDE'].copy()
    if result.empty:
        return pd.DataFrame(columns=_COLUMNS)
    if not {'type_facture', 'client_id'}.issubset(result.columns):
        raise DataReadError('Type documentaire ou client absent')
    if not result['type_facture'].isin(['FactureClient', 'FactureAvoir']).all():
        raise DataReadError('Type documentaire non reconnu')
    for col in ['facture_id', 'client_id']:
        if not result[col].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise DataReadError('Identifiant documentaire invalide')
    if result['facture_id'].duplicated().any():
        raise DataReadError('Facture dupliquée')
    for col in ['montant_ht', 'montant_ttc', 'montant_paye', 'montant_timbre']:
        result[col] = numeric_values(result, col)
    bills = result['type_facture'] == 'FactureClient'
    if ((result.loc[bills, ['montant_ht', 'montant_ttc', 'montant_paye']] < 0).any().any()
            or (result.loc[bills, 'montant_paye'] > result.loc[bills, 'montant_ttc']).any()
            or (result.loc[~bills, ['montant_ht', 'montant_ttc']] > 0).any().any()):
        raise DataReadError('Montants documentaires incohérents')
    result['date_obj'] = dates(result, 'date')
    return result


def in_period(documents, start, end):
    if documents.empty:
        return documents.copy()
    start, end = pd.Timestamp(start).tz_localize(None).normalize(), pd.Timestamp(end).tz_localize(None).normalize()
    if start > end:
        raise DataReadError('Période inversée')
    return documents.loc[documents['date_obj'].between(start, end)].copy()


def client_invoices(documents):
    return documents.loc[documents['type_facture'] == 'FactureClient'].copy()


def open_receivables(documents, today):
    result = client_invoices(documents)
    result['reste_a_payer'] = result['montant_ttc'] - result['montant_paye']
    result = result.loc[result['reste_a_payer'] > 0].copy()
    if result.empty:
        result['retard_jours'] = pd.Series(dtype='int64')
        return result
    # Le lettrage conserve statut=VALIDE même pour un paiement partiel ou total.
    due = dates(result, 'date_echeance')
    result['retard_jours'] = (pd.Timestamp(today).tz_localize(None).normalize() - due).dt.days
    return result


def ageing_balance(receivables):
    days, balance = receivables['retard_jours'], receivables['reste_a_payer']
    return {'Non échu': balance[days <= 0].sum(),
            '1 à 30 jours': balance[(days > 0) & (days <= 30)].sum(),
            '31 à 60 jours': balance[(days > 30) & (days <= 60)].sum(),
            '+ de 60 jrs': balance[days > 60].sum()}
