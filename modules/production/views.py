"""
Interface utilisateur du module Production.
Intègre le Bilan de Masse dynamique, la gestion sécurisée des stocks,
la sélection ergonomique des OF et la déclaration d'emballage.
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.db_service import fetch_data
from modules.production.service import (
    create_recette, create_ordre_fabrication, get_recettes,
    get_ordres_fabrication, changer_statut_of, enregistrer_controle_qualite
)

def get_produits_actifs():
    df = pd.DataFrame(fetch_data("produits"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def get_mp_actives():
    df = pd.DataFrame(fetch_data("matieres_premieres"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def get_skus_actifs():
    df = pd.DataFrame(fetch_data("sku_conditionnement"))
    return df[df["actif"] == "OUI"] if not df.empty and "actif" in df.columns else pd.DataFrame()

def show_production_page():
    st.title("🏭 Production & Nomenclatures")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Production", "ecriture")

    if "panier_recette" not in st.session_state:
        st.session_state["panier_recette"] = []

    tab1, tab2, tab3 = st.tabs(["📝 Créer une Recette", "⚙️ Lancer un OF", "📊 Suivi Production"])

    df_pf = get_produits_actifs()
    df_mp = get_mp_actives()
    df_skus = get_skus_actifs()

    with tab1:
        st.subheader("Nouvelle Nomenclature (Recette du Vrac)")
        st.info("La recette concerne uniquement les composants chimiques. L'emballage sera géré au niveau du SKU.")
        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif df_pf.empty or df_mp.empty:
            st.warning("Veuillez configurer des Produits et Matières Premières actifs.")
        else:
            c_pf, c_ver, c_rend = st.columns(3)
            liste_pf = {row["pf_id"]: f"{row['pf_id']} - {row['nom']}" for _, row in df_pf.iterrows()}
            pf_choisi = c_pf.selectbox("Produit Fini Vrac", options=list(liste_pf.keys()), format_func=lambda x: liste_pf[x])
            version = c_ver.text_input("Version (ex: v1.0, Été 2024)", value="v1.0")
            rendement = c_rend.number_input("Rendement (Quantité produite par batch)", min_value=1.0, value=1000.0, step=10.0)

            instructions = st.text_area("Instructions de fabrication")

            st.markdown(f"**Nomenclature (Matières requises pour {rendement} unités de vrac) :**")
            with st.expander("➕ Ajouter un composant chimique", expanded=True):
                c_mp, c_qte, c_btn = st.columns([3, 1, 1])
                # On exclut idéalement les emballages de la recette vrac pour éviter la double déduction
                if "categorie_mp" in df_mp.columns:
                    df_mp_vrac = df_mp[df_mp["categorie_mp"] != "EMBALLAGE_CONSOMMABLE"]
                else:
                    df_mp_vrac = df_mp

                liste_mp = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_mp_vrac.iterrows()}
                mp_choisie = c_mp.selectbox("Matière Première", options=list(liste_mp.keys()), format_func=lambda x: liste_mp[x])
                qte_requise = c_qte.number_input("Quantité requise", min_value=0.01, step=1.0)

                if c_btn.button("Ajouter à la recette"):
                    st.session_state["panier_recette"].append({
                        "mp_id": mp_choisie,
                        "nom_mp": liste_mp[mp_choisie],
                        "quantite_par_unite": qte_requise
                    })
                    st.rerun()

            if st.session_state["panier_recette"]:
                st.dataframe(pd.DataFrame(st.session_state["panier_recette"])[["mp_id", "nom_mp", "quantite_par_unite"]], use_container_width=True)

                # --- BILAN DE MASSE ---
                st.markdown("### ⚖️ Bilan de Masse (Cohérence de la recette)")
                somme_ingredients = sum(item["quantite_par_unite"] for item in st.session_state["panier_recette"])
                ecart = somme_ingredients - rendement

                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Somme des Ingrédients", f"{somme_ingredients:.2f}")
                col_m2.metric("Rendement Attendu", f"{rendement:.2f}")

                btn_desactive = False
                if ecart == 0:
                    col_m3.metric("Écart", "0.00", "Équilibré")
                    st.success("✅ La recette est parfaitement équilibrée.")
                elif ecart > 0:
                    col_m3.metric("Surplus (Perte technique)", f"+{ecart:.2f}", delta_color="inverse")
                    st.warning(f"⚠️ La somme des matières dépasse le rendement de {ecart:.2f}. C'est acceptable si vous prévoyez une évaporation/perte.")
                else:
                    col_m3.metric("Manquant", f"{ecart:.2f}", delta_color="inverse")
                    st.error(f"❌ Il manque {-ecart:.2f} de matières pour atteindre le rendement visé. Veuillez ajuster les quantités.")
                    btn_desactive = True

                c_action1, c_action2 = st.columns(2)
                if c_action1.button("🗑️ Vider le panier"):
                    st.session_state["panier_recette"] = []
                    st.rerun()

                if c_action2.button("✅ Sauvegarder la recette", type="primary", disabled=btn_desactive):
                    recette_id = create_recette(pf_choisi, version, rendement, instructions, st.session_state["panier_recette"])
                    st.session_state["panier_recette"] = []
                    st.success(f"Recette {recette_id} validée !")
                    st.cache_data.clear()
                    st.rerun()

    with tab2:
        st.subheader("Lancer un Ordre de Fabrication (OF)")
        df_recettes = get_recettes()

        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif df_recettes.empty:
            st.warning("Aucune recette existante.")
        elif df_skus.empty or df_pf.empty:
            st.warning("Veuillez configurer des Produits et SKU actifs.")
        else:
            # 1. Sélection du SKU
            dict_produits = {row["pf_id"]: row["nom"] for _, row in df_pf.iterrows()}
            liste_skus = {}
            for _, row in df_skus.iterrows():
                nom_produit = dict_produits.get(row.get("pf_id", ""), "Produit inconnu")
                format_val = row.get("format", "")
                sku_id = row["sku_id"]
                liste_skus[sku_id] = f"{nom_produit} - {format_val} ({sku_id})"

            sku_choisi = st.selectbox("1. Produit fini à conditionner (SKU)", options=list(liste_skus.keys()), format_func=lambda x: liste_skus[x])

            # Identification du pf_id rattaché au SKU choisi
            pf_id_cible = df_skus[df_skus["sku_id"] == sku_choisi]["pf_id"].iloc[0] if sku_choisi else None

            # Filtrage des recettes correspondantes
            recettes_compatibles = {}
            if pf_id_cible:
                df_recettes_pf = df_recettes[(df_recettes["pf_id"] == pf_id_cible) & (df_recettes["actif"] == "OUI")]
                for _, row in df_recettes_pf.iterrows():
                    recettes_compatibles[row["recette_id"]] = f"Version {row['version']} (Rendement: {row['rendement_unite']})"

            if not recettes_compatibles:
                st.error("❌ Aucune recette active trouvée pour ce produit. Veuillez créer une recette d'abord.")
            else:
                # 2. Formulaire des paramètres de production
                with st.form("form_of"):
                    st.markdown("**2. Détails de l'Ordre de Fabrication**")
                    c1, c2 = st.columns(2)
                    recette_choisie = c1.selectbox("Recette à utiliser", options=list(recettes_compatibles.keys()), format_func=lambda x: recettes_compatibles[x])
                    quantite = c2.number_input("Unités prévues (ex: 40 sacs)", min_value=1.0, step=1.0)

                    c3, c4 = st.columns(2)
                    date_planif = c3.date_input("Date planifiée")
                    notes = c4.text_input("Notes de fabrication")

                    if st.form_submit_button("🚀 Lancer l'OF", type="primary"):
                        if recette_choisie and sku_choisi:
                            of_id = create_ordre_fabrication(pf_id_cible, recette_choisie, sku_choisi, quantite, str(date_planif), notes)
                            st.success(f"OF {of_id} généré avec succès !")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Veuillez sélectionner une recette et un SKU valides.")

    with tab3:
        st.subheader("Suivi et Exécution des OF")
        df_ofs = get_ordres_fabrication()

        if df_ofs.empty:
            st.info("Aucun Ordre de Fabrication en cours.")
        else:
            st.dataframe(df_ofs.sort_values(by="date_planification", ascending=False), use_container_width=True)

            st.divider()
            st.subheader("⚙️ Agir sur un OF")

            ofs_actifs = df_ofs[~df_ofs["statut"].isin(["TERMINE", "REJETE"])]

            if not can_write:
                st.warning("🔒 Mode lecture seule. Vous ne pouvez pas faire progresser les OF.")
            elif ofs_actifs.empty:
                st.success("Tous les OF sont terminés !")
            else:
                liste_ofs = {row["of_id"]: f"{row['of_id']} - {row['statut']}" for _, row in ofs_actifs.iterrows()}
                of_choisi = st.selectbox("Sélectionner un OF à traiter", options=list(liste_ofs.keys()), format_func=lambda x: liste_ofs[x])

                if of_choisi:
                    of_data = ofs_actifs[ofs_actifs["of_id"] == of_choisi].iloc[0]
                    statut_actuel = of_data["statut"]
                    qte_prevue = float(of_data["quantite_prevue"])
                    sku_associe = of_data["sku_id"]

                    st.write(f"**Statut actuel :** `{statut_actuel}` | **Quantité prévue :** {qte_prevue} unités de {sku_associe}")

                    if statut_actuel == "PLANIFIE":
                        if st.button("▶️ Lancer la production (Passer EN COURS)", type="primary"):
                            changer_statut_of(of_choisi, "EN_COURS")
                            st.success("L'OF est maintenant en cours de production.")
                            st.cache_data.clear()
                            st.rerun()

                    elif statut_actuel == "EN_COURS":
                        if st.button("⏸️ Déclarer production terminée (Passer en CONTRÔLE QUALITÉ)", type="primary"):
                            changer_statut_of(of_choisi, "CONTROLE_QUALITE")
                            st.success("L'OF est prêt pour le contrôle qualité.")
                            st.cache_data.clear()
                            st.rerun()

                    elif statut_actuel == "CONTROLE_QUALITE":
                        st.markdown("### 🔬 Formulaire de Clôture & Contrôle Qualité")

                        # Récupération de l'emballage lié au SKU
                        emballage_id = ""
                        nom_emballage = "Aucun emballage configuré sur ce SKU"
                        if not df_skus.empty and "emballage_mp_id" in df_skus.columns:
                            sku_info = df_skus[df_skus["sku_id"] == sku_associe]
                            if not sku_info.empty:
                                emballage_id = str(sku_info.iloc[0].get("emballage_mp_id", ""))
                                if emballage_id and emballage_id.strip() and emballage_id != "nan":
                                    nom_emballage = f"Emballage: {emballage_id}"
                                    if not df_mp.empty:
                                        mp_info = df_mp[df_mp["mp_id"] == emballage_id]
                                        if not mp_info.empty:
                                            nom_emballage = f"{mp_info.iloc[0]['nom']} ({emballage_id})"
                                else:
                                    emballage_id = ""

                        with st.form("form_cq"):
                            st.markdown("**1. Résultat qualité**")
                            conforme = st.radio("Le produit est-il conforme ?", ["OUI", "NON"])
                            remarques = st.text_area("Remarques / Motif de rejet")
                            controleur = st.text_input("Nom du contrôleur")

                            st.markdown("**2. Déclaration logistique (Si Conforme)**")
                            st.info("Déclarez les quantités réelles pour ajuster précisément les stocks.")
                            c1, c2 = st.columns(2)
                            qte_produite = c1.number_input("Quantité réellement produite (SKU)", min_value=0.0, max_value=float(qte_prevue*1.5), value=float(qte_prevue))

                            st.write(f"*{nom_emballage}*")
                            qte_emballage = c2.number_input("Quantité d'emballages consommée (pertes incluses)", min_value=0.0, value=float(qte_prevue) if emballage_id else 0.0, disabled=not emballage_id)

                            submit = st.form_submit_button("Valider le Contrôle & Clôturer l'OF", type="primary")

                            if submit:
                                if not controleur:
                                    st.error("Le nom du contrôleur est obligatoire.")
                                else:
                                    try:
                                        enregistrer_controle_qualite(
                                            of_choisi, conforme, remarques, controleur,
                                            qte_produite, emballage_id, qte_emballage
                                        )
                                        if conforme == "OUI":
                                            st.success("✅ OF Clôturé avec succès. Vrac et Emballages ont été déduits des stocks !")
                                        else:
                                            st.error("❌ OF Rejeté. Aucun mouvement de stock n'a été généré.")
                                        st.cache_data.clear()
                                        st.rerun()
                                    except ValueError as ve:
                                        st.error(f"❌ Impossible de clôturer l'OF : {ve}")
                                    except Exception as e:
                                        st.error(f"❌ Une erreur système est survenue : {e}")