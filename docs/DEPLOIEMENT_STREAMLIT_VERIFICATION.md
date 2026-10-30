# Vérification du déploiement Streamlit — Sofiane ERP

## Source du code

- Dépôt : `Verwolfy/erp-mortier`
- Branche principale et unique : `main`
- Base unique active : Supabase `erp-mortier` (`wenydirqtmkywbxbxfal`), PRODUCTION.
- Ancien projet TEST : inactif, non nécessaire au fonctionnement en PRODUCTION.
- Point d'entrée Streamlit : `app.py`
- Identifiant visuel à rechercher **après authentification et accès au module Ventes** :
  `Version interface Ventes : SOF-ERP-20261030-EXO-HIST-02`

L'identifiant est codé dans `modules/ventes/views.py` ; sa présence permet de
vérifier que **cette version du code UI** a atteint l'application consultée.
Il ne s'agit **pas** d'un SHA Git, ni d'une preuve de conformité de la facturation.

## Contrôle du déploiement effectif

1. Identifier l'URL Streamlit réelle et le fournisseur d'hébergement. Aucune
   URL de l'application n'a été prouvée dans le dépôt GitHub à ce jour.
2. Si Streamlit Community Cloud est utilisé, ouvrir l'espace de travail du
   propriétaire du dépôt dans `share.streamlit.io` ; vérifier le dépôt
   `Verwolfy/erp-mortier`, la branche `main` et `app.py`.
3. Vérifier que le déploiement a terminé sans erreur dans les journaux
   d'application, **sans publier de secrets**.
4. Après authentification, ouvrir Ventes et constater la présence du repère
   ci-dessus. Le noter avec l'URL, la branche et la date de vérification.
5. Si le repère manque, **ne pas annoncer un déploiement réussi**. Contrôler
   le rattachement du dépôt/branche, le démarrage et les journaux de l'hôte.
   Les tests GitHub Actions seuls ne garantissent pas le déploiement.

## Frontière réglementaire

Le service central Ventes bloque désormais DRAFT/VALIDATE lorsqu'un dossier
fiscal client existe ou que sa lecture échoue. C'est un contrôle applicatif,
non atomique avec la RPC SQL. Le nouvel écran fournit un diagnostic, un registre non homologué et une
simulation pure par SKU. Ces fonctions **n'activent pas** la facture
transactionnelle. La RPC `public.erp_sale_transaction` utilise encore
une TVA historique codée en dur et la migration SQL 013 reste bloquée.
Les classifications TVA des 7 SKU actifs doivent être documentées et
validées sans taux ni source inventés.
