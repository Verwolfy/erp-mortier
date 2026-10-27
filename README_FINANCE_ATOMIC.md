# ERP Mortier — Finance transactionnelle (à tester, pas prête pour production)

**Ce patch n'a pas été exécuté sur un vrai Supabase.** Le code Python et les
contrats statiques SQL ont été testés localement, mais la migration doit être
validée dans une instance PostgreSQL/Supabase **distincte** de la production.

## Avant de lancer la migration

1. Sauvegarder le schéma et des données de test anonymisées dans un projet Supabase TEST.
2. Exécuter `sql/finance_preflight_readonly.sql` **sur TEST** pour lister les colonnes,
   détecter les règlements incohérents, les factures avec montant payé incohérent,
   et les anciennes écritures non équilibrées. Si le script échoue sur des tables
   absentes ou des types inattendus, arrêter et corriger le schéma/test.
3. Vérifier manuellement la structure de `factures_fournisseurs` : le code suppose
   `facture_fournisseur_id`, `fournisseur_id`, `montant_ttc` et `statut_paiement`
   (texte). Aucun champ de montant payé fournisseur n'est ajouté : le cumul provient
   de la table `lettrage`.
4. Installer `sql/006_atomic_finance.sql` **uniquement sur TEST**. Cette fonction
   est limitée au rôle `service_role`; prévoir `stock_service_key` dans les secrets
   du serveur de TEST uniquement. Ne jamais committer les clés dans Git.
5. Tester avec vraies transactions, deux utilisateurs simultanés, double-clic,
   paiement partiel et complet, panne réseau, remboursement, factures fournisseurs,
   crédit client, reprises et nettoyage de la copie de test. Ne pas transférer
   ces données test dans la production.

## Changements métier : vérifier avec le comptable

- `creer_compte` utilise un seul appel atomique. `solde_initial` est un **solde
  d'ouverture**, pas une écriture de journal d'ouverture. Les écritures
  d'ouverture et la reprise des anciens soldes doivent être comptabilisées
  séparément, suivant les règles applicables.
- `enregistrer_reglement` garde ses paramètres positionnels historiques, mais
  **exige maintenant** `contrepartie_compte_id` (mot-clé) : le compte comptable de
  contrepartie doit être connu et actif dans `comptes`. Sinon le service refuse
  l'opération. Le paiement produit **deux écritures** d'un même montant : banque
  débit / créance crédit pour un encaissement, dette débit / banque crédit pour
  un décaissement. Ce mécanisme NE constitue PAS à lui seul un grand livre complet
  et n'implémente pas la TVA, les écritures de facturation ni les extournes.
- `enregistrer_lettrage` vérifie dans la RPC le règlement, le sens du flux,
  l'identité du partenaire, le statut du document, les montants et l'allocation
  déjà effectuée. Une facture client doit être **`VALIDE`**. Son statut commercial
  reste `VALIDE` même quand elle est entièrement payée, afin de ne pas casser
  l'intégration Ventes/avoirs. Le montant payé est mis à jour dans `montant_paye`.
- Les fournisseurs utilisent un statut de paiement textuel `PARTIELLE` / `PAYEE`.
  Leur montant payé est calculé depuis les lettrages ; il n'est jamais déduit
  de `statut_paiement`.
- Les avoirs négatifs, remboursements, reversements, extournes et régularisations
  de règlements ne sont pas implémentés. Ils doivent avoir un workflow propre.
- Le `lettrage_id` des deux écritures de règlement reste vide : un règlement
  peut être affecté à plusieurs factures. La traçabilité est assurée par
  `document_source_id = reglement_id` et la table `lettrage`.
- Si les montants historiques (`montant_alloue`, `montant_paye`) divergent des
  écritures de lettrage, la RPC **refuse** toute nouvelle allocation et exige
  d'abord une réconciliation documentée. Ne pas corriger ces écarts automatiquement.
- Les nouveaux événements sont enregistrés dans `erp_finance_outbox` de manière
  atomique, mais aucun worker Google Sheets n'est livré par ce correctif.

## Sécurité et reprise

- L'application vérifie les permissions Finance via `check_server_permission`.
  Le contrôle SQL est exécuté avec une clé serveur ; ne pas la mettre dans un
  navigateur, une feuille Google ou le dépôt. La vérification Python seule
  n'est pas une politique RLS/Supabase Auth complète.
- Chaque règlement doit avoir une référence traçable unique par compte. La RPC
  bloque la réutilisation de `reference_trace` sur un même compte, même avec
  un nouvel `operation_id`. Prévoir des références d’espèces individualisées.
  Les écritures directes hors RPC ne sont pas sécurisées par ce verrou.
- Le paramètre optionnel `operation_id` doit être généré et conservé par le
  formulaire Streamlit : si un appel retourne une réponse incertaine, **réutiliser
  le même identifiant et exactement le même payload**. Sinon une deuxième
  opération financière réelle peut être créée.
- La migration utilise `SECURITY INVOKER`, `FOR UPDATE`, un registre idempotent
  et un outbox. Ces mécanismes nécessitent de vrais tests SQL, notamment pour
  confirmer que les contraintes existantes correspondent bien aux hypothèses.

## Compatibilité UI et déploiement

Avant toute PR `main`, adapter `modules/finance/views.py` pour sélectionner un
**compte de contrepartie**, conserver les `operation_id` et afficher la situation
réelle d'une facture payée à partir de `montant_paye / montant_ttc`, sans attendre
le statut `PAYEE`. Prévoir l'affichage distinct de la trésorerie et du grand livre,
et le processus d'ouverture / régularisation comptable. Tester aussi les écrans
Achats/Ventes, le suivi des encaissements et la synchronisation Google Sheets.

**ITERATING — aucune exécution SQL sur la production et aucune fusion vers `main`.**
