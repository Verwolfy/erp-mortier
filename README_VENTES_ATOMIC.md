# ERP Mortier — transactions Ventes (préparation uniquement)

Le patch conserve les six principales fonctions publiques de `modules/ventes/service.py`.
Il remplace les mutations séparées par `public.erp_sale_transaction(p_action,p_operation_id,p_payload)`.
**Aucune migration n'a été testée ni déployée sur un PostgreSQL réel.**

## Prérequis

1. Utiliser un projet Supabase de **test entièrement séparé** et une copie anonyme des données utiles.
2. Vérifier `sql/vente_preflight_readonly.sql` et rapprocher les stocks physiques / lots et les commandes ouvertes.
3. Exécuter en TEST la migration **002** (Stocks), puis **005** (Ventes). La migration Ventes appelle `erp_apply_stock_movement` lors d'un BL. Valider aussi l'intégration avec les migrations Production et Achats.
4. Dans les secrets *serveur* Streamlit de TEST : `st.secrets['supabase']['stock_service_key']` doit être une clé `service_role`, jamais transmise à un utilisateur ou au navigateur. Ne pas mettre cette clé dans Git.
5. Vérifier le RBAC réel (`factures`, `bons_livraison`, `mouvements_pf`) et les privilèges PostgreSQL. Le client Python n'est pas une frontière de sécurité contre un serveur compromis.

## Règles métier modifiées

- **Brouillon** : entête + lignes + numéro légal atomiques (compteur verrouillé). Le générateur historique `generer_numero_facture_legal` reste disponible mais **ne doit pas être utilisé avant `create_facture_brouillon`** : il réserverait un numéro inutilement.
- **Validation** : possible seulement pour un brouillon ; ne réserve ni ne sort le stock. Les contrôles physiques sont effectués lors de l'expédition.
- **Annulation** : seulement un brouillon non payé, sans retour automatique en stock. Une facture validée doit faire l'objet d'un **avoir** selon les procédures comptables applicables. Un vrai retour physique nécessitera une réception de retour indépendante (fonctionnalité restant à développer).
- **Avoir** : nécessite une facture originale et ne doit pas dépasser le TTC original, après cumul des avoirs validés. Aucun timbre sur les avoirs dans cette première implémentation, en attente de validation fiscale.
- **BL** : nécessité d'une **commande client existante**, limitation des quantités livrées au cumul commandé, allocations FIFO réelles ; le `bl_id` est généré sous la forme `BL-<UUID>` (attention aux écrans ou exports attendant un numéro séquentiel).
- **Remise** des lignes de facture : montant absolu (pas pourcentage). Taux de TVA de 19 %, droit de timbre 1 % limité à 2 500 DZD : conventions de l'ancien code à **faire vérifier juridiquement et fiscalement** avant production.
- **Outbox** `erp_sales_outbox` : événement enregistré atomiquement, **mais aucun traitement asynchrone Google Sheets n'est encore implémenté**. Supabase seul fait foi.

## Attention impérative : `operation_id`

Toute opération expose un paramètre optionnel `operation_id`. Pour un double clic, une reconnexion ou un timeout, **réutiliser exactement le même identifiant** (par exemple UUID stocké par le formulaire Streamlit dans `st.session_state`). Si la fonction lève `SaleOperationError`, son attribut `operation_id` indique l'identifiant à réutiliser avec les **mêmes paramètres**. Si on laisse Python générer un identifiant différent à chaque appel, deux clics différents peuvent créer deux opérations.

## Tester localement dans PowerShell

```powershell
.\.venv\Scripts\python.exe -m compileall -q app.py core config modules
.\.venv\Scripts\python.exe -m pytest -q tests/test_ventes_atomic.py
.\.venv\Scripts\python.exe -m pytest -q tests/test_app_security.py tests/test_auth_hardening.py tests/test_db_service_security.py tests/test_stocks_atomic.py tests/test_production_atomic.py tests/test_achats_atomic.py tests/test_ventes_atomic.py
```

Ces tests utilisent des doubles de la base Supabase et des vérifications statiques SQL ; ils **ne prouvent ni l'atomicité réelle, ni le comportement RLS, ni l'absence d'interblocages**.

## Avant une PR vers `main`

- Adapter `modules/ventes/views.py` aux statuts, BL et idempotence ; vérifier les cas avec commandes sans lignes ou avec sélections de lots manuelles.
- Tester SQL 002 + 003 + 004 + 005 sur une base réelle de TEST : transactions concurrentes, données préexistantes, verrouillage du compteur, rejeu de la même opération, interruption réseau, retours physiques et avoirs partiels.
- Vérifier les échéances fiscales, la numérotation légale, les règles d'avoirs, TVA et timbre avec le responsable comptable en Algérie.
- Préparer un mécanisme de synchronisation différée Google Sheets depuis les outbox et une procédure de retour arrière validée.
- Tant que ces points ne sont pas validés : **ITERATING, NE PAS FUSIONNER DANS main**.
