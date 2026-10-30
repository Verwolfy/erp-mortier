-- ERP 031 : précontrôle TVA client au moment d'une vente (LECTURE SEULE).
-- Pas de facture, pas de création d'attestation, pas d'activation 0 %.
-- Seul le backend service_role peut appeler cette fonction. Le résultat
-- PRECONTROLE_OK ne vaut PAS une autorisation de facturation : il doit être
-- revalidé de manière atomique dans la future transaction SQL de vente.
BEGIN;

CREATE FUNCTION public.erp_exoneration_tva_precontrole_vente(
    p_client_id text,
    p_sku_ids text[],
    p_date_facture date
) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $fn$
DECLARE
    d public.erp_exonerations_tva_clients%ROWTYPE;
    nb_dossiers integer;
    nb_sku_inactifs integer;
    nb_sku_manquants integer;
BEGIN
    IF p_client_id IS NULL OR length(btrim(p_client_id)) NOT BETWEEN 1 AND 200
       OR p_date_facture IS NULL
       OR p_date_facture > CURRENT_DATE
       OR p_sku_ids IS NULL
       OR cardinality(p_sku_ids) NOT BETWEEN 1 AND 200
       OR EXISTS (
           SELECT 1 FROM unnest(p_sku_ids) AS entree(sku)
           WHERE entree.sku IS NULL OR length(btrim(entree.sku))=0
       )
       OR (SELECT count(DISTINCT entree.sku) FROM unnest(p_sku_ids) entree(sku))
          <> cardinality(p_sku_ids)
    THEN
       RAISE EXCEPTION 'Précontrôle fiscal : arguments invalides'
         USING ERRCODE='22023';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.clients c WHERE c.client_id=p_client_id
        AND upper(btrim(coalesce(c.actif,''))) IN ('OUI','TRUE','YES','1')
    ) THEN
        RETURN jsonb_build_object(
            'statut','A_BLOQUER','motif','CLIENT_INACTIF_OU_INCONNU',
            'autorise_facturation',false);
    END IF;

    SELECT count(*) INTO nb_sku_inactifs
    FROM unnest(p_sku_ids) AS entree(sku)
    LEFT JOIN public.sku_conditionnement s ON s.sku_id=entree.sku
    WHERE s.sku_id IS NULL
       OR upper(btrim(coalesce(s.actif,''))) NOT IN ('OUI','TRUE','YES','1');
    IF nb_sku_inactifs>0 THEN
        RETURN jsonb_build_object(
            'statut','A_BLOQUER','motif','SKU_INACTIF_OU_INCONNU',
            'autorise_facturation',false);
    END IF;

    -- Un dossier révoqué ou encore en attente applicable à la date
    -- interdit toute présomption de 0 %. Plus d'un dossier = ambiguïté.
    SELECT count(*) INTO nb_dossiers
    FROM public.erp_exonerations_tva_clients e
    WHERE e.client_id=p_client_id
      AND e.date_effet<=p_date_facture AND e.date_fin>=p_date_facture;
    IF nb_dossiers=0 THEN
        RETURN jsonb_build_object(
            'statut','AUCUN_DOSSIER','motif','AUCUNE_PREUVE_ENREGISTREE',
            'autorise_facturation',false);
    END IF;
    IF nb_dossiers<>1 THEN
        RETURN jsonb_build_object(
            'statut','A_BLOQUER','motif','ATTESTATIONS_CONCURRENTES',
            'autorise_facturation',false);
    END IF;
    SELECT * INTO STRICT d
    FROM public.erp_exonerations_tva_clients e
    WHERE e.client_id=p_client_id
      AND e.date_effet<=p_date_facture AND e.date_fin>=p_date_facture;

    IF d.statut<>'VALIDEE'
       OR d.date_validation IS NULL
       OR d.date_validation>p_date_facture
       OR d.date_verification IS NULL
       OR d.date_verification>p_date_facture
       OR d.valide_par IS NULL
       OR d.cree_par IS NULL
       OR d.valide_par=d.cree_par
       OR nullif(btrim(coalesce(d.reference_avis_validation,'')),'') IS NULL
       OR nullif(btrim(coalesce(d.reference_piece_interne,'')),'') IS NULL
    THEN
        RETURN jsonb_build_object(
            'statut','A_BLOQUER','motif','ATTESTATION_NON_HOMOLOGUEE',
            'autorise_facturation',false);
    END IF;

    -- La couverture doit être complète pour le panier soumis. Les
    -- factures mixtes 19 %/0 % demandent un calcul par ligne homologué.
    SELECT count(*) INTO nb_sku_manquants
    FROM unnest(p_sku_ids) AS entree(sku)
    WHERE NOT EXISTS (
        SELECT 1 FROM public.erp_exonerations_tva_skus x
        WHERE x.attestation_id=d.attestation_id AND x.sku_id=entree.sku
    );
    IF nb_sku_manquants>0 THEN
        RETURN jsonb_build_object(
            'statut','A_BLOQUER','motif','PORTEE_SKU_PARTIELLE',
            'autorise_facturation',false);
    END IF;

    RETURN jsonb_build_object(
        'statut','PRECONTROLE_OK',
        'motif','ATTESTATION_ET_PORTEE_VERIFIEES',
        'attestation_id',d.attestation_id,
        'reference_attestation',d.reference_attestation,
        'date_validation',d.date_validation,
        'nombre_sku',cardinality(p_sku_ids),
        'autorise_facturation',false);
END;
$fn$;

REVOKE ALL PRIVILEGES ON FUNCTION
 public.erp_exoneration_tva_precontrole_vente(text,text[],date)
 FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION
 public.erp_exoneration_tva_precontrole_vente(text,text[],date)
 TO service_role;

DO $verify$
BEGIN
 IF has_function_privilege(
      'anon','public.erp_exoneration_tva_precontrole_vente(text,text[],date)','EXECUTE')
    OR has_function_privilege(
      'authenticated','public.erp_exoneration_tva_precontrole_vente(text,text[],date)','EXECUTE')
    OR NOT has_function_privilege(
      'service_role','public.erp_exoneration_tva_precontrole_vente(text,text[],date)','EXECUTE')
 THEN
   RAISE EXCEPTION 'Précontrôle fiscal exposé aux rôles navigateur';
 END IF;
END;
$verify$;
COMMIT;
