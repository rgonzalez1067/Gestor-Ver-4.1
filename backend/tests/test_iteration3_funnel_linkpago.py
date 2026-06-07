# ruff: noqa
"""
Iteration 3 tests:
- Link de Pago in action-notifications catalog & configs (Pyme + Corp)
- Funnel report delivered_breakdown
- Funnel recalculate endpoint (admin only)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASS = "admin123"
USER_EMAIL = "srubio@megasoft.com.ve"
USER_PASS = "Test1234!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("token") or data.get("access_token")
    assert token, f"no token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user_token():
    return _login(USER_EMAIL, USER_PASS)


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}


# --- Catalog ---
class TestCatalog:
    def test_catalog_has_link_pago(self, admin_headers):
        r = requests.get(f"{API}/action-notifications/catalog", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # product_subcategories
        subs = data.get("product_subcategories", [])
        # could be list of dict {id,label} or dict
        if isinstance(subs, dict):
            assert "link_pago" in subs
            label = subs["link_pago"]
            assert "Link de Pago" in (label.get("label") if isinstance(label, dict) else label)
        else:
            ids = [s.get("id") if isinstance(s, dict) else s for s in subs]
            assert "link_pago" in ids, f"link_pago missing from {ids}"
            for s in subs:
                if isinstance(s, dict) and s.get("id") == "link_pago":
                    assert "Link de Pago" in s.get("label", ""), f"label wrong: {s}"

        allowed = data.get("allowed_actions_by_biz_sub", {})
        assert "implementacion_pyme|link_pago" in allowed, list(allowed.keys())[:10]
        assert "implementacion_corp|link_pago" in allowed, list(allowed.keys())[:10]
        legacy_actions = {"send_to_client", "approve", "invoice", "collect", "send_to_implementation"}
        pyme_acts = set(allowed["implementacion_pyme|link_pago"])
        corp_acts = set(allowed["implementacion_corp|link_pago"])
        assert legacy_actions.issubset(pyme_acts), f"pyme missing: {legacy_actions - pyme_acts}"
        assert legacy_actions.issubset(corp_acts), f"corp missing: {legacy_actions - corp_acts}"


# --- Configs PUT ---
class TestConfigsLinkPago:
    def test_put_pyme_link_pago_send_to_client(self, admin_headers):
        payload = {
            "business_type": "implementacion_pyme",
            "product_subcategory": "link_pago",
            "action_id": "send_to_client",
            "recipients": [
                {"type": "client_field", "client_field": "primary_contact_email",
                 "template_id": None, "send_pdf_attachments": True, "row_id": "row_test_1"}
            ],
        }
        r = requests.put(f"{API}/action-notifications/configs", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"

    def test_put_corp_link_pago_approve(self, admin_headers):
        payload = {
            "business_type": "implementacion_corp",
            "product_subcategory": "link_pago",
            "action_id": "approve",
            "recipients": [
                {"type": "client_field", "client_field": "primary_contact_email",
                 "template_id": None, "send_pdf_attachments": False, "row_id": "row_test_2"}
            ],
        }
        r = requests.put(f"{API}/action-notifications/configs", headers=admin_headers, json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"


# --- Funnel ---
class TestFunnel:
    def test_funnel_has_delivered_breakdown(self, admin_headers):
        r = requests.get(f"{API}/reports/sales/funnel", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "delivered_breakdown" in data, list(data.keys())
        bd = data["delivered_breakdown"]
        for k in ("implementaciones", "equipos", "reparaciones"):
            assert k in bd, f"missing segment {k}"
            seg = bd[k]
            assert "count" in seg and "amount_usd" in seg, seg

        # stage Entregada == sum of 3 segments
        stages = data.get("stages", [])
        delivered_stage = None
        for s in stages:
            name = s.get("name") or s.get("label") or s.get("stage") or s.get("id")
            if name and "ntregada" in str(name):
                delivered_stage = s
                break
        assert delivered_stage is not None, f"stages: {[s.get('name') for s in stages]}"
        total_count = sum(bd[k]["count"] for k in ("implementaciones", "equipos", "reparaciones"))
        total_amount = sum(bd[k]["amount_usd"] for k in ("implementaciones", "equipos", "reparaciones"))
        stage_count = delivered_stage.get("count", delivered_stage.get("value"))
        assert stage_count == total_count, f"stage count {stage_count} != sum {total_count}"
        # amount may be float; tolerate small diff
        stage_amt = delivered_stage.get("amount_usd", delivered_stage.get("amount", 0))
        assert abs(stage_amt - total_amount) < 0.01, f"stage amt {stage_amt} != sum {total_amount}"


# --- Recalculate ---
class TestRecalculate:
    def test_recalculate_admin_ok(self, admin_headers):
        r = requests.post(f"{API}/reports/sales/funnel/recalculate", headers=admin_headers, timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        for k in ("scanned", "updated", "fields_added"):
            assert k in data, f"missing {k} in {data}"

    def test_recalculate_non_admin_forbidden(self, user_headers):
        r = requests.post(f"{API}/reports/sales/funnel/recalculate", headers=user_headers, timeout=30)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"


# --- Regression LINK_PAGO quotes ---
class TestLinkPagoRegression:
    def test_quotes_contain_link_pago(self, admin_headers):
        r = requests.get(f"{API}/quotes", headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        quotes = data if isinstance(data, list) else data.get("quotes", data.get("items", []))
        link_pago = [q for q in quotes if (q.get("quote_type") or "").upper() == "LINK_PAGO"]
        assert len(link_pago) >= 1, f"expected at least 1 LINK_PAGO quote, found {len(link_pago)}"
