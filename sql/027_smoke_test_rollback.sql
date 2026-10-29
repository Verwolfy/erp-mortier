-- 027 : TEST UNIQUEMENT ; faux justificatif et aucun enregistrement conservé.
-- Exécuter comme administrateur SQL sur le projet de test.
BEGIN;
DO $smoke$
DECLARE
 acteur text;
 client text;
 sku text;
 op uuid := gen_random_uuid();
 entree jsonb;
 cree jsonb;
 repris jsonb;
 refused boolean;
BEGIN
 SELECT u.user_id INTO acteur
 FROM public.users u
 JOIN public.erp_security_authorities a ON a.user_id=u.user_id
 WHERE a.habilitation='SECURITY_MANAGER'
   AND a.actif IS TRUE AND a.retire_le IS NULL
   AND upper(btrim(coalesce(u.actif,''))) IN ('OUI','TRUE','YES','1')
 LIMIT 1;
 SELECT client_id INTO client FROM public.clients
 WHERE upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 ORDER BY client_id LIMIT 1;
 SELECT sku_id INTO sku FROM public.sku_conditionnement
 WHERE upper(btrim(coalesce(actif,''))) IN ('OUI','TRUE','YES','1')
 ORDER BY sku_id LIMIT 1;
 IF acteur IS NULL OR client IS NULL OR sku IS NULL THEN
    RAISE EXCEPTION 'Références de TEST absentes';
 END IF;

 entree:=jsonb_build_object(
   'client_id',client,'reference_attestation','FICTIF-ROLLBACK-027-'||op::text,
   'autorite_emettrice','AUTORITE-FICTIVE',
   'reference_piece_interne','PIECE-FICTIVE-TEST',
   'justification','AUCUNE VALEUR JURIDIQUE',
   'date_effet','2026-01-01','date_fin','2026-12-31',
   'sku_ids',jsonb_build_array(sku)
 );
 cree:=public.erp_exoneration_tva_action(acteur,'CREER_BROUILLON',op,entree);
 repris:=public.erp_exoneration_tva_action(acteur,'CREER_BROUILLON',op,entree);
 IF cree->>'statut'<>'A_VALIDER' OR repris->>'idempotent'<>'true'
     OR cree->>'attestation_id'<>repris->>'attestation_id' THEN
   RAISE EXCEPTION 'Brouillon ou idempotence non conformes';
 END IF;

 refused:=false;
 BEGIN
   PERFORM public.erp_exoneration_tva_action(
     acteur,'VALIDER',gen_random_uuid(),
     jsonb_build_object('attestation_id',cree->>'attestation_id',
       'date_verification','2026-10-29',
       'reference_avis_validation','AVIS-FICTIF',
       'verification_documentaire',true)
   );
 EXCEPTION WHEN insufficient_privilege THEN refused:=true;
 END;
 IF NOT refused THEN
   RAISE EXCEPTION 'Validation sans habilitation fiscale autorisée';
 END IF;

 refused:=false;
 BEGIN
   PERFORM public.erp_exoneration_tva_action(
     'IDENTITE-NON-HABILITEE','CREER_BROUILLON',gen_random_uuid(),entree
   );
 EXCEPTION WHEN insufficient_privilege THEN refused:=true;
 END;
 IF NOT refused THEN RAISE EXCEPTION 'Utilisateur non habilité accepté'; END IF;
 RAISE NOTICE 'SMOKE 027 OK : création, rejouabilité, refus sécurité ; ROLLBACK';
END;
$smoke$;
ROLLBACK;
