"""
Interface utilisateur du module RH.
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from modules.rh.service import create_employe, create_demande_conge, get_employes, get_conges


def _mark_rh_activity() -> None:
    """Signale une interaction RH sans renouveler directement la session."""
    st.session_state["_erp_rh_interacted"] = True


def _rh_access() -> tuple[str, bool, bool] | None:
    """Rôle de la base et compte actif, non du champ role en session."""
    try:
        if st.session_state.get("authenticated") is not True:
            return None
        user = st.session_state.get("user")
        user_id = user.get("user_id") if isinstance(user, dict) else None
        if not isinstance(user_id, str) or not user_id.strip():
            return None
        from core.db_service import get_supabase_client
        result = (get_supabase_client().table("users")
                  .select("user_id,role,actif").eq("user_id", user_id)
                  .limit(2).execute())
        rows = result.data
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            return None
        actor = rows[0]
        active = actor.get("actif")
        if (actor.get("user_id") != user_id
                or (active is not True and str(active).strip().upper()
                    not in {"OUI", "TRUE", "1", "ACTIF", "ACTIVE", "YES"})
                or not isinstance(actor.get("role"), str)):
            return None
        user_role = actor["role"]
        if has_permission(user_role, "RH", "lecture") is not True:
            return None
        can_write = has_permission(user_role, "RH", "ecriture") is True
        can_read_paie = has_permission(user_role, "Paie", "lecture") is True
        return user_role, can_write, can_read_paie
    except Exception:
        return None


def show_rh_page():
    st.title("👥 Ressources Humaines")
    access = _rh_access()
    if access is None:
        st.error("Accès RH refusé : session, compte ou permission non vérifiable.")
        return
    user_role, can_write, can_read_paie = access
    noms_onglets = ["👨‍💼 Registre des Employés", "🌴 Gestion des Congés"]
    if can_read_paie:
        noms_onglets.append("🧮 Simulation IRG (non validée)")
        noms_onglets.append("🔎 Préparation Paie IRG / CNAS")
    onglets = st.tabs(noms_onglets)
    tab1, tab2 = onglets[:2]

    with tab1:
        st.subheader("Employés")
        if can_write:
            with st.expander("➕ Ajouter un employé"):
                with st.form("form_employe"):
                    c1, c2 = st.columns(2)
                    nom = c1.text_input("Nom complet *")
                    poste = c2.text_input("Poste")
                    service = c1.selectbox("Service",
                                           ["Direction", "Production", "Ventes", "Logistique", "RH", "Maintenance"])
                    manager = c2.text_input("ID Manager (Optionnel)")
                    date_embauche = c1.date_input("Date d'embauche")

                    if st.form_submit_button("Enregistrer", type="primary", on_click=_mark_rh_activity):
                        if nom:
                            create_employe(nom, poste, service, manager, str(date_embauche))
                            st.success(f"Employé {nom} ajouté avec succès !")
                            st.rerun()
                        else:
                            st.error("Le nom est obligatoire.")

        df_emp = get_employes()
        if not df_emp.empty:
            st.dataframe(df_emp, use_container_width=True)
        else:
            st.info("Aucun employé enregistré.")

    with tab2:
        st.subheader("Demandes de Congés")
        if can_write:
            if df_emp.empty:
                st.warning("Veuillez d'abord ajouter des employés pour saisir des congés.")
            else:
                with st.form("form_conges"):
                    c_emp, c_dates = st.columns(2)
                    liste_employes = {row["employe_id"]: f"{row['employe_id']} - {row['nom']}" for _, row in
                                      df_emp.iterrows() if str(row.get("actif", "")) == "OUI"}
                    emp_choisi = c_emp.selectbox("Employé", options=list(liste_employes.keys()),
                                                 format_func=lambda x: liste_employes[x])

                    c_deb, c_fin = c_dates.columns(2)
                    date_debut = c_deb.date_input("Date de début")
                    date_fin = c_fin.date_input("Date de fin")
                    motif = st.text_input("Motif (Ex: Congé annuel, Maladie)")

                    if st.form_submit_button("Soumettre la demande", type="primary", on_click=_mark_rh_activity):
                        if date_fin < date_debut:
                            st.error("La date de fin ne peut pas précéder la date de début.")
                        else:
                            create_demande_conge(emp_choisi, str(date_debut), str(date_fin), motif)
                            st.success("Demande enregistrée !")
                            st.rerun()

        df_conges = get_conges()
        if not df_conges.empty:
            st.dataframe(df_conges, use_container_width=True)
        else:
            st.info("Aucune demande de congé.")
    if can_read_paie:
        with onglets[2]:
            st.subheader("Simulation IRG - traitements et salaires")
            st.warning(
                "Simulation interne uniquement : ni bulletin de paie, "
                "ni calcul fiscal homologué, ni déclaration."
            )
            st.caption(
                "Seules les assiettes imposables déjà déterminées et les "
                "règles vérifiées disponibles dans Supabase sont acceptées."
            )
            from core.utils import get_local_now
            date_fiscale = st.date_input(
                "Date de paie", value=get_local_now().date(),
                key="rh_irg_date",
            )
            assiette = st.text_input(
                "Assiette imposable mensuelle (DZD) - montant exact",
                key="rh_irg_assiette",
                placeholder="Ex. 50000.00",
            )
            profil = st.selectbox(
                "Catégorie de revenu mensuel",
                ["SALARIE", "HANDICAPE_RETRAITE"],
                key="rh_irg_profil",
            )
            if st.button(
                "Simuler IRG", key="rh_irg_simuler",
                on_click=_mark_rh_activity,
            ):
                fresh = _rh_access()
                if fresh is None or fresh[0] != user_role or fresh[2] is not True:
                    st.error("Droit Paie absent ou révoqué ; simulation interdite.")
                    return
                from core.irg_salaires import IRGNonDisponible
                from core.irg_service import simuler_irg_depuis_supabase
                try:
                    irg = simuler_irg_depuis_supabase(
                        assiette, date_fiscale.isoformat(), profil,
                    )
                except IRGNonDisponible:
                    st.error(
                        "Simulation indisponible : assiette invalide, règle "
                        "IRG manquante ou réglementation non confirmée."
                    )
                else:
                    st.metric("IRG mensuel simulé (DZD)", irg["irg_simule"])
                    st.caption(
                        f"Barème : {irg['code']} | "
                        f"Date effet : {irg['date_effet']} | "
                        "Statut : simulation non validée"
                    )


    if can_read_paie:
        with onglets[3]:
            _preflight_paie_tab(user_role)


def _preflight_paie_tab(user_role: str) -> None:
    """Diagnostic des règles IRG/CNAS ; n'émet aucune fiche de paie."""
    st.subheader("Préparation des références IRG et CNAS")
    st.caption("Statut réglementaire uniquement, sans données nominatives de salarié.")
    from core.utils import get_local_now
    date_paie = st.date_input(
        "Date réglementaire à vérifier", value=get_local_now().date(),
        key="rh_paie_preflight_date",
    )
    if not st.button("Vérifier les référentiels", key="rh_paie_preflight",
                     on_click=_mark_rh_activity):
        return
    fresh = _rh_access()
    if fresh is None or fresh[0] != user_role or fresh[2] is not True:
        st.error("Droit Paie absent, révoqué ou non vérifiable.")
        return
    from core.preflight_paie import PreparationPaieIndisponible, lire_preparation_paie
    from core.db_service import get_supabase_client
    try:
        result = lire_preparation_paie(
            db_client=get_supabase_client(), date_paie=date_paie.isoformat()
        )
    except PreparationPaieIndisponible:
        st.error("Référentiels incomplets ou contradictoires : aucun diagnostic partiel.")
        return
    except Exception:
        st.error("Référentiels de paie indisponibles : aucun diagnostic partiel.")
        return
    st.metric("CNAS salariale documentée", "Oui" if result["reference_cnas_salarie"] else "Non")
    st.metric("CNAS employeur documentée", "Oui" if result["reference_cnas_employeur"] else "Non")
    st.metric("Barème IRG mensuel documenté", "Oui" if result["reference_irg_mensuel"] else "Non")
    st.warning(
        "Assiettes individuelles, profils, particularités et déclarations "
        "non validés : aucun bulletin de paie officiel ne peut être produit."
    )
