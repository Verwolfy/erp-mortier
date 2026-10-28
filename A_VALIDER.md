# A_VALIDER — ERP Mortier, conformité algérienne (lot C, 2026-10-28)

Ce document est un registre de décisions **à valider avant activation**. Les taux et dates non validés ne sont pas chargés en base.

| Sujet | Fait / constat | Décision attendue |
|---|---|---|
| TVA standard | La DGI décrit les taux normal 19 % et réduit 9 %, fiche mise à jour le 23 février 2026. Source primaire : https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee | Confirmer que l'entreprise est assujettie au régime réel, déterminer la classe fiscale de chaque SKU et l'assiette adaptée |
| Fait générateur TVA | La DGI indique en général la livraison pour les ventes de biens, des règles distinctes pour les services/travaux | Ne pas assimiler systématiquement date de facture et fait générateur sans modèle livraison/facture |
| TVA exonérée ou réduite | Le taux unique par facture du prototype ne couvre ni exonération, ni 9 %, ni factures mixtes | Développer ventilation par ligne, statut fiscal client et preuves avant activation |
| Timbre sur espèces | Le taux/plafond historiques du code n'ont pas été vérifiés sur un texte officiel à jour | Valider calcul, plafond, champ d'application, exceptions, date d'effet et référence avant insertion des paramètres |
| Avoirs | Un avoir peut porter sur un taux de TVA historique. Le brouillon SQL 013 refuse de recalculer un avoir avec un taux courant différent de l'original | Développer une correction fiscalement fidèle, validée par facture d'origine ; ne jamais altérer le document original |
| SQL 012/013 | Migrations préparées mais ni appliquées ni intégrées ; droits RLS/GRANT inclus | Tests de migration et validation distincte des modifications d'accès avant application |
| Valeurs à injecter | `TVA_VENTE_TAUX`, `TIMBRE_ESPECES_TAUX`, `TIMBRE_ESPECES_PLAFOND` | Pas de seed tant que chaque valeur, source et date d'effet ne sont pas vérifiées |
| Déploiement | L'interface utilise les anciens taux fixes tant que PR #2 n'est pas fusionnée | Exécuter suite complète, contrôles secrets, tests SQL et Guide & Aide avant merge ; préserver changements locaux en cours |

Le moteur Python/SQL du lot C est **un socle technique**, pas une déclaration de conformité fiscale.
