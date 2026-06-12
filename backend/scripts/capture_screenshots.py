"""
Captura pantallas reales del módulo de Proyectos (y flujos asociados) para el manual.
Login vía API + localStorage, navegación con Playwright. Guarda PNGs en /app/docs/screenshots/.
"""
import os, json, time
import requests
from playwright.sync_api import sync_playwright

BACKEND = open('/app/frontend/.env').read()
BASE = [l for l in BACKEND.splitlines() if l.startswith('REACT_APP_BACKEND_URL=')][0].split('=', 1)[1].strip()
EMAIL = 'rgonzalez@megasoft.com.ve'
PWD = 'admin123'
MULTISTORE_PID = 'prj_698951f4193a'  # PRY-2026-06-027-PRI (4 sucursales, directo)
OUT = '/app/docs/screenshots'
os.makedirs(OUT, exist_ok=True)

# 1) login API
r = requests.post(f'{BASE}/api/auth/login', json={'email': EMAIL, 'password': PWD}, timeout=30)
r.raise_for_status()
data = r.json()
token = data['session_token']
user = json.dumps(data['user'])
print('login OK, token len', len(token))

results = {}

def shot(page, name, wait=900):
    page.wait_for_timeout(wait)
    path = os.path.join(OUT, name + '.png')
    page.screenshot(path=path, full_page=False)
    results[name] = os.path.exists(path)
    print(' shot', name, results[name])

def safe_click(page, selector, wait=1200):
    try:
        el = page.query_selector(selector)
        if el:
            el.click()
            page.wait_for_timeout(wait)
            return True
    except Exception as e:
        print('  click fail', selector, e)
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    ctx = browser.new_context(viewport={'width': 1600, 'height': 1000})
    page = ctx.new_page()
    # set localStorage before app loads
    page.add_init_script(f"""
        localStorage.setItem('session_token', {json.dumps(token)});
        localStorage.setItem('user', {json.dumps(user)});
        localStorage.setItem('sidebar_pinned','true');
        localStorage.setItem('sidebar_collapsed','false');
    """)

    # ---- Lista de Proyectos ----
    page.goto(f'{BASE}/projects', wait_until='networkidle')
    page.wait_for_timeout(2500)
    shot(page, '01_projects_list')

    # Actualización masiva (reasignación) desde la lista
    if safe_click(page, '[data-testid="bulk-reassign-open-btn"]'):
        shot(page, '02_bulk_reassign_dialog')
        # cerrar (Escape)
        page.keyboard.press('Escape'); page.wait_for_timeout(500)

    # Plantillas desde la lista
    if safe_click(page, '[data-testid="projects-templates-btn"]'):
        shot(page, '03_projects_templates_from_list')
        page.keyboard.press('Escape'); page.wait_for_timeout(500)

    # ---- Detalle de Proyecto (multitienda) ----
    page.goto(f'{BASE}/projects/{MULTISTORE_PID}', wait_until='networkidle')
    page.wait_for_timeout(3000)
    shot(page, '04_project_detail_overview')

    # Sección multitienda (actualización individual de tiendas)
    try:
        sec = page.query_selector('[data-testid="multistore-section"]')
        if sec:
            sec.scroll_into_view_if_needed(); page.wait_for_timeout(800)
            shot(page, '05_multistore_individual')
    except Exception as e:
        print('  multistore section fail', e)

    # Actualización Masiva (batch) en detalle
    if safe_click(page, '[data-testid="batch-update-btn"]'):
        shot(page, '06_batch_update_dialog')
        page.keyboard.press('Escape'); page.wait_for_timeout(500)

    # Plantillas (creación) en detalle
    if safe_click(page, '[data-testid="manage-templates-btn"]'):
        shot(page, '07_templates_dialog')
        # seleccionar primera plantilla para mostrar el formulario poblado
        try:
            it = page.query_selector('[data-testid^="template-item-"]')
            if it:
                it.click(); page.wait_for_timeout(700)
                shot(page, '08_template_edit_form')
        except Exception as e:
            print('  template item fail', e)
        page.keyboard.press('Escape'); page.wait_for_timeout(500)

    # Notificaciones a Clientes/Bancos
    opened = safe_click(page, '[data-testid="notifications-btn"]')
    if not opened:
        opened = safe_click(page, '[data-testid="notif-bank-client-btn"]')
    if opened or page.query_selector('[data-testid="notif-dialog"]'):
        page.wait_for_timeout(800)
        if page.query_selector('[data-testid="notif-dialog"]'):
            shot(page, '09_notifications_dialog')
        page.keyboard.press('Escape'); page.wait_for_timeout(500)

    # Otras Notificaciones (Adhoc)
    if safe_click(page, '[data-testid="adhoc-email-btn"]'):
        page.wait_for_timeout(900)
        if page.query_selector('[data-testid="adhoc-email-dialog"]'):
            shot(page, '10_adhoc_dialog')
        page.keyboard.press('Escape'); page.wait_for_timeout(500)

    browser.close()

print('RESULTS:', json.dumps(results, indent=2))
print('Captured', sum(1 for v in results.values() if v), 'of', len(results))
