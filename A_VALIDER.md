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


## Sécurisation du simulateur fiscal historique — 29 octobre 2026

La DGI confirme sur son portail actualisé le 23 février 2026 que la TVA
normale est de **19 %**, la TVA réduite de **9 %** et que le fait générateur
diffère selon vente, prestation et travaux :
https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee

Le droit de timbre de quittance relève de l'article 100 du Code du timbre,
modifié par la loi de finances 2025, articles 46 et 47, JO n°84 du
26 décembre 2024 : https://www.mf.gov.dz/images/pdf/loidefinance/Loi_de_finance_2025_FR.pdf
La DGI a publié un **Code du timbre consolidé 2026** :
https://www.mfdgi.gov.dz/fr/a-propos/actu-fr/codes-fiscaux-fr

En conséquence, le moteur dormant `core/fiscalite_facturation.py` **refuse
dorénavant tout calcul de facture espèces** au lieu de produire 1 % plafonné
à 2 500 DA. Son service de lecture n'interroge plus les anciens paramètres
de timbre. Ce correctif **ne modifie pas** la RPC Ventes actuellement
utilisée, qui conserve temporairement l'ancienne formule : ce point demeure
bloquant pour certifier la facturation comme conforme.

Avant la bascule réelle :
- classifier les articles et le régime fiscal (exonération, 9 %, 19 %) ;
- séparer facture/avoir, encaissement et éventuelle quittance ;
- confirmer le Code du timbre 2026 et les exemptions applicables ;
- traiter les règlements partiels, modes de paiement et avoirs historiques ;
- installer et tester une nouvelle fonction transactionnelle Ventes plutôt
  que rejouer aveuglément l'ancien fichier `sql/013`.


## Référentiels 2026 officiels — état au 29 octobre 2026

Le lot 021 a importé sur TEST et PRODUCTION :
- TVA normale DGI : **19 %** ; TVA réduite DGI : **9 %**.
- Règle G50 mensuelle du régime réel, `application_entreprise=NON_CLASSEE`.
- 25 comptes de la nomenclature SCF officielle, **tous inactifs/non mouvementables**.

Il reste à confirmer le régime d'imposition de l'entreprise, classifier
chaque SKU avec preuve juridique et date d'effet, puis définir le plan
comptable réellement mouvementable, les journaux et exercices.
**La présence des taux de référence ne constitue pas une autorisation
de facturer sans classification.**

Références et date de vérification :
`docs/REFERENTIELS_OFFICIELS_2026.md`.
