# Scénario fictif intégré — SIM26 — 5 novembre 2026

## Objectif
Tester en production Supabase **uniquement avec des enregistrements explicitement fictifs**, sans activer d'opération commerciale, comptable ou fiscale réelle. Complément aux **80 lignes DEMO26 déjà présentes**. Tous les identifiants de ce nouveau lot portent le préfixe `SIM26_`.

- Base cible : `wenydirqtmkywbxbxfal` — production, sans changement de schéma ni de permissions.
- Jeu intégré : **40 nouvelles lignes réparties dans 37 tables** ; total des deux jeux : **120 lignes fictives**.
- Les tables techniques/système/authentification, les référentiels fiscaux réels et les permissions ne sont **pas alimentés artificiellement**.
- Les dates métier sont du **13 au 25 octobre 2026** : pour tester les historiques dans l'interface, sélectionner octobre 2026. Les tableaux de bord de novembre ne doivent pas être interprétés comme résumant toutes les opérations fictives.
- Ne pas utiliser les factures, taux, comptes ou montants comme justificatifs ou déclarations réelles. Le taux TVA illustratif 19 % est une valeur du **scénario fictif historique**, non une vérification du droit applicable.

## Processus reliés, dans l'ordre

| Étape | Références | Données |
|---|---|---|
| Tiers et référentiels | `SIM26_FOU`, `SIM26_CLI`, `SIM26_MP`, `SIM26_PF`, `SIM26_SKU`, `SIM26_BANK` | Fournisseur, client, MP, PF, SKU, banque fictifs |
| Achat | `SIM26_PO`, `SIM26_POL` | 100 kg à 10 DZD = 1 000 DZD |
| Réception | `SIM26_GR`, `SIM26_GRL`, `SIM26_LOT_MP` | Réception conforme de 100 kg, lot tracé |
| Stock MP | `SIM26_MV_IN`, `SIM26_MV_OUT` | Entrée 100 kg, sortie fabrication 100 kg |
| Recette | `SIM26_REC`, `SIM26_RECL` | V1 fictive ; 10 kg de MP par unité |
| Fabrication | `SIM26_OF`, `SIM26_CONS` | 10 unités prévues et produites, 100 kg consommés |
| Qualité | `SIM26_QC` | Conforme = OUI |
| Stock PF | `SIM26_LOT_PF`, `SIM26_PF_IN`, `SIM26_PF_OUT` | Entrée 10 unités, sortie 10 unités |
| Commercial | `SIM26_DEV`, `SIM26_DEVL`, `SIM26_SO`, `SIM26_SOL` | Devis accepté, commande de 10 unités à 200 DZD HT |
| Expédition | `SIM26_DN`, `SIM26_DNL` | Livraison complète des 10 unités |
| Facturation | `SIM26_INV`, `SIM26_INVL` | 2 000 DZD HT, simulation TVA 380 DZD, TTC 2 380 DZD |
| Encaissement | `SIM26_PAY`, `SIM26_MATCH` | Paiement 2 380 DZD, lettrage intégral |
| Achats fournisseurs | `SIM26_BILL`, `SIM26_BILLL` | Facture fournisseur fictive **BROUILLON**, 1 000 DZD |
| CRM et projets | `SIM26_OPP`, `SIM26_CALL`, `SIM26_PROJ`, `SIM26_TASK`, `SIM26_TIME` | Opportunité gagnée, interaction, projet, tâche et feuille de temps test |

### Conservation des stocks
- MP : `100 entrées - 100 consommées = 0` ; stock courant = 0.
- PF : `10 produites - 10 livrées = 0` ; stock courant = 0.
- Les lots sont marqués épuisés ; aucune quantité existante de `DEMO26` ou d'un tiers réel n'est modifiée.

## Preuves SQL et automatisation
- Seed versionné : `sql/demo/20261105_seed_cycle_complet_SIM26_FICTIF.sql` ; prétest transactionnel `ROLLBACK` réussi puis **40 insertions exécutées avec COMMIT**.
- Contrôle : `sql/demo/20261105_verification_cycle_complet_SIM26_FICTIF.sql` ; **40 IDs vus dans 37 tables, 0 écart**, 100 kg reçus/consommés, 10 unités produites/livrées, qualité OUI, facture/paiement/lettrage à 2 380 DZD.
- Ancien contrôle : `sql/demo/20261105_verification_EXACTE_80_lignes_FICTIF.sql` ; les 80 identifiants anciens sont à vérifier indépendamment.
- Le rollback indépendant du nouveau cycle : `sql/demo/20261105_rollback_cycle_complet_SIM26_FICTIF.sql`.
- Le rollback **des deux jeux** : `sql/demo/20261105_rollback_TOTAL_120_lignes_FICTIVES.sql`, soit **95 DELETE dans une transaction**, suppression de SIM26 d'abord pour respecter les références à DEMO26. **Essai à blanc réussi**, suivi d'un `ROLLBACK`. Ne jamais déclencher le `COMMIT` de ce script pendant les tests.
- Protection : `scripts/envoyer_relances.py` et `core/export_scf.py` bloquent désormais les préfixes `DEMO26_` et `SIM26_` pour les courriels et exports SCF contrôlés, et des tests de régression sont ajoutés.

## Limites précises
Les liens et données testent le **modèle relationnel et les indicateurs**, pas l'exécution des transitions via les boutons d'une session Streamlit authentifiée. Les 9 écrans Dashboard restent à valider visuellement via `https://nextgent-erp.streamlit.app/` avec un compte déjà habilité. Ne jamais interpréter ce scénario comme une homologation fiscale, un essai SMTP réel ou une preuve de livraison du dernier commit sur Streamlit Cloud.

## Reprise
1. Vérifier le verdict des workflows GitHub du dernier commit. Réparer seulement les erreurs confirmées.
2. Lancer les deux scripts de vérification **lecture seule** sur Supabase et comparer avec les valeurs attendues.
3. Dans Streamlit, sélectionner **octobre 2026** pour l'historique du cycle complet, contrôler les onglets sans validation transactionnelle réelle.
4. Après la campagne, utiliser le rollback indépendant `SIM26` ou le rollback intégral `120` uniquement si le retrait des jeux fictifs est souhaité. L'utilisateur souhaite actuellement **conserver les données pour les essais**.

## Ajustement de statuts à l'interface (post-seed)

Après insertion du lot, contrôle des libellés utilisés par les vues métier : `commandes_achats.SIM26_PO.statut` = `RECEPTIONNE`, `commandes_ventes.SIM26_SO.statut` = `TERMINE`, `bons_livraison.SIM26_DN.statut` = `EXPEDIE`. Ces trois changements portent exclusivement sur les lignes SIM26 et sont intégrés au seed versionné pour une reproduction future. Dans la base principale, ils ont été appliqués après contrôle préalable des anciens statuts. Le contrôle SQL lecture seule a reconfirmé les **40 lignes**, **0 anomalie**, et ces trois états.

**Ne pas rejouer le seed sur la base déjà alimentée** : l'opération échouerait sur les identifiants réservés.
