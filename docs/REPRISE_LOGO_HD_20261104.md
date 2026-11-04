# NEXTGEN — Reprise branding logo HD — 4 novembre 2026

## Objectif et décision
Remplacer le petit logo flou dans les documents NEXTGEN par le JPEG haute définition fourni par l'utilisateur, de manière persistante sur GitHub `main`, sans modification Supabase.

## Preuves et fichiers
- Original fourni : `Logo NG.jpeg`, 2048 × 868 pixels, 148 445 octets.
- Objet Git du fichier **identique octet pour octet** : SHA `d36d6e451635faad641cdb2a6e6d7713657066fa`, confirmé par `git hash-object` du fichier d'origine local.
- Nouveau fichier dans le dépôt : `assets/nextgen_logo_hd.jpg`.
- `modules/documents/views.py` : le fichier HD est maintenant choisi par défaut pour les brouillons PDF et DOCX. Un upload HD temporaire reste possible depuis Streamlit (session seulement, aucune écriture SQL/Storage).
- `modules/documents/branding_images.py` : découpe uniquement le slogan de bandeau du bas et garde intégralement le mot-symbole NEXTGEN / BUILDING SOLUTIONS. Recadrage 0.84 de la hauteur source, suppression des marges blanches et réduction proportionnelle sans réagrandissement destructeur.
- `tests/test_documents_nextgen.py` : image source JPEG vérifiée, génération PDF/DOCX, fonctions d'images. Le littéral de la signature PNG a été corrigé après échec CI dû au test lui-même.
- Prévisualisation locale : `/mnt/data/NEXTGEN_entete_HD_corrige.png`, vérifiée visuellement avec l'intégralité du wordmark.
- Commits principaux du lot : `6e2727f` (asset), `269ab76` (usage par défaut), `7fa2026` (recadrage), `86f8e05` (signature de test).
- Aucun changement Supabase ; la base TEST demeure en pause.

## Contrôles et prochaines actions
- Vérifier le verdict final des GitHub Actions après le dernier commit documentaire.
- Sur Streamlit : Administration → Documents NEXTGEN → Générer Devis et Facture, contrôler le logo net, l'en-tête, le pied, le QR et la pagination.
- Conserver tous les exports en BROUILLON - NON VALABLE / NON EMIS. Aucun taux fiscal implicite ni émission de pièces.
- Maintenir le compte administrateur avec un mot de passe fort ; ne pas partager de secrets.

