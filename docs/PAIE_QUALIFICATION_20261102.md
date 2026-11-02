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
