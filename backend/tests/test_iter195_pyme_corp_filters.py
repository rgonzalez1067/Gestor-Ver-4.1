"""Iter195 — PyME/Corp filters in action matrix & override + alphabetic order.

Tests:
- /action-notifications/catalog: users sorted A-Z (label)
- /quote-action-overrides: allowed_user_emails resolved
- /other-actions/catalog: users sorted A-Z (label)
"""
import os, requests, pytest

BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
ADMIN_EMAIL = 'rgonzalez@megasoft.com.ve'
ADMIN_PASS = 'admin123'


@pytest.fixture(scope='module')
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={'email': ADMIN_EMAIL, 'password': ADMIN_PASS})
    assert r.status_code == 200, r.text
    body = r.json()
    return body.get('session_token') or body.get('access_token') or body.get('token')


@pytest.fixture(scope='module')
def hdrs(token):
    return {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


def _is_alpha_sorted(labels):
    norm = [str(x or '').strip().lower() for x in labels]
    return norm == sorted(norm)


def test_action_notifications_catalog_users_sorted(hdrs):
    r = requests.get(f"{BASE}/api/action-notifications/catalog", headers=hdrs)
    assert r.status_code == 200, r.text
    data = r.json()
    users = data.get('users', [])
    assert len(users) > 0, 'catalog must return users'
    labels = [u.get('label') or u.get('name') or u.get('email') for u in users]
    assert _is_alpha_sorted(labels), f"users not A-Z sorted: {labels[:10]}"
    # sede counts (informational)
    pyme = [u for u in users if (u.get('sede') or '').upper() == 'PYME']
    corp = [u for u in users if (u.get('sede') or '').upper() == 'CORP']
    print(f"users={len(users)} pyme={len(pyme)} corp={len(corp)}")
    assert len(pyme) > 0 and len(corp) > 0


def test_other_actions_catalog_users_sorted(hdrs):
    r = requests.get(f"{BASE}/api/other-actions/catalog", headers=hdrs)
    assert r.status_code == 200, r.text
    data = r.json()
    users = data.get('users') or data.get('available_users') or []
    assert len(users) > 0
    labels = [u.get('label') or u.get('name') or u.get('email') for u in users]
    assert _is_alpha_sorted(labels), f"other-actions users not A-Z: {labels[:10]}"


def test_quote_action_overrides_has_allowed_emails(hdrs):
    r = requests.get(f"{BASE}/api/quote-action-overrides", headers=hdrs)
    assert r.status_code == 200, r.text
    body = r.json()
    overrides = body['items'] if isinstance(body, dict) else body
    assert isinstance(overrides, list)
    # find one with allowed users
    with_users = [o for o in overrides if o.get('allowed_user_ids')]
    if not with_users:
        pytest.skip('no overrides with allowed_user_ids in this env')
    sample = with_users[0]
    assert 'allowed_user_emails' in sample, f"missing allowed_user_emails: keys={list(sample.keys())}"
    assert isinstance(sample['allowed_user_emails'], list)
    # specifically validate the PyME approve override per problem statement
    pyme_approve = [o for o in overrides if o.get('business_type') == 'implementacion_pyme' and o.get('action_id') == 'approve' and o.get('allowed_user_ids')]
    if pyme_approve:
        emails = pyme_approve[0]['allowed_user_emails']
        assert len(emails) == len(pyme_approve[0]['allowed_user_ids']), f"emails not fully resolved: {emails}"
        print(f"PyME|approve emails: {emails}")
    print(f"sample override: keys={list(sample.keys())}")


def test_quote_custom_actions_has_allowed_emails(hdrs):
    r = requests.get(f"{BASE}/api/quote-custom-actions", headers=hdrs)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body['items'] if isinstance(body, dict) and 'items' in body else (body if isinstance(body, list) else [])
    if not items or not all(isinstance(x, dict) for x in items):
        pytest.skip('no custom actions in env or non-dict shape')
    candidates = [c for c in items if c.get('allowed_user_ids')]
    if not candidates:
        pytest.skip('no custom actions with allowed_user_ids')
    sample = candidates[0]
    assert 'allowed_user_emails' in sample
