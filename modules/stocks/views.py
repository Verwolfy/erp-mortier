"""Écran Stocks : contrôle de lecture et entrées manuelles anti-doublon.

Supabase reste la source de vérité. En cas d'erreur réseau, on réutilise le
même operation_id (idempotence de sql/002_atomic_stock_movement.sql).
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import pandas as pd
import streamlit as st
from modules.help.contextual import show_context_help, topic_help, field_help

from config.roles import has_permission
from core.db_service import fetch_data, get_supabase_client
from modules.stocks.service import (
    enregistrer_entree_mp,
    get_mouvements,
    get_mouvements_pf,
    get_stock_actuel_mp,
    get_stock_actuel_pf,
)

_LOG = logging.getLogger(__name__)
_ACTIVE = frozenset({"oui", "true", "1", "actif", "active", "yes"})
_PENDING_PREFIX = "stocks_entree_manuelle_"


def _stock_access() -> tuple[str, bool] | None:
    """Confirme l'utilisateur/son rôle en base AVANT les lectures de l'écran.

    Ne jamais accorder les droits à partir du seul rôle en session Streamlit,
    puisque la clé service_role contourne RLS.
    """
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
        records = response.data or []
        if len(records) != 1 or not isinstance(records[0], dict):
            return None
        account = records[0]
        if account.get("user_id") != user_id:
            return None
        active = account.get("actif")
        if active is not True and str(active).strip().casefold() not in _ACTIVE:
            return None
        role = account.get("role")
        if not isinstance(role, str) or not role.strip():
            return None
        if has_permission(role, "Stocks", "lecture") is not True:
            return None
        return user_id, has_permission(role, "Stocks", "ecriture") is True
    except Exception as exc:
        _LOG.warning("Accès Stocks non vérifiable (%s)", type(exc).__name__)
        return None


def _entry_key(user_id: str) -> str:
    """Séparer les reprises d'opération entre utilisateurs du même navigateur."""
    return f"{_PENDING_PREFIX}{user_id}"


def _execute_entry(user_id: str) -> bool:
    """Exécute uniquement l'entrée figée, avec son identifiant initial.

    Un timeout peut arriver après le commit. On ne détruit jamais le dossier
    de reprise à la réception d'une exception (même inattendue).
    """
    record = st.session_state[_entry_key(user_id)]
    if record["status"] == "confirmed":
        return False
    payload = record["payload"]
    operation_id = record["operation_id"]
    try:
        enregistrer_entree_mp(
            payload["mp_id"], payload["quantite"], payload["prix_entree"],
            payload["reference"], payload["date_peremption"],
            operation_id=operation_id,
        )
    except (ValueError, PermissionError):
        # Le service Stocks ne lève ces erreurs qu'AVANT tout appel RPC.
        # La saisie peut donc être corrigée sans risque de double écriture.
        del st.session_state[_entry_key(user_id)]
        st.error("Entrée refusée avant enregistrement. Vérifiez les valeurs ou vos droits.")
        return False
    except Exception as exc:
        # Inclut StockOperationError, mais aussi un retour inattendu de l'API.
        # Ne pas exposer les détails techniques ni fabriquer un autre ID.
        _LOG.warning("Entrée Stocks non confirmée (%s)", type(exc).__name__)
        record["status"] = "uncertain"
        st.error("Entrée non confirmée. Conservez cet identifiant et "
                 "vérifiez la réception avant de la relancer.")
        st.code(operation_id)
        return False

    record["status"] = "confirmed"
    st.rerun()
    return True


def _display_entry_status(user_id: str) -> bool:
    """Affiche une entrée déjà engagée ; interdit une deuxième soumission.

    Retourne True si un enregistrement existant occupe le formulaire.
    """
    key = _entry_key(user_id)
    record = st.session_state.get(key)
    if record is None:
        return False
    if (not isinstance(record, dict)
            or record.get("status") not in {"uncertain", "confirmed"}
            or not isinstance(record.get("operation_id"), str)
            or not record["operation_id"].startswith("STK-MAN-")
            or not isinstance(record.get("payload"), dict)
            or any(name not in record["payload"] for name in
                   ("mp_id", "quantite", "prix_entree", "reference", "date_peremption"))):
        st.error("État de réception inconnu : faites contrôler la session par un administrateur.")
        return True

    st.code(record["operation_id"])
    if record["status"] == "confirmed":
        st.success("Entrée confirmée. Une nouvelle entrée nécessite une action explicite.")
        if st.button("Préparer une nouvelle entrée", key=f"stock_new_{user_id}", on_click=_mark_stocks_activity, help=field_help("Préparer une nouvelle entrée", module="stocks")):
            del st.session_state[key]
            st.rerun()
    else:
        st.warning("Réception au statut incertain. Ne créez pas une autre entrée "
                   "pour cette même réception.")
        st.info("Réessayer conserve exactement l'article, la quantité, le prix, "
                "la référence et l'identifiant de l'essai initial.")
        if st.button("Réessayer la même opération", key=f"stock_retry_{user_id}", on_click=_mark_stocks_activity, help=field_help("Réessayer la même opération", module="stocks")):
            _execute_entry(user_id)
    return True


def get_mp_actives():
    df = pd.DataFrame(fetch_data("matieres_premieres"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()


def get_skus_actifs():
    df = pd.DataFrame(fetch_data("sku_conditionnement"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()


def get_produits():
    return pd.DataFrame(fetch_data("produits"))


def _mark_stocks_activity() -> None:
    """Signale une interaction, sans prolonger directement la session."""
    st.session_state["_erp_stocks_interacted"] = True


def _display_value(qty: object, cost: object) -> str | None:
    """Montant en DZD affiché uniquement lorsque le PMP est connu."""
    if cost is None or pd.isna(cost):
        return None
    try:
        q, p = Decimal(str(qty)), Decimal(str(cost))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Stock ou PMP invalide") from exc
    if not q.is_finite() or not p.is_finite() or q < 0 or p < 0:
        raise ValueError("Stock ou PMP invalide")
    return format((q * p).quantize(Decimal("0.01")), "f")


def _statement_tab() -> None:
    """État périodique, lecture exhaustive bornée et sans écriture SQL."""
    st.subheader("État des mouvements MP / PF")
    st.caption("Quantités et valorisation DZD sur période. Aucun retour client, rebut ou perte n'est "
               "identifiable de façon fiable dans le journal actuel : ces colonnes restent non renseignées.")
    start = st.date_input("Du (inclus)", value=date.today().replace(day=1),
                          key="stocks_statement_start")
    end = st.date_input("Au (inclus)", value=date.today(), key="stocks_statement_end")
    mode = st.radio("Présentation", ["Non valorisé (quantités)", "Valorisé (DZD)"],
                    key="stocks_statement_mode", horizontal=True)
    export_format = st.selectbox(
        "Format de l'état", ["Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"],
        key="stocks_statement_export_format",
    )
    if not st.button("Calculer l'état des mouvements", key="stocks_statement_load",
                     on_click=_mark_stocks_activity):
        return
    from core.strict_reads import fetch_data_strict, DataReadError
    from modules.stocks.stock_statement import build_stock_statement, StockStatementError
    try:
        # Historique intégral exigé : une pagination partielle fausserait le stock initial.
        stocks_mp = fetch_data_strict("stock_actuel", max_rows=10000)
        stocks_pf = fetch_data_strict("stock_actuel_pf", max_rows=10000)
        movements_mp = fetch_data_strict("mouvements", max_rows=10000)
        movements_pf = fetch_data_strict("mouvements_pf", max_rows=10000)
        materials = fetch_data_strict("matieres_premieres", max_rows=10000)
        skus = fetch_data_strict("sku_conditionnement", max_rows=10000)
        products = fetch_data_strict("produits", max_rows=10000)
        names = {p["pf_id"]: p.get("nom") or p["pf_id"] for p in products}
        labels_mp = {m["mp_id"]: (m.get("nom") or m["mp_id"], m.get("unite_stock") or "")
                     for m in materials}
        labels_pf = {s["sku_id"]: (
            f"{names.get(s['pf_id'], s['pf_id'])} — {s.get('format') or ''}",
            s.get("unite_vente") or "") for s in skus}
        report_mp = build_stock_statement(
            stocks_mp, movements_mp, item_type="MP",
            start_date=start.isoformat(), end_date=end.isoformat(), labels=labels_mp)
        report_pf = build_stock_statement(
            stocks_pf, movements_pf, item_type="PF",
            start_date=start.isoformat(), end_date=end.isoformat(), labels=labels_pf)
    except (PermissionError, DataReadError, StockStatementError, ValueError, KeyError,
            TypeError, AttributeError) as exc:
        _LOG.warning("État des stocks non vérifiable (%s)", type(exc).__name__)
        st.error("État non disponible : droits, historique, période ou données incohérents. "
                 "Aucun état partiel n'est présenté.")
        return
    columns_qty = ["article", "designation", "unite", "stock_initial", "entrees",
                   "sorties", "retours_clients", "pertes", "stock_final", "tracabilite"]
    columns_value = columns_qty + [
        "pmp_actuel_dzd", "valeur_stock_actuel_dzd",
        "valeur_initiale_dzd", "valeur_entrees_dzd", "valeur_sorties_dzd",
        "valeur_finale_historique_dzd", "valorisation"]
    selected = columns_value if mode == "Valorisé (DZD)" else columns_qty
    for title, rows in (("Matières premières et emballages", report_mp),
                        ("Produits finis (unités SKU)", report_pf)):
        st.subheader(title)
        df = pd.DataFrame(rows, columns=selected)
        st.dataframe(df, use_container_width=True, hide_index=True)
        from core.export_formats import build_export, export_filename, ExportError
        fmt = export_format.split("(")[1].split(")")[0].lstrip(".")
        try:
            payload, mime, ext = build_export(
                df.to_dict("records"), selected, fmt=fmt,
                title=f"État périodique — {title} — {start} au {end}",
                warning="état de gestion NON CERTIFIÉ SCF, stock initial reconstitué",
            )
        except ExportError:
            st.warning("Format sélectionné indisponible pour ce volume : choisir Excel ou CSV.")
        else:
            st.download_button(
                f"Télécharger {export_format} — {title}", data=payload,
                file_name=export_filename(f"Etat_{title}_{start}_{end}", ext),
                mime=mime, key="stocks_statement_export_" +
                ("mp" if rows is report_mp else "pf"),
            )
    st.caption("Stock initial/final reconstitué depuis le stock courant et TOUS les mouvements "
               "historiques. Les coûts historiques proviennent des mouvements enregistrés, "
               "pas du PMP actuel. Un historique sans prix ou un stock antérieur non tracé "
               "rend la valorisation historique indisponible. Rapport de gestion non certifié SCF.")


def show_stocks_page():
    st.title("📦 Gestion des Stocks")

    # Contrôle serveur EN PREMIER : aucun appel fetch_data si lecture interdite.
    access = _stock_access()
    if access is None:
        st.error("Accès aux stocks refusé ou session expirée.")
        return
    user_id, can_write = access

    # st.tabs exécute les trois panneaux, même lorsqu'un seul est visible.
    # Une sélection explicite évite les lectures et formulaires hors écran.
    panels = ("📊 État des Stocks", "🔄 Entrée Manuelle (hors BR)",
              "📋 Historique des Mouvements", "📈 État périodique MP / PF")
    active_panel = st.selectbox(
        "Vue Stocks", panels, key="_erp_stocks_active_panel",
        on_change=_mark_stocks_activity,
        help="Le contenu du seul panneau choisi est chargé.",
    )
    # Le référentiel n'est pas nécessaire pour la consultation des historiques
    # avant un clic ni pour le formulaire d'un utilisateur sans droit d'écriture.
    df_mp_global = (get_mp_actives()
                    if active_panel == panels[1] and can_write
                    else pd.DataFrame())

    if active_panel == panels[3]:
        _statement_tab()

    # --- ONGLET 1 : ÉTAT DES STOCKS ---
    if active_panel == panels[0]:
        st.subheader("Consultation des stocks actuels", help=topic_help("stocks.etat"))
        show_context_help(st, "stocks.etat")
        categories = ("🧪 Matières Premières (Vrac)", "📦 Emballages",
                      "🛍️ Produits Finis")
        active_category = st.selectbox(
            "Catégorie de stock", categories,
            key="_erp_stocks_active_category",
            on_change=_mark_stocks_activity,
            help="Les stocks MP et PF sont lus uniquement dans leur catégorie.",
        )
        if active_category != categories[2]:
            df_mp_global = get_mp_actives()
            df_stock = get_stock_actuel_mp()
            if not df_stock.empty and not df_mp_global.empty:
                df_display = pd.merge(
                    df_stock,
                    df_mp_global[['mp_id', 'nom', 'unite_stock', 'stock_mini', 'categorie_mp']],
                    on='mp_id', how='left',
                )
                is_emballage = df_display["categorie_mp"].fillna("").str.strip().str.upper().isin(
                    ["EMBALLAGE", "EMBALLAGE_CONSOMMABLE"])
                df_vrac = df_display.loc[~is_emballage]
                df_emb = df_display.loc[is_emballage]
            else:
                df_vrac = pd.DataFrame()
                df_emb = pd.DataFrame()

        if active_category == categories[0]:

            show_context_help(st, "stocks.vrac")
            if not df_vrac.empty:
                df_vrac = df_vrac.copy()
                df_vrac["valeur_stock_dzd"] = df_vrac.apply(
                    lambda r: _display_value(r["quantite_disponible"], r["cmp_actuel"]), axis=1)
                st.caption("PMP = coût moyen pondéré unitaire actuel. Valeur = quantité × PMP (DZD).")
                st.dataframe(
                    df_vrac[["mp_id", "nom", "quantite_disponible", "unite_stock",
                             "cmp_actuel", "valeur_stock_dzd", "stock_mini", "derniere_maj"]].rename(
                        columns={"cmp_actuel": "PMP (DZD/unité)",
                                 "valeur_stock_dzd": "Valeur stock (DZD)"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock actuel disponible pour les Matières Premières (Vrac).")

        if active_category == categories[1]:

            show_context_help(st, "stocks.emballages")
            if not df_emb.empty:
                df_emb = df_emb.copy()
                df_emb["valeur_stock_dzd"] = df_emb.apply(
                    lambda r: _display_value(r["quantite_disponible"], r["cmp_actuel"]), axis=1)
                st.caption("PMP = coût moyen pondéré unitaire actuel. Valeur = quantité × PMP (DZD).")
                st.dataframe(
                    df_emb[["mp_id", "nom", "quantite_disponible", "unite_stock",
                            "cmp_actuel", "valeur_stock_dzd", "stock_mini", "derniere_maj"]].rename(
                        columns={"cmp_actuel": "PMP (DZD/unité)",
                                 "valeur_stock_dzd": "Valeur stock (DZD)"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock actuel disponible pour les Emballages.")

        if active_category == categories[2]:

            show_context_help(st, "stocks.pf")
            df_stock_pf = get_stock_actuel_pf()
            df_skus = get_skus_actifs()
            df_prods = get_produits()

            if not df_stock_pf.empty and not df_skus.empty and not df_prods.empty:
                df_skus_prods = pd.merge(df_skus, df_prods[['pf_id', 'nom']], on='pf_id', how='left')
                df_skus_prods['nom_complet'] = df_skus_prods['nom'] + " - " + df_skus_prods['format'].fillna("")
                df_display_pf = pd.merge(df_stock_pf, df_skus_prods[['sku_id', 'nom_complet', 'unite_vente']], on='sku_id', how='left')
                df_display_pf["valeur_stock_dzd"] = df_display_pf.apply(
                    lambda r: _display_value(r["quantite_disponible"], r["cout_revient"]), axis=1)
                st.caption("PMP PF = coût moyen pondéré par unité SKU, pas le coût par kg/L. "
                           "Valeur = quantité SKU × PMP (DZD).")
                st.dataframe(
                    df_display_pf[["sku_id", "nom_complet", "quantite_disponible",
                                   "unite_vente", "cout_revient", "valeur_stock_dzd",
                                   "derniere_maj"]].rename(
                        columns={"cout_revient": "PMP PF (DZD/SKU)",
                                 "valeur_stock_dzd": "Valeur stock (DZD)"}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock de Produits Finis n'a encore été généré par la Production.")

    # --- ONGLET 2 : ENTRÉE MANUELLE ---
    if active_panel == panels[1]:
        st.subheader("Ajustement / Entrée manuelle", help=topic_help("stocks.entree"))
        show_context_help(st, "stocks.entree")
        st.info("Les entrées de PF passent uniquement par la Production. Une réception "
                "déjà enregistrée dans Achats ne doit pas être saisie à nouveau ici.")

        if not can_write:
            st.warning("🔒 Mode lecture seule : vous n'avez pas les droits de modification des stocks.")
        elif _display_entry_status(user_id):
            pass  # On ne crée pas de deuxième opération si l'essai est incertain/confirmé.
        elif not df_mp_global.empty:
            type_entree = st.radio("Que souhaitez-vous approvisionner ?", ["🧪 Matière Première (Vrac)", "📦 Emballage"], horizontal=True, on_change=_mark_stocks_activity, help=field_help("Que souhaitez-vous approvisionner ?", module="stocks"))
            if "Emballage" in type_entree:
                df_mp_filtre = df_mp_global[df_mp_global["categorie_mp"].fillna("").str.strip().str.upper().isin(["EMBALLAGE", "EMBALLAGE_CONSOMMABLE"])]
            else:
                df_mp_filtre = df_mp_global[~df_mp_global["categorie_mp"].fillna("").str.strip().str.upper().isin(["EMBALLAGE", "EMBALLAGE_CONSOMMABLE"])]

            if df_mp_filtre.empty:
                st.warning(f"Aucun article de type '{type_entree}' n'a été trouvé dans le référentiel.")
            else:
                with st.form("form_entree_stock"):
                    c1, c2 = st.columns(2)
                    liste_mp = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_mp_filtre.iterrows()}
                    mp_choisie = c1.selectbox("Article sélectionné", options=list(liste_mp.keys()), format_func=lambda x: liste_mp[x], help=field_help("Article sélectionné", module="stocks"))
                    quantite = c2.number_input("Quantité réceptionnée", min_value=0.1, step=1.0, help=field_help("Quantité réceptionnée", module="stocks"))
                    prix_entree = c1.number_input("Prix d'entrée unitaire (DZD)", min_value=0.0, step=10.0, help=field_help("Prix d'entrée unitaire (DZD)", module="stocks"))
                    reference = c2.text_input("Référence (ex: Ajustement validé)", help=field_help("Référence (ex: Ajustement validé)", module="stocks"))
                    date_peremption = c1.date_input("Date de péremption", help=field_help("Date de péremption", module="stocks"))

                    submitted = st.form_submit_button("Valider l'entrée en stock", type="primary", on_click=_mark_stocks_activity, help=field_help("Valider l'entrée en stock", module="stocks"))
                if submitted:
                    if not isinstance(reference, str) or not reference.strip():
                        st.error("Veuillez saisir une référence.")
                    else:
                        # Enregistrer le dossier de reprise AVANT le premier appel RPC.
                        st.session_state[_entry_key(user_id)] = {
                            "operation_id": f"STK-MAN-{uuid4().hex}",
                            "status": "uncertain",
                            "payload": {
                                "mp_id": mp_choisie, "quantite": quantite,
                                "prix_entree": prix_entree,
                                "reference": reference.strip(),
                                "date_peremption": str(date_peremption),
                            },
                        }
                        _execute_entry(user_id)
        else:
            st.warning("Aucun article actif trouvé dans le référentiel.")

    # --- ONGLET 3 : HISTORIQUE DES MOUVEMENTS ---
    if active_panel == panels[2]:
        st.subheader("Historique des mouvements", help=topic_help("stocks.historique"))
        show_context_help(st, "stocks.historique")
        st.caption("Consultation paginée : 50 mouvements maximum par registre et par clic.")
        page_stock = st.number_input(
            "Page des mouvements", min_value=1, max_value=1000,
            value=1, step=1, key="ng_stocks_history_page"
        , help=field_help("Page des mouvements", module="stocks"))
        from core.history_filters import history_period_inputs
        period = history_period_inputs("ng_stocks_history")
        if period is not None and st.button(
                "Afficher les mouvements de stock", key="ng_stocks_history_load",
                on_click=_mark_stocks_activity, help=field_help("Afficher les mouvements de stock", module="stocks")):
            from core.strict_reads import fetch_history_page_strict, DataReadError
            try:
                mp_rows, mp_total = fetch_history_page_strict("mouvements", page=int(page_stock), date_column="date", **period)
                pf_rows, pf_total = fetch_history_page_strict("mouvements_pf", page=int(page_stock), date_column="date", **period)
                df_mouv = pd.DataFrame(mp_rows)
                df_mouv_pf = pd.DataFrame(pf_rows)
            except (PermissionError, DataReadError, ValueError):
                st.error("Historique Stocks indisponible : droits ou lecture incomplète.")
            else:
                st.caption(
                    f"Page {int(page_stock)} : mouvements MP {len(mp_rows)}/{mp_total}, "
                    f"mouvements PF {len(pf_rows)}/{pf_total}."
                )
                # Historique ouvert explicitement : récupérer le référentiel
                # seulement si une page MP doit être ventilée par catégorie.
                df_mp_global = get_mp_actives() if not df_mouv.empty else pd.DataFrame()
                if not df_mouv.empty and not df_mp_global.empty:
                    df_mouv_detail = pd.merge(
                        df_mouv, df_mp_global[["mp_id", "categorie_mp"]],
                        on="mp_id", how="left"
                    )
                    emballages = df_mouv_detail["categorie_mp"].fillna("").str.strip().str.upper().isin(
                        ["EMBALLAGE", "EMBALLAGE_CONSOMMABLE"]
                    )
                    df_mouv_vrac = df_mouv_detail.loc[~emballages]
                    df_mouv_emb = df_mouv_detail.loc[emballages]
                else:
                    df_mouv_vrac = pd.DataFrame()
                    df_mouv_emb = pd.DataFrame()
                st.caption("Les catégories Vrac et Emballages sont filtrées sur la page MP chargée.")
                with st.expander("Mouvements Vrac", expanded=True):
                    if df_mouv_vrac.empty:
                        st.info("Aucun mouvement Vrac sur cette page.")
                    else:
                        st.dataframe(df_mouv_vrac.drop(columns=["categorie_mp"]),
                                     use_container_width=True, hide_index=True)
                with st.expander("Mouvements Emballages"):
                    if df_mouv_emb.empty:
                        st.info("Aucun mouvement Emballages sur cette page.")
                    else:
                        st.dataframe(df_mouv_emb.drop(columns=["categorie_mp"]),
                                     use_container_width=True, hide_index=True)
                with st.expander("Mouvements Produits Finis"):
                    if df_mouv_pf.empty:
                        st.info("Aucun mouvement PF sur cette page.")
                    else:
                        st.dataframe(df_mouv_pf, use_container_width=True, hide_index=True)
