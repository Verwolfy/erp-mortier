"""ERP-061 — Régressions de recette transverse Achats/Finance/Documents.

La vérification SQL transactionnelle sur Supabase principal est documentée
séparément ; ces tests locaux ne créent aucune commande ni aucun paiement.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_supplier_payment_sql_checks_client_specific_field_only_in_client_branch():
    source = (ROOT / "sql/006_atomic_finance.sql").read_text(encoding="utf-8")
    assert "IF v_doc_type='FactureClient' AND" not in source
    assert "IF v_doc_type='FactureClient' THEN" in source
    assert "IF v_invoice_applied IS DISTINCT FROM coalesce(v_invoice.montant_paye,0) THEN" in source
    assert "THEN 'PAYEE' ELSE 'PARTIELLE' END" in source


def test_supplier_draft_is_blocked_in_source_sql_and_prepared_migration():
    source = (ROOT / "sql/006_atomic_finance.sql").read_text(encoding="utf-8")
    migration = (ROOT / "sql/ERP_061_PREPARATION_lettrage_fournisseur_20261123.sql").read_text(
        encoding="utf-8"
    )
    assert "NOT IN ('NON_PAYEE','PARTIELLE')" in source
    assert "NOT IN (''NON_PAYEE'',''PARTIELLE'')" in migration
    assert "Version SQL Finance inconnue : patch refusé" in migration
    assert "REVOKE ALL ON FUNCTION public.erp_finance_transaction" in migration
    assert "GRANT EXECUTE ON FUNCTION public.erp_finance_transaction" in migration
    assert "COMMIT;" in migration  # source only; not applied without approval


def test_purchase_order_pdf_still_marked_copy_and_not_emitted():
    source = (ROOT / "modules/documents/erp_print.py").read_text(encoding="utf-8")
    assert '"Commande fournisseur": ("commandes_achats"' in source
    assert "COPIE DE CONSULTATION - NON SIGNÉE / NON ÉMISE" in source
    assert 'def render_operation_pdf(snapshot: dict) -> bytes:' in source


def test_purchase_service_never_treats_order_as_receipt_or_payment():
    source = (ROOT / "modules/achats/service.py").read_text(encoding="utf-8")
    assert '"erp_create_purchase_order"' in source
    assert '"erp_receive_purchase_order"' in source
    assert '"erp_finance_transaction"' not in source
