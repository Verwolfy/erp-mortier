-- Lecture seule : exécuter sur COPIE Supabase, jamais une migration.
-- Rechercher les réceptions excédentaires et les BC sans lignes.
SELECT c.commande_achat_id, c.statut,
       count(l.ligne_achat_id) AS lignes_commande
FROM public.commandes_achats c
LEFT JOIN public.lignes_achats l ON l.commande_achat_id=c.commande_achat_id
GROUP BY c.commande_achat_id,c.statut
HAVING count(l.ligne_achat_id)=0;

WITH ordered AS (
  SELECT commande_achat_id,mp_id,sum(qte_totale) AS qte_commandee
  FROM public.lignes_achats GROUP BY commande_achat_id,mp_id
), received AS (
  SELECT b.commande_achat_id,l.mp_id,sum(l.quantite_recue) AS qte_recue
  FROM public.bons_reception b
  JOIN public.lignes_bons_reception l ON l.bon_reception_id=b.bon_reception_id
  GROUP BY b.commande_achat_id,l.mp_id
)
SELECT coalesce(o.commande_achat_id,r.commande_achat_id) AS commande_achat_id,
       coalesce(o.mp_id,r.mp_id) AS mp_id,
       coalesce(o.qte_commandee,0) AS qte_commandee,
       coalesce(r.qte_recue,0) AS qte_recue
FROM ordered o FULL OUTER JOIN received r
  ON o.commande_achat_id=r.commande_achat_id AND o.mp_id=r.mp_id
WHERE coalesce(r.qte_recue,0) > coalesce(o.qte_commandee,0);

SELECT l.ligne_br_id,l.bon_reception_id,l.mp_id,l.lot_attribue_id
FROM public.lignes_bons_reception l
LEFT JOIN public.lots t ON t.lot_id=l.lot_attribue_id
WHERE l.lot_attribue_id IS NOT NULL AND t.lot_id IS NULL;
