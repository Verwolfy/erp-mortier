-- ERP-057B : contrôle obligatoire des lots aux transitions de campagne.
-- La validation d'un constat n'est jamais un ajustement de stock.
BEGIN;
CREATE OR REPLACE FUNCTION public.erp_inventory_lot_transition_guard()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $body$
DECLARE v_invalid integer;
BEGIN
 IF NEW.statut IS NOT DISTINCT FROM OLD.statut THEN RETURN NEW; END IF;
 IF OLD.statut='OUVERT' AND NEW.statut='SOUMIS' THEN
   SELECT count(*) INTO v_invalid
   FROM public.erp_inventaire_lots
   WHERE inventaire_id=OLD.inventaire_id AND quantite_comptee IS NULL;
   IF v_invalid>0 THEN
    RAISE EXCEPTION 'Comptage des lots incomplet : % lignes',v_invalid USING ERRCODE='23514';
   END IF;
 ELSIF OLD.statut='SOUMIS' AND NEW.statut IN ('SANS_ECART','ECARTS_A_QUALIFIER') THEN
   -- Une validation est interdite si un lot est modifié, supprimé ou ajouté
   -- depuis la photographie de la campagne.
   SELECT count(*) INTO v_invalid
   FROM public.erp_inventaire_lots il
   LEFT JOIN public.lots l ON l.lot_id=il.lot_id
   WHERE il.inventaire_id=OLD.inventaire_id
     AND (l.lot_id IS NULL
      OR l.type_item IS DISTINCT FROM il.type_article
      OR l.item_id IS DISTINCT FROM il.article_id
      OR l.quantite_restante IS DISTINCT FROM il.quantite_theorique
      OR l.statut IS DISTINCT FROM il.statut_snapshot
      OR l.date_peremption IS DISTINCT FROM il.date_peremption_snapshot
      OR il.quantite_comptee IS NULL);
   IF v_invalid>0 THEN
    RAISE EXCEPTION 'Lots modifiés ou non comptés depuis la photographie' USING ERRCODE='40001';
   END IF;
   SELECT count(*) INTO v_invalid FROM public.lots l
   WHERE (OLD.categorie='TOUS' OR l.type_item=OLD.categorie)
     AND NOT EXISTS(SELECT 1 FROM public.erp_inventaire_lots il
         WHERE il.inventaire_id=OLD.inventaire_id AND il.lot_id=l.lot_id);
   IF v_invalid>0 THEN
    RAISE EXCEPTION 'Nouveaux lots depuis la photographie' USING ERRCODE='40001';
   END IF;
   -- Aucune référence avec stock positif ne peut être dite réconciliée
   -- lorsque les lots ne couvrent pas la quantité théorique.
   SELECT count(*) INTO v_invalid
   FROM public.erp_inventaire_lignes il
   LEFT JOIN LATERAL (
     SELECT coalesce(sum(l.quantite_theorique),0) as qty,
            coalesce(sum(l.quantite_comptee),0) as qty_counted,
            count(*) as n
     FROM public.erp_inventaire_lots l
     WHERE l.inventaire_id=il.inventaire_id
       AND l.type_article=il.type_article
       AND l.article_id=il.article_id
   ) ls ON TRUE
   WHERE il.inventaire_id=OLD.inventaire_id
     AND (ls.qty IS DISTINCT FROM il.quantite_theorique
          OR (ls.n>0 AND ls.qty_counted IS DISTINCT FROM il.quantite_comptee));
   IF v_invalid>0 THEN
    RAISE EXCEPTION 'Lots non réconciliés aux articles (% références)',v_invalid
      USING ERRCODE='23514';
   END IF;
 ELSE
   RAISE EXCEPTION 'Transition inventaire interdite' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $body$;
DROP TRIGGER IF EXISTS erp_inventory_lot_transition_guard ON public.erp_inventaires;
CREATE TRIGGER erp_inventory_lot_transition_guard
BEFORE UPDATE OF statut ON public.erp_inventaires
FOR EACH ROW EXECUTE FUNCTION public.erp_inventory_lot_transition_guard();
REVOKE ALL ON FUNCTION public.erp_inventory_lot_transition_guard()
 FROM PUBLIC,anon,authenticated;
COMMIT;
