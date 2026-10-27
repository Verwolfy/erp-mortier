-- Lecture seule, à lancer sur Supabase TEST. Ne modifie aucune donnée.
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='public' AND table_name IN
 ('comptes','reglements','lettrage','ecritures_comptables','factures','factures_fournisseurs')
ORDER BY table_name,ordinal_position;

-- Reglements dont le montant alloué ne correspond pas aux lettrages.
SELECT r.reglement_id, r.montant_total, r.montant_alloue,
       COALESCE(sum(l.montant_applique),0) AS somme_lettree
FROM public.reglements r LEFT JOIN public.lettrage l ON l.reglement_id=r.reglement_id
GROUP BY r.reglement_id,r.montant_total,r.montant_alloue
HAVING COALESCE(sum(l.montant_applique),0) IS DISTINCT FROM COALESCE(r.montant_alloue,0);

-- Factures clients avec montant_paye différent de la somme des lettrages.
SELECT f.facture_id, f.statut, f.montant_ttc, f.montant_paye,
       COALESCE(sum(l.montant_applique),0) AS somme_lettree
FROM public.factures f LEFT JOIN public.lettrage l ON l.type_document='FactureClient'
   AND l.document_id=f.facture_id
GROUP BY f.facture_id,f.statut,f.montant_ttc,f.montant_paye
HAVING COALESCE(sum(l.montant_applique),0) IS DISTINCT FROM COALESCE(f.montant_paye,0);

SELECT f.statut, count(*) AS nombre
FROM public.factures f GROUP BY f.statut ORDER BY f.statut;

-- Vérifier les écritures de règlement déséquilibrées (y compris anciennes).
SELECT r.reglement_id, count(e.ecriture_id) AS ecritures,
       COALESCE(sum(e.debit),0) AS total_debit,
       COALESCE(sum(e.credit),0) AS total_credit
FROM public.reglements r LEFT JOIN public.ecritures_comptables e
   ON e.document_source_id=r.reglement_id
GROUP BY r.reglement_id
HAVING COALESCE(sum(e.debit),0) IS DISTINCT FROM COALESCE(sum(e.credit),0);

-- Références de paiement dupliquées (à examiner avant migration).
SELECT compte_id, reference_trace, count(*) AS nombre
FROM public.reglements
WHERE reference_trace IS NOT NULL AND btrim(reference_trace)<>''
GROUP BY compte_id, reference_trace HAVING count(*)>1;
