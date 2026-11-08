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


def test_aucune_nouvelle_constante_reglementaire():
    """Le passif historique reste visible ; toute nouvelle occurrence est bloquée.

    Ceci n'homologue pas les 6 écarts existants. Ils doivent disparaître
    après refonte et essais du calcul fiscal Python + RPC PostgreSQL.
    """
    from collections import Counter

    findings = mod.audit(Path(__file__).resolve().parents[1])
    actual = Counter((entry["path"], entry["rule"]) for entry in findings)
    legacy = Counter({
        ("modules/ventes/service.py", "constante_tva_timbre"): 3,
        ("sql/005_atomic_sales.sql", "calcul_tva_sql"): 1,
        ("sql/005_atomic_sales.sql", "timbre_sql"): 1,
        ("sql/005_atomic_sales.sql", "taux_facture_sql"): 1,
    })
    assert not (actual - legacy), (
        "Nouvelle constante fiscale détectée : "
        + repr(sorted((actual - legacy).items()))
    )


def test_preflight_tva_ne_fixe_plus_de_taux_numerique():
    path = Path(__file__).resolve().parents[1] / "core/preflight_reglementaire.py"
    code = path.read_text(encoding="utf-8")
    assert '0.19' not in code
    assert '0.09' not in code
    assert "chercher_parametre" in code
