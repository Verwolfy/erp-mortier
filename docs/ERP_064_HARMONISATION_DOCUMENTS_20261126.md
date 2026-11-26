# ERP-064 — Harmonisation des documents exportés (26 novembre 2026)

## Résultat

- **Statut : code fusionné dans `main`.** [PR #94](https://github.com/Verwolfy/erp-mortier/pull/94), merge squash `280f9e7087e16f0e0d8d241f03decc7f6b74fd1a`.
- Le **nom officiel** reste exactement **SARL NEXT GENRATION BUILDING SOLUTIONS**, sans correction orthographique arbitraire.
- Aucune écriture SQL, modification RLS/GRANT, facture officielle, signature, envoi, mouvement de stock ou nouvel identifiant administrateur n'a été réalisée.
- Les six PDF joints le 26/11 (commande fournisseur, facture fournisseur, OF, commande client, BL et facture client) ont servi à l'analyse. Ce sont des exports historiques **non régénérés** lors de ce changement.

## Règles de présentation implémentées

1. Références longues : cellules/entêtes adaptés et retours à la ligne, sans troncature silencieuse dans les copies ERP ; les tableaux logistiques n'affichent plus de prix inutiles. Les exports tabulaires génériques restent explicitement abrégés (Excel/CSV conservant les valeurs).
2. Identités : **Raison Sociale**, **Adresse de Facturation**, **AI**, suppression des blocs « ÉMETTEUR/DESTINATAIRE ». L'identité juridique de chaque partenaire est toujours prise dans le référentiel d'origine.
3. Données manquantes ou « Non renseigné » : non imprimées. Les sections sans données FT/FDS sont omises des brouillons ; leur statut non validé reste visible.
4. Montants DZD à deux décimales avec espaces de milliers et virgule ; TVA, HT/TTC et timbre affichés sans « non homologuée » ou « enregistré » dans les libellés. Les montants absents en base restent absents, **aucune taxe n'est inventée**.
5. Factures et avoirs : TTC en lettres, dinars et centimes, lorsque le TTC est présent.
6. TVA normale **19 %** dans l'éditeur de brouillon : mode de **simulation avec confirmation explicite** de l'éligibilité. Aucune écriture rétroactive ou application automatique aux taux réduits/exonérés.
7. QR vectoriels (ou QR dans les FT/FDS) : type, référence, date quand connue, identifiant et empreinte ; **pas de NIF, nom du client ou lien public en clair**. Ce sont des codes de repérage, **pas des signatures ni des preuves d'émission**.

## Code touché

- `modules/documents/party_identity.py`, `pdf_presentation.py`, `erp_print.py`, `internal_print.py`, `layout_nextgen.py`, `views.py`, `product_sheets.py`, `branding_images.py`.
- `core/pdf_generator.py`, `core/export_formats.py`.
- Tests : `tests/test_pdf_harmonisation_20261126.py`, `tests/test_documents_party_identity.py`, `tests/test_product_sheets_nextgen.py`, `tests/test_erp054_operation_print.py`.

## Validation

- [Audit réconciliation #45814221665](https://github.com/Verwolfy/erp-mortier/actions/runs/45814221665) : **success**, `3 556 passed, 1 warning`, code PR final `13a674b076`.
- [Tests facturation #45814221790](https://github.com/Verwolfy/erp-mortier/actions/runs/45814221790) : **success**, `3 556 passed, 1 warning`, même SHA.
- Le premier run avait détecté trois régressions d'assertion, corrigées avant fusion : deux libellés modifiés et interdiction de fabriquer un total pour un devis dont le total n'était pas persistant.
- **CI de la documentation/du merge sur main** : vérifier les runs les plus récents, ne pas réutiliser le succès PR comme preuve automatique du déploiement Streamlit.
- **Aucun E2E authentifié Streamlit ni inspection visuelle d'un PDF nouvellement généré par l'application hébergée n'a été effectué** : le rendu final réel doit être vérifié dans le prochain cycle de tests. Les scripts génèrent bien des PDF selon les tests mais les métriques de pagination/QR scannable sur périphériques physiques restent à homologuer.

## Points à ne pas confondre

- `FAC-2026-000001` des pièces jointes : montants enregistrés 1250 HT, 237,50 TVA et 1487,50 TTC ; le TTC en lettres correspondant est **Mille quatre cent quatre-vingt-sept dinars et cinquante centimes.** Il ne s'agit pas d'une nouvelle facture émise.
- La facture fournisseur `DEMO26_FF1` n'a pas de TVA/TTC enregistrés ; les lignes absentes sont masquées et le 19 % n'est **pas** imposé arbitrairement.
- Le devis sans totaux persistés reste sans total supposé. Le total d'une commande client peut être calculé **indicativement** à partir des quantités et prix enregistrés.
- Codes « Wilaya 10 » et « Pays DZ » : la conversion vers les libellés de référence n'a **pas** été ajoutée faute de règle serveur vérifiée ; éviter d'introduire de nouveaux référentiels codés en dur. Les données sources restent exactes.

## Prochaine étape du projet

1. Vérifier, en session **Streamlit authentifiée**, le parcours impression / aperçu / PDF pour les six types d'origine, avec captures avant/après, références longues, TVA manquante, QR scannable et pagination multi-pages.
2. Vérifier que Streamlit a effectivement déployé le commit fusionné ; tant que non fait, ne pas déclarer l'application hébergée conforme.
3. Examiner les validations fiscales/documents non émis avant toute homologation d'émission ; les avertissements légaux sont conservés.
4. Continuer la phase de tests ERP. **La sauvegarde externe vers Cloudflare R2 reste en pause** jusqu'à clôture de cette phase et accord spécifique de l'utilisateur.
