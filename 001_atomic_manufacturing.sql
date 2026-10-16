-- ERP Mortier: sous-système isolé; NE MODIFIE PAS les tables historiques.
-- Exécuter en environnement de test via Supabase migrations APRÈS revue DBA.
-- Les tables sont dans un schéma NON EXPOSE à PostgREST.
-- Utilise auth.uid() : requiert de véritables sessions Supabase Auth.
BEGIN;
CREATE SCHEMA IF NOT EXISTS erp_hardening;
REVOKE ALL ON SCHEMA erp_hardening FROM PUBLIC;
GRANT USAGE ON SCHEMA erp_hardening TO authenticated;

CREATE TABLE IF NOT EXISTS erp_hardening.company_members (
  company_id uuid NOT NULL,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('admin','inventory','production')),
  PRIMARY KEY (company_id, user_id)
);
CREATE TABLE IF NOT EXISTS erp_hardening.items (
  company_id uuid NOT NULL,
  item_code text NOT NULL CHECK (length(item_code) BETWEEN 1 AND 64),
  unit text NOT NULL CHECK (unit IN ('kg','L','u')),
  PRIMARY KEY (company_id, item_code)
);
CREATE TABLE IF NOT EXISTS erp_hardening.recipes (
  recipe_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  finished_item_code text NOT NULL,
  base_quantity numeric(24,6) NOT NULL CHECK (base_quantity > 0),
  status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','ARCHIVED')),
  FOREIGN KEY (company_id, finished_item_code) REFERENCES erp_hardening.items(company_id, item_code),
  UNIQUE (recipe_id, company_id)
);
CREATE TABLE IF NOT EXISTS erp_hardening.recipe_lines (
  recipe_id uuid NOT NULL,
  company_id uuid NOT NULL,
  item_code text NOT NULL,
  quantity numeric(24,6) NOT NULL CHECK (quantity > 0),
  PRIMARY KEY (recipe_id, item_code),
  FOREIGN KEY (recipe_id, company_id) REFERENCES erp_hardening.recipes(recipe_id, company_id) ON DELETE RESTRICT,
  FOREIGN KEY (company_id, item_code) REFERENCES erp_hardening.items(company_id, item_code)
);
CREATE TABLE IF NOT EXISTS erp_hardening.lots (
  lot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
  company_id uuid NOT NULL,
  item_code text NOT NULL,
  lot_code text NOT NULL CHECK (length(lot_code) BETWEEN 1 AND 64),
  remaining numeric(24,6) NOT NULL CHECK (remaining >= 0),
  unit_cost numeric(24,6) NOT NULL CHECK (unit_cost >= 0),
  received_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (company_id, item_code, lot_code),
  UNIQUE (company_id, item_code, lot_id),
  FOREIGN KEY (company_id, item_code) REFERENCES erp_hardening.items(company_id, item_code)
);
CREATE INDEX IF NOT EXISTS erp_lots_fifo ON erp_hardening.lots(company_id, item_code, receipt_seq) WHERE remaining > 0;
CREATE TABLE IF NOT EXISTS erp_hardening.operations (
  company_id uuid NOT NULL,
  operation_id uuid NOT NULL,
  action text NOT NULL CHECK (action IN ('RECEIPT','MANUFACTURE')),
  request jsonb NOT NULL,
  result jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, operation_id)
);
CREATE TABLE IF NOT EXISTS erp_hardening.movements (
  movement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  company_id uuid NOT NULL,
  operation_id uuid NOT NULL,
  item_code text NOT NULL,
  lot_id uuid NOT NULL,
  direction text NOT NULL CHECK (direction IN ('IN','OUT')),
  quantity numeric(24,6) NOT NULL CHECK (quantity > 0),
  unit_cost numeric(24,6) NOT NULL CHECK (unit_cost >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (company_id, operation_id) REFERENCES erp_hardening.operations(company_id, operation_id),
  FOREIGN KEY (company_id, item_code) REFERENCES erp_hardening.items(company_id, item_code),
  FOREIGN KEY (company_id, item_code, lot_id) REFERENCES erp_hardening.lots(company_id, item_code, lot_id)
);
CREATE INDEX IF NOT EXISTS erp_movements_order ON erp_hardening.movements(company_id, operation_id);

-- Défense supplémentaire : aucune lecture/écriture sur les tables via Data API.
REVOKE ALL ON ALL TABLES IN SCHEMA erp_hardening FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA erp_hardening FROM PUBLIC, anon, authenticated;
ALTER TABLE erp_hardening.company_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_hardening.items ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_hardening.recipes ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_hardening.recipe_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_hardening.lots ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_hardening.operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp_hardening.movements ENABLE ROW LEVEL SECURITY;

-- Immutabilité métier : pas de modification silencieuse d'une recette approuvée.
-- Les éditions de lignes verrouillent l'en-tête pour se sérialiser avec l'approbation.
CREATE OR REPLACE FUNCTION erp_hardening.guard_recipe() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'DRAFT' THEN
      RAISE EXCEPTION 'Approved/archived recipe cannot be deleted' USING ERRCODE='22023';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.status <> 'DRAFT' AND
     (NEW.recipe_id IS DISTINCT FROM OLD.recipe_id OR
      NEW.company_id IS DISTINCT FROM OLD.company_id OR
      NEW.finished_item_code IS DISTINCT FROM OLD.finished_item_code OR
      NEW.base_quantity IS DISTINCT FROM OLD.base_quantity OR
      NEW.status = 'DRAFT') THEN
    RAISE EXCEPTION 'Approved recipe is immutable' USING ERRCODE='22023';
  END IF;
  IF OLD.status = 'ARCHIVED' AND NEW.status <> 'ARCHIVED' THEN
    RAISE EXCEPTION 'Archived recipe is immutable' USING ERRCODE='22023';
  END IF;
  IF OLD.status <> 'APPROVED' AND NEW.status = 'APPROVED' AND
     NOT EXISTS (SELECT 1 FROM erp_hardening.recipe_lines WHERE recipe_id=NEW.recipe_id) THEN
    RAISE EXCEPTION 'Cannot approve empty recipe' USING ERRCODE='22023';
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS erp_guard_recipe ON erp_hardening.recipes;
CREATE TRIGGER erp_guard_recipe BEFORE UPDATE OR DELETE ON erp_hardening.recipes
FOR EACH ROW EXECUTE FUNCTION erp_hardening.guard_recipe();

CREATE OR REPLACE FUNCTION erp_hardening.guard_recipe_line() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
  v_recipe erp_hardening.recipes%ROWTYPE;
BEGIN
  IF TG_OP = 'UPDATE' AND
     (NEW.recipe_id <> OLD.recipe_id OR NEW.company_id <> OLD.company_id OR NEW.item_code <> OLD.item_code) THEN
    RAISE EXCEPTION 'Cannot move existing component between recipes' USING ERRCODE='22023';
  END IF;
  SELECT * INTO v_recipe FROM erp_hardening.recipes
  WHERE recipe_id = CASE WHEN TG_OP = 'DELETE' THEN OLD.recipe_id ELSE NEW.recipe_id END
  FOR UPDATE;
  IF NOT FOUND OR v_recipe.status <> 'DRAFT' THEN
    RAISE EXCEPTION 'Only draft recipe lines are editable' USING ERRCODE='22023';
  END IF;
  IF TG_OP <> 'DELETE' AND NEW.item_code = v_recipe.finished_item_code THEN
    RAISE EXCEPTION 'Finished item cannot be its own recipe input' USING ERRCODE='22023';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS erp_guard_recipe_line ON erp_hardening.recipe_lines;
CREATE TRIGGER erp_guard_recipe_line BEFORE INSERT OR UPDATE OR DELETE ON erp_hardening.recipe_lines
FOR EACH ROW EXECUTE FUNCTION erp_hardening.guard_recipe_line();

-- La fonction SEC DEFINER est dans le schéma non exposé, avec search_path vide.
-- Toutes les identités et permissions sont contrôlées DANS la base : pas d'ID user arbitraire.
CREATE OR REPLACE FUNCTION erp_hardening.receive_lot(
  p_company_id uuid, p_item_code text, p_lot_code text,
  p_quantity numeric, p_unit_cost numeric, p_operation_id uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  v_request jsonb;
  v_record erp_hardening.operations%ROWTYPE;
  v_lot_id uuid;
  v_result jsonb;
BEGIN
  IF auth.uid() IS NULL OR NOT EXISTS (
    SELECT 1 FROM erp_hardening.company_members
    WHERE company_id = p_company_id AND user_id = auth.uid()
      AND role IN ('admin', 'inventory', 'production')
  ) THEN
    RAISE EXCEPTION 'Access denied' USING ERRCODE = '42501';
  END IF;
  IF p_company_id IS NULL OR p_operation_id IS NULL OR
     p_item_code IS NULL OR length(p_item_code) NOT BETWEEN 1 AND 64 OR
     p_lot_code IS NULL OR length(p_lot_code) NOT BETWEEN 1 AND 64 OR
     p_quantity IS NULL OR p_quantity <= 0 OR p_quantity <> round(p_quantity, 6) OR
     p_unit_cost IS NULL OR p_unit_cost < 0 OR p_unit_cost <> round(p_unit_cost, 6) THEN
    RAISE EXCEPTION 'Invalid receipt request' USING ERRCODE = '22023';
  END IF;
  v_request := pg_catalog.jsonb_build_object('item',p_item_code,'lot',p_lot_code,
                'quantity',p_quantity,'unit_cost',p_unit_cost);
  INSERT INTO erp_hardening.operations(company_id,operation_id,action,request)
    VALUES(p_company_id,p_operation_id,'RECEIPT',v_request)
    ON CONFLICT DO NOTHING;
  IF NOT FOUND THEN
    SELECT * INTO STRICT v_record FROM erp_hardening.operations
      WHERE company_id=p_company_id AND operation_id=p_operation_id FOR UPDATE;
    IF v_record.action <> 'RECEIPT' OR v_record.request <> v_request OR v_record.result IS NULL THEN
      RAISE EXCEPTION 'Idempotency key conflict' USING ERRCODE = '23505';
    END IF;
    RETURN v_record.result;
  END IF;
  -- Verrouiller l'article avant de modifier un lot (même ordre de verrouillage qu'en production).
  PERFORM 1 FROM erp_hardening.items
     WHERE company_id=p_company_id AND item_code=p_item_code FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Unknown item' USING ERRCODE = '22023';
  END IF;
  INSERT INTO erp_hardening.lots(company_id,item_code,lot_code,remaining,unit_cost)
    VALUES(p_company_id,p_item_code,p_lot_code,p_quantity,p_unit_cost)
    RETURNING lot_id INTO v_lot_id;
  INSERT INTO erp_hardening.movements(company_id,operation_id,item_code,lot_id,direction,quantity,unit_cost)
    VALUES(p_company_id,p_operation_id,p_item_code,v_lot_id,'IN',p_quantity,p_unit_cost);
  v_result := pg_catalog.jsonb_build_object('status','ok','action','RECEIPT',
        'operation_id',p_operation_id,'lot_id',v_lot_id,'quantity',p_quantity);
  UPDATE erp_hardening.operations SET result=v_result
    WHERE company_id=p_company_id AND operation_id=p_operation_id;
  RETURN v_result;
END; $$;

CREATE OR REPLACE FUNCTION erp_hardening.manufacture(
 p_company_id uuid, p_recipe_id uuid, p_finished_lot text,
 p_output_quantity numeric, p_operation_id uuid
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  v_request jsonb;
  v_record erp_hardening.operations%ROWTYPE;
  v_recipe erp_hardening.recipes%ROWTYPE;
  v_lock record;
  v_comp record;
  v_lot record;
  v_needed numeric;
  v_take numeric;
  v_total_cost numeric := 0;
  v_unit_cost numeric;
  v_finished_lot_id uuid;
  v_result jsonb;
  v_allocations jsonb := '[]'::jsonb;
BEGIN
  IF auth.uid() IS NULL OR NOT EXISTS (
    SELECT 1 FROM erp_hardening.company_members
    WHERE company_id=p_company_id AND user_id=auth.uid()
      AND role IN ('admin', 'production')
  ) THEN
    RAISE EXCEPTION 'Access denied' USING ERRCODE = '42501';
  END IF;
  IF p_company_id IS NULL OR p_recipe_id IS NULL OR p_operation_id IS NULL OR
     p_finished_lot IS NULL OR length(p_finished_lot) NOT BETWEEN 1 AND 64 OR
     p_output_quantity IS NULL OR p_output_quantity <= 0 OR
     p_output_quantity <> round(p_output_quantity,6) THEN
    RAISE EXCEPTION 'Invalid manufacturing request' USING ERRCODE = '22023';
  END IF;
  v_request := pg_catalog.jsonb_build_object('recipe_id',p_recipe_id,
       'lot',p_finished_lot,'quantity',p_output_quantity);
  INSERT INTO erp_hardening.operations(company_id,operation_id,action,request)
    VALUES(p_company_id,p_operation_id,'MANUFACTURE',v_request)
    ON CONFLICT DO NOTHING;
  IF NOT FOUND THEN
    SELECT * INTO STRICT v_record FROM erp_hardening.operations
      WHERE company_id=p_company_id AND operation_id=p_operation_id FOR UPDATE;
    IF v_record.action <> 'MANUFACTURE' OR v_record.request <> v_request OR v_record.result IS NULL THEN
      RAISE EXCEPTION 'Idempotency key conflict' USING ERRCODE = '23505';
    END IF;
    RETURN v_record.result;
  END IF;
  SELECT * INTO v_recipe FROM erp_hardening.recipes
    WHERE recipe_id=p_recipe_id AND company_id=p_company_id AND status='APPROVED' FOR SHARE;
  IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM erp_hardening.recipe_lines WHERE recipe_id=p_recipe_id) THEN
    RAISE EXCEPTION 'No approved and populated recipe' USING ERRCODE = '22023';
  END IF;
  -- Les composants et le PF sont verrouillés dans un ordre global stable, évitant les deadlocks entre OF.
  FOR v_lock IN
    SELECT item_code FROM (
      SELECT rl.item_code FROM erp_hardening.recipe_lines rl WHERE rl.recipe_id=p_recipe_id
      UNION SELECT v_recipe.finished_item_code
    ) AS all_items ORDER BY item_code
  LOOP
    PERFORM 1 FROM erp_hardening.items
       WHERE company_id=p_company_id AND item_code=v_lock.item_code FOR UPDATE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'Unknown recipe component' USING ERRCODE = '22023';
    END IF;
  END LOOP;
  FOR v_comp IN
    SELECT rl.item_code,
      pg_catalog.round(rl.quantity * p_output_quantity / v_recipe.base_quantity, 6) AS required
    FROM erp_hardening.recipe_lines rl WHERE rl.recipe_id=p_recipe_id ORDER BY rl.item_code
  LOOP
    IF v_comp.required <= 0 OR v_comp.required > 999999999999 THEN
      RAISE EXCEPTION 'Invalid calculated material quantity' USING ERRCODE = '22023';
    END IF;
    v_needed := v_comp.required;
    FOR v_lot IN
      SELECT lot_id, remaining, unit_cost FROM erp_hardening.lots
      WHERE company_id=p_company_id AND item_code=v_comp.item_code AND remaining > 0
      ORDER BY receipt_seq FOR UPDATE
    LOOP
      v_take := LEAST(v_needed, v_lot.remaining);
      UPDATE erp_hardening.lots SET remaining=remaining-v_take WHERE lot_id=v_lot.lot_id;
      INSERT INTO erp_hardening.movements(company_id,operation_id,item_code,lot_id,direction,quantity,unit_cost)
        VALUES(p_company_id,p_operation_id,v_comp.item_code,v_lot.lot_id,'OUT',v_take,v_lot.unit_cost);
      v_total_cost := v_total_cost + v_take*v_lot.unit_cost;
      v_allocations := v_allocations || pg_catalog.jsonb_build_array(
         pg_catalog.jsonb_build_object('item',v_comp.item_code,'lot_id',v_lot.lot_id,'quantity',v_take));
      v_needed := v_needed - v_take;
      EXIT WHEN v_needed = 0;
    END LOOP;
    IF v_needed > 0 THEN
      -- L'erreur annule TOUT : aucun lot n'est prélevé, aucun PF n'est créé.
      RAISE EXCEPTION 'Insufficient stock for item %', v_comp.item_code USING ERRCODE = 'P0001';
    END IF;
  END LOOP;
  v_unit_cost := pg_catalog.round(v_total_cost/p_output_quantity,6);
  INSERT INTO erp_hardening.lots(company_id,item_code,lot_code,remaining,unit_cost)
    VALUES(p_company_id,v_recipe.finished_item_code,p_finished_lot,p_output_quantity,v_unit_cost)
    RETURNING lot_id INTO v_finished_lot_id;
  INSERT INTO erp_hardening.movements(company_id,operation_id,item_code,lot_id,direction,quantity,unit_cost)
    VALUES(p_company_id,p_operation_id,v_recipe.finished_item_code,v_finished_lot_id,'IN',p_output_quantity,v_unit_cost);
  v_result := pg_catalog.jsonb_build_object('status','ok','action','MANUFACTURE',
     'operation_id',p_operation_id,'finished_lot_id',v_finished_lot_id,
     'output_quantity',p_output_quantity,'total_material_cost',v_total_cost,
     'unit_material_cost',v_unit_cost,'consumed_lots',v_allocations);
  UPDATE erp_hardening.operations SET result=v_result
    WHERE company_id=p_company_id AND operation_id=p_operation_id;
  RETURN v_result;
END; $$;

-- Ne donner d'exécution qu'à des utilisateurs connectés ; pas d'accès au schéma par l'API REST.
REVOKE ALL ON FUNCTION erp_hardening.receive_lot(uuid,text,text,numeric,numeric,uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION erp_hardening.manufacture(uuid,uuid,text,numeric,uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION erp_hardening.receive_lot(uuid,text,text,numeric,numeric,uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION erp_hardening.manufacture(uuid,uuid,text,numeric,uuid) TO authenticated;

CREATE OR REPLACE FUNCTION public.erp_receive_lot(
 p_company_id uuid, p_item_code text, p_lot_code text,
 p_quantity numeric, p_unit_cost numeric, p_operation_id uuid
) RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path = '' AS $$
 SELECT erp_hardening.receive_lot(p_company_id,p_item_code,p_lot_code,p_quantity,p_unit_cost,p_operation_id)
$$;
CREATE OR REPLACE FUNCTION public.erp_manufacture(
 p_company_id uuid, p_recipe_id uuid, p_finished_lot text,
 p_output_quantity numeric, p_operation_id uuid
) RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path = '' AS $$
 SELECT erp_hardening.manufacture(p_company_id,p_recipe_id,p_finished_lot,p_output_quantity,p_operation_id)
$$;
REVOKE ALL ON FUNCTION public.erp_receive_lot(uuid,text,text,numeric,numeric,uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.erp_manufacture(uuid,uuid,text,numeric,uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.erp_receive_lot(uuid,text,text,numeric,numeric,uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.erp_manufacture(uuid,uuid,text,numeric,uuid) TO authenticated;
COMMIT;
