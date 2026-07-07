# ruff: noqa
"""Tests for Iteration 7:
1) FIFO segmentado por almacén — Mayor de Activos (asset-ledger) aplica PEPS
   por (item_id, warehouse_id), no global.
2) Restricción LCH (Los Chaguaramos) — Solo sede=CORP puede generar
   salidas/transferencias/asignaciones temporales desde LCH (admin bypass).
"""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import load_dotenv

# Load backend .env so MONGO_URL/DB_NAME are available
load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://heartbeat-clean.preview.emergentagent.com").rstrip("/")
LCH_ID = "whs_bea89b61"
TBP_ID = "whs_f00b02f4"

ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"

# Test user with sede=PYME and inventarios=edit (created in fixture)
PYME_USER_EMAIL = "TEST_pyme_inv@megasoft.com.ve"
PYME_USER_PASSWORD = "Test1234!"

# Test SKU and movement IDs (cleaned up afterwards)
TEST_ITEM_ID = f"TEST_hwr_{uuid.uuid4().hex[:8]}"
TEST_TAG = f"TEST_iter7_{uuid.uuid4().hex[:6]}"


# ------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module")
def db_sync():
    """Sync wrapper for DB ops in fixtures (avoid event-loop issues)."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    return db, client


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown(db_sync):
    """Seed test item + movements + pyme user, then tear down."""
    db, client = db_sync

    async def seed():
        # 1. Create test hardware item
        await db.hardware.insert_one({
            "hardware_id": TEST_ITEM_ID,
            "name": f"{TEST_TAG} SKU",
            "type": "General",  # non-serialized
            "price_usd": 10,
        })

        # 2. Create 3 entries in LCH (costs 10, 12, 14) and 3 in TBP (costs 20, 22, 24)
        # Use staggered acquisition_dates to lock FIFO order deterministically.
        now = datetime.now(timezone.utc)
        movements = []

        def mk(wh, cost, days_ago):
            return {
                "movement_id": f"mov_{uuid.uuid4().hex[:8]}",
                "warehouse_id": wh,
                "item_id": TEST_ITEM_ID,
                "item_name": f"{TEST_TAG} SKU",
                "item_type": "General",
                "movement_type": "entrada",
                "quantity": 10,
                "unit_cost": cost,
                "acquisition_date": (now - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                "created_at": (now - timedelta(days=days_ago)).isoformat(),
                "supplier": "TEST Supplier",
                "invoice_ref": f"INV-{cost}",
                "serials": [],
                "reference": TEST_TAG,
            }
        # LCH lots — oldest first ($10) so PEPS picks it.
        movements.append(mk(LCH_ID, 10, 30))
        movements.append(mk(LCH_ID, 12, 20))
        movements.append(mk(LCH_ID, 14, 10))
        # TBP lots — oldest first ($20).
        movements.append(mk(TBP_ID, 20, 30))
        movements.append(mk(TBP_ID, 22, 20))
        movements.append(mk(TBP_ID, 24, 10))
        await db.inventory_movements.insert_many(movements)

        # 3. Insert 1 salida in LCH and 1 in TBP (qty=1 each)
        for wh in (LCH_ID, TBP_ID):
            await db.inventory_movements.insert_one({
                "movement_id": f"mov_{uuid.uuid4().hex[:8]}",
                "warehouse_id": wh,
                "item_id": TEST_ITEM_ID,
                "item_name": f"{TEST_TAG} SKU",
                "item_type": "General",
                "movement_type": "salida",
                "quantity": 1,
                "unit_cost": 0,
                "created_at": now.isoformat(),
                "reference": TEST_TAG,
                "serials": [],
            })

        # 4. Create test PYME user with inventarios=edit
        from config import hash_password
        await db.users.delete_one({"email": PYME_USER_EMAIL})
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": PYME_USER_EMAIL,
            "first_name": "Test",
            "last_name": "PYME-Inv",
            "role": "user",
            "sede": "PYME",
            "password_hash": hash_password(PYME_USER_PASSWORD),
            "active": True,
            "permissions": {
                "inventarios": "edit",
                "dispositivos": "read",
            },
        })

        # 5. Create test CORP user (sede=CORP) for positive control
        await db.users.delete_one({"email": "TEST_corp_inv@megasoft.com.ve"})
        await db.users.insert_one({
            "user_id": f"usr_{uuid.uuid4().hex[:12]}",
            "email": "TEST_corp_inv@megasoft.com.ve",
            "first_name": "Test",
            "last_name": "CORP-Inv",
            "role": "user",
            "sede": "CORP",
            "password_hash": hash_password(PYME_USER_PASSWORD),
            "active": True,
            "permissions": {"inventarios": "edit", "dispositivos": "read"},
        })

    _run(seed())
    yield

    async def teardown():
        await db.hardware.delete_many({"hardware_id": TEST_ITEM_ID})
        await db.inventory_movements.delete_many({"item_id": TEST_ITEM_ID})
        await db.users.delete_many({"email": {"$in": [PYME_USER_EMAIL, "TEST_corp_inv@megasoft.com.ve"]}})
        await db.user_sessions.delete_many({"user_id": {"$exists": True}, "session_token": {"$regex": "^TEST_"}})
        client.close()

    _run(teardown())


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    return data.get("session_token") or data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def pyme_token():
    return _login(PYME_USER_EMAIL, PYME_USER_PASSWORD)


@pytest.fixture(scope="module")
def corp_token():
    return _login("TEST_corp_inv@megasoft.com.ve", PYME_USER_PASSWORD)


# ===================== TESTS =====================

# Feature 1: Asset ledger lots include warehouse info, no cross-mixing
class TestAssetLedgerWarehouse:
    def test_lots_have_warehouse_fields(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/inventory/asset-ledger",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data
        assert "grand_total" in data
        # find our test item
        test_item = next((it for it in data["items"] if it["item_id"] == TEST_ITEM_ID), None)
        assert test_item is not None, f"Test item {TEST_ITEM_ID} not found in ledger"
        for lot in test_item["lots"]:
            assert "warehouse_id" in lot, f"Lot missing warehouse_id: {lot}"
            assert "warehouse_name" in lot, f"Lot missing warehouse_name: {lot}"
            assert lot["warehouse_id"] in (LCH_ID, TBP_ID)

    def test_no_lot_mixing_between_warehouses(self, admin_token):
        """Each lot belongs to exactly ONE warehouse."""
        r = requests.get(f"{BASE_URL}/api/inventory/asset-ledger",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        data = r.json()
        for item in data["items"]:
            for lot in item["lots"]:
                # warehouse_id is a single string, not a list
                assert isinstance(lot["warehouse_id"], str) and lot["warehouse_id"]


# Feature 2: FIFO segmented per (item, warehouse)
class TestFifoSegmented:
    def test_fifo_segmented_per_warehouse(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/inventory/asset-ledger",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        test_item = next((it for it in data["items"] if it["item_id"] == TEST_ITEM_ID), None)
        assert test_item is not None

        # Build lookup: (warehouse_id, unit_cost) -> remaining
        lots_idx = {(l["warehouse_id"], l["unit_cost"]): l for l in test_item["lots"]}

        # LCH oldest lot (cost=10) should have remaining 9
        lch_10 = lots_idx.get((LCH_ID, 10))
        assert lch_10 is not None, f"LCH cost=10 lot missing. Lots: {test_item['lots']}"
        assert lch_10["remaining"] == 9, f"Expected LCH $10 remaining=9, got {lch_10['remaining']}"

        # LCH cost=12 and 14 should still be 10
        lch_12 = lots_idx.get((LCH_ID, 12))
        lch_14 = lots_idx.get((LCH_ID, 14))
        assert lch_12 and lch_12["remaining"] == 10
        assert lch_14 and lch_14["remaining"] == 10

        # TBP oldest lot (cost=20) should have remaining 9
        tbp_20 = lots_idx.get((TBP_ID, 20))
        assert tbp_20 is not None
        assert tbp_20["remaining"] == 9, f"Expected TBP $20 remaining=9, got {tbp_20['remaining']}"
        tbp_22 = lots_idx.get((TBP_ID, 22))
        tbp_24 = lots_idx.get((TBP_ID, 24))
        assert tbp_22 and tbp_22["remaining"] == 10
        assert tbp_24 and tbp_24["remaining"] == 10

    def test_total_units_consistency(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/inventory/asset-ledger",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        data = r.json()
        test_item = next((it for it in data["items"] if it["item_id"] == TEST_ITEM_ID), None)
        assert test_item is not None
        # 60 entered, 2 exits → 58 total
        assert test_item["total_units"] == 58, f"Expected total_units=58, got {test_item['total_units']}"
        assert test_item["units_lch"] == 29, f"Expected units_lch=29, got {test_item['units_lch']}"
        assert test_item["units_tbp"] == 29, f"Expected units_tbp=29, got {test_item['units_tbp']}"
        # item_total = 9*10 + 10*12 + 10*14 + 9*20 + 10*22 + 10*24 = 90+120+140+180+220+240 = 990
        assert abs(test_item["item_total"] - 990) < 0.01

    def test_grand_total_consistent(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/inventory/asset-ledger",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        data = r.json()
        assert data["grand_total"] >= 990  # at least our contribution
        # And grand_total ≈ sum of item_totals
        calc = sum(it["item_total"] for it in data["items"])
        assert abs(data["grand_total"] - round(calc, 2)) < 1.0


# Feature 4-6: LCH restriction by sede=CORP
EXPECTED_LCH_MSG = "Almacén Los Chaguaramos está restringido exclusivamente para usuarios del segmento Corp"


class TestLchRestriction:
    def test_pyme_user_cannot_dispatch_from_lch(self, pyme_token):
        """POST /api/inventory/warehouses/{LCH}/exit by sede=PYME → 403 LCH msg."""
        r = requests.post(
            f"{BASE_URL}/api/inventory/warehouses/{LCH_ID}/exit",
            headers={"Authorization": f"Bearer {pyme_token}"},
            json={"item_id": TEST_ITEM_ID, "quantity": 1, "reference": TEST_TAG},
            timeout=30,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert EXPECTED_LCH_MSG in detail, f"Wrong error msg: {detail}"

    def test_pyme_user_can_dispatch_from_tbp(self, pyme_token):
        """sede=PYME → TBP must NOT trigger LCH restriction (validates negative path)."""
        r = requests.post(
            f"{BASE_URL}/api/inventory/warehouses/{TBP_ID}/exit",
            headers={"Authorization": f"Bearer {pyme_token}"},
            json={"item_id": TEST_ITEM_ID, "quantity": 1, "reference": TEST_TAG},
            timeout=30,
        )
        # Should succeed (200/201) — TBP has stock and no LCH check
        # Allow 200 or 201, or 400 if jurisdiction blocks (but we didn't set almacen_asignado)
        assert r.status_code in (200, 201), f"PYME→TBP should succeed, got {r.status_code}: {r.text}"
        body = r.json()
        # No LCH error message
        assert EXPECTED_LCH_MSG not in str(body)

    def test_corp_user_can_dispatch_from_lch(self, corp_token):
        """sede=CORP → LCH allowed."""
        r = requests.post(
            f"{BASE_URL}/api/inventory/warehouses/{LCH_ID}/exit",
            headers={"Authorization": f"Bearer {corp_token}"},
            json={"item_id": TEST_ITEM_ID, "quantity": 1, "reference": TEST_TAG},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"CORP→LCH should succeed, got {r.status_code}: {r.text}"

    def test_admin_can_dispatch_from_lch(self, admin_token):
        """Admin bypass even though sede=TBP."""
        r = requests.post(
            f"{BASE_URL}/api/inventory/warehouses/{LCH_ID}/exit",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"item_id": TEST_ITEM_ID, "quantity": 1, "reference": TEST_TAG},
            timeout=30,
        )
        assert r.status_code in (200, 201), f"Admin→LCH should succeed, got {r.status_code}: {r.text}"

    def test_pyme_cannot_transfer_from_lch(self, pyme_token):
        """POST /api/inventory/transfer source=LCH by PYME → 403 LCH."""
        r = requests.post(
            f"{BASE_URL}/api/inventory/transfer",
            headers={"Authorization": f"Bearer {pyme_token}"},
            json={
                "source_warehouse_id": LCH_ID,
                "dest_warehouse_id": TBP_ID,
                "item_id": TEST_ITEM_ID,
                "quantity": 1,
                "notes": TEST_TAG,
            },
            timeout=30,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        assert EXPECTED_LCH_MSG in r.json().get("detail", "")

    def test_pyme_cannot_create_temp_assignment_from_lch(self, pyme_token):
        """POST /api/inventory/temporary-assignments warehouse=LCH by PYME → 403 LCH."""
        r = requests.post(
            f"{BASE_URL}/api/inventory/temporary-assignments",
            headers={"Authorization": f"Bearer {pyme_token}"},
            json={
                "warehouse_id": LCH_ID,
                "item_id": TEST_ITEM_ID,
                "quantity": 1,
                "responsible_user_id": "external",
                "is_external_responsible": True,
                "responsible_external_name": "Test external",
                "reason": f"{TEST_TAG} temporal test",
            },
            timeout=30,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        assert EXPECTED_LCH_MSG in r.json().get("detail", "")


# Feature 8: Regression - asset ledger still returns all warehouses correctly
class TestRegression:
    def test_admin_ledger_returns_all_warehouses(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/inventory/asset-ledger",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        # Check at least one lot in TBP and one in LCH globally (besides our test item)
        seen_whs = set()
        for it in data["items"]:
            for lot in it["lots"]:
                seen_whs.add(lot["warehouse_id"])
        assert LCH_ID in seen_whs, "No LCH lots in ledger"
        # Note: TBP may or may not have lots depending on pre-existing data, but our test item does
        assert TBP_ID in seen_whs
