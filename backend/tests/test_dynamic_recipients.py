# ruff: noqa
"""Regresión del destinatario dinámico 'Usuario Implementador'.

Valida la resolución en runtime y la política de contingencia (fallback) de
`services.dynamic_recipients.resolve_project_implementer`.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import services.dynamic_recipients as dr


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _fake_db(find_one):
    return SimpleNamespace(users=SimpleNamespace(find_one=find_one))


def test_resolves_assigned_implementer(monkeypatch):
    """Caso normal: proyecto con implementador → su correo, sin fallback."""
    monkeypatch.setattr(dr, "_resolve_user_email", AsyncMock(return_value=("juan@megasoft.com.ve", "Juan Pérez")))
    project = {"project_number": "PRY-1", "assigned_to_user_id": "user_juan"}
    email, name, uid, note = _run(dr.resolve_project_implementer(project))
    assert email == "juan@megasoft.com.ve"
    assert uid == "user_juan"
    assert note is None  # implementador real, sin contingencia


def test_fallback_to_coordinator(monkeypatch):
    """Sin implementador → Coordinador de Implementación, con nota de fallback."""
    monkeypatch.setattr(dr, "_resolve_user_email", AsyncMock(return_value=None))
    coord = {"email": "coord@megasoft.com.ve", "first_name": "Kelly", "last_name": "Coord", "user_id": "user_coord"}
    monkeypatch.setattr(dr, "db", _fake_db(AsyncMock(return_value=coord)))
    email, name, uid, note = _run(dr.resolve_project_implementer({"assigned_to_user_id": None}))
    assert email == "coord@megasoft.com.ve"
    assert uid == "user_coord"
    assert note and "Coordinador" in note


def test_fallback_to_admin(monkeypatch):
    """Sin implementador ni coordinador → Administrador."""
    monkeypatch.setattr(dr, "_resolve_user_email", AsyncMock(return_value=None))
    admin = {"email": "admin@megasoft.com.ve", "first_name": "Rafael", "last_name": "Admin", "user_id": "user_admin"}
    # Primera llamada (coordinador) → None; segunda (admin) → admin.
    monkeypatch.setattr(dr, "db", _fake_db(AsyncMock(side_effect=[None, admin])))
    email, name, uid, note = _run(dr.resolve_project_implementer({"assigned_to_user_id": None}))
    assert email == "admin@megasoft.com.ve"
    assert uid == "user_admin"
    assert note and "Administrador" in note


def test_no_recipient_available(monkeypatch):
    """Sin implementador, coordinador ni admin → vacío con nota descriptiva."""
    monkeypatch.setattr(dr, "_resolve_user_email", AsyncMock(return_value=None))
    monkeypatch.setattr(dr, "db", _fake_db(AsyncMock(return_value=None)))
    email, name, uid, note = _run(dr.resolve_project_implementer(None))
    assert email == ""
    assert uid is None
    assert note  # describe la imposibilidad de resolver
