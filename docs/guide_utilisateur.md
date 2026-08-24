GUIDE D'UTILISATEUR — ERP MORTIER, ADJUVANTS & PEINTURE

Bienvenue sur votre nouvel ERP ! Ce système a été conçu pour centraliser et automatiser l'ensemble de vos processus industriels, de l'achat des matières premières jusqu'à la facturation client et la comptabilité.

Ce guide vous accompagnera pas à pas dans l'utilisation quotidienne de l'application.

-------------------------------------------------------------------------------
1. CONNEXION & SECURITE
-------------------------------------------------------------------------------
Votre ERP est protégé par un système de sécurité de haut niveau :
- Identifiants : Demandez votre Login et Mot de passe à votre administrateur.
- Déconnexion automatique : Pour des raisons de sécurité, le système vous déconnecte après 30 minutes d'inactivité.
- Droits d'accès : Ce que vous voyez et pouvez modifier dépend de votre Rôle (ex: un Acheteur ne verra pas forcément la Comptabilité). Si un bouton d'action est grisé ou absent, c'est que vous êtes en mode "Lecture seule" sur ce module.

-------------------------------------------------------------------------------
2. MODULE ADMINISTRATION (Base de données)
-------------------------------------------------------------------------------
C'est le cœur du système. Tout commence ici.

A. Créer un Utilisateur
Seuls les Administrateurs peuvent créer des accès.
1. Allez dans Administration > Utilisateurs & Sécurité.
2. Créez l'utilisateur en lui attribuant un rôle (Admin, Commercial, etc.).
3. Définissez ses permissions (Lecture / Écriture) module par module.

B. Gérer les Référentiels (Clients, Fournisseurs, Articles)
Avant de faire le moindre achat ou la moindre vente, vous devez peupler vos catalogues :
1. Allez dans Administration > Référentiels.
2. Clients & Fournisseurs : Renseignez les coordonnées, NIF, RC, etc.
3. Matières Premières (MP) : Définissez vos ciments, sables, adjuvants chimiques et emballages. Renseignez bien les stocks minimums pour déclencher les alertes.
4. Produits (PF) & SKU : Créez vos produits génériques (ex: Mortier Colle), puis déclinez-les en SKU (ex: Sac de 25 Kg). Liez chaque SKU à son emballage correspondant.

-------------------------------------------------------------------------------
3. MODULE ACHATS (Approvisionnement MP)
-------------------------------------------------------------------------------
Ce module gère le réapprovisionnement de vos stocks physiques.

A. Passer une Commande
1. Allez dans Achats > onglet Nouvelle Commande.
2. Sélectionnez le fournisseur, la devise et ajoutez vos Matières Premières ou Emballages au panier.
3. Validez la commande. Elle passe au statut EN_ATTENTE.

B. Réceptionner la Marchandise (Entrée en Stock)
C'est cette étape qui augmente votre stock physique !
1. Allez dans l'onglet Réception & Entrée Stock.
2. Sélectionnez une commande en attente.
3. Indiquez la quantité réellement reçue, la conformité et la date de péremption.
4. Cliquez sur Valider la réception. Le système génère un Bon de Réception (BR) et augmente automatiquement le stock de la matière.

-------------------------------------------------------------------------------
4. MODULE PRODUCTION (Transformation MP -> PF)
-------------------------------------------------------------------------------
Ce module permet de consommer vos Matières Premières (MP) pour créer des Produits Finis (PF).

A. Créer une Recette (Nomenclature)
1. Allez dans l'onglet Créer une Recette.
2. Sélectionnez le Produit Fini (Vrac) et indiquez le rendement (ex: 1000 Kg).
3. Ajoutez les composants chimiques. Le Bilan de Masse vous indique en temps réel si votre recette est équilibrée.

B. Lancer et Suivre un Ordre de Fabrication (OF)
1. Allez dans Lancer un OF, choisissez un produit à fabriquer (SKU) et la quantité de sacs/unités prévue.
2. Dans l'onglet Suivi Production, vous pouvez faire avancer l'OF :
   - PLANIFIE -> EN COURS (Lancement en machine).
   - EN COURS -> CONTROLE QUALITE.

C. Clôturer l'OF (Déduction du Stock)
1. Lors du Contrôle Qualité, indiquez si le produit est conforme.
2. Saisissez la quantité réellement produite (SKU) et le nombre d'emballages consommés (pertes incluses).
3. À la validation : Le système déduit automatiquement le Vrac et les Emballages du stock de Matières Premières, et ajoute le Produit Fini dans le stock PF.

-------------------------------------------------------------------------------
5. MODULE STOCKS
-------------------------------------------------------------------------------
Ce module est purement consultatif et permet d'analyser vos inventaires générés par les Achats, la Production et les Ventes.

- Matières Premières : Consultez le stock disponible et la valeur (basée sur le Coût Moyen Pondéré - CMP).
- Produits Finis : Consultez les stocks de vos SKU.
- Traçabilité & Lots : Suivez la date de péremption et le statut de chaque lot généré par le système.

-------------------------------------------------------------------------------
6. MODULE VENTES & LOGISTIQUE
-------------------------------------------------------------------------------

A. Créer une Facture (Brouillon)
1. Allez dans Ventes > Nouveau Document.
2. Sélectionnez le client et ajoutez les Produits Finis au panier (les remises et le timbre fiscal se calculent automatiquement).
3. Si un produit est en rupture de stock, une alerte s'affiche.
4. Enregistrez en Brouillon (cela n'impacte pas encore les stocks) et téléchargez le PDF si besoin.

B. Valider la Facture ou Lancer en Production (Make-to-Order)
1. Allez dans Historique & Workflow.
2. Sélectionnez votre facture Brouillon.
3. Cas 1 (Stock suffisant) : Cliquez sur Valider.
4. Cas 2 (Rupture) : Le système bloque la validation et vous propose le bouton "Lancer en Production". Cela génère un OF d'urgence dans le module Production !

C. Expédier la Marchandise (Bon de Livraison)
1. Allez dans Expéditions & Bons de Livraison.
2. Sélectionnez une facture validée.
3. Affectez les Lots exacts que vous expédiez au client.
4. À la validation, le BL est généré et les stocks de Produits Finis sont déduits.

-------------------------------------------------------------------------------
7. MODULE FINANCE & COMPTABILITE
-------------------------------------------------------------------------------
Ce module centralise la trésorerie et le lettrage comptable.

A. Gérer les Comptes et Saisir les Flux
1. Créez vos Caisses et Comptes bancaires dans l'onglet Comptes & Caisses.
2. Saisissez vos paiements dans Saisie Règlements (Encaissement d'un client ou Décaissement vers un fournisseur). Le système génère automatiquement une écriture comptable.

B. Le Lettrage (Rapprochement bancaire)
Pour qu'une facture passe au statut PAYEE, il faut lui associer un règlement.
1. Allez dans Lettrage.
2. Sélectionnez un Règlement en attente à gauche.
3. Sélectionnez la Facture correspondante à droite.
4. Indiquez le montant à appliquer et validez.

C. Le Grand Livre
Retrouvez dans l'onglet Grand Livre toutes les écritures comptables (Débits/Crédits) générées automatiquement par le système, assurant une traçabilité financière parfaite.

-------------------------------------------------------------------------------
8. CRM & RH
-------------------------------------------------------------------------------
- CRM : Suivez vos opportunités commerciales dans un Pipeline (Nouvelle, Qualification, Proposition, Gagnée). Cela vous permet de prévoir votre chiffre d'affaires futur.
- RH : Gérez le registre de vos employés, suivez les demandes de congés et enregistrez les pointages/feuilles de temps pour la gestion de la paie.

-------------------------------------------------------------------------------
9. TABLEAUX DE BORD (Dashboards)
-------------------------------------------------------------------------------
Ce module est le centre de pilotage de l'entreprise. Il regroupe les KPIs (Indicateurs Clés de Performance) en temps réel calculés à partir de vos données SQL.

- Vue Direction : Résumé global (CA, Trésorerie, Impayés, Alertes Stock).
- Ventes : Balance âgée (qui vous doit quoi et depuis quand), Top Clients, Panier moyen.
- Achats : Dépendance fournisseurs, suivi de l'évolution du prix d'achat des matières premières.
- Stocks : Valeur financière immobilisée, liste des lots qui périment bientôt.
- Production : Taux de rejet lors des contrôles qualité, volume de production.

-------------------------------------------------------------------------------
FOIRE AUX QUESTIONS (Dépannage)
-------------------------------------------------------------------------------
- Je n'arrive pas à valider une réception d'achat : Vérifiez que vous avez bien les droits d'écriture sur les modules Achats ET Stocks (car la réception impacte les deux).
- Je n'arrive pas à clôturer un Ordre de Fabrication (OF) : Le système vérifie s'il y a assez de Vrac (chimique) ET assez d'Emballages en stock pour produire la quantité saisie. Si le stock MP est insuffisant, l'OF sera bloqué.
- Le PDF de ma facture ne se génère pas : Assurez-vous d'avoir bien renseigné les coordonnées complètes du client (Adresse, NIF, RC) dans le module Administration.
- Ma facture reste au statut PARTIELLE dans la finance : Cela signifie que la somme lettrée (affectée) est inférieure au montant TTC de la facture. Ajoutez un nouveau règlement et lettrez la différence.