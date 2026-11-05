-- Exclusivement TEST ffuhbmcfyexsbjwhryvj ; aucune écriture.
SELECT (SELECT count(*) FROM public.bons_reception WHERE commande_achat_id='IT26_RACE_PO') AS receptions,
(SELECT coalesce(sum(l.quantite_recue),0) FROM public.lignes_bons_reception l JOIN public.bons_reception b ON b.bon_reception_id=l.bon_reception_id WHERE b.commande_achat_id='IT26_RACE_PO') AS quantite_recue,
(SELECT quantite_disponible FROM public.stock_actuel WHERE mp_id='IT26_RACE_MP') AS stock_mp,
(SELECT count(*) FROM public.erp_purchase_operations WHERE operation_id IN ('IT26_RACE_REC_A','IT26_RACE_REC_B')) AS receptions_enregistrees,
(SELECT statut FROM public.commandes_achats WHERE commande_achat_id='IT26_RACE_PO') AS statut;
