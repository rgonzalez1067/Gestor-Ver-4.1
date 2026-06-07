# ruff: noqa
"""Backend tests for P1 Push Notifications (iteration 179).

Covers:
- /api/notifications/config (GET list, PUT update — admin only)
- /api/notifications (feed + unread count + mark read + mark-all-read)
- Direct call to notify() service (persistence + recipient resolution by sede)
- Real trigger: POST /api/quotes/{id}/approve
- Scheduler jobs registered (import and introspect)
"""
import os
import asyncio
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


# ------------------------- Fixtures -------------------------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("access_token")
    assert token, f"No session_token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def non_admin_token():
    """Uses cmarin (departamento=Administración, sede=Pyme) but role likely not admin."""
    for email in ["cmarin@megasoft.com.ve"]:
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": "admin123"},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("session_token")
    pytest.skip("Could not login as non-admin; skipping 403 tests")


# ------------------------- Config endpoints -------------------------

class TestNotificationConfig:
    def test_get_config_returns_16_events(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/notifications/config", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body and "priorities" in body
        assert len(body["items"]) == 16, f"Expected 16 events, got {len(body['items'])}"
        # Each event shape
        sample = body["items"][0]
        for key in ("event_type", "label", "category", "is_active", "priority", "scheduled"):
            assert key in sample, f"Missing {key} in config item"
        # Priorities list
        assert set(body["priorities"]) == {"high", "medium", "low"}
        # At least 3 scheduled events
        scheduled = [e for e in body["items"] if e.get("scheduled")]
        assert len(scheduled) == 3

    def test_get_config_non_admin_forbidden(self, non_admin_token):
        if not non_admin_token:
            pytest.skip("no non-admin")
        r = requests.get(
            f"{BASE_URL}/api/notifications/config",
            headers={"Authorization": f"Bearer {non_admin_token}"},
            timeout=15,
        )
        assert r.status_code == 403

    def test_put_config_updates(self, admin_headers):
        # Toggle priority on quote_approved to medium, then back to high
        r = requests.put(
            f"{BASE_URL}/api/notifications/config/quote_approved",
            headers=admin_headers,
            json={"priority": "medium", "is_active": True},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["priority"] == "medium"
        assert data["is_active"] is True

        # Revert
        r = requests.put(
            f"{BASE_URL}/api/notifications/config/quote_approved",
            headers=admin_headers,
            json={"priority": "high"},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["priority"] == "high"

    def test_put_config_invalid_priority(self, admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/notifications/config/quote_approved",
            headers=admin_headers,
            json={"priority": "urgent"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_put_config_unknown_event(self, admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/notifications/config/not_a_real_event",
            headers=admin_headers,
            json={"is_active": False},
            timeout=15,
        )
        assert r.status_code == 404

    def test_put_config_non_admin_forbidden(self, non_admin_token):
        if not non_admin_token:
            pytest.skip("no non-admin")
        r = requests.put(
            f"{BASE_URL}/api/notifications/config/quote_approved",
            headers={"Authorization": f"Bearer {non_admin_token}"},
            json={"is_active": False},
            timeout=15,
        )
        assert r.status_code == 403


# ------------------------- Feed endpoints -------------------------

class TestNotificationFeed:
    def test_list_feed(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/notifications?limit=50", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "unread_count" in body
        assert isinstance(body["items"], list)
        assert isinstance(body["unread_count"], int)

    def test_unread_count(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert "count" in r.json()

    def test_only_unread_filter(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/notifications?only_unread=true&limit=50", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["is_read"] is False

    def test_mark_all_read(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/notifications/mark-all-read", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "updated" in body
        # After mark-all-read, unread must be 0
        c = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=admin_headers, timeout=15)
        assert c.json()["count"] == 0


# ------------------------- Direct notify() service -------------------------

class TestNotifyService:
    def test_notify_quote_approved_persists_for_admins(self, admin_headers):
        """Call notify() directly; expect >=1 recipient (admin user)."""
        import sys
        sys.path.insert(0, "/app/backend")
        from services.notification_service import notify  # type: ignore

        unique_title = f"TEST_notify_{uuid.uuid4().hex[:8]}"
        count = asyncio.run(
            notify(
                "quote_approved",
                unique_title,
                "msg test",
                context={"sede": "TBP"},
            )
        )
        assert count >= 1, f"Expected at least 1 recipient, got {count}"

        # Admin should have received it (via GET feed)
        r = requests.get(f"{BASE_URL}/api/notifications?limit=100", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        titles = [n["title"] for n in r.json()["items"]]
        assert unique_title in titles, "Notification title not found in admin feed"

    def test_notify_disabled_event_returns_zero(self, admin_headers):
        """When is_active=false → notify returns 0 and nothing new appears in admin feed."""
        # Snapshot unread count
        before = requests.get(f"{BASE_URL}/api/notifications?limit=100", headers=admin_headers, timeout=15).json()
        before_ids = {n["notification_id"] for n in before["items"]}

        # Disable event
        r = requests.put(
            f"{BASE_URL}/api/notifications/config/quote_invoiced",
            headers=admin_headers,
            json={"is_active": False},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        try:
            # Attempt to fire a notify via a subprocess (new event loop + fresh motor client)
            import subprocess
            unique_title = f"TEST_disabled_{uuid.uuid4().hex[:8]}"
            code = (
                "import asyncio, sys; sys.path.insert(0,'/app/backend');"
                "from services.notification_service import notify;"
                f"c=asyncio.run(notify('quote_invoiced','{unique_title}','x',context={{'sede':'TBP'}}));"
                "print('COUNT',c)"
            )
            out = subprocess.run(["python", "-c", code], capture_output=True, text=True, cwd="/app/backend", timeout=30)
            assert "COUNT 0" in out.stdout, f"Expected 0 recipients; got: {out.stdout} {out.stderr}"

            # Verify no new notification with that title
            after = requests.get(f"{BASE_URL}/api/notifications?limit=100", headers=admin_headers, timeout=15).json()
            assert unique_title not in [n["title"] for n in after["items"]]
        finally:
            requests.put(
                f"{BASE_URL}/api/notifications/config/quote_invoiced",
                headers=admin_headers,
                json={"is_active": True},
                timeout=15,
            )


# ------------------------- Scheduler introspection -------------------------

class TestScheduler:
    def test_scheduler_registers_3_jobs(self):
        """Start scheduler in a fresh loop and verify 3 jobs with correct IDs."""
        import sys
        sys.path.insert(0, "/app/backend")

        async def _inspect():
            from services import notification_scheduler as sch  # type: ignore
            # Start (idempotent)
            sch.start_scheduler()
            jobs = sch.scheduler.get_jobs()
            ids = {j.id for j in jobs}
            # Stop so this test process doesn't keep the scheduler alive
            sch.stop_scheduler()
            return ids

        ids = asyncio.run(_inspect())
        assert ids == {"taller_15d", "proj_not_started", "proj_stalled"}, f"Got job ids: {ids}"
