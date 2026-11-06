# Campagne — Précontrôle de validation des coûts industriels
Date : 6 novembre 2026

## Périmètre
Dépôt `Verwolfy/erp-mortier`, fonctionnalité `Production & Nomenclatures > Coûts industriels`. La présente campagne est **non comptabilisante** et ne modifie ni le CUMP, ni les stocks, ni les pièces SCF.

## Diagnostic Supabase production en lecture seule
- Projet : `erp-mortier` (`wenydirqtmkywbxbxfal`).
- Période `COST-P-170840f6-ce99-447b-b8f3-48faee465fd5` : 06/11/2026 → 06/11/2026, BROUILLON.
- Période `COST-P-3e99d785-3e9c-4aa8-baa2-a8bc16fa477e` : 01/11/2026 → 06/11/2026, BROUILLON.
- Chaque période a 0 charge, 0 assiette, 0 imputation. Six natures actives.
- Les seuls OF terminés observés sont `SIM26_OF` (18/10/2026) et `OF-0001` (24/10/2026) : **hors période**.
- Une pièce SCF BROUILLON (2 lignes), zéro VALIDEE. Une pièce brouillon **ne constitue pas** une preuve recevable.
- L'audit SQL `audit_ok=true` pour 0 = 0 est numériquement exact mais ne valide pas la période. La RPC `erp_cost_validate_period(text)` exige charges, assiettes et preuves SCF VALIDEE.

## Circuit opératoire complet — données réelles uniquement
1. Comptabilité : préparer une pièce SCF sur un exercice OUVERT, avec source documentaire réelle, au moins deux lignes et équilibre débit/crédit ; faire approuver/valider la pièce par la personne habilitée. Ne jamais transformer une pièce fictive ou brouillon en preuve.
2. Production : disposer d'un OF TERMINE, avec une date `date_fin` comprise dans la période analytique. Choisir ou créer une période correspondant à la date réelle, sans retoucher les dates historiques.
3. Coûts : choisir une nature (énergie, main-d'œuvre, etc.), une clé d'imputation et saisir un montant réel justifié ; l'ajout crée uniquement un pool SIMULATION.
4. Preuve : lier le pool à la **pièce SCF VALIDEE et à une ligne au débit distincte**, avec un montant inférieur ou égal au débit et une justification explicite ; la RPC documentaire fait la liaison et passe à DOCUMENTE en une transaction.
5. Assiette : renseigner la mesure justifiée de chaque OF terminé dans les dates, pour la même clé d'imputation (unités, kg, heures, kWh…). Aucune valeur estimée ne doit être présentée comme mesurée.
6. Précontrôle (nouveau) : cliquer sur « Vérifier les prérequis ». Le service contrôle la présence des charges/assiettes, le statut DOCUMENTE, le rapprochement au débit SCF, les OF éligibles, la synthèse et l'audit.
7. Validation : confirmation explicite ; **le précontrôle est recalculé au clic**, puis la RPC SQL vérifie sous verrou avant de changer BROUILLON → VALIDE et de figer les instantanés OF. Ne jamais contourner le blocage en SQL.
8. Export : sur VALIDE uniquement, bouton de préparation puis export JSON d'un unique snapshot SQL ; rapport analytique non comptable.

## Sécurité et contrôles de non-régression
- Habilitations de lecture Production ET Finance pour le précontrôle. Les opérations d'écriture exigent les permissions correspondantes.
- Aucun droit SQL, RLS/GRANT ou clé modifiés.
- Aucune donnée de simulation injectée en production. Les tests unitaires utilisent des doublures ; les lectures SQL réelles restent séparées.
- Chaque insertion/upsert Python doit obtenir un retour contenant l'identifiant attendu ; un résultat vide ou incohérent est signalé **incertain**. Après panne, vérifier Supabase avant une répétition (éviter les doublons).
- Le précontrôle traverse plusieurs appels et n'a **pas** d'instantané transactionnel unique ; seule la RPC SQL est décisionnelle. Une information de précontrôle « prêt » ne certifie pas un résultat futur.

## Restes à faire et frontières
- Contrôler le déploiement effectif Streamlit auprès de l'hébergeur ; GitHub Actions ne constitue pas une preuve visuelle.
- Obtenir les pièces et justificatifs **réels** ainsi que l'exercice/les journaux SCF autorisés pour un cycle complet en production.
- Aucun coût n'est calculable sur les brouillons de novembre tant que les données correspondantes n'existent pas.
- Une validation par un expert-comptable algérien reste indispensable avant toute production réglementaire.

## Preuves de CI
À compléter après création de la PR et exécution effective des workflows. Ne pas qualifier les tests d'OK avant leur résultat.
