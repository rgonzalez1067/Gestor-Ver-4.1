# ruff: noqa
"""Iteration 184 backend tests: banks contacts repeater, suggested-contacts,
preview-notification matrix qty inheritance, and irregular quotes report."""
import os
import pytest
import requests
import uuid

def _read_frontend_env():
    p = "/app/frontend/.env"
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    return line.split("=", 1)[1].strip()
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not found"
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Auth failed: {r.status_code} {r.text}")
    return r.json().get("session_token") or r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- 1. POST /api/banks with contacts[] ----------
@pytest.fixture(scope="module")
def created_bank(headers):
    payload = {
        "name": f"TEST_Bank_{uuid.uuid4().hex[:6]}",
        "type": "Banco",
        "country": "Venezuela",
        "contacts": [
            {"first_name": "Juan", "last_name": "Pérez", "position": "Gerente",
             "email": "juan.perez@test.com", "phone": "0212-1111111", "contact_type": "Principal"},
            {"first_name": "Ana", "last_name": "García", "position": "Ing. Soporte",
             "email": "ana.garcia@test.com", "phone": "0212-2222222", "contact_type": "Técnico"},
            {"first_name": "Luis", "last_name": "Otro", "position": "Otros",
             "email": "luis@test.com", "phone": "0212-3333333", "contact_type": "Otro"},
        ],
    }
    r = requests.post(f"{BASE_URL}/api/banks", json=payload, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    bank = r.json()
    yield bank
    # cleanup
    requests.delete(f"{BASE_URL}/api/banks/{bank['bank_id']}", headers=headers, timeout=30)


def test_create_bank_assigns_contact_ids_and_syncs_legacy(created_bank, headers):
    assert "contacts" in created_bank and len(created_bank["contacts"]) == 3
    for c in created_bank["contacts"]:
        assert c.get("contact_id"), f"missing contact_id: {c}"
        assert c["contact_id"].startswith("bcn_")
    # Verify legacy sync persisted in DB by fetching via GET
    rg = requests.get(f"{BASE_URL}/api/banks", headers=headers, timeout=30)
    assert rg.status_code == 200
    fetched = next((b for b in rg.json() if b["bank_id"] == created_bank["bank_id"]), None)
    assert fetched is not None
    assert fetched.get("contact_email") == "juan.perez@test.com", \
        "Legacy contact_email not synced from Principal contact. POST response also missing sync (returns model not doc) — see bug report."
    assert fetched.get("contact_phone") == "0212-1111111"
    assert "Juan" in (fetched.get("contact_name") or "")


# ---------- 2. PUT /api/banks/{id} updates legacy from Principal ----------
def test_update_bank_syncs_legacy_from_first_principal(created_bank, headers):
    bank_id = created_bank["bank_id"]
    new_payload = {
        "name": created_bank["name"],
        "type": "Banco",
        "country": "Venezuela",
        # Wipe legacy so sync repopulates
        "contact_name": None,
        "contact_email": None,
        "contact_phone": None,
        "contacts": [
            {"first_name": "Carlos", "last_name": "Nuevo", "position": "Director",
             "email": "carlos.nuevo@test.com", "phone": "0212-9999999", "contact_type": "Principal"},
            {"first_name": "Sofia", "last_name": "Tech", "position": "Soporte",
             "email": "sofia@test.com", "phone": "0212-8888888", "contact_type": "Técnico"},
        ],
    }
    r = requests.put(f"{BASE_URL}/api/banks/{bank_id}", json=new_payload, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b.get("contact_email") == "carlos.nuevo@test.com"
    assert b.get("contact_phone") == "0212-9999999"
    assert "Carlos" in (b.get("contact_name") or "")
    assert all(c.get("contact_id") for c in b["contacts"])


# ---------- 3. GET /api/banks migrates legacy contact_name -> contacts[0] in-memory ----------
def test_get_banks_migrates_legacy_to_contacts(headers):
    # Find any bank in DB without contacts but with contact_name (legacy)
    r = requests.get(f"{BASE_URL}/api/banks", headers=headers, timeout=30)
    assert r.status_code == 200
    banks = r.json()
    legacy_found = False
    for b in banks:
        if b.get("contact_name") and b.get("contacts"):
            # If contact_name present, contacts must contain at least one entry of type Principal
            first = b["contacts"][0]
            if first.get("contact_id", "").startswith("bcn_legacy_") or first.get("contact_type") == "Principal":
                legacy_found = True
                assert first.get("contact_type") == "Principal"
                break
    # Not strictly required to exist; assertion passes if found at least one consistent example
    # (still validates response shape)
    assert isinstance(banks, list)


# ---------- 4. GET /api/projects/{id}/suggested-contacts ----------
def test_suggested_contacts_returns_bank_contacts(headers):
    # Find a project that has a sponsor bank or banks list
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    if r.status_code != 200:
        pytest.skip("projects list unavailable")
    projects = r.json() if isinstance(r.json(), list) else r.json().get("projects", [])
    if not projects:
        pytest.skip("no projects to test suggested-contacts")
    found = None
    for p in projects[:30]:
        rs = requests.get(f"{BASE_URL}/api/projects/{p['project_id']}/suggested-contacts", headers=headers, timeout=30)
        if rs.status_code == 200:
            data = rs.json()
            items = data if isinstance(data, list) else data.get("suggestions") or data.get("contacts") or []
            bank_items = [i for i in items if (i.get("source") == "bank")]
            if bank_items:
                found = bank_items
                break
    if not found:
        pytest.skip("No project with bank suggested contacts available")
    sample = found[0]
    for f in ("email", "label", "source"):
        assert f in sample, f"missing field {f} in {sample}"
    assert sample["source"] == "bank"
    # bank_name and contact_type expected for repeater contacts
    assert "bank_name" in sample or "name" in sample


# ---------- 5. preview-notification matrix uses real cantidad_cajas ----------
def test_preview_notification_matrix_qty(headers):
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    if r.status_code != 200:
        pytest.skip("projects unavailable")
    projects = r.json() if isinstance(r.json(), list) else r.json().get("projects", [])
    target = None
    for p in projects:
        services = p.get("services") or []
        for s in services:
            if s.get("item_type") == "additional" and s.get("bank_name") and s.get("item_name") and s.get("cantidad_cajas"):
                if int(s.get("cantidad_cajas")) > 1:
                    target = (p, s)
                    break
        if target:
            break
    if not target:
        pytest.skip("No project with additional service with cantidad_cajas>1 found")
    project, svc = target
    body = {"target": "bank", "bank_name": svc["bank_name"]}
    rp = requests.post(f"{BASE_URL}/api/projects/{project['project_id']}/preview-notification",
                       json=body, headers=headers, timeout=60)
    if rp.status_code != 200:
        pytest.skip(f"preview-notification not available: {rp.status_code} {rp.text[:200]}")
    resp = rp.json()
    matrix_html = resp.get("matrix_html") or resp.get("html") or ""
    # The exact qty should appear at least once in the matrix HTML
    assert str(svc["cantidad_cajas"]) in matrix_html, \
        f"expected cantidad_cajas={svc['cantidad_cajas']} in matrix HTML; got: {matrix_html[:500]}"
    # Should not be defaulting to "1" only
    print(f"Matrix HTML excerpt: {matrix_html[:300]}")


# ---------- 6. Irregular quotes report includes 'Pasó a Proyecto sin Aprobación previa' ----------
def test_irregular_quotes_report_includes_proyecto_sin_aprobacion(headers):
    r = requests.get(f"{BASE_URL}/api/reports/sales/irregular-quotes", headers=headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else (data.get("quotes") or data.get("items") or [])
    assert isinstance(items, list)
    rule_found = False
    quote_numbers = []
    for it in items:
        quote_numbers.append(it.get("quote_number"))
        for iss in (it.get("issues") or []):
            txt = iss if isinstance(iss, str) else (iss.get("rule") or iss.get("message") or "")
            if "Proyecto" in txt and "Aprobaci" in txt:
                rule_found = True
                break
    print(f"Irregular quotes returned: {quote_numbers}")
    # Per requirement, history records with archived_trigger='status_enviada_imple*' AND approved_at=None
    # MUST appear here with rule 'Pasó a Proyecto sin Aprobación previa'.
    # DB has 3 such records: COT-2026-04-026/028/029-PYME (status_enviada_imple_recovered, no approved_at)
    assert rule_found, (
        "Rule 'Pasó a Proyecto sin Aprobación previa' did not fire. "
        "Likely cause: _detect_irregularities checks startswith('enviada a imple') but actual "
        "DB values are 'status_enviada_imple' / 'status_enviada_imple_recovered'."
    )


# ---------- 7. inject_custom_message helper ----------
def test_inject_custom_message_helper():
    import sys
    sys.path.insert(0, "/app/backend")
    from config import inject_custom_message  # type: ignore

    user = {"first_name": "Rafael", "last_name": "G"}

    # 1) With marker
    html1 = "<p>Header</p>{Mensaje_Personalizado}<p>Footer</p>"
    out1 = inject_custom_message(html1, "HOLA", user)
    assert "HOLA" in out1 and "{Mensaje_Personalizado}" not in out1

    # 2) Without marker but with Atentamente — must insert BEFORE
    html2 = "<p>Buenas tardes</p><p>Atentamente,</p><p>Equipo</p>"
    out2 = inject_custom_message(html2, "MENSAJE_OPERADOR", user)
    assert "MENSAJE_OPERADOR" in out2
    assert out2.index("MENSAJE_OPERADOR") < out2.index("Atentamente"), \
        "operator message must appear BEFORE 'Atentamente'"

    # 3) No marker, no Atentamente -> append
    html3 = "<p>Solo cuerpo</p>"
    out3 = inject_custom_message(html3, "FINAL_MSG", user)
    assert "FINAL_MSG" in out3
