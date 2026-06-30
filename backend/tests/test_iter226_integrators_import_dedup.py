"""
Iteration 226: Bug fix verification for POST /api/integrators/import dedup composite key.

Scenarios covered:
  1) PRUEBA DE FUEGO: same Nombre+Tipo but different Aplicativo and/or Modalidad ->
     all rows must be inserted as independent records.
  2) TRUE DUPLICATE: 100% identical rows across (Nombre, Tipo, Tipo de Integración,
     Aplicativo, Modalidad) -> only one inserted, the other reported as
     error_type='duplicate' (column 'Fila duplicada') and skipped.
  3) Regression: valid single-row import works; invalid Tipo/Modalidad still
     rejected; new Contacto Principal fields still imported.
  4) Counts integrity: total_processed == rows in file; success+updated+skipped
     covers all rows; error_count == len(errors).

Cleanup: all created integrators use prefix 'QATEST_DUP_' and are deleted at the
end via direct DB cleanup helper API (best-effort) or per-record DELETE.
"""

import io
import os
import csv
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for local runs (will still respect /api prefix routing)
    BASE_URL = "http://localhost:8001"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

PREFIX = "QATEST_DUP_"


# --- Fixtures -----------------------------------------------------------------

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("token")
    assert token, f"No session_token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# --- Helpers ------------------------------------------------------------------

CSV_HEADERS = [
    "Nombre", "Tipo", "Tipo Integración", "Aplicativo", "Modalidad",
    "Estatus", "Gestor", "Implementador", "Nro de Ticket",
    "Nombre del Contacto Principal", "Teléfono Contacto Principal",
    "Email Contacto Principal", "Negociación de Interfaz",
]


def _map_in(d):
    """Convert test row keys that use 'Tipo de Integración' to the actual header 'Tipo Integración'."""
    out = dict(d)
    if "Tipo de Integración" in out:
        out["Tipo Integración"] = out.pop("Tipo de Integración")
    return out


def make_csv(rows):
    """rows: list of dicts with at least Nombre, Tipo, Aplicativo, Modalidad."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADERS)
    writer.writeheader()
    for r in rows:
        full = {h: "" for h in CSV_HEADERS}
        full.update(_map_in(r))
        writer.writerow(full)
    return buf.getvalue().encode("utf-8")


def post_import(token, csv_bytes, filename="qa_dup.csv", mode="upsert"):
    files = {"file": (filename, csv_bytes, "text/csv")}
    data = {"mode": mode}
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(
        f"{BASE_URL}/api/integrators/import",
        headers=headers, files=files, data=data, timeout=120,
    )
    return r


def fetch_all_integrators(token, name_prefix=PREFIX):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/integrators", headers=headers, timeout=30)
    assert r.status_code == 200, f"GET /api/integrators failed: {r.status_code} {r.text}"
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("integrators", payload.get("items", []))
    return [i for i in items if (i.get("name") or "").startswith(name_prefix)]


def delete_integrator(token, integrator_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.delete(f"{BASE_URL}/api/integrators/{integrator_id}", headers=headers, timeout=30)
    return r


# --- Tests --------------------------------------------------------------------

class TestImportDedupCompositeKey:
    """Bug-fix scope: composite key now includes app_name + integration_modality.
    Plus in-file dedup keyed by all 5 critical columns."""

    def test_01_prueba_de_fuego_same_name_diff_app_or_modality(self, admin_token):
        """10 distinct rows where several share Nombre+Tipo but differ in
        Aplicativo and/or Modalidad. All 10 must be inserted."""
        run_id = uuid.uuid4().hex[:6]
        base_name_a = f"{PREFIX}A_{run_id}"
        base_name_b = f"{PREFIX}B_{run_id}"

        rows = [
            # 5 rows same name A, differing in Aplicativo/Modalidad
            {"Nombre": base_name_a, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "App1", "Modalidad": "REST"},
            {"Nombre": base_name_a, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "App2", "Modalidad": "REST"},
            {"Nombre": base_name_a, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "App1", "Modalidad": "MPOS"},
            {"Nombre": base_name_a, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "App3", "Modalidad": "Wrapper"},
            {"Nombre": base_name_a, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "App3", "Modalidad": "Stand Alone"},
            # 5 rows same name B, differing in Aplicativo/Modalidad
            {"Nombre": base_name_b, "Tipo": "Comercio", "Tipo de Integración": "CR", "Aplicativo": "Sys1", "Modalidad": "Bridge PG"},
            {"Nombre": base_name_b, "Tipo": "Comercio", "Tipo de Integración": "CR", "Aplicativo": "Sys2", "Modalidad": "Bridge PG"},
            {"Nombre": base_name_b, "Tipo": "Comercio", "Tipo de Integración": "CR", "Aplicativo": "Sys1", "Modalidad": "PG Universal"},
            {"Nombre": base_name_b, "Tipo": "Comercio", "Tipo de Integración": "LP", "Aplicativo": "Sys1", "Modalidad": "Bridge PG"},
            {"Nombre": base_name_b, "Tipo": "Comercio", "Tipo de Integración": "CR", "Aplicativo": "Sys3", "Modalidad": "REST"},
        ]
        csv_bytes = make_csv(rows)
        r = post_import(admin_token, csv_bytes, filename=f"prueba_fuego_{run_id}.csv")
        assert r.status_code == 200, f"Import HTTP failed: {r.status_code} {r.text}"
        body = r.json()
        print(f"PRUEBA DE FUEGO result: status={body.get('status')} success={body.get('success_count')} updated={body.get('updated_count')} skipped={body.get('skipped_count')} errors={body.get('error_count')} total={body.get('total_processed')}")

        assert body.get("status") in ("success", "partial"), f"Unexpected status: {body.get('status')}"
        assert body.get("total_processed") == 10, f"total_processed expected 10, got {body.get('total_processed')}"
        # All 10 must be created (not updated, not skipped): no pre-existing records
        assert body.get("success_count") == 10, (
            f"success_count expected 10, got {body.get('success_count')}; "
            f"updated={body.get('updated_count')} skipped={body.get('skipped_count')} errors={body.get('errors')}"
        )
        assert body.get("skipped_count", 0) == 0
        # Counts integrity
        assert body.get("error_count") == len(body.get("errors", []))

        # Verify DB persistence via GET
        all_qa = fetch_all_integrators(admin_token)
        a_records = [i for i in all_qa if i.get("name") == base_name_a]
        b_records = [i for i in all_qa if i.get("name") == base_name_b]
        assert len(a_records) == 5, f"Expected 5 records for {base_name_a}, found {len(a_records)}"
        assert len(b_records) == 5, f"Expected 5 records for {base_name_b}, found {len(b_records)}"

        # Verify each distinct (app_name, integration_modality) combination exists for A
        a_combos = {(i.get("app_name"), i.get("integration_modality")) for i in a_records}
        expected_a = {("App1", "REST"), ("App2", "REST"), ("App1", "MPOS"), ("App3", "Wrapper"), ("App3", "Stand Alone")}
        assert a_combos == expected_a, f"A combos mismatch: got {a_combos}, expected {expected_a}"

        # And for B: distinct on (app, modality, integration_type)
        b_combos = {(i.get("app_name"), i.get("integration_modality"), i.get("integration_type")) for i in b_records}
        expected_b = {
            ("Sys1", "Bridge PG", "CR"),
            ("Sys2", "Bridge PG", "CR"),
            ("Sys1", "PG Universal", "CR"),
            ("Sys1", "Bridge PG", "LP"),
            ("Sys3", "REST", "CR"),
        }
        assert b_combos == expected_b, f"B combos mismatch: got {b_combos}, expected {expected_b}"

    def test_02_true_duplicate_only_one_inserted(self, admin_token):
        """Two rows 100% identical -> one inserted, the other reported as
        duplicate with column 'Fila duplicada' and counted in skipped_count.
        Import must NOT hard-fail."""
        run_id = uuid.uuid4().hex[:6]
        nombre = f"{PREFIX}TRUE_{run_id}"

        rows = [
            {"Nombre": nombre, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "DupApp", "Modalidad": "REST"},
            {"Nombre": nombre, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "DupApp", "Modalidad": "REST"},  # 100% idéntica
            {"Nombre": nombre, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "OtherApp", "Modalidad": "REST"},  # distinta -> debe insertarse
        ]
        csv_bytes = make_csv(rows)
        r = post_import(admin_token, csv_bytes, filename=f"true_dup_{run_id}.csv")
        assert r.status_code == 200, f"HTTP failed: {r.status_code} {r.text}"
        body = r.json()
        print(f"TRUE DUPLICATE result: status={body.get('status')} success={body.get('success_count')} skipped={body.get('skipped_count')} errors_count={body.get('error_count')}")

        assert body.get("status") in ("success", "partial")
        assert body.get("total_processed") == 3
        assert body.get("success_count") == 2, f"Expected 2 created, got {body.get('success_count')}"
        assert body.get("skipped_count") == 1, f"Expected 1 skipped, got {body.get('skipped_count')}"

        # Find duplicate error
        dup_errors = [e for e in body.get("errors", []) if e.get("error_type") == "duplicate"]
        assert len(dup_errors) >= 1, f"No duplicate error reported. errors={body.get('errors')}"
        dup = dup_errors[0]
        assert "duplicada" in (dup.get("column", "").lower()) or "duplicada" in (dup.get("message", "").lower()), \
            f"Duplicate error missing 'Fila duplicada' marker: {dup}"

        # Counts integrity
        assert body.get("error_count") == len(body.get("errors", []))
        # No hard-fail
        assert body.get("status") != "error"

        # Verify only 2 records persisted with this name
        records = [i for i in fetch_all_integrators(admin_token) if i.get("name") == nombre]
        assert len(records) == 2, f"Expected 2 persisted records for {nombre}, found {len(records)}"

    def test_03_regression_valid_single_row(self, admin_token):
        """A normal valid single row still creates and persists Contacto Principal fields."""
        run_id = uuid.uuid4().hex[:6]
        nombre = f"{PREFIX}REG_{run_id}"
        rows = [{
            "Nombre": nombre,
            "Tipo": "Integrador",
            "Tipo de Integración": "PG",
            "Aplicativo": "RegApp",
            "Modalidad": "REST",
            "Nombre del Contacto Principal": "Juan Perez",
            "Teléfono Contacto Principal": "+58-212-1234567",
            "Email Contacto Principal": "juan.perez@example.com",
            "Negociación de Interfaz": "Sí",
        }]
        csv_bytes = make_csv(rows)
        r = post_import(admin_token, csv_bytes, filename=f"reg_valid_{run_id}.csv")
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        body = r.json()
        print(f"REGRESSION valid result: {body.get('status')} success={body.get('success_count')} errors={body.get('error_count')}")
        assert body.get("success_count") == 1, f"Expected 1 created, got {body.get('success_count')}; errors={body.get('errors')}"
        assert body.get("error_count") == 0

        records = [i for i in fetch_all_integrators(admin_token) if i.get("name") == nombre]
        assert len(records) == 1
        rec = records[0]
        assert rec.get("principal_contact_name") == "Juan Perez"
        assert rec.get("principal_contact_email") == "juan.perez@example.com"
        assert rec.get("principal_contact_phone") and "1234567" in rec.get("principal_contact_phone")
        assert rec.get("interface_negotiation") == "Sí"

    def test_04_regression_invalid_modality_rejected(self, admin_token):
        """An invalid Modalidad is still rejected as before (not silently passed)."""
        run_id = uuid.uuid4().hex[:6]
        nombre = f"{PREFIX}INV_{run_id}"
        rows = [{
            "Nombre": nombre,
            "Tipo": "Integrador",
            "Tipo de Integración": "PG",
            "Aplicativo": "InvApp",
            "Modalidad": "InvalidModalityXYZ",  # invalid
        }]
        csv_bytes = make_csv(rows)
        r = post_import(admin_token, csv_bytes, filename=f"reg_inv_{run_id}.csv")
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        body = r.json()
        print(f"REGRESSION invalid modality: {body.get('status')} success={body.get('success_count')} errors={body.get('error_count')} skipped={body.get('skipped_count')}")
        assert body.get("success_count") == 0
        # Either skipped or counted under error_count; spec says blocking error
        assert body.get("error_count") >= 1
        modality_errors = [e for e in body.get("errors", []) if "modalidad" in (e.get("column", "").lower()) or "modalidad" in (e.get("message", "").lower())]
        assert modality_errors, f"Expected modality error, got {body.get('errors')}"

        # Verify NOT persisted
        records = [i for i in fetch_all_integrators(admin_token) if i.get("name") == nombre]
        assert len(records) == 0, f"Invalid row was wrongly persisted: {records}"

    def test_05_regression_invalid_principal_contact_email_rejected(self, admin_token):
        """Invalid Email Contacto Principal blocks the row (existing behavior)."""
        run_id = uuid.uuid4().hex[:6]
        nombre = f"{PREFIX}INVMAIL_{run_id}"
        rows = [{
            "Nombre": nombre,
            "Tipo": "Integrador",
            "Tipo de Integración": "PG",
            "Aplicativo": "MailApp",
            "Modalidad": "REST",
            "Email Contacto Principal": "not-an-email",
        }]
        csv_bytes = make_csv(rows)
        r = post_import(admin_token, csv_bytes, filename=f"reg_invmail_{run_id}.csv")
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        body = r.json()
        print(f"REGRESSION invalid email: success={body.get('success_count')} errors={body.get('error_count')}")
        # Either rejected with error OR accepted but should not crash. Per spec it must be rejected.
        if body.get("success_count") == 1:
            # If implementation didn't reject, surface as test failure for retest
            pytest.fail(f"Invalid principal_contact_email was silently accepted: errors={body.get('errors')}")
        else:
            assert body.get("error_count") >= 1
            records = [i for i in fetch_all_integrators(admin_token) if i.get("name") == nombre]
            assert len(records) == 0

    def test_06_counts_integrity_mixed_file(self, admin_token):
        """Mixed file: 3 distinct valid + 1 true-duplicate + 1 invalid modality.
        success+updated+skipped + (rows with blocking errors) == total_processed,
        and error_count == len(errors)."""
        run_id = uuid.uuid4().hex[:6]
        n1 = f"{PREFIX}MIX1_{run_id}"
        n2 = f"{PREFIX}MIX2_{run_id}"

        rows = [
            {"Nombre": n1, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "M1", "Modalidad": "REST"},
            {"Nombre": n1, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "M2", "Modalidad": "REST"},
            {"Nombre": n2, "Tipo": "Comercio", "Tipo de Integración": "CR", "Aplicativo": "M3", "Modalidad": "Bridge PG"},
            # 100% duplicate of row 1 -> skipped (duplicate)
            {"Nombre": n1, "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "M1", "Modalidad": "REST"},
            # invalid modality -> blocking error (skipped_count++ in current impl, but reported in errors)
            {"Nombre": f"{PREFIX}MIXBAD_{run_id}", "Tipo": "Integrador", "Tipo de Integración": "PG", "Aplicativo": "MX", "Modalidad": "Bogus"},
        ]
        csv_bytes = make_csv(rows)
        r = post_import(admin_token, csv_bytes, filename=f"mixed_{run_id}.csv")
        assert r.status_code == 200
        body = r.json()
        print(f"MIXED result: total={body.get('total_processed')} success={body.get('success_count')} updated={body.get('updated_count')} skipped={body.get('skipped_count')} error_count={body.get('error_count')} status={body.get('status')}")

        assert body.get("total_processed") == 5
        assert body.get("success_count") == 3
        # Both invalid + duplicate land in skipped_count per current impl
        assert body.get("skipped_count") >= 2, f"Expected at least 2 skipped, got {body.get('skipped_count')}"
        # error_count == len(errors)
        assert body.get("error_count") == len(body.get("errors", []))
        # Accounting (no row vanishes): success + updated + skipped == total_processed
        accounted = body.get("success_count", 0) + body.get("updated_count", 0) + body.get("skipped_count", 0)
        assert accounted == body.get("total_processed"), (
            f"Accounting mismatch: success({body.get('success_count')}) + updated({body.get('updated_count')}) "
            f"+ skipped({body.get('skipped_count')}) = {accounted}, expected {body.get('total_processed')}"
        )

        # Confirm duplicate error is present
        dup = [e for e in body.get("errors", []) if e.get("error_type") == "duplicate"]
        assert dup, f"Duplicate error expected in mixed file. errors={body.get('errors')}"


# --- Final cleanup (module-level) --------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _cleanup_after_tests(admin_token):
    """Delete all QATEST_DUP_ integrators after the module runs."""
    yield
    try:
        remaining = fetch_all_integrators(admin_token)
        print(f"\n[CLEANUP] Deleting {len(remaining)} QATEST_DUP_* integrators...")
        deleted = 0
        for i in remaining:
            iid = i.get("integrator_id") or i.get("id")
            if not iid:
                continue
            resp = delete_integrator(admin_token, iid)
            if resp.status_code in (200, 204):
                deleted += 1
            else:
                print(f"[CLEANUP] DELETE {iid} -> {resp.status_code} {resp.text[:120]}")
        # Verify
        post_cleanup = fetch_all_integrators(admin_token)
        print(f"[CLEANUP] Deleted {deleted}; remaining QATEST_DUP_ = {len(post_cleanup)}")
        assert len(post_cleanup) == 0, f"Cleanup incomplete, {len(post_cleanup)} QATEST_DUP_ left"
    except Exception as e:
        print(f"[CLEANUP] Error: {e}")
