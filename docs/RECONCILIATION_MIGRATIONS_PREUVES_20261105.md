# Réconciliation SQL ERP — preuves du 5 novembre 2026

**Source réelle :** `supabase_migrations.schema_migrations.statements[1]` sur la base principale `wenydirqtmkywbxbxfal`. **Source dépôt :** fichiers SQL de `Verwolfy/erp-mortier` (branche `main`). Vérification des chaînes réalisée en lecture seule ; aucune migration rejouée ni modifiée.

## Résultats

| Versions | Résultat |
|---|---|
| 20261027200803, 20261027201513, 20261027201607 | Le SQL exécuté apparaît **exactement** dans le fichier archivé, précédé de deux commentaires d'en-tête ; archive complète avec préambule documentaire uniquement |
| 20261027201418 | Les six segments `sql/supabase_applied/20261027201418_*.sql`, sans leurs deux lignes d'en-tête individuelles et avec espaces supprimés pour comparaison, correspondent au texte exécuté ; variations de séparateurs/espaces entre segments |
| 20261028203753, 20261028203801, 20261028203807, 20261028204352 | Identité exacte entre chaîne Supabase et fichier du dépôt |
| 20261029085429, 20261029101828, 20261029112102, 20261029112232, 20261029131913, 20261029200156, 20261029201625 | Identité exacte entre chaîne Supabase et fichier du dépôt |
| 20261029202954, 20261029204104, 20261029210253, 20261029210305, 20261030155229, 20261030164230 | Identité exacte entre chaîne Supabase et fichier du dépôt |
| 20261031204336, 20261031220121 | Migrations du site référencées hors dépôt ERP : **non comparées ici** ; aucun SQL réexécuté |

**Synthèse :** 17 correspondances textuelles exactes ; 3 correspondances exactes après exclusion des deux commentaires d'archive ; 1 correspondance de six segments après suppression de leurs en-têtes et normalisation des espaces ; 2 migrations de site hors périmètre de cette comparaison. Les 23 migrations sont enregistrées dans l'historique natif Supabase.

**Réserve :** la normalisation des espaces n'est pas équivalente à une validation de schéma réel, de politiques RLS, de privilèges, ni à un test de migration sur base vierge. Une revue hostile des droits et un diff structurel restent requis. Les 3 archives et l'assemblage des 6 segments ne sont pas des fichiers autonomes exécutables tels quels sans revue. `public.schema_migrations` est vide : **ne pas la remplir à partir d'une simple similarité de nom** ; déterminer d'abord sa fonction et son contrat avec le code.

**Dernier contrôle CI connu avant le présent audit :** `main` commit `638e259`, workflow de réconciliation run `42064409724`, conclusion `success`. Le scanner de taux figés y est non bloquant ; pas de certification fiscale implicite.

**Prochaines actions :** comparer le schéma réel aux migrations et inventorier les droits ; vérifier la CI du commit courant ; traiter les branches divergentes sans réintroduire d'anciennes protections. Supprimer uniquement les branches fusionnées, selon la consigne utilisateur, quand un outil de suppression autorisé sera disponible.
