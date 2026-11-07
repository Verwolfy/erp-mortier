# Aide contextuelle ERP — Guide opératoire

**Périmètre :** Administration, Achats, Stocks, Production, Ventes, CRM, Finance, RH, Tableaux de bord, Documents et Guide. Référentiel statique `modules/help/contextual.py`.

## Fonctionnement

- **Survol d'un libellé ou d'un champ** : l'icône de tooltip Streamlit explique la notion ou la saisie. Fonction `topic_help()` pour les titres et `field_help()` pour les contrôles.
- **Clic sur « ⓘ Aide : [rubrique] »** : ouvre une fenêtre légère qui détaille la notion, le chemin à suivre et les vérifications. Fonction `show_context_help(st, topic)`.
- **Mobile / tactile** : utiliser le bouton cliquable. L'accessibilité ne repose jamais uniquement sur le survol ou la couleur.
- **Onglets** : Streamlit 1.38 n'expose pas un bouton interactif dans le libellé natif de `st.tabs`. L'aide se trouve au début du contenu de chaque onglet, sans modifier le nom de l'onglet.
- **Formulaires** : le paramètre natif `help=` des champs conserve le widget et son état ; les actions conservent les appels métier et leurs garde-fous. Les textes n'exécutent aucune requête, RPC ni écriture.

## Exemple : Production > Consommations et contrôles

**Historique des consommations et contrôles qualité.** Un OF (ordre de fabrication) consomme des matières par lot réel, et sa clôture produit un contrôle qualité (CQ).

1. Ouvrir **Production & Nomenclatures > Consommations et contrôles**.
2. Survoler le titre ou cliquer sur **ⓘ Aide : Consommations et contrôles qualité** pour lire les consignes.
3. Dans **Page des historiques Production**, saisir `1` (première page), puis cliquer sur **Afficher l'historique Production**.
4. Consulter les historiques paginés et rapprocher les OF, les lots, quantités et statuts. Une page vide ne prouve ni une absence globale de données ni un échec de lecture.

## Bonnes pratiques d'UX et de sécurité

1. **Deux niveaux** : une définition très courte au survol ; une procédure en trois parties au clic. Ne pas afficher un pavé d'aide toujours ouvert.
2. **Clarté** : conserver les mots du métier (OF, CQ, SKU, CUMP, SCF) avec leur signification en contexte. Employer les mêmes noms que les onglets visibles.
3. **Aide actionnable** : expliquer les étapes concrètes, l'impact du clic et ce qu'il faut contrôler avant de valider.
4. **Aides près de l'action** : titre de section + bouton cliquable, et infobulle sur le champ/contrôle. Aucune modification CSS/JS non officielle des onglets.
5. **Accessibilité** : bouton au clavier et au tactile, texte clair sans dépendance à la couleur ; ne pas réserver l'aide au survol.
6. **Moindre privilège** : aucun contrôle RBAC/RLS n'est contourné. Une aide est affichée seulement si le module correspondant est déjà accessible.
7. **Confidentialité** : aucun identifiant réel, secret, URL privée, donnée RH personnelle ni contenu utilisateur injecté dans les textes statiques.
8. **Transaction incertaine** : pour une validation ou création à résultat inconnu, vérifier les données en base et réutiliser les mécanismes de reprise prévus ; ne pas provoquer de doublon.
9. **Frontières fiscales et comptables** : les aides ne qualifient pas les taux TVA/IRG/CNAS, ne valident pas de pièces SCF et ne modifient ni coûts ni stocks.
10. **Évolutivité** : ajouter la notion à `TOPICS`, insérer `show_context_help` dans le bon écran, puis ajouter une aide de champ si nécessaire ; tester l'unicité des boutons et la CI.

## Contrôle qualité

- `tests/test_contextual_help_erp.py` vérifie le catalogue, les références des écrans, les infobulles, l'absence de requêtes et la couverture.
- La suite CI complète est obligatoire avant fusion.
- Vérifier ensuite dans l'ERP hébergé le survol et le clic, à l'aide du repère de version de la branche réellement déployée ; **CI verte ≠ déploiement prouvé**.

**Limite volontaire :** le même texte d'aide ne remplace ni une formation, ni la qualification comptable officielle, ni les validations de l'entreprise.
