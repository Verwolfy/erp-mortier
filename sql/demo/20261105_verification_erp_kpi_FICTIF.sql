-- Contrôle lecture seule du jeu fictif ERP du 05/11/2026.
-- Les chiffres sont des scénarios de test, pas des résultats comptables réels.
DO $test$
DECLARE v_bad integer;
BEGIN
  SELECT count(*) INTO v_bad FROM (
    SELECT 1 WHERE (SELECT count(*) FROM public.clients WHERE client_id LIKE 'DEMO26_%')<>2
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.factures WHERE facture_id LIKE 'DEMO26_%')<>2
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.pipeline WHERE opportunite_id LIKE 'DEMO26_%')<>3
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.reglements WHERE reglement_id LIKE 'DEMO26_%')<>2
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.scf_pieces WHERE reference LIKE 'DEMO26_%' AND statut='BROUILLON')<>1
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.paie_bulletins_v2 WHERE bulletin_id='90000000-0026-4026-8026-000000000001' AND statut='PREPARE')<>1
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.erp_sku_fiscalite WHERE sku_id LIKE 'DEMO26_%' AND statut='A_VALIDER')<>2
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.ordres_fabrication WHERE of_id LIKE 'DEMO26_%')<>2
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.sku_conditionnement WHERE sku_id LIKE 'DEMO26_%')<>2
    UNION ALL SELECT 1 WHERE (SELECT count(*) FROM public.fiches_de_paie WHERE fiche_paie_id LIKE 'DEMO26_%')<>1
    UNION ALL SELECT 1 WHERE (SELECT coalesce(sum(montant_ht),0) FROM public.factures WHERE facture_id LIKE 'DEMO26_%' AND statut='VALIDE' AND date BETWEEN '2026-11-01' AND '2026-11-30')<>16000
    UNION ALL SELECT 1 WHERE (SELECT coalesce(sum(valeur_estimee*probabilite_pct/100),0) FROM public.pipeline WHERE opportunite_id LIKE 'DEMO26_%' AND statut='En Négociation')<>300000
    UNION ALL SELECT 1 WHERE (SELECT coalesce(sum(quantite_disponible*cmp_actuel),0) FROM public.stock_actuel WHERE mp_id LIKE 'DEMO26_%')<>63000
    UNION ALL SELECT 1 WHERE (SELECT coalesce(sum(quantite_disponible*cout_revient),0) FROM public.stock_actuel_pf WHERE sku_id LIKE 'DEMO26_%')<>270000
  ) failed;
  IF v_bad<>0 THEN RAISE EXCEPTION '% contrôles démo échoués',v_bad; END IF;
END $test$;
SELECT 'CONTROLES_DEMO_OK' AS resultat;
