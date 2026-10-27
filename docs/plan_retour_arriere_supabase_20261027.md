# Retour arrière — migrations Supabase PRINCIPALE (27/10/2026)

## Sources de sauvegarde
- Fichiers conservés **sur le PC de l'utilisateur, hors Git** :
  `C:\LH\Perso\ERP_PYT\sauvegardes_erp\20261027_191110\PRINCIPALE-public.dump`
  et `PRINCIPALE-public.sql`.
- Ces archives contiennent uniquement le schéma `public`. Une restauration à blanc n'a **pas** encore été testée.
- Une restauration intégrale en écrasant la base PRINCIPALE est **interdite** sans analyse préalable des changements depuis la sauvegarde.

## Migrations
- `erp_012_harden_principale_grants` : retire les droits directs des rôles anon/authenticated sur `public`; modifie des privilèges par défaut et le chemin `increment_compteur`.
- `erp_013_security_tables_and_rpc` : ajoute cinq tables, cinq fonctions, un secret neuf, et une habilitation sécurité à l'administrateur présent.
- `erp_014_sales_order_security_fix` : passe `erp_create_sales_order` en SECURITY DEFINER, avec chemin sécurisé, et limitation à service_role.
- `erp_015_auto_rls_trigger` : crée `rls_auto_enable` et `ensure_rls` activé.

## Plan non destructeur en cas d'incident
1. **Bloquer le déploiement GitHub main** et sauvegarder l'état courant avant toute correction.
2. Si le déclencheur pose problème, désactiver uniquement `ensure_rls` après diagnostic; ne pas désactiver RLS des tables.
3. Si une RPC de sécurité pose problème, suspendre ses appels applicatifs. Ne pas supprimer les tables contenant des opérations ou tentatives d'authentification.
4. Si la création de commande régresse, investiguer les droits et logs; un retour à SECURITY INVOKER reproduirait l'erreur de privilège FOR SHARE déjà observée.
5. En cas de besoin de réouverture API, restaurer **uniquement les GRANT strictement nécessaires après examen** des anciennes ACL du dump. Ne jamais rétablir `GRANT ALL` aux rôles publics globalement.
6. Documenter l'incident, valider en TEST, puis appliquer un correctif versionné avec tests.

## Critères avant publication main
- 70 tables en PRINCIPALE, RLS sur toutes.
- Pas d'EXECUTE anon/authenticated sur les RPC de sécurité.
- Tests Python de la branche main locale réussis.
- Vérifier session ERP, vente, permissions SECURITY_MANAGER et configuration des secrets Streamlit.
- Aucune copie des comptes, tokens, secrets ni données fictives de TEST.
