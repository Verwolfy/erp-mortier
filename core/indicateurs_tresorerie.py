"""Trésorerie indicative : soldes initiaux + règlements validés, sans écriture."""
import pandas as pd
from core.indicateurs_factures import numeric_values, dates
from core.strict_reads import DataReadError


def validated_payments(frame):
    columns = ['compte_id', 'type_flux', 'montant_total', 'montant_alloue', 'date_obj']
    if frame.empty:
        return pd.DataFrame(columns=columns)
    if 'statut' not in frame or not frame['statut'].isin(['VALIDE','BROUILLON','ANNULE']).all():
        raise DataReadError('Statut de règlement non reconnu')
    result = frame.loc[frame['statut'] == 'VALIDE'].copy()
    if result.empty:
        return pd.DataFrame(columns=columns)
    if not {'compte_id','type_flux'}.issubset(result):
        raise DataReadError('Compte ou flux absent')
    if not result['type_flux'].isin(['ENCAISSEMENT','DECAISSEMENT']).all():
        raise DataReadError('Flux inconnu')
    for col in ['montant_total','montant_alloue']:
        result[col] = numeric_values(result,col)
    if ((result['montant_total'] <= 0) | (result['montant_alloue'] < 0)
            | (result['montant_alloue'] > result['montant_total'])).any():
        raise DataReadError('Montant ou allocation incohérent')
    result['date_obj'] = dates(result,'date_reglement')
    return result


def cash_balances(accounts, payments, today):
    columns = ['compte_id','nom_compte','type_compte','solde']
    if accounts.empty:
        if not payments.empty:
            raise DataReadError('Règlement sans compte disponible')
        return pd.DataFrame(columns=columns)
    if not {'compte_id','nom_compte','type_compte','solde_initial'}.issubset(accounts):
        raise DataReadError('Référentiel des comptes incomplet')
    if not accounts['type_compte'].map(lambda v:isinstance(v,str) and bool(v.strip())).all():
        raise DataReadError('Type de compte absent')
    cash = accounts.loc[accounts['type_compte'].str.strip().str.lower().isin(['banque','caisse'])].copy()
    if cash['compte_id'].duplicated().any() or not cash['compte_id'].map(
            lambda v:isinstance(v,str) and bool(v.strip())).all():
        raise DataReadError('Identifiant de compte ambigu')
    cash['solde'] = numeric_values(cash,'solde_initial')
    if not payments.empty:
        if not payments['compte_id'].isin(cash['compte_id']).all():
            raise DataReadError('Règlement sans compte de trésorerie reconnu')
        current = payments.loc[payments['date_obj'] <= pd.Timestamp(today).tz_localize(None).normalize()].copy()
        current['flux_signe'] = current['montant_total'].where(current['type_flux']=='ENCAISSEMENT',-current['montant_total'])
        movements = current.groupby('compte_id')['flux_signe'].sum()
        cash['solde'] += cash['compte_id'].map(movements).fillna(0)
    return cash[columns]
