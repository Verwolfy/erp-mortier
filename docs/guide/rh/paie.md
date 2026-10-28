---
titre: Paie et confidentialité - Mode simulation
module: rh
roles_autorises: [ADMIN, RH]
version: 1
date_maj: 2026-10-28
regles_liees: [PAIE-001, IRG-001, CNAS-001]
---
# Paie, CNAS, IRG — mode simulation

Le calculateur prépare une simulation avec salaire de base, primes, assiettes sociales et fiscales, cotisations et retenues. Les taux CNAS doivent être confirmés, datés et sourcés dans le registre réglementaire.

L'IRG doit être calculé par un moteur fiscal complet prenant en charge barèmes, exonérations, abattements et situations individuelles. **Le module actuel exige un montant IRG déjà validé et sa preuve ; il ne calcule pas l'IRG légal.**

Les bulletins sont confidentiels : les accès RH/paie et les téléchargements doivent être vérifiés sur le serveur. La migration 015 prépare un stockage privé, sans aucune activation automatique.

## Non disponibles
Émission légale de bulletins, transmission CNAS/DAS, CASNOS, écritures de paie, régularisation rétroactive, correction par bulletin rectificatif et clôture de paie.

Aucune des simulations ne doit être distribuée comme fiche de paie officielle.

## Simulation IRG mensuelle (nouveau prototype)

Dans **RH**, une rubrique de simulation IRG est réservée aux utilisateurs ayant
le droit spécifique `Paie / lecture`. L'accès général RH ne suffit pas.
Elle ne demande aucun identifiant d'employé ni ne sauvegarde la valeur saisie.

Le calcul exige le registre `regles_reglementaires` non ambigu et une règle
`IRG_SALAIRES_MENSUEL` confirmée, avec barème annuel, abattement de base,
seuil d'exonération et coefficients des abattements complémentaires.

Référence publique de contrôle : [DGI — IRG traitements et salaires](https://www.mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires).

**Non opérationnel pour paie officielle :** aucune règle légale n'est chargée
par défaut dans Supabase. Le prototype traite les revenus mensuels réguliers
uniquement ; les primes exceptionnelles, revenus occasionnels, particularités
individuelles et arrondis légaux doivent être validés avec un professionnel
avant émission.
