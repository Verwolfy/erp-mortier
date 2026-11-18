# ERP-053 — Déblocage du référentiel de conditionnement BOND (18 novembre 2026)

## Déclencheur
Capture de l'écran authentifié **Production & Nomenclatures → OF → Créer un ordre de fabrication** :
- SKU : `NG-SKU-BOND-C1T-SAC-5KG`, « FENEK-BOND C1T — Sac 5 kg ».
- Erreur : `Création d'OF bloquée : Unité KG/L et type de conditionnement incompatibles`.

## Diagnostic fondé sur Supabase principal
Projet `wenydirqtmkywbxbxfal`. Lectures directes :
- SKU `NG-SKU-BOND-C1T-SAC-5KG` : `pf_id=BOND-C1T`, `unite_vente=SAC`, `poids_net=5`, `facteur_conversion=5`, `emballage_mp_id=NG-EMB-SAC-5KG`, `actif=OUI`.
- Emballage `NG-EMB-SAC-5KG` : `categorie_mp=EMBALLAGE`, `unite_stock=U`, `actif=OUI`.
- Produit `BOND-C1T` : `unite_production=NULL`, d'où le refus dans `_sku_pack_spec()` de `modules/production/views.py`. Ce refus protège correctement contre une conversion non qualifiée ; l'erreur est due à la fiche produit incomplète.
- 16 produits `BOND-*` actifs avec `unite_production=NULL` avant correction ; tous leurs SKU actifs sont des sacs avec `facteur_conversion=poids_net`, et chacun dispose d'au moins un SKU actif.
- Aucun de ces 16 produits ne possédait une recette active ; aucun OF `BOND-*` n'existait.
- `docs/LOT_NEXTGEN_SKU_20261101.md` confirme la décision utilisateur « BOND : sacs 5, 10, 25 kg ». Aucune conversion litre↔kg n'est déduite.

## Correction effectuée en base
**Une seule transaction SQL sur le Supabase principal**, avec contrôles bloquants avant mise à jour :
1. Vérification de l'ensemble exact de 16 produits `BOND-*` actifs sans unité.
2. Refus si recette active, SKU actif absent ou SKU incompatible (`SAC`, poids net/facteur).
3. Mise à jour limitée à `public.produits.unite_production='KG'` pour ces 16 produits.
4. Vérification post-commit : `bond_kg=16`, `bond_sans_unite=0`, `recettes_bond_actives=0`, `of_bond=0`.
5. Invariants vérifiés : `erp_sku_fiscalite` VALIDEE = 0 ; `ecritures_comptables` = 0.
6. Les 12 produits `FLOW-*` sans unité restent **inchangés** : densités et formats liquides non qualifiés.

Aucune écriture sur les recettes, OF, stocks, factures, paiements, TVA, comptabilité SCF, droits ou comptes.

## Code et tests
- `modules/production/views.py` : en cas d'unité de production absente, message spécifique `Unité de production non renseignée pour [PF] (KG ou L à qualifier avant fabrication)` au lieu du message générique ; garde-fou KG/L inchangé.
- `tests/test_production_views_security.py` : test du refus explicite d'une unité NULL et test du SKU BOND-C1T sac 5 kg avec `KG` ; conversion 10 sacs = 50 kg, **sans inventer de recette**.
- Commits : `5bf72d5853bb80ed28c2f5408d105a037ef4f607` et `30761a06c736695fe61441854995f712e10df6fc`.
- CI à suivre sur `main` après publication du rapport.

## Limite opérationnelle
Après correction, le contrôle de conditionnement de `BOND-C1T` est cohérent, **mais l'écran doit désormais afficher « Aucune recette active pour ce produit »**. Ce message est prédit par le code et les données ; **il n'a pas encore été confirmé en navigateur**.

Une vérification TinyFish a été tentée avec le profil Bitwarden précédemment autorisé, mais **aucune exécution n'a démarré** : portefeuille TinyFish insuffisant (solde négatif). Aucune tentative répétée.

Ne pas créer une recette commerciale avec une formulation fictive. La qualification industrielle et la validation de laboratoire sont requises. Suivi [issue #79](https://github.com/Verwolfy/erp-mortier/issues/79). L'écart de version Streamlit hébergé [#78](https://github.com/Verwolfy/erp-mortier/issues/78) reste ouvert.

## Suite
1. Vérifier CI du commit de test et absence de régression.
2. Lorsqu'un navigateur authentifié est disponible, recharger Production > OF, sélectionner le SKU BOND-C1T sac 5 kg et constater le message « Aucune recette active pour ce produit ».
3. Obtenir la recette réelle validée et ses MP ; l'enregistrer par RPC sécurisé avec contrôle qualité, puis tester un OF sur données de test isolées.
4. Traiter les unités des autres familles seulement avec justificatifs de densité, conditionnement et procédé. Ne jamais inférer `L` de `KG` ou inversement.
