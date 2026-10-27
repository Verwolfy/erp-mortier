"""Tests offline 010-A-02D-01 : aucun accès réseau ni Supabase nécessaire."""
from pathlib import Path
import ast
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

class SecurityMigrationStaticTests(unittest.TestCase):
    def test_python_syntax(self):
        for name in ("core/db_service.py", "core/security_service.py",
                     "modules/admin/service.py", "modules/admin/views.py", "app.py",
                     "modules/help/views.py"):
            ast.parse(source(name), filename=name)

    def test_sql_transaction(self):
        sql = source("sql/010A_02D_01_security_rpc_TEST.sql")
        self.assertRegex(sql, r"(?m)^BEGIN;")
        self.assertRegex(sql, r"(?m)^COMMIT;")
        self.assertEqual(sql.count("CREATE OR REPLACE FUNCTION public.erp_security_"), 3)

    def test_no_client_grants(self):
        sql = source("sql/010A_02D_01_security_rpc_TEST.sql")
        self.assertNotRegex(sql, r"(?i)GRANT\s+(ALL|INSERT|SELECT|UPDATE|DELETE)\b")
        self.assertNotRegex(sql, r"(?i)GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+[^;]+\s+TO\s+(anon|authenticated)")
        self.assertIn("REVOKE ALL PRIVILEGES", sql)

    def test_no_sensitive_generic_inserts(self):
        src = source("core/db_service.py")
        self.assertIn('if table_name in {"users", "permissions"}', src)
        insert_set = src.split("_HYBRID_INSERT_TABLES = frozenset({", 1)[1].split("})", 1)[0]
        self.assertNotIn('"users"', insert_set)
        self.assertNotIn('"permissions"', insert_set)

    def test_sql_audit_atomic(self):
        sql = source("sql/010A_02D_01_security_rpc_TEST.sql")
        self.assertGreaterEqual(sql.count("INSERT INTO public.audit_trail"), 2)
        self.assertGreaterEqual(sql.count("INSERT INTO public.erp_security_operations"), 2)
        self.assertIn("SECURITY DEFINER", sql)
        self.assertIn("SET search_path = pg_catalog, pg_temp", sql)

    def test_manager_checked_in_services(self):
        src = source("modules/admin/service.py")
        self.assertIn("require_security_manager()", src)
        self.assertNotIn('insert_hybrid("users"', src)
        self.assertNotIn('insert_hybrid("permissions"', src)

    def test_manager_checked_in_ui(self):
        src = source("modules/admin/views.py")
        self.assertIn("if not is_security_manager()", src)
        self.assertIn("STANDARD_ROLES", src)
        self.assertIn("STANDARD_MODULES", src)
        self.assertNotIn('st.text_input("Rôle (ex: ADMIN', src)

    def test_menu_not_admin_bypass(self):
        src = source("app.py")
        self.assertIn("if is_security_manager():", src)
        self.assertNotIn('if name == "Administration" and has_permission', src)

    def test_management_no_shared_cache(self):
        src = source("core/security_service.py")
        self.assertNotIn("@st.cache_data", src)
        self.assertNotIn("@st.cache_resource", src)
        self.assertIn("st.session_state", src)

    def test_docs_updated(self):
        for file in ("docs/guide_utilisateur.md", "modules/help/views.py"):
            self.assertIn("SECURITY_MANAGER", source(file))

    def test_no_prod_ref(self):
        sql = source("sql/010A_02D_01_security_rpc_TEST.sql")
        self.assertIn("ffuhbmcfyexsbjwhryvj", sql)
        self.assertNotIn("wenydirqtmkywbxbxfal", sql)

if __name__ == "__main__":
    unittest.main(verbosity=2)
