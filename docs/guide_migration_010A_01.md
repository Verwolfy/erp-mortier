# Guide et Aide — Migration 010-A-01 : isolation des environnements

**Statut : correctif proposé, NON déployé. À installer et tester uniquement sur une branche et un projet TEST isolés.**

## Pourquoi cette sécurité ?

Une application Streamlit lancée depuis un PC peut utiliser les secrets d'une
base réelle. Les tâches automatiques GitHub peuvent également envoyer des
courriels réels. Le correctif ajoute un contrôle explicite **avant l'ouverture
des clients Supabase ou Google Sheets**. En cas d'erreur, l'accès est refusé.

## Administrateur — prérequis Streamlit TEST

Créer un **projet Supabase TEST distinct** et des **classeurs Google TEST distincts**.
Dans les secrets du déploiement **TEST uniquement**, ajouter (exemples fictifs) :

```toml
[erp_environment]
name = "TEST"
test_supabase_url = "https://REF-PROJET-TEST.supabase.co"
production_supabase_url = "https://REF-PROJET-PROD.supabase.co"
production_enabled = false

[erp_environment.test_sheets_ids]
referentiels = "ID-DE-CLASSEUR-TEST"
achats = "ID-DE-CLASSEUR-TEST-ACHATS"
stocks = "ID-DE-CLASSEUR-TEST-STOCKS"
production = "ID-DE-CLASSEUR-TEST-PRODUCTION"
ventes = "ID-DE-CLASSEUR-TEST-VENTES"
crm = "ID-DE-CLASSEUR-TEST-CRM"
rh = "ID-DE-CLASSEUR-TEST-RH"
logs = "ID-DE-CLASSEUR-TEST-LOGS"
finance = "ID-DE-CLASSEUR-TEST-FINANCE"
```

La valeur `supabase.url` déjà utilisée doit pointer EXACTEMENT vers
`erp_environment.test_supabase_url`. Les clés TEST sont dans `supabase.key`
et `supabase.stock_service_key` et les secrets Google sont des identifiants
TEST. **Ne pas recopier des clés, données ou fichiers Google PROD en TEST.**

## Administrateur — PRODUCTION

Le mode `PRODUCTION` requiert `production_enabled = true`, à renseigner
uniquement après autorisation formelle de déploiement et tests satisfaisants.
L'URL active doit correspondre exactement à `production_supabase_url`.
L'environnement TEST ne peut utiliser aucun ID Google Sheets de la liste
`config/settings.py`, lesquels sont considérés comme les classeurs PROD.

## Actions planifiées GitHub

Définir séparément dans GitHub Actions les variables d'environnement :
`ERP_ENV`, `ERP_TEST_SUPABASE_URL`, `ERP_PRODUCTION_SUPABASE_URL`,
`ERP_PRODUCTION_ENABLED`. Ne jamais mettre de clés dans ces variables : garder
`SUPABASE_KEY`, `SMTP_USER`, `SMTP_PASSWORD` dans **GitHub Secrets**.

Pour les relances, configurer `ERP_REMINDER_MINIMUM_DZD` (seuil métier validé)
et `ERP_ENABLE_EMAIL_SEND` ; en mode TEST aucun e-mail ne part, même avec
`ERP_ENABLE_EMAIL_SEND=true`. En PRODUCTION, l'envoi demande deux autorisations
concordantes : `ERP_PRODUCTION_ENABLED=true` ET `ERP_ENABLE_EMAIL_SEND=true`.

## FAQ / Aide contextuelle

- **« Politique ERP absente »** : la section `erp_environment` manque dans
  Streamlit Secrets. Ne pas contourner le contrôle.
- **« Projet Supabase différent »** : vérifier la correspondance des URL et le
  profil TEST/PRODUCTION. Ne pas copier les clés de production dans TEST.
- **« Classeur TEST identique »** : un identifiant de classeur TEST correspond
  à un classeur réel connu. Créer un nouveau classeur TEST.
- **« PRODUCTION désactivée »** : le feu vert de mise en production n'a pas
  été explicitement matérialisé dans la configuration.
- **« SIMULATION »** : les relances sont évaluées mais aucun e-mail n'est envoyé.

## Limites et contrôles avant fusion

Ce premier verrou est une **défense supplémentaire**, pas un pare-feu réseau.
Il ne prouve pas qu'une clé Supabase appartient au projet déclaré, n'empêche
pas un autre script non protégé de contacter la production, et ne remplace ni
RLS, ni RBAC, ni l'isolation des secrets et des comptes fournisseurs.
Les autres outils externes, la rotation des secrets et les procédures de
recette feront l'objet des étapes 010-A suivantes.

## Compatibilité / performance

Les clients Supabase et gspread ne sont plus partagés dans un cache global
entre les sessions. Ce choix évite la réutilisation d'un client authentifié
à travers différents utilisateurs et assure que la politique TEST/PROD est
vérifiée pour chaque création. Il faut mesurer le coût réseau et la charge
de connexions lors des tests de performance avant de publier cette version.
