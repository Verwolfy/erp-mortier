===============================================================================
               DOCUMENTATION ARCHITECTURE & SCRIPTS - ERP HYBRIDE
===============================================================================
Projet : ERP Mortier, Adjuvants & Peinture
Architecture : Python (Streamlit) + Supabase (SQL) + Google Sheets (Backup)
Dernière mise à jour de l'architecture : Intégration des filtres SQL (Anti-OOM)
et précision comptable (Decimal).
===============================================================================

-------------------------------------------------------------------------------
1. RACINE & CONFIGURATION GLOBALE
-------------------------------------------------------------------------------
> app.py
  - Rôle : Point d'entrée principal de l'application Streamlit.
  - Détails importants : Gère le routage vers les différents modules, affiche le 
    menu latéral selon les droits, et intègre un Timeout de sécurité (déconnexion 
    automatique après 30 minutes d'inactivité).

> requirements.txt / runtime.txt
  - Rôle : Définit les dépendances et la version de l'environnement serveur.
  - Détails importants : Fixé sur Python 3.12. Contient gspread, supabase, 
    bcrypt (sécurité), et tenacity (résilience réseau).

> config/settings.py
  - Rôle : Variables globales.
  - Détails importants : Contient les IDs des Google Sheets (Backup) et fixe 
    le fuseau horaire (Africa/Algiers) pour horodater correctement les flux.

> config/roles.py
  - Rôle : Gestion des permissions (RBAC).
  - Détails importants : Interroge la base de données pour vérifier si l'utilisateur 
    a le droit de Lecture/Écriture. Bypass automatique pour le rôle "ADMIN".

-------------------------------------------------------------------------------
2. DOSSIER 'core/' (LE MOTEUR DE L'ERP)
-------------------------------------------------------------------------------
> core/db_service.py
  - Rôle : Chef d'orchestre de la base de données hybride.
  - Détails importants : Gère le "Dual-Write" (écriture SQL puis Sheets). Intègre 
    la fonction 'fetch_data_filtered' pour filtrer la donnée côté SQL et éviter 
    les crashs mémoire (Out of Memory), ainsi qu'une sécurité backend stricte.

> core/sheets_service.py
  - Rôle : Connexion à l'API Google Sheets.
  - Détails importants : Utilise '@retry' (Tenacity) pour relancer l'écriture 
    en cas de micro-coupure réseau. Met en cache les lectures.

> core/utils.py
  - Rôle : Fonctions utilitaires.
  - Détails importants : Sépare les identifiants séquentiels (ex: FAC-2026-0001) 
    des identifiants techniques UUID (pour les millions de mouvements de stocks).

> core/logger.py
  - Rôle : Piste d'audit et debug.
  - Détails importants : Alimente l'onglet 'AuditTrail' (qui a fait quoi et quand) 
    et l'onglet 'Erreurs' (capture des crashs Python).

> core/pdf_generator.py
  - Rôle : Génération de documents PDF (Factures, BL, etc.).
  - Détails importants : Unifie l'en-tête et le pied de page, convertit les 
    montants en toutes lettres (Dinars Algériens).

> core/listes_service.py
  - Rôle : Alimente tous les menus déroulants de l'UI (Pays, Catégories, etc.).

-------------------------------------------------------------------------------
3. DOSSIER 'modules/' (LOGIQUE MÉTIER & INTERFACES)
Chaque module contient 'service.py' (logique/calculs) et 'views.py' (UI Streamlit).
-------------------------------------------------------------------------------
> modules/auth/
  - Rôle : Authentification.
  - Détails importants : Hachage bcrypt, protection anti-bruteforce (blocage de 
    3 minutes après 3 tentatives ratées), pas d'autocomplétion.

> modules/admin/
  - Rôle : Gestion des Référentiels (Clients, Fournisseurs, Matériaux, SKU).
  - Détails importants : Interface de type tableau éditable (Inline Editing).

> modules/achats/
  - Rôle : Commandes d'achats et Bons de Réception (BR).
  - Détails importants : La validation d'un BR incrémente instantanément le stock 
    physique (CMP mis à jour) via la communication avec modules.stocks.service.

> modules/stocks/
  - Rôle : Inventaire, Mouvements et Traçabilité.
  - Détails importants : Utilise la méthode FIFO stricte. Décrémente les Lots 
    les plus anciens en premier. Calcule la valeur financière (CMP).

> modules/production/
  - Rôle : Recettes (BOM), Ordres de Fabrication (OF), Contrôle Qualité.
  - Détails importants : Affiche le Bilan de Masse en temps réel. La clôture 
    d'un OF déduit le vrac chimique + l'emballage, et ajoute le Produit Fini 
    en stock. Peut générer des OF d'urgence depuis le module Ventes.

> modules/ventes/
  - Rôle : Cycle "Order-to-Cash" (Devis, Factures, BL).
  - Détails importants : Utilise la librairie Python 'Decimal' pour garantir 
    une précision financière absolue sur le calcul de la TVA et du timbre fiscal. 
    Empêche la validation si le stock est insuffisant.

> modules/finance/
  - Rôle : Trésorerie, Lettrage et Comptabilité.
  - Détails importants : Alimente le Grand Livre (Écritures Comptables) 
    automatiquement à chaque règlement. Le Lettrage fait passer le statut de la 
    facture à PAYEE.

> modules/crm/ & modules/rh/
  - Rôle : Pipeline commercial, notes d'interactions, annuaire employés et congés.

> modules/dashboards/
  - Rôle : Centre de pilotage (KPIs).
  - Détails importants : Utilise 'fetch_data_by_date_range' pour interroger 
    Supabase par dates afin de calculer le Compte de Résultat (P&L) et les 
    balances âgées sans saturer la RAM.

-------------------------------------------------------------------------------
4. DOSSIER 'scripts/' & '.github/workflows/' (AUTOMATISATION)
-------------------------------------------------------------------------------
> scripts/envoyer_relances.py
  - Rôle : Tâche CRON qui cherche les factures échues de plus de 10 DZD.
  - Détails importants : Envoie un email SMTP automatique aux clients retardataires.

> scripts/recalculer_stock.py
  - Rôle : Audit de sécurité nocturne.
  - Détails importants : Fait la somme mathématique de tous les mouvements (+/-) 
    depuis le début de l'entreprise et la compare au stock actuel affiché, puis 
    corrige les écarts.

> scripts/import_data.py
  - Rôle : Initialisation des données.
  - Détails importants : Injecte le dictionnaire industriel de base (Wilayas, 
    Codes Douaniers, Catégories MP spécifiques à la chimie du bâtiment).

> .github/workflows/*.yml
  - Rôle : Fichiers YAML pour GitHub Actions.
  - Détails importants : Configurés sur Python 3.12, ils exécutent les scripts 
    précédents de façon autonome, sans intervention humaine.

===============================================================================
Fin du fichier d'aide.