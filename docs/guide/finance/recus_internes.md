# Accusés internes de paiement — livraison 020

## Périmètre

Les tables Finance existantes restent la source du paiement réellement
enregistré : `reglements`, `lettrage`, `factures`.

Une nouvelle opération `erp_emettre_recu_interne` crée un **accusé interne**
pour un règlement client validé, enregistré et daté :
- un accusé par `reglement_id`, indépendamment du nombre de factures lettrées ;
- `operation_id` unique et stable pour les reprises après timeout ;
- identifiant `RINT-...` non assimilable à une séquence légale ;
- référence de règlement, date, client, montant total et moyen enregistrés comme instantané ;
- annulation, suppression et modification de l'instantané interdites au niveau SQL ;
- la transaction ne modifie ni montant payé de la facture ni écriture comptable ;
- nouveau statut `INTERNE_NON_FISCAL` et `timbre_statut=NON_CALCULE` ;
- service Python soumis aux autorisations Finance, exécutable seulement avec la clé serveur ;
- aucune entrée officielle, PDF de quittance ou timbre déclaré.

## Sécurité

La table `erp_recus_internes` a RLS activée, aucun privilège pour `anon` /
`authenticated` et les privilèges `SELECT, INSERT` pour le seul `service_role`.
La fonction `SECURITY INVOKER` est exécutée par le serveur et ne permet aucun
appel public. Une deuxième tentative sur le même règlement et le même
`operation_id` retourne l'identifiant existant ; une tentative de création
différente sur le même règlement est rejetée.

## Prérequis opérationnel

Migration source : `sql/020_recus_internes.sql`, migration Supabase
`erp_020_recus_internes_20261029`, à exécuter sur TEST puis PRODUCTION après
les tests et contrôles de sécurité. Aucun enregistrement historique n'est
modifié par le script.

Les paiements partiels sont conservés au niveau des lettrages ; l'accusé est
rattaché au **montant total réellement reçu**, sans multiplication par facture.
Une dévolution fiscale par paiement partiel demandera une validation légale
supplémentaire avant émission d'une quittance officielle.

La sauvegarde PostgreSQL reste facultative conformément à la décision du
propriétaire. La finalisation d'une quittance fiscale (article 100 du Code
du timbre, JO n°84 de 2024 / consolidation 2026) n'est PAS couverte.

## Vérification

- Tests ciblés Python et tests statiques SQL.
- Analyse syntaxique PostgreSQL et PL/pgSQL.
- Vérification réelle des privilèges sur TEST.
- Transaction de vérification idempotence / refus de doublon, dans
  une transaction annulée par ROLLBACK sur TEST.
- Surveillance des éventuels résultats d'API inconnus et reprise avec
  le même identifiant d'opération dans l'interface.


## État de déploiement — 29 octobre 2026

La migration `erp_020_recus_internes_20261029` a été exécutée sur
**Supabase TEST puis PRODUCTION**, sans changement d'anciennes factures.

Les deux environnements ont été vérifiés : table disponible, RLS active,
aucun privilège de lecture pour `anon` ou `authenticated`, droits
`SELECT, INSERT` et `EXECUTE` pour `service_role`.

Un essai transactionnel sur TEST a vérifié la création, la répétition avec
le même `operation_id`, le refus d'un autre accusé pour le même règlement,
le blocage des mises à jour et des suppressions. L'essai a été terminé par
`ROLLBACK` et le contrôle suivant a confirmé **0 document de test conservé**.
Le registre de production contient **0 accusé** au moment de l'installation.

L'émission d'un **accusé interne** ne valide en aucun cas la conformité des
quittances fiscales, ni la régularité d'un timbre de règlement.
