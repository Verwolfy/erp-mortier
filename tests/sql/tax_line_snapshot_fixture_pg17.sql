-- ERP-046 PostgreSQL 17 jetable : tables réduites, données fiscales fictives.
CREATE TABLE public.lignes_facture(
    ligne_facture_id text PRIMARY KEY,
    facture_id text,
    sku_id text,
    total_ligne_ht numeric,
    quantite numeric,
    prix_unitaire numeric,
    remise_ligne numeric
);
INSERT INTO public.lignes_facture(
 ligne_facture_id,facture_id,sku_id,total_ligne_ht,quantite,prix_unitaire,remise_ligne
) VALUES ('LFA-SIM-LEGACY','FAC-SIM-OLD','SKU-SIM-N',100.00,1,100.00,0);
