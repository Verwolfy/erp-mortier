# Diagnostic Streamlit : PDF FAC-2026-000001 non actualisé (26/11/2026)

**Statut : non résolu — déploiement Streamlit à contrôler, code source GitHub conforme.**

## Preuves
- GitHub `main` contient PR #94 fusionnée (`280f9e7087e16f0e0d8d241f03decc7f6b74fd1a`), suivie de `119ef992a4a3ee971368cd05efa6be82f58c1d26` (état constaté à la revue). Suites CI de PR et de main réussies, **3556 tests** dans chaque pipeline.
- PDF fourni `NEXTGEN_Copie_FAC-2026-000001_2026-11-26 (5).pdf`, daté dans les métadonnées **2026-11-26 14:59:18 UTC**. PDF précédent `(3)` : **12:33:08 UTC**.
- Les deux PDF, bien que binaires différents, ont **exactement le même flux graphique de page** (SHA-256 `065c01b6dd084d516f6d0506c3efb937c752a0124d5e2405fe2c17f693edb46a`). Ils montrent toujours `NEXTGEN - ÉMETTEUR`, `Nom / raison sociale`, `AI (article d'imposition)`, `Non renseigné`, `TVA enregistrée (non homologuée)`, sans QR ni TTC en lettres. **Un nouveau PDF a été généré avec une ancienne version du générateur**.
- `main/modules/documents/erp_print.py` appelle bien le nouveau code et ne produit plus ces libellés. L'ERP Streamlit dispose déjà dans `app.py` d'un témoin **barre latérale → Version ERP : <SHA>**, issu de `core/release_provenance.py`.

## Prochain diagnostic
1. **Lire le SHA réellement visible dans la barre latérale de l'application authentifiée**. Il doit être `280f9e7…` ou ultérieur, idéalement `119ef992…` ou tout nouveau commit main ayant conservé le correctif. Le SHA de la CI GitHub **ne prouve pas** le SHA de l'instance Streamlit.
2. Vérifier dans Streamlit Community Cloud les coordonnées du déploiement : `Verwolfy/erp-mortier`, branche `main`, fichier `app.py`. Le compte de Streamlit Cloud n'est pas exposé par les connecteurs directs disponibles dans cette conversation ; **TinyFish non utilisé**.
3. Si branche et dépôt corrects mais le SHA est ancien, **redémarrer (Reboot)** l'application depuis Streamlit Cloud en sachant que cela interrompt les sessions connectées ; ne pas prétendre qu'un redémarrage a eu lieu tant que non confirmé.
4. Régénérer `FAC-2026-000001`, vérifier QR, libellés, format DZD, montant en lettres et pagination. Si SHA moderne et rendu ancien, rechercher mauvais import / ancienne version du processus dans les logs, sans imprimer de secrets.
5. Ne pas créer de commits vides, ne pas modifier Supabase ou RLS pour ce diagnostic.

Règle : **ne pas déclarer la recette Streamlit validée** avant inspection d'un PDF régénéré réellement conforme.

## Continuité
- `docs/ERP_064_HARMONISATION_DOCUMENTS_20261126.md` : corrections et preuves CI.
- `docs/ETAT_AVANCEMENT.md` : suivi central.
- Sauvegarde externe R2/B2 : **toujours en pause** jusqu'à fin des tests ERP et accord ultérieur.

Documentation Streamlit : https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/reboot-your-app
