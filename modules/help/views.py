"""Guide utilisateur aligné sur les écrans disponibles, sans écriture métier."""
import streamlit as st
from modules.help.contextual import show_context_help, topic_help


HELP_SECTIONS = {
    "ⓘ Aide contextuelle (survol et clic)": """
**Dans chaque rubrique ERP :** survolez l'icône d'aide d'un titre, champ ou
bouton pour consulter une explication courte. Cliquez sur le bouton
**ⓘ Aide : [nom de la rubrique]** pour ouvrir trois points : notion,
comment procéder et contrôles avant validation.

Dans **Production > Consommations et contrôles**, choisissez la page
des historiques, puis cliquez sur **Afficher l'historique Production**.
Le chargement est volontairement manuel et paginé. Une liste vide ne signifie
pas nécessairement une erreur ni l'absence d'autres pages.

Sur téléphone ou tablette, utilisez l'aide cliquable plutôt que le survol.
Les aides ne changent jamais les permissions, montants, stocks ou pièces SCF.
Aucune transaction ne doit être rejouée après une réponse incertaine sans
vérifier d'abord la base.
""",
    "🏠 Introduction": """
Cet ERP centralise les référentiels, achats, stocks, production, ventes et suivis.
Les menus visibles dépendent de vos habilitations. Une session inactive expire
après 30 minutes ; reconnectez-vous si nécessaire.

**Enregistrement et sauvegarde sont distincts.** Une opération confirmée est
persistée en base ; cela ne constitue pas une sauvegarde PostgreSQL.
Une réponse réseau incertaine ne prouve ni le succès ni l'échec de l'opération.
Consultez la rubrique Incidents avant de recommencer une saisie.

**Consultation de contrôle :** utilisez les tableaux, filtres et historiques.
Ne validez aucune commande, réception, fabrication, facture ou paiement fictif
pour tester la production. Un tableau vide et une lecture en erreur ne sont pas
équivalents. Les simulations ne constituent pas une validation réglementaire.
""",
    "📄 Documents administratifs NEXTGEN": """
**Accès :** Administration > Documents NEXTGEN.

La bibliothèque regroupe 20 types de documents (Ventes, Achats, Stocks,
Production, Finance et RH). Saisir les données dans le formulaire, corriger les
lignes puis télécharger PDF, Word modifiable ou JSON.

Les exports sont des **BROUILLONS NON VALABLES** et ne créent aucune pièce dans
Supabase. La saisie reste libre ; le bouton « Charger les référentiels autorisés »
permet désormais de reprendre un client/fournisseur actif, un SKU actif
(Ventes) ou une matière première active (Stocks/Production), sous réserve des
droits de lecture ERP. Aucune opération métier ni aucun mouvement de stock n'est créé.
Le prix catalogue est uniquement indicatif et ne renseigne pas le devis
automatiquement. La quantité et le prix sont confirmés manuellement.
Les montants de lignes et le total HT sont calculés en Decimal ; le TTC
nécessite un montant de taxes saisi explicitement. Aucun taux de TVA n'est
déduit automatiquement. Les exports refusent des montants incohérents.
Aucune facture ou aucun avoir officiels ne sont émis.

Les brouillons peuvent être exportés en JSON puis réimportés depuis
« Reprendre un brouillon ». Seuls les JSON BROUILLON du même type sont
acceptés ; l'identifiant QR est conservé. Aucun historique serveur n'est créé.

Chaque création reçoit un identifiant QR aléatoire. Le QR encode cet identifiant,
le type, la date et le NIF de l'émetteur, sans données confidentielles.
Il ne constitue **pas encore** un lien de suivi en ligne ou un registre durable :
aucun portail de vérification ou historique de consultation n'a été déployé.
Ne pas annoncer une traçabilité juridiquement certifiée.

Logo et en-tête : SARL NEXT GENRATION BUILDING SOLUTIONS.
Pied de page : adresse Bouira, RC, NIF et courriel de facturation.
Une validation réglementaire reste nécessaire avant toute émission officielle.

**FT et FDS :** dans Documents administratifs > Module > Fiches produits,
choisir Fiche technique (10 rubriques) ou Fiche de données de sécurité
(16 rubriques SGH). Renseigner les éléments techniques à partir de sources
fiables, puis exporter un PDF, un Word modifiable ou un JSON. La présentation
reprend la charte de la facture NEXTGEN (bleu, vert, en-tête, QR interne,
mentions d'entreprise), mais jamais les montants ou les taxes.
Les champs non renseignés restent explicitement signalés ; aucun danger,
composition ni performance n'est déduit. Les exports FT/FDS sont des brouillons
non validés, sans enregistrement dans Supabase et sans suivi QR public.
Une vérification technique/réglementaire humaine est indispensable avant diffusion.
""",
    "⚙️ Administration & Référentiels": """
**Qualité référentiels :** Administration > Qualité référentiels >
« Analyser les référentiels autorisés ». Audit transversal lecture seule sur
Clients, Fournisseurs, Produits, SKU et Matières premières :
IDs manquants/doublons, désignations manquantes, SKU reliés à un produit
absent. Les inactifs sont comptés séparément (pas des erreurs).
Le rapport ne révèle ni coordonnées ni données individuelles. Les droits
de lecture serveur sont vérifiés sur chaque table : si une lecture est
refusée ou incomplète, aucun bilan partiel n'est présenté.
Le bouton « Analyser les liens métier autorisés » ajoute un contrôle des
Commandes Ventes ↔ Clients, Commandes Achats ↔ Fournisseurs, et
Ordres de fabrication ↔ Produits. Les liens absents sont signalés comme
éléments à vérifier, sans suppression ni correction automatique.
Le contrôle **Analyser les stocks autorisés** vérifie les références
articles, les quantités disponibles et les lots (quantité restante,
quantité initiale, liens MP/PF). **Analyser les mouvements de stock
autorisés** vérifie les articles, les types ENTREE/SORTIE, les quantités
et la cohérence éventuelle des lots associés. Les résultats sont agrégés ;
aucun mouvement ou solde n'est modifié. Il n'effectue pas de rapprochement
comptable automatique des soldes avec les mouvements historiques.

L'audit **Analyser les flux Achats et Ventes autorisés** vérifie les
lignes de commande, livraisons, réceptions et factures : parents et
articles absents/introuvables, quantités invalides ou non positives.
Les factures hors commande restent possibles, sans être classées comme
erreurs. Il ne recalcule pas les taxes, remises ou soldes.
Ce contrôle ne corrige aucune ligne automatiquement.

Les onglets de référentiels permettent de consulter les listes de choix,
matières premières, produits, clients, fournisseurs et conditionnements (SKU).
Un SKU est une présentation vendable d'un produit, liée à un emballage.
Avant une saisie réelle, vérifier l'unité, le produit parent et le conditionnement.

**Utilisateurs & Sécurité :** la gestion des comptes exige une habilitation
nominative SECURITY_MANAGER, indépendante du seul rôle ADMIN.

**Qualification TVA SKU :** l'inventaire documentaire signale les références
à qualifier. Exporter un registre ne classe pas fiscalement les produits.
**Exonérations TVA :** un brouillon de dossier ne vaut pas exonération validée.
La décision fiscale exige une habilitation supplémentaire et un contrôleur
distinct du créateur. Ne jamais inventer de pièce ni de validateur.
""",
    "🏢 Achats & Fournisseurs": """
- **Nouvelle Commande :** sélectionner le fournisseur, renseigner les lignes
  et vérifier quantités, unités et prix avant toute validation réelle.
- **Réception & Entrée Stock :** sélectionner la commande et renseigner les
  quantités réellement reçues. La validation crée le bon de réception et
  affecte les stocks ; ce bouton ne sert pas à tester la connexion.
- **Historique & Suivi :** consulter les commandes et bons de réception.

Les quantités sont saisies en unités de stock avec trois décimales. Le prix
d’une réception provient de la commande et son taux historique ; une réception
partielle conserve le solde à recevoir. La date de péremption est facultative :
la renseigner uniquement si elle est connue pour le lot reçu. Les réceptions non conformes ou avec
réserve sont bloquées : la quarantaine n’est pas disponible.

Si une lecture est indisponible ou incomplète, l’écran signale l’erreur et
bloque la rubrique concernée : réessayer avant de conclure à un registre vide.
Les consultations sont limitées à 10 000 lignes par table ou filtre ; au-delà,
faire réduire le volume de consultation avant de poursuivre.

Ne pas ressaisir dans Stocks une réception déjà enregistrée ici.
Après une réponse incertaine, conserver l'identifiant d'opération et utiliser
la reprise proposée avant d'envisager une nouvelle saisie.
Si le message « Connexion serveur Achats indisponible avant envoi » apparaît,
l’administrateur doit vérifier la configuration Supabase et la clé serveur dédiée
du déploiement. Si le paramètre supabase.stock_service_key est absent, le propriétaire doit renseigner la clé serveur du projet dans la section [supabase] des secrets Streamlit. Conserver le dossier de reprise pendant cette vérification.
""",
    "📦 Stocks & Magasin": """
- **État des Stocks :** consulter séparément matières premières en vrac,
  emballages et produits finis, avec unités et dates de mise à jour.
- **Entrée Manuelle (hors BR) :** réservée aux matières premières et emballages,
  pour une entrée réelle hors réception d'achat. La quantité doit être positive
  et une référence est obligatoire. Cet écran ne propose pas de correction
  négative d'inventaire ; signaler les écarts au responsable.
- **Historique des Mouvements :** retrouver les mouvements vrac, emballages et PF.

Les entrées de produits finis passent par Production. Ne pas doubler une entrée
issue d'un bon de réception. Un recalcul de contrôle ne corrige pas à lui seul
les quantités enregistrées.
""",
    "🏭 Production": """
- **Recettes :** consulter ou préparer une recette avec ses matières premières.
- **OF :** consulter les paramètres puis créer uniquement un ordre réel autorisé.
- **Production et CQ :** suivre les ordres et effectuer le contrôle qualité
  avant la clôture. Vérifier quantités, conditionnement et consommations.
- **Consommations et contrôles :** consulter l'historique associé aux OF.
- **Coûts industriels :** sélectionner une période par son libellé ET ses
  dates. Une liste de charges vide ne signifie pas une erreur de connexion.
  Les charges analytiques doivent être justifiées par une pièce SCF validée,
  puis réparties sur des OF terminés dans les dates de la période.
  L'audit mesure l'équilibre de répartition, pas l'existence de justificatifs :
  **0 DZD réparti sur 0 DZD peut apparaître équilibré, sans que la période
  soit validable**. Une charge doit avoir un montant strictement positif et
  chaque assiette mesurée doit aussi être positive ; un total analytique nul
  bloque le précontrôle même lorsque la répartition est équilibrée.
  Cliquer sur **Précontrôle avant validation**
  puis **Vérifier les prérequis** : ce diagnostic en lecture seule détaille les
  charges, assiettes, rapprochements SCF et OF terminés dans les dates.
  Une période de novembre ne peut pas englober un OF terminé en octobre.
  Corriger les anomalies et relancer le précontrôle ; une validation explicitement
  confirmée effectue **à nouveau** le précontrôle, puis la transaction SQL.
  Le précontrôle utilise plusieurs lectures réseau et ne constitue pas
  une validation transactionnelle ; la RPC SQL fait toujours autorité.
  Les écritures de charges et d'assiettes doivent être confirmées par une
  réponse du serveur ; si la réponse est incertaine, **contrôler Supabase
  avant toute nouvelle tentative**, plutôt que doubler une saisie.
  Les coûts analytiques ne modifient ni le CUMP ni les écritures du journal SCF.

La clôture peut modifier les stocks de matières, d'emballages et de produits
finis. Ne pas clôturer un OF pour tester l'écran. Conserver la référence de
l'opération si une confirmation réseau manque.
""",
    "🤝 Ventes & CRM": """
**Ventes & Facturation** comporte les onglets **Facture / Avoir**,
**Commandes clients**, **Bons de livraison**, **Suivi factures** et
**TVA par SKU (contrôle)**. La facture ou l'avoir est préparé en brouillon,
puis suit les actions proposées dans Suivi factures. Une commande, un BL et
une facture sont des documents distincts : contrôler leurs références et statuts.
Le présent guide ne décrit pas de conversion automatique d'un devis en facture.

**Fiscalité :** la qualification documentaire et le précontrôle d'exonération
n'autorisent pas à facturer à 0 %. Un historique d'exonération peut bloquer le
circuit historique et exiger une revue fiscale. Ne pas modifier le client ou
supprimer un dossier pour contourner ce blocage.

**CRM** comporte **Pipeline (Opportunités)**, **Consigner une interaction** et
**Historique des échanges**. Le pipeline suit prospect, statut, valeur estimée
et probabilité ; ce montant n'est pas un chiffre d'affaires facturé.
Une interaction rattache des notes et un éventuel rappel à un client actif.
La saisie d'un rappel ne prouve pas qu'un e-mail a été envoyé.
""",
    "💰 Finance & Trésorerie": """
- **Comptes** et **Règlements :** vérifier compte, contrepartie, sens du flux,
  montant et référence avant d'enregistrer un paiement réel.
- **Lettrage :** consulter les affectations des règlements aux documents ;
  un règlement peut être partiellement affecté.
- **Tableau de bord** et **Journal des écritures :** consulter les flux et
  écritures enregistrés. Ce journal n'est pas un grand livre SCF complet.
- **Rapprochement quittances**, **Accusés internes** et **Pré-audit Finance → SCF :**
  lire les contrôles et leurs réserves. Un accusé interne n'est pas un reçu
  fiscal officiel.
- **Balance SCF (lecture seule)**, **Préparation TVA / SCF** et
  **Correspondances Finance / SCF :** contrôler la configuration existante.
  Des références présentes ne prouvent pas qu'un exercice, des journaux ou
  des imputations sont actifs et homologués.

Ne pas créer de paiement fictif ni compléter des comptes ou taux au hasard.
""",
    "👥 Ressources Humaines": """
**Registre des Employés** et **Gestion des Congés** sont soumis aux droits RH.
Consulter les dossiers uniquement dans le cadre de vos habilitations.
Les écritures exigent des droits confirmés au moment de l'action.

**Simulation IRG (non validée)** et **Préparation Paie IRG / CNAS** sont visibles
uniquement avec les droits requis. Une simulation ne produit pas un bulletin
homologué ni une déclaration officielle. Les références à confirmer, assiettes
et périodes manquantes doivent être examinées avant tout usage réglementaire.
Ne pas inventer de salaire, taux, salarié ou justificatif pour lever un blocage.
""",
    "📚 Paie : règles et références": """
### Périmètre retenu

Le premier modèle concerne les **salariés du régime général** : salaire de base,
prime mensuelle de rendement et prime mensuelle de panier. L’entreprise a indiqué
moins de 20 employés réels ; les fiches SIM-RH ne sont pas des salariés réels.
La situation et l’effectif propres à chaque période restent à vérifier. Les
rappels et primes non mensuelles restent hors du premier périmètre.

**État actuel : les deux références CNAS et le barème IRG ne sont pas qualifiés
dans l’ERP ; aucun bulletin officiel ni déclaration ne peut être produit.**
Les exemples fictifs servent aux tests, sans valeur fiscale ou sociale.

### Cotisations et rémunération

- **Cotisations salarié / employeur :** le tableau du décret exécutif 15-236
  indique 9 % à la charge du salarié, 25 % à la charge de l’employeur et 0,5 %
  à la charge du fonds des œuvres sociales pour les branches listées. Cela ne
  prouve pas le coût employeur complet. Vérifier l’applicabilité, les assiettes,
  les autres contributions et les cas particuliers.
  [Source : Journal officiel n°49 du 16 septembre 2015, page 7](https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf).
- **Prime de rendement :** montant et conditions doivent être documentés ; son
  traitement fiscal et social reste à qualifier.
  [Source fiscale : DGI, traitements et salaires](https://mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires).
- **Prime de panier :** distinguer son objet et les justificatifs applicables ;
  son traitement fiscal et social n’est pas automatiquement présumé exonéré.
  [Source fiscale : DGI, traitements et salaires](https://mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires).
- **Coût employeur :** détailler les contributions, assiettes, périodes et
  sources. Une charge inconnue reste non déterminée. Pour les charges
  collectives, définir et tracer une clé de répartition par charge ; aucune
  répartition automatique n’a encore été qualifiée.
  [Source du tableau des cotisations : JO n°49/2015](https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf).

### IRG sur les salaires

La DGI décrit un barème progressif mensualisé, une exonération jusqu’à 30 000 DA
et des abattements selon l’assiette et le profil. L’assiette individuelle et la
date d’application doivent être vérifiées.
[Source : DGI, article 104 du CIDTA](https://mfdgi.gov.dz/fr/particuliers/irg-traitements-et-salaires).

La [table IRG 2022 DGI](https://www.mfdgi.gov.dz/images/bareme_irg/TABLE_IRG_2022.pdf)
sert aux comparaisons. Des écarts de quelques centimes subsistent avec le moteur
sur certains exemples : la portée de la table et les règles d’arrondi restent
à établir avant qualification. Un double arrondi peut changer le résultat ;
l’ordre applicable reste à vérifier.

### Formation et apprentissage

- La loi de finances 2022 a introduit une exonération de la **taxe de formation
  professionnelle** pour les employeurs de moins de 20 employés. Vérifier le
  texte consolidé, le décompte et la période ; ne pas appliquer automatiquement
  cette exonération à la taxe d’apprentissage.
  [Source : loi de finances 2022, article 56, JO n°100](https://www.joradp.dz/FTP/jo-francais/2021/F2021100.pdf).
- La loi de finances 2026 modifie l’assiette semestrielle et le calcul de ces
  taxes en tenant compte des dépenses éligibles. Examiner ces postes collectifs
  séparément ; ne pas ajouter mécaniquement deux taux fixes par bulletin.
  [Source : loi de finances 2026, articles 18 à 20](https://dgb.mf.gov.dz/wp-content/uploads/2026/01/LF-2026.pdf).

### Atelier de paie fictive

Dans **RH → Atelier paie fictive**, le rôle doit disposer de Paie/lecture.
Seuls les employés SIM-RH-001 à 008 actifs et marqués [FICTIF] sont proposés.
Le bouton calcule un exemple en mémoire, sans écriture. Les retenues de 5 %,
10 % et 1 000 DZD sont arbitraires : elles ne représentent ni taux CNAS ni
barème IRG et ne doivent pas servir à une paie ou une déclaration réelle.

### Comparaison DGI 2022 pour les salariés fictifs

Dans l’atelier, le bouton **Comparer avec la table DGI 2022** affiche, pour les
huit profils fictifs, des exemples fixes relevés dans la table cas général.
L’hypothèse est un brut totalement soumis à une cotisation salariale de 9 %,
sans prime ni autre retenue ; le net affiché est une comparaison arithmétique,
non une fiche de paie validée. La quote-part employeur à 25 % illustre le tableau
du décret ; elle ne représente pas nécessairement toutes les charges.
[Table DGI 2022](https://www.mfdgi.gov.dz/images/bareme_irg/TABLE_IRG_2022.pdf)
et [JO n°49/2015, p. 7](https://www.joradp.dz/FTP/jo-francais/2015/F2015049.pdf).
Aucune donnée de paie n’est enregistrée. Les autres assiettes, primes et règles
réelles restent à qualifier ; les références réglementaires ne sont pas activées.

### Utiliser l’écran

Dans **RH → Préparation Paie IRG / CNAS**, choisir la date et lancer **Vérifier
les référentiels**. « Non » indique que la référence attendue n’est pas
qualifiée ou disponible ; une erreur de lecture s’affiche séparément. Un « Oui »
éventuel ne valide pas les assiettes individuelles, les profils ni un bulletin.
Ne pas utiliser de règle ou de salaire fictif comme référence juridique.

[Dossier détaillé : qualification des références de paie](https://github.com/Verwolfy/erp-mortier/blob/main/docs/PAIE_QUALIFICATION_20261102.md).
""",
    "📊 Tableaux de bord": """
Les onglets couvrent Direction, Rentabilité (P&L), Ventes & Facturation, Achats,
Stocks, Production, CRM, RH et Finance, selon les droits de consultation.

Vérifier la période sélectionnée et conserver une date de début antérieure
ou égale à la date de fin. Comparer les indicateurs aux documents sources
avant de prendre une décision. Le P&L est une synthèse de gestion, pas un
compte de résultat réglementaire certifié. Un pipeline commercial n'est pas
une vente ; un règlement n'est pas nécessairement intégralement lettré.
Les lectures des Dashboards sont paginées et contrôlées. En cas de panne,
de refus d'accès, de réponse incohérente ou de dépassement de la limite de
consultation (10 000 lignes par lecture), la rubrique affiche une indisponibilité
au lieu d'un total partiel. Les autres rubriques peuvent rester consultables.
Réduire la période peut aider pour les lectures filtrées ; certains référentiels
restent lus dans leur ensemble. Les indicateurs de facturation brute retiennent les factures clients VALIDE,
hors avoirs, brouillons et annulations. Le ratio des avoirs validés est séparé.
La balance âgée conserve toutes les créances ouvertes, même sans vente dans
la période choisie ; les paiements partiels diminuent le reste à recouvrer.
Les coûts produits manquants rendent le P&L indisponible. Ses coûts actuels
restent une limite : le solde affiché est estimatif. Les nets de paie enregistrés
sont filtrés par mois/année, tous statuts de paiement ; ils ne prouvent ni une
paie validée, ni un paiement, ni le coût employeur. Choisir des mois complets
si des fiches existent : aucun prorata journalier n’est inventé.
Les OPEX sont les décaissements VALIDE vers les fournisseurs classés OPEX.
Un fournisseur absent, une catégorie vide ou un montant invalide rend la rubrique
indisponible. Le solde mélange facturation et décaissements, sans calculer un
résultat comptable. Repère des calculs : SOF-ERP-20261102-KPI-05.
Les retards Achats restent globaux même sur une période vide. Une commande
échue aujourd’hui n’est pas encore en retard ; dates manquantes signalées.
La trésorerie indicative porte sur Banque/Caisse : soldes initiaux plus
règlements VALIDE jusqu’à aujourd’hui, indépendamment du filtre des flux.
Elle exclut les comptes tiers et les autres écritures ; les soldes initiaux
ne sont pas datés. Elle ne constitue pas un rapprochement bancaire.
Stocks : un coût manquant sur une quantité positive ou un seuil inconnu rend
la rubrique indisponible. Les lots déjà périmés sont inclus ; les lots sans
date sont signalés comme non évalués. Une quantité nulle ne nécessite pas
de coût pour sa valorisation nulle. Les alertes de seuil portent sur les lignes
de stock présentes, pas sur les références sans ligne de stock.
CRM : statuts du formulaire reconnus ; pipeline ouvert global. La période
filtre la date de création, pas une date de clôture absente du schéma.
Les valeurs gagnées sont des estimations commerciales, pas du CA facturé.
RH : seuls les employés actif=OUI comptent ; les services absents restent visibles.
Le contrôle ne constitue pas un instantané
transactionnel de toutes les tables ni une validation comptable des calculs.
""",
    "🛠️ Incidents et reprise": """
**CRM et Dashboards :** le repère de lecture est SOF-ERP-20261101-READ-01.
Un message d'indisponibilité ne signifie pas que le registre est vide.

**Lecture indisponible :** noter l'écran, l'heure et le message affiché,
puis réessayer la consultation. Ne pas remplacer les données absentes par zéro.
**Opération incertaine :** conserver la session et l'identifiant d'opération ;
utiliser Reprendre si l'écran le propose. Ne pas créer une nouvelle opération
pour compenser une réponse manquante : la première peut avoir été enregistrée.
Si la session est perdue, demander un contrôle des documents et journaux avant
une nouvelle saisie.
**Accès refusé :** vérifier l'identité et les habilitations avec le responsable.
Ne pas désactiver les gardes, la RLS ou les contrôles de session.

Pour signaler une anomalie : module, onglet, étapes, résultat attendu/observé,
heure et référence interne utile. Masquer mots de passe, clés, données RH et
informations personnelles dans les captures.

Une CI verte prouve la réussite des tests exécutés, pas le déploiement hébergé.
Après mise à jour, contrôler les repères de version visibles et les écrans
sans créer de transaction métier de test.
""",
    "🔐 Environnements et sécurité (010-A)": """
**Simulations RH autorisées :** les fiches SIM-RH-001 à SIM-RH-010 sont fictives,
avec 8 actifs et 2 inactifs. Elles apparaissent dans les compteurs RH.
Réutiliser ces identifiants ; ne pas générer de paiement ou déclaration réelle.

**Consigne actuelle :** exploitation sur main et Supabase PRODUCTION.
Le projet TEST est conservé en pause : ne pas le réveiller ni le supprimer.
Les anciens protocoles utilisant TEST décrivent un contexte historique.
Les tests automatisés utilisent des doubles locaux sans transactions réelles.

Une politique absente, un projet différent ou une production désactivée doit
être examiné par l'administrateur. Ne pas contourner ces contrôles pour ouvrir
un écran. Les clés serveur et mots de passe ne doivent jamais figurer dans
le guide, une capture ou un ticket.
""",
    "🔎 Vérification des droits SQL (010-A-02)": """
Les contrôles de production restent en lecture seule. Aucun GRANT, REVOKE,
changement de politique ou suppression n'est autorisé par cette page.

La RLS contrôle l'accès aux lignes ; les GRANT contrôlent les privilèges SQL.
Une RLS active sans politique peut être intentionnelle pour une table privée.
Le rôle service_role est réservé au serveur et ne doit jamais être exposé.

L'administrateur vérifie l'identité du projet de production puis examine
schéma, privilèges, politiques, fonctions et historique des migrations.
Les résultats INFO ou OK portent sur un contrôle précis et ne constituent
pas une certification globale. Ne pas réactiver TEST pour comparer les droits.
""",
}


def _mark_help_activity() -> None:
    """Signale un changement de rubrique sans prolongation directe."""
    st.session_state["_erp_help_interacted"] = True


def show_help_page():
    st.title("📚 Guide d'Utilisation de l'ERP")
    show_context_help(st, "help.guide")
    st.caption("Guide révisé le 2 novembre 2026 — SOF-ERP-20261102-GUIDE-11")
    st.markdown("Sélectionnez une rubrique dans le menu de gauche.")
    st.sidebar.markdown("---")
    st.sidebar.subheader("📑 Navigation Documentaire")
    rubrique = st.sidebar.radio(
        "Choisissez un module :", list(HELP_SECTIONS),
        help="Procédures, limites et conduite à tenir en cas d'incident.",
        on_change=_mark_help_activity,
    )
    st.divider()
    st.header(rubrique)
    st.markdown(HELP_SECTIONS[rubrique])
