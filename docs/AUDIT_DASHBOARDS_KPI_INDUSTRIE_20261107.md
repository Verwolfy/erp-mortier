# Audit détaillé — Tableaux de bord & KPIs Sofiane ERP
**Date : 7 novembre 2026. Dépôt :** `Verwolfy/erp-mortier` — module `modules/dashboards`.  
**Domaine :** fabrication/conditionnement de matériaux de construction, matières premières, emballages, produits finis, distribution B2B et recouvrement.

## 1. Diagnostic sur le code source (état initial)
Le module comporte **9 onglets**. Les calculs sont implémentés dans `modules/dashboards/service.py`, l'affichage dans `views.py`, et les lectures passent par `core.strict_reads`. Le contrôle d'accès `Dashboards:lecture` précède les onglets ; les 9 vues sont isolées par `read_section`. Un cache de portée **un seul rendu** réduit les lectures de table répétées, mais ne remplace ni une lecture paresseuse d'onglet ni un snapshot SQL transactionnel.

| Rubrique | KPI existants | Lacunes observées | Évolution intégrée dans la PR |
|---|---|---|---|
| Direction | Facturation brute HT du mois, trésorerie indicative, créances >30 j, stocks sous seuil | Valeurs sans objectif ni série, fenêtres hétérogènes | Périmètre conservé, libellés prudents |
| Rentabilité | Facturation brute, coût PF au coût **actuel**, OPEX payées, nets de paie, solde estimé | Terme EBITDA impropre pour une vraie comptabilité ; absence de cascade graphique ; % indéfini si CA = 0 | Cascade **waterfall** et taux **N/D** sans dénominateur |
| Ventes | Facturation HT/TTC, panier moyen, avoirs, balance âgée, top clients | Pas de série temporelle ; top clients seulement tabulaire ; ratio 0/0 trompeur | Courbe journalière réelle, classement horizontal, ratio N/D |
| Achats | Montant commandes, retards, fournisseurs, évolution prix | « Achats » ≠ réception/facturation ; prix d'origine en devises mêlées ; coercition `NaN→0` | Libellé commande, prix converti en **DZD/unité de stock**, refus des faux zéros |
| Stocks | Valeur MP/PF, seuils, lots à risque | Lots déjà périmés mêlés aux échéances futures ; absence de date de péremption à signaler | Comptage **périmés / bientôt échus / dates inconnues** distinct |
| Production | Nb OF planifiés, statuts, ratio CQ rejeté | OF datés par planification ≠ contrôles datés par contrôle ; 0 % sans CQ ; seuil de rejet 5 % arbitraire | Achèvement de cohorte, nombre de contrôles, ratio CQ **N/D** si aucun, histogramme OF/jour, suppression du 5 % arbitraire |
| CRM | Pipeline pondéré ouvert, conversion des affaires créées sur la période, gagnées par commercial | Conversion 0 % affichée sans affaire close | **N/D** si aucun dossier clos, bars horizontales |
| RH | Effectif actif, congés en attente, service | Vision stock actuelle, sans absences effectives ni historique fiable | Périmètre conservé : aucune mesure RH inventée |
| Finance | Entrants, sortants, % montant affecté, soldes indicatifs actuels | Pas de flux net ni série ; taux 0 sans encaissement ; soldes actuels indépendants du filtre | Flux net, non affecté, séries entrées/sorties, ratio N/D |

## 2. Définitions à appliquer
- **Facturation brute HT** : somme des `FactureClient` `VALIDE` dans la période, **hors avoirs**. Ne pas appeler « CA net encaissé ».
- **Créances >30 jours** : soldes des factures client validées non payées, dont le retard dépasse 30 jours. **Instantané global**, même si un filtre de dates est sélectionné.
- **Solde de trésorerie indicatif** : solde initial des comptes Banque/Caisse + règlements `VALIDE` jusqu'au jour de lecture ; non rapproché avec la banque.
- **Commandes d'achat** : valeur engagée des commandes **datées** de la période ; ≠ achats reçus ni factures fournisseurs.
- **Taux de rejet CQ** : `nb contrôles NON / nb contrôles disponibles` sur les dates des contrôles. Si aucun contrôle, afficher **N/D**, pas 0 %. Ce taux n'est PAS le taux de rebut matière/quantité.
- **Achèvement de cohorte OF** : `nb OF de statut actuel TERMINE / nb OF dont la date de planification est dans la période`. Il ne mesure ni la ponctualité ni le rendement.
- **Taux d'affectation** : `montant d'encaissements affecté / encaissements validés` dans la période. Pas un lettrage comptable certifié.
- **Pipeline pondéré** : somme `valeur estimée × probabilité` des opportunités ouvertes à date ; sans lien automatique avec facturation.
- **Indicateur N/D** : dénominateur nul, source insuffisante ou absence de constat : ne jamais afficher un faux 0 %, une cible inventée ni une extrapolation.

## 3. Bonnes pratiques de visualisation et gouvernance
1. **Objectif métier avant graphique** : une carte par décision (trésorerie, retards, créances, OF/CQ, rupture), les détails dans l'onglet métier.
2. **Période visible et comparable** : indiquer si l'indicateur est sur la période filtrée, global, ou à aujourd'hui. Ne jamais comparer des mois incomplets à des mois complets sans étiquette.
3. **Unité explicite** : DZD, DZD/unité de stock, OF, contrôle CQ, %, jour. Pas de graphique croisant des grandeurs disparates sur une même échelle.
4. **Types de graphiques** : lignes pour dates/évolutions ; barres horizontales pour fournisseurs, clients, services et statuts ; waterfall pour reconstitution de solde ; tableau pour traçabilité et diagnostic.
5. **Zéros honnêtes et barres comparables** : pas de prix `NaN→0`, pas de courbe à zéro fabriquée lorsque la série est vide ; tri des catégories par importance, comparateurs sur une seule unité.
6. **Signification des couleurs** : couleur + texte/label, jamais couleur seule. Pas de seuils rouge/vert arbitraires : objectifs validés à configurer dans un futur référentiel.
7. **Provenance et fraîcheur** : nom du KPI, population, date de référence, source, définition et dernière extraction. Les KPIs de plusieurs lectures API ne sont pas des instantanés transactionnels.
8. **Accessibilité** : souris + clavier + tactile ; explication au survol/clic, tableau alternatif pour analyses détaillées.
9. **Sécurité** : respect des droits Dashboards et des droits sur chaque source, pas d'appel à `service_role` côté navigateur, pas d'export de données non autorisées.
10. **Performance** : cache limité à un rendu, filtres serveur, agrégations SQL validées quand la volumétrie l'exigera ; envisager le **chargement paresseux** des onglets (les `st.tabs` actuels exécutent leur contenu).

## 4. KPI industriels pertinents, mais NON calculables avec les données actuelles
| KPI cible | Formule / utilité | Données supplémentaires nécessaires |
|---|---|---|
| TRS / OEE | Disponibilité × Performance × Qualité | Journal machine, temps planifiés, arrêts, cadence nominale, quantités bonnes/rebutées |
| Rendement matière par formulation | Quantité conforme / matière engagée, sur des unités homogènes | Matières effectivement pesées par OF et produit, pertes, densités lorsque pertinentes |
| Coût réel par kg / SKU | Coûts de production réels validés / quantité conforme | Écritures SCF validées, périodes analytiques clôturées, coût énergétique et OF éligibles |
| OTIF fournisseur ou client | Livraisons à la date promise **et** en quantité complète / livraisons attendues | Dates promises et réalisées, quantités demandées et réellement livrées, règles de tolérance |
| Rotation des stocks / DIO | Consommation ou COGS historique / stock moyen comparable | Historique fiable des coûts, quantités et valorisations par intervalle |
| DSO rigoureux | Créances + facturation sur une fenêtre comparable (définition approuvée) | Règles de calcul validées, convention de périmètre, dates et traitement des avoirs |
| Taux de rupture et couverture de stock | Nombre de ruptures / couverture en jours selon consommation réelle | Chronologie des sorties et prévisions validées de la demande |
| Réclamations / lots non conformes | Événements par lot / unités distribuées | Réclamations client datées, lots vendus, modalités de comptabilisation |

**Important :** ne jamais produire OEE, OTIF, DSO, rendement kg ou coût unitaire industriel par inférence d'un autre KPI. Des données manquantes doivent être déclarées **non disponibles**.

## 5. Ordre de mise en œuvre
- **P0 (sans migration DB)** : libellés honnêtes, graphiques fondés sur les transactions validées, ratios N/D, prix convertis, risques stocks séparés, tests — **développement soumis à PR, CI obligatoire**.
- **P1 (après qualification métier)** : objectifs paramétrables datés, comparaison avec période précédente de même longueur, annotations d'écarts et actions recommandées, dictionnaire des KPI approuvé.
- **P2 (migrations après accord)** : journaux machine/arrêt/qualité, historique d'inventaire, engagements de livraison et snapshots analytiques ; calculs TRS, OTIF, consommation kg, coûts industriels réels.

## 6. Références externes méthodologiques
- ISO 22400 (définitions des indicateurs de production) : https://www.iso.org/obp/ui/ — section ISO 22400.
- Microsoft Learn — Designing Power BI dashboards : https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboards-design-tips
- Microsoft Learn — KPI visuals : https://learn.microsoft.com/en-us/power-bi/visuals/power-bi-visualization-kpi
- Microsoft Fabric — Data visualization accessibility : https://github.com/microsoft/skills-for-fabric/blob/main/skills/powerbi-report-cli/references/design/accessibility.md

**Aucun changement de la base de production, de RLS, des GRANT, des secrets ou des écritures comptables n'est requis pour P0.**
