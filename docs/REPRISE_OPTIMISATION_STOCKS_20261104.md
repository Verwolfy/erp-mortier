# Sofiane ERP — Reprise optimisation Stocks — 4 novembre 2026

## Contexte
- Dépôt GitHub `Verwolfy/erp-mortier`, branche `main` ; ERP `https://nextgent-erp.streamlit.app/`.
- Production Supabase `wenydirqtmkywbxbxfal`, projet TEST `ffuhbmcfyexsbjwhryvj` toujours inactif.
- Les documents NEXTGEN conservent le statut BROUILLON et le QR local non certifié. SQL 033 du registre QR préparé, NON DÉPLOYÉ ; aucune écriture SQL autorisée dans ce lot.

## Réalisé
- `modules/admin/stock_quality.py` : calculs **en lecture seule** pour :
  1. `stock_actuel` (MP) et `stock_actuel_pf` (SKU) : identifiants manquants/doublons, références inconnues, quantités invalides/négatives.
  2. `lots` : identifiants et liens MP/PF, quantités initiales/restantes invalides, négatives ou restantes supérieures à initiales.
  3. `mouvements` et `mouvements_pf` : référence MP/SKU, type ENTREE/SORTIE, quantités finies et positives, compatibilité lot/article/type si un lot est renseigné.
- Lectures via `core.db_service.fetch_data_paginated` : droits RBAC serveur, maximum 5000 lignes/table, aucune synthèse partielle en cas d'erreur.
- `modules/admin/views.py` : onglet Administration > Qualité référentiels, boutons **Analyser les stocks autorisés** et **Analyser les mouvements de stock autorisés**. Résultats agrégés, sans ID ni donnée personnelle.
- `tests/test_admin_stock_quality.py` : données fictives, cas de quantités/lot illégaux, refus RBAC, contrôle d'absence de fonctions d'écriture.
- `modules/help/views.py` : instructions mises à jour.
- Vérification Supabase en lecture seule : `lots.type_item` utilise MP (5) / PF (1), `mouvements` contient ENTREE (5) / SORTIE (3), `mouvements_pf` contient ENTREE (1) / SORTIE (1). Ces totaux reflètent l'état au moment de la requête et ne sont pas un audit complet.
- Commits du lot : `2c2181b`, `e48d225`, `0d51828`, `85a0e53`, `2b32efa`, `be53d46`, `a3e9987`.

## Limites
- Contrôle structurel **seulement** : ne prouve pas la conformité des stocks ni le rapprochement quantitatif entre historique des mouvements, lots et soldes.
- Certains stocks historiques peuvent avoir été créés sans lots ; ne pas comparer naïvement les sommes.
- Les résultats sont disponibles pour les rôles ayant les droits de lecture nécessaires aux tables demandées. Aucune correction automatique ni mouvement ERP créé.
- Contrôle visuel dans Streamlit reste à effectuer.

## Suites
1. Vérifier le verdict final CI GitHub des derniers commits et corriger toute régression.
2. Avec une session ERP autorisée, tester les deux nouveaux boutons et les refus d'accès RBAC.
3. Audit Achats/Ventes : cohérence des lignes de commande et références SKU/MP, sans modifier écritures.
4. Revoir les constantes de fiscalité en Ventes avec le référentiel légal et un professionnel compétent avant changement.
5. Registre QR 033 : uniquement après validation du modèle d'identité et des tests RLS/transactions, sans migration précipitée.
