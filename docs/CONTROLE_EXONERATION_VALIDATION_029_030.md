# Sofiane ERP — contrôles fiscaux 029/030

## Périmètre et règle métier

- Sur les ventes de l'entreprise : **TVA normale 19 %**, ou **0 % uniquement pour un client muni d'une attestation applicable, validée et couvrant les SKU facturés**. Le taux réduit 9 % est hors du périmètre métier Ventes.
- Le client et les SKU doivent aussi être encore actifs au moment où le second contrôleur homologue l'attestation. Cela ne remplace ni l'avis juridique, ni les vérifications des limites et conditions figurant sur la pièce réelle.
- Le valideur doit détenir simultanément SECURITY_MANAGER et l'habilitation fiscale `erp_exonerations_tva_validateurs` active ; le créateur du dossier ne peut pas signer son propre dossier. Aucun rôle n'est attribué par défaut.

## Migration 029 — recontrôle au moment de valider

- Fichier : `sql/029_recontrole_client_skus_validation.sql`.
- Change uniquement la fonction `public.erp_exoneration_tva_action`, sans modification de factures.
- À l'action `VALIDER`, rejette les dossiers dont le client n'est plus actif et ceux dont au moins un SKU est inactif ou absent, ainsi que les portées vides.
- Les gardes antérieures (identité, double habilitation, idempotence, date de vérification et référence d'avis) demeurent.

## Migration 030 — audit métier exploitable

- Fichier : `sql/030_journal_acteur_metier_exoneration.sql`.
- Colonnes ajoutées au journal privé : `acteur_metier` (référence utilisateur) et `operation_id` (UUID de l'action), en complément de `acteur_sql`.
- La RPC écrit ces valeurs dans des paramètres **locaux à la transaction** ; le trigger de journalisation les lit. Un changement manuel par l'administrateur PostgreSQL peut laisser `acteur_metier` vide, mais conserve `acteur_sql`.
- Le journal est sous RLS, sans lecture directe pour les utilisateurs navigateur ni pour `service_role`.
- Une relation entre un événement et sa requête peut être reconstruite en jointure avec `erp_exonerations_tva_operations`, sans supposer l'identité à partir du nom du rôle de base de données.

## Tests et déploiement

- Tests statiques intégrés à CI : `tests/test_exoneration_sql_029.py`, `tests/test_exoneration_sql_030.py`.
- Transactions TEST sous `BEGIN/ROLLBACK` : `sql/029_smoke_test_rollback.sql` et `sql/030_smoke_test_rollback.sql`. Elles vérifient refus client inactif, refus SKU inactif, puis validation, révocation et trois événements cohérents. Aucune attestation, aucune autorité temporaire et aucun validateur fictif n'est conservé.
- **Ordre impératif de migration : 029, puis 030.** Vérifier chaque historique de migration Supabase et les privilèges de la RPC après déploiement.
- Ne jamais exécuter les smoke tests à données fictives sur PRODUCTION. La vérification de production se fait en SELECT uniquement.

## Vérifications production conseillées

```sql
SELECT
  (SELECT count(*) FROM public.erp_exonerations_tva_clients) AS attestations,
  (SELECT count(*) FROM public.erp_exonerations_tva_validateurs WHERE actif) AS validateurs_actifs,
  (SELECT count(*) FROM public.erp_exonerations_tva_operations) AS operations,
  (SELECT count(*) FROM public.erp_exonerations_tva_evenements) AS evenements,
  has_function_privilege('anon',
    'public.erp_exoneration_tva_action(text,text,uuid,jsonb)','EXECUTE') AS anon_exec,
  has_function_privilege('authenticated',
    'public.erp_exoneration_tva_action(text,text,uuid,jsonb)','EXECUTE') AS auth_exec,
  has_function_privilege('service_role',
    'public.erp_exoneration_tva_action(text,text,uuid,jsonb)','EXECUTE') AS serveur_exec;
```

## Blocages indépendants

- Aucun validateur fiscal réel n'a encore été désigné.
- Les classifications fiscales des 7 SKU actifs sont encore absentes.
- La RPC de facturation réelle `public.erp_sale_transaction` n'utilise pas encore les attestations et doit rester inchangée avant homologation.
- URL et branche effectivement déployées sur l'application Streamlit toujours non identifiées : un commit GitHub et une CI verte n'établissent pas le déploiement hébergé.
