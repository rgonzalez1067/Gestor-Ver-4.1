"""
Iteration 5 — Bug fix: Mayor de Activos must include POS / PinPads received directly in TBP.

Validates:
- GET /api/inventory/asset-ledger response shape
- items include POS (Morefun MF360, MF919) and PinPad (Verifone P200)
- units_lch + units_tbp consistent with total_units (>= total_units when no other wh)
- grand_total equals the sum of item_total
- only items with balance > 0 appear
- method == "PEPS (FIFO)"
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "rgonzalez@megasoft.com.ve"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("session_token") or data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data.keys()}"
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def ledger(auth_headers):
    r = requests.get(
        f"{BASE_URL}/api/inventory/asset-ledger", headers=auth_headers, timeout=30
    )
    assert r.status_code == 200, f"Ledger failed: {r.status_code} {r.text}"
    return r.json()


def test_response_shape(ledger):
    assert ledger.get("method") == "PEPS (FIFO)"
    assert isinstance(ledger.get("items"), list)
    assert "grand_total" in ledger
    assert "total_items" in ledger


def test_includes_pos_and_pinpad(ledger):
    """Bug fix: POS Morefun and PinPad Verifone must appear when received in TBP."""
    items = ledger["items"]
    types_seen = {(i.get("item_type") or "").lower() for i in items}
    names = [i.get("item_name", "") for i in items]
    print(f"Item types seen: {types_seen}")
    print(f"Item names: {names}")

    # At least one POS and one PinPad in the report
    has_pos = any("pos" in (t or "") for t in types_seen) or any(
        "morefun" in n.lower() or "mf360" in n.lower() or "mf919" in n.lower()
        for n in names
    )
    has_pinpad = any("pinpad" in (t or "") for t in types_seen) or any(
        "verifone" in n.lower() or "p200" in n.lower() or "pinpad" in n.lower()
        for n in names
    )
    assert has_pos, f"No POS items appear in asset-ledger. types={types_seen} names={names}"
    assert has_pinpad, f"No PinPad items appear in asset-ledger. types={types_seen} names={names}"


def test_only_positive_balance(ledger):
    for it in ledger["items"]:
        assert it["total_units"] > 0, f"item {it['item_id']} has total_units<=0"
        # All lots in active list must have remaining>0
        for lot in it.get("lots", []):
            assert lot["remaining"] > 0


def test_grand_total_matches_sum_item_total(ledger):
    s = round(sum(i["item_total"] for i in ledger["items"]), 2)
    gt = round(ledger["grand_total"], 2)
    assert abs(s - gt) < 0.05, f"grand_total {gt} != sum(item_total) {s}"


def test_units_breakdown_consistent(ledger):
    """units_lch + units_tbp should be <= total_units (other warehouses may exist)."""
    for it in ledger["items"]:
        total = it["total_units"]
        lch = it.get("units_lch", 0)
        tbp = it.get("units_tbp", 0)
        assert lch >= 0 and tbp >= 0
        assert lch + tbp <= total + 0.001, (
            f"item {it['item_name']}: lch({lch})+tbp({tbp}) > total({total})"
        )


def test_pos_pinpad_appear_in_tbp_column(ledger):
    """Specific assertion of bug fix: POS/PinPad should be visible (units in TBP if received there)."""
    items = ledger["items"]
    relevant = [
        i for i in items
        if any(k in i.get("item_name", "").lower() for k in ("morefun", "mf360", "mf919", "verifone", "p200", "pinpad"))
        or (i.get("item_type") or "").lower() in ("pos", "pinpad")
    ]
    assert len(relevant) >= 2, f"Expected ≥2 POS/PinPad rows, got {len(relevant)}"
    # All these items should have at least some visible breakdown (either lch or tbp positive)
    for it in relevant:
        assert it["units_lch"] + it["units_tbp"] > 0, (
            f"Item {it['item_name']} has no LCH/TBP breakdown (lch=0, tbp=0) — bug not fixed"
        )
