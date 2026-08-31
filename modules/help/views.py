"""
Module d'Aide et Documentation de l'ERP.
Accessible à tous les utilisateurs. Format "Documentation" avec menu latéral.
"""
import streamlit as st


def show_help_page():
    st.title("📚 Guide d'Utilisation de l'ERP")
    st.markdown(
        "Bienvenue dans le manuel d'utilisation. Sélectionnez une rubrique dans le menu de gauche pour consulter les procédures détaillées.")

    # Sous-menu latéral spécifique à la documentation
    st.sidebar.markdown("---")
    st.sidebar.subheader("📑 Navigation Documentaire")
    rubrique = st.sidebar.radio(
        "Choisissez un module :",
        [
            "🏠 Introduction",
            "⚙️ Administration & Référentiels",
            "🏢 Achats & Fournisseurs",
            "📦 Stocks & Magasin",
            "🏭 Production",
            "🤝 Ventes & CRM",
            "💰 Finance & Trésorerie"
        ]
    )

    st.divider()

    if rubrique == "🏠 Introduction":
        st.header("Introduction")
        st.markdown("""
        Cet ERP est conçu pour centraliser la gestion de votre entreprise de production (Mortiers, Peintures, Adjuvants). 
        Il fonctionne en temps réel et assure une traçabilité totale de vos opérations.

        **Principes de base :**
        * **Sauvegarde automatique :** Toute action validée est instantanément enregistrée dans la base de données.
        * **Menus déroulants :** La majorité des formulaires utilisent des listes de choix. Si une option manque, elle doit être ajoutée dans le module *Administration*.
        * **Droits d'accès :** Si vous ne voyez pas un bouton ou un menu, c'est que votre profil utilisateur ne dispose pas des permissions nécessaires. Rapprochez-vous de votre administrateur.
        """)

    elif rubrique == "⚙️ Administration & Référentiels":
        st.header("⚙️ Administration & Référentiels")

        st.subheader("1. Gérer les listes de choix (Menus déroulants)")
        st.markdown("""
        Cette section permet d'alimenter toutes les listes de l'ERP (Catégories, Pays, Unités, etc.).
        1. Allez dans l'onglet **📝 Listes de choix**.
        2. Sélectionnez une liste existante ou tapez le code d'une nouvelle liste.
        3. Remplissez le code court (ex: `DZ`) et le libellé affiché (ex: `Algérie`).
        4. Cliquez sur **➕ Ajouter l'élément**. La modification est immédiate dans tout l'ERP.
        """)

        st.subheader("2. Ajouter un Produit Fini ou une Matière Première")
        st.markdown("""
        1. Ouvrez l'onglet correspondant (**🧪 Matières Premières** ou **🛍️ Produits**).
        2. Déroulez la section **➕ Nouvelle Matière Première** (ou Nouveau Produit).
        3. Renseignez obligatoirement le nom, l'unité et la catégorie.
        4. Validez. Le produit apparaît dans le tableau en dessous.
        """)

        st.subheader("3. Créer un Conditionnement (SKU)")
        st.markdown("""
        Un SKU représente la version vendable d'un produit (ex: *Sac de 25kg* ou *Seau de 20L*).
        1. Allez dans l'onglet **📦 SKU**.
        2. Sélectionnez le Produit Fini parent.
        3. Associez-lui l'emballage correspondant (la matière première de type *EMBALLAGE*).
        4. Définissez le poids net et le prix de vente par défaut.
        """)

    elif rubrique == "🏢 Achats & Fournisseurs":
        st.header("🏢 Achats & Fournisseurs")

        st.subheader("1. Créer un Bon de Commande (BC)")
        st.markdown("""
        1. Accédez au module **Achats**.
        2. Cliquez sur **Nouveau Bon de Commande**.
        3. Sélectionnez le fournisseur dans la liste.
        4. Ajoutez les articles un par un en précisant la quantité et le prix unitaire négocié.
        5. Cliquez sur **Valider la commande**. Son statut passe à *En attente de réception*.
        """)

        st.subheader("2. Réceptionner la marchandise (Bon de Réception)")
        st.markdown("""
        1. Dans la liste des commandes en cours, cliquez sur le bouton **Réceptionner** face à la commande concernée.
        2. Vérifiez les quantités réellement livrées par le transporteur.
        3. Si la quantité diffère de la commande, ajustez-la dans le champ correspondant.
        4. Validez la réception. **Attention :** Cette action met automatiquement à jour vos stocks de matières premières.
        """)

    elif rubrique == "📦 Stocks & Magasin":
        st.header("📦 Stocks & Magasin")

        st.subheader("1. Consulter l'état des stocks")
        st.markdown("""
        1. Le tableau de bord principal vous affiche les niveaux actuels.
        2. Les articles en dessous de leur seuil de sécurité sont surlignés en rouge ou apparaissent dans l'onglet **Alertes**.
        """)

        st.subheader("2. Faire un ajustement d'inventaire (Sortie/Entrée manuelle)")
        st.markdown("""
        1. Allez dans l'onglet **Ajustements**.
        2. Sélectionnez l'article concerné (Matière première ou Produit fini/SKU).
        3. Indiquez la quantité (utilisez un signe négatif `-` pour une perte, une casse ou une péremption).
        4. Saisissez obligatoirement un motif justifiant cet écart.
        5. Validez pour mettre le stock à jour.
        """)

    elif rubrique == "🏭 Production":
        st.header("🏭 Production")

        st.subheader("1. Créer un Ordre de Fabrication (OF)")
        st.markdown("""
        1. Dans le module Production, cliquez sur **Nouvel OF**.
        2. Sélectionnez la recette / formule à produire.
        3. Indiquez la quantité totale à fabriquer.
        4. Le système calcule automatiquement les besoins théoriques en matières premières.
        5. Enregistrez l'OF (statut *Planifié*).
        """)

        st.subheader("2. Clôturer un Ordre de Fabrication")
        st.markdown("""
        1. Ouvrez un OF en cours.
        2. Renseignez les quantités réellement consommées (si elles diffèrent de la théorie suite à des pertes).
        3. Validez la production.
        4. **Conséquences automatiques :** Les matières premières sont déduites du stock, et les produits finis sont ajoutés au stock, prêts à être vendus.
        """)

    elif rubrique == "🤝 Ventes & CRM":
        st.header("🤝 Ventes & CRM")

        st.subheader("1. Rédiger un Devis (Proforma)")
        st.markdown("""
        1. Allez dans l'onglet **Nouveau Devis**.
        2. Sélectionnez le client.
        3. Ajoutez les produits (SKU) au panier. Les prix par défaut s'affichent mais restent modifiables.
        4. Enregistrez. Vous pouvez désormais imprimer ou exporter le devis en PDF.
        """)

        st.subheader("2. Convertir en Facture & Bon de Livraison (BL)")
        st.markdown("""
        1. Ouvrez un devis validé par le client.
        2. Cliquez sur **Générer le Bon de Livraison**.
        3. Vérifiez les quantités expédiées. La validation du BL déduira immédiatement les articles du stock de produits finis.
        4. Une fois expédié, cliquez sur **Générer la Facture** pour transférer la pièce vers la comptabilité.
        """)

    elif rubrique == "💰 Finance & Trésorerie":
        st.header("💰 Finance & Trésorerie")

        st.subheader("1. Enregistrer un paiement client")
        st.markdown("""
        1. Allez dans l'onglet **Encaissements**.
        2. Sélectionnez la facture en attente de paiement.
        3. Indiquez le montant reçu (permet de gérer les acomptes ou paiements partiels).
        4. Précisez le mode de règlement (Virement, Chèque, Espèces) et la date.
        5. Validez. Le solde du client est mis à jour.
        """)

        st.subheader("2. Consulter les impayés")
        st.markdown("""
        1. Le tableau de bord financier vous indique la liste des factures échues non réglées.
        2. Vous pouvez filtrer par client pour préparer vos relances téléphoniques ou par email.
        """)