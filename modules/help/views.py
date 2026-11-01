"""Guide utilisateur aligné sur les écrans disponibles, sans écriture métier."""
import streamlit as st


HELP_SECTIONS = {
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
    "⚙️ Administration & Référentiels": """
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

Ne pas ressaisir dans Stocks une réception déjà enregistrée ici.
Après une réponse incertaine, conserver l'identifiant d'opération et utiliser
la reprise proposée avant d'envisager une nouvelle saisie.
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
restent lus dans leur ensemble. Le contrôle ne constitue pas un instantané
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
    st.caption("Guide révisé le 1 novembre 2026 — SOF-ERP-20261101-GUIDE-03")
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
