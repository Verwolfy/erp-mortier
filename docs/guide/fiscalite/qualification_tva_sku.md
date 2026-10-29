---
titre: Qualification TVA par SKU — audit préalable
module: fiscalite
roles_autorises: [ADMIN, COMPTABLE]
version: 1
date_maj: 2026-10-29
regles_liees: [TVA-SKU-022]
---

# Qualification de la TVA des produits

**Pourquoi :** 19 % et 9 % sont des taux généraux documentés par la DGI,
mais les ventes de mortiers, de ciments-colles et d'autres matériaux ne
doivent pas se voir appliquer un taux par simple analogie commerciale.

**Comment :** l'onglet **Ventes → TVA par SKU (contrôle)** affiche le
statut des produits. Le registre `erp_sku_fiscalite` conserve des
versions datées et une décision explicite :

- `NON_CLASSE` : aucune qualification applicable à la date du contrôle ;
- `A_VALIDER` : un dossier existe, sans approbation complète ;
- `VALIDE` : une catégorie NORMAL / REDUIT / EXONERE / HORS_CHAMP
  a un justificatif, une date de contrôle et un approbateur.

La migration 022 n'assigne **aucun** régime fiscal aux SKU. Elle ouvre
la consultation au rôle serveur seulement, sans écriture depuis l'application.
Une classification approuvée ne peut pas être utilisée dans la facturation
tant que le régime de l'entreprise, les faits générateurs, les avoirs et
la version de la RPC Ventes ne sont pas vérifiés.

Les dates ne doivent pas se chevaucher. Un conflit arrête l'ensemble du
contrôle plutôt que d'afficher un taux arbitraire.

**Sources :**
- DGI TVA (19 % normal / 9 % réduit), dispositions d'assujettissement et
  exemptions :
  https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee
- Loi de finances 2026, JO 88 du 31 décembre 2025 (article 53) :
  https://www.mf.gov.dz/images/pdf/loidefinance/Loi_de_Finances_2026_FR.pdf

Aucune sauvegarde PostgreSQL n'est imposée. Le circuit historique de
facturation n'est pas modifié par cette étape.


## État des bases — 29 octobre 2026

Les migrations `erp_022_qualification_tva_sku_20261029` et
`erp_023_tva_sku_acl_lecture_20261029` ont été appliquées sur TEST
et PRODUCTION. Les deux projets contiennent 7 SKU et **0 dossier fiscal
classé**. Aucune facture n'a été modifiée.

Un écart initial a été détecté : production héritait de permissions
`service_role` permettant l'écriture. La migration 023 a explicitement
révoqué ces permissions. Vérification finale identique sur les deux bases :
RLS active, lecture serveur autorisée, aucune lecture publique ni
écriture du rôle serveur.

Ce contrôle est un **état préparatoire**, pas une preuve de conformité
ou une autorisation d'appliquer 19 %/9 % à tous les SKU.
