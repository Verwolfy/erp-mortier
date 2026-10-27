-- Read-only diagnostics. Execute ONLY on a separate TEST Supabase project.
-- Avoid interpreting these results as sufficient to certify accounting / units.

-- 1) Open orders and associated recipes / SKU product consistency.
SELECT ofab.of_id, ofab.statut, ofab.pf_id, ofab.recette_id, ofab.sku_id,
       ofab.quantite_prevue, r.pf_id AS recette_pf, r.actif AS recette_active,
       sku.pf_id AS sku_pf,
       CASE WHEN r.recette_id IS NULL OR sku.sku_id IS NULL
                      OR r.pf_id IS DISTINCT FROM ofab.pf_id
                      OR sku.pf_id IS DISTINCT FROM ofab.pf_id
            THEN 'INCOHERENT' ELSE 'OK' END AS verification
FROM public.ordres_fabrication AS ofab
LEFT JOIN public.recettes AS r ON r.recette_id = ofab.recette_id
LEFT JOIN public.sku_conditionnement AS sku ON sku.sku_id = ofab.sku_id
WHERE ofab.statut IN ('PLANIFIE','EN_COURS')
ORDER BY ofab.of_id LIMIT 500;

-- 2) Recipe lines: missing, zero and negative quantities.
SELECT r.recette_id, r.pf_id, count(l.ligne_recette_id) AS nb_lignes,
       count(l.ligne_recette_id) FILTER (
         WHERE l.mp_id IS NULL OR l.quantite_par_unite IS NULL
            OR l.quantite_par_unite <= 0) AS nb_invalides
FROM public.recettes AS r
LEFT JOIN public.lignes_recette AS l ON l.recette_id = r.recette_id
GROUP BY r.recette_id, r.pf_id
HAVING count(l.ligne_recette_id) = 0
    OR count(l.ligne_recette_id) FILTER (
         WHERE l.mp_id IS NULL OR l.quantite_par_unite IS NULL
            OR l.quantite_par_unite <= 0) > 0
ORDER BY r.recette_id;

-- 3) Duplicate components are consolidated in the new closure function.
SELECT recette_id, mp_id, count(*) AS nombre_lignes
FROM public.lignes_recette
GROUP BY recette_id, mp_id
HAVING count(*) > 1
ORDER BY recette_id, mp_id;
