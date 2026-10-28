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
