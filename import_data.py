"""
Script d'importation globale des listes de référence dans Supabase.
Spécialisé pour l'industrie des Mortiers, Adjuvants et Peintures en Algérie.
"""
from core.db_service import get_supabase_client

def importer_referentiels():
    print("⏳ Préparation et injection des données expertes dans Supabase...")
    supabase = get_supabase_client()
    donnees = []

    def ajouter_liste(liste_code, elements, parent_prefix=""):
        for index, (val_code, val_lib) in enumerate(elements):
            ordre = index + 1
            parent_code = f"{parent_prefix}:{val_code}" if parent_prefix else None
            donnees.append({
                "liste_code": liste_code,
                "valeur_code": val_code,
                "valeur_libelle": val_lib,
                "parent_code": parent_code,
                "ordre": ordre,
                "actif": "OUI"
            })

    def ajouter_wilayas(liste_code, elements, parent_code):
        for index, (val_code, val_lib) in enumerate(elements):
            ordre = index + 1
            donnees.append({
                "liste_code": liste_code,
                "valeur_code": val_code,
                "valeur_libelle": val_lib,
                "parent_code": parent_code,
                "ordre": ordre,
                "actif": "OUI"
            })

    # --- 1. CATÉGORIES CLIENTS ---
    ajouter_liste("CAT_CLIENT", [
        ("DISTRIB", "Distributeur / Grossiste Principal"),
        ("DROGUERIE", "Droguerie / Quincaillerie (Détaillant)"),
        ("ENT_BTP", "Entreprise de Réalisation (BTP / Génie Civil)"),
        ("PROMO", "Promoteur Immobilier"),
        ("APPLIC", "Applicateur Agréé / Artisan (Peintre, Façadier, Carreleur)"),
        ("CENTRALE", "Centrale à Béton (Client Adjuvants)"),
        ("MARCHE_PUB", "Marché Public / Institutionnel"),
        ("B2C", "Client Final (Particulier)")
    ])

    # --- 2. CATÉGORIES MATIÈRES PREMIÈRES ---
    ajouter_liste("CAT_MP", [
        ("LIANT_HYD", "Liants Hydrauliques (Ciment, Chaux, Plâtre)"),
        ("CHARGE_MIN", "Charges Minérales (Carbonate, Sable siliceux, Talc, Baryte)"),
        ("RESINE_AQ", "Résines & Dispersions Aqueuses (Acrylique, Vinylique, VAE)"),
        ("RESINE_SOLV", "Résines Solvantées (Alkyde, Époxy, Polyuréthane)"),
        ("ADD_RHEO", "Additifs Rhéologiques (Éthers de cellulose, HPMC, HEC)"),
        ("ADD_BETO", "Additifs Béton/Mortier (Superplastifiants PCE/SNF)"),
        ("PIGMENT_BL", "Pigments Blancs (Dioxyde de Titane - TiO2)"),
        ("PIGMENT_COL", "Pigments Colorés (Oxydes de fer)"),
        ("SOLVANT", "Solvants & Coalescents (White Spirit, Texanol)"),
        ("BIOCIDE", "Biocides & Conservateurs"),
        ("AGENT_SURF", "Agents de Surface (Anti-mousse, Dispersants)"),
        ("EMBALLAGE", "Emballages (Sacs, Seaux, Fûts, IBC, Palettes)")
    ])

    # --- 3. CATÉGORIES PRODUITS FINIS ---
    ajouter_liste("CAT_PF", [
        ("MORT_COLLE", "Mortiers Colles (C1, C2, C2TE...)"),
        ("MORT_JOINTS", "Mortiers de Jointoiement"),
        ("END_FACADE", "Enduits de Façade (Monocouche, RPE)"),
        ("END_LISS", "Enduits de Lissage & Rebouchage"),
        ("MORT_TECH", "Mortiers Techniques (Réparation, Ragréage)"),
        ("ADJ_PLAST", "Adjuvants : Plastifiants & Superplastifiants"),
        ("ADJ_PRISE", "Adjuvants : Accélérateurs & Retardateurs"),
        ("ADJ_HYDRO", "Adjuvants : Hydrofuges & Entraîneurs d'air"),
        ("ADJ_CURE", "Adjuvants : Produits de cure & Décoffrants"),
        ("PEINT_INT", "Peintures Décoratives Intérieures"),
        ("PEINT_EXT", "Peintures Extérieures (Façade, Pliolite)"),
        ("PEINT_TECH", "Peintures Techniques (Époxy, Sol, Antirouille)"),
        ("ETANCHEITE", "Produits d'Étanchéité"),
        ("PRIMAIRE", "Primaires & Sous-couches")
    ])

    # --- 4. UNITÉS DE MESURE ---
    ajouter_liste("UNITE_MESURE", [
        ("KG", "Kilogramme (Kg)"), ("T", "Tonne (T)"), ("G", "Gramme (g)"),
        ("L", "Litre (L)"), ("ML", "Millilitre (ml)"),
        ("U", "Unité"), ("SAC", "Sac"), ("SEAU", "Seau"), ("FUT", "Fût"),
        ("IBC", "Cuve IBC (1000L)"), ("PAL", "Palette"), ("M", "Mètre")
    ])

    # --- 5. CODES SH (HS CODES DOUANES) ---
    ajouter_liste("HS_CODE", [
        ("250510", "2505.10 - Sables siliceux et quartzeux"),
        ("252220", "2522.20 - Chaux éteinte"),
        ("252329", "2523.29 - Ciments Portland"),
        ("253090", "2530.90 - Carbonate de calcium naturel"),
        ("282110", "2821.10 - Oxydes et hydroxydes de fer"),
        ("283650", "2836.50 - Carbonate de calcium synthétique"),
        ("291816", "2918.16 - Gluconate de sodium"),
        ("320611", "3206.11 - Dioxyde de titane (TiO2)"),
        ("320649", "3206.49 - Autres matières colorantes"),
        ("320820", "3208.20 - Peintures non aqueuses"),
        ("320910", "3209.10 - Peintures aqueuses"),
        ("381600", "3816.00 - Ciments et mortiers réfractaires"),
        ("382440", "3824.40 - Additifs pour ciments et bétons"),
        ("382450", "3824.50 - Mortiers non réfractaires"),
        ("390529", "3905.29 - Poudres VAE / Acétate de vinyle"),
        ("390690", "3906.90 - Résines acryliques"),
        ("391239", "3912.39 - Éthers de cellulose (HPMC, HEC)"),
        ("392321", "3923.21 - Sacs en polymères d'éthylène")
    ])

    # --- 6. PAYS ---
    ajouter_liste("PAYS", [
        ("DZ", "Algérie"), ("CN", "Chine"), ("TR", "Turquie"), ("IT", "Italie"),
        ("FR", "France"), ("ES", "Espagne"), ("DE", "Allemagne"), ("AE", "Émirats Arabes Unis"),
        ("SA", "Arabie Saoudite"), ("IN", "Inde"), ("EG", "Égypte"), ("TN", "Tunisie"),
        ("MA", "Maroc"), ("PT", "Portugal"), ("BE", "Belgique"), ("KR", "Corée du Sud")
    ])

    # --- 7. WILAYAS (58 Wilayas) ---
    ajouter_wilayas("WILAYA", [
        ("01", "01 - Adrar"), ("02", "02 - Chlef"), ("03", "03 - Laghouat"),
        ("04", "04 - Oum El Bouaghi"), ("05", "05 - Batna"), ("06", "06 - Béjaïa"),
        ("07", "07 - Biskra"), ("08", "08 - Béchar"), ("09", "09 - Blida"),
        ("10", "10 - Bouira"), ("11", "11 - Tamanrasset"), ("12", "12 - Tébessa"),
        ("13", "13 - Tlemcen"), ("14", "14 - Tiaret"), ("15", "15 - Tizi Ouzou"),
        ("16", "16 - Alger"), ("17", "17 - Djelfa"), ("18", "18 - Jijel"),
        ("19", "19 - Sétif"), ("20", "20 - Saïda"), ("21", "21 - Skikda"),
        ("22", "22 - Sidi Bel Abbès"), ("23", "23 - Annaba"), ("24", "24 - Guelma"),
        ("25", "25 - Constantine"), ("26", "26 - Médéa"), ("27", "27 - Mostaganem"),
        ("28", "28 - M'Sila"), ("29", "29 - Mascara"), ("30", "30 - Ouargla"),
        ("31", "31 - Oran"), ("32", "32 - El Bayadh"), ("33", "33 - Illizi"),
        ("34", "34 - Bordj Bou Arréridj"), ("35", "35 - Boumerdès"), ("36", "36 - El Tarf"),
        ("37", "37 - Tindouf"), ("38", "38 - Tissemsilt"), ("39", "39 - El Oued"),
        ("40", "40 - Khenchela"), ("41", "41 - Souk Ahras"), ("42", "42 - Tipaza"),
        ("43", "43 - Mila"), ("44", "44 - Aïn Defla"), ("45", "45 - Naâma"),
        ("46", "46 - Aïn Témouchent"), ("47", "47 - Ghardaïa"), ("48", "48 - Relizane"),
        ("49", "49 - Timimoun"), ("50", "50 - Bordj Badji Mokhtar"), ("51", "51 - Ouled Djellal"),
        ("52", "52 - Béni Abbès"), ("53", "53 - In Salah"), ("54", "54 - In Guezzam"),
        ("55", "55 - Touggourt"), ("56", "56 - Djanet"), ("57", "57 - El M'Ghair"),
        ("58", "58 - El Meniaa")
    ], parent_code="PAYS:DZ")

    # --- 8. FINANCES & CRM ---
    ajouter_liste("DEVISE", [
        ("DZD", "Dinar Algérien (DZD)"), ("EUR", "Euro (€)"),
        ("USD", "Dollar Américain ($)"), ("CNY", "Yuan Chinois (¥)")
    ])

    ajouter_liste("MODE_PAIEMENT", [
        ("VIREMENT", "Virement Bancaire"), ("CHEQUE", "Chèque Bancaire"),
        ("ESPECES", "Espèces"), ("LC", "Lettre de Crédit (Credoc)"),
        ("REMISE_DOC", "Remise Documentaire (Remdoc)")
    ])

    ajouter_liste("CONDITION_PAIEMENT", [
        ("AVANCE_100", "100% à la commande"), ("IMMEDIAT", "Paiement à la livraison"),
        ("NET_30", "Net 30 jours"), ("NET_60", "Net 60 jours"), ("NET_90", "Net 90 jours")
    ])

    print(f"🚀 Insertion de {len(donnees)} lignes dans Supabase...")
    try:
        # Nettoyage préventif des anciennes données de test
        supabase.table("listes_reference").delete().neq("id", 0).execute()
        # Insertion groupée des données expertes
        supabase.table("listes_reference").insert(donnees).execute()
        print("✅ Importation dans Supabase terminée avec succès !")
    except Exception as e:
        print(f"❌ Erreur lors de l'insertion Supabase : {e}")

if __name__ == "__main__":
    importer_referentiels()