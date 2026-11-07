"""Aides contextuelles ERP : contenu statique, lecture seule, sans données de session.

API compatible Streamlit >= 1.38 : st.popover(help=...) pour le clic + survol.
La protection métier et les rôles restent assurés par les pages et services existants.
"""
from __future__ import annotations

# Chaque rubrique a une notion, une procédure et un point de contrôle.
TOPICS: dict[str, tuple[str, str, str, str]] = {
    "navigation": ("Navigation et habilitations", "Le menu affiche uniquement les modules autorisés pour le compte connecté.", "Choisir un module dans la barre latérale, puis ouvrir l'onglet métier concerné.", "Les droits sont revérifiés côté serveur ; une rubrique visible ne garantit pas un droit d'écriture."),
    "admin.clients": ("Clients", "Un client est un tiers commercial utilisé dans les ventes, factures et règlements.", "Ouvrir Clients, rechercher un tiers existant, puis préparer une nouvelle fiche si autorisé ; vérifier les champs avant l'enregistrement.", "Contrôler identité, coordonnées et données fiscales réelles ; éviter les doublons."),
    "admin.fournisseurs": ("Fournisseurs", "Un fournisseur est un tiers auprès duquel l'entreprise achète des matières, emballages ou prestations.", "Consulter le référentiel, puis préparer la fiche fournisseur et vérifier ses informations avant création.", "Ne pas inventer de NIF, RC, coordonnées ou références légales."),
    "admin.matieres": ("Matières premières", "Référentiel des matières consommables ou emballages suivis en stock avec une unité de mesure.", "Vérifier catégorie, unité, stock mini et statut actif avant de créer une matière.", "La catégorie EMBALLAGE n'est pas un ingrédient de recette ; pas de conversion kg ↔ L supposée."),
    "admin.produits": ("Produits finis", "Produit fabriqué à partir d'une recette, distinct de son format commercial SKU.", "Définir l'unité de fabrication, créer le produit et le rattacher à la recette correcte.", "Vérifier la cohérence des unités et éviter les références produit dupliquées."),
    "admin.sku": ("Conditionnements SKU", "Un SKU est une variante vendable d'un produit fini : format, unité de vente et quantité équivalente.", "Associer un produit, un emballage et un facteur de conversion vérifiés ; puis contrôler l'activation.", "Ne pas assimiler des litres à des kilogrammes ; vérifier les conditionnements physiques avant fabrication."),
    "admin.listes": ("Listes de choix", "Référentiels contrôlant les valeurs proposées dans certains menus déroulants.", "Sélectionner la liste métier, vérifier les valeurs existantes, puis ajouter une option autorisée.", "Ne pas supprimer une valeur utilisée par des documents historiques."),
    "admin.exonerations": ("Exonérations TVA clients", "Dossiers documentaires d'exonération soumis à portée, validité et habilitation fiscale.", "Consulter le dossier et ses pièces ; faire vérifier par le circuit fiscal habilité avant tout effet.", "Une attestation en brouillon ne suffit pas pour appliquer 0 % ; aucune présomption d'éligibilité."),
    "admin.tva": ("Qualification TVA SKU", "Documentation du régime fiscal applicable à chaque article commercialisé.", "Rechercher les SKU actifs, contrôler leurs justificatifs et signaler les classifications incomplètes.", "Aucune qualification automatique ni taux inventé ; la validation fiscale est séparée."),
    "admin.documents": ("Documents administratifs", "Gabarits de documents exportables PDF, Word ou JSON sans création automatique d'une transaction métier.", "Choisir une famille, remplir les champs, vérifier les montants et exporter un brouillon.", "Les exports portent la mention BROUILLON et ne constituent pas des factures officielles."),
    "admin.qualite": ("Qualité des référentiels", "Contrôles transversaux de cohérence des clients, fournisseurs, produits, SKU et matières.", "Lancer l'analyse en lecture seule, examiner les anomalies puis corriger les données sources par les écrans autorisés.", "Aucune correction automatique ; un champ absent ne doit pas être remplacé par une valeur supposée."),
    "admin.utilisateur": ("Comptes utilisateurs", "Gestion des accès nominatifs à l'application.", "Créer un accès uniquement pour un collaborateur autorisé et définir son rôle.", "Respecter le principe du moindre privilège ; ne jamais partager d'identifiants."),
    "admin.permissions": ("Permissions et rôles", "Matrice indiquant quels modules peuvent être consultés ou modifiés selon un rôle.", "Choisir un rôle, examiner les droits existants et n'ajouter que les autorisations nécessaires.", "Les droits critiques exigent une revue ; les validations SQL restent indépendantes de l'interface."),
    "admin.annuaire": ("Annuaire et matrice", "Consultation des utilisateurs enregistrés et de la répartition des permissions.", "Rechercher un utilisateur et contrôler son statut actif, son rôle et ses habilitations.", "Les informations d'authentification sensibles ne doivent pas être affichées."),
    "admin.audit": ("Piste d'audit", "Traçabilité des opérations et changements enregistrés par l'ERP.", "Afficher ou actualiser les journaux, puis rechercher la référence et l'auteur d'une opération.", "Une absence de log historique ne prouve pas l'absence de transaction ; rapprocher avec Supabase."),
    "achats.commande": ("Nouvelle commande fournisseur", "Document indiquant les articles et quantités commandés à un fournisseur.", "Sélectionner le fournisseur, ajouter les lignes avec unités/prix, renseigner les modalités puis vérifier avant création.", "Une commande n'ajoute pas de stock ; vérifier les données et ne pas relancer avec une autre référence après erreur réseau."),
    "achats.reception": ("Réception et entrée stock", "Enregistrement des quantités réellement reçues et du contrôle de conformité.", "Choisir une commande réceptionnable, saisir quantité conforme et lot, puis valider le bon de réception si autorisé.", "Éviter les doubles réceptions ; vérifier le solde, la qualité et la date de péremption si disponible."),
    "achats.historique": ("Historique achats", "Consultation des commandes, bons de réception et statuts enregistrés.", "Choisir une page puis cliquer sur le chargement de l'historique pour afficher les lignes.", "50 lignes maximum par page ; une page vide n'est pas nécessairement une erreur ni une absence totale de données."),
    "stocks.etat": ("État des stocks", "Quantités disponibles par article et lot, avec valorisation lorsque calculable.", "Choisir la famille vrac, emballages ou produits finis ; contrôler quantités, unités et dates.", "La valorisation CUMP n'est pas une facture et ne remplace pas le rapprochement physique."),
    "stocks.vrac": ("Matières premières en vrac", "Stocks de composants non classés comme emballages.", "Consulter quantité disponible, unité, stock minimum et prix moyen pondéré.", "Les données de stock doivent être rapprochées des mouvements et inventaires physiques."),
    "stocks.emballages": ("Emballages", "Stocks d'unités de conditionnement consommées pendant la fabrication.", "Consulter chaque emballage et son unité puis vérifier la disponibilité avant un OF.", "Ne pas confondre emballage et matière première de formulation."),
    "stocks.pf": ("Produits finis", "Stock disponible des articles fabriqués et conditionnés.", "Consulter les références produits/SKU et leurs quantités disponibles.", "Les entrées de produits finis sont générées par la clôture de production autorisée."),
    "stocks.entree": ("Entrée ou ajustement manuel", "Mouvement de stock hors bon de réception destiné aux cas autorisés.", "Choisir le type de matière, vérifier motif, unité, quantité et référence d'opération avant de confirmer.", "Ne pas doubler une réception Achats ni créer manuellement un produit fini ; conserver la référence en cas de timeout."),
    "stocks.historique": ("Historique des mouvements", "Journal des entrées, sorties et ajustements de stocks.", "Sélectionner la page et demander le chargement ; filtrer ou rapprocher les opérations utiles.", "L'historique est paginé ; les opérations doivent être rapprochées par identifiant et lot."),
    "production.recettes": ("Recettes et nomenclatures", "Formulation de fabrication : matières nécessaires pour produire une quantité déterminée de produit.", "Choisir le produit, renseigner rendement du batch et composants, comparer unités/quantités et sauvegarder après confirmation.", "Le service enregistre les quantités par unité produite ; ne pas additionner kg et L sans conversion validée."),
    "production.of": ("Ordres de fabrication (OF)", "Ordre planifiant la production d'un SKU selon une recette validée.", "Choisir SKU et recette, vérifier la quantité entière de conditionnements, la date et le besoin théorique, puis créer l'OF.", "Contrôler disponibilité des matières et emballages ; création non confirmée = vérifier en base avant de réessayer."),
    "production.cq": ("Production et contrôle qualité (CQ)", "Suivi d'un OF jusqu'à son contrôle puis sa clôture conforme ou son rejet.", "Choisir l'OF, vérifier les consommations et l'emballage, saisir le contrôle qualité, puis confirmer une seule clôture.", "Une clôture conforme déclenche des mouvements de stock atomiques ; ne pas l'utiliser pour une simple simulation."),
    "production.historique": ("Consommations et contrôles qualité", "Historique des matières réellement consommées par les OF et des contrôles CQ enregistrés.", "Choisir la page d'historique puis cliquer sur « Afficher l'historique Production » ; examiner les lots et statuts.", "Chargement manuel et pagination limitent les lectures ; ne pas confondre absence de lignes et lecture en erreur."),
    "production.couts": ("Coûts industriels analytiques", "Charges indirectes ou directes imputées à des OF, séparément du CUMP et des écritures comptables SCF.", "Choisir une période, créer uniquement des charges justifiées et des clés mesurées ; contrôler les pièces SCF puis lancer le précontrôle.", "Une période vide peut avoir un audit arithmétique équilibré à zéro mais n'est pas validable ; pas de pièce ou coût inventé."),
    "ventes.facture": ("Facture ou avoir — brouillon", "Document de facturation ou correction commerciale préparé sous réserves fiscales.", "Sélectionner la vente et les données autorisées, préparer les lignes puis contrôler montants, TVA et statut.", "Le circuit historique n'est pas homologué pour toutes les situations TVA ; ne pas émettre une facture officielle sans validation."),
    "ventes.commandes": ("Commandes clients", "Engagement de livraison d'articles demandé par un client.", "Choisir client et SKU, renseigner quantités et prix, vérifier avant l'enregistrement.", "Une commande, un bon de livraison et une facture sont des documents distincts."),
    "ventes.bl": ("Bons de livraison", "Document retraçant la livraison physique effectuée au titre d'une commande client.", "Sélectionner la commande, contrôler le stock disponible et les quantités réellement expédiées.", "Ne pas livrer au-delà des quantités autorisées ni réutiliser des opérations après une confirmation incertaine."),
    "ventes.suivi": ("Suivi des factures", "Consultation des états d'émission, paiement et éventuelles annulations des factures.", "Rechercher le document, examiner son statut et ses opérations liées avant toute action.", "Ne pas modifier un document fiscal validé sans circuit d'avoir et autorisation conforme."),
    "ventes.tva": ("TVA par SKU — contrôle", "État documentaire du régime de TVA associé aux articles et, le cas échéant, au client.", "Consulter les lignes et justificatifs, puis faire qualifier les anomalies par le service habilité.", "Ne pas déduire automatiquement une exonération ni un taux applicable d'un dossier incomplet."),
    "crm.pipeline": ("Pipeline commercial", "Suivi des opportunités du premier contact à une issue commerciale.", "Créer une opportunité puis renseigner étape, propriétaire, valeur estimée et prochaines actions.", "Une opportunité n'est ni une commande acceptée ni un chiffre d'affaires facturé."),
    "crm.interaction": ("Consigner une interaction", "Trace d'un appel, rendez-vous ou échange lié à un client.", "Choisir le client, saisir type, date, notes utiles et éventuel rappel.", "Éviter les données confidentielles inutiles ; un rappel n'envoie pas automatiquement de message."),
    "crm.historique": ("Historique des échanges", "Consultation des interactions commerciales déjà enregistrées.", "Choisir la page puis demander le chargement de l'historique.", "Vérifier la bonne association client ; le journal est paginé."),
    "crm.nextgen": ("Demandes NextGen", "Demandes d'informations ou contacts reçus du site NextGen.", "Charger les demandes autorisées, qualifier leur statut et traiter manuellement les suites.", "Aucune conversion automatique d'une demande en client ERP ; respecter la confidentialité des coordonnées."),
    "finance.dashboard": ("Tableau de bord financier", "Synthèse des flux enregistrés de trésorerie.", "Lire les indicateurs et rapprocher les variations avec les comptes et règlements.", "Ce tableau n'est pas un grand livre SCF complet."),
    "finance.comptes": ("Comptes et caisses", "Référentiel des comptes bancaires, caisses et contreparties de règlement.", "Consulter le compte puis créer/mettre à jour uniquement les données justifiées.", "Ne pas confondre compte de paiement ERP et compte réglementaire SCF."),
    "finance.reglements": ("Règlements", "Entrées ou sorties d'argent imputables à une opération de trésorerie.", "Sélectionner le sens, le compte, le montant et la pièce de référence, puis confirmer la transaction.", "Ne pas doubler un paiement après échec réseau ; rapprocher les opérations d'origine."),
    "finance.lettrage": ("Lettrage", "Association d'un règlement à une facture cliente ou fournisseur, totale ou partielle.", "Choisir le document et le règlement puis contrôler le solde à affecter.", "Le lettrage n'enregistre pas une nouvelle rentrée d'argent ; les paiements partiels doivent être respectés."),
    "finance.journal": ("Journal des écritures", "Historique des écritures enregistrées par l'ERP.", "Consulter dates, débits et crédits, puis rapprocher avec les règlements sources.", "Ne pas assimiler ce journal technique à une comptabilité SCF intégralement homologuée."),
    "finance.scf": ("Balance SCF — lecture seule", "Synthèse par compte des pièces SCF validées, sans création d'écritures.", "Cliquer sur Charger la balance, puis examiner l'équilibre et les anomalies éventuelles.", "Une pièce en brouillon n'entre pas dans cette balance ; une balance vide ne vaut pas homologation."),
    "finance.quittances": ("Rapprochement quittances", "Contrôle des règlements et de leurs justificatifs internes.", "Lancer le diagnostic, examiner les paiements partiels et les affectations.", "Le diagnostic n'émet pas de quittance fiscale officielle."),
    "finance.accuses": ("Accusés internes", "Justificatifs internes d'encaissement sans valeur de quittance fiscale officielle.", "Consulter les accusés et rapprocher la référence au règlement confirmé.", "Ne pas présenter un accusé interne comme document fiscal ou paiement nouveau."),
    "finance.preaudit": ("Pré-audit Finance vers SCF", "Contrôles de cohérence entre flux ERP et écritures/comptes SCF.", "Déclencher le contrôle de lecture et examiner les écarts documentés.", "Aucune écriture n'est transférée ou homologuée automatiquement."),
    "finance.reglementaire": ("Préparation TVA et SCF", "État de disponibilité des référentiels fiscaux, comptes et exercices.", "Lancer les contrôles puis corriger les paramètres non qualifiés via le circuit autorisé.", "Ne pas lancer une facture ou une comptabilisation officielle sur la seule base de ce diagnostic."),
    "finance.correspondances": ("Correspondances Finance / SCF", "Comparaison des numéros de comptes ERP avec le référentiel SCF.", "Charger la comparaison, relever les correspondances exactes et les absences.", "Un numéro identique ne prouve pas la correcte imputation comptable."),
    "rh.employes": ("Employés", "Dossiers des salariés utilisés par les fonctions RH.", "Créer ou modifier une fiche nominative autorisée et contrôler le statut et les dates.", "Limiter l'accès aux personnes habilitées ; éviter les données personnelles non nécessaires."),
    "rh.conges": ("Demandes de congé", "Enregistrement et suivi des absences demandées par les salariés.", "Choisir un salarié actif, renseigner les dates et suivre le statut de validation.", "Respecter l'organisation et les habilitations ; une demande n'est pas automatiquement un congé approuvé."),
    "rh.irg": ("Simulation IRG", "Estimation fiscale pédagogique basée sur les paramètres disponibles.", "Choisir les éléments autorisés et lancer une simulation avant de comparer les références.", "Ne constitue ni bulletin de paie homologué ni déclaration fiscale ; vérifier les règles en vigueur."),
    "rh.pae": ("Préparation IRG et CNAS", "Contrôle documentaire des barèmes et contributions sociales nécessaires à la paie.", "Choisir la date réglementaire et examiner les références manquantes.", "Aucun taux CNAS/IRG supposé ne doit être utilisé pour une paie officielle."),
    "rh.simulation": ("Atelier paie fictive", "Bac d'essai de calcul sur des données explicitement fictives.", "Utiliser seulement les fiches SIM-RH prévues par le module et examiner les résultats à titre de test.", "Pas de bulletins, paiement ni déclaration ; ne pas mélanger aux données réelles."),
    "dashboard.direction": ("Vue Direction", "Synthèse des indicateurs de l'entreprise à date.", "Examiner les KPI, puis ouvrir les modules sources pour rapprocher les chiffres.", "Les données peuvent être incomplètes et certaines métriques ne sont pas des comptes légaux."),
    "dashboard.pnl": ("Rentabilité (P&L)", "Estimation de gestion du résultat à partir de revenus et coûts disponibles.", "Choisir la période, lire les réserves et rapprocher revenus, coûts et charges.", "Coûts de produits parfois non historiques ; ne pas qualifier ce P&L de compte de résultat légal."),
    "dashboard.ventes": ("Analyse des ventes", "Indicateurs de facturation, avoirs et créances clients.", "Définir dates et charger les statistiques ; examiner le périmètre de chaque KPI.", "Les créances globales peuvent dépasser la période choisie."),
    "dashboard.achats": ("Analyse des achats", "Dépenses, réceptionnements et suivi des fournisseurs.", "Choisir dates et lire les commandes/retards selon leur statut.", "Les commandes non reçues ne valent pas entrée en stock."),
    "dashboard.stocks": ("Analyse des stocks", "Valorisation et alertes d'inventaire, notamment lots proches de péremption.", "Régler le délai d'alerte puis examiner lots, quantités et valorisations.", "Une date de péremption manquante n'implique pas qu'un lot est utilisable."),
    "dashboard.production": ("Performance de production", "Indicateurs de fabrication et qualité des OF.", "Filtrer la période puis comparer OF lancés, clôturés et anomalies.", "Distinguer prévisions d'OF et quantités réellement clôturées."),
    "dashboard.crm": ("Performance CRM", "Lecture agrégée des opportunités et du pipeline.", "Définir dates et contrôler statut et valeur estimée.", "Une opportunité gagnée n'est pas une vente facturée."),
    "dashboard.rh": ("Indicateurs RH", "Effectifs et répartitions des fiches salariés enregistrées.", "Consulter les effectifs actifs et leur répartition par service.", "Les dossiers fictifs ou incomplets ne doivent pas étayer une déclaration officielle."),
    "dashboard.finance": ("Trésorerie et rapprochement", "Suivi des flux et écarts de règlement.", "Choisir la période, contrôler les encaissements/décaissements et rapprocher les comptes.", "Le calcul agrégé ne remplace pas le rapprochement bancaire ou le grand livre."),
    "documents.edition": ("Documents NEXTGEN", "Éditeur de brouillons administratifs et fiches techniques à exporter.", "Choisir le modèle, renseigner les données vérifiées puis exporter PDF, DOCX ou JSON.", "Aucun document officiel ni écriture Supabase n'est créé ; la conformité doit être validée."),
    "documents.import": ("Reprise d'un brouillon", "Chargement local d'un JSON de brouillon compatible avec le modèle sélectionné.", "Importer le fichier précédemment exporté et revoir toutes les lignes avant de poursuivre.", "Ne pas importer de données confidentielles non autorisées ni utiliser un JSON d'un autre type."),
    "documents.lignes": ("Lignes de document", "Détails de prestation, quantité, prix ou autres champs selon le document.", "Ajouter, renseigner et vérifier chaque ligne ; contrôler les totaux si présents.", "Les valeurs fiscales et techniques ne sont pas déduites automatiquement."),
    "documents.logo": ("Identité visuelle", "Logo et mentions d'entreprise placés sur les exports de brouillons.", "Vérifier l'aperçu et ne remplacer le logo que par un fichier officiel autorisé.", "Un QR interne n'est pas une preuve de certification ni une page de suivi."),
    "help.guide": ("Guide et aide", "Documentation opératoire des modules et de leurs limites.", "Choisir une rubrique dans l'aide, lire les consignes et revenir au module concerné.", "En cas d'incertitude sur une transaction, vérifier en base plutôt que rejouer l'opération."),
}


def topic_help(topic: str) -> str:
    """Résumé accessible au survol du titre ou du bouton d'aide."""
    title, notion, _, _ = TOPICS[topic]
    return f"{notion} Ouvrir « Aide : {title} » pour les étapes et contrôles."


def show_context_help(st, topic: str) -> None:
    """Affiche un bouton accessible au clavier, au tactile et à la souris.

    Le survol décrit brièvement la notion ; le clic ouvre la procédure.
    Les popovers ne contiennent aucun widget métier ou requête réseau.
    """
    title, notion, procedure, vigilance = TOPICS[topic]
    with st.popover(f"ⓘ Aide : {title}", help=f"{notion} Cliquez pour la procédure."):
        st.markdown(f"**Notion** — {notion}")
        st.markdown(f"**Comment faire** — {procedure}")
        st.markdown(f"**À vérifier** — {vigilance}")


# Conseils de champ génériques, enrichis par famille métier. Aucune donnée saisie
# n'est lue par ce composant. Les écrans peuvent fournir une aide spécialisée.
FIELD_GUIDANCE = (
    (("historique", "page"), "Choisir un numéro de page puis cliquer sur le bouton de chargement ; seules les lignes de cette page seront récupérées."),
    (("date", "début"), "Choisir le début de la période étudiée ; vérifier qu'il précède ou égale la fin."),
    (("date", "fin"), "Choisir la fin de la période étudiée ; contrôler la cohérence avec la date de début."),
    (("fournisseur",), "Sélectionner un fournisseur existant et actif ; vérifier son identité avant d'engager un achat."),
    (("client",), "Sélectionner le bon client dans le référentiel actif ; contrôler les données avant toute vente."),
    (("sku",), "SKU : article commercial avec un format et une unité de vente ; vérifier le facteur de conversion et l'emballage."),
    (("recette",), "Recette : formulation de matières par unité produite ; vérifier la version et les unités."),
    (("of",), "OF : ordre de fabrication. Vérifier statut, quantités, recette et date avant toute opération."),
    (("lot",), "Vérifier l'identifiant du lot réel et les informations de traçabilité avant toute entrée ou consommation."),
    (("débit",), "Montant porté au débit d'une ligne comptable. Vérifier la pièce SCF et sa validation."),
    (("crédit",), "Montant porté au crédit d'une ligne comptable. Vérifier la contrepartie de l'écriture."),
    (("quantité",), "Saisir la quantité dans l'unité indiquée. Vérifier si la saisie concerne un batch, des SKU entiers ou une unité de stock."),
    (("prix",), "Vérifier le prix dans la devise et l'unité applicables, ainsi que le document fournisseur ou le tarif de référence."),
    (("montant",), "Saisir un montant documenté ; contrôler signe, décimales, devise et justification avant validation."),
    (("tva",), "TVA : utiliser uniquement une qualification fiscale et des pièces vérifiées ; aucune exonération automatique."),
    (("taux",), "Un taux fiscal ou social doit être justifié et valable à la date concernée, sans supposition."),
    (("compte",), "Vérifier l'identifiant et le type de compte ; distinguer trésorerie ERP et plan comptable SCF."),
    (("période",), "Choisir la période exacte et vérifier les dates des documents et OF rattachés."),
    (("date",), "Sélectionner la date de l'opération ou de référence ; ne pas antidater un événement réel."),
    (("statut",), "Le statut représente l'état actuel du dossier ; une validation peut être définitive et soumise à droits."),
    (("remarque",), "Ajouter une observation factuelle utile, sans données personnelles ou secrets non nécessaires."),
    (("justificatif",), "Renseigner une référence de pièce réelle et vérifiable ; un texte libre ne remplace pas une validation SCF."),
    (("référence",), "Utiliser l'identifiant réel du document et vérifier qu'il correspond à l'opération recherchée."),
    (("mot de passe",), "Choisir un mot de passe robuste. Ne jamais le communiquer ni l'inscrire dans un journal."),
    (("identifiant",), "Utiliser l'identifiant exact provenant du référentiel, sans en inventer de nouveau."),
    (("nom",), "Utiliser la désignation exacte et vérifier les doublons avant enregistrement."),
)


def field_help(label: str, *, module: str = "") -> str:
    """Info courte pour les formulaires, avec consignes de saisie non sensibles.

    Un champ sans définition métier reconnue reçoit une procédure conservatrice.
    """
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Libellé de champ manquant")
    normalized = label.casefold()
    # Une action doit être décrite comme telle, pas comme un champ de saisie.
    if any(word in normalized for word in ("valider", "confirmer", "clôturer", "cloturer", "supprimer", "annuler")):
        return ("Action susceptible d'avoir un effet durable : vérifier le dossier, "
                "les montants, les pièces et les droits avant confirmation. "
                "Si la réponse réseau est incertaine, contrôler la base avant de recommencer.")
    if any(word in normalized for word in ("enregistrer", "créer", "creer", "générer", "generer", "sauvegarder", "ajouter")):
        return ("Vérifier toutes les valeurs et la référence de l'opération avant "
                "de créer ou d'enregistrer. Une réponse incertaine ne doit pas entraîner un doublon.")
    if any(word in normalized for word in ("afficher", "charger", "rafraîchir", "actualiser", "analyser", "contrôler", "verifier", "vérifier", "comparer")):
        return ("Charger ou contrôler les informations autorisées à la demande. "
                "Cette consultation ne crée pas de transaction métier.")
    if "page" in normalized and ("historique" in normalized or "mouvement" in normalized or "facture" in normalized):
        return ("Pagination : choisir le numéro de page (à partir de 1), puis demander "
                "l'affichage de l'historique. Cette action ne crée aucune opération.")
    # La pagination prend priorité sur la simple notion de page.
    if "page" in normalized and ("historique" in normalized or "mouvement" in normalized or "facture" in normalized):
        return ("Pagination : choisir le numéro de page (à partir de 1), puis demander "
                "l'affichage de l'historique. Cette action ne crée aucune opération.")
    for tokens, explanation in FIELD_GUIDANCE:
        if all(token in normalized for token in tokens):
            return explanation
    context = f" ({module})" if module else ""
    return (f"Champ {label}{context} : sélectionner ou saisir une valeur réelle, "
            "vérifier les unités et la source avant toute confirmation.")
