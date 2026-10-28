-- Migration ERP 019 : index non destructeurs pour les tables privees.
-- Compatible PostgreSQL 17, aucune mise à jour de données historiques.
BEGIN;
CREATE INDEX IF NOT EXISTS scf_pieces_code_journal_idx
    ON public.scf_pieces (code_journal);
CREATE INDEX IF NOT EXISTS scf_lignes_compte_idx
    ON public.scf_lignes (compte);
CREATE INDEX IF NOT EXISTS paie_bulletins_v2_periode_id_idx
    ON public.paie_bulletins_v2 (periode_id);
CREATE INDEX IF NOT EXISTS scf_pieces_validees_date_idx
    ON public.scf_pieces (date_ecriture, piece_id)
    WHERE statut = 'VALIDEE';
COMMIT;
