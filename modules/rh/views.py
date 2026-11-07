"""
Interface utilisateur du module RH.
"""
import streamlit as st
from modules.help.contextual import show_context_help, topic_help, field_help
import pandas as pd
from config.roles import has_permission
from core.strict_reads import DataReadError
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
    try:
        df_emp = get_employes()
        df_conges = get_conges()
    except (DataReadError, PermissionError):
        st.error("RH : données indisponibles ou accès refusé. Réessayez la consultation ; aucune liste vide ne peut être confirmée.")
        return
    noms_onglets = ["👨‍💼 Registre des Employés", "🌴 Gestion des Congés"]
    if can_read_paie:
        noms_onglets.append("🧮 Simulation IRG (non validée)")
        noms_onglets.append("🔎 Préparation Paie IRG / CNAS")
        noms_onglets.append("🧪 Atelier paie fictive")
    onglets = st.tabs(noms_onglets)
    tab1, tab2 = onglets[:2]

    with tab1:
        st.subheader("Employés", help=topic_help("rh.employes"))
        show_context_help(st, "rh.employes")
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
                        fresh = _rh_access()
                        if fresh is None or fresh[0] != user_role or fresh[1] is not True:
                            st.error("Droit RH écriture absent ou révoqué ; ajout interdit.")
                        elif nom:
                            try:
                                create_employe(nom, poste, service, manager, str(date_embauche))
                            except RuntimeError:
                                st.error("Création non confirmée : consultez le registre avant de recommencer pour éviter un doublon.")
                            else:
                                st.success(f"Employé {nom} ajouté avec succès !")
                                st.rerun()
                        else:
                            st.error("Le nom est obligatoire.")

        if not df_emp.empty and "employe_id" in df_emp:
            fictifs = df_emp["employe_id"].astype(str).str.startswith("SIM-RH-").sum()
            if fictifs:
                st.warning(f"{fictifs} fiche(s) SIM-RH fictive(s) dans ce registre. Elles servent aux tests et figurent dans les compteurs ; ne pas les utiliser pour une paie ou une déclaration réelle.")
        if not df_emp.empty:
            st.dataframe(df_emp, use_container_width=True)
        else:
            st.info("Aucun employé enregistré.")

    with tab2:
        st.subheader("Demandes de Congés", help=topic_help("rh.conges"))
        show_context_help(st, "rh.conges")
        if can_write:
            liste_employes = {row["employe_id"]: f"{row['employe_id']} - {row['nom']}"
                              for _, row in df_emp.iterrows() if str(row.get("actif", "")) == "OUI"}
            if df_emp.empty:
                st.warning("Veuillez d'abord ajouter des employés pour saisir des congés.")
            elif not liste_employes:
                st.warning("Aucun employé actif : aucune demande de congé ne peut être saisie.")
            else:
                with st.form("form_conges"):
                    c_emp, c_dates = st.columns(2)
                    emp_choisi = c_emp.selectbox("Employé", options=list(liste_employes.keys()),
                                                 format_func=lambda x: liste_employes[x])

                    c_deb, c_fin = c_dates.columns(2)
                    date_debut = c_deb.date_input("Date de début")
                    date_fin = c_fin.date_input("Date de fin")
                    motif = st.text_input("Motif (Ex: Congé annuel, Maladie)")

                    if st.form_submit_button("Soumettre la demande", type="primary", on_click=_mark_rh_activity):
                        fresh = _rh_access()
                        if fresh is None or fresh[0] != user_role or fresh[1] is not True:
                            st.error("Droit RH écriture absent ou révoqué ; congé non enregistré.")
                        elif date_fin < date_debut:
                            st.error("La date de fin ne peut pas précéder la date de début.")
                        else:
                            try:
                                create_demande_conge(emp_choisi, str(date_debut), str(date_fin), motif)
                            except RuntimeError:
                                st.error("Enregistrement non confirmé : consultez le registre avant de recommencer pour éviter un doublon.")
                            except (ValueError, DataReadError, PermissionError):
                                st.error("Demande non confirmée : vérifiez l’employé, les dates et le registre avant toute nouvelle tentative.")
                            else:
                                st.success("Demande enregistrée !")
                                st.rerun()

        if not df_conges.empty:
            if "demande_conge_id" in df_conges:
                fictifs_conges = df_conges["demande_conge_id"].astype(str).str.startswith("SIM-CNG-").sum()
                if fictifs_conges:
                    st.warning(f"{fictifs_conges} demande(s) SIM-CNG fictive(s) dans ce registre ; elles figurent dans les compteurs.")
            st.dataframe(df_conges, use_container_width=True)
        else:
            st.info("Aucune demande de congé.")
    if can_read_paie:
        with onglets[2]:
            st.subheader("Simulation IRG - traitements et salaires", help=topic_help("rh.irg"))
            show_context_help(st, "rh.irg")
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

        with onglets[4]:
            _atelier_paie_fictive(df_emp, user_role)


def _atelier_paie_fictive(df_emp: pd.DataFrame, user_role: str) -> None:
    """Atelier arithmétique borné au jeu SIM-RH ; aucune écriture ou règle légale."""
    st.subheader("Atelier de paie fictive", help=topic_help("rh.simulation"))
    show_context_help(st, "rh.simulation")
    st.warning("TEST UNIQUEMENT — montants et taux arbitraires ; aucun calcul CNAS ou IRG officiel, aucun bulletin, paiement ou déclaration. Ne pas utiliser pour une paie réelle.")
    st.caption("Exemple fixe : retenue de test 5 %, contribution de test 10 %, retenue forfaitaire de test 1 000 DZD. Ces valeurs ne sont pas des taux légaux.")
    required = {"employe_id", "nom", "actif"}
    if df_emp.empty or not required.issubset(df_emp):
        st.info("Aucun employé fictif actif disponible.")
        return
    rows = df_emp.loc[
        df_emp["employe_id"].astype(str).str.fullmatch(r"SIM-RH-00[1-8]")
        & df_emp["nom"].astype(str).str.startswith("[FICTIF]")
        & (df_emp["actif"] == "OUI")
    ].sort_values("employe_id")
    if rows.empty:
        st.info("Aucun employé fictif actif disponible.")
        return
    options = rows["employe_id"].tolist()
    chosen = st.selectbox("Employé fictif", options=options, key="rh_test_employe",
                          on_change=_mark_rh_activity)
    if st.button("Calculer l’exemple fictif", key="rh_test_calculer",
                 on_click=_mark_rh_activity):
        fresh = _rh_access()
        if fresh is None or fresh[0] != user_role or fresh[2] is not True:
            st.error("Droit Paie absent, révoqué ou non vérifiable.")
            return
        from decimal import Decimal
        number = int(chosen.rsplit("-", 1)[1])
        base = Decimal("40000") + Decimal(number) * Decimal("1000")
        retenue = base * Decimal("0.05")
        contribution = base * Decimal("0.10")
        net = base - retenue - Decimal("1000")
        st.metric("Base fictive (DZD)", f"{base:.2f}")
        st.metric("Retenues fictives (DZD)", f"{retenue + Decimal('1000'):.2f}")
        st.metric("Net fictif (DZD)", f"{net:.2f}")
        st.metric("Contribution fictive de test (DZD)", f"{contribution:.2f}")
        st.caption("Calcul en mémoire seulement ; aucune donnée de paie n’est enregistrée.")

    st.divider()
    st.markdown("**Comparaison fictive avec la table DGI 2022**")
    st.caption("Hypothèses de test : brut fictif totalement soumis à 9 % de cotisation salariale, aucune prime ni autre retenue ; assiette IRG = brut − cotisation. Les 8 valeurs proviennent de lignes précises de la table DGI 2022. Applicabilité à la période et assiettes réelles non vérifiées.")
    st.markdown("[Table DGI 2022](https://www.mfdgi.gov.dz/images/bareme_irg/TABLE_IRG_2022.pdf) · [Journal officiel n°49/2015, page 7](https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf)")
    if st.button("Comparer avec la table DGI 2022", key="rh_test_dgi",
                 on_click=_mark_rh_activity):
        fresh = _rh_access()
        if fresh is None or fresh[0] != user_role or fresh[2] is not True:
            st.error("Droit Paie absent, révoqué ou non vérifiable.")
            return
        from core.simulation_paie_dgi import comparaison_dgi_2022
        simulation = comparaison_dgi_2022(chosen)
        st.warning("SIMULATION DOCUMENTAIRE : résultat non qualifié pour une paie réelle, aucun bulletin enregistré.")
        st.metric("Brut fictif DGI (DZD)", f"{simulation['brut']:.2f}")
        st.metric("Cotisation salariale fictive à 9 % (DZD)", f"{simulation['cotisation_salarie']:.2f}")
        st.metric("Assiette IRG fictive (DZD)", f"{simulation['assiette_irg']:.2f}")
        st.metric("IRG lu dans la table DGI 2022 (DZD)", f"{simulation['irg_table']:.2f}")
        st.metric("Net fictif comparatif (DZD)", f"{simulation['net']:.2f}")
        st.metric("Quote-part employeur fictive à 25 % (DZD)", f"{simulation['cotisation_employeur']:.2f}")
        st.caption("La quote-part employeur affichée ne couvre pas nécessairement toutes les contributions. Pas de prime ni autre retenue ; aucune écriture.")



def _preflight_paie_tab(user_role: str) -> None:
    """Diagnostic des règles IRG/CNAS ; n'émet aucune fiche de paie."""
    st.subheader("Préparation des références IRG et CNAS", help=topic_help("rh.pae"))
    show_context_help(st, "rh.pae")
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
