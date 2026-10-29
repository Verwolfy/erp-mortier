# Référentiels algériens officiels — instantané 2026

**Vérification le 29 octobre 2026.** La migration
`sql/021_referentiels_2026_officiels.sql` est une **initialisation contrôlée**.
Les textes et taux sont recherchés dans les sources publiques officielles.
**Ne pas inventer de données fiscales, comptables ou sociales pour combler
les inconnues.**

## Sources vérifiées et portée

1. **DGI Algérie, « La taxe sur la valeur ajoutée (TVA) »**, page mise à
   jour le 23 février 2026.
   https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee

   Taux normal **19 %**, taux réduit **9 %**. Ce dernier ne s'applique
   qu'aux opérations classées à l'article 23 du CTCA. Les exemptions
   sont définies dans d'autres articles. La DGI précise notamment
   que les assujettis au **régime IFU ne sont pas concernés par la TVA**.
   La G50 mensuelle concerne le régime réel dans les 20 premiers
   jours du mois suivant la période déclarée.

2. **Loi n° 25-17 du 14 décembre 2025, LF 2026**, Journal officiel n° 88
   du 31 décembre 2025, notamment **article 53**, qui étend des cas
   relevant du taux réduit.
   https://www.mf.gov.dz/images/pdf/loidefinance/Loi_de_Finances_2026_FR.pdf

3. **Arrêté du 26 juillet 2008**, système comptable financier, publié
   au Journal officiel n° 19 du 25 mars 2009, nomenclature pages
   40–44 et règles de fonctionnement.
   https://www.joradp.dz/FTP/jo-francais/2009/F2009019.pdf
   Présentation par le ministère des Finances :
   https://www.mf.gov.dz/pdf/Le_Systeme_comptable_Financier.pdf

4. **Codes fiscaux algériens édition 2026** publiés par la DGI le
   7 mai 2026, dont Code du timbre 2026 et CTCA 2026 :
   https://www.mfdgi.gov.dz/fr/a-propos/actu-fr/codes-fiscaux-fr

## Ce que la migration insère

- **Deux paramètres de référence** : `TVA_TAUX_NORMAL` = 0,19 et
  `TVA_TAUX_REDUIT` = 0,09, juridiquement documentés et datés.
  Ils ne correspondent **PAS** au code technique `TVA_VENTE_TAUX`
  de la facturation ; aucune facture n'obtient automatiquement
  l'un ou l'autre taux.
- **Une règle déclarative** `TVA_G50_MENSUEL_REGIME_REEL`, avec
  calendrier de principe : 20 premiers jours du mois suivant ;
  `application_entreprise=NON_CLASSEE` pour empêcher de la
  considérer comme une obligation déterminée pour l'entreprise.
- **25 comptes de nomenclature SCF** issus du texte officiel,
  notamment 401 fournisseurs, 411 clients, 421 personnel, 431
  sécurité sociale, 445 taxes sur le CA, 512 banques comptes
  courants, 53 caisse, 601 matières premières, 701 ventes de
  produits finis. **Tous sont initialement `actif=false` et
  `mouvementable=false`.**

Le champ `date_effet='2026-01-01'` dans les références TVA et G50
délimite le **périmètre annuel de cet instantané 2026**, et non
la date d'adoption historique des taux. Pour les opérations
antérieures ou futures, il faut vérifier la version juridique
qui leur est applicable.

## Ce qui n'est volontairement PAS inséré

- Aucun taux `TVA_VENTE_TAUX` applicable indistinctement aux
  produits de la société, aucune fiscalité inventée par SKU.
- Aucune grille IRG ou taux CNAS sans vérification complète des
  assiettes et exemptions, aucune fiche de paie.
- Aucun **barème actif de timbre** sans analyse complète du
  Code du timbre 2026, des types de quittance, des exemptions et
  des modes de paiement.
- Aucun journal ni exercice comptable arbitraire ; aucun solde
  d'ouverture ni pièce SCF fictive.
- Aucun changement à la RPC `erp_sale_transaction`, aux
  factures ou aux anciennes écritures.

## Vérifications de sécurité

La migration est **atomique** et **relançable** sur une base
préexistante vide : `ON CONFLICT DO NOTHING` suivi de vérifications
qui annulent le lot si une référence contradictoire existe.
Elle ne change ni les permissions RLS ni les droits `GRANT`.

Avant mise en fonctionnement effectif, la société devra
confirmer son régime fiscal, identifier les SKU soumis à
19 %, à 9 % ou exonérés (avec justificatifs et date), approuver
le plan de comptes à utiliser et fournir ses journaux et
dates d'exercice. Le développement pourra alors mettre en
place des contrôles côté serveur et les écritures de bout en bout.

**Une entrée de référence « confirmée » ne constitue pas une
attestation de conformité fiscale de l'entreprise.**


## Déploiement constaté le 29 octobre 2026

La migration `erp_021_referentiels_officiels_dgi_scf_20261029` a été
**appliquée avec succès d'abord sur Supabase TEST, ensuite sur PRODUCTION**.
Contrôle SQL en lecture seule effectué immédiatement après chaque installation :

| Compteur | TEST | PRODUCTION |
|---|---:|---:|
| Taux TVA généraux sourcés | 2 | 2 |
| Règle G50 du régime réel | 1 | 1 |
| Comptes SCF proposés | 25 | 25 |
| Comptes SCF actifs ou mouvementables | 0 | 0 |
| Journaux, exercices et pièces SCF | 0 | 0 |
| Taux universel de facturation | 0 | 0 |
| Factures historiques | 1 | 1 |

La RLS de `scf_plan_comptes` reste active et `anon` n'a pas
le droit de consultation. Les comptes sont disponibles pour revue,
**sans accès au moteur de comptabilisation**. La migration n'a
touché ni les factures ni les déclarations.

L'enregistrement des taux **ne valide pas** l'assujettissement de la
société ni la classification TVA de ses produits. Les nouvelles valeurs
ne sont pas raccordées au circuit transactionnel Ventes historique.
