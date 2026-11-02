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

Le registre des congés signale désormais le nombre de demandes `SIM-CNG-`. Si une écriture d’employé ou de congé ne reçoit pas de confirmation, l’écran demande de vérifier le registre avant toute nouvelle tentative ; cela ne garantit pas une reprise transactionnelle automatique.


## Atelier fictif intégré

Onglet RH « Atelier paie fictive » réservé aux personnes disposant de Paie/lecture ; seules les huit fiches actives SIM-RH-001 à 008 avec marqueur [FICTIF] sont proposées. Calcul en mémoire : base fictive 40 000 + 1 000 × numéro, retenue de test 5 %, contribution de test 10 % et retenue de test 1 000 DA. Ces paramètres sont arbitraires, non juridiques et sans correspondance CNAS/IRG. Aucun bulletin, montant, paiement ou déclaration n'est enregistré. Le contrôle d'accès est revérifié au clic.

Les références réglementaires et les bulletins officiels restent bloqués tant que les règles, assiettes, dates et arrondis ne sont pas qualifiés. Le rendu hébergé dépend du déploiement effectif de Streamlit.


## Comparaison DGI 2022 sur les huit salaires de l’atelier

Sur demande utilisateur, comparaison documentaire préparée le 2 novembre 2026, **simulation hors ERP, non enregistrée en base et non validée pour la paie réelle**. Les salaires bruts fictifs correspondent aux bases de l’atelier existant. Hypothèses de test : base entièrement soumise à la cotisation de 9 %, aucune prime de rendement/panier ni autre retenue, et l’assiette IRG = brut fictif − cotisation salariale. Ces hypothèses ne qualifient pas une assiette individuelle réelle.

Les valeurs IRG proviennent des lignes cas général de la [table DGI 2022](https://www.mfdgi.gov.dz/images/bareme_irg/TABLE_IRG_2022.pdf) correspondant aux assiettes ci-dessous, toutes multiples de 10 DA. La colonne patronale est une comparaison à 25 % de l’assiette fictive selon le tableau du [décret 15-236, JO n°49/2015 p.7](https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf) ; elle n’inclut ni ne prouve toutes les autres charges employeur. Aucun montant n'est un taux ou une règle juridique créée en base.

| Employé fictif | Brut hypothétique DA | Cotisation salariale hypothétique DA | Assiette IRG hypothétique DA | IRG table DGI 2022 DA | Net arithmétique hypothétique DA | Quote-part patronale 25 % hypothétique DA |
|---|---:|---:|---:|---:|---:|---:|
| SIM-RH-001 | 41000.00 | 3690.00 | 37310.00 | 2481.30 | 34828.70 | 10250.00 |
| SIM-RH-002 | 42000.00 | 3780.00 | 38220.00 | 2690.60 | 35529.40 | 10500.00 |
| SIM-RH-003 | 43000.00 | 3870.00 | 39130.00 | 2899.90 | 36230.10 | 10750.00 |
| SIM-RH-004 | 44000.00 | 3960.00 | 40040.00 | 3110.80 | 36929.20 | 11000.00 |
| SIM-RH-005 | 45000.00 | 4050.00 | 40950.00 | 3356.50 | 37593.50 | 11250.00 |
| SIM-RH-006 | 46000.00 | 4140.00 | 41860.00 | 3602.20 | 38257.80 | 11500.00 |
| SIM-RH-007 | 47000.00 | 4230.00 | 42770.00 | 3847.90 | 38922.10 | 11750.00 |
| SIM-RH-008 | 48000.00 | 4320.00 | 43680.00 | 4093.60 | 39586.40 | 12000.00 |

Les bases et primes réelles, l’assiette CNAS, le traitement du panier, les retenues et l’ensemble des charges restent à qualifier ; il ne faut pas utiliser ce tableau pour un bulletin ou un versement réel. L’applicabilité 2026 et le traitement des montants hors des lignes de la table ne sont pas démontrés par ces huit exemples. L’atelier ERP conserve l’exemple arbitraire distinct (5 %, 10 %, 1 000 DA) et propose maintenant un bouton séparé pour afficher cette comparaison DGI 2022, en mémoire et réservée aux employés fictifs actifs.

L'environnement d'exécution local était indisponible pendant cette intervention : comparaison arithmétique et lignes sources vérifiées, mais tests automatisés et rendu Streamlit connecté non exécutés. Les paramètres CNAS/IRG restent absents des registres de production, pour éviter de présenter un calcul dont l'arrondi et les assiettes ne sont pas établis comme une règle juridique confirmée.


## Comparaison DGI dans l'atelier RH

Le bouton « Comparer avec la table DGI 2022 » affiche les huit lignes de référence ci-dessus et leurs sources. Il vérifie la permission Paie au clic, ne permet que les fiches fictives actives admises et n’enregistre aucun résultat. L’exemple suppose des primes et autres retenues nulles ; il ne remplace pas les règles de paie de l’entreprise ni un bulletin officiel. Les références réglementaires restent non activées.
