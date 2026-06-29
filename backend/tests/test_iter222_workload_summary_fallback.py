"""Iter 222 — Implementer Workload Summary: name-fallback bug fix + new metric pairs.
Covers:
  - Shape: cajas_asignadas/cajas_pendientes/pvv_asignados/pvv_pendientes/projects_count/avance_global.
  - Constraints: cajas_pendientes <= cajas_asignadas; pvv_pendientes <= pvv_asignados; avance 0-100.
  - Name fallback: querying by user_id vs by name yields identical totals for Omar Jiménez.
  - Resilience: nonexistent user/name → 200 with zeros (no 500).
  - Coverage: every distinct implementer (from /api/projects + /api/projects/implementers/list) → 200.
"""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("session_token")
    assert tok, f"no session_token in response: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# --- Shape / constraints ---
def test_shape_and_constraints_omar(headers):
    uid = "user_3cc63615f2c0"
    r = requests.get(f"{BASE_URL}/api/projects/implementers/{uid}/workload-summary",
                     headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    expected = {"user_id", "implementer_name", "projects_count",
                "cajas_asignadas", "cajas_pendientes",
                "pvv_asignados", "pvv_pendientes", "avance_global"}
    assert expected.issubset(d.keys()), f"missing keys: {expected - set(d.keys())}"
    # non-negative ints
    for k in ("projects_count", "cajas_asignadas", "cajas_pendientes",
              "pvv_asignados", "pvv_pendientes", "avance_global"):
        assert isinstance(d[k], int) and d[k] >= 0, f"{k}={d[k]!r}"
    assert 0 <= d["avance_global"] <= 100
    assert d["cajas_pendientes"] <= d["cajas_asignadas"], d
    assert d["pvv_pendientes"] <= d["pvv_asignados"], d
    assert d["user_id"] == uid


# --- BUG FIX: name fallback equivalence ---
def test_name_fallback_equals_user_id_for_omar(headers):
    uid = "user_3cc63615f2c0"
    by_id = requests.get(f"{BASE_URL}/api/projects/implementers/{uid}/workload-summary",
                        headers=headers, timeout=20).json()
    by_name = requests.get(f"{BASE_URL}/api/projects/implementers/_/workload-summary",
                          headers=headers, params={"name": "Omar Jiménez"}, timeout=20).json()
    for k in ("projects_count", "cajas_asignadas", "cajas_pendientes",
              "pvv_asignados", "pvv_pendientes", "avance_global"):
        assert by_id[k] == by_name[k], f"{k}: id={by_id[k]} name={by_name[k]} (full id={by_id}, name={by_name})"


def test_name_fallback_also_with_placeholders(headers):
    """When the user_id is a 'placeholder' literal, must use name fallback."""
    for placeholder in ("_", "none", "null", "undefined"):
        r = requests.get(f"{BASE_URL}/api/projects/implementers/{placeholder}/workload-summary",
                         headers=headers, params={"name": "Omar Jiménez"}, timeout=20)
        assert r.status_code == 200, (placeholder, r.text)
        d = r.json()
        assert d["projects_count"] >= 1, f"placeholder {placeholder} produced 0 for Omar: {d}"


# --- Resilience ---
def test_resilience_nonexistent_id_and_name(headers):
    r = requests.get(f"{BASE_URL}/api/projects/implementers/nope/workload-summary",
                     headers=headers, params={"name": "Fulano Inexistente"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("projects_count", "cajas_asignadas", "cajas_pendientes",
             "pvv_asignados", "pvv_pendientes", "avance_global"):
        assert d[k] == 0, f"expected zero for {k}, got {d[k]}"


def test_resilience_unknown_id_no_name(headers):
    r = requests.get(f"{BASE_URL}/api/projects/implementers/totally-bogus-id/workload-summary",
                     headers=headers, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json()["projects_count"] == 0


# --- Coverage: EVERY distinct implementer must respond 200 (the bug was 'no se puede ver') ---
def _collect_implementers(headers):
    seen = {}  # user_id -> name
    # From /projects/implementers/list
    try:
        r = requests.get(f"{BASE_URL}/api/projects/implementers/list", headers=headers, timeout=20)
        if r.status_code == 200:
            for item in (r.json() or []):
                uid = item.get("user_id") or item.get("id") or ""
                nm = item.get("name") or item.get("full_name") or ""
                if uid or nm:
                    seen[uid] = nm
    except Exception:
        pass
    # From /projects (distinct assigned_to_user_id + assigned_to_name)
    r = requests.get(f"{BASE_URL}/api/projects", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("items") or payload.get("projects") or []
    for p in items:
        uid = (p.get("assigned_to_user_id") or "").strip()
        nm = (p.get("assigned_to_name") or "").strip()
        if not nm or nm.lower() in ("sin asignar", ""):
            continue
        seen.setdefault(uid, nm)
    return seen


def test_every_implementer_returns_200(headers):
    impls = _collect_implementers(headers)
    assert impls, "no implementers discovered to test"
    failures = []
    for uid, nm in impls.items():
        params = {"name": nm} if nm else None
        url_uid = uid if uid else "_"
        try:
            r = requests.get(f"{BASE_URL}/api/projects/implementers/{url_uid}/workload-summary",
                            headers=headers, params=params, timeout=25)
            if r.status_code != 200:
                failures.append({"uid": uid, "name": nm, "status": r.status_code, "body": r.text[:200]})
            else:
                d = r.json()
                for k in ("projects_count", "cajas_asignadas", "cajas_pendientes",
                         "pvv_asignados", "pvv_pendientes", "avance_global"):
                    if k not in d:
                        failures.append({"uid": uid, "name": nm, "missing_key": k})
                        break
        except Exception as e:
            failures.append({"uid": uid, "name": nm, "exc": str(e)})
    assert not failures, f"{len(failures)}/{len(impls)} implementer summaries failed: {failures[:10]}"


def test_constraints_for_all_implementers(headers):
    """Validates pendientes <= asignadas and avance in [0,100] across all real implementers."""
    impls = _collect_implementers(headers)
    bad = []
    for uid, nm in impls.items():
        params = {"name": nm} if nm else None
        url_uid = uid if uid else "_"
        r = requests.get(f"{BASE_URL}/api/projects/implementers/{url_uid}/workload-summary",
                        headers=headers, params=params, timeout=25)
        if r.status_code != 200:
            continue
        d = r.json()
        if d["cajas_pendientes"] > d["cajas_asignadas"]:
            bad.append((uid or nm, "cajas pend > asig", d))
        if d["pvv_pendientes"] > d["pvv_asignados"]:
            bad.append((uid or nm, "pvv pend > asig", d))
        if not (0 <= d["avance_global"] <= 100):
            bad.append((uid or nm, "avance out of range", d))
    assert not bad, f"constraint violations: {bad[:10]}"
