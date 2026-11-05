-- EXCLUSIVEMENT erp-mortier-test, projet ffuhbmcfyexsbjwhryvj.
-- VRAIES RPC, y compris commandes, stocks, factures, règlement et lettrage.
-- Aucune écriture durable : ROLLBACK et GRANT éphémères.
BEGIN;
SET LOCAL statement_timeout='45s';
GRANT UPDATE ON public.clients, public.produits, public.sku_conditionnement,
  public.lignes_commande_ventes, public.lignes_bons_livraison,
  public.lignes_facture, public.mouvements_pf,
  public.erp_sales_order_creations, public.erp_sales_outbox,
  public.ecritures_comptables, public.lettrage TO service_role;
INSERT INTO public.clients(client_id,nom,actif)
VALUES ('IT26_SALE_CLIENT','[TEST] Client essai transactions','OUI');
INSERT INTO public.produits(pf_id,nom,categorie_pf,unite_production,actif)
VALUES ('IT26_SALE_PF','[TEST] Produit vente','Mortier','KG','OUI');
INSERT INTO public.sku_conditionnement
(sku_id,pf_id,format,poids_net,unite_vente,facteur_conversion,prix_vente_defaut,actif)
VALUES ('IT26_SALE_SKU','IT26_SALE_PF','SAC 1KG',1,'SAC',1,20,'OUI');
SET LOCAL ROLE service_role;
DO $test$
DECLARE
  v_order jsonb; v_replay jsonb; v_ship jsonb;
  v_draft jsonb; v_validate jsonb;
  v_cash jsonb; v_counter jsonb; v_payment jsonb; v_alloc jsonb;
  v_order_id text; v_invoice_id text; v_cash_id text; v_counter_id text; v_pay_id text;
  v_lines jsonb:='[{"sku_id":"IT26_SALE_SKU","quantite":"2","prix_unitaire":"20"}]'::jsonb;
  v_ship_payload jsonb;
  v_invoice_payload jsonb;
  v_payment_payload jsonb;
  v_alloc_payload jsonb;
  v_attempted boolean;
BEGIN
  PERFORM public.erp_apply_stock_movement(
    'IT26_SALE_STOCK','PF','ENTREE','IT26_SALE_SKU',2,5,'[TEST] Stock PF',NULL);
  v_order:=public.erp_create_sales_order('IT26_SALES_ORDER','IT26_SALE_CLIENT','2026-11-05',v_lines);
  v_replay:=public.erp_create_sales_order('IT26_SALES_ORDER','IT26_SALE_CLIENT','2026-11-05',v_lines);
  IF v_order IS DISTINCT FROM v_replay OR v_order->>'statut'<>'EN_ATTENTE' THEN
    RAISE EXCEPTION 'Commande client non idempotente'; END IF;
  v_order_id:=v_order->>'commande_vente_id';
  BEGIN
    PERFORM public.erp_create_sales_order(
      'IT26_SALES_ORDER','IT26_SALE_CLIENT','2026-11-05',
      '[{"sku_id":"IT26_SALE_SKU","quantite":"3","prix_unitaire":"20"}]'::jsonb);
    RAISE EXCEPTION 'Commande contradictoire autorisée';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  v_ship_payload:=jsonb_build_object(
    'commande_vente_id',v_order_id,'transporteur','[TEST] Transport','zone','TEST',
    'lignes',jsonb_build_array(jsonb_build_object('sku_id','IT26_SALE_SKU','quantite_livree','2')));
  v_ship:=public.erp_sale_transaction('SHIP','IT26_SALE_SHIP',v_ship_payload);
  v_replay:=public.erp_sale_transaction('SHIP','IT26_SALE_SHIP',v_ship_payload);
  IF v_ship IS DISTINCT FROM v_replay OR
     (SELECT quantite_disponible FROM public.stock_actuel_pf WHERE sku_id='IT26_SALE_SKU') IS DISTINCT FROM 0
  THEN RAISE EXCEPTION 'Livraison double ou stock incorrect'; END IF;
  BEGIN
    PERFORM public.erp_sale_transaction('SHIP','IT26_SALE_SHIP',
       jsonb_set(v_ship_payload,'{zone}','"DIFFERENTE"'::jsonb));
    RAISE EXCEPTION 'Livraison contradictoire autorisée';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  v_invoice_payload:=jsonb_build_object(
    'client_id','IT26_SALE_CLIENT','date_echeance','2026-11-30',
    'remise_globale','0','paiement_especes',false,
    'type_facture','FactureClient','facture_origine_id','',
    'montant_ht','40','montant_tva','7.60','montant_timbre','0',
    'montant_ttc','47.60',
    'lignes',jsonb_build_array(jsonb_build_object(
      'sku_id','IT26_SALE_SKU','quantite','2','prix_unitaire','20',
      'remise_ligne','0','total_ligne_ht','40')));
  v_draft:=public.erp_sale_transaction('DRAFT','IT26_SALE_DRAFT',v_invoice_payload);
  v_replay:=public.erp_sale_transaction('DRAFT','IT26_SALE_DRAFT',v_invoice_payload);
  IF v_draft IS DISTINCT FROM v_replay THEN RAISE EXCEPTION 'Brouillon non idempotent'; END IF;
  v_invoice_id:=v_draft->>'facture_id';
  v_validate:=public.erp_sale_transaction('VALIDATE','IT26_SALE_VALIDATE',
    jsonb_build_object('facture_id',v_invoice_id));
  v_replay:=public.erp_sale_transaction('VALIDATE','IT26_SALE_VALIDATE',
    jsonb_build_object('facture_id',v_invoice_id));
  IF v_validate IS DISTINCT FROM v_replay OR
     (SELECT statut FROM public.factures WHERE facture_id=v_invoice_id)<>'VALIDE'
  THEN RAISE EXCEPTION 'Validation facture non idempotente'; END IF;
  BEGIN
    PERFORM public.erp_sale_transaction('VALIDATE','IT26_SALE_VALIDATE_AGAIN',
      jsonb_build_object('facture_id',v_invoice_id));
    RAISE EXCEPTION 'Deuxième validation avec nouvel ID acceptée';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  v_cash:=public.erp_finance_transaction('ACCOUNT','IT26_ACC_CASH',
    '{"nom_compte":"[TEST] Banque","type_compte":"Banque","numero_compte":"IT26_BANK_NO","solde_initial":"0"}'::jsonb);
  v_replay:=public.erp_finance_transaction('ACCOUNT','IT26_ACC_CASH',
    '{"nom_compte":"[TEST] Banque","type_compte":"Banque","numero_compte":"IT26_BANK_NO","solde_initial":"0"}'::jsonb);
  IF v_cash IS DISTINCT FROM v_replay THEN RAISE EXCEPTION 'Compte Banque non idempotent'; END IF;
  v_counter:=public.erp_finance_transaction('ACCOUNT','IT26_ACC_CLIENT',
    '{"nom_compte":"[TEST] Compte client","type_compte":"Tiers client","numero_compte":"IT26_CLIENT_NO","solde_initial":"0"}'::jsonb);
  v_cash_id:=v_cash->>'compte_id'; v_counter_id:=v_counter->>'compte_id';
  v_payment_payload:=jsonb_build_object(
    'date_reglement','2026-11-05','type_flux','ENCAISSEMENT',
    'partenaire_id','IT26_SALE_CLIENT','compte_id',v_cash_id,
    'contrepartie_compte_id',v_counter_id,'mode_paiement','VIREMENT',
    'reference_trace','IT26_BANK_TRACE','montant_total','47.60');
  v_payment:=public.erp_finance_transaction('PAYMENT','IT26_PAYMENT',v_payment_payload);
  v_replay:=public.erp_finance_transaction('PAYMENT','IT26_PAYMENT',v_payment_payload);
  IF v_payment IS DISTINCT FROM v_replay THEN RAISE EXCEPTION 'Paiement non idempotent'; END IF;
  v_pay_id:=v_payment->>'reglement_id';
  BEGIN
    PERFORM public.erp_finance_transaction('PAYMENT','IT26_PAYMENT_DUP',v_payment_payload);
    RAISE EXCEPTION 'Doublon référence bancaire accepté';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  v_alloc_payload:=jsonb_build_object(
    'reglement_id',v_pay_id,'document_id',v_invoice_id,
    'type_document','FactureClient','montant_applique','47.60');
  v_alloc:=public.erp_finance_transaction('ALLOCATE','IT26_ALLOC',v_alloc_payload);
  v_replay:=public.erp_finance_transaction('ALLOCATE','IT26_ALLOC',v_alloc_payload);
  IF v_alloc IS DISTINCT FROM v_replay THEN RAISE EXCEPTION 'Lettrage non idempotent'; END IF;
  BEGIN
    PERFORM public.erp_finance_transaction('ALLOCATE','IT26_ALLOC_DUP',v_alloc_payload);
    RAISE EXCEPTION 'Sur-lettrage accepté';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  IF (SELECT count(*) FROM public.commandes_ventes WHERE commande_vente_id=v_order_id)<>1
    OR (SELECT count(*) FROM public.bons_livraison WHERE commande_vente_id=v_order_id)<>1
    OR (SELECT count(*) FROM public.factures WHERE facture_id=v_invoice_id)<>1
    OR (SELECT montant_paye FROM public.factures WHERE facture_id=v_invoice_id) IS DISTINCT FROM 47.60
    OR (SELECT montant_alloue FROM public.reglements WHERE reglement_id=v_pay_id) IS DISTINCT FROM 47.60
    OR (SELECT count(*) FROM public.lettrage WHERE reglement_id=v_pay_id)<>1
    OR (SELECT count(*) FROM public.ecritures_comptables WHERE document_source_id=v_pay_id)<>2
  THEN RAISE EXCEPTION 'État final vente / règlement / lettrage incorrect'; END IF;
END
$test$;
RESET ROLE;
SELECT 'VENTE_FACTURATION_PAIEMENT_LETTRAGE_IDEMPOTENCE_OK' AS resultat;
ROLLBACK;
