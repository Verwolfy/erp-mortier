-- Migration 014, LOT D : socle SCF en tables nouvelles uniquement.
-- BROUILLON : ne pas appliquer avant autorisation séparée RLS/GRANT.
-- Prérequis : migration 012 (schema_migrations).
-- Les comptes ci-dessous sont libres : aucune nomenclature fiscale implantée.
BEGIN;

CREATE TABLE IF NOT EXISTS public.scf_exercices (
  exercice_id text PRIMARY KEY,
  date_debut date NOT NULL,
  date_fin date NOT NULL,
  statut text NOT NULL DEFAULT 'OUVERT'
    CHECK (statut IN ('OUVERT','CLOTURE')),
  CHECK (date_fin >= date_debut)
);

CREATE TABLE IF NOT EXISTS public.scf_plan_comptes (
  numero_compte text PRIMARY KEY
    CHECK (numero_compte ~ '^[1-8][0-9]{1,7}$'),
  libelle text NOT NULL CHECK (length(btrim(libelle)) BETWEEN 1 AND 200),
  actif boolean NOT NULL DEFAULT true,
  mouvementable boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.scf_journaux (
  code_journal text PRIMARY KEY
    CHECK (code_journal ~ '^[A-Z0-9_]{2,12}$'),
  libelle text NOT NULL CHECK (length(btrim(libelle)) BETWEEN 1 AND 200)
);

CREATE TABLE IF NOT EXISTS public.scf_pieces (
  piece_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exercice_id text NOT NULL REFERENCES public.scf_exercices(exercice_id),
  code_journal text NOT NULL REFERENCES public.scf_journaux(code_journal),
  reference text NOT NULL,
  document_source text NOT NULL,
  date_ecriture date NOT NULL,
  libelle text NOT NULL,
  statut text NOT NULL DEFAULT 'BROUILLON' CHECK (statut IN ('BROUILLON','VALIDEE')),
  date_validation timestamptz,
  cree_le timestamptz NOT NULL DEFAULT now(),
  UNIQUE (exercice_id, code_journal, reference),
  CHECK (length(btrim(reference)) BETWEEN 1 AND 200),
  CHECK (length(btrim(document_source)) BETWEEN 1 AND 200),
  CHECK (length(btrim(libelle)) BETWEEN 1 AND 500),
  CHECK ((statut='BROUILLON' AND date_validation IS NULL)
         OR (statut='VALIDEE' AND date_validation IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS public.scf_lignes (
  ligne_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  piece_id uuid NOT NULL REFERENCES public.scf_pieces(piece_id),
  numero integer NOT NULL CHECK (numero BETWEEN 1 AND 200),
  compte text NOT NULL REFERENCES public.scf_plan_comptes(numero_compte),
  debit numeric(20,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
  credit numeric(20,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
  UNIQUE (piece_id,numero),
  CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);

-- Toute édition de lignes verrouille d'abord la pièce parente.
-- Un document validé ne peut être modifié ou supprimé. Une correction
-- future doit générer une nouvelle contrepassation et non un UPDATE.
CREATE OR REPLACE FUNCTION public.scf_garder_lignes()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $func$
DECLARE
  v_piece uuid;
  v_statut text;
  v_actif boolean;
  v_mouvementable boolean;
BEGIN
  v_piece := CASE WHEN TG_OP='DELETE' THEN OLD.piece_id ELSE NEW.piece_id END;
  IF TG_OP='UPDATE' AND NEW.piece_id IS DISTINCT FROM OLD.piece_id THEN
    RAISE EXCEPTION 'Deplacement de ligne interdit' USING ERRCODE='23514';
  END IF;
  SELECT statut INTO v_statut FROM public.scf_pieces
    WHERE piece_id=v_piece FOR UPDATE;
  IF v_statut IS DISTINCT FROM 'BROUILLON' THEN
    RAISE EXCEPTION 'Piece non modifiable' USING ERRCODE='23514';
  END IF;
  IF TG_OP <> 'DELETE' THEN
    SELECT actif,mouvementable INTO v_actif,v_mouvementable
      FROM public.scf_plan_comptes WHERE numero_compte=NEW.compte;
    IF v_actif IS DISTINCT FROM true OR v_mouvementable IS DISTINCT FROM true THEN
      RAISE EXCEPTION 'Compte inactif ou non mouvementable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;
  RETURN OLD;
END;
$func$;

CREATE OR REPLACE FUNCTION public.scf_garder_pieces()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, public
AS $func$
DECLARE
  v_periode record;
  v_lignes integer;
  v_debit numeric;
  v_credit numeric;
BEGIN
  IF TG_OP='DELETE' THEN
    IF OLD.statut='VALIDEE' THEN
      RAISE EXCEPTION 'Suppression piece validee interdite' USING ERRCODE='23514';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.statut='VALIDEE' THEN
    RAISE EXCEPTION 'Piece validee immuable' USING ERRCODE='23514';
  END IF;
  IF NEW.statut='VALIDEE' THEN
    SELECT * INTO v_periode FROM public.scf_exercices
      WHERE exercice_id=NEW.exercice_id FOR SHARE;
    IF NOT FOUND OR v_periode.statut<>'OUVERT'
       OR NEW.date_ecriture<v_periode.date_debut
       OR NEW.date_ecriture>v_periode.date_fin THEN
      RAISE EXCEPTION 'Periode SCF fermee ou date hors exercice' USING ERRCODE='23514';
    END IF;
    SELECT count(*),coalesce(sum(debit),0),coalesce(sum(credit),0)
      INTO v_lignes,v_debit,v_credit
      FROM public.scf_lignes WHERE piece_id=OLD.piece_id;
    IF v_lignes<2 OR v_debit<=0 OR v_debit<>v_credit THEN
      RAISE EXCEPTION 'Piece SCF desequilibree' USING ERRCODE='23514';
    END IF;
    NEW.date_validation := now();
  END IF;
  RETURN NEW;
END;
$func$;

-- Les fonctions de déclenchement ne peuvent pas être appelées comme RPC.
-- Les triggers servent de défense supplémentaire à la couche métier.
CREATE TRIGGER scf_lignes_immutabilite
  BEFORE INSERT OR UPDATE OR DELETE ON public.scf_lignes
  FOR EACH ROW EXECUTE FUNCTION public.scf_garder_lignes();
CREATE TRIGGER scf_pieces_immutabilite
  BEFORE UPDATE OR DELETE ON public.scf_pieces
  FOR EACH ROW EXECUTE FUNCTION public.scf_garder_pieces();

ALTER TABLE public.scf_exercices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scf_plan_comptes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scf_journaux ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scf_pieces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scf_lignes ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.scf_exercices,public.scf_plan_comptes,public.scf_journaux,
              public.scf_pieces,public.scf_lignes FROM PUBLIC,anon,authenticated;
-- Aucune politique permissive : les accès passent par le service serveur
-- après vérification explicite des rôles SCF.
COMMIT;
