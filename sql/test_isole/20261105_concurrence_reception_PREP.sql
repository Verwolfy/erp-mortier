-- TEST UNIQUEMENT: erp-mortier-test ffuhbmcfyexsbjwhryvj.
-- Fixtures temporaires, jamais sur la base de production.
BEGIN;
SET LOCAL statement_timeout='30s';
DO $g$ BEGIN
 IF EXISTS (SELECT 1 FROM public.commandes_achats WHERE commande_achat_id='IT26_RACE_PO')
 OR EXISTS (SELECT 1 FROM public.matieres_premieres WHERE mp_id='IT26_RACE_MP')
 THEN RAISE EXCEPTION 'Fixture test déjà présente : arrêt'; END IF;
END $g$;
INSERT INTO public.fournisseurs(fournisseur_id,nom,actif) VALUES
 ('IT26_RACE_FOU','[TEST] Fournisseur concurrency','OUI');
INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
VALUES ('IT26_RACE_MP','[TEST] MP concurrente','Granulat','kg','OUI');
SET LOCAL ROLE service_role;
SELECT public.erp_create_purchase_order(
 'IT26_RACE_CREATE','IT26_RACE_PO','IT26_RACE_FOU','MP','DZD',1,
 'VIREMENT','30 JOURS','2026-11-30',
 '[{"ligne_achat_id":"IT26_RACE_POL","mp_id":"IT26_RACE_MP","unite_cond":"kg","qte_cond":10,"qte_totale":10,"prix_unitaire":5,"total_devise":50}]'::jsonb);
RESET ROLE;
COMMIT;
