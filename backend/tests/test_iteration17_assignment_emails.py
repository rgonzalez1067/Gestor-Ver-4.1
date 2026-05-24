"""Tests Iteration 17 — Notificaciones Automatizadas por Correo
(Asignación de Contactos Iniciales y Proyectos).

Cubre:
- Render del template HTML (subject + variables dinámicas presentes).
- Bitácora de envíos (assignment_email_sent / assignment_email_failed).
- Asincronía: la función pública NO bloquea (retorna inmediatamente).
- Wiring: el endpoint de asignación de contacto dispara el correo (mock).
"""
import os
import sys
import asyncio
import uuid
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import db  # noqa: E402


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------- 1) Plantilla Contacto Inicial: subject + variables ----------
def test_initial_contact_template_includes_required_variables():
    import services.assignment_notifications as an
    captured = {}

    async def fake_send_email(*, to, subject, html, action):
        captured["to"] = to
        captured["subject"] = subject
        captured["html"] = html
        captured["action"] = action
        return {"status": "sent"}

    async def runner():
        # Monkeypatch send_email para evitar SMTP real
        an.send_email = fake_send_email
        contact = {
            "contact_id": "ic_test_001",
            "contact_name": "María Pérez",
            "phone": "+58 414-1234567",
            "email": "maria.perez@ejemplo.com",
            "referred_by": "Página Web",
            "interest_notes": "Implementación VPOS sede principal",
            "due_date": "2026-02-28",
            "legal_name": "Distribuidora Andina C.A.",
        }
        target_user = {
            "user_id": "usr_e2e_001",
            "email": "ejecutivo@meganexus.test",
            "first_name": "Carla",
            "last_name": "Suárez",
        }
        await an.notify_initial_contact_assigned(
            contact=contact, target_user=target_user, assigner_name="Rafael González"
        )
        # Esperamos a que el create_task corra
        await asyncio.sleep(0.3)

    _run(runner())
    assert captured.get("subject") == "Asignación de una nueva tarea de Contacto Inicial"
    assert captured.get("to") == ["ejecutivo@meganexus.test"]
    html = captured.get("html", "")
    # Variables obligatorias por requerimiento del usuario
    for token in [
        "María Pérez",
        "+58 414-1234567",
        "maria.perez@ejemplo.com",
        "Página Web",
        "Implementación VPOS",
        "2026-02-28",
        "Carla Suárez",  # destinatario en el saludo
        "Rafael González",  # asigner
    ]:
        assert token in html, f"Falta '{token}' en el HTML renderizado"
    assert captured.get("action") == "initial_contact_assigned"


# ---------- 2) Plantilla Proyecto: subject dinámico + variables ----------
def test_project_template_subject_and_variables():
    import services.assignment_notifications as an
    captured = {}

    async def fake_send_email(*, to, subject, html, action):
        captured.update({"to": to, "subject": subject, "html": html, "action": action})
        return {"status": "sent"}

    async def runner():
        an.send_email = fake_send_email
        project = {
            "project_id": "prj_test_001",
            "project_number": "PRJ-2026-001",
            "client_id": "cli_x_unused",  # se intenta lookup, no debe romper
            "client_name": "Acme Holdings, C.A.",
            "client_sede": "PYME",
            "quote_type": "VPOS",
            "created_at": "2026-02-10T14:30:00",
            "assigned_at": "2026-02-15T09:45:00",
        }
        target_user = {
            "user_id": "usr_impl_001",
            "email": "implementador@meganexus.test",
            "first_name": "Luis",
            "last_name": "Marín",
        }
        await an.notify_project_assigned(
            project=project,
            target_user=target_user,
            assigner_name="Rafael González",
            executive_name="Sergio Rubio",
        )
        await asyncio.sleep(0.3)

    _run(runner())
    subject = captured.get("subject", "")
    assert subject.startswith("Asignación de nuevo Proyecto de Implementación Cliente :")
    assert "Acme Holdings, C.A." in subject
    html = captured.get("html", "")
    for token in [
        "PRJ-2026-001",
        "Acme Holdings, C.A.",
        "PYME",
        "VPOS",
        "2026-02-10 14:30:00",
        "2026-02-15 09:45:00",
        "Sergio Rubio",
        "Luis Marín",
        "Rafael González",
    ]:
        assert token in html, f"Falta '{token}' en el HTML del proyecto"
    assert captured.get("action") == "project_assigned"


# ---------- 3) Bitácora: assignment_email_sent registrado ----------
def test_bitacora_logs_assignment_email_sent():
    import services.assignment_notifications as an

    suffix = uuid.uuid4().hex[:10]

    async def fake_send_email(*, to, subject, html, action):
        return {"status": "sent"}

    async def runner():
        an.send_email = fake_send_email
        contact = {
            "contact_id": f"ic_bit_{suffix}",
            "contact_name": "Test",
            "email": "x@y.z",
            "referred_by": "X",
            "interest_notes": "Y",
            "due_date": "2026-03-01",
            "legal_name": "Z",
        }
        target = {"user_id": "u1", "email": "t@meganexus.test", "first_name": "T", "last_name": "U"}
        await an.notify_initial_contact_assigned(
            contact=contact, target_user=target, assigner_name="Tester"
        )
        await asyncio.sleep(0.5)
        rec = await db.bitacora.find_one({
            "reference_id": contact["contact_id"],
            "action": "assignment_email_sent",
        })
        return rec

    rec = _run(runner())
    assert rec is not None, "No se registró entrada en bitácora"
    assert rec["sub_action"] == "initial_contact_assigned"
    assert rec["to"] == ["t@meganexus.test"]


# ---------- 4) Asincronía: el caller no espera al envío ----------
def test_notify_returns_immediately_when_send_is_slow():
    """`notify_*` usa asyncio.create_task → debe retornar de inmediato aun si
    el envío tarda. Validamos midiendo el tiempo del await público.
    """
    import services.assignment_notifications as an

    async def slow_send_email(*, to, subject, html, action):
        await asyncio.sleep(2.0)  # simula SMTP lento
        return {"status": "sent"}

    async def runner():
        an.send_email = slow_send_email
        contact = {
            "contact_id": "ic_async",
            "contact_name": "Async",
            "email": "a@b.c",
            "referred_by": "Test",
            "interest_notes": "Test",
            "due_date": "2026-01-01",
            "legal_name": "Async LLC",
        }
        target = {"user_id": "u_async", "email": "x@meganexus.test", "first_name": "A", "last_name": "B"}
        t0 = time.monotonic()
        await an.notify_initial_contact_assigned(
            contact=contact, target_user=target, assigner_name="X"
        )
        elapsed = time.monotonic() - t0
        return elapsed

    elapsed = _run(runner())
    # Debe haber retornado MUY rápido (<0.5s) — el envío de 2s corre en background
    assert elapsed < 0.5, f"notify NO retorna inmediato: tardó {elapsed:.2f}s"


# ---------- 5) Sin email destino: no rompe ----------
def test_no_email_does_not_call_send():
    import services.assignment_notifications as an
    called = {"flag": False}

    async def trapped(*a, **kw):
        called["flag"] = True
        return {"status": "sent"}

    async def runner():
        an.send_email = trapped
        await an.notify_initial_contact_assigned(
            contact={"contact_id": "x", "legal_name": "X"},
            target_user={"user_id": "u", "email": "", "first_name": "X"},
        )
        await asyncio.sleep(0.2)

    _run(runner())
    assert called["flag"] is False, "send_email no debe llamarse sin destinatario"


# ---------- 6) Wiring: endpoint /assign de contacto dispara el correo ----------
def test_assign_initial_contact_endpoint_triggers_email():
    """Inserta un contacto y un usuario destino reales en BD, llama al endpoint
    `assign_initial_contact` directamente y verifica que se llamó al servicio.
    """
    from routes.initial_contacts import assign_initial_contact, InitialContactAssign
    import services.assignment_notifications as an

    suffix = uuid.uuid4().hex[:8]
    contact_id = f"ic_wire_{suffix}"
    target_user_id = f"usr_wire_{suffix}"

    captured = {"called": False}

    async def stub_notify(*, contact, target_user, assigner_name=""):
        captured["called"] = True
        captured["contact_id"] = contact.get("contact_id")
        captured["target_email"] = target_user.get("email")
        captured["assigner"] = assigner_name

    # Inyectamos también una versión que NO toque SMTP en el módulo de notify
    async def runner():
        import routes.initial_contacts as ic_module
        original_notify = ic_module.notify_initial_contact_assigned
        ic_module.notify_initial_contact_assigned = stub_notify

        # Seed: usuario admin + usuario destino + contacto
        admin = {
            "user_id": f"adm_wire_{suffix}",
            "email": f"admin_{suffix}@meganexus.test",
            "first_name": "Admin",
            "last_name": "Wire",
            "role": "admin",
            "cargo": "Director",
            "sede": "PYME",
            "is_active": True,
        }
        target = {
            "user_id": target_user_id,
            "email": f"target_{suffix}@meganexus.test",
            "first_name": "Target",
            "last_name": "Wire",
            "role": "user",
            "cargo": "Ejecutivo",
            "sede": "PYME",
            "is_active": True,
        }
        contact = {
            "contact_id": contact_id,
            "contact_name": "Lead Wire",
            "phone": "+58000",
            "email": "lead@x.com",
            "legal_name": "Wire Test SA",
            "interest_notes": "test",
            "referred_by": "test",
            "due_date": "2026-04-01",
            "assigned_to_user_id": admin["user_id"],
            "assigned_to_name": "Admin Wire",
            "sede": "PYME",
            "is_converted": False,
            "created_by_user_id": admin["user_id"],
            "created_by_name": "Admin Wire",
            "created_at": "2026-02-20T10:00:00",
            "updated_at": "2026-02-20T10:00:00",
            "bitacora": [],
        }
        await db.users.insert_one(dict(admin))
        await db.users.insert_one(dict(target))
        await db.initial_contacts.insert_one(dict(contact))

        # Monkey-patch get_current_user para devolver al admin sin token
        import routes.initial_contacts as icm
        async def fake_get_current_user(authorization):  # noqa: ARG001
            return dict(admin)
        # patch módulo
        icm.get_current_user = fake_get_current_user

        try:
            resp = await assign_initial_contact(
                contact_id=contact_id,
                data=InitialContactAssign(assigned_to_user_id=target_user_id, comment="prueba"),
                authorization="x",
            )
        finally:
            ic_module.notify_initial_contact_assigned = original_notify

        # Limpieza
        await db.users.delete_many({"user_id": {"$in": [admin["user_id"], target_user_id]}})
        await db.initial_contacts.delete_one({"contact_id": contact_id})
        return resp

    resp = _run(runner())
    assert resp.get("assigned_to") == "Target Wire"
    assert captured["called"] is True
    assert captured["contact_id"] == contact_id
    assert captured["target_email"].startswith("target_")
    assert "Admin Wire" in captured["assigner"]
