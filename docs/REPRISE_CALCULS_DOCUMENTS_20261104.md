# Reprise NEXTGEN — calculs de brouillons financiers (4 novembre 2026)

## Décisions confirmées
- Conserver projet Supabase TEST en pause ; production inchangée.
- GitHub `Verwolfy/erp-mortier` branche `main`.
- Entête et pied de page en images, logo NEXTGEN, 20 modèles administratifs.
- Saisie de lignes via formulaires Streamlit (sans `st.data_editor`).
- Documents administratifs encore **BROUILLON - NON VALABLE / NON EMIS**.

## Réalisé dans cette intervention
- Nouveau `modules/documents/calculations.py` : calcul précis Decimal pour quantités × prix, somme HT, TTC uniquement quand taxes saisies. Accepte une virgule décimale simple ; refuse montants négatifs, NaN, infini et valeurs hors limites ; ne modifie pas les données d'entrée.
- `modules/documents/views.py` : montants de ligne dérivés et non saisissables, total HT automatiquement calculé, taxe renseignée explicitement sans taux implicite, TTC calculé si montant de taxes validé ; export suspendu en cas d'erreur de saisie.
- `tests/test_documents_nextgen.py` : scénario 10 × 300 + 2 × 100000 = 203000 HT ; taxe saisie 2000 -> 205000 TTC ; erreurs et cas sans taxes.
- Commits : `7ea8a986`, `11647e8a`, `ed59eb5c`.

## Contraintes et suites
- Aucune règle fiscale/TVA introduite ; ne pas émettre de facture officielle ou mettre en base une transaction de test.
- Attendre le verdict CI du commit `ed59eb5c`, workflows `41814719122` (tests) et `41814719144` (audit).
- Contrôle visuel à effectuer dans Streamlit : deux lignes produits, calcul instantané HT, taxes saisies seulement si connues, export PDF/DOCX, non-régression logo/QR/signatures.
- Prévoir ultérieurement le raccordement aux référentiels clients, SKU et tarifs validés, un registre QR sécurisé dans Supabase et une procédure d'homologation.
