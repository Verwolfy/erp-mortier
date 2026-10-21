"""Écran Stocks : contrôle de lecture et entrées manuelles anti-doublon.

Supabase reste la source de vérité. En cas d'erreur réseau, on réutilise le
même operation_id (idempotence de sql/002_atomic_stock_movement.sql).
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pandas as pd
import streamlit as st

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
    st.cache_data.clear()
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
        if st.button("Préparer une nouvelle entrée", key=f"stock_new_{user_id}"):
            del st.session_state[key]
            st.rerun()
    else:
        st.warning("Réception au statut incertain. Ne créez pas une autre entrée "
                   "pour cette même réception.")
        st.info("Réessayer conserve exactement l'article, la quantité, le prix, "
                "la référence et l'identifiant de l'essai initial.")
        if st.button("Réessayer la même opération", key=f"stock_retry_{user_id}"):
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


def show_stocks_page():
    st.title("📦 Gestion des Stocks")

    # Contrôle serveur EN PREMIER : aucun appel fetch_data si lecture interdite.
    access = _stock_access()
    if access is None:
        st.error("Accès aux stocks refusé ou session expirée.")
        return
    user_id, can_write = access

    tab1, tab2, tab3 = st.tabs(["📊 État des Stocks", "🔄 Entrée Manuelle (hors BR)", "📋 Historique des Mouvements"])

    df_mp_global = get_mp_actives()

    # --- ONGLET 1 : ÉTAT DES STOCKS ---
    with tab1:
        st.subheader("Consultation des stocks actuels")
        sous_tab_vrac, sous_tab_emb, sous_tab_pf = st.tabs(["🧪 Matières Premières (Vrac)", "📦 Emballages", "🛍️ Produits Finis"])
        df_stock = get_stock_actuel_mp()

        if not df_stock.empty and not df_mp_global.empty:
            df_display = pd.merge(df_stock, df_mp_global[['mp_id', 'nom', 'unite_stock', 'stock_mini', 'categorie_mp']], on='mp_id', how='left')
            df_vrac = df_display[df_display["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"]
            df_emb = df_display[df_display["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]
        else:
            df_vrac = pd.DataFrame()
            df_emb = pd.DataFrame()

        with sous_tab_vrac:
            if not df_vrac.empty:
                st.dataframe(
                    df_vrac[["mp_id", "nom", "quantite_disponible", "unite_stock", "cmp_actuel", "stock_mini", "derniere_maj"]],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock actuel disponible pour les Matières Premières (Vrac).")

        with sous_tab_emb:
            if not df_emb.empty:
                st.dataframe(
                    df_emb[["mp_id", "nom", "quantite_disponible", "unite_stock", "cmp_actuel", "stock_mini", "derniere_maj"]],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock actuel disponible pour les Emballages.")

        with sous_tab_pf:
            df_stock_pf = get_stock_actuel_pf()
            df_skus = get_skus_actifs()
            df_prods = get_produits()

            if not df_stock_pf.empty and not df_skus.empty and not df_prods.empty:
                df_skus_prods = pd.merge(df_skus, df_prods[['pf_id', 'nom']], on='pf_id', how='left')
                df_skus_prods['nom_complet'] = df_skus_prods['nom'] + " - " + df_skus_prods['format'].fillna("")
                df_display_pf = pd.merge(df_stock_pf, df_skus_prods[['sku_id', 'nom_complet', 'unite_vente']], on='sku_id', how='left')
                st.dataframe(
                    df_display_pf[["sku_id", "nom_complet", "quantite_disponible", "unite_vente", "cout_revient", "derniere_maj"]],
                    use_container_width=True, hide_index=True
                )
            else:
                st.info("Aucun stock de Produits Finis n'a encore été généré par la Production.")

    # --- ONGLET 2 : ENTRÉE MANUELLE ---
    with tab2:
        st.subheader("Ajustement / Entrée manuelle")
        st.info("Les entrées de PF passent uniquement par la Production. Une réception "
                "déjà enregistrée dans Achats ne doit pas être saisie à nouveau ici.")

        if not can_write:
            st.warning("🔒 Mode lecture seule : vous n'avez pas les droits de modification des stocks.")
        elif _display_entry_status(user_id):
            pass  # On ne crée pas de deuxième opération si l'essai est incertain/confirmé.
        elif not df_mp_global.empty:
            type_entree = st.radio("Que souhaitez-vous approvisionner ?", ["🧪 Matière Première (Vrac)", "📦 Emballage"], horizontal=True)
            if "Emballage" in type_entree:
                df_mp_filtre = df_mp_global[df_mp_global["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]
            else:
                df_mp_filtre = df_mp_global[df_mp_global["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"]

            if df_mp_filtre.empty:
                st.warning(f"Aucun article de type '{type_entree}' n'a été trouvé dans le référentiel.")
            else:
                with st.form("form_entree_stock"):
                    c1, c2 = st.columns(2)
                    liste_mp = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_mp_filtre.iterrows()}
                    mp_choisie = c1.selectbox("Article sélectionné", options=list(liste_mp.keys()), format_func=lambda x: liste_mp[x])
                    quantite = c2.number_input("Quantité réceptionnée", min_value=0.1, step=1.0)
                    prix_entree = c1.number_input("Prix d'entrée unitaire (DZD)", min_value=0.0, step=10.0)
                    reference = c2.text_input("Référence (ex: Ajustement validé)")
                    date_peremption = c1.date_input("Date de péremption")

                    submitted = st.form_submit_button("Valider l'entrée en stock", type="primary")
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
    with tab3:
        st.subheader("Historique des mouvements")
        sous_tab_hist_vrac, sous_tab_hist_emb, sous_tab_hist_pf = st.tabs(["🧪 Mouvements Vrac", "📦 Mouvements Emballages", "🛍️ Mouvements PF"])
        df_mouv = get_mouvements()
        if not df_mouv.empty and not df_mp_global.empty:
            df_mouv_detail = pd.merge(df_mouv, df_mp_global[['mp_id', 'categorie_mp']], on='mp_id', how='left')
            df_mouv_vrac = df_mouv_detail[df_mouv_detail["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"]
            df_mouv_emb = df_mouv_detail[df_mouv_detail["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]
        else:
            df_mouv_vrac = pd.DataFrame()
            df_mouv_emb = pd.DataFrame()

        with sous_tab_hist_vrac:
            if not df_mouv_vrac.empty:
                st.dataframe(df_mouv_vrac.drop(columns=["categorie_mp"]).sort_values(by="date", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun mouvement enregistré pour le Vrac.")

        with sous_tab_hist_emb:
            if not df_mouv_emb.empty:
                st.dataframe(df_mouv_emb.drop(columns=["categorie_mp"]).sort_values(by="date", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun mouvement enregistré pour les Emballages.")

        with sous_tab_hist_pf:
            df_mouv_pf = get_mouvements_pf()
            if not df_mouv_pf.empty:
                st.dataframe(df_mouv_pf.sort_values(by="date", ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun mouvement enregistré pour les Produits Finis.")
