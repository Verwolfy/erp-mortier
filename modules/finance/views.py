"""Interface Finance : vérification des droits et reprises transactionnelles.

Les lectures sont réservées aux utilisateurs autorisés. Les trois mutations
sont déléguées à modules.finance.service (RPC 006), avec un operation_id stable.
Ceci n'est PAS une comptabilité générale complète.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import logging
from uuid import uuid4

import pandas as pd
import streamlit as st

from config.roles import has_permission
from core.db_service import fetch_data_paginated, get_supabase_client
from core.listes_service import get_liste, liste_to_dict
from modules.finance.service import (
    creer_compte,
    enregistrer_lettrage,
    enregistrer_reglement,
    creer_accuse_encaissement,
)

_LOG = logging.getLogger(__name__)
_ACTIVE = frozenset({"oui", "true", "1", "actif", "active", "yes"})
_ACTIONS = {
    "account": ("creer_compte", "compte_id", frozenset({
        "nom_compte", "type_compte", "numero_compte", "solde_initial"})),
    "payment": ("enregistrer_reglement", "reglement_id", frozenset({
        "date_reglement", "type_flux", "partenaire_id", "compte_id",
        "mode_paiement", "reference_trace", "montant_total", "contrepartie_compte_id"})),
    "allocate": ("enregistrer_lettrage", "lettrage_id", frozenset({
        "reglement_id", "document_id", "type_document", "montant_applique"})),
    "receipt": ("creer_accuse_encaissement", "recu_id", frozenset({"reglement_id"})),
}
_TREASURY_TYPES = frozenset({"banque", "caisse"})
_COUNTER_TYPES = {
    "ENCAISSEMENT": frozenset({"tiers client", "client", "clients"}),
    "DECAISSEMENT": frozenset({"tiers fournisseur", "fournisseur", "fournisseurs"}),
}


def _mark_finance_activity() -> None:
    """Signale une interaction sans prolonger directement la session."""
    st.session_state["_erp_finance_interacted"] = True


def _finance_access() -> tuple[str, bool] | None:
    """Contrôle frais du compte actif, avant consultation avec service_role."""
    try:
        if st.session_state.get("authenticated") is not True:
            return None
        user = st.session_state.get("user")
        if not isinstance(user, dict):
            return None
        user_id = user.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        response = (get_supabase_client().table("users")
                    .select("user_id,role,actif")
                    .eq("user_id", user_id).limit(1).execute())
        accounts = response.data or []
        if len(accounts) != 1 or not isinstance(accounts[0], dict):
            return None
        account = accounts[0]
        active = account.get("actif")
        if account.get("user_id") != user_id or (
            active is not True and str(active).strip().casefold() not in _ACTIVE
        ):
            return None
        role = account.get("role")
        if not isinstance(role, str) or not role.strip():
            return None
        if has_permission(role, "Finance", "lecture") is not True:
            return None
        return user_id, has_permission(role, "Finance", "ecriture") is True
    except Exception as exc:
        _LOG.warning("Accès Finance non vérifiable (%s)", type(exc).__name__)
        return None


def _money(value, label: str, *, allow_zero: bool = False,
           allow_negative: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{label} invalide")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{label} invalide") from exc
    if (not number.is_finite() or abs(number) >= Decimal("1e15")
            or (number < 0 and not allow_negative)
            or (number == 0 and not allow_zero)
            or number != number.quantize(Decimal("0.01"))):
        raise ValueError(f"{label} invalide (centimes requis)")
    return number


def _required(value: str, label: str, limit: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f"{label} obligatoire (max {limit} caractères)")
    return value.strip()


def _op_key(kind: str, user_id: str) -> str:
    if kind not in _ACTIONS:
        raise ValueError("Action Finance inconnue")
    return f"finance_{kind}_{user_id}"


def _execute_operation(kind: str, user_id: str) -> None:
    key = _op_key(kind, user_id)
    record = st.session_state[key]
    if record["status"] == "confirmed":
        return
    methods = {"account": creer_compte, "payment": enregistrer_reglement,
               "allocate": enregistrer_lettrage, "receipt": creer_accuse_encaissement}
    try:
        document_id = methods[kind](**deepcopy(record["payload"]),
                                    operation_id=record["operation_id"])
        if not isinstance(document_id, str) or not document_id.strip():
            raise RuntimeError("Réponse documentaire absente")
    except (ValueError, PermissionError):
        # Le service Finance émet ces erreurs avant le RPC.
        del st.session_state[key]
        st.error("Opération refusée avant enregistrement. Corrigez la saisie ou les droits.")
        return
    except Exception as exc:
        # Timeout possible APRES validation SQL : garder ID ET payload inchangés.
        _LOG.warning("Opération Finance non confirmée (%s)", type(exc).__name__)
        record["status"] = "uncertain"
        st.error("Opération non confirmée : vérifier le résultat avant toute nouvelle saisie.")
        st.code(record["operation_id"])
        return
    record["status"] = "confirmed"
    record["document_id"] = document_id
    st.rerun()


def _start_operation(kind: str, user_id: str, payload: dict) -> None:
    key = _op_key(kind, user_id)
    if key in st.session_state:
        st.error("Une opération existe déjà ; utilisez sa reprise ou confirmez-la.")
        return
    st.session_state[key] = {
        "status": "uncertain", "operation_id": (
            f"RECUI-{uuid4().hex}" if kind == "receipt" else f"FIN-UI-{uuid4().hex}"
        ),
        "payload": deepcopy(payload),
    }
    _execute_operation(kind, user_id)


def _operation_panel(kind: str, user_id: str) -> bool:
    key = _op_key(kind, user_id)
    if key not in st.session_state:
        return False
    record = st.session_state[key]
    if (not isinstance(record, dict)
            or record.get("status") not in {"uncertain", "confirmed"}
            or not isinstance(record.get("operation_id"), str)
            or not record["operation_id"].startswith(
                "RECUI-" if kind == "receipt" else "FIN-UI-"
            )
            or not isinstance(record.get("payload"), dict)
            or not _ACTIONS[kind][2].issubset(record["payload"])
            or (record["status"] == "confirmed" and
                (not isinstance(record.get("document_id"), str)
                 or not record["document_id"]))):
        st.error("Dossier de reprise incorrect : faites vérifier l'opération par un administrateur.")
        return True
    st.code(record["operation_id"])
    if record["status"] == "uncertain":
        st.warning("Transaction non confirmée. Ne créez pas un deuxième règlement ou lettrage.")
        st.info("La reprise réutilise exactement la même référence, les mêmes montants et le même identifiant.")
        if st.button("Réessayer la même opération", key=f"finance_retry_{kind}_{user_id}", on_click=_mark_finance_activity):
            _execute_operation(kind, user_id)
    else:
        st.success(f"Opération confirmée : {record['document_id']}")
        if st.button("Préparer une nouvelle opération", key=f"finance_new_{kind}_{user_id}", on_click=_mark_finance_activity):
            del st.session_state[key]
            st.rerun()
    return True


def _active_account_rows(df: pd.DataFrame, allowed_types: frozenset[str]) -> dict[str, str]:
    if df.empty:
        return {}
    required = {"compte_id", "nom_compte", "type_compte", "statut"}
    if not required.issubset(df.columns):
        raise ValueError("Colonnes de comptes manquantes")
    result = {}
    for _, row in df.iterrows():
        if str(row["statut"]).strip().upper() != "OUI":
            continue
        if str(row["type_compte"]).strip().casefold() not in allowed_types:
            continue
        ident = row["compte_id"]
        if isinstance(ident, str) and ident.strip():
            result[ident] = f"{row['nom_compte']} ({ident})"
    return result


def _open_payments(df: pd.DataFrame, flow: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    required = {"reglement_id", "type_flux", "partenaire_id", "statut",
                "montant_total", "montant_alloue"}
    if not required.issubset(df.columns):
        raise ValueError("Historique des règlements incomplet")
    result = []
    for _, row in df.iterrows():
        if row["type_flux"] != flow or row["statut"] != "VALIDE":
            continue
        total = _money(row["montant_total"], "Montant règlement")
        allocated = _money(row["montant_alloue"], "Montant alloué", allow_zero=True)
        if allocated > total:
            raise ValueError("Règlement sur-alloué : contrôle nécessaire")
        if allocated < total:
            result.append({"reglement_id": row["reglement_id"],
                           "partenaire_id": row["partenaire_id"], "restant": total - allocated})
    return pd.DataFrame(result)


def _open_invoices(df: pd.DataFrame, document_type: str, partner_id: str,
                   allocations: pd.DataFrame | None = None) -> list[dict]:
    """Soldes affichés : le SQL 006 vérifie de nouveau sous verrou."""
    if df.empty:
        return []
    is_customer = document_type == "FactureClient"
    if not is_customer and document_type != "FactureFournisseur":
        raise ValueError("Document inconnu")
    id_col = "facture_id" if is_customer else "facture_fournisseur_id"
    partner_col = "client_id" if is_customer else "fournisseur_id"
    mandatory = {id_col, partner_col, "montant_ttc"}
    mandatory |= {"statut", "type_facture", "montant_paye"} if is_customer else {"statut_paiement"}
    if not mandatory.issubset(df.columns):
        raise ValueError("Historique des factures incomplet")
    paid_by_supplier_doc = {}
    if not is_customer and allocations is None:
        raise ValueError("Historique des lettrages fournisseurs obligatoire")
    if not is_customer and not allocations.empty:
        if not {"type_document", "document_id", "montant_applique"}.issubset(allocations.columns):
            raise ValueError("Historique de lettrage incomplet")
        for _, allocation in allocations.iterrows():
            if allocation["type_document"] != "FactureFournisseur":
                continue
            doc_id = allocation["document_id"]
            amount = _money(allocation["montant_applique"], "Lettrage")
            paid_by_supplier_doc[doc_id] = paid_by_supplier_doc.get(doc_id, Decimal(0)) + amount
    result = []
    for _, row in df.iterrows():
        if row[partner_col] != partner_id:
            continue
        if is_customer:
            if row["statut"] != "VALIDE" or row["type_facture"] != "FactureClient":
                continue
        elif str(row["statut_paiement"]).strip().upper() in {"ANNULE", "REJETE", "PAYEE"}:
            continue
        total = _money(row["montant_ttc"], "Montant TTC")
        paid = (_money(row["montant_paye"], "Montant payé", allow_zero=True)
                if is_customer else paid_by_supplier_doc.get(row[id_col], Decimal(0)))
        if paid > total:
            raise ValueError("Facture surpayée : contrôle nécessaire")
        if paid < total:
            result.append({"document_id": row[id_col], "reste": total - paid})
    return result


def _load_table(table: str) -> pd.DataFrame:
    # Lecture paginée afin de ne pas tronquer silencieusement les résultats.
    return pd.DataFrame(fetch_data_paginated(table, page_size=500, max_rows=10000))


def _accounts_tab(user_id: str, can_write: bool, accounts: pd.DataFrame) -> None:
    st.subheader("Comptes bancaires, caisses et contreparties")
    if not accounts.empty:
        st.dataframe(accounts, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun compte enregistré.")
    if not can_write:
        st.info("Mode lecture seule.")
        return
    if _operation_panel("account", user_id):
        return
    with st.form(f"finance_create_account_{user_id}"):
        nom = st.text_input("Nom du compte")
        type_c = st.selectbox("Type de compte", ["Banque", "Caisse", "Tiers client", "Tiers fournisseur"])
        numero = st.text_input("Numéro comptable ou bancaire (unique)")
        solde = st.number_input("Solde initial (DZD)", min_value=0.0, step=0.01, format="%.2f")
        if st.form_submit_button("Enregistrer le compte", type="primary", on_click=_mark_finance_activity):
            try:
                payload = {"nom_compte": _required(nom, "Nom du compte"),
                           "type_compte": type_c, "numero_compte": _required(numero, "Numéro de compte"),
                           "solde_initial": float(_money(solde, "Solde initial", allow_zero=True))}
                _start_operation("account", user_id, payload)
            except ValueError as exc:
                st.error(str(exc))
    st.caption("Les soldes initiaux ne génèrent pas encore d'écritures d'ouverture équilibrées.")


def _payment_tab(user_id: str, can_write: bool, accounts: pd.DataFrame) -> None:
    st.subheader("Règlements et écritures de contrepartie")
    if not can_write:
        st.info("Mode lecture seule.")
        return
    if _operation_panel("payment", user_id):
        return
    try:
        cash = _active_account_rows(accounts, _TREASURY_TYPES)
    except ValueError as exc:
        st.error(str(exc))
        return
    if not cash:
        st.warning("Créez d'abord un compte Banque ou Caisse actif.")
        return
    type_flux = st.radio("Sens du règlement", ["ENCAISSEMENT", "DECAISSEMENT"], horizontal=True, on_change=_mark_finance_activity)
    try:
        counterparties = _active_account_rows(accounts, _COUNTER_TYPES[type_flux])
        partner_table = "clients" if type_flux == "ENCAISSEMENT" else "fournisseurs"
        partner_field = "client_id" if type_flux == "ENCAISSEMENT" else "fournisseur_id"
        partners = _load_table(partner_table)
        if not partners.empty and not {partner_field, "nom"}.issubset(partners.columns):
            raise ValueError("Référentiel partenaires incomplet")
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        _LOG.warning("Référentiel Finance non disponible (%s)", type(exc).__name__)
        st.error("Référentiel non disponible. Aucune opération possible.")
        return
    if not counterparties:
        st.warning("Créez un compte actif de type Tiers client ou Tiers fournisseur avant le règlement.")
        return
    if partners.empty:
        st.warning("Aucun partenaire disponible pour ce type de règlement.")
        return
    partner_options = {r[partner_field]: f"{r['nom']} ({r[partner_field]})"
                       for _, r in partners.iterrows() if isinstance(r[partner_field], str)}
    if not partner_options:
        st.warning("Aucun identifiant partenaire utilisable.")
        return
    with st.form(f"finance_payment_{user_id}"):
        date_reg = st.date_input("Date de l'opération")
        partner_id = st.selectbox("Partenaire", list(partner_options), format_func=partner_options.get)
        cash_id = st.selectbox("Compte Banque / Caisse", list(cash), format_func=cash.get)
        counter_id = st.selectbox("Compte de contrepartie", list(counterparties), format_func=counterparties.get)
        raw_modes = liste_to_dict(get_liste("ModePaiement"))
        modes = list(raw_modes) if raw_modes else ["ESPECES", "CHEQUE", "VIREMENT"]
        mode_paiement = st.selectbox("Mode de paiement", modes)
        reference = st.text_input("Référence de règlement unique (obligatoire)")
        montant = st.number_input("Montant (DZD)", min_value=0.01, step=0.01, format="%.2f")
        if st.form_submit_button("Enregistrer le règlement", type="primary", on_click=_mark_finance_activity):
            try:
                if cash_id == counter_id:
                    raise ValueError("Les deux comptes doivent être distincts")
                payload = {"date_reglement": str(date_reg), "type_flux": type_flux,
                           "partenaire_id": _required(partner_id, "Partenaire"),
                           "compte_id": _required(cash_id, "Compte de trésorerie"),
                           "contrepartie_compte_id": _required(counter_id, "Compte contrepartie"),
                           "mode_paiement": _required(mode_paiement, "Mode de paiement"),
                           "reference_trace": _required(reference, "Référence de règlement"),
                           "montant_total": float(_money(montant, "Montant"))}
                _start_operation("payment", user_id, payload)
            except ValueError as exc:
                st.error(str(exc))


def _allocation_tab(user_id: str, can_write: bool, reglements: pd.DataFrame) -> None:
    st.subheader("Affectation des règlements aux factures")
    if not can_write:
        st.info("Mode lecture seule.")
        return
    if _operation_panel("allocate", user_id):
        return
    doc_type = st.radio("Document à régler", ["FactureClient", "FactureFournisseur"], horizontal=True, on_change=_mark_finance_activity)
    flow = "ENCAISSEMENT" if doc_type == "FactureClient" else "DECAISSEMENT"
    try:
        ouverts = _open_payments(reglements, flow)
    except ValueError as exc:
        st.error(str(exc))
        return
    if ouverts.empty:
        st.info("Aucun règlement ouvert pour ce type de document.")
        return
    options = {r["reglement_id"]: f"{r['reglement_id']} — solde : {r['restant']} DZD"
               for _, r in ouverts.iterrows()}
    reg_id = st.selectbox("Règlement à affecter", list(options), format_func=options.get, on_change=_mark_finance_activity)
    reg = ouverts[ouverts["reglement_id"] == reg_id].iloc[0]
    table = "factures" if doc_type == "FactureClient" else "factures_fournisseurs"
    try:
        invoices = _load_table(table)
        letters = _load_table("lettrage") if doc_type == "FactureFournisseur" else pd.DataFrame()
        eligible = _open_invoices(invoices, doc_type, reg["partenaire_id"], letters)
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        _LOG.warning("Factures Finance non disponibles (%s)", type(exc).__name__)
        st.error("Factures ou lettrages non disponibles : aucune affectation possible.")
        return
    if not eligible:
        st.info("Aucune facture payable correspondant à ce partenaire.")
        return
    invoice_options = {item["document_id"]: f"{item['document_id']} — dû : {item['reste']} DZD"
                       for item in eligible}
    with st.form(f"finance_allocation_{user_id}"):
        document_id = st.selectbox("Facture à solder", list(invoice_options), format_func=invoice_options.get)
        montant = st.number_input("Montant à affecter (DZD)", min_value=0.01,
                                  step=0.01, format="%.2f")
        if st.form_submit_button("Valider le lettrage", type="primary", on_click=_mark_finance_activity):
            try:
                due = next(item["reste"] for item in eligible if item["document_id"] == document_id)
                val = _money(montant, "Montant appliqué")
                if val > reg["restant"] or val > due:
                    raise ValueError("Montant supérieur au solde du règlement ou de la facture")
                _start_operation("allocate", user_id, {
                    "reglement_id": reg_id, "document_id": document_id,
                    "type_document": doc_type, "montant_applique": float(val),
                })
            except ValueError as exc:
                st.error(str(exc))


def _dashboard(reglements: pd.DataFrame) -> None:
    st.subheader("Synthèse des flux enregistrés")
    if reglements.empty:
        st.info("Aucun règlement enregistré.")
        return
    required = {"type_flux", "montant_total", "date_reglement"}
    if not required.issubset(reglements.columns):
        st.error("Historique des règlements incomplet")
        return
    receipts = Decimal(0)
    payments = Decimal(0)
    try:
        for _, row in reglements.iterrows():
            if row["type_flux"] == "ENCAISSEMENT":
                receipts += _money(row["montant_total"], "Encaissement")
            elif row["type_flux"] == "DECAISSEMENT":
                payments += _money(row["montant_total"], "Décaissement")
    except ValueError:
        st.error("Montants de trésorerie incohérents")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Encaissements", f"{receipts:,.2f} DZD")
    c2.metric("Décaissements", f"{payments:,.2f} DZD")
    c3.metric("Flux net", f"{receipts - payments:,.2f} DZD")
    st.dataframe(reglements.sort_values("date_reglement", ascending=False),
                 use_container_width=True, hide_index=True)
    st.caption("Le flux net n'est pas le solde bancaire et n'intègre pas les soldes initiaux.")


def _journal(entries: pd.DataFrame) -> None:
    st.subheader("Journal des écritures enregistrées (pas un grand livre complet)")
    if entries.empty:
        st.info("Aucune écriture enregistrée.")
        return
    if not {"debit", "credit", "date_ecriture"}.issubset(entries.columns):
        st.error("Colonnes du journal incomplètes")
        return
    try:
        debit = sum((_money(v, "Débit", allow_zero=True)
                     for v in entries["debit"]), Decimal(0))
        credit = sum((_money(v, "Crédit", allow_zero=True)
                      for v in entries["credit"]), Decimal(0))
    except ValueError:
        st.error("Écritures comptables non numériques ou incohérentes")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Total débit", f"{debit:,.2f} DZD")
    c2.metric("Total crédit", f"{credit:,.2f} DZD")
    c3.metric("Écart", f"{debit-credit:,.2f} DZD")
    if debit != credit:
        st.warning("Journal déséquilibré : vérifier les écritures historiques. Aucune correction automatique.")
    else:
        st.info("Écritures affichées équilibrées ; cela ne valide pas toute la comptabilité générale.")
    st.dataframe(entries.sort_values("date_ecriture", ascending=False),
                 use_container_width=True, hide_index=True)


def show_finance_page() -> None:
    access = _finance_access()
    if access is None:
        st.error("Accès Finance refusé ou session non vérifiable.")
        return
    user_id, can_write = access
    st.title("🏦 Comptabilité & Trésorerie")
    tabs = st.tabs(["📊 Tableau de bord", "🏦 Comptes", "💸 Règlements",
                    "🔗 Lettrage", "📖 Journal des écritures",
                    "📚 Balance SCF (lecture seule)", "🧾 Rapprochement quittances",
                    "🧾 Accusés internes", "📒 Pré-audit Finance → SCF",
                    "🔎 Préparation TVA / SCF", "🔗 Correspondances Finance / SCF"])
    try:
        accounts = _load_table("comptes")
        reglements = _load_table("reglements")
        if not isinstance(accounts, pd.DataFrame) or not isinstance(reglements, pd.DataFrame):
            raise ValueError("Résultat Finance invalide")
    except Exception as exc:
        _LOG.warning("Lecture Finance impossible (%s)", type(exc).__name__)
        st.error("Données Finance indisponibles ; aucune modification possible.")
        return
    with tabs[0]:
        _dashboard(reglements)
    with tabs[1]:
        _accounts_tab(user_id, can_write, accounts)
    with tabs[2]:
        _payment_tab(user_id, can_write, accounts)
    with tabs[3]:
        _allocation_tab(user_id, can_write, reglements)
    with tabs[4]:
        try:
            _journal(_load_table("ecritures_comptables"))
        except Exception as exc:
            _LOG.warning("Journal Finance indisponible (%s)", type(exc).__name__)
            st.error("Journal non disponible.")

    with tabs[5]:
        _scf_balance_tab(user_id)
    with tabs[6]:
        _quittances_rapprochement_tab(user_id)
    with tabs[7]:
        _accuses_internes_tab(user_id, can_write, reglements)
    with tabs[8]:
        _audit_finance_vers_scf_tab(user_id, accounts, reglements)
    with tabs[9]:
        _preflight_reglementaire_tab(user_id)
    with tabs[10]:
        _correspondances_finance_scf_tab(user_id, accounts)


def _lecture_complete_quittances(table: str, colonnes: str) -> list[dict]:
    """Lecture intégrale bornée, échec si pagination tronquée ou erreur API."""
    if table not in {"reglements", "lettrage", "factures"}:
        raise ValueError("Table non autorisée pour l'audit des quittances")
    response = (
        get_supabase_client().table(table)
        .select(colonnes, count="exact")
        .range(0, 999)
        .execute()
    )
    rows = response.data
    count = response.count
    if (not isinstance(rows, list) or isinstance(count, bool)
            or not isinstance(count, int) or count != len(rows)
            or len(rows) > 1000 or not all(isinstance(r, dict) for r in rows)):
        raise ValueError("Historique de règlement tronqué ou incorrect")
    return rows


def _quittances_rapprochement_tab(user_id: str) -> None:
    """Contrôle en lecture seule ; aucun reçu fiscal n'est créé ni exporté."""
    st.subheader("Rapprochement des règlements et factures clients")
    st.caption(
        "État interne uniquement : les paiements partiels et les affectations "
        "multiples sont vérifiés sans émission d'une quittance fiscale."
    )
    st.warning(
        "Le timbre ne peut être liquidé automatiquement : règlement effectif, "
        "exceptions et règle juridique datée doivent être validés. "
        "Le timbre historique des factures n'est pas recalculé."
    )
    if not st.button("Vérifier les encaissements", key="finance_quittances_verifier"):
        st.info("Contrôle à la demande, sans modification de la comptabilité.")
        return
    _mark_finance_activity()
    access = _finance_access()  # Permission et compte actif relus au moment du clic.
    if access is None or access[0] != user_id:
        st.error("Autorisation Finance non vérifiable, aucune donnée affichée.")
        return
    from core.quittances_rapprochement import (
        RapprochementIndisponible, rapprocher_reglements_clients,
    )
    try:
        paiements = _lecture_complete_quittances(
            "reglements",
            "reglement_id,date_reglement,type_flux,partenaire_id,mode_paiement,"
            "montant_total,montant_alloue,statut",
        )
        lettrages = _lecture_complete_quittances(
            "lettrage",
            "lettrage_id,reglement_id,document_id,type_document,montant_applique",
        )
        factures = _lecture_complete_quittances(
            "factures",
            "facture_id,client_id,statut,type_facture,montant_ttc,montant_paye",
        )
        resultat = rapprocher_reglements_clients(paiements, lettrages, factures)
    except (RapprochementIndisponible, ValueError) as exc:
        _LOG.warning("Rapprochement quittances refusé (%s)", type(exc).__name__)
        st.error("Rapprochement impossible : historiques incomplets ou incohérents.")
        return
    except Exception as exc:
        _LOG.warning("Lecture quittances inaccessible (%s)", type(exc).__name__)
        st.error("Lecture Finance indisponible ; aucun total partiel présenté.")
        return
    st.metric("Encaissements rapprochés", resultat["nombre_reglements"])
    st.metric("Total des encaissements (DZD)", resultat["montant_encaisse_total"])
    if not resultat["reglements"]:
        st.info("Aucun encaissement client validé.")
        return
    rows = [
        {**{k: v for k, v in p.items() if k not in ("factures", "statut")},
         "factures_lettrées": ", ".join(
             f"{f['facture_id']} ({f['montant_applique']} DZD)"
             for f in p["factures"]
         )}
        for p in resultat["reglements"]
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Ce tableau n'est pas une quittance légale et ne constate aucun droit de timbre.")


def _scf_balance_tab(user_id: str) -> None:
    """Vue non destructive : autorisation spécifique revérifiée côté serveur."""
    st.subheader("Balance comptable SCF — consultation")
    st.caption(
        "Uniquement les pièces validées des nouvelles tables SCF. "
        "Cette balance ne remplace pas les états comptables réglementaires."
    )
    # Ne jamais déduire le droit SCF de la seule permission Finance.
    try:
        current = (
            get_supabase_client().table("users")
            .select("user_id,role,actif")
            .eq("user_id", user_id).limit(2).execute()
        )
        rows = current.data
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise PermissionError("Compte SCF non vérifiable")
        account = rows[0]
        active = account.get("actif")
        if (account.get("user_id") != user_id
                or (active is not True
                    and str(active).strip().casefold() not in _ACTIVE)
                or not isinstance(account.get("role"), str)
                or has_permission(account["role"], "SCF", "lecture") is not True):
            raise PermissionError("Droit SCF manquant")
    except Exception as exc:
        _LOG.warning("Habilitation SCF non vérifiable (%s)", type(exc).__name__)
        st.info("Accès à la balance SCF non disponible pour ce profil.")
        return

    if not st.button("Charger la balance SCF", key="finance_scf_load"):
        st.info("Lecture à la demande ; aucune pièce n'est modifiée.")
        return
    _mark_finance_activity()
    from core.scf_service import LectureSCFIndisponible, lire_balance_scf
    try:
        resultat = lire_balance_scf()
    except LectureSCFIndisponible as exc:
        _LOG.warning("Lecture SCF refusée (%s)", type(exc).__name__)
        st.error("Balance SCF indisponible ou incomplète ; aucune somme partielle affichée.")
        return
    st.metric("Pièces validées", resultat["pieces"])
    st.metric("Lignes contrôlées", resultat["lignes"])
    if resultat["balance"]:
        table = pd.DataFrame.from_dict(resultat["balance"], orient="index")
        table.index.name = "Compte SCF"
        st.dataframe(table, use_container_width=True)
    else:
        st.info("Aucune écriture SCF validée.")


def _accuses_internes_tab(user_id: str, can_write: bool,
                          paiements: pd.DataFrame) -> None:
    """Accusé de caisse interne, jamais une quittance fiscale officielle."""
    st.subheader("Accusés internes d'encaissement")
    st.warning(
        "Document interne NON fiscal. Aucun timbre, numéro de quittance légale "
        "ou paiement nouveau n'est créé."
    )
    try:
        recus = _load_table("erp_recus_internes")
        if not recus.empty:
            colonnes = ["recu_id", "reglement_id", "date_reglement",
                        "montant_encaisse", "statut"]
            if not set(colonnes).issubset(recus.columns):
                raise ValueError("Historique des accusés incomplet")
            st.dataframe(recus[colonnes], use_container_width=True, hide_index=True)
    except Exception as exc:
        _LOG.warning("Accusés internes indisponibles (%s)", type(exc).__name__)
        st.error("Journal des accusés inaccessible : émission désactivée.")
        return
    if not can_write:
        st.info("Lecture seule : émission réservée à Finance / écriture.")
        return
    if _operation_panel("receipt", user_id):
        return
    if paiements.empty:
        st.info("Aucun encaissement à traiter.")
        return
    colonnes = {"reglement_id", "type_flux", "statut", "montant_total"}
    if not colonnes.issubset(paiements.columns):
        st.error("Registre des règlements incomplet.")
        return
    existants = set(recus["reglement_id"]) if not recus.empty else set()
    choix = {
        row["reglement_id"]: f"{row['reglement_id']} : {row['montant_total']} DZD"
        for _, row in paiements.iterrows()
        if row["type_flux"] == "ENCAISSEMENT"
        and row["statut"] == "VALIDE"
        and isinstance(row["reglement_id"], str)
        and row["reglement_id"] not in existants
    }
    if not choix:
        st.info("Aucun règlement validé sans accusé existant.")
        return
    reglement_id = st.selectbox(
        "Règlement encaissé", list(choix), format_func=choix.get,
        key="finance_accuse_reglement", on_change=_mark_finance_activity,
    )
    if st.button(
        "Émettre un accusé interne", key="finance_accuse_emettre",
        on_click=_mark_finance_activity,
    ):
        _start_operation("receipt", user_id, {"reglement_id": reglement_id})


def _audit_finance_vers_scf_tab(
    user_id: str, comptes: pd.DataFrame, reglements: pd.DataFrame,
) -> None:
    """Diagnostic RPC Finance, pas une écriture comptable SCF."""
    st.subheader("Pré-audit des règlements pour la comptabilité SCF")
    st.caption(
        "Vérifie les écritures en partie double générées par les opérations "
        "Finance REGF-. Les numéros de comptes affichés ne sont pas validés "
        "comme plan SCF et aucune écriture n'est transférée."
    )
    if not st.button("Contrôler les écritures de trésorerie",
                     key="finance_scf_pre_audit"):
        return
    _mark_finance_activity()
    access = _finance_access()
    if access is None or access[0] != user_id:
        st.error("Habilitation Finance non vérifiable : audit interdit.")
        return
    from core.rapprochement_finance_scf import (
        AuditTresorerieIndisponible, auditer_reglements_vers_scf,
    )
    try:
        ecritures = _load_table("ecritures_comptables")
        result = auditer_reglements_vers_scf(
            reglements.to_dict(orient="records"),
            ecritures.to_dict(orient="records"),
            comptes.to_dict(orient="records"),
        )
    except (AuditTresorerieIndisponible, ValueError) as exc:
        _LOG.warning("Pré-audit Finance SCF incohérent (%s)", type(exc).__name__)
        st.error("Journal Finance incomplet ou incohérent : aucun résultat partiel.")
        return
    except Exception as exc:
        _LOG.warning("Pré-audit Finance SCF impossible (%s)", type(exc).__name__)
        st.error("Journal indisponible : aucun résultat partiel.")
        return
    st.metric("Règlements RPC contrôlés", result["reglements_rpc_valides"])
    st.metric("Encaissements vérifiés (DZD)", result["montant_encaisse"])
    st.metric("Décaissements vérifiés (DZD)", result["montant_decaisse"])
    if result["reglements_historiques_hors_controle"]:
        st.warning(
            f"{result['reglements_historiques_hors_controle']} règlement(s) "
            "historiques exclus de cet audit faute de provenance RPC vérifiée."
        )
    if result["ecritures"]:
        summary = [{
            "reglement_id": r["reglement_id"],
            "date": r["date_ecriture"],
            "sens": r["sens"],
            "montant": r["montant"],
            "débit": r["total_debit"],
            "crédit": r["total_credit"],
            "statut": r["statut"],
            "comptes_finance": ", ".join(
                f"{l['compte_finance']} / {l['numero_compte_saisi']}"
                for l in r["lignes"]
            ),
        } for r in result["ecritures"]]
        st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune écriture issue de la RPC Finance à rapprocher.")
    st.caption("Ce contrôle n'est pas une balance SCF, ni une comptabilisation officielle.")


def _preflight_reglementaire_tab(user_id: str) -> None:
    """Diagnostic non fiscal uniquement, aucune règle appliquée ni écriture."""
    st.subheader("Préparation des référentiels fiscaux et SCF")
    st.caption("Contrôle de disponibilité, sans calcul de facture ni écriture comptable.")
    if not st.button("Contrôler les référentiels", key="finance_preflight_reglementaire"):
        return
    _mark_finance_activity()
    access = _finance_access()
    if access is None or access[0] != user_id:
        st.error("Droit Finance non vérifiable : consultation refusée.")
        return
    from core.preflight_reglementaire import PreflightIndisponible, lire_preflight
    try:
        result = lire_preflight(db_client=get_supabase_client())
    except PreflightIndisponible as exc:
        _LOG.warning("Préflight non disponible (%s)", type(exc).__name__)
        st.error("Référentiels indisponibles ou incohérents : aucun résultat partiel.")
        return
    except Exception as exc:
        _LOG.warning("Préflight interrompu (%s)", type(exc).__name__)
        st.error("Diagnostic indisponible, aucun résultat partiel.")
        return
    st.metric("Taux TVA de référence", result["taux_reference_disponibles"])
    st.metric("Comptes SCF de référence", result["comptes_scf_reference"])
    st.metric("Comptes SCF mouvementables", result["comptes_scf_mouvementables"])
    st.metric("Journaux SCF", result["journaux_scf"])
    st.metric("Exercices SCF ouverts", result["exercices_scf_ouverts"])
    st.warning(
        "Classification TVA des produits et régime fiscal de l'entreprise "
        "non vérifiés. Facturation réglementaire et comptabilisation SCF "
        "non autorisées par ce diagnostic."
    )


def _correspondances_finance_scf_tab(user_id: str, comptes: pd.DataFrame) -> None:
    """Vérifie les seuls numéros SCF exacts : aucun rapprochement officiel."""
    st.subheader("Correspondances comptes Finance → SCF")
    st.caption(
        "Comparaison exacte, sans inférence ni écriture automatique. "
        "Un numéro identique n'homologue pas une imputation comptable."
    )
    if not st.button("Comparer les comptes", key="finance_scf_correspondances"):
        return
    _mark_finance_activity()
    access = _finance_access()
    if access is None or access[0] != user_id:
        st.error("Autorisation Finance absente ou non vérifiable.")
        return
    from core.correspondances_finance_scf import (
        CorrespondanceSCFIndisponible, lire_correspondances_finance_scf,
    )
    try:
        if not isinstance(comptes, pd.DataFrame):
            raise CorrespondanceSCFIndisponible("Source Finance invalide")
        resultat = lire_correspondances_finance_scf(
            comptes.to_dict(orient="records"), db_client=get_supabase_client()
        )
    except CorrespondanceSCFIndisponible as exc:
        _LOG.warning("Correspondances Finance SCF refusées (%s)", type(exc).__name__)
        st.error("Comptes incomplets ou incohérents : aucune correspondance affichée.")
        return
    except Exception as exc:
        _LOG.warning("Lecture des correspondances impossible (%s)", type(exc).__name__)
        st.error("Comparaison indisponible, aucun résultat partiel.")
        return
    st.metric("Comptes Finance", resultat["nombre_comptes_finance"])
    st.metric("Références SCF", resultat["nombre_comptes_scf"])
    st.metric("Références SCF inactives", resultat["repartition"]["REFERENCE_INACTIVE"])
    st.metric("Comptes Finance sans référence", (
        resultat["repartition"]["SANS_NUMERO"] +
        resultat["repartition"]["NON_REFERENCE"]
    ))
    if resultat["lignes"]:
        st.dataframe(pd.DataFrame(resultat["lignes"]), use_container_width=True,
                     hide_index=True)
    else:
        st.info("Aucun compte Finance à comparer.")
    st.warning(
        "Aucune correspondance n'est homologuée. La validation des comptes "
        "SCF, des journaux et des exercices reste nécessaire avant de "
        "comptabiliser automatiquement."
    )
