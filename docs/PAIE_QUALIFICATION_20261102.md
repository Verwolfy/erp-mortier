# Qualification des références de paie — 2 novembre 2026

## État : NON QUALIFIÉ

Aucune référence n’a été insérée ni activée dans Supabase. Le diagnostic ne porte ni sur la paie de salariés réels, ni sur une déclaration. Les champs du registre ne doivent pas être marqués `CONFIRMEE` tant que la portée, la version et le calcul n’ont pas été vérifiés.

## Cotisations : périmètre à clarifier

Le [Journal officiel n° 49 du 16 septembre 2015, page 7, décret exécutif 15-236](https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf) modifie l’article 2 du décret 94-187 et présente, pour les branches listées, 25 % à la charge de l’employeur, 9 % à la charge du salarié, 0,5 % à la charge du fonds des œuvres sociales, soit 34,5 %. Ces montants caractérisent ce tableau ; ils ne démontrent pas, à eux seuls, le coût employeur complet ni l’absence d’autres contributions.

Le code `CNAS_EMPLOYEUR_TAUX` est utilisé dans `core/paie_preparation.py` pour le calcul `cout_employeur = brut + cotisation_employeur`. Avant de le qualifier, identifier précisément si ce champ doit représenter uniquement la quote-part du tableau ou le total des contributions patronales et quel traitement distinct appliquer aux autres contributions. Vérifier sur textes officiels ultérieurs, catégories, exonérations et date d’effet applicable. Il serait trompeur d’afficher un coût employeur complet sans préciser ce périmètre.

Le champ `CNAS_SALARIE_TAUX` peut être rapproché des 9 % du tableau, mais la version en vigueur, l’assiette, les exceptions et la date d’effet restent à vérifier pour le contexte de l’entreprise avant activation. Un pourcentage vérifié ne valide pas automatiquement l’assiette individuelle.

## IRG : rapprochement documentaire partiel

La [DGI décrit le calcul](https://mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires) et publie une [table mensuelle rectifiée 2022](https://www.mfdgi.gov.dz/images/bareme_irg/TABLE_IRG_2022.pdf). Il faut confirmer sa portée en 2026, ses catégories particulières, la détermination et l’arrondi de l’assiette, ainsi que les règles d’arrondi intermédiaire et final.

Comparaison du moteur actuel en utilisant exclusivement la fixture locale `tests/test_irg_salaires.py` (date/statut de règle fictifs) et les lignes de la table DGI 2022 :

| Assiette mensuelle fictive | Catégorie | Table DGI 2022 (DA) | Moteur actuel (DA) | Écart moteur - table (DA) |
|---:|---|---:|---:|---:|
| 33 000 | Cas général / SALARIE | 1 328,60 | 1 328,55 | -0,05 |
| 35 000 | Cas général / SALARIE | 2 070,00 | 2 069,96 | -0,04 |
| 35 010 | Cas général / SALARIE | 2 071,40 | 2 071,38 | -0,02 |
| 50 000 | Cas général / SALARIE | 5 800,00 | 5 800,00 | 0,00 |

La comparaison ne tranche pas si la table ou une formule avec arrondi final doit être utilisée pour chaque situation. Les différences sont mesurées, leur origine et le mode d’arrondi légal ne sont pas encore établis ; ne pas simplement modifier l’arrondi pour faire correspondre quelques lignes. Les cas particuliers et les limites doivent être examinés séparément. La fixture de test n’est pas un paramétrage juridique de production.

## Étapes restantes

1. Obtenir une source officielle consolidée et datée couvrant toutes les cotisations et contributions concernées et leurs assiettes ; définir les champs distincts et la portée du coût employeur.
2. Établir les règles exactes d’arrondi IRG et la compatibilité de la table DGI avec la date cible, puis confronter le moteur à un ensemble représentatif de lignes, seuils et catégories, y compris entrées non multiples de 10 DA.
3. Préparer des données de référence traçables avec dates, unités et sources ; confirmer les droits et vérifier les registres sans doublons avant toute écriture. Tester sans paie réelle.
4. Maintenir l’interdiction de bulletin officiel tant que les profils, assiettes, règles, validation et circuit légal ne sont pas établis. Ne pas réveiller le projet TEST.


## Périmètre choisi par l’utilisateur — 2 novembre 2026

- Phase initiale : salariés du **régime général**. Les autres profils sont hors périmètre et ne doivent pas être traités par défaut comme un salarié général.
- Le coût employeur recherché doit être aussi complet que possible, avec chaque contribution détaillée et son assiette, sa période et sa source. Distinguer les montants établis des montants non calculables ; ne jamais remplacer une contribution inconnue par zéro.
- Finalité : préparer à terme des bulletins utilisables par l’entreprise, après vérification complète des règles, des arrondis et des profils ; ne pas lever les blocages actuels au seul motif de ce choix.

### Contribution formation et apprentissage : portée

La [loi de finances 2026, articles 18 à 20](https://dgb.mf.gov.dz/wp-content/uploads/2026/01/LF-2026.pdf), modifie les articles 196 bis, 196 quater et 196 quinquies du CIDTA : les deux dispositifs ont une assiette de masse salariale brute **semestrielle** et leur calcul tient compte des dépenses éligibles du semestre. Ces taxes ne peuvent pas être ajoutées mécaniquement comme deux taux fixes à chaque bulletin individuel. Il faut vérifier le champ d’application, les exonérations, les dépenses et les justificatifs propres à l’entreprise et à la période avant de calculer un montant.

Le calcul d’un coût employeur individuel complet nécessite une règle documentée de répartition des charges collectives lorsqu’une telle répartition est pertinente. À défaut, les présenter séparément comme montant collectif non attribué ; ne pas inventer de clé de répartition ni traiter les fiches fictives comme effectif réel.

### Validation réglementaire encore nécessaire

La table IRG 2022 et le moteur divergent de quelques centimes dans les cas rapportés ci-dessus. Les conditions d’arrondi, la date d’effet de la table et son utilisation pour des bases non multiples de 10 DA ne sont pas encore établies. La preuve d’un cas concordant ne valide pas l’ensemble du barème. Les deux références CNAS et le barème restent absents du registre actif ; aucune écriture ni changement de permission n’a été effectué.


## Précisions fournies par l’utilisateur — 2 novembre 2026

- Effectif réel annoncé : **moins de 20 employés**, en excluant les dix fiches fictives `SIM-RH-`. Cette déclaration décrit la situation indiquée ; elle ne prouve pas l’effectif à chaque période ni la méthode juridique de décompte.
- Premier modèle : salaire de base, prime de rendement mensuelle et prime de panier. Le caractère mensuel ne suffit pas à déterminer le traitement social ou fiscal ; documenter séparément conditions d’attribution, pièces et règles applicables à chaque composante. Les rappels et primes non mensuelles restent hors de ce premier périmètre.
- Charges collectives : une répartition est souhaitée lorsqu’elle est nécessaire, avec une **clé propre à chaque charge** ; aucune clé n’a encore été choisie pour un poste donné. Une charge non déterminée ou non répartissable reste indiquée comme telle et ne devient pas zéro.

### Textes et incidence sur le périmètre déclaré

L’article 56 de la [loi de finances 2022, JO n°100](https://www.joradp.dz/FTP/jo-francais/2021/F2021100.pdf), a introduit l’article 196 ter prévoyant une exonération de la **taxe de formation professionnelle** pour les employeurs de moins de vingt employés. La [loi de finances 2026, articles 18 à 20](https://dgb.mf.gov.dz/wp-content/uploads/2026/01/LF-2026.pdf), modifie séparément le champ, l’assiette et le taux des taxes de formation et d’apprentissage. Vérifier le texte consolidé, la période, la définition de l’effectif et les déclarations avant d’appliquer cette exonération ; ne pas l’étendre automatiquement à l’apprentissage.

La [DGI, traitements et salaires](https://mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires), distingue diverses indemnités et rémunérations pour l’IRG. Elle ne suffit pas à qualifier automatiquement la prime de panier particulière de l’entreprise, ni son assiette sociale ; vérifier les textes et justificatifs spécifiques.

### Matrice de réalisation

| Poste | Décision de produit | État de qualification |
|---|---|---|
| Base | Salaire de base du régime général | Assiettes et profils à vérifier |
| Rendement | Prime mensuelle distincte | Règles sociales/fiscales à vérifier |
| Panier | Prime mensuelle distincte | Conditions et traitement à vérifier, sans présumer une exonération |
| CNAS salarié | Retenue séparée | Texte, date d’effet et assiette à confirmer pour le profil |
| CNAS employeur | Contribution distincte | Périmètre et autres contributions à confirmer |
| Formation / apprentissage | Charges collectives semestrielles distinctes | Éligibilité et justificatifs par période à vérifier |
| Répartition | Choisir une clé par charge | Aucune clé choisie ; ne pas répartir par défaut |
| IRG | Régime général mensuel initialement | Écarts d’arrondi avec la table à résoudre |

Aucun montant de rémunération réel, dossier individuel, taux qualifié ou règle active n’a été ajouté à Supabase à partir de ces choix.


## Essai d'arrondi non déployé

Le [Journal officiel n°57 du 31 décembre 1990, article 324](https://www.joradp.dz/FTP/Jo-Francais/1990/F1990057.pdf) énonce une règle générale pour l'assiette et les cotisations, sous réserve des dispositions spéciales ; sa version applicable au salaire et aux retenues pour la période visée reste à vérifier dans le code consolidé et les instructions pertinentes. Ne pas confondre cet article avec une règle générale établie spécifiquement pour toutes les étapes des retenues sur salaires.

L'essai local arrondit **après le calcul actuel** au dixième de dinar le plus proche, avec égalité arrondie vers le haut. Sur les quatre exemples de cas général (33 000, 35 000, 35 010 et 50 000 DA), il reproduit les quatre valeurs publiées dans la table DGI 2022 citée plus haut. C'est une hypothèse expérimentale, non une preuve de conformité. Les multiples arrondis intermédiaires, les bases non multiples de 10, les seuils et la version applicable ne sont pas établis. Le script de test est `tests/test_irg_recherche_arrondi.py` ; il ne change ni le moteur ni les données de production.

La [DGI annonce la publication des codes fiscaux 2026](https://mfdgi.gov.dz/fr/a-propos/actu-fr/codes-fiscaux-fr), mais le téléchargement du code consolidé n'a pas abouti lors de cette recherche. Obtenir l'édition applicable et comparer les articles pertinents, les dispositions spéciales et, si disponibles, les instructions de calcul avant toute qualification.
