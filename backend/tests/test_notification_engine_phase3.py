# ruff: noqa
"""Phase 3 — Seeder Legacy + Auditoría de despachos.

Tests para validar:
  1. POST /seed-legacy crea configs para todas las combinaciones permitidas.
  2. Re-ejecutar el seeder (overwrite=False) NO sobrescribe configs con recipients.
  3. Combinaciones client-facing reciben fila `client_field` con plantilla preseleccionada.
  4. GET /audit-log retorna despachos del engine con filtros aplicables.
  5. RBAC: ambos endpoints son admin-only.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, '/app/backend')
load_dotenv('/app/backend/.env')


async def _login(client, email, password):
    res = await client.post('/api/auth/login', json={"email": email, "password": password})
    assert res.status_code == 200, f"login failed: {res.text}"
    d = res.json()
    return d.get('session_token') or d.get('token')


async def _run():
    from server import app
    c = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = c[os.environ['DB_NAME']]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        admin_token = await _login(ac, 'rgonzalez@megasoft.com.ve', 'admin123')
        admin_h = {"Authorization": f"Bearer {admin_token}"}

        # Pre-create one config with recipients (to test skip on seed)
        protected_key = "equipos|_|invoice"
        await db.action_notification_configs.update_one(
            {"config_key": protected_key},
            {"$set": {
                "config_key": protected_key,
                "business_type": "equipos",
                "product_subcategory": None,
                "action_id": "invoice",
                "recipients": [{"row_id": "row_protected", "type": "user", "user_id": "user_admin_main",
                                "template_id": "tpl_test", "send_pdf_attachments": False}],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

        # -------- 1. Seed without overwrite --------
        res = await ac.post('/api/action-notifications/seed-legacy', headers=admin_h)
        assert res.status_code == 200, res.text
        d = res.json()
        assert 'created' in d and 'updated' in d and 'skipped_existing' in d
        # Total combinaciones = 57
        assert d['total_combinations'] == 57, f"expected 57, got {d['total_combinations']}"
        # Protected debe seguir intacta
        kept = await db.action_notification_configs.find_one({"config_key": protected_key}, {"_id": 0})
        assert kept and kept['recipients'][0]['row_id'] == 'row_protected', \
            f"Seeder rompió config protegida: {kept}"
        print(f"[OK] Seeder: created={d['created']} updated={d['updated']} skipped={d['skipped_existing']} (protegida intacta)")

        # -------- 2. Client-facing combinations have client_field row --------
        send_to_client_pyme_vpos = await db.action_notification_configs.find_one(
            {"config_key": "implementacion_pyme|vpos|send_to_client"}, {"_id": 0}
        )
        assert send_to_client_pyme_vpos, "send_to_client | implementacion_pyme | vpos no encontrada"
        recips = send_to_client_pyme_vpos.get('recipients', [])
        assert any(r.get('type') == 'client_field' for r in recips), \
            f"send_to_client debe tener fila client_field, got: {recips}"
        print("[OK] send_to_client | implementacion_pyme | vpos tiene fila client_field")

        # repair_complete | reparaciones también
        rc_repair = await db.action_notification_configs.find_one(
            {"config_key": "reparaciones|_|repair_complete"}, {"_id": 0}
        )
        assert rc_repair and any(r.get('type') == 'client_field' for r in rc_repair['recipients']), \
            "repair_complete | reparaciones debe tener client_field"
        print("[OK] repair_complete | reparaciones tiene fila client_field")

        # invoice | implementacion_pyme | vpos NO debe tener client_field (acción interna)
        inv_pyme = await db.action_notification_configs.find_one(
            {"config_key": "implementacion_pyme|vpos|invoice"}, {"_id": 0}
        )
        assert inv_pyme is not None
        assert not any(r.get('type') == 'client_field' for r in inv_pyme.get('recipients', [])), \
            "invoice no debe pre-cargar client_field"
        print("[OK] invoice | implementacion_pyme | vpos sin client_field (correcto)")

        # -------- 3. Audit-log endpoint --------
        # Insertar 2 despachos sintéticos para validar filtros
        now_iso = datetime.now(timezone.utc).isoformat()
        synthetic = [
            {"action": "notification_engine_dispatch", "action_id": "approve",
             "config_key": "implementacion_pyme|vpos|approve", "quote_id": "q_audit_test_1",
             "quote_number": "COT-AUDIT-001", "sent_count": 2, "skipped": [],
             "executed_by": "rgonzalez@megasoft.com.ve", "executed_at": now_iso},
            {"action": "notification_engine_dispatch", "action_id": "send_to_client",
             "config_key": "equipos|_|send_to_client", "quote_id": "q_audit_test_2",
             "quote_number": "COT-AUDIT-002", "sent_count": 1,
             "skipped": [{"row_id": "r1", "reason": "Cliente sin email"}],
             "executed_by": "rgonzalez@megasoft.com.ve", "executed_at": now_iso},
        ]
        await db.bitacora.insert_many(synthetic)

        res = await ac.get('/api/action-notifications/audit-log', headers=admin_h, params={"limit": 50})
        assert res.status_code == 200
        items = res.json()['items']
        assert any(it.get('quote_number') == 'COT-AUDIT-001' for it in items), \
            "audit-log no devolvió COT-AUDIT-001"
        assert any(it.get('quote_number') == 'COT-AUDIT-002' for it in items)
        print(f"[OK] audit-log retorna {len(items)} despachos")

        # Filtro por business_type=equipos
        res = await ac.get('/api/action-notifications/audit-log', headers=admin_h,
                           params={"business_type": "equipos", "limit": 50})
        items = res.json()['items']
        assert all(it['config_key'].startswith('equipos|') for it in items), \
            "filtro business_type=equipos falló"
        print(f"[OK] audit-log filtro business_type=equipos: {len(items)} resultados")

        # Filtro por action_id=approve
        res = await ac.get('/api/action-notifications/audit-log', headers=admin_h,
                           params={"action_id": "approve", "limit": 50})
        items = res.json()['items']
        assert all(it['action_id'] == 'approve' for it in items)
        print(f"[OK] audit-log filtro action_id=approve: {len(items)} resultados")

        # Filtro por quote_number
        res = await ac.get('/api/action-notifications/audit-log', headers=admin_h,
                           params={"quote_number": "COT-AUDIT-001"})
        items = res.json()['items']
        assert len(items) == 1 and items[0]['quote_number'] == 'COT-AUDIT-001'
        print(f"[OK] audit-log filtro quote_number=COT-AUDIT-001: {len(items)} resultado(s)")

        # -------- 4. RBAC: non-admin → 403 --------
        try:
            non_admin_token = await _login(ac, 'srubio@megasoft.com.ve', 'Test1234!')
            non_admin_h = {"Authorization": f"Bearer {non_admin_token}"}
            res = await ac.post('/api/action-notifications/seed-legacy', headers=non_admin_h)
            assert res.status_code == 403, f"expected 403 for non-admin seed, got {res.status_code}"
            res = await ac.get('/api/action-notifications/audit-log', headers=non_admin_h)
            assert res.status_code == 403, f"expected 403 for non-admin audit, got {res.status_code}"
            print("[OK] RBAC: non-admin bloqueado en seed-legacy y audit-log (403)")
        except AssertionError:
            raise
        except Exception as _e:
            print(f"[WARN] No se pudo loguear srubio (RBAC test skipped): {_e}")

        # -------- Cleanup --------
        await db.bitacora.delete_many({"quote_id": {"$in": ["q_audit_test_1", "q_audit_test_2"]}})
        await db.action_notification_configs.delete_one({"config_key": protected_key})
        # Limpiar TODAS las configs creadas por el seeder (auto_seeded=True) para
        # no contaminar tests legacy posteriores (ej. test_repair_complete_admin_pdf
        # depende de que NO haya config dinámica para reparaciones|_|repair_complete).
        cleaned = await db.action_notification_configs.delete_many({"auto_seeded": True})
        print(f"[cleanup] {cleaned.deleted_count} configs auto_seeded eliminadas")

    c.close()


def test_phase3_seed_and_audit():
    asyncio.run(_run())


if __name__ == "__main__":
    test_phase3_seed_and_audit()
    print("\nALL PHASE 3 TESTS PASSED")
