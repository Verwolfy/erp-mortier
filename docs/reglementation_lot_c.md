# Lot C — Registre fiscal algérien et facturation paramétrée

**État : PR #2 en brouillon, non fusionnée, aucune migration appliquée sur Supabase.**

## Réalisé sur la branche
- `core/reglementation.py` : recherche d'un paramètre confirmé par code et date.
- `core/baremes.py` : tranches marginales progressives versionnées, aucune table IRG réelle.
- `core/fiscalite_facturation.py` : calcul TVA et timbre sur un montant HT standard avec trace des taux et plafonds, sans taux en dur ; limites : factures à taux réduit, exonération, multi-taux.
- `core/fiscalite_service.py` : lecture Supabase du registre avec contrôle du compte exact, refus des lectures incomplètes ou non confirmées.
- `modules/ventes/service.py` et `views.py` : prévisualisation et brouillon reliés au lecteur de paramètres. La date réelle du brouillon est transmise à SQL. **Un registre vide provoquera le refus de créer une facture, et non le recours aux anciens taux.**
- `sql/012_reglementation_registre.sql` : schéma des règles et paramètres datés. Nouveau RLS/GRANT non appliqué.
- `sql/013_facturation_parametree.sql` : remplace la RPC 005 par une version qui prend TVA/timbre depuis le registre, conserve l'historique des pièces et refuse un avoir au taux historique différent. **À tester sur TEST avant toute mise en service.**
- `A_VALIDER.md` : restrictions et points juridiques à valider.

## Vérifications
- 26 tests locaux exécutés avec succès sur les nouveaux calculateurs et la lecture simulée (pytest).
- CI GitHub (workflow `.github/workflows/lot_c_tests.yml`) : compilation + tests ciblés + suite ERP ; consulter le dernier run pour le statut à jour.
- Les tests statiques SQL ne remplacent ni un `psql` de test ni un scénario transactionnel bout en bout.
- Aucun taux fiscal algérien chargé ou appliqué dans Supabase.

## Risques et blocages avant fusion
1. Sources officielles et validation des taux/plafonds applicables par date et régime fiscal.
2. Une facture avec TVA réduite, mixte ou exonérée n'est pas encore prise en charge : bloquer ou différencier selon classification SKU et client.
3. Pour les marchandises, la date du fait générateur peut être la livraison, pas la date de facture : établir le lien réel avant conformité.
4. Appliquer 012 puis 013 sur Supabase TEST **uniquement après autorisation de la modification des droits** ; vérifier service_role, RLS et concurrence.
5. Suite complète verte, tests SQL et vérifications de production et de sauvegardes avant merge. Préserver les trois fichiers locaux modifiés : `README.md`, `modules/help/views.py` et `scripts/sauvegarder_google_sheets.py`.
6. Les paramètres en vigueur ne doivent jamais être créés automatiquement avec des valeurs fictives.

## Source primaire identifiée
DGI Algérie, « La taxe sur la valeur ajoutée », mise à jour du 23 février 2026 : https://www.mfdgi.gov.dz/fr/professionnels/services-pro/regime-reel/la-taxe-sur-la-valeur-ajoutee.
Ce document officiel décrit le taux normal et le taux réduit, ainsi que des faits générateurs distincts selon l'opération. Vérifier aussi le texte légal et l'assujettissement effectif avant toute activation.
