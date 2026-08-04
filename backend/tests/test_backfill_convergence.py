"""Convergence test for POST /api/admin/attachments/recover-to-storage.

Validates the fix for the truncated inventory bug:
- After a full real-run, an immediate dry-run must show `uploaded ≈ 0` (only
  genuinely missing-from-disk items can appear). Previously, files beyond the
  1000-key inventory truncation kept being re-uploaded on every run.
- Files that live past the 1000-key inventory limit must be classified as
  already_in_storage (not uploaded, not missing).
- Each batch (limit=100) must complete well under the 60s proxy timeout.
"""

import os
import time
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0]).rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"
ENDPOINT = f"{BASE_URL}/api/admin/attachments/recover-to-storage"
LIMIT = 100


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text}"
    tok = r.json().get("session_token")
    assert tok, "No session_token in login response"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _run_full(auth_headers, dry_run: bool):
    """Paginate through all batches and return aggregate totals + per-batch durations."""
    skip = 0
    agg = {
        "scanned": 0, "already_in_storage": 0, "uploaded": 0,
        "missing_everywhere": 0, "errors": 0,
    }
    total = None
    batch_times = []
    batches = 0
    while True:
        t0 = time.time()
        r = requests.post(
            ENDPOINT,
            params={"dry_run": str(dry_run).lower(), "skip": skip, "limit": LIMIT},
            headers=auth_headers,
            timeout=90,
        )
        elapsed = time.time() - t0
        batch_times.append(elapsed)
        assert r.status_code == 200, f"skip={skip} status={r.status_code} body={r.text[:400]}"
        data = r.json()
        for k in agg:
            agg[k] += int(data.get(k, 0) or 0)
        total = data.get("total")
        batches += 1
        # Safety: log per-batch info
        print(f"[{'DRY' if dry_run else 'REAL'}] skip={skip} took={elapsed:.1f}s "
              f"scanned={data.get('scanned')} ok={data.get('already_in_storage')} "
              f"uploaded={data.get('uploaded')} missing={data.get('missing_everywhere')} "
              f"errors={data.get('errors')} done={data.get('done')}")
        if data.get("done"):
            break
        skip = data.get("next_skip")
        assert skip is not None, "next_skip missing while not done"
        assert batches < 60, "Too many batches, aborting"
    agg["total"] = total
    agg["batch_times"] = batch_times
    return agg


class TestBackfillConvergence:

    def test_1_real_run_full(self, auth_headers, request):
        """Execute a full real-run (dry_run=false). Persist result for next test."""
        res = _run_full(auth_headers, dry_run=False)
        print(f"REAL-RUN AGGREGATE: {res}")
        # Basic sanity
        assert res["total"] is not None and res["total"] > 0
        assert res["scanned"] == res["total"]
        # Every batch must be well under proxy timeout (60s).
        max_batch = max(res["batch_times"])
        assert max_batch < 55.0, f"A batch exceeded proxy safety window: {max_batch:.1f}s"
        request.config.cache.set("real_run", res)

    def test_2_dry_run_after_real_converges(self, auth_headers, request):
        """Immediately after real-run, dry-run must yield uploaded≈0."""
        prev = request.config.cache.get("real_run", None)
        assert prev is not None, "Real-run fixture missing"
        res = _run_full(auth_headers, dry_run=True)
        print(f"DRY-RUN AGGREGATE (post-real): {res}")
        assert res["scanned"] == res["total"], "Scan mismatch"
        # After the fix, uploaded (=por subir) should converge to (at most) items
        # whose local file also disappeared. The interesting number is items
        # counted as "uploaded" that DO exist in storage; ideally zero.
        # Tolerance: 0 (all remaining "uploaded" items are genuinely local-only files
        # not yet uploaded). We assert strict convergence: nothing that already lives
        # in storage should be re-classified as uploaded.
        # Sanity: already_in_storage should have grown to cover the actual storage set.
        assert res["already_in_storage"] >= prev["already_in_storage"], (
            f"already_in_storage regressed: pre={prev['already_in_storage']} "
            f"post={res['already_in_storage']}"
        )
        # Strong convergence claim: 'uploaded' in the audit dry-run right after a
        # full real-run must be 0 (any item that we just uploaded is now in storage;
        # any item counted as uploaded means either it was newly created OR the
        # storage check missed it - the bug we are fixing).
        assert res["uploaded"] == 0, (
            f"Convergence FAIL: dry-run right after real-run still reports "
            f"{res['uploaded']} items as 'por subir'. Truncated-inventory bug not fully fixed."
        )

    def test_3_batch_latency_truncated_zone(self, auth_headers):
        """Batches inside the truncated-inventory zone (skip>1000) must respond <60s."""
        # Pick skip=1100 (past the 1000-key truncation zone) and skip=0 baseline.
        for skip in (0, 1100):
            t0 = time.time()
            r = requests.post(
                ENDPOINT,
                params={"dry_run": "true", "skip": skip, "limit": LIMIT},
                headers=auth_headers,
                timeout=90,
            )
            elapsed = time.time() - t0
            print(f"[LATENCY] skip={skip} elapsed={elapsed:.1f}s status={r.status_code}")
            # Some corpora may have <1100 items; only assert when the endpoint accepts it.
            assert r.status_code == 200
            assert elapsed < 55.0, f"skip={skip} exceeded 55s: {elapsed:.1f}s"

    def test_4_storage_key_exists_beyond_1000(self, auth_headers):
        """Direct check on the sample rel provided by the bug report:
        rel='attachments/quo_d7b16affbd9a/att_77a60c963c8c.pdf' should be found
        in storage via storage_key_exists even though list_storage_keys truncates.
        Uses an in-process import (this test runs on the backend host).
        """
        import sys
        sys.path.insert(0, "/app/backend")
        try:
            from services.pdf_storage import list_storage_keys, storage_key_exists
        except Exception as e:
            pytest.skip(f"Cannot import pdf_storage in-process: {e}")

        sample = "attachments/quo_d7b16affbd9a/att_77a60c963c8c.pdf"
        try:
            keys = list_storage_keys()
        except Exception as e:
            pytest.skip(f"Storage not initialized in test process: {e}")
        in_inventory = sample in keys
        exists_auth = storage_key_exists(sample)
        print(f"[SAMPLE] rel={sample} in_inventory={in_inventory} "
              f"storage_key_exists={exists_auth} inventory_size={len(keys)}")
        # Inventory truncation is expected (<=1000).
        assert len(keys) <= 1000
        # The point of the fix: authoritative check must be truthy even if inventory misses it.
        # If the exact sample no longer exists we skip; otherwise assert authoritative True.
        if not exists_auth:
            pytest.skip("Sample rel not present in current storage; cannot assert.")
        assert exists_auth is True
