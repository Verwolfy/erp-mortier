# Modèles NEXTGEN : fiches techniques (FT) et fiches de données de sécurité (FDS)

Date d'intégration : 3 novembre 2026. Statut : **brouillons uniquement, non validés**.

## Référence graphique commune

Le visuel de facture fourni dans la conversation sert de **référence de présentation**, non de modèle juridique pour les FDS.

- A4 portrait, identité NEXTGEN et logo en haut.
- Couleurs dominantes bleu marine (environ #0A3153), vert (#09944E), encarts gris clair.
- Bandeau central du titre, tableaux de métadonnées (référence, révision, date, code produit).
- Encart d'identification du produit, rubriques hiérarchisées et séparées, lisibles en multipage.
- Pied de page : adresse, RC, NIF, contact ; pagination.
- QR : **identifiant interne hors ligne**. Aucune URL de suivi ou disponibilité publique n'est simulée.
- Traçabilité documentaire : identifiant unique, version et date, emplacements de rédaction, vérification et approbation.
- Texte « BROUILLON - DOCUMENT TECHNIQUE NON VALIDÉ » affiché dans les exports.

### À ne pas recopier depuis la facture

Aucun prix, TVA, total TTC, échéance de paiement, client facturé, montant en lettres, ni signature commerciale : ces éléments ne sont pas adaptés à une FT/FDS.

## Fiche technique (FT)

Dix rubriques : identification, applications, performances documentées, supports, mode d'emploi, consommation, conditionnement/conservation, précautions, normes/essais, assistance et observations.

L'utilisateur renseigne les données **mesurées ou vérifiées**. Ne jamais déduire des temps de prise, dosages, rendements, densités, classes EN/ISO, compositions ou performances de la seule désignation commerciale.

## Fiche de données de sécurité (FDS)

Seize rubriques du format général SGH : identification, dangers, composition, premiers secours, lutte contre l'incendie, dispersion accidentelle, manipulation/stockage, exposition/protection, propriétés physico-chimiques, stabilité/réactivité, toxicologie, écologie, élimination, transport, réglementation, informations complémentaires.

**Important :** la présence de seize rubriques ne certifie **ni la complétude ni la conformité** de la FDS. Toute classification, pictogramme, mention H/P, substance/CAS, numéro d'urgence, EPI, mesure d'intervention et donnée réglementaire doit provenir d'une source adaptée, vérifiée par le responsable compétent. Le format doit être contrôlé au regard du pays de commercialisation et de la réglementation applicable.

Référence générale de structure : [ONU CEE/UNECE — SGH, annexe 4, guide de préparation des FDS](https://unece.org/ghs-rev7-2017).

## Utilisation dans l'ERP

1. Ouvrir **Documents administratifs > Module : Fiches produits**.
2. Sélectionner « Fiche technique » ou « Fiche de données de sécurité ».
3. Renseigner référence, révision, produit, code/SKU, date, conditionnement, responsable et rubriques.
4. Exporter PDF, Word modifiable ou JSON. La session n'écrit pas dans Supabase.
5. Faire vérifier les données puis suivre le processus de validation documentaire **en dehors de cet écran** ; l'émission officielle n'est pas disponible dans ce module.

Code : modules/documents/product_sheets.py ; intégration : modules/documents/views.py ; tests : tests/test_product_sheets_nextgen.py.

## Limites et évolutions

- Le modèle ne récupère pas encore les FT/FDS fournisseurs ni les données certifiées de site_produits/SKU.
- Aucun contenu technique ou danger n'est prérempli automatiquement ; les champs restent vides.
- La signature et l'approbation sont des emplacements, **pas une validation électronique**.
- Le QR contient seulement un JSON d'identité. Il ne dirige pas vers un service de suivi.
- Avant diffusion : appliquer une procédure de validation humaine et contrôler les obligations locales.
- Vérifier visuellement les exports PDF/Word et les tests CI après déploiement.
