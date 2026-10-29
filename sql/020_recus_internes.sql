-- ERP 020 : accusés internes d'encaissement, sans valeur de quittance fiscale.
-- Ne modifie aucune facture, règlement ou écriture existante.
BEGIN;

CREATE TABLE public.erp_recus_internes (
  recu_id text PRIMARY KEY
    CHECK (recu_id ~ '^RINT-[0-9a-f-]{36}$'),
  reglement_id text NOT NULL UNIQUE
    REFERENCES public.reglements(reglement_id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  operation_id text NOT NULL UNIQUE
    CHECK (operation_id ~ '^RECUI-[A-Za-z0-9-]{8,120}$'),
  client_id text NOT NULL CHECK (length(btrim(client_id)) BETWEEN 1 AND 200),
  date_reglement date NOT NULL,
  montant_encaisse numeric(18,2) NOT NULL
    CHECK (montant_encaisse > 0 AND montant_encaisse < 1000000000000000),
  mode_paiement text NOT NULL CHECK (length(btrim(mode_paiement)) BETWEEN 1 AND 200),
  reference_reglement text NOT NULL CHECK (length(btrim(reference_reglement)) BETWEEN 1 AND 200),
  statut text NOT NULL DEFAULT 'INTERNE_NON_FISCAL'
    CHECK (statut = 'INTERNE_NON_FISCAL'),
  timbre_statut text NOT NULL DEFAULT 'NON_CALCULE'
    CHECK (timbre_statut = 'NON_CALCULE'),
  cree_le timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX erp_recus_internes_date_idx
  ON public.erp_recus_internes (date_reglement, recu_id);

ALTER TABLE public.erp_recus_internes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.erp_recus_internes FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.erp_recus_internes TO service_role;

-- Le reçu est un instantané définitivement figé : aucune modification
-- de montant/taxe/statut ni suppression, même par le rôle serveur.
CREATE FUNCTION public.erp_bloquer_mutation_recu_interne()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $block$
BEGIN
  RAISE EXCEPTION 'Recu interne immuable : mutation refusee'
    USING ERRCODE = '23514';
END;
$block$;
CREATE TRIGGER erp_recus_internes_immutables
  BEFORE UPDATE OR DELETE ON public.erp_recus_internes
  FOR EACH ROW EXECUTE FUNCTION public.erp_bloquer_mutation_recu_interne();

CREATE FUNCTION public.erp_emettre_recu_interne(
  p_operation_id text, p_reglement_id text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $body$
DECLARE
  v_reg public.reglements%ROWTYPE;
  v_recu public.erp_recus_internes%ROWTYPE;
  v_date date;
  v_id text;
BEGIN
  IF p_operation_id IS NULL OR
     p_operation_id !~ '^RECUI-[A-Za-z0-9-]{8,120}$' OR
     p_reglement_id IS NULL OR
     length(btrim(p_reglement_id)) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'Identifiants de recu interne invalides'
      USING ERRCODE = '22023';
  END IF;

  -- Le verrou sur le paiement sérialise deux demandes de reçu concurrentes.
  SELECT * INTO v_reg FROM public.reglements
    WHERE reglement_id = p_reglement_id FOR UPDATE;
  IF NOT FOUND OR v_reg.type_flux IS DISTINCT FROM 'ENCAISSEMENT'
     OR v_reg.statut IS DISTINCT FROM 'VALIDE' THEN
    RAISE EXCEPTION 'Encaissement inexistant ou non valide'
      USING ERRCODE = '23514';
  END IF;

  IF v_reg.montant_total IS NULL OR
     v_reg.montant_total <= 0 OR
     v_reg.montant_total >= 1000000000000000 OR
     v_reg.montant_total <> round(v_reg.montant_total, 2) OR
     v_reg.montant_alloue IS NULL OR
     v_reg.montant_alloue < 0 OR
     v_reg.montant_alloue > v_reg.montant_total OR
     v_reg.montant_alloue <> round(v_reg.montant_alloue, 2) OR
     length(btrim(coalesce(v_reg.partenaire_id, ''))) NOT BETWEEN 1 AND 200 OR
     length(btrim(coalesce(v_reg.mode_paiement, ''))) NOT BETWEEN 1 AND 200 OR
     length(btrim(coalesce(v_reg.reference_trace, ''))) NOT BETWEEN 1 AND 200 OR
     v_reg.date_reglement IS NULL OR
     v_reg.date_reglement !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} THEN
    RAISE EXCEPTION 'Encaissement incoherent, refuse sans mutation'
      USING ERRCODE = '23514';
  END IF;
  BEGIN
    v_date := v_reg.date_reglement::date;
  EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
    RAISE EXCEPTION 'Date de reglement non valide' USING ERRCODE='23514';
  END;
  IF to_char(v_date, 'YYYY-MM-DD') <> v_reg.date_reglement THEN
    RAISE EXCEPTION 'Date de reglement non canonique' USING ERRCODE='23514';
  END IF;

  SELECT * INTO v_recu FROM public.erp_recus_internes
    WHERE reglement_id = p_reglement_id;
  IF FOUND THEN
    IF v_recu.operation_id IS DISTINCT FROM p_operation_id OR
       v_recu.client_id IS DISTINCT FROM v_reg.partenaire_id OR
       v_recu.montant_encaisse IS DISTINCT FROM v_reg.montant_total OR
       v_recu.date_reglement IS DISTINCT FROM v_date OR
       v_recu.mode_paiement IS DISTINCT FROM v_reg.mode_paiement OR
       v_recu.reference_reglement IS DISTINCT FROM v_reg.reference_trace THEN
      RAISE EXCEPTION 'Recu deja emis ou source historique modifiee'
        USING ERRCODE='23505';
    END IF;
    RETURN jsonb_build_object(
      'recu_id', v_recu.recu_id,
      'reglement_id', v_recu.reglement_id,
      'operation_id', v_recu.operation_id,
      'statut', v_recu.statut,
      'timbre_statut', v_recu.timbre_statut
    );
  END IF;

  v_id := 'RINT-' || gen_random_uuid()::text;
  INSERT INTO public.erp_recus_internes (
    recu_id, reglement_id, operation_id, client_id, date_reglement,
    montant_encaisse, mode_paiement, reference_reglement
  ) VALUES (
    v_id, p_reglement_id, p_operation_id, v_reg.partenaire_id,
    v_date, v_reg.montant_total, v_reg.mode_paiement, v_reg.reference_trace
  );
  RETURN jsonb_build_object(
    'recu_id', v_id,
    'reglement_id', p_reglement_id,
    'operation_id', p_operation_id,
    'statut', 'INTERNE_NON_FISCAL',
    'timbre_statut', 'NON_CALCULE'
  );
END;
$body$;

REVOKE ALL ON FUNCTION public.erp_bloquer_mutation_recu_interne() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.erp_emettre_recu_interne(text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_emettre_recu_interne(text,text) TO service_role;
COMMIT;
 THEN
    RAISE EXCEPTION 'Encaissement incoherent, refuse sans mutation'
      USING ERRCODE = '23514';
  END IF;
  BEGIN
    v_date := v_reg.date_reglement::date;
  EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
    RAISE EXCEPTION 'Date de reglement non valide' USING ERRCODE='23514';
  END;
  IF to_char(v_date, 'YYYY-MM-DD') <> v_reg.date_reglement THEN
    RAISE EXCEPTION 'Date de reglement non canonique' USING ERRCODE='23514';
  END IF;

  SELECT * INTO v_recu FROM public.erp_recus_internes
    WHERE reglement_id = p_reglement_id;
  IF FOUND THEN
    IF v_recu.operation_id IS DISTINCT FROM p_operation_id OR
       v_recu.client_id IS DISTINCT FROM v_reg.partenaire_id OR
       v_recu.montant_encaisse IS DISTINCT FROM v_reg.montant_total OR
       v_recu.date_reglement IS DISTINCT FROM v_date OR
       v_recu.mode_paiement IS DISTINCT FROM v_reg.mode_paiement OR
       v_recu.reference_reglement IS DISTINCT FROM v_reg.reference_trace THEN
      RAISE EXCEPTION 'Recu deja emis ou source historique modifiee'
        USING ERRCODE='23505';
    END IF;
    RETURN jsonb_build_object(
      'recu_id', v_recu.recu_id,
      'reglement_id', v_recu.reglement_id,
      'operation_id', v_recu.operation_id,
      'statut', v_recu.statut,
      'timbre_statut', v_recu.timbre_statut
    );
  END IF;

  v_id := 'RINT-' || gen_random_uuid()::text;
  INSERT INTO public.erp_recus_internes (
    recu_id, reglement_id, operation_id, client_id, date_reglement,
    montant_encaisse, mode_paiement, reference_reglement
  ) VALUES (
    v_id, p_reglement_id, p_operation_id, v_reg.partenaire_id,
    v_date, v_reg.montant_total, v_reg.mode_paiement, v_reg.reference_trace
  );
  RETURN jsonb_build_object(
    'recu_id', v_id,
    'reglement_id', p_reglement_id,
    'operation_id', p_operation_id,
    'statut', 'INTERNE_NON_FISCAL',
    'timbre_statut', 'NON_CALCULE'
  );
END;
$body$;

REVOKE ALL ON FUNCTION public.erp_bloquer_mutation_recu_interne() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.erp_emettre_recu_interne(text,text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.erp_emettre_recu_interne(text,text) TO service_role;
COMMIT;
