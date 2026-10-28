-- Préflight des lots C/D/F. LECTURE SEULE : aucune écriture.
-- Vérifier les noms et privilèges sur Supabase TEST avant migration 012-015.
WITH attendues(lot, nom) AS (
  VALUES
  ('012', 'schema_migrations'),
  ('012', 'parametres_reglementaires'),
  ('012', 'regles_reglementaires'),
  ('014', 'scf_exercices'),
  ('014', 'scf_plan_comptes'),
  ('014', 'scf_journaux'),
  ('014', 'scf_pieces'),
  ('014', 'scf_lignes'),
  ('015', 'paie_periodes_v2'),
  ('015', 'paie_bulletins_v2'),
  ('015', 'paie_lignes_v2')
)
SELECT a.lot, a.nom AS table_attendue,
       CASE WHEN c.oid IS NULL THEN 'ABSENTE' ELSE 'PRESENTE' END AS etat,
       COALESCE(c.relrowsecurity, false) AS rls_active,
       COALESCE(has_table_privilege('anon', c.oid, 'SELECT'), false) AS select_anon,
       COALESCE(has_table_privilege('authenticated', c.oid, 'SELECT'), false) AS select_authenticated,
       COALESCE(has_table_privilege('service_role', c.oid, 'SELECT'), false) AS select_service_role
FROM attendues a
LEFT JOIN pg_catalog.pg_namespace n
    ON n.nspname = 'public'
LEFT JOIN pg_catalog.pg_class c
    ON c.relnamespace = n.oid AND c.relname = a.nom AND c.relkind IN ('r','p')
ORDER BY a.lot, a.nom;
