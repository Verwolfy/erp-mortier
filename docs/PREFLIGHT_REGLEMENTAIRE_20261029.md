# Préflight réglementaire — 29 octobre 2026

**Pourquoi :** la migration 021 a installé 2 taux généraux TVA, 1 règle G50 et 25 comptes SCF de référence. Cela ne prouve ni le régime fiscal de l'entreprise, ni l'éligibilité TVA d'un SKU, ni l'existence d'une comptabilité SCF prête.

**Comment :** le module `core/preflight_reglementaire.py` lit, sous client serveur privé, cinq registres de manière exhaustive (comptage exact) et fournit un diagnostic *en lecture seule*. Il refuse les réponses incomplètes et les références contradictoires. Il n'a aucun mécanisme de validation automatique d'un taux par produit et renvoie explicitement `facturation_reglementaire_prete=false` et `comptabilisation_scf_prete=false`.

L'outil est un diagnostic technique, **pas une homologation fiscale ou comptable**. Les taux TVA généraux et les comptes SCF restent documentés dans `docs/REFERENTIELS_OFFICIELS_2026.md`.

**Étape suivante :** établir la classification juridiquement étayée des produits et la configuration de l'entreprise, puis tester les parcours facturation → règlement → SCF avant toute activation. Aucune donnée juridique fictive, aucune écriture métier et aucune migration supplémentaire ne sont ajoutées ici.
