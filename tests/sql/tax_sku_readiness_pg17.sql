-- Diagnostic technique ERP-047 : uniquement sur PostgreSQL 17 jetable.
BEGIN;
INSERT INTO public.sku_conditionnement(sku_id,actif)
VALUES('SKU-SIM-MANQUANT','OUI');

DO $test$
DECLARE got text;
BEGIN
    SELECT etat_technique INTO got FROM public.erp_tva_sku_readiness('2026-11-09')
     WHERE sku_id='SKU-SIM-N';
    IF got IS DISTINCT FROM 'PRET_TECHNIQUEMENT' THEN
        RAISE EXCEPTION 'Normal valide technique : %',got;
    END IF;
    SELECT etat_technique INTO got FROM public.erp_tva_sku_readiness('2026-11-09')
     WHERE sku_id='SKU-SIM-R';
    IF got IS DISTINCT FROM 'PRET_TECHNIQUEMENT' THEN
        RAISE EXCEPTION 'Réduit valide technique : %',got;
    END IF;
    SELECT etat_technique INTO got FROM public.erp_tva_sku_readiness('2026-11-09')
     WHERE sku_id='SKU-SIM-UNVERIFIE';
    IF got IS DISTINCT FROM 'A_VALIDER' THEN
        RAISE EXCEPTION 'Version non validée : %',got;
    END IF;
    SELECT etat_technique INTO got FROM public.erp_tva_sku_readiness('2026-11-09')
     WHERE sku_id='SKU-SIM-EXO';
    IF got IS DISTINCT FROM 'HORS_MOTEUR_PILOTE' THEN
        RAISE EXCEPTION 'Exonération non prise en charge : %',got;
    END IF;
    SELECT etat_technique INTO got FROM public.erp_tva_sku_readiness('2026-11-09')
     WHERE sku_id='SKU-SIM-MANQUANT';
    IF got IS DISTINCT FROM 'SANS_FICHE' THEN
        RAISE EXCEPTION 'Fiche manquante : %',got;
    END IF;
    IF (SELECT count(*) FROM public.erp_tva_sku_readiness('2026-11-09') WHERE sku_id='SKU-SIM-INACTIF') <> 0 THEN
        RAISE EXCEPTION 'SKU inactif présent dans diagnostic';
    END IF;
    IF has_function_privilege('anon','public.erp_tva_sku_readiness(date)','EXECUTE')
       OR has_function_privilege('authenticated','public.erp_tva_sku_readiness(date)','EXECUTE')
       OR NOT has_function_privilege('service_role','public.erp_tva_sku_readiness(date)','EXECUTE') THEN
       RAISE EXCEPTION 'Droits diagnostic TVA incorrects';
    END IF;
END;
$test$;

SET LOCAL ROLE service_role;
DO $client$
DECLARE got text;
BEGIN
  SELECT etat_technique INTO got FROM public.erp_tva_sku_readiness('2026-11-09')
  WHERE sku_id='SKU-SIM-N';
  IF got IS DISTINCT FROM 'PRET_TECHNIQUEMENT' THEN
    RAISE EXCEPTION 'Diagnostic sous service_role non fonctionnel';
  END IF;
END;
$client$;
RESET ROLE;

INSERT INTO public.erp_sku_fiscalite(
   sku_id,date_effet,categorie_tva,code_parametre,statut
) VALUES ('SKU-SIM-N','2026-09-01',NULL,NULL,'A_VALIDER');
DO $conflict$
BEGIN
 IF (SELECT etat_technique FROM public.erp_tva_sku_readiness('2026-11-09')
      WHERE sku_id='SKU-SIM-N') IS DISTINCT FROM 'CONFLIT_VERSIONS' THEN
   RAISE EXCEPTION 'Chevauchement non détecté';
 END IF;
END;
$conflict$;

INSERT INTO public.parametres_reglementaires(
    code,valeur,unite,statut_juridique,niveau_confiance,date_effet,
    source,date_verification
) VALUES('TVA_TAUX_REDUIT',0.08,'fraction','a_confirmer','RECOUPEE',
         '2026-09-01','TAUX-FICTIF','2026-09-02');
DO $rate$
BEGIN
 IF (SELECT etat_technique FROM public.erp_tva_sku_readiness('2026-11-09')
      WHERE sku_id='SKU-SIM-R') IS DISTINCT FROM 'TAUX_A_VERIFIER' THEN
   RAISE EXCEPTION 'Taux TVA chevauchant non détecté';
 END IF;
END;
$rate$;
ROLLBACK;
