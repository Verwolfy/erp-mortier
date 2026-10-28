# ERP Mortier — à valider avant activation réglementaire

_Mise à jour au 28 octobre 2026. Aucun paramètre réel n'est inséré automatiquement._

| Domaine | État vérifié | Condition d'activation |
|---|---|---|
| TVA | La DGI présente le taux normal 19 % et réduit 9 %, et des faits générateurs distincts selon la nature de l'opération : https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee | Régime fiscal, classification de chaque article, exonération, taux réduit, date juridique et assiette par ligne ; tests complets |
| Timbre quittance | Art. 46 de la LF 2025 (JO n° 84 du 26/12/2024) : classes de montant par tranche de 100 DA ou fraction, minimum 5 DA et art. 47 sur paiement électronique : https://www.joradp.dz/FTP/jo-francais/2024/F2024084.pdf | Vérifier Code du timbre consolidé 2026 et périmètre des reçus ; lier à un **paiement constaté**, non à la simple facture |
| Timbre actuel en production | Ancienne formule `1 %` plafonnée `2 500 DA` dans Python et SQL 005 ; **écart confirmé avec l'art. 46** | Migrer le circuit règlement/quittance, traiter paiements partiels et exceptions, puis basculer Python+SQL atomiquement après validation |
| Nouveau calculateur de timbre | `core/timbre_quittance.py` permet les classes par montant, la fraction de tranche et l'exonération électronique à partir d'une règle versionnée | Tests et validation juridique ; aucune valeur légale n'est activée dans Supabase |
| Avoirs historiques | Taux TVA d'origine à respecter ; SQL 013, non appliqué, refuse certains avoirs à taux différent | Développer rapprochement document original et tests de non-réécriture |
| IRG/CNAS | Modules de simulation paramétrables, sans barèmes officiels activés | Vérification CNAS, IRG, abattements, règles de paie et preuves |
| SCF | Nouvelles tables installées et protégées ; calculs préparatoires et balance en lecture | Revue comptable, plan de comptes, liaisons ventes/achats/paie et états officiels |
| Supabase | Registre SQL 012, SCF 014 et Paie 015 appliqués sous les noms migrations Supabase 016–018 ; index SQL 019 appliqués | SQL 013 **non appliqué**, car bloquerait les ventes sans paramètres |
| Permissions | 66 différences d'ACL `service_role` sur anciennes tables TEST/production ; nouvelles tables identiques, RLS active | Ne pas appliquer de GRANT/REVOKE global ; documenter une éventuelle exception par usage |
| Sauvegarde PostgreSQL | L'utilisateur a explicitement écarté cette étape obligatoire | Ne pas lancer `pg_dump` ; contrôles des opérations destructrices maintenus |

Le code fiscal ne constitue pas une conformité réglementaire attestée.
La production conserve actuellement le circuit Ventes existant jusqu'à une
bascule coordonnée et validée. Aucune facture ancienne n'est modifiée.
