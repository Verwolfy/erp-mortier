"""Contractualise les signatures des RPC utilisées par les modules métier.

Tests statiques sans secrets, sans client Supabase, sans écriture de production.
Les signatures SQL de référence sont vérifiées séparément par l'audit SQL.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "achats": {
        "erp_create_purchase_order": {
            "p_operation_id", "p_order_id", "p_fournisseur_id", "p_type_achat",
            "p_devise", "p_taux_change", "p_mode_paiement", "p_delai_paiement",
            "p_date_voulue", "p_lines",
        },
        "erp_receive_purchase_order": {
            "p_operation_id", "p_br_id", "p_commande_achat_id",
            "p_date_reception", "p_controle_conformite", "p_remarques",
            "p_date_peremption", "p_lines",
        },
    },
    "production": {
        "erp_create_recipe": {
            "p_operation_id", "p_pf_id", "p_version", "p_rendement_unite",
            "p_instructions", "p_date_effet", "p_lignes",
        },
        "erp_create_manufacturing_order": {
            "p_operation_id", "p_pf_id", "p_recette_id", "p_sku_id",
            "p_quantite_prevue", "p_date_planification", "p_notes",
        },
        "erp_start_manufacturing_order": {"p_of_id"},
        "erp_close_manufacturing_order": {
            "p_of_id", "p_conforme", "p_remarques", "p_controleur",
            "p_quantite_produite", "p_emballage_mp_id",
            "p_emballage_consomme",
        },
    },
    "ventes": {
        "erp_create_sales_order": {
            "p_operation_id", "p_client_id", "p_date", "p_lignes",
        },
        "erp_sale_transaction": {
            "p_action", "p_operation_id", "p_payload",
        },
    },
    "finance": {
        "erp_finance_transaction": {
            "p_action", "p_operation_id", "p_payload",
        },
    },
}


def _dictionary_keys(expression):
    assert isinstance(expression, ast.Dict), "Le payload RPC doit être un dictionnaire"
    keys = []
    for key in expression.keys:
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        keys.append(key.value)
    assert len(keys) == len(set(keys))
    return set(keys)


def _payload_for_call(fn, call):
    assert len(call.args) >= 2
    payload = call.args[1]
    if isinstance(payload, ast.Dict):
        return _dictionary_keys(payload)
    assert isinstance(payload, ast.Name)
    assignments = [node.value for node in ast.walk(fn)
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == payload.id
                           for target in node.targets)]
    assert len(assignments) == 1, "Payload RPC ambigu"
    return _dictionary_keys(assignments[0])


def test_python_rpc_names_and_payload_keys_match_database_contract():
    for module, expected in EXPECTED.items():
        path = ROOT / "modules" / module / "service.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = {}
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call) or not call.args:
                    continue
                callee = call.func
                name = (callee.attr if isinstance(callee, ast.Attribute)
                        else callee.id if isinstance(callee, ast.Name) else None)
                if name not in {"rpc", "_rpc", "_create_rpc"}:
                    continue
                rpc = call.args[0]
                if not isinstance(rpc, ast.Constant) or rpc.value not in expected:
                    continue
                assert rpc.value not in found, "Appel RPC ambigu"
                found[rpc.value] = _payload_for_call(fn, call)
        assert found == expected, f"Contrat Python RPC divergent : {module}"


def test_sql_security_audit_contains_all_nine_rpcs_and_is_read_only():
    audit = (ROOT / "sql" / "demo" /
             "20261105_audit_9_rpc_transactions_LECTURE_SEULE.sql"
            ).read_text(encoding="utf-8")
    expected = {rpc for module in EXPECTED.values() for rpc in module}
    assert len(expected) == 9
    for rpc in expected:
        assert audit.count("'" + rpc + "'") >= 1
    assert "search_path=pg_catalog, pg_temp" in audit
    assert "search_path=pg_catalog, public" in audit
    assert "has_function_privilege('anon'" in audit
    assert "has_function_privilege('authenticated'" in audit
    import re
    assert not re.search(r"(?im)^\s*(DELETE|UPDATE|INSERT|ALTER|DROP|TRUNCATE|CALL|DO)\s+", audit)
