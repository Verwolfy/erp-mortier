"""ERP-063 : visa BC préparé, jamais une émission ni un paiement."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_internal_visa_migration_keeps_public_roles_denied():
    source = (ROOT / "sql/ERP_063_PREPARATION_visa_bc_20261123.sql"
              ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "SECURITY INVOKER" in source
    assert "FROM PUBLIC,anon,authenticated" in source
    assert "TO service_role" in source
    assert "v_visa.preparateur_id=p_acteur_id" in source
    assert "v_visa.empreinte_source IS DISTINCT FROM v_hash" in source
    assert "v_da.approbateur_id=v_da.demandeur_id" in source
    assert "VISÉ" not in source  # statut technique sans signature électronique
    assert "'signature_effectuee',false" in source
    assert "'transmission_fournisseur_effectuee',false" in source
    assert "'paiement_autorise',false" in source
    assert "public.erp_finance_transaction(" not in source
    assert "public.erp_apply_stock_movement(" not in source


def test_visa_is_linked_to_approved_da_and_frozen_po():
    code = (ROOT / "sql/ERP_063_PREPARATION_visa_bc_20261123.sql"
            ).read_text(encoding="utf-8")
    assert "REFERENCES public.erp_purchase_requests(demande_id)" in code
    assert "v_da.approbateur_id IS NULL" in code
    assert "v_po.statut<>'EN_ATTENTE'" in code
    assert "Visa rétrospectif interdit après réception" in code
    assert "resultat=v_result" in code
    assert "v_operation.payload IS DISTINCT FROM p_payload" in code


def test_supplier_pdf_is_copy_and_never_sent_automatically():
    view = (ROOT / "modules/achats/three_way_views.py").read_text(encoding="utf-8")
    assert "load_operation_snapshot(" in view
    assert '"Commande fournisseur"' in view
    assert 'render_operation_pdf(snapshot)' in view
    assert "NON ÉMISE" in view
    assert "st.download_button(" in view
    assert "send_mail" not in view
    assert "transmettre_au_fournisseur" not in view
