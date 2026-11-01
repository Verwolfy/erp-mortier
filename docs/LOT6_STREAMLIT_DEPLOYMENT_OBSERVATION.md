# NextGen — Vérification du déploiement Streamlit (Lot 6)

Date : 2026-11-01.

- **URL connue par capture utilisateur (31/10)** : https://nextgent-erp.streamlit.app/
- ERP GitHub : \`Verwolfy/erp-mortier\` / \`main\` ; onglet NextGen fusionné via PR #31, commit \`6a64c882f00ce6f295e98eead3ba856fe3a6e67e\`.
- Le test public \`.github/workflows/streamlit-shell-observe.yml\` est en **lecture seule** : récupère au plus 160 Ko de HTML anonyme, sans connexion et sans cookies.
- **Attention** : une réponse HTTP 200 ne démontre ni le SHA Git déployé, ni l'état des secrets Streamlit, ni la disponibilité de l'onglet après connexion.
- Vérification fonctionnelle **à effectuer dans le tableau Streamlit Cloud** : app \`nextgent-erp\`, dépôt \`Verwolfy/erp-mortier\`, branche \`main\`, entrée \`app.py\`, journaux de déploiement, puis connexion ERP via accès déjà détenu et onglet CRM « Demandes NextGen ».
- L'onglet doit montrer un message d'inactivité par défaut. Ne pas activer \`nextgen.crm_inbox_read_enabled\` en production tant que l'analyse de confidentialité et l'audit de la clé \`service_role\` ne sont pas finalisés.
- **Aucun changement d'identifiant, token, base, DNS ou déploiement forcé dans ce lot**. Le workflow émet un warning plutôt que de marquer le code en échec si le réseau ne permet pas de conclure.
