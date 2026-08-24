"""
Interface utilisateur du module Ventes.
Fusion du module Facturation (Avoirs, Remises, Timbre fiscal).
Intègre la génération unifiée de PDF, le lien avec les Stocks, et le cycle de vie (Brouillon/Valide/Annule).
"""
import streamlit as st
import pandas as pd
from config.roles import has_permission
from modules.ventes.service import (
    create_facture_brouillon,
    valider_facture,
    annuler_facture,
    get_factures,
    calculer_montants_facture
)
from modules.admin.service import get_dataframe
from core.utils import get_local_now
from core.pdf_generator import generer_document_standard

def show_ventes_page():
    st.title("🧾 Ventes & Facturation")

    user_role = st.session_state.get("user", {}).get("role", "")
    can_write = has_permission(user_role, "Ventes", "ecriture")

    if "panier_vente" not in st.session_state:
        st.session_state["panier_vente"] = []

    tab1, tab2 = st.tabs(["➕ Nouveau Document", "📋 Historique & Validation"])

    df_clients = get_dataframe("Clients", only_active=True)
    df_skus = get_dataframe("SkuConditionnement", only_active=True)
    df_produits = get_dataframe("Produits", only_active=True)
    df_f = get_factures()

    # --- ONGLET 1 : CRÉATION (BROUILLON) ---
    with tab1:
        st.subheader("Préparer une Facture / Avoir (Brouillon)")

        if "last_pdf" in st.session_state and "last_doc_id" in st.session_state:
            st.success(f"✅ Document {st.session_state['last_doc_id']} enregistré en tant que brouillon !")
            st.download_button(
                label=f"📄 Télécharger {st.session_state['last_doc_id']} (PDF)",
                data=st.session_state["last_pdf"],
                file_name=f"{st.session_state['last_doc_id']}.pdf",
                mime="application/pdf",
                type="primary"
            )
            st.divider()

        if not can_write:
            st.info("🔒 Mode lecture seule.")
        elif df_clients.empty or df_skus.empty or df_produits.empty:
            st.warning("Veuillez configurer des Clients, Produits et SKU actifs dans l'Administration.")
        else:
            c_cli, c_ech, c_type, c_orig = st.columns(4)
            liste_clients = {row["client_id"]: f"{row['client_id']} - {row['nom']}" for _, row in df_clients.iterrows()}
            client_choisi = c_cli.selectbox("Client", options=list(liste_clients.keys()), format_func=lambda x: liste_clients[x])
            date_echeance = c_ech.date_input("Date d'échéance")
            type_doc = c_type.selectbox("Type de document", ["FactureClient", "FactureAvoir"])
            is_avoir = (type_doc == "FactureAvoir")

            facture_origine_id = ""
            if is_avoir:
                if not df_f.empty and "type_facture" in df_f.columns:
                    df_factures_clients = df_f[df_f["type_facture"] == "FactureClient"]
                    liste_facs = df_factures_clients["facture_id"].tolist()
                    facture_origine_id = c_orig.selectbox("Facture d'origine", [""] + liste_facs)
                else:
                    c_orig.info("Aucune facture passée.")

            st.markdown("**Panier de produits :**")
            with st.expander("➕ Ajouter un produit", expanded=True):
                c_sku, c_qte, c_prix = st.columns(3)

                dict_produits = {row["pf_id"]: row["nom"] for _, row in df_produits.iterrows()}
                liste_skus = {}
                for _, row in df_skus.iterrows():
                    nom_produit = dict_produits.get(row.get("pf_id", ""), "Produit inconnu")
                    format_val = row.get("format", "")
                    sku_id = row["sku_id"]
                    liste_skus[sku_id] = f"{nom_produit} - {format_val} ({sku_id})"

                sku_choisi = c_sku.selectbox("Produit", options=list(liste_skus.keys()), format_func=lambda x: liste_skus[x])
                prix_defaut = float(df_skus[df_skus["sku_id"] == sku_choisi]["prix_vente_defaut"].iloc[0]) if sku_choisi else 0.0

                qte = c_qte.number_input("Quantité", min_value=1.0, step=1.0)
                prix_u = c_prix.number_input("Prix unitaire HT", min_value=0.0, value=prix_defaut, step=10.0)

                st.markdown("**Remise applicable sur cet article :**")
                c_remise_type, c_remise_val, c_btn = st.columns([2, 2, 1])
                type_remise = c_remise_type.selectbox("Type de remise", ["Montant (DZD)", "Pourcentage (%)"])
                valeur_remise = c_remise_val.number_input("Valeur Remise", min_value=0.0, step=1.0)

                if c_btn.button("Ajouter au panier"):
                    remise_dzd = valeur_remise if type_remise == "Montant (DZD)" else (qte * prix_u * (valeur_remise / 100))

                    st.session_state["panier_vente"].append({
                        "sku_id": sku_choisi,
                        "nom_produit": liste_skus[sku_choisi],
                        "nom": liste_skus[sku_choisi],
                        "quantite": qte,
                        "prix_unitaire": prix_u,
                        "remise": remise_dzd,
                        "taux_tva": 0.19,
                        "total_ht": (qte * prix_u) - remise_dzd
                    })
                    st.rerun()

            if st.session_state["panier_vente"]:
                df_panier = pd.DataFrame(st.session_state["panier_vente"])
                st.dataframe(df_panier[["sku_id", "nom_produit", "quantite", "prix_unitaire", "remise", "total_ht"]], use_container_width=True)

                st.markdown("**Options de facturation globales :**")
                col_remise, col_especes = st.columns(2)
                remise_globale = col_remise.number_input("Remise globale supplémentaire (DZD)", min_value=0.0, step=100.0)
                paiement_especes = col_especes.checkbox("Paiement en espèces (Applique le timbre fiscal)")

                totaux = calculer_montants_facture(st.session_state["panier_vente"], remise_globale, paiement_especes)

                st.info(f"**Total HT Bruts:** {totaux['total_ht']:,.2f} | **Total Remises:** {totaux['total_remise']:,.2f} | **Net à Payer HT:** {totaux['net_a_payer']:,.2f} | **TVA:** {totaux['total_tva']:,.2f} | **Timbre Fiscal:** {totaux['timbre_fiscal']:,.2f} | **TTC Final:** {totaux['total_ttc']:,.2f} DZD")

                # Changement du bouton pour refléter l'action (Création de brouillon)
                if st.button("📝 Enregistrer le Brouillon", type="primary"):
                    try:
                        # Appel du nouveau service : ne déduit PAS le stock
                        doc_id = create_facture_brouillon(client_choisi, str(date_echeance), st.session_state["panier_vente"], remise_globale, paiement_especes, is_avoir, facture_origine_id)

                        client_row = df_clients[df_clients["client_id"] == client_choisi].iloc[0]
                        client_info = {
                            "nom": client_row["nom"],
                            "adresse": client_row.get("adresse", ""),
                            "telephone": client_row.get("mobile_contact", ""),
                            "nif": client_row.get("nif", ""),
                            "rc": client_row.get("rc", "")
                        }

                        params_entreprise = {
                            "entreprise_nom": "MON ENTREPRISE",
                            "entreprise_adresse": "123 Zone Industrielle",
                            "entreprise_tel": "0555 00 00 00",
                            "devise": "DZD",
                            "doc_couleur": "#0047AB",
                            "doc_footer": "SARL MON ENTREPRISE - Capital 1.000.000 DZD - RIB : 000 0000 000000 00"
                        }

                        date_jour = get_local_now().strftime("%Y-%m-%d")
                        titre_doc = "FACTURE D'AVOIR (BROUILLON)" if is_avoir else "FACTURE (BROUILLON)"

                        pdf_bytes = generer_document_standard(
                            doc_type=titre_doc,
                            doc_id=doc_id,
                            date_doc=date_jour,
                            partner_info=client_info,
                            lignes=st.session_state["panier_vente"],
                            totaux=totaux,
                            params=params_entreprise,
                            is_supplier=False
                        )

                        st.session_state["last_pdf"] = pdf_bytes
                        st.session_state["last_doc_id"] = doc_id
                        st.session_state["panier_vente"] = []

                        st.cache_data.clear()
                        st.rerun()

                    except ValueError as e:
                        st.error(f"❌ Impossible d'enregistrer le document : {e}")
                    except Exception as e:
                        st.error(f"❌ Une erreur système est survenue : {e}")

                if st.button("🗑️ Vider le panier"):
                    st.session_state["panier_vente"] = []
                    st.rerun()

    # --- ONGLET 2 : WORKFLOW (VALIDATION / ANNULATION) ---
    with tab2:
        st.subheader("📚 Registre des Factures (Workflow)")
        if not df_f.empty:
            df_f_sorted = df_f.sort_values(by="date", ascending=False)
            st.dataframe(df_f_sorted[["facture_id", "date", "client_id", "montant_ttc", "statut"]], use_container_width=True)

            if can_write:
                st.divider()
                st.markdown("### ⚡ Actions sur les documents")

                facture_choisie = st.selectbox("Sélectionnez une facture", df_f_sorted["facture_id"].tolist())

                if facture_choisie:
                    statut_actuel = df_f_sorted[df_f_sorted["facture_id"] == facture_choisie].iloc[0]["statut"]
                    st.info(f"Statut actuel : **{statut_actuel}**")

                    col1, col2 = st.columns(2)

                    with col1:
                        if statut_actuel == "BROUILLON":
                            if st.button("✅ VALIDER LA FACTURE (Déduire les stocks)", type="primary", use_container_width=True):
                                try:
                                    valider_facture(facture_choisie)
                                    st.success(f"La facture {facture_choisie} a été validée avec succès !")
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erreur de validation : {e}")
                        else:
                            st.button("✅ VALIDER LA FACTURE", disabled=True, use_container_width=True, help="Uniquement pour les brouillons.")

                    with col2:
                        if statut_actuel == "VALIDE":
                            if st.button("❌ ANNULER LA FACTURE (Réinjecter les stocks)", type="secondary", use_container_width=True):
                                try:
                                    annuler_facture(facture_choisie)
                                    st.warning(f"La facture {facture_choisie} a été annulée. Les stocks ont été réajustés.")
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erreur d'annulation : {e}")
                        else:
                            st.button("❌ ANNULER LA FACTURE", disabled=True, use_container_width=True, help="Uniquement pour les factures validées.")
        else:
            st.info("Aucun document émis pour le moment.")