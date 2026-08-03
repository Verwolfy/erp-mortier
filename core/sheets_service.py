"""
Service centralisé d'accès à Google Sheets.
Conforme à l'architecture définie dans docs/schema_reference.md.
Inclut : gestion du cache, résilience (Tenacity), écritures groupées et verrouillage optimiste.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from config.settings import SHEETS_IDS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@st.cache_resource(show_spinner=False)
def get_google_client():
    """Initialise et met en cache le client gspread pour éviter les reconnexions inutiles."""
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
    client = get_google_client()
    sheet_id = SHEETS_IDS.get(module_name)

    if not sheet_id:
        raise ValueError(f"ID introuvable dans settings.py pour le module : {module_name}")

    sheet = client.open_by_key(sheet_id)
    return sheet.worksheet(sheet_name)

@st.cache_data(ttl=300, show_spinner=False)
def get_all_records(module_name: str, sheet_name: str) -> list:
    """Lit l'ensemble des enregistrements sous forme de dictionnaire avec mise en cache."""
    try:
        worksheet = get_worksheet(module_name, sheet_name)
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Erreur de lecture Google Sheets [{module_name}/{sheet_name}]: {e}")
        return []

def append_rows_batch(module_name: str, sheet_name: str, rows: list):
    """Ajoute plusieurs lignes en une seule requête API et vide le cache."""
    if not rows:
        return
    worksheet = get_worksheet(module_name, sheet_name)
    worksheet.append_rows(rows)
    st.cache_data.clear()

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

    st.cache_data.clear()

def update_multiple_cells_by_id(module_name: str, sheet_name: str, id_col: str, target_id: str, updates: dict):
    """
    Met à jour plusieurs colonnes d'une même ligne en une seule requête API groupée.
    updates est un dictionnaire: {'nom_colonne': nouvelle_valeur, ...}
    """
    ws = get_worksheet(module_name, sheet_name)
    headers = ws.row_values(1)

    try:
        id_col_idx = headers.index(id_col)
    except ValueError:
        return  # La colonne ID n'existe pas

    col_values = ws.col_values(id_col_idx + 1)
    try:
        row_idx = col_values.index(str(target_id)) + 1
    except ValueError:
        return  # L'ID ciblé n'a pas été trouvé

    cells_to_update = []
    for col_name, new_val in updates.items():
        if col_name in headers:
            col_idx = headers.index(col_name) + 1
            cells_to_update.append(gspread.Cell(row=row_idx, col=col_idx, value=new_val))

    if cells_to_update:
        ws.update_cells(cells_to_update)
        st.cache_data.clear()

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