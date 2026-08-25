"""
Interface utilisateur de l'Administration.
Intègre le filtrage en cascade dynamique Pays -> Wilaya.
Édition directe en tableau (Inline Editing) avec menus déroulants robustes.
Gestion dynamique des listes de référence.
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from core.listes_service import get_liste, liste_to_dict
from core.db_service import fetch_data, insert_hybrid, update_hybrid
from modules.admin.service import (
    get_dataframe, add_fournisseur, add_matiere_premiere,
    add_produit, add_sku, add_client, sauvegarder_modifications,
    add_user, add_permission, get_users, get_permissions, get_audit_logs
)

# --- FALLBACKS SÉCURISÉS (Tirés de docs/schema_reference.md) ---
PAYS_FALLBACK = ["DZ", "FR", "CN", "TR", "ES", "IT", "DE", "AE", "EG", "TN", "MA", "LY", "MR", "Autre"]
WILAYA_FALLBACK = [str(i).zfill(2) for i in range(1, 59)]
CAT_CLIENT_FALLBACK = ["PARTICULIER", "PRO_BTP", "REVENDEUR", "NEGOCE", "PROMOTEUR", "ENTREPRISE_CONSTRUCTION", "MARCHE_PUBLIC", "EXPORT"]
UNITE_FALLBACK = ["Kg", "Litre", "Sac", "Palette", "Unité", "Fût", "Seau", "Tonne"]
CAT_MP_FALLBACK = ["LIANT", "GRANULAT", "ADJUVANT_CHIMIQUE", "RESINE_LIANT_POLYMERE", "PIGMENT_COLORANT", "SOLVANT", "ADDITIF_PEINTURE", "FIBRE", "EMBALLAGE_CONSOMMABLE"]
CAT_PF_FALLBACK = ["ENDUIT_MONOCOUCHE", "ENDUIT_PAREMENT", "MORTIER_SCELLEMENT", "MORTIER_REPARATION", "CHAPE_FLUIDE_AUTONIVELANTE", "RAGREAGE_AUTOLISSANT", "CIMENT_COLLE", "MORTIER_BATARD", "MORTIER_REFRACTAIRE", "MORTIER_JOINT_ASSISE", "SUPERPLASTIFIANT", "PLASTIFIANT_REDUCTEUR_EAU", "PEINTURE_BATIMENT_INTERIEUR", "PEINTURE_FACADE_EXTERIEUR", "VERNIS"]
HS_CODE_FALLBACK = ["2523.10", "2523.21", "2523.29", "2523.30", "2523.90", "2521.00", "3824.40", "3824.50", "3208", "3209", "3210", "3206", "6810"]

def get_opts(liste_code: str, fallback: list) -> list:
    """Extrait les clés de la liste de référence, ou utilise le fallback si vide."""
    res = liste_to_dict(get_liste(liste_code))
    return [str(k) for k in res.keys()] if res else fallback

def gerer_listes_reference():
    """Interface pour ajouter et modifier les catégories, pays, wilayas, etc."""
    st.subheader("⚙️ Gestion des Listes de Choix (Menus déroulants)")

    df_listes = pd.DataFrame(fetch_data("listes_reference"))

    # 1. Identifier les listes existantes
    listes_existantes = []
    if not df_listes.empty and "liste_code" in df_listes.columns:
        listes_existantes = sorted(df_listes["liste_code"].dropna().unique().tolist())

    col1, col2 = st.columns(2)
    action = col1.radio("Que voulez-vous faire ?", ["Éditer une liste existante", "Créer un nouveau type de liste"])

    liste_cible = ""
    if action == "Éditer une liste existante":
        if listes_existantes:
            liste_cible = col2.selectbox("Sélectionnez la liste", listes_existantes)
        else:
            st.info("Aucune liste configurée.")
    else:
        liste_cible = col2.text_input("Nom du code (ex: PAYS, WILAYA, CATEGORIE_CLIENT)").strip().upper()

    # 2. Affichage et Formulaire d'ajout
    if liste_cible:
        st.divider()
        st.markdown(f"### Éléments de la liste : `{liste_cible}`")

        # --- FORMULAIRE D'AJOUT ---
        with st.form(f"form_add_{liste_cible}"):
            c1, c2, c3 = st.columns([1, 2, 1])
            val_code = c1.text_input("Code court (ex: DZA, 31, VIP)")
            val_libelle = c2.text_input("Libellé affiché (ex: Algérie, Oran, Client VIP)")
            ordre = c3.number_input("Ordre d'affichage", min_value=1, value=1, step=1)

            if st.form_submit_button("➕ Ajouter l'élément", type="primary"):
                if val_code and val_libelle:
                    data_nouvel_element = {
                        "liste_code": liste_cible,
                        "parent_code": "",
                        "valeur_code": val_code,
                        "valeur_libelle": val_libelle,
                        "ordre": ordre,
                        "actif": "OUI"
                    }
                    try:
                        insert_hybrid("listes_reference", data_nouvel_element)
                        st.success(f"Élément '{val_libelle}' ajouté avec succès !")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur d'insertion : {e}")
                else:
                    st.error("Le code et le libellé sont obligatoires.")

        # --- LISTE DES ÉLÉMENTS EXISTANTS ---
        if not df_listes.empty and "liste_code" in df_listes.columns:
            df_filtre = df_listes[df_listes["liste_code"] == liste_cible].sort_values(by="ordre")

            if not df_filtre.empty:
                st.markdown("**Éléments actuellement configurés :**")
                for _, row in df_filtre.iterrows():
                    rc1, rc2, rc3, rc4 = st.columns([1, 2, 1, 1])
                    rc1.code(row.get('valeur_code', ''))
                    rc2.write(row.get('valeur_libelle', ''))

                    statut_actuel = str(row.get("actif", "OUI")).upper()
                    nouveau_statut = rc3.selectbox(
                        "Statut",
                        ["OUI", "NON"],
                        index=0 if statut_actuel == "OUI" else 1,
                        key=f"statut_{row.get('id', row.get('valeur_code'))}"
                    )

                    if nouveau_statut != statut_actuel:
                        update_hybrid("listes_reference", "id", str(row.get('id')), {"actif": nouveau_statut})
                        st.toast(f"Statut mis à jour pour {row.get('valeur_libelle')}")
                        st.cache_data.clear()
                        st.rerun()
            else:
                st.info("Cette liste est vide.")

def render_editable_dataframe(sheet_name: str, id_col: str, can_write: bool, selectbox_cols: dict = None):
    """Génère un tableau interactif permettant l'édition directe des données avec listes de choix robustes."""
    df = get_dataframe(sheet_name)

    if df.empty or not can_write:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return

    # 1. NETTOYAGE CRITIQUE : Supprimer les "None" et "nan" qui bloquent Streamlit
    df = df.fillna("")
    df = df.replace(["None", "nan", "<NA>"], "")

    editor_key = f"editor_{sheet_name}"

    # Configuration de base
    config = {
        id_col: st.column_config.TextColumn(id_col, disabled=True),
        "actif": st.column_config.SelectboxColumn("actif", options=["OUI", "NON"])
    }

    # 2. Injection dynamique et sécurisée des menus déroulants
    if selectbox_cols:
        for col, opts in selectbox_cols.items():
            if col in df.columns:
                existing = [str(x) for x in df[col].unique() if str(x).strip() != ""]
                final_opts = [""] + sorted(list(set([str(x) for x in opts] + existing)))

                config[col] = st.column_config.SelectboxColumn(
                    col,
                    options=final_opts,
                    required=False
                )

    st.info("💡 **Astuce :** Double-cliquez sur une cellule pour la modifier. Les menus déroulants s'afficheront.")

    st.data_editor(
        df,
        key=editor_key,
        column_config=config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed"
    )

    # Capture des cellules modifiées
    changes = st.session_state[editor_key].get("edited_rows", {})

    if changes:
        st.warning(f"⚠️ {len(changes)} ligne(s) modifiée(s) en attente de sauvegarde.")
        if st.button(f"💾 Enregistrer les modifications ({sheet_name})", type="primary", key=f"save_{sheet_name}"):
            with st.spinner("Mise à jour dans Google Sheets/Supabase..."):
                success = sauvegarder_modifications(sheet_name, id_col, df, changes)
                if success:
                    st.success("Modifications enregistrées avec succès !")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Une erreur est survenue lors de l'enregistrement.")

def show_admin_page():
    st.title("⚙️ Administration & Référentiels")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Administration", "ecriture")

    if not can_write:
        st.info("🔒 Mode lecture seule : vous n'avez pas les droits d'ajout ou de modification.")

    # Chargement global des listes de références avec fallback
    pays_opts = get_opts("Pays", PAYS_FALLBACK)
    wilaya_opts = get_opts("Wilaya", WILAYA_FALLBACK)
    unite_opts = get_opts("UniteMesure", UNITE_FALLBACK)

    tab1, tab2, tab3, tab4, tab5, tab_listes = st.tabs(["👥 Clients", "🏢 Fournisseurs", "🧪 Matières Premières", "🛍️ Produits", "📦 SKU", "📝 Listes de choix"])

    # --- CLIENTS ---
    with tab1:
        st.subheader("Gestion des Clients")
        if can_write:
            with st.expander("➕ Ajouter un client"):
                st.markdown("**Informations de base**")
                c1, c2, c3 = st.columns(3)
                nom = c1.text_input("Nom de l'entreprise *", key="cli_nom")

                cat_opts = get_opts("CategorieClient", CAT_CLIENT_FALLBACK)
                cat = c2.selectbox("Catégorie", options=cat_opts, key="cli_cat")

                type_c = c3.selectbox("Type", ["Entreprise", "Particulier"], key="cli_type")

                st.markdown("**Coordonnées**")
                c4, c5, c6 = st.columns(3)

                pays = c4.selectbox("Pays", options=pays_opts, key="cli_pays")

                parent_code = f"Pays:{pays}" if pays else None
                dict_wilaya = liste_to_dict(get_liste("Wilaya", parent_code=parent_code))
                wilaya_aj = c5.selectbox("Wilaya / Région", options=list(dict_wilaya.keys()) if dict_wilaya else wilaya_opts, key="cli_wilaya")

                adresse = c6.text_input("Adresse", key="cli_adresse")

                st.markdown("**Informations Légales & Contact**")
                c7, c8, c9 = st.columns(3)
                rc = c7.text_input("Registre de Commerce (RC)", key="cli_rc")
                nif = c8.text_input("NIF", key="cli_nif")
                nis = c9.text_input("NIS", key="cli_nis")

                c10, c11, c12 = st.columns(3)
                nom_contact = c10.text_input("Nom du contact", key="cli_nom_c")
                poste_contact = c11.text_input("Poste", key="cli_poste_c")
                mobile_contact = c12.text_input("Mobile / Téléphone", key="cli_mob_c")
                email_contact = st.text_input("Email du contact", key="cli_email_c")

                if st.button("Enregistrer le client", type="primary", key="btn_save_client"):
                    if nom:
                        add_client({
                            "nom": nom, "categorie_client": cat, "type_client": type_c,
                            "pays": pays, "wilaya": wilaya_aj, "adresse": adresse,
                            "rc": rc, "nif": nif, "nis": nis,
                            "nom_contact": nom_contact, "poste_contact": poste_contact,
                            "mobile_contact": mobile_contact, "email_contact": email_contact
                        })
                        st.success(f"Client {nom} ajouté.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Le nom est obligatoire.")

        config_cli = {
            "categorie_client": get_opts("CategorieClient", CAT_CLIENT_FALLBACK),
            "type_client": ["Entreprise", "Particulier"],
            "pays": pays_opts,
            "wilaya": wilaya_opts
        }
        render_editable_dataframe("Clients", "client_id", can_write, config_cli)

    # --- FOURNISSEURS ---
    with tab2:
        st.subheader("Gestion des Fournisseurs")
        if can_write:
            with st.expander("➕ Ajouter un fournisseur"):
                st.markdown("**Informations de base**")
                c1, c2, c3 = st.columns(3)
                nom = c1.text_input("Nom du fournisseur *", key="fou_nom")
                categorie = c2.text_input("Catégorie d'achats", key="fou_cat")
                type_ent = c3.selectbox("Type d'entreprise", ["Fabricant", "Distributeur", "Grossiste", "Autre"], key="fou_type")

                st.markdown("**Coordonnées & Logistique**")
                c4, c5, c6 = st.columns(3)

                pays = c4.selectbox("Pays d'origine", options=pays_opts, key="fou_pays")

                parent_code = f"Pays:{pays}" if pays else None
                dict_wilaya = liste_to_dict(get_liste("Wilaya", parent_code=parent_code))
                wilaya_aj = c5.selectbox("Wilaya / Région", options=list(dict_wilaya.keys()) if dict_wilaya else wilaya_opts, key="fou_wilaya")

                delai = c6.number_input("Délai approvisionnement (jours)", min_value=0, step=1, key="fou_delai")

                st.markdown("**Informations Légales & Contact**")
                c7, c8, c9 = st.columns(3)
                rc = c7.text_input("Registre de Commerce (RC)", key="fou_rc")
                nif = c8.text_input("NIF", key="fou_nif")
                nis = c9.text_input("NIS", key="fou_nis")

                c10, c11, c12 = st.columns(3)
                nom_contact = c10.text_input("Nom du contact", key="fou_nom_c")
                poste_contact = c11.text_input("Poste", key="fou_poste_c")
                mobile_contact = c12.text_input("Mobile / Téléphone", key="fou_mob_c")
                email_contact = st.text_input("Email du contact", key="fou_email_c")

                if st.button("Enregistrer le fournisseur", type="primary", key="btn_save_fou"):
                    if nom:
                        add_fournisseur({
                            "nom": nom, "categorie": categorie, "type_entreprise": type_ent,
                            "pays": pays, "wilaya": wilaya_aj, "delai_appro_jours": delai,
                            "rc": rc, "nif": nif, "nis": nis,
                            "nom_contact": nom_contact, "poste_contact": poste_contact,
                            "mobile_contact": mobile_contact, "email_contact": email_contact
                        })
                        st.success("Fournisseur ajouté.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("Le nom du fournisseur est obligatoire.")

        config_fou = {
            "type_entreprise": ["Fabricant", "Distributeur", "Grossiste", "Autre"],
            "pays": pays_opts,
            "wilaya": wilaya_opts
        }
        render_editable_dataframe("Fournisseurs", "fournisseur_id", can_write, config_fou)

    # --- MATIERES PREMIERES ---
    with tab3:
        st.subheader("Matières Premières")
        if can_write:
            with st.expander("➕ Nouvelle Matière Première"):
                with st.form("form_mp"):
                    st.markdown("**Informations de base**")
                    c1, c2 = st.columns(2)
                    nom = c1.text_input("Désignation *")

                    cat_mp_opts = get_opts("CategorieMP", CAT_MP_FALLBACK)
                    cat_mp = c2.selectbox("Catégorie", options=cat_mp_opts)

                    unite = c1.selectbox("Unité de stock", options=unite_opts)
                    origine_pays = c2.selectbox("Pays d'origine", options=pays_opts)

                    st.markdown("**Gestion des Stocks & Logistique**")
                    c3, c4, c5 = st.columns(3)
                    poids_net = c3.number_input("Poids net unitaire", min_value=0.0, step=1.0)
                    stock_mini = c4.number_input("Stock minimum", min_value=0.0, step=1.0)
                    stock_maxi = c5.number_input("Stock maximum", min_value=0.0, step=1.0)

                    c6, c7 = st.columns(2)
                    duree_peremption = c6.number_input("Durée de péremption (jours)", min_value=0, step=1)

                    hs_opts = get_opts("HSCode", HS_CODE_FALLBACK)
                    hs = c7.selectbox("Code SH (Douane)", options=hs_opts)

                    taux_dedouanement = st.number_input("Taux de dédouanement (%)", min_value=0.0, max_value=100.0, step=1.0)

                    st.markdown("**Documents Techniques**")
                    lien_ft = st.text_input("Lien Fiche Technique (URL)")
                    lien_fds = st.text_input("Lien Fiche de Données de Sécurité - FDS (URL)")

                    if st.form_submit_button("Enregistrer", type="primary"):
                        if nom:
                            add_matiere_premiere({
                                "nom": nom, "categorie_mp": cat_mp, "unite_stock": unite,
                                "origine_pays": origine_pays, "duree_peremption_jours": duree_peremption,
                                "poids_net": poids_net, "stock_mini": stock_mini, "stock_maxi": stock_maxi,
                                "hs_code": hs, "taux_dedouanement": taux_dedouanement,
                                "lien_fiche_technique": lien_ft, "lien_fiche_securite": lien_fds
                            })
                            st.success("Matière première ajoutée.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("La désignation est obligatoire.")

        config_mp = {
            "categorie_mp": get_opts("CategorieMP", CAT_MP_FALLBACK),
            "unite_stock": unite_opts,
            "origine_pays": pays_opts,
            "hs_code": get_opts("HSCode", HS_CODE_FALLBACK)
        }
        render_editable_dataframe("MatieresPremieres", "mp_id", can_write, config_mp)

    # --- PRODUITS ---
    with tab4:
        st.subheader("Produits Finis")
        if can_write:
            with st.expander("➕ Nouveau Produit"):
                with st.form("form_pf"):
                    c1, c2 = st.columns(2)
                    nom = c1.text_input("Nom du Produit *")

                    cat_pf_opts = get_opts("CategoriePF", CAT_PF_FALLBACK)
                    cat_pf = c2.selectbox("Catégorie", options=cat_pf_opts)

                    unite = c1.selectbox("Unité de production", options=unite_opts)

                    if st.form_submit_button("Enregistrer", type="primary"):
                        if nom:
                            add_produit({"nom": nom, "categorie_pf": cat_pf, "unite_production": unite})
                            st.success("Produit ajouté.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Le nom du produit est obligatoire.")

        config_pf = {
            "categorie_pf": get_opts("CategoriePF", CAT_PF_FALLBACK),
            "unite_production": unite_opts
        }
        render_editable_dataframe("Produits", "pf_id", can_write, config_pf)

    # --- SKUs ---
    with tab5:
        st.subheader("Conditionnements (SKU)")
        if can_write:
            df_pf = get_dataframe("Produits", only_active=True)
            df_mp = get_dataframe("MatieresPremieres", only_active=True)

            if not df_pf.empty:
                liste_pf = {row["pf_id"]: f"{row['pf_id']} - {row['nom']}" for _, row in df_pf.iterrows()}

                if not df_mp.empty and "categorie_mp" in df_mp.columns:
                    df_emballage = df_mp[df_mp["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]
                    liste_emballage = {row["mp_id"]: f"{row['mp_id']} - {row['nom']}" for _, row in df_emballage.iterrows()}
                else:
                    liste_emballage = {}

                with st.expander("➕ Nouveau SKU"):
                    with st.form("form_sku"):
                        pf_id = st.selectbox("Produit lié", options=list(liste_pf.keys()), format_func=lambda x: liste_pf[x])

                        st.markdown("**Informations commerciales**")
                        c1, c2 = st.columns(2)
                        format_val = c1.text_input("Format (ex: Sac 25kg)")
                        prix = c2.number_input("Prix de vente défaut (DZD)", min_value=0.0, step=10.0)

                        st.markdown("**Informations techniques (Production & Stocks)**")
                        c3, c4 = st.columns(2)
                        emballage_mp_id = c3.selectbox("Emballage principal", options=[""] + list(liste_emballage.keys()), format_func=lambda x: liste_emballage.get(x, "Aucun" if x == "" else x))
                        poids_net = c4.number_input("Poids net (Kg/L)", min_value=0.01, step=1.0)

                        c5, c6 = st.columns(2)
                        unite = c5.selectbox("Unité de vente", options=unite_opts)
                        facteur = c6.number_input("Facteur de conversion (vs unité prod)", min_value=0.001, value=1.0, step=0.1)

                        if st.form_submit_button("Enregistrer", type="primary"):
                            add_sku({
                                "pf_id": pf_id, "format": format_val, "prix_vente_defaut": prix,
                                "emballage_mp_id": emballage_mp_id, "poids_net": poids_net, "unite_vente": unite,
                                "facteur_conversion": facteur
                            })
                            st.success("SKU ajouté avec succès.")
                            st.cache_data.clear()
                            st.rerun()
            else:
                st.warning("Créez d'abord un produit actif.")

        df_produits = get_dataframe("Produits")
        pf_opts = []
        if not df_produits.empty and "pf_id" in df_produits.columns:
            pf_opts = [str(x) for x in df_produits["pf_id"].dropna().unique() if str(x).strip() not in ["", "None", "nan"]]

        df_mp = get_dataframe("MatieresPremieres")
        emballage_opts = []
        if not df_mp.empty and "categorie_mp" in df_mp.columns and "mp_id" in df_mp.columns:
            emballage_opts = [str(x) for x in df_mp[df_mp["categorie_mp"] == "EMBALLAGE_CONSOMMABLE"]["mp_id"].dropna().unique()]

        config_sku = {
            "pf_id": pf_opts if pf_opts else [""],
            "emballage_mp_id": emballage_opts if emballage_opts else [""],
            "unite_vente": unite_opts
        }
        render_editable_dataframe("SkuConditionnement", "sku_id", can_write, config_sku)

    # --- LISTES DE CHOIX ---
    with tab_listes:
        if can_write:
            gerer_listes_reference()
        else:
            st.info("🔒 Mode lecture seule : vous ne pouvez pas modifier les listes.")

# ==========================================
# PAGE DE GESTION DES UTILISATEURS
# ==========================================
def show_user_management():
    """Affiche l'interface de gestion des accès, de la sécurité et des logs."""
    st.title("🔐 Sécurité & Utilisateurs")

    # Vérification des permissions
    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Administration", "ecriture")

    if not can_write:
        st.error("Vous n'avez pas les droits d'administration pour accéder à cette page.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["Créer un Utilisateur", "Définir les Permissions", "Annuaire Existant", "Piste d'Audit (Logs)"])

    # ONGLET 1 : Création de compte
    with tab1:
        st.subheader("Ajouter un nouvel accès")
        with st.form("form_add_user", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                nom = st.text_input("Nom complet de l'employé *")
                login = st.text_input("Identifiant de connexion (ex: jdupont) *")
            with col2:
                role = st.text_input("Rôle (ex: ADMIN, COMMERCIAL, MAGASINIER) *").upper()
                mdp = st.text_input("Mot de passe temporaire *", type="password")

            submit_user = st.form_submit_button("Enregistrer l'utilisateur", use_container_width=True)

            if submit_user:
                if nom and login and role and mdp:
                    try:
                        nouveau_id = add_user(nom, login, mdp, role)
                        st.success(f"Utilisateur {nom} ({nouveau_id}) créé avec succès ! Le mot de passe a été crypté.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Une erreur est survenue : {e}")
                else:
                    st.warning("Veuillez remplir tous les champs obligatoires (*).")

    # ONGLET 2 : Gestion des permissions
    with tab2:
        st.subheader("Attribuer des droits d'accès à un rôle")
        st.info("Rappel : Les statuts doivent s'écrire 'OUI' ou 'NON'.")

        with st.form("form_add_perm", clear_on_submit=True):
            role_cible = st.text_input("Rôle concerné (ex: COMMERCIAL) *").upper()

            # Liste exacte des modules
            modules_disponibles = ["Administration", "Achats", "Stocks", "Production", "Ventes", "Finance", "CRM", "RH", "Logs"]
            module_cible = st.selectbox("Module de l'ERP", modules_disponibles)

            col_l, col_e = st.columns(2)
            with col_l:
                droit_lecture = st.selectbox("Peut lire les données ?", ["OUI", "NON"], index=0)
            with col_e:
                droit_ecriture = st.selectbox("Peut modifier/créer des données ?", ["OUI", "NON"], index=1)

            submit_perm = st.form_submit_button("Ajouter la permission", use_container_width=True)

            if submit_perm:
                if role_cible:
                    try:
                        add_permission(role_cible, module_cible, droit_lecture, droit_ecriture)
                        st.success(f"La permission sur le module '{module_cible}' a été ajoutée au rôle '{role_cible}'.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Une erreur est survenue : {e}")
                else:
                    st.warning("Veuillez saisir un nom de rôle.")

    # ONGLET 3 : Consultation rapide
    with tab3:
        st.subheader("Annuaire des Utilisateurs")
        df_users = get_users()
        if not df_users.empty:
            # On masque le hash_mdp pour l'affichage pour plus de sécurité visuelle
            cols_a_afficher = [col for col in df_users.columns if col != "hash_mdp"]
            st.dataframe(df_users[cols_a_afficher], use_container_width=True, hide_index=True)
        else:
            st.write("Aucun utilisateur trouvé.")

        st.subheader("Matrice des Permissions")
        df_perms = get_permissions()
        if not df_perms.empty:
            st.dataframe(df_perms, use_container_width=True, hide_index=True)
        else:
            st.write("Aucune permission trouvée.")

    # ONGLET 4 : Piste d'audit (Logs)
    with tab4:
        st.subheader("Historique des Actions (Audit Trail)")
        st.info("Traçabilité complète et automatique des modifications de la base de données.")

        if st.button("🔄 Rafraîchir les logs"):
            st.cache_data.clear()

        df_logs = get_audit_logs()
        if not df_logs.empty:
            st.dataframe(df_logs, use_container_width=True, hide_index=True)
        else:
            st.write("Aucune activité enregistrée pour le moment.")