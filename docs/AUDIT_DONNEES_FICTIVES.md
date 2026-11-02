# Registre des données fictives — audit du 2 novembre 2026

Autorisation utilisateur : enregistrements fictifs dans tous les modules pour les audits, nettoyage après leur fin. Ces données restent en PRODUCTION jusqu’au nettoyage ; elles peuvent apparaître dans les totaux et tableaux de bord. Ne pas utiliser pour une activité réelle. Ne pas supprimer maintenant.

## Scénario Achats SIM-AUD-20261102

- Fournisseur : `SIM-AUD-FOU-001`, nom marqué `[FICTIF AUDIT]`.
- Matière : `SIM-AUD-MP-001`, KG, nom marqué `[FICTIF AUDIT]`, réservée aux simulations.
- Commande : `CMA-0001`, ligne `SIM-AUD-LAC-001`, 0,003 KG × prix arbitraire de test 10 DZD = 0,03 DZD.
- Opération commande : `ACH-UI-f69847663ade494fb506c9279fcb0c2f`. Tentative Streamlit non confirmée, absence vérifiée puis appel direct de la RPC avec le même identifiant réussi.
- Première réception : `SIM-AUD-BR-001`, ligne `SIM-AUD-LBR-001`, 0,001 KG ; opération `ACH-UI-5de50b0198dc4be29ea941eab962f392`. Tentative Streamlit non confirmée, appel direct de la RPC réussi, statut partiel. Répétition à l’identique sans doublon.
- Solde : `SIM-AUD-BR-002`, ligne `SIM-AUD-LBR-002`, 0,002 KG ; opération `SIM-AUD-REC-002`, appel direct RPC réussi, statut final RECEPTIONNE.
- Lots : `LOT-d92781c6-c1ba-4874-95c8-c571692a0e16` et `LOT-ced7953b-263a-4f4f-8ee8-dcbff13d189a`. Péremption NULL, quantités 0,001 et 0,002.
- Mouvements : `MOUV-a76a13f6-cb24-41e4-b8a4-9efce746d44c` et `MOUV-4b64f33e-e568-40c3-a977-33f342a96215`.
- Stock fictif final : 0,003 KG, CMP 10 DZD/KG, valeur 0,03 DZD. Deux réceptions et deux mouvements exactement.

## Nettoyage à préparer en fin d’audit

Rapprocher ces identifiants avec les éventuelles nouvelles utilisations : références, documents, lignes, lots et mouvements, stock, opérations/outbox Achats et Stocks, éventuelles copies Google Sheets. Retrouver les opérations Stocks par leurs résultats et les références BR ; aucun effacement générique par préfixe. Vérifier toutes les dépendances et les sauvegardes avant une suppression ciblée, conserver les preuves de l’audit. La suppression physique n’a pas été effectuée. Les traces d’audit doivent suivre leur règle de conservation ; ne pas les effacer automatiquement.

## Limite du scénario

Les fonctions métier Supabase et les lectures hébergées ont été exercées. La création du client serveur dédié échoue avant l’appel RPC depuis Streamlit : le parcours d’écriture complet depuis l’interface reste non validé. Aucun secret n’a été lu ou remplacé. Les dossiers de reprise restent en session : conserver les mêmes identifiants après correction de la configuration.
