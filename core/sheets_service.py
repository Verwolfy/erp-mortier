"""
Service centralisé d'accès à Google Sheets.
Conforme à l'architecture définie dans docs/schema_reference.md.
Inclut : gestion du cache, résilience (Tenacity) sur la lecture ET l'écriture, et verrouillage optimiste.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from config.settings import SHEETS_IDS
from core.environment_guard import (
    policy_from_streamlit, require_supabase_target, require_sheet_id,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def get_google_client():
    """Vérifie la politique avant chaque connexion Google (010-A-01)."""
    require_supabase_target(
        policy_from_streamlit(st.secrets), st.secrets["supabase"]["url"]
    )
    credentials_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(
        credentials_dict,
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )
    return gspread.authorize(credentials)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def get_worksheet(module_name: str, sheet_name: str):
    """
    Récupère une feuille spécifique d'un module donné.
    Le module_name doit correspondre aux clés de SHEETS_IDS (ex: 'referentiels').
    """
    sheet_id = require_sheet_id(
        policy_from_streamlit(st.secrets), st.secrets["supabase"]["url"],
        module_name, SHEETS_IDS
    )
    client = get_google_client()

    sheet = client.open_by_key(sheet_id)
    return sheet.worksheet(sheet_name)

def get_all_records(module_name: str, sheet_name: str) -> list:
    """Lit l'ensemble des enregistrements sous forme de dictionnaire avec mise en cache."""
    try:
        worksheet = get_worksheet(module_name, sheet_name)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Erreur de lecture Google Sheets [{module_name}/{sheet_name}]: {e}")
        return []

# Pas de retry automatique sur les ajouts de lignes.
def append_rows_batch(module_name: str, sheet_name: str, rows: list,
                      column_names: list[str] | None = None):
    """Ajoute les lignes selon les en-tetes reels Google Sheets."""
    if not rows:
        return

    worksheet = get_worksheet(module_name, sheet_name)

    if column_names is not None:
        headers = worksheet.row_values(1)

        if (
            not headers
            or len(headers) != len(set(headers))
            or len(column_names) != len(set(column_names))
            or len(headers) != len(column_names)
            or set(headers) != set(column_names)
        ):
            raise ValueError(
                f"En-tetes incompatibles : {module_name}/{sheet_name}"
            )

        if any(len(row) != len(column_names) for row in rows):
            raise ValueError("Nombre de valeurs incorrect")

        indexes = [column_names.index(header) for header in headers]
        rows = [[row[index] for index in indexes] for row in rows]

    worksheet.append_rows(rows)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def update_cell_by_id(module_name: str, sheet_name: str, id_col: str, target_id: str, col_name: str, new_value):
    """
    Mise à jour ciblée d'une seule cellule via recherche dynamique de colonne.
    """
    ws = get_worksheet(module_name, sheet_name)
    all_values = ws.get_all_values()
    if not all_values:
        return

    headers = all_values[0]
    if id_col not in headers or col_name not in headers:
        raise KeyError(f"En-tête manquant: {id_col} ou {col_name}")

    id_idx = headers.index(id_col)
    col_idx = headers.index(col_name) + 1

    for row_idx, row in enumerate(all_values[1:], start=2):
        if len(row) > id_idx and str(row[id_idx]) == str(target_id):
            ws.update_cell(row_idx, col_idx, str(new_value))
            break

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def update_multiple_cells_by_id(module_name: str, sheet_name: str, id_col: str, target_id: str, updates: dict):
    """
    Met à jour plusieurs colonnes d'une même ligne en une seule requête API groupée.
    updates est un dictionnaire: {'nom_colonne': nouvelle_valeur, ...}
    """
    if not updates:
        return

    ws = get_worksheet(module_name, sheet_name)
    headers = ws.row_values(1)

    if not headers or len(headers) != len(set(headers)):
        raise ValueError("En-tetes Google Sheets invalides")

    missing = [key for key in [id_col, *updates] if key not in headers]
    if missing:
        raise KeyError(f"Colonnes manquantes : {missing}")

    values = ws.col_values(headers.index(id_col) + 1)
    matches = [
        i for i, value in enumerate(values, start=1)
        if i > 1 and str(value) == str(target_id)
    ]

    if len(matches) != 1:
        raise ValueError("Identifiant absent ou duplique dans Google Sheets")

    cells = [
        gspread.Cell(
            row=matches[0],
            col=headers.index(column) + 1,
            value=value
        )
        for column, value in updates.items()
    ]

    ws.update_cells(cells)

def check_optimistic_lock(module_name: str, sheet_name: str, id_col: str, target_id: str, lock_col: str, expected_lock_value: str) -> bool:
    """
    Bypass le cache pour vérifier si la cellule contient toujours la valeur attendue en direct.
    Essentiel pour éviter les doublons de numérotation.
    """
    ws = get_worksheet(module_name, sheet_name)
    records = ws.get_all_records()
    for row in records:
        if str(row.get(id_col)) == str(target_id):
            current_val = str(row.get(lock_col, ""))
            if current_val != str(expected_lock_value):
                return False  # Conflit : la valeur a été modifiée par un autre processus
            return True
    return True