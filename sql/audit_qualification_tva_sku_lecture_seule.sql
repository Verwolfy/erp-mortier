-- Audit de qualification TVA des SKU actifs — lecture seule.
-- Ce SELECT n'affecte jamais de taux ni ne prouve la conformité juridique.
-- Date d'observation: CURRENT_DATE (horloge du serveur SQL).
-- Aucune mutation, création de fonction/vue ou changement de droits.
WITH classifications AS (
    SELECT
        sku_id,
        count(*) FILTER (
            WHERE statut = 'VALIDEE'
              AND date_effet <= current_date
              AND (date_fin IS NULL OR date_fin >= current_date)
        ) AS nombre_validees_applicables,
        count(*) FILTER (
            WHERE statut = 'A_VALIDER'
              AND date_effet <= current_date
              AND (date_fin IS NULL OR date_fin >= current_date)
        ) AS nombre_a_valider_applicables
    FROM public.erp_sku_fiscalite
    GROUP BY sku_id
)
SELECT
    current_date AS date_audit,
    s.sku_id,
    s.pf_id,
    s.format,
    s.unite_vente,
    coalesce(c.nombre_validees_applicables, 0) AS classifications_validees,
    coalesce(c.nombre_a_valider_applicables, 0) AS classifications_a_valider,
    CASE
        WHEN coalesce(c.nombre_validees_applicables, 0) > 1
            THEN 'AMBIGUITE_A_RESORBER'
        WHEN coalesce(c.nombre_validees_applicables, 0) = 1
            THEN 'CLASSIFICATION_A_REVERIFIER'
        WHEN coalesce(c.nombre_a_valider_applicables, 0) > 0
            THEN 'VALIDATION_EN_ATTENTE'
        ELSE 'QUALIFICATION_MANQUANTE'
    END AS statut_diagnostic
FROM public.sku_conditionnement AS s
LEFT JOIN classifications AS c ON c.sku_id = s.sku_id
WHERE s.actif = 'OUI'
ORDER BY s.sku_id;
