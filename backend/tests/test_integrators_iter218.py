"""Iter 218 — Integrators: default classified view + responsible contact capture."""
import os, requests, pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

@pytest.fixture(scope='module')
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "rgonzalez@megasoft.com.ve", "password": "admin123"})
    assert r.status_code == 200, r.text
    return r.json().get('session_token') or r.json().get('token')

@pytest.fixture(scope='module')
def h(token):
    return {"Authorization": f"Bearer {token}"}

# Default view should exclude closed (and frontend filters by scope client-side too)
def test_default_view_excludes_closed(h):
    r = requests.get(f"{BASE_URL}/api/integrators", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert all(i.get('integrator_status') != 'Cerrado' for i in data)

def test_show_all_includes_more(h):
    r1 = requests.get(f"{BASE_URL}/api/integrators", headers=h)
    r2 = requests.get(f"{BASE_URL}/api/integrators?show_all=true", headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(r2.json()) >= len(r1.json())

# Classified rows must include at least the 4 known ones
def test_classified_rows_present(h):
    r = requests.get(f"{BASE_URL}/api/integrators?show_all=true", headers=h)
    data = r.json()
    classified = [i for i in data if i.get('project_scope') in ('new', 'component', 'expansion')]
    assert len(classified) >= 3
    names = {(i.get('name') or '').lower() for i in classified}
    # known classified per the task
    assert any('rafatech' in n or 'alcantara' in n or 'xetux' in n or 'saint' in n for n in names)

# Create new integrator with responsible contact and verify persisted in contacts[0]
def test_create_new_with_responsible_contact_and_cleanup(h):
    payload = {
        "name": "ZZZ QA Responsable Test 218",
        "integrator_type": "Integrador",
        "integration_type": "PG",
        "app_name": "QA APP 218",
        "integration_modality": "PG Universal",
        "integrator_status": "En proceso",
        "contacts": [{"contact_id": "ctc_qa218", "name": "QA Responsable",
                      "email": "qa218@example.com", "phone": "+58 412-0000000"}]
    }
    r = requests.post(f"{BASE_URL}/api/integrators", json=payload, headers=h)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created.get('project_scope') == 'new'
    contacts = created.get('contacts') or []
    assert len(contacts) >= 1
    assert contacts[0].get('email') == 'qa218@example.com'
    assert contacts[0].get('name') == 'QA Responsable'
    assert contacts[0].get('phone') == '+58 412-0000000'
    iid = created['integrator_id']
    # Cleanup
    d = requests.delete(f"{BASE_URL}/api/integrators/{iid}", headers=h)
    assert d.status_code == 200

# Expand endpoint accepts contacts and merges them dedup by email
def test_expand_accepts_contacts(h):
    # create base integrator
    base = {
        "name": "ZZZ QA Expand 218",
        "integrator_type": "Integrador",
        "integration_type": "PG",
        "app_name": "QA EXPAND APP",
        "integration_modality": "PG Universal",
        "integrator_status": "En proceso",
        "contacts": [{"name": "Base", "email": "base218@example.com", "phone": "1"}]
    }
    r = requests.post(f"{BASE_URL}/api/integrators", json=base, headers=h)
    assert r.status_code == 200
    iid = r.json()['integrator_id']
    # Expand with new contact
    ex = requests.post(f"{BASE_URL}/api/integrators/{iid}/expand",
                       json={"productos_certificar": "TDD/TDC",
                             "contacts": [{"name": "Resp Expand", "email": "respexp218@example.com", "phone": "2"}]},
                       headers=h)
    assert ex.status_code == 200, ex.text
    body = ex.json()
    assert body.get('project_scope') == 'expansion'
    emails = {(c.get('email') or '').lower() for c in (body.get('contacts') or [])}
    assert 'base218@example.com' in emails
    assert 'respexp218@example.com' in emails
    # Cleanup
    requests.delete(f"{BASE_URL}/api/integrators/{iid}", headers=h)
