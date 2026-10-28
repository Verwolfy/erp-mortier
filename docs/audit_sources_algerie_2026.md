# Audit documentaire de conformité algérienne — 28 octobre 2026

Statut : revue de sources publiques, **pas validation d'une liquidation fiscale ni avis d'expert**.

| Sujet | Source primaire consultée | Résultat | Intégration ERP |
|---|---|---|---|
| TVA normale/réduite | DGI, La taxe sur la valeur ajoutée, https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee | La fiche officielle décrit 19 % et 9 %, avec des opérations distinctes. Vérifier l'éligibilité par produit et date d'effet avant l'activation. | Moteur générique disponible, taux applicables **non chargés** |
| Fait générateur TVA | Même fiche DGI | Ventes de biens : livraison en règle générale ; services et travaux : règles distinctes d'encaissement. Des exceptions existent. | Agrégation par date du fait générateur de chaque pièce ; contrôle de lien livraison/facture **à développer** |
| IRG traitements/salaires | DGI, https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires | Barème progressif, exonérations et abattements particuliers selon les revenus / situations. | Moteur marginal générique, calcul IRG complet **non disponible** |
| Obligations CNAS | Portail officiel https://teledeclaration.cnas.dz/index.jsp | Déclaration des assiettes, paiement des cotisations, DAS ; les taux de contribution 2026 n'ont pas été confirmés sur ce portail. | Taux sociaux **non chargés** |
| Timbre espèces | Texte légal consolidé 2026 non encore vérifié | Les valeurs historiques Python/SQL sont des conventions non certifiées. | Aucun taux ni plafond actif ; création de facture bloquée sans paramètres confirmés |
| SCF | Loi 07-11 du 25/11/2007, JO 74 : https://www.joradp.dz/ftp/jo-francais/2007/f2007074.pdf | Texte source identifié, détail des sous-comptes et états à auditer. | Contrôle équilibrage et états préparatoires uniquement |

## Points empêchant une mise en production
1. Vérifier les dates d'effet et les classes fiscales applicables aux SKU, clients, factures et livraisons.
2. Réconcilier les taux de TVA Python **et SQL** et tester une vente soumise à 9 %, une exonération, un avoir historique et les factures mixtes.
3. Confirmer les taux CNAS par période, l'assiette, les exemptions et l'IRG complet, avec tests officiels.
4. Valider les droits RH, l'immutabilité des bulletins et la protection des données personnelles.
5. Rejouer les migrations en TEST dans l'ordre, avec tests SQL et possibilité de retour arrière.
6. Ne jamais annoncer « conforme » ou « prêt à déployer » sans preuve de tests fonctionnels, juridiques et d'intégration.

**Important :** les calculs et pièces produits par ces branches ne constituent pas un justificatif fiscal ou social officiel.
