# Tableaux de bord & KPIs — revue ergonomique DEMO et contrôle visuel
**Date : 7 novembre 2026 | Objet : PR d'ajustement UX/graphique**

## Constat et corrections
1. **Position du mode démonstration** : auparavant, `st.tabs()` créait la navigation avant `st.toggle()`. Comme Streamlit dispose ses blocs dans l'ordre de création, le mode DEMO pouvait apparaître après les panneaux au lieu d'être immédiatement visible. Désormais le sélecteur, la bannière et l'avertissement de provenance sont affichés **avant les neuf onglets**. Aucun changement des droits ni des sources.
2. **Date de référence** : tous les sélecteurs de période utilisent le fuseau de l'ERP via `get_local_now()`, et non `datetime.date.today()` dépendant du serveur. Les filtres et le mode DEMO ont ainsi la même date métier.
3. **Cascade de gestion** : la dernière barre Plotly (mesure `total`) a `y=0` pour obtenir le cumul. Son infobulle pouvait afficher **0 DZD**, même lorsque le solde estimé était non nul. L'infobulle affiche désormais le solde de gestion calculé via `customdata`, sans modifier le calcul ni présenter ce solde comme un EBITDA comptable.
4. **Tests de non-régression** : ordre DOM logique du sélecteur avant `st.tabs`, heure de référence ERP et valeur du total dans le tooltip Plotly.

## Validation prévue / qualité
- Tests des KPI et rendu des neuf panneaux : `tests/test_dashboard_demo_mode.py`, `tests/test_dashboard_demo_streamlit_smoke.py`, `tests/test_dashboard_kpi_visuals.py`.
- CI GitHub ERP et audit de réconciliation avant fusion sur `main`.
- Aucune migration, aucun nouveau flux de données, aucune modification de Supabase et aucune création/suppression de `DEMO/SIM`.

## Limites de vérification de l'hébergement
- GitHub Actions peut confirmer le rendu sans navigateur par `AppTest`, la présence des neuf onglets et les valeurs calculées sur des exemples fictifs.
- L'URL déclarée `https://nextgent-erp.streamlit.app/` a renvoyé lors des derniers contrôles **HTTP 303 vers `share.streamlit.io`**. Ce résultat ne démontre ni un déploiement échoué ni une interface authentifiée accessible.
- La version réelle exécutée par Streamlit Cloud, le comportement sur écran mobile et les captures visuelles de la session utilisateur restent **non vérifiés** en l'absence d'accès authentifié.

## Procédure de recette visuelle (sans opération métier)
1. Dans Streamlit Cloud, vérifier que l'application cible est liée à `Verwolfy/erp-mortier` branche `main` et vérifier le dernier SHA réellement déployé.
2. Ouvrir l'ERP avec un utilisateur habilité `Dashboards:lecture`. Vérifier que **Mode démonstration** apparaît directement sous le titre, avant les neuf onglets.
3. Activer DEMO ; lire la bannière fictive et cliquer successivement sur Direction, Rentabilité, Ventes, Achats, Stocks, Production, CRM, RH et Finance. Confirmer la visibilité des cartes, courbes, barres, cascade, labels d'unité et info-bulles, notamment le **solde final DZD** de la cascade.
4. Changer les filtres de dates, matière, unité et alerte péremption ; contrôler l'absence de graphique trompeur à zéro lorsque le dénominateur est nul ou que la source manque.
5. Désactiver DEMO et vérifier le retour au réel avec l'avertissement de provenance `DEMO/SIM`. Ne jamais utiliser ces références pour une validation comptable.
6. Répéter sur mobile : bannière lisible, onglets accessibles, aucune coupe des grands nombres, aide accessible au clic.
7. En cas d'anomalie, relever uniquement le SHA visible, l'onglet, le champ et un message d'erreur expurgé de secrets ; ne jamais communiquer une clé service_role.

## Décisions actives
Les données de développement `DEMO/SIM` restent conservées jusqu'à finalisation du projet. Leurs montants, dates, taux et identifiants sont **fictifs pour test**, ne constituent aucune qualification fiscale, CNAS, IRG, coût SCF ou reporting officiel.
