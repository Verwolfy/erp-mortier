# ERP-063 — Rapprochement fournisseur trois voies, copie PDF BC et visa interne préparé
Date : 23 novembre 2026. Repo : `Verwolfy/erp-mortier`, branche `main`.
Base principale Supabase : `wenydirqtmkywbxbxfal`. Aucun TinyFish.

## Statut de livraison
- **Actif dans le code, sans migration** : outil de contrôle **consultatif** `Achats → Historique & Suivi`, explicitement ouvert par l'utilisateur. Possibilité de générer une copie PDF du bon de commande fournisseur à partir des données enregistrées, et un état de rapprochement BC / BR / facture en **Excel, CSV, PDF**.
- **Préparé mais NON installé** : `sql/ERP_063_PREPARATION_visa_bc_20261123.sql` — contrôle interne par un second valideur, dépendant du schéma DA d'ERP-062 qui lui-même reste désactivé. **Aucune signature, émission ou transmission n'a eu lieu**.
- **Financier** : aucune migration ERP-061 de réparation de paiement activée, aucun règlement autorisé.

## Ce que vérifie le rapprochement 3 voies
Lecture stricte avec droits RBAC **frais** de `factures_fournisseurs`, `lignes_factures_fournisseurs`, `commandes_achats`, `lignes_achats`, `bons_reception`, `lignes_bons_reception`.
1. Référence BC, fournisseur et lien facture/commande.
2. Quantité prévue au BC, quantité réceptionnée **conforme**, quantité facturée et **somme des quantités de TOUTES les factures rattachées** (brouillons compris, faute de règle fiable d'annulation).
3. Prix unitaire enregistré sur le BC et sur la facture, ainsi que calculs ligne HT exactement égaux à quantité × prix ; seuls BC DZD / taux 1 sont rapprochés.
4. Somme des lignes HT = en-tête HT ; présence des montants TVA/TTC et égalité arithmétique HT + TVA = TTC. Ce contrôle **ne valide pas le taux fiscal**.
5. Refus si dossier incomplet, données incohérentes, prix contradictoires, BR non conformes, quantité cumulée au-delà du BC ou des réceptions, facture en `BROUILLON`, montant manquant. Lectures bornées et vérifiées ; les lectures multi-tables ne sont **pas atomiques** et ne constituent pas une preuve de validation.
6. Quel que soit le constat, `autorise_paiement=false`, `ecriture_stock=false`, `certification_fiscale=false`. Un rapprochement « concordant » signifie **documentaire seulement**.

### Audit réel en lecture seule (principal)
- `DEMO26_FF1` : BC `DEMO26_CA1`, MP `DEMO26_MP1`, 1000 commandés / 1000 réceptionnés conformes / 1000 facturés à 80 DZD (HT 80 000 DZD) ; facture `BROUILLON`, **TVA/TTC absents**, donc **non payable**.
- `SIM26_BILL` : BC `SIM26_PO`, MP `SIM26_MP`, 100 commandés/reçus conformes/facturés à 10 DZD (HT 1000 DZD, TVA 0, TTC 1000) ; facture `BROUILLON`, donc **non payable**.
- Pas d'écriture de stock ou finance pendant ces lectures.

## Copie imprimable du BC
- `modules/achats/three_way_views.py` expose le téléchargement PDF via `modules.documents.erp_print.load_operation_snapshot` et `render_operation_pdf`.
- L'écran affiche **COPIE NON ÉMISE / NON SIGNÉE** ; aucune intégration signature/SMTP/banque. Le PDF reflète uniquement l'en-tête et les lignes persistées.
- Dans `modules/achats/views.py`, les composants ERP-063 ne s'importent **qu'après clic d'ouverture explicite** pour préserver le chargement paresseux et les droits de navigation.

## Visa BC : préparation SQL non appliquée
Fichier : `sql/ERP_063_PREPARATION_visa_bc_20261123.sql`.
- Prérequis : ERP-062 DA installée et `demande approuvée par un autre acteur` liée au BC.
- `PREPARE` : seulement le demandeur de la DA, sur un BC `EN_ATTENTE` **sans aucune réception**, avec empreinte interne des données de l'en-tête et des lignes.
- `VISA` / `REFUSE` : second utilisateur ADMIN **distinct du préparateur**, avec comparaison de l'empreinte et contrôle du statut du BC. Le refus nécessite un motif.
- Journal d'opérations idempotent, RLS sur les deux tables, aucune autorisation `anon` / `authenticated`, RPC `SECURITY INVOKER` réservée `service_role`.
- Réponse marquée `signature_effectuee=false`, `transmission_fournisseur_effectuee=false`, `paiement_autorise=false`. L'empreinte MD5 est un **témoin technique de changement, pas une signature cryptographique**.
- Aucune RPC ne produit d'émission commerciale, de réception, de virement ni de comptabilité.

### Test SQL réel annulé
Les migrations préparatoires ERP-062 et ERP-063 ont été exécutées ensemble en `BEGIN...ROLLBACK` sur le principal : création de DA pour 2 kg MP, soumission, second approbateur temporaire non connectable, approbation, BC créé, dossier de visa préparé puis rejoué sans doublon ; refus de l'auto-visa et refus d'un visa après modification du prix ; visa indépendant positif et garantie **aucune signature, transmission, paiement**. Tests ACL. Résultat après rollback : **0 nouvel utilisateur, 0 table de visa et 0 BC de test conservés**.

## Fichiers GitHub
- `modules/achats/three_way_match.py` : calcul et accès strict aux pièces ; contrôles cumulatifs sans aucune mutation.
- `modules/achats/three_way_views.py` : écran de contrôle, exports et copie du BC fournisseur.
- `modules/achats/views.py` : nouvelles fonctionnalités à chargement explicite, dans Historique & Suivi.
- `tests/test_erp063_three_way.py` : TVA manquante, cumul sur plusieurs factures, prix, quantités, BR non conforme, droits, calculs non payables.
- `tests/test_erp063_po_visa.py` : séparation des tâches, empreinte, aucun envoi.
- `tests/test_achats_views_security.py`, `tests/test_lot07_achats_lazy.py` : maintien des contrôles d'historique tout en tolérant les nouveaux boutons de consultation.
- `sql/ERP_063_PREPARATION_visa_bc_20261123.sql` : préparée, **NON APPLIQUÉE**.
- `docs/ERP_063_CONTROLE_TROIS_VOIES_VISA_BC_20261123.md` (ce document).

## Risques et étapes d'homologation
1. Le module de validation documentaire est **une consultation**, pas une décision de paiement ; ne jamais l'utiliser comme autorisation bancaire/fiscale.
2. La RPC de règlement fournisseur ERP-061 reste **buguée en production** (#85). Un correctif prouvé en `ROLLBACK` attend revue et approbation financière.
3. ERP-062 DA et ERP-063 visa n'ont **pas de tables en production** ; second approbateur réel manquant, et l'ancienne RPC BC directe reste techniquement accessible. Ne pas activer `ERP_PURCHASE_REQUESTS_ENABLED` sans migration/habilitation.
4. L'émission fournisseur réelle nécessite signature, piste de preuve de transmission, version du PDF, approbation d'un responsable et état de non-répudiation : **non livré**.
5. Le contrôle 3 voies doit évoluer vers un **snapshot transactionnel SQL** avec tolérances métier homologuées, multi-devises, taxes réelles et statut d'une facture VALIDÉE ; pas de contournement par faux documents.
6. La version effectivement déployée sur Streamlit reste non vérifiée (#78), pas de test navigateur authentifié.
7. Suivi : [Achats #86](https://github.com/Verwolfy/erp-mortier/issues/86), [Finance #85](https://github.com/Verwolfy/erp-mortier/issues/85), [Déploiement #78](https://github.com/Verwolfy/erp-mortier/issues/78).
