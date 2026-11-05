"""Indicateurs de stock contrôlés, sans écriture ni valorisation inventée."""
import pandas as pd
from core.indicateurs_factures import numeric_values, dates
from core.strict_reads import DataReadError


def nonnegative(frame, column):
    values = numeric_values(frame, column)
    if (values < 0).any():
        raise DataReadError('Quantité, coût ou seuil négatif')
    return values


def stock_value(frame, cost_column):
    if frame.empty:
        return 0.0
    quantity = nonnegative(frame, 'quantite_disponible')
    held = frame.loc[quantity > 0]
    if held.empty:
        return 0.0
    costs = nonnegative(held, cost_column)
    return (quantity.loc[held.index] * costs).sum()


def threshold_status(stock, references):
    """Seuils configurés uniquement : l'absence de seuil n'est pas un seuil nul.

    Renvoie (alertes fiables, références sans seuil). Refuse les identifiants
    ambigus, l'absence de référence et les seuils renseignés mais invalides.
    """
    if stock.empty:
        return 0, 0
    if 'mp_id' not in stock or not {'mp_id', 'stock_mini'}.issubset(references):
        raise DataReadError('Référentiel de seuils incomplet')
    if not stock['mp_id'].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
        raise DataReadError('Référence stock invalide')
    relevant = references.loc[references['mp_id'].isin(stock['mp_id'])]
    if relevant['mp_id'].duplicated().any() or stock['mp_id'].duplicated().any():
        raise DataReadError('Référence stock ambiguë')
    merged = stock.merge(relevant[['mp_id', 'stock_mini']], on='mp_id',
                         how='left', indicator=True)
    if (merged['_merge'] != 'both').any():
        raise DataReadError('Matière première sans référentiel')
    quantities = nonnegative(merged, 'quantite_disponible')
    missing = merged['stock_mini'].isna() | merged['stock_mini'].astype(str).str.strip().eq('')
    known = merged.loc[~missing]
    if known.empty:
        return 0, int(missing.sum())
    limits = nonnegative(known, 'stock_mini')
    alerts = int((quantities.loc[known.index] < limits).sum())
    return alerts, int(missing.sum())


def below_threshold(stock, references):
    """Nombre d'alertes évaluables ; pour les seuils absents, voir threshold_status."""
    return threshold_status(stock, references)[0]


def expiry_alerts(lots, today, days):
    if lots.empty:
        return pd.DataFrame(), 0
    quantity = nonnegative(lots, 'quantite_restante')
    held = lots.loc[quantity > 0].copy()
    if held.empty:
        return held, 0
    if 'date_peremption' not in held:
        raise DataReadError('Champ de péremption absent')
    unknown = held['date_peremption'].isna() | held['date_peremption'].astype(str).str.strip().eq('')
    dated = held.loc[~unknown].copy()
    if dated.empty:
        return dated, int(unknown.sum())
    due = dates(dated, 'date_peremption')
    limit = pd.Timestamp(today).tz_localize(None).normalize() + pd.Timedelta(days=days)
    # Inclut les lots déjà périmés et ceux dont l'échéance est aujourd'hui.
    return dated.loc[due <= limit].copy(), int(unknown.sum())
