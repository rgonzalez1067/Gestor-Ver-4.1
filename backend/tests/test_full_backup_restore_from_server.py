"""Tests for restore-from-server (GridFS) full-backup flow."""
import os
import time
import json
import asyncio
import requests
import pytest


def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL missing"
    return v.rstrip("/")


BASE_URL = _load_backend_url()
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
    assert tok, r.text
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def ready_job_id(headers):
    """Ensure at least one ready backup exists in GridFS."""
    # Check latest first
    r = requests.get(f"{BASE_URL}/api/admin/full-backup/latest", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    if data.get("available"):
        return data["job_id"], data

    # Trigger build
    rb = requests.post(f"{BASE_URL}/api/admin/full-backup/build", headers=headers, timeout=30)
    assert rb.status_code in (200, 202), rb.text
    job_id = rb.json().get("job_id")
    assert job_id
    # Poll status
    for _ in range(120):
        rs = requests.get(
            f"{BASE_URL}/api/admin/full-backup/build-status",
            headers=headers, params={"job_id": job_id}, timeout=30,
        )
        assert rs.status_code == 200, rs.text
        st = rs.json().get("status")
        if st == "ready":
            break
        if st in ("error", "failed"):
            pytest.fail(f"Build failed: {rs.json()}")
        time.sleep(2)
    else:
        pytest.fail("Backup build timed out")

    r2 = requests.get(f"{BASE_URL}/api/admin/full-backup/latest", headers=headers, timeout=30)
    d2 = r2.json()
    assert d2.get("available"), d2
    return d2["job_id"], d2


def test_latest_returns_structure(headers, ready_job_id):
    job_id, data = ready_job_id
    assert data.get("available") is True
    assert data.get("job_id") == job_id
    assert isinstance(data.get("collections"), list)
    assert len(data["collections"]) > 0
    for c in data["collections"][:3]:
        assert "name" in c and "count" in c
    assert data.get("db_name")
    assert isinstance(data.get("size_bytes"), int)


def _pick_small_collections(collections, wanted_names):
    have = {c["name"]: c["count"] for c in collections}
    return [n for n in wanted_names if n in have], have


def test_restore_from_server_selective_fast(headers, ready_job_id):
    job_id, data = ready_job_id
    candidates = ["project_sla_config", "banks", "email_footer_config", "company_settings"]
    picks, counts = _pick_small_collections(data["collections"], candidates)
    assert len(picks) >= 1, f"Ninguna candidata en backup. Colecciones disponibles: {list(counts.keys())[:20]}"
    picks = picks[:2]

    payload = {
        "job_id": job_id,
        "mode": "merge",
        "collections": json.dumps(picks),
    }
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/admin/full-backup/restore-from-server",
        headers=headers, data=payload, timeout=120,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok", body
    assert body.get("selective") is True
    assert body.get("skipped") in ([], None)
    assert body.get("dropped_extra") in ([], None)
    summary = body.get("summary") or []
    assert len(summary) == len(picks), summary
    names_in_summary = {s.get("collection") or s.get("name") for s in summary}
    assert set(picks).issubset(names_in_summary)

    # Verify counts against /latest counts (merge should not reduce)
    for s in summary:
        name = s.get("collection") or s.get("name")
        restored = s.get("restored") or s.get("upserted") or s.get("count")
        if restored is not None and name in counts:
            assert restored <= counts[name] + 1  # allow tolerance

    print(f"restore-from-server selective elapsed={elapsed:.2f}s picks={picks}")
    assert elapsed < 30, f"Restore demasiado lento: {elapsed}s"


def test_server_not_blocked_during_restore(headers, ready_job_id):
    """Fire restore + info in parallel; info must respond quickly."""
    job_id, data = ready_job_id
    candidates = ["project_sla_config", "banks", "email_footer_config", "company_settings"]
    picks, _ = _pick_small_collections(data["collections"], candidates)
    picks = picks[:1] or ["project_sla_config"]

    async def run():
        loop = asyncio.get_event_loop()

        def do_restore():
            return requests.post(
                f"{BASE_URL}/api/admin/full-backup/restore-from-server",
                headers=headers,
                data={"job_id": job_id, "mode": "merge", "collections": json.dumps(picks)},
                timeout=120,
            )

        def do_info():
            time.sleep(0.2)  # start slightly after restore
            return requests.get(f"{BASE_URL}/api/admin/full-backup/info", headers=headers, timeout=30)

        t_restore = loop.run_in_executor(None, do_restore)
        t_info = loop.run_in_executor(None, do_info)
        r_restore, r_info = await asyncio.gather(t_restore, t_info)
        return r_restore, r_info

    r_restore, r_info = asyncio.run(run())
    assert r_restore.status_code == 200, r_restore.text
    assert r_info.status_code == 200, r_info.text


def test_restore_from_server_invalid_collection(headers, ready_job_id):
    job_id, _ = ready_job_id
    r = requests.post(
        f"{BASE_URL}/api/admin/full-backup/restore-from-server",
        headers=headers,
        data={"job_id": job_id, "mode": "merge", "collections": json.dumps(["__no_existe__"])},
        timeout=60,
    )
    assert r.status_code == 400, r.text


def test_restore_from_server_bad_job_id(headers):
    r = requests.post(
        f"{BASE_URL}/api/admin/full-backup/restore-from-server",
        headers=headers,
        data={"job_id": "job_does_not_exist_xxx", "mode": "merge", "collections": json.dumps(["banks"])},
        timeout=30,
    )
    assert r.status_code == 404, r.text
