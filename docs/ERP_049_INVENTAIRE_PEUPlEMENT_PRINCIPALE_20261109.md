# ERP-049 — Inventaire de peuplement, Supabase PRINCIPAL
Date : 2026-11-09. Base : erp-mortier `wenydirqtmkywbxbxfal`. Base TEST : INACTIVE, non sollicitée.

## Résultat exécuté et vérifié
- 97 tables publiques inspectées ; avant l'opération 78 non vides et 19 vides ; après l'opération 81 non vides et 16 vides.
- 42 enregistrements SIM-ERP49 ajoutés dans 29 tables, sans modification/suppression des historiques.
- Script GitHub : `seeds/ERP_049_demo_metiers_additif_20261109.sql` ; transaction à blanc `BEGIN ... ROLLBACK` réussie, insertion transactionnelle `COMMIT` réussie.
- 15/15 contrôles SQL réussis : `tests/sql/erp_049_demo_verification.sql`. Rejeu idempotent avec ROLLBACK testé.
- Invariants de la principale après : 4 factures, 4 lignes de facture, 3 règlements, zéro écriture dans `ecritures_comptables`, zéro SKU fiscalement VALIDEE, 145 SKU actifs.
- Les 2 SKU prototypes et 2 recettes ajoutées restent `actif='NON'` ; aucun stock physique ni mouvement n'est créé.
- Seule la table `parametres` reçoit un marqueur TECHNIQUE ; aucun taux/paramètre réglementaire n'est inventé.
- Les coûts ajoutés portent `statut='SIMULATION'`, sans pièce comptable inventée.

## Pourquoi toutes les tables ne sont pas remplies
Certaines tables ne peuvent être alimentées correctement que par RPC métier, une authentification réelle, une véritable preuve légale ou une facture validée. Les forcer à contenir un enregistrement fictif créerait une fausse réalité comptable, juridique ou de stock. **Vide** n'est pas nécessairement un défaut de préparation.

Tables laissées vides (16) : `ecritures_comptables`, `erreurs`, `erp_finance_operations`, `erp_finance_outbox`, `erp_security_operations`, `schema_migrations`, `erp_recus_internes`, `erp_exonerations_tva_clients`, `erp_exonerations_tva_skus`, `erp_exonerations_tva_evenements`, `erp_exonerations_tva_validateurs`, `erp_exonerations_tva_operations`, `site_demandes`, `erp_cost_pool_scf_evidence`, `erp_cost_of_validation_snapshot`, `erp_sku_tva_qualifications`.

## Classification et couverture
- DEMO ajoutée (ERP-049) : 29 table(s)
- Stock / livraison : mouvements métier requis : 11 table(s)
- Finance : processus métier requis : 8 table(s)
- Référentiel existant : conserver : 3 table(s)
- Sécurité / audit : non semée : 11 table(s)
- SCF / paie : pièces authentiques requises : 10 table(s)
- Journal technique / preuve : génération par RPC : 14 table(s)
- Fiscalité / juridique : protégé : 9 table(s)
- Site web : conserver / consentement réel requis : 2 table(s)

## Inventaire complet — nombre de lignes après ERP-049
| Table publique | Lignes | Traitement |
|---|---:|---|
| `appels_offres` | 2 | DEMO ajoutée (ERP-049) |
| `audit_trail` | 1 | Sécurité / audit : non semée |
| `bons_livraison` | 3 | Stock / livraison : mouvements métier requis |
| `bons_reception` | 4 | Stock / livraison : mouvements métier requis |
| `clients` | 12 | DEMO ajoutée (ERP-049) |
| `commandes_achats` | 5 | DEMO ajoutée (ERP-049) |
| `commandes_ventes` | 5 | DEMO ajoutée (ERP-049) |
| `comptes` | 3 | Finance : processus métier requis |
| `compteurs` | 12 | Référentiel existant : conserver |
| `consommations_of` | 5 | Stock / livraison : mouvements métier requis |
| `contrats` | 2 | DEMO ajoutée (ERP-049) |
| `controle_qualite` | 3 | Stock / livraison : mouvements métier requis |
| `demandes_conges` | 5 | DEMO ajoutée (ERP-049) |
| `devis` | 3 | DEMO ajoutée (ERP-049) |
| `ecritures_comptables` | 0 | SCF / paie : pièces authentiques requises |
| `employes` | 14 | DEMO ajoutée (ERP-049) |
| `erp_auth_attempt_tokens` | 52 | Sécurité / audit : non semée |
| `erp_auth_rate_secret` | 1 | Sécurité / audit : non semée |
| `erp_auth_rate_state` | 1 | Sécurité / audit : non semée |
| `erp_cost_drivers` | 1 | DEMO ajoutée (ERP-049) |
| `erp_cost_natures` | 6 | Référentiel existant : conserver |
| `erp_cost_of_validation_snapshot` | 0 | Journal technique / preuve : génération par RPC |
| `erp_cost_periods` | 3 | DEMO ajoutée (ERP-049) |
| `erp_cost_pool_scf_evidence` | 0 | Journal technique / preuve : génération par RPC |
| `erp_cost_pools` | 1 | DEMO ajoutée (ERP-049) |
| `erp_exonerations_tva_clients` | 0 | Fiscalité / juridique : protégé |
| `erp_exonerations_tva_evenements` | 0 | Fiscalité / juridique : protégé |
| `erp_exonerations_tva_operations` | 0 | Fiscalité / juridique : protégé |
| `erp_exonerations_tva_skus` | 0 | Fiscalité / juridique : protégé |
| `erp_exonerations_tva_validateurs` | 0 | Fiscalité / juridique : protégé |
| `erp_finance_operations` | 0 | Journal technique / preuve : génération par RPC |
| `erp_finance_outbox` | 0 | Journal technique / preuve : génération par RPC |
| `erp_of_closures` | 1 | Journal technique / preuve : génération par RPC |
| `erp_of_outbox` | 1 | Journal technique / preuve : génération par RPC |
| `erp_production_creations` | 2 | Journal technique / preuve : génération par RPC |
| `erp_purchase_operations` | 3 | Journal technique / preuve : génération par RPC |
| `erp_purchase_outbox` | 3 | Journal technique / preuve : génération par RPC |
| `erp_recus_internes` | 0 | Finance : processus métier requis |
| `erp_sales_operations` | 3 | Journal technique / preuve : génération par RPC |
| `erp_sales_order_creations` | 1 | Journal technique / preuve : génération par RPC |
| `erp_sales_outbox` | 3 | Journal technique / preuve : génération par RPC |
| `erp_security_authorities` | 1 | Sécurité / audit : non semée |
| `erp_security_operations` | 0 | Sécurité / audit : non semée |
| `erp_sku_fiscalite` | 2 | Fiscalité / juridique : protégé |
| `erp_sku_tva_qualifications` | 0 | Fiscalité / juridique : protégé |
| `erp_stock_operations` | 10 | Journal technique / preuve : génération par RPC |
| `erp_stock_outbox` | 10 | Journal technique / preuve : génération par RPC |
| `erreurs` | 0 | Sécurité / audit : non semée |
| `factures` | 4 | Finance : processus métier requis |
| `factures_fournisseurs` | 2 | Finance : processus métier requis |
| `feuilles_de_temps` | 3 | DEMO ajoutée (ERP-049) |
| `fiches_de_paie` | 1 | SCF / paie : pièces authentiques requises |
| `fournisseurs` | 11 | DEMO ajoutée (ERP-049) |
| `grilles_tarifaires` | 2 | DEMO ajoutée (ERP-049) |
| `interactions` | 4 | DEMO ajoutée (ERP-049) |
| `lettrage` | 2 | Finance : processus métier requis |
| `lignes_achats` | 4 | DEMO ajoutée (ERP-049) |
| `lignes_bons_livraison` | 3 | Stock / livraison : mouvements métier requis |
| `lignes_bons_reception` | 4 | Stock / livraison : mouvements métier requis |
| `lignes_commande_ventes` | 5 | DEMO ajoutée (ERP-049) |
| `lignes_devis` | 3 | DEMO ajoutée (ERP-049) |
| `lignes_facture` | 4 | Finance : processus métier requis |
| `lignes_factures_fournisseurs` | 2 | Finance : processus métier requis |
| `lignes_recette` | 11 | DEMO ajoutée (ERP-049) |
| `listes_reference` | 152 | Référentiel existant : conserver |
| `logs` | 3 | Sécurité / audit : non semée |
| `lots` | 10 | Stock / livraison : mouvements métier requis |
| `matieres_premieres` | 126 | DEMO ajoutée (ERP-049) |
| `mouvements` | 12 | Stock / livraison : mouvements métier requis |
| `mouvements_pf` | 6 | Stock / livraison : mouvements métier requis |
| `ordres_fabrication` | 5 | DEMO ajoutée (ERP-049) |
| `paie_bulletins_v2` | 1 | SCF / paie : pièces authentiques requises |
| `paie_lignes_v2` | 1 | SCF / paie : pièces authentiques requises |
| `paie_periodes_v2` | 1 | SCF / paie : pièces authentiques requises |
| `parametres` | 1 | DEMO ajoutée (ERP-049) |
| `parametres_reglementaires` | 5 | Fiscalité / juridique : protégé |
| `permissions` | 9 | Sécurité / audit : non semée |
| `pipeline` | 5 | DEMO ajoutée (ERP-049) |
| `produits` | 61 | DEMO ajoutée (ERP-049) |
| `projets` | 3 | DEMO ajoutée (ERP-049) |
| `recettes` | 6 | DEMO ajoutée (ERP-049) |
| `reglements` | 3 | Finance : processus métier requis |
| `regles_reglementaires` | 1 | Fiscalité / juridique : protégé |
| `reponses_appels_offres` | 2 | DEMO ajoutée (ERP-049) |
| `scf_exercices` | 1 | SCF / paie : pièces authentiques requises |
| `scf_journaux` | 1 | SCF / paie : pièces authentiques requises |
| `scf_lignes` | 2 | SCF / paie : pièces authentiques requises |
| `scf_pieces` | 1 | SCF / paie : pièces authentiques requises |
| `scf_plan_comptes` | 27 | SCF / paie : pièces authentiques requises |
| `schema_migrations` | 0 | Sécurité / audit : non semée |
| `site_demandes` | 0 | Site web : conserver / consentement réel requis |
| `site_produits` | 50 | Site web : conserver / consentement réel requis |
| `sku_conditionnement` | 154 | DEMO ajoutée (ERP-049) |
| `stock_actuel` | 114 | Stock / livraison : mouvements métier requis |
| `stock_actuel_pf` | 146 | Stock / livraison : mouvements métier requis |
| `taches` | 3 | DEMO ajoutée (ERP-049) |
| `users` | 1 | Sécurité / audit : non semée |

## Prochaine suite de tests
1. Exécuter en lecture seule `tests/sql/erp_049_demo_verification.sql` sur le principal et conserver la sortie.
2. Tester l'affichage authentifié CRM, Achats, Ventes, RH, Production, Projets, Coûts avec préfixe `SIM-ERP49` ; aucune vente fiscale réelle sur les SKU non qualifiés.
3. Tester les transactions atomiques avec les RPC autorisées ; ne jamais ajouter à la main des lignes dans les caches de stock, opérations, outbox ou journaux.
4. Ne pas qualifier fictivement les SKU pour débloquer des factures ; l'ERP-048 n'a pas encore remplacé l'ancien moteur.
5. Vérifier le SHA réellement déployé Streamlit et la CI de `main` ; code GitHub n'est pas preuve de déploiement public.
6. Validation par un expert-comptable algérien obligatoire avant usage réglementaire réel.

## Notes
Cette opération n'a appliqué aucune migration de schéma, n'a pas touché aux RLS/GRANT, n'a pas réactivé la base TEST.
