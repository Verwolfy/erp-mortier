# Ressources humaines — jeu de simulation permanent

Créé le 2 novembre 2026 dans la production `wenydirqtmkywbxbxfal`, sur demande explicite de l’utilisateur. Le projet TEST reste en pause.

## Registre de référence

La source reproductible est `tests/fixtures/rh_simulation_employes.json`. Ces dix personnes sont entièrement fictives. Les dates d’embauche sont des données de scénario, sans portée juridique. Aucun compte utilisateur, salaire, identifiant social, coordonnées bancaires ou bulletin n’a été créé.

| ID | Service | Scénario | Actif | Manager |
|---|---|---|---|---|
| SIM-RH-001 | Direction | Responsable racine | OUI | — |
| SIM-RH-002 | RH | Gestionnaire RH | OUI | 001 |
| SIM-RH-003 | Production | Responsable intermédiaire | OUI | 001 |
| SIM-RH-004 | Production | Opérateur récent | OUI | 003 |
| SIM-RH-005 | Production | Embauche le jour de création du jeu | OUI | 003 |
| SIM-RH-006 | Ventes | Commercial | OUI | 001 |
| SIM-RH-007 | Logistique | Magasinier | OUI | 001 |
| SIM-RH-008 | Maintenance | Technicien | OUI | 003 |
| SIM-RH-009 | Production | Employé inactif | NON | 003 |
| SIM-RH-010 | Ventes | Employée inactive | NON | 001 |

Les noms commencent par `[FICTIF]`. Les managers abrégés dans le tableau portent tous le préfixe `SIM-RH-`. Les ID ne consomment pas la séquence EMP des vraies fiches.

## État vérifié après création

- 10 lignes ajoutées, 8 actives et 2 inactives ; aucun manager introuvable.
- 0 demande de congé et 0 bulletin v2 attachés au jeu.
- RLS toujours active ; aucune modification de schéma, permission ou règle de sécurité.
- Insertion SQL directe sur `employes` uniquement, sans mise à jour des lignes existantes et sans synchronisation Google Sheets. Les lectures ERP utilisent Supabase.
- Le Dashboard actuel compte les 8 actifs fictifs. Ne pas interpréter cet effectif comme une donnée RH réelle ; le registre affiche un avertissement.

## Tests et poursuite

| Domaine | Résultat initial / travail restant |
|---|---|
| Registre | Les 10 fiches sont en base ; rendu local AppTest et avertissement fictif contrôlés. Déploiement hébergé à confirmer après connexion. |
| Effectif | 8 actifs, répartis sur 6 services, vérifiés avec le même jeu hors ligne. |
| Congés | Sélecteur limité aux 8 actifs ; défaut de formulaire vide corrigé quand tous les employés sont inactifs. Aucune demande réelle soumise. |
| Hiérarchie | Liens existants et absence d’ID dupliqué vérifiés ; formulaire manager libre à renforcer. |
| Lecture | Anciennes lectures RH encore susceptibles de renvoyer vide sur panne ; migrer vers les lectures contrôlées et vérifier les messages. |
| Écriture | Auditer validation du salarié actif à la soumission, dates, doublons et reprise après résultat incertain ; ne pas annoncer de succès sans confirmation. |
| Cycle de congé | Définir/implémenter les transitions autorisées et leur audit ; ne pas inventer de règles légales de droits ou d’acquisition. |
| Paie | Utiliser uniquement les simulateurs autorisés et les règles vérifiées ; aucune rémunération fictive ne doit devenir un paiement ou une déclaration. |

Les tests automatiques chargent la fixture locale et n’écrivent jamais en production. Réutiliser les mêmes ID pour les prochains scénarios ; ne pas recréer les employés à chaque essai. Toute modification future du jeu doit être journalisée. Ne pas supprimer ou réinitialiser les fiches sans autorisation explicite.

## Scénario du 2 novembre 2026 : congés et paie fictifs

Trois demandes ont été insérées dans la base principale, toutes marquées `[SIMULATION]`, statut `EN_ATTENTE` :

- `SIM-CNG-001` : `SIM-RH-004`, du 10 au 12 novembre 2026.
- `SIM-CNG-002` : `SIM-RH-006`, le 16 novembre 2026.
- `SIM-CNG-003` : `SIM-RH-008`, du 28 décembre 2026 au 2 janvier 2027.

Ces demandes figurent dans le compteur des congés en attente ; elles ne sont pas des congés de personnes réelles. Aucune approbation n’a été simulée dans la base et elles ne doivent pas être utilisées pour une paie réelle.

Huit bulletins ont été calculés **en mémoire seulement**, un pour chaque employé fictif actif, par le moteur `preparer_bulletin_paie` et le test `tests/test_rh_scenario_complet.py`. Les salaires de scénario (41 000 à 48 000 DZD), les taux 5 % / 10 % et la retenue IRG de 1 000 DZD sont des **valeurs arbitraires de test**, sans valeur légale ou fiscale. Les preuves sont des doubles `TEST_FICTIF` et ne représentent aucune validation juridique. Les résultats portent `SIMULATION_NON_VALIDEE` ; aucun bulletin n’est enregistré ou validé dans Supabase, aucun paiement n’est créé.

La simulation du cycle complet reste limitée : le module ne fournit pas encore un cycle d’approbation et d’annulation des congés ni une émission de bulletin homologuée. Les fonctions et autorisations doivent être auditées avant toute activation ; ne pas inventer de règles juridiques pour compléter ce parcours.
