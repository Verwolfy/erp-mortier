-- ERP-047 : diagnostic SQL lecture seule de la préparation fiscale TVA/SKU.
-- Aucune qualification, aucun taux ni pièce comptable n'est créé/modifié.
-- Le mot PRET ci-dessous signifie "prêt techniquement pour essais",
-- sans attester de la validité juridique réelle d'un régime produit.
CREATE OR REPLACE FUNCTION public.erp_tva_sku_readiness(p_date date)
RETURNS TABLE (
    sku_id text,
    etat_technique text,
    fiches_applicables bigint,
    code_tva text
)
LANGUAGE plpgsql STABLE SECURITY INVOKER
SET search_path = pg_catalog, public
AS $erp_readiness$
BEGIN
    IF p_date IS NULL THEN
        RAISE EXCEPTION 'Date requise pour audit fiscal SKU'
            USING ERRCODE='22023';
    END IF;
    RETURN QUERY
    SELECT s.sku_id::text,
           CASE
             WHEN f.nb = 0 THEN 'SANS_FICHE'
             WHEN f.nb > 1 THEN 'CONFLIT_VERSIONS'
             WHEN f.categorie IN ('EXONERE','HORS_CHAMP') THEN 'HORS_MOTEUR_PILOTE'
             WHEN f.valide <> 1 THEN 'A_VALIDER'
             WHEN r.nb <> 1 OR r.valide <> 1 THEN 'TAUX_A_VERIFIER'
             ELSE 'PRET_TECHNIQUEMENT'
           END::text AS etat_technique,
           f.nb::bigint,
           (CASE WHEN f.nb = 1 THEN f.code ELSE NULL END)::text
    FROM public.sku_conditionnement s
    CROSS JOIN LATERAL (
        SELECT
          count(*) AS nb,
          max(q.categorie_tva) AS categorie,
          max(q.code_parametre) AS code,
          count(*) FILTER (WHERE
             q.statut = 'VALIDEE'
             AND (
                 (q.categorie_tva='NORMAL' AND q.code_parametre='TVA_TAUX_NORMAL')
                 OR (q.categorie_tva='REDUIT' AND q.code_parametre='TVA_TAUX_REDUIT')
             )
             AND nullif(btrim(q.source_juridique),'') IS NOT NULL
             AND nullif(btrim(q.justification),'') IS NOT NULL
             AND nullif(btrim(q.valide_par),'') IS NOT NULL
             AND q.date_verification IS NOT NULL
             AND q.date_validation IS NOT NULL) AS valide
        FROM public.erp_sku_fiscalite q
        WHERE q.sku_id=s.sku_id
          AND q.date_effet <= p_date
          AND (q.date_fin IS NULL OR q.date_fin >= p_date)
    ) f
    CROSS JOIN LATERAL (
        SELECT
           count(*) AS nb,
           count(*) FILTER (WHERE
               p.statut_juridique='en_vigueur'
               AND p.niveau_confiance='CONFIRMEE'
               AND p.unite='fraction'
               AND p.valeur IS NOT NULL
               AND p.valeur::text NOT IN ('NaN','Infinity','-Infinity')
               AND p.valeur BETWEEN 0 AND 1
               AND nullif(btrim(p.source),'') IS NOT NULL
               AND p.date_verification IS NOT NULL) AS valide
        FROM public.parametres_reglementaires p
        WHERE p.code=f.code
          AND p.date_effet<=p_date
          AND (p.date_fin IS NULL OR p.date_fin>=p_date)
    ) r
    WHERE s.actif='OUI'
    ORDER BY s.sku_id;
END;
$erp_readiness$;

REVOKE ALL ON FUNCTION public.erp_tva_sku_readiness(date)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_tva_sku_readiness(date)
    TO service_role;

COMMENT ON FUNCTION public.erp_tva_sku_readiness(date) IS
 'Diagnostic technique des SKU au jour demandé ; VALIDEE est un état BDD, pas une preuve d homologation juridique.';
