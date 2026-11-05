-- EXCLUSIVEMENT erp-mortier-test (ffuhbmcfyexsbjwhryvj).
-- Toutes les écritures sont annulées ; ne jamais exécuter sur production.
BEGIN;
SET LOCAL statement_timeout = '40s';
INSERT INTO public.fournisseurs(fournisseur_id, nom, actif)
VALUES ('IT26_FOU','[TEST] Fournisseur transactionnel','OUI');
INSERT INTO public.matieres_premieres(mp_id,nom,categorie_mp,unite_stock,actif)
VALUES ('IT26_MP','[TEST] Matière transactionnelle','Granulat','kg','OUI');
SET LOCAL ROLE service_role;
DO $test$
DECLARE
  lignes jsonb := '[{"ligne_achat_id":"IT26_POL","mp_id":"IT26_MP","unite_cond":"kg","qte_cond":10,"qte_totale":10,"prix_unitaire":5,"total_devise":50}]'::jsonb;
  rec1 jsonb := '[{"ligne_br_id":"IT26_GRL1","mp_id":"IT26_MP","quantite_recue":4,"prix_unitaire":5}]'::jsonb;
  rec2 jsonb := '[{"ligne_br_id":"IT26_GRL2","mp_id":"IT26_MP","quantite_recue":6,"prix_unitaire":5}]'::jsonb;
  a jsonb; b jsonb; c jsonb; err text;
  stock numeric;
BEGIN
  a := public.erp_create_purchase_order(
    'IT26_OP_PURCHASE','IT26_PO','IT26_FOU','MP','DZD',1,'VIREMENT','30 JOURS','2026-11-30',lignes);
  b := public.erp_create_purchase_order(
    'IT26_OP_PURCHASE','IT26_PO_RETRY','IT26_FOU','MP','DZD',1,'VIREMENT','30 JOURS','2026-11-30',lignes);
  IF a IS DISTINCT FROM b THEN RAISE EXCEPTION 'Achat non idempotent'; END IF;
  BEGIN
    PERFORM public.erp_create_purchase_order(
      'IT26_OP_PURCHASE','IT26_PO_RETRY','IT26_FOU','MP','DZD',1,'VIREMENT','30 JOURS','2026-11-30',
      '[{"ligne_achat_id":"IT26_POL","mp_id":"IT26_MP","unite_cond":"kg","qte_cond":11,"qte_totale":11,"prix_unitaire":5,"total_devise":55}]'::jsonb);
    RAISE EXCEPTION 'Réutilisation contradictoire acceptée';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  a := public.erp_receive_purchase_order(
    'IT26_OP_RECEIPT1','IT26_GR1','IT26_PO','2026-11-05','OUI','[TEST] partiel','2027-11-05',rec1);
  b := public.erp_receive_purchase_order(
    'IT26_OP_RECEIPT1','IT26_GR1_RETRY','IT26_PO','2026-11-05','OUI','[TEST] partiel','2027-11-05',rec1);
  IF a IS DISTINCT FROM b OR a->>'statut_commande'<>'PARTIELLEMENT_RECEPTIONNE'
  THEN RAISE EXCEPTION 'Réception partielle non idempotente'; END IF;
  c := public.erp_receive_purchase_order(
    'IT26_OP_RECEIPT2','IT26_GR2','IT26_PO','2026-11-05','OUI','[TEST] solde','2027-11-05',rec2);
  IF c->>'statut_commande'<>'RECEPTIONNE'
  THEN RAISE EXCEPTION 'Réception finale incomplète'; END IF;
  b := public.erp_receive_purchase_order(
    'IT26_OP_RECEIPT2','IT26_GR2_RETRY','IT26_PO','2026-11-05','OUI','[TEST] solde','2027-11-05',rec2);
  IF c IS DISTINCT FROM b THEN RAISE EXCEPTION 'Réception finale non idempotente'; END IF;
  BEGIN
    PERFORM public.erp_receive_purchase_order(
      'IT26_OP_RECEIPT3','IT26_GR_OVER','IT26_PO','2026-11-05','OUI','[TEST] trop','2027-11-05',rec1);
    RAISE EXCEPTION 'Sur-réception acceptée';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  SELECT quantite_disponible INTO stock FROM public.stock_actuel WHERE mp_id='IT26_MP';
  IF stock IS DISTINCT FROM 10
      OR (SELECT count(*) FROM public.commandes_achats WHERE commande_achat_id='IT26_PO')<>1
      OR (SELECT count(*) FROM public.bons_reception WHERE commande_achat_id='IT26_PO')<>2
      OR (SELECT count(*) FROM public.mouvements WHERE mp_id='IT26_MP' AND type_mouvement='ENTREE')<>2
      OR (SELECT statut FROM public.commandes_achats WHERE commande_achat_id='IT26_PO')<>'RECEPTIONNE'
  THEN RAISE EXCEPTION 'Invariant achat/réception/stock violé'; END IF;
END
$test$;
RESET ROLE;
SELECT 'ACHAT_RECEPTION_TRANSITIONS_IDEMPOTENCE_OK' AS resultat;
ROLLBACK;
