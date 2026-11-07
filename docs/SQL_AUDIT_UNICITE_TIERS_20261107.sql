-- PR de préparation, SQL STRICTEMENT EN LECTURE SEULE.
-- Lancer sur Supabase pour inventorier les collisions avant toute future
-- contrainte d'unicité. Ce fichier ne contient aucun DDL, INSERT ni UPDATE.
-- Les NIF/RC sont comparés dans CHAQUE référentiel, pas entre client et
-- fournisseur. La normalisation SQL n'ignore que les séparateurs ASCII.
-- Les accents du nom nécessitent une politique métier distincte.
WITH tiers AS (
  SELECT 'clients'::text AS source, client_id::text AS id,
         nom::text, nif::text, rc::text, pays::text
  FROM public.clients
  UNION ALL
  SELECT 'fournisseurs', fournisseur_id::text, nom, nif, rc, pays
  FROM public.fournisseurs
),
clefs AS (
  SELECT source, id, pays,
         NULLIF(regexp_replace(upper(coalesce(nif, '')),
                             '[^A-Z0-9]', '', 'g'), '') AS nif_normalise,
         NULLIF(regexp_replace(upper(coalesce(rc, '')),
                             '[^A-Z0-9]', '', 'g'), '') AS rc_normalise,
         NULLIF(regexp_replace(lower(btrim(coalesce(nom, ''))),
                             '[[:space:]]+', ' ', 'g'), '') AS nom_simplifie
  FROM tiers
),
collisions AS (
  SELECT source, 'NIF'::text AS cle, nif_normalise AS valeur, count(*) AS nombre
  FROM clefs WHERE nif_normalise IS NOT NULL
  GROUP BY source, nif_normalise HAVING count(*) > 1
  UNION ALL
  SELECT source, 'RC', rc_normalise, count(*)
  FROM clefs WHERE rc_normalise IS NOT NULL
  GROUP BY source, rc_normalise HAVING count(*) > 1
  UNION ALL
  SELECT source, 'NOM_A_REVOIR', nom_simplifie, count(*)
  FROM clefs WHERE nom_simplifie IS NOT NULL
  GROUP BY source, nom_simplifie HAVING count(*) > 1
)
SELECT source, cle, count(*) AS groupes_en_conflit,
       sum(nombre) AS fiches_concernees
FROM collisions
GROUP BY source, cle ORDER BY source, cle;

-- Aucune valeur NIF/RC ni identité nominative n'est retournée ci-dessus.
-- IMPORTANT : une absence de collisions n'autorise pas automatiquement
-- la création d'index UNIQUE. Définir d'abord les exceptions (pays,
-- établissements, homonymes) et l'impact sur les écritures concurrentes.
