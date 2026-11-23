-- ERP-061 PREPARATION (NON APPLIQUEE à Supabase principal).
-- Le paiement fournisseur est critique : soumettre ce correctif à approbation.
-- Conserve le corps de la RPC installé et ses autres règles fiscales/SCF.
-- Fix: branches client/fournisseur indépendantes; facture fournisseur BROUILLON non payable.
BEGIN;
DO $erp061$
DECLARE
 v_def text;
 v_new text;
 v_old_filter text := 'OR upper(btrim(coalesce(v_invoice.statut_paiement,''''))) IN ('''',''ANNULE'',''REJETE'',''PAYEE'')';
 v_new_filter text := 'OR upper(btrim(coalesce(v_invoice.statut_paiement,''''))) NOT IN (''NON_PAYEE'',''PARTIELLE'')';
BEGIN
 SELECT pg_get_functiondef('public.erp_finance_transaction(text,text,jsonb)'::regprocedure)
 INTO STRICT v_def;
 -- Fonction déjà corrigée : aucun changement nécessaire.
 IF position(v_new_filter IN v_def)>0
    AND position('IF v_doc_type=''FactureClient'' THEN' IN v_def)>0
    AND position('v_invoice_applied IS DISTINCT FROM coalesce(v_invoice.montant_paye,0) THEN' IN v_def)>0
 THEN RETURN; END IF;
 IF position(v_old_filter IN v_def)=0 OR
    position('IF v_doc_type=''FactureClient'' AND' IN v_def)=0 OR
    position('v_letter_id := ''LET-''' IN v_def)=0
 THEN RAISE EXCEPTION 'Version SQL Finance inconnue : patch refusé sans revue'
  USING ERRCODE='23514'; END IF;
 v_new:=replace(v_def,v_old_filter,v_new_filter);
 v_new:=regexp_replace(v_new,
  $rx$IF v_doc_type='FactureClient' AND[[:space:]]+v_invoice_applied IS DISTINCT FROM coalesce[(]v_invoice[.]montant_paye,0[)] THEN$rx$,
  E'IF v_doc_type=''FactureClient'' THEN\n            IF v_invoice_applied IS DISTINCT FROM coalesce(v_invoice.montant_paye,0) THEN');
 v_new:=regexp_replace(v_new,
  $rx$RAISE EXCEPTION 'Facture client : montant payé incohérent avec les lettrages' USING ERRCODE='23514';[[:space:]]+END IF;[[:space:]]+v_letter_id :=$rx$,
  E'RAISE EXCEPTION ''Facture client : montant payé incohérent avec les lettrages'' USING ERRCODE=''23514'';\n            END IF;\n        END IF;\n        v_letter_id :=');
 IF v_new=v_def OR position(v_new_filter IN v_new)=0
    OR position('IF v_doc_type=''FactureClient'' AND' IN v_new)>0
    OR position('IF v_doc_type=''FactureClient'' THEN' IN v_new)=0
 THEN RAISE EXCEPTION 'Réécriture SQL financière partielle : refus'
  USING ERRCODE='23514'; END IF;
 EXECUTE v_new;
END $erp061$;
REVOKE ALL ON FUNCTION public.erp_finance_transaction(text,text,jsonb)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_finance_transaction(text,text,jsonb)
 TO service_role;
COMMIT;
