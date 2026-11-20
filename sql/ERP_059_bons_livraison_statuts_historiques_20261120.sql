-- ERP-059 — correction ciblée de l'historique BL et de la garde anti-doublon.
-- Le changement initial a été appliqué à Supabase le 20/11/2026.
-- Forme de migration rejouable ci-dessous : aucune reproduction des fonctions
-- de facturation, des taux fiscaux ou des règles de timbre existants.
-- La fonction courante est conservée et seule la branche SHIP est renforcée.
BEGIN;

DO $erp059$
DECLARE
 v_def text;
 v_old text := 'AND b.statut=''EXPEDIE'' AND l.sku_id=v_sku.sku_id';
 v_new text := 'AND b.statut IN (''EXPEDIE'',''LIVRE'',''LIVREE'',''TERMINE'') AND l.sku_id=v_sku.sku_id';
 v_marker text := '-- Valider les cumul avant tout débit de stock.';
 v_guard text := $guard$
 -- Un BL dont l'état historique est inconnu peut masquer des quantités livrées.
 IF EXISTS (
    SELECT 1 FROM public.bons_livraison b
    WHERE b.commande_vente_id=v_order.commande_vente_id
      AND (b.statut IS NULL OR b.statut NOT IN
        ('EXPEDIE','LIVRE','LIVREE','TERMINE',
         'ANNULE','ANNULEE','BROUILLON','DRAFT'))
 ) THEN
    RAISE EXCEPTION 'Statut historique de BL non réconcilié : revue requise'
      USING ERRCODE='23514';
 END IF;
 $guard$;
BEGIN
 SELECT pg_get_functiondef('public.erp_sale_transaction(text,text,jsonb)'::regprocedure)
 INTO STRICT v_def;

 -- Idempotence pour environnements où la correction est déjà présente.
 IF position(v_new IN v_def) > 0
   AND position('Statut historique de BL non réconcilié' IN v_def) > 0 THEN
    RETURN;
 END IF;
 IF position(v_old IN v_def) = 0
   OR position(v_marker IN v_def) = 0
   OR position('ELSIF p_action=''SHIP''' IN v_def) = 0 THEN
   RAISE EXCEPTION 'RPC ventes inconnue : patch BL refusé sans revue'
     USING ERRCODE='23514';
 END IF;
 -- Remplacer uniquement la sélection de lignes BL et ajouter la garde
 -- avant le contrôle des cumuls. Aucun recalcul fiscal n'est introduit.
 v_def := replace(v_def,v_old,v_new);
 v_def := replace(v_def,v_marker,v_guard || E'\n        ' || v_marker);
 EXECUTE v_def;
END $erp059$;

REVOKE ALL ON FUNCTION public.erp_sale_transaction(text,text,jsonb)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.erp_sale_transaction(text,text,jsonb)
 TO service_role;
COMMIT;
