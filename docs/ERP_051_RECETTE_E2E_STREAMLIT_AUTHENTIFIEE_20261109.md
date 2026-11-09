# ERP-051 — Recette E2E authentifiée Streamlit (09 novembre 2026)

## Périmètre
- URL contrôlée : https://nextgent-erp.streamlit.app/
- Méthode : navigateur TinyFish avec connexion ERP **effectivement réussie** grâce à un identifiant de test stocké dans TinyVault / Bitwarden ; aucun secret divulgué ou copié dans le dépôt.
- Rôle vérifié : `ADMIN`. Les droits des autres profils **ne sont pas vérifiés** par cette session.
- Limite stricte : navigation et consultation seulement ; aucun clic de validation, facture, règlement, création, suppression, lancement production, réception, paie ni modification de configuration.
- Deux runs E2E :
  - [Inspection des 9 modules](https://agent.tinyfish.ai/runs/cb122cc1-beda-404b-8f4c-86c283f28a89), 31 étapes, succès.
  - [Contre-vérification des panneaux et versions](https://agent.tinyfish.ai/runs/2951214e-2ee0-4f00-81da-eb267860224c), 16 étapes, succès.

## Résultats vérifiés de navigation
| Module | Ecran ouvert | Résultat | Limite |
|---|---|---|---|
| Administration | Référentiels et clients | Oui, aucune erreur bloquante vue | Écritures interdites pendant essai |
| Achats | Nouvelle commande, fournisseurs et MP de test | Oui, tableau et sélecteurs lus | Aucun bon de commande créé |
| Stocks | État des stocks MP | Oui, cinq lignes de stock visibles | Pas de mouvement |
| Production | Recettes / nomenclatures | Oui, formulaire et composants accessibles | Pas de fabrication |
| Ventes | Facture / Avoir | Oui, marqueur version Ventes visible | Aucune émission ni validation |
| CRM | Pipeline opportunités | Oui, titre CRM confirmé en contre-vérification | Pas d'opportunité créée |
| Finance | Tableau de bord et règlements | Oui, indicateurs lus | Aucun paiement ni lettrage |
| RH | Registre des employés | Oui, en-têtes vérifiés dont `employe_id`, `nom`, `poste`, `service` | Aucun salarié créé ; données nominatives non copiées |
| Dashboards | Vue Direction | Oui, avertissement sur provenance DEMO/SIM | KPI non homologués |

**Résultat : 9/9 menus fonctionnels pour le rôle ADMIN, en lecture seule.** Aucune erreur visuelle bloquante signalée par le navigateur pendant les deux exécutions. Ce n'est **pas** une homologation de l'intégralité des transactions, des permissions autres rôles, ni de toutes les sous-vues.

## Données de démonstration
- Plusieurs références préexistantes `DEMO26_`, `SIM26_` et `SIM-AUD-` ont été observées dans les vues Achats/Stocks/Finance.
- Dashboard Direction : message `Provenance à qualifier: 33 référence(s) avec préfixe DEMO/SIM détectée(s) parmi les sources métier. Ces lignes restent incluses dans les KPI; ne pas prendre ces indicateurs pour des résultats d'exploitation homologués.`
- La présence de données DEMO à l'écran n'est pas une preuve que **chaque** nouvel enregistrement de l'espace `SIM-ERP49-` est individuellement visible dans la vue testée.

## ANOMALIE : provenance de version incohérente
Les deux runs ont rapporté la même version en barre latérale :

`Version ERP : 15a63bf9d77968b4c4d0b9b6ad74b614f68c3984 · checkout Git local · SHA attendu non fourni`

Le run de contre-vérification a explicitement lu dans Ventes :

`Version interface Ventes : SOF-ERP-20261109-TAX-READINESS-01`

GitHub confirme :
- `15a63bf9...` = ancien commit présent dans le dépôt (merge LOT-06B) ;
- dans **ce** commit, `modules/ventes/views.py` affiche `SOF-ERP-20261030-EXO-HIST-02` ;
- le `main` observé juste avant cette note était `8c8565ae2d526fb2de3c1a6f950b00eea3aa1ad8`, soit **195 commits d'avance** sur `15a63bf9` (comparaison GitHub) ;
- ce `main` contient `SOF-ERP-20261109-TAX-READINESS-01`.

Conclusion : le `git HEAD` affiché dans la barre latérale et le marqueur du code Ventes se contredisent. **Il est impossible de certifier le commit exact des sources actuellement exécutées.** Vérification de Streamlit Cloud, cache, checkout effectif et configuration déploiement indispensable avant homologation.

Suivi ouvert : [GitHub issue #78](https://github.com/Verwolfy/erp-mortier/issues/78).

## Protections préservées
- Aucun changement de données métier, aucun contournement de RLS/GRANT et aucune modification du socle fiscal ou SCF par cette recette.
- Les anomalies fiscales/couts précédentes restent ouvertes : [#76](https://github.com/Verwolfy/erp-mortier/issues/76) (facture sans qualification de SKU acceptée côté RPC historique) et [#77](https://github.com/Verwolfy/erp-mortier/issues/77) (achats inactifs).
- La CI précédente vérifie des tests Python simulés, la recette ici atteste une navigation **réelle authentifiée**, mais les transactions réelles sur site restent non exercées.

## Suite recommandée
1. Élucider l'écart `git HEAD` / marqueur Ventes avec l'issue #78 ; vérifier source et branche déployée dans Streamlit Cloud sans secrets.
2. Après remise en cohérence, refaire la recette E2E des 9 modules, puis les sous-vues et permissions de profils non-ADMIN.
3. Corriger la protection fiscale (#76) avant toute émission réelle, puis clarifier le contrôle des références inactives Achats (#77).
4. Mettre à part les références DEMO des KPI de gestion destinés à l'exploitation ou maintenir un avertissement explicite.

Aucun mot de passe Bitwarden ou API TinyFish n'a été consigné dans ce document.
