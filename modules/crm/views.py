"""
Interface utilisateur du module CRM.
"""
import streamlit as st
import logging
from modules.help.contextual import show_context_help, topic_help, field_help
import pandas as pd
from config.roles import has_permission
from core.db_service import get_supabase_client
from core.strict_reads import fetch_data_strict as fetch_data, read_section
from core.listes_service import get_liste, liste_to_dict
from modules.crm.service import create_opportunite, create_interaction, get_pipeline, get_interactions
from modules.crm.site_requests import inbox_enabled, list_requests_readonly, MAX_ROWS

_LOG = logging.getLogger(__name__)
_ACTIVE = frozenset({"OUI", "TRUE", "1", "ACTIF", "ACTIVE", "YES"})


def _crm_access() -> tuple[str, bool] | None:
    """Rôle et compte CRM réinterrogés en base, jamais tirés de la session.

    Un contrôle serveur est aussi exécuté lors de chaque validation d'écriture.
    Toute réponse absente, contradictoire ou erreur réseau refuse l'accès.
    """
    try:
        if st.session_state.get("authenticated") is not True:
            return None
        session_user = st.session_state.get("user")
        if not isinstance(session_user, dict):
            return None
        user_id = session_user.get("user_id")
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        response = (get_supabase_client().table("users")
                    .select("user_id,role,actif")
                    .eq("user_id", user_id).limit(2).execute())
        records = response.data
        if not isinstance(records, list) or len(records) != 1:
            return None
        actor = records[0]
        if not isinstance(actor, dict) or actor.get("user_id") != user_id:
            return None
        active = actor.get("actif")
        if not (active is True or (
                isinstance(active, str) and active.strip().upper() in _ACTIVE)):
            return None
        role = actor.get("role")
        if not isinstance(role, str) or not role.strip():
            return None
        if has_permission(role, "CRM", "lecture") is not True:
            return None
        return user_id, has_permission(role, "CRM", "ecriture") is True
    except Exception as exc:
        _LOG.warning("Accès CRM non vérifiable (%s)", type(exc).__name__)
        return None


def _mark_crm_activity() -> None:
    """Signale une interaction sans renouvellement direct."""
    st.session_state["_erp_crm_interacted"] = True


def get_clients_actifs():
    df = pd.DataFrame(fetch_data("clients"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def show_crm_page():
    st.title("🤝 CRM & Relation Client")
    st.caption("Version lectures CRM : SOF-ERP-20261101-READ-01")

    # Le rôle et l'état actif sont revalidés depuis Supabase avant toute vue.
    # Le rôle contenu dans la session ne constitue jamais une autorisation.
    access = _crm_access()
    if access is None:
        st.error("Accès CRM refusé : compte ou droits non vérifiables.")
        return
    user_id, can_write = access

    # Contrairement à st.tabs, une sélection ne calcule pas les vues masquées.
    panels = ("🎯 Pipeline (Opportunités)", "📞 Consigner une interaction",
              "📋 Historique des échanges", "🌐 Demandes NextGen")
    active_panel = st.selectbox(
        "Vue CRM", panels, key="_erp_crm_active_panel",
        on_change=_mark_crm_activity,
        help="Une seule vue CRM est chargée à la fois.",
    )

    if active_panel == panels[0]:
        with read_section("Pipeline"):
            st.subheader("Gestion du Pipeline", help=topic_help("crm.pipeline"))
            show_context_help(st, "crm.pipeline")
            if can_write:
                with st.expander("➕ Nouvelle Opportunité"):
                    with st.form("form_opp"):
                        c1, c2 = st.columns(2)
                        prospect = c1.text_input("Nom du prospect / entreprise *", help=field_help("Nom du prospect / entreprise *", module="crm"))
                        contact = c2.text_input("Contact (Nom, Email, Tel)", help=field_help("Contact (Nom, Email, Tel)", module="crm"))

                        statut = c1.selectbox("Statut", ["Nouveau", "Contacté", "En Négociation", "Gagné", "Perdu"], help=field_help("Statut", module="crm"))
                        commercial = c2.text_input("ID Commercial assigné (ex: USR-0001)", help=field_help("ID Commercial assigné (ex: USR-0001)", module="crm"))

                        valeur = c1.number_input("Valeur estimée (DZD)", min_value=0.0, step=1000.0, help=field_help("Valeur estimée (DZD)", module="crm"))
                        probabilite = c2.slider("Probabilité de succès (%)", 0, 100, 50, help=field_help("Probabilité de succès (%)", module="crm"))

                        if st.form_submit_button("Ajouter au pipeline", type="primary", on_click=_mark_crm_activity, help=field_help("Ajouter au pipeline", module="crm")):
                            fresh = _crm_access()
                            if fresh is None or fresh[0] != user_id or fresh[1] is not True:
                                st.error("Droit CRM écriture absent ou révoqué ; création interdite.")
                            elif prospect:
                                create_opportunite(prospect, contact, statut, commercial, valeur, float(probabilite))
                                st.success("Opportunité créée !")
                                st.rerun()
                            else:
                                st.error("Le nom du prospect est obligatoire.")

            df_pipe = get_pipeline()
            if not df_pipe.empty:
                st.dataframe(df_pipe, use_container_width=True)
            else:
                st.info("Aucune opportunité en cours.")

    if active_panel == panels[1]:
        with read_section("Clients CRM"):
            st.subheader("Consigner une Interaction", help=topic_help("crm.interaction"))
            show_context_help(st, "crm.interaction")
            df_clients = get_clients_actifs() if can_write else pd.DataFrame()

            if not can_write:
                st.info("🔒 Mode lecture seule.")
            elif df_clients.empty:
                st.warning("Veuillez configurer des clients dans l'Administration.")
            else:
                with st.form("form_interaction"):
                    c_cli, c_type = st.columns(2)
                    liste_clients = {row["client_id"]: f"{row['client_id']} - {row['nom']}" for _, row in df_clients.iterrows()}
                    client_choisi = c_cli.selectbox("Client concerné", options=list(liste_clients.keys()), format_func=lambda x: liste_clients[x], help=field_help("Client concerné", module="crm"))

                    # Utilisation du format PascalCase
                    dict_types = liste_to_dict(get_liste("TypeInteractionCRM", strict=True))
                    if not dict_types:
                        dict_types = {"Appel": "Appel", "Email": "Email", "Visite": "Visite", "Relance": "Relance"}
                    type_action = c_type.selectbox("Type d'action", options=list(dict_types.keys()), format_func=lambda x: dict_types.get(x, x), help=field_help("Type d'action", module="crm"))

                    notes = st.text_area("Notes et compte-rendu", help=field_help("Notes et compte-rendu", module="crm"))
                    date_rappel = st.date_input("Date de prochain rappel (optionnel)", value=None, help=field_help("Date de prochain rappel (optionnel)", module="crm"))

                    date_rappel_str = str(date_rappel) if date_rappel else ""

                    if st.form_submit_button("Enregistrer l'interaction", type="primary", on_click=_mark_crm_activity, help=field_help("Enregistrer l'interaction", module="crm")):
                        fresh = _crm_access()
                        if fresh is None or fresh[0] != user_id or fresh[1] is not True:
                            st.error("Droit CRM écriture absent ou révoqué ; enregistrement interdit.")
                        else:
                            create_interaction(client_choisi, type_action, notes, date_rappel_str)
                            st.success("Interaction enregistrée !")
                            st.rerun()

    if active_panel == panels[2]:
        with read_section("Historique CRM"):
            st.subheader("Historique des Interactions", help=topic_help("crm.historique"))
            show_context_help(st, "crm.historique")
            st.caption("Chargement à la demande pour éviter une lecture inutile à chaque navigation.")
            page_crm = st.number_input(
                "Page historique CRM", min_value=1, max_value=1000, value=1,
                step=1, key="ng_crm_history_page", help=field_help("Page historique CRM", module="crm"))
            if st.button("Afficher l'historique CRM", key="ng_crm_load_history", help=field_help("Afficher l'historique CRM", module="crm")):
                from modules.crm.service import get_interactions_page
                df_int, total = get_interactions_page(page=int(page_crm))
                if not df_int.empty:
                    st.caption(f"Page {int(page_crm)} — {len(df_int)} lignes affichées sur {total} au total (50 maximum par page).")
                    st.dataframe(df_int, use_container_width=True)
                elif total:
                    st.info(f"Page sans résultat ; {total} interactions disponibles. Choisissez une page antérieure.")
                else:
                    st.info("Aucun historique disponible.")

    if active_panel == panels[3]:
        st.subheader("Demandes reçues du site NextGen", help=topic_help("crm.nextgen"))
        show_context_help(st, "crm.nextgen")
        # Fixed UI fingerprint allows an authenticated operator to confirm deployed UI version.
        st.caption("Version interface NextGen CRM : SOF-NEXTGEN-CRM-20261101-L9")
        st.caption("Consultation technique non nominative. Aucune conversion client automatique.")
        if not inbox_enabled():
            st.info("Fonction préparée, en attente de validation confidentialité et d'activation par l'administrateur.")
        else:
            try:
                demandes, suite = list_requests_readonly()
            except PermissionError:
                st.error("Accès aux demandes refusé. Vérifiez votre habilitation CRM.")
            except Exception:
                # Ne jamais inclure la réponse Supabase, une clé ou des données personnelles.
                st.error("Lecture des demandes indisponible. Aucune donnée affichée.")
            else:
                if not demandes:
                    st.info("Aucune demande NextGen enregistrée.")
                else:
                    affichage = pd.DataFrame(demandes).rename(columns={
                        "demande_id": "Identifiant technique",
                        "type_demande": "Type",
                        "statut": "Statut",
                        "cree_le": "Créée le",
                    })
                    st.dataframe(affichage, use_container_width=True, hide_index=True)
                    if suite:
                        st.warning(
                            f"Affichage limité aux {MAX_ROWS} demandes les plus récentes. "
                            "L'ensemble de l'historique n'est pas affiché."
                        )
