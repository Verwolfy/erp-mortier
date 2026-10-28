"""Le scanner doit détecter un taux figé et accepter une lecture en base."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "auditer_parametres_reglementaires.py"
spec = importlib.util.spec_from_file_location("erp_regulatory_scan", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

def test_detection_constantes_python(tmp_path):
    write(tmp_path, "modules/ventes/service.py",
          "TAUX_TVA = Decimal('0.19')\nMAX_TIMBRE = Decimal('2500')\n")
    result = mod.audit(tmp_path)
    assert [r["rule"] for r in result] == ["constante_tva_timbre"] * 2

def test_detection_regle_sql(tmp_path):
    write(tmp_path, "sql/005.sql", """v_tax := round(v_net_ht * 0.19,2);
THEN least(round((v_net_ht+v_tax)*0.01,2),2500);
VALUES(v_invoice_id,NULL,p_client,v_now,v_net_ht,0.19, v_tax);
""")
    assert {r["rule"] for r in mod.audit(tmp_path)} == {
        "calcul_tva_sql", "timbre_sql", "taux_facture_sql"
    }

def test_exclusion_des_tests_docs_et_commentaires(tmp_path):
    write(tmp_path, "tests/example.py", "TAUX_TVA = Decimal('0.19')")
    write(tmp_path, "docs/ancien.sql", "v_tax := round(v_net_ht * 0.19,2);")
    write(tmp_path, "core/notes.py", "# TAUX_TVA = Decimal('0.19')")
    assert mod.audit(tmp_path) == []

def test_accepte_un_parametre_dynamique(tmp_path):
    write(tmp_path, "modules/ventes/service.py",
          "taxe = montant_ht * get_param('TVA_TAUX_NORMAL', date_operation)")
    write(tmp_path, "sql/013.sql",
          "v_tax := round(v_net_ht * public.get_param('TVA', v_date),2);")
    assert mod.audit(tmp_path) == []

def test_trace_ligne_et_fichier(tmp_path):
    write(tmp_path, "core/testme.py", "x = 1\nTAUX_TIMBRE = Decimal('0.01')\n")
    assert mod.audit(tmp_path) == [
        {"path": "core/testme.py", "line": 2, "rule": "constante_tva_timbre"}
    ]
