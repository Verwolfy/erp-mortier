# ERP-065 — Une seule page A4 pour les documents opérationnels (26 novembre 2026)

## Décision et résultat
- Demande explicite : les documents opérationnels ERP doivent tenir **sur une seule page A4**.
- Exemple de validation : `NEXTGEN_Copie_FAC-2026-000001_2026-11-26 (6).pdf`, deux pages ; la première avait toutes les données et le TTC en lettres, la deuxième ne contenait **que le QR et un texte de consultation**.
- Correctif **fusionné sur `main`** depuis [PR #95](https://github.com/Verwolfy/erp-mortier/pull/95), SHA merge **`d040a3490035d7e04b088925f1c7922375fa91c3`**.
- Le nom légal est maintenu exactement : **SARL NEXT GENRATION BUILDING SOLUTIONS**.
- Aucune modification de Supabase, des RLS, des données ni des taux historiques.

## Implémentation
- `modules/documents/erp_print.py` : QR vectoriel placé **à gauche des totaux**, dans la même bande horizontale, au lieu de créer une section de 45 mm après les montants en lettres. Mention de consultation répétée supprimée dans le corps car **statut NON ÉMIS toujours en tête**. Pas de page 2 automatique.
- `modules/documents/party_identity.py` : les panneaux de coordonnées respectent le mode `single_page`.
- `modules/documents/layout_nextgen.py` : brouillons PDF (20 modèles) avec QR et signatures côte à côte, références longues repliées ; pas de page 2 automatique.
- `modules/documents/internal_print.py` : champs internes en lignes compactes intégrales et QR sur la même page ; pas d'annexe implicite.
- `core/pdf_generator.py` : moteur historique de facture/commande avec QR en parallèle des totaux et refus explicite si trop rempli.
- **Document réellement trop volumineux** : le PDF est **refusé explicitement** ; ne pas supprimer des données, imprimer en police illisible ni fournir une fausse page unique.

## Tests avec preuve GitHub
- [PR CI Audit `45849187480`](https://github.com/Verwolfy/erp-mortier/actions/runs/45849187480) : **success**, `3597 passed, 12 warnings`.
- [PR CI Facturation `45849187493`](https://github.com/Verwolfy/erp-mortier/actions/runs/45849187493) : **success**, `3597 passed, 12 warnings`.
- Commit testé : `82d38d0260d93712b02cf724fac10b592d960c0c`.
- Tests `tests/test_documents_a4_une_page_20261126.py` : 8 types d'opérations, copies internes, 20 types de brouillons, facture avec coordonnées détaillées et montant en lettres, refus de documents très longs, moteur historique.
- Les premiers pipelines avaient échoué : la mention finale prenait trop de hauteur sur des documents denses ; les fiches internes avaient trop de marges verticales. Ces défauts ont été corrigés **avant fusion**.

## À valider dans Streamlit (recette réelle)
1. Vérifier que la barre latérale affiche le nouveau SHA `main` incluant `d040a349` (ou plus récent) et que les sources sont conformes.
2. Réexporter `FAC-2026-000001` depuis Streamlit.
3. Contrôler **1/1 page**, QR visible et scannable, TTC en chiffres et en lettres, identités légales, pied de page non masqué et lisibilité.
4. Répéter pour commandes, BL, OF, BR et factures fournisseurs sur des enregistrements représentatifs.
5. Les pipelines de PR ne constituent pas à eux seuls une preuve de rendu ou déploiement effectif dans Streamlit.

## Portée et exclusions
- Règle appliquée aux **pièces opérationnelles** et modèles administratifs courts : factures, commandes, devis, livraisons, réceptions, OF, copies internes, brouillons.
- **Rapports tabulaires volumineux et FT/FDS réglementaires** : ne pas forcer artificiellement sur une page si cela risque de supprimer des mentions obligatoires ; leur pagination est une exigence fonctionnelle distincte et doit être arbitrée séparément.
- Aucune facture fiscale officielle n'a été émise par la correction.
- Le projet Cloudflare R2/B2 demeure **EN PAUSE** jusqu'à clôture des tests ERP et nouvel accord utilisateur.

## Référence de continuité
Lire ce document et `docs/ETAT_AVANCEMENT.md` lors de la prochaine discussion. L'application et la base doivent être auditées avec leurs accès directs GitHub/Supabase, **sans TinyFish**.
