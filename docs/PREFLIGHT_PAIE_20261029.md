Diagnostic préalable IRG/CNAS — 29 octobre 2026

Pourquoi : l'habilitation RH/Paie a été renforcée, mais les paramètres juridiques de paie restent distincts de la gestion du personnel. L'absence de barèmes datés bloque les calculs officiels.

Comment : le nouvel onglet RH → Préparation Paie IRG / CNAS vérifie à une date sélectionnée les références CNAS_SALARIE_TAUX, CNAS_EMPLOYEUR_TAUX et IRG_SALAIRES_MENSUEL. Les registres sont lus en totalité (compteur exact). Les règles contradictoires, les sources absentes, les périodes invalides et les taux sociaux hors limites bloquent le diagnostic.

L'outil ne lit aucune fiche salarié, aucun salaire et aucune donnée personnelle. Il n'émet aucun bulletin et ne comptabilise aucune cotisation. Les valeurs absentes sont signalées, jamais inventées.

Le rôle courant est revérifié dans Supabase avant consultation. Les données de test sont synthétiques et ne constituent pas une norme algérienne.

Restent nécessaires pour une utilisation légale : barèmes IRG/CNAS officiels complets à date, qualification des assiettes et profils individuels, règles des primes, congés, plafonds et retenues, validation comptable et tests de paie bout en bout.

## Contrôle des unités et montants — correctif

**Pourquoi :** l'unité `pourcentage` (ex. 9) ne doit jamais être interprétée comme une fraction (ex. 0,09). Les références de taux CNAS ne sont exploitables que si leur unité est exactement `fraction`, avec une valeur comprise entre 0 et 1.

**Comment :** le moteur de sélection réglementaire accepte désormais l'exigence explicite `unite_attendue="fraction"`. Le préflight IRG/CNAS et la préparation non officielle de paie utilisent ce contrôle ; tout paramètre incompatible, incomplet ou ambigu bloque le calcul. La somme salaire de base + primes est également contrôlée contre le dépassement de limite décimale.

**Portée :** aucun taux réel n'a été ajouté et aucune fiche de paie n'a été modifiée. Les fixtures de tests utilisent uniquement des valeurs synthétiques, isolées de Supabase.
