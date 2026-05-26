"""Iteration 19 — Validar que TODAS las variables documentadas en la
acción "Enviar a Implementación" se resuelven correctamente en el motor
dinámico de notificaciones.

Bug reportado por el usuario: {Cantidad_Cajas} aparecía vacío al renderizar
el correo. Verificamos también el resto de aliases en español.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.notification_engine import _build_template_vars, _render  # noqa: E402


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _sample_quote():
    return {
        "quote_id": "test_q_001",
        "quote_number": "COT-2026-02-001-PYME",
        "client_id": None,  # sin lookup en db
        "client_name": "Inversiones ACME, C.A.",
        "client_rif": "J-12345678-9",
        "sede": "PYME",
        "client_segment": "PYME",
        "cantidad_cajas": 12,
        "integrator_name": "Sistemas Andinos C.A.",
        "integrator_app_name": "AndinoPOS",
        "pinpad_model": "Verifone VX820",
        "sponsor_bank_name": "Banco de Venezuela",
        "total_usd": 4520.50,
        "created_by_user_id": None,
        "company_name": "Merchant Server",
    }


def test_cantidad_cajas_se_resuelve():
    """El usuario reportó que {Cantidad_Cajas} venía vacío."""
    vars_ = _run(_build_template_vars(_sample_quote()))
    assert vars_["Cantidad_Cajas"] == "12"
    assert vars_["cantidad_cajas"] == "12"
    assert vars_["cajas"] == "12"


def test_cantidad_cajas_vacio_si_no_existe():
    q = _sample_quote()
    q.pop("cantidad_cajas")
    vars_ = _run(_build_template_vars(q))
    assert vars_["Cantidad_Cajas"] == ""
    assert vars_["cantidad_cajas"] == ""


def test_integrador_y_aliases():
    vars_ = _run(_build_template_vars(_sample_quote()))
    assert vars_["Integrador"] == "Sistemas Andinos C.A."
    assert vars_["integrator_name"] == "Sistemas Andinos C.A."


def test_aplicativo_integracion_y_aliases():
    vars_ = _run(_build_template_vars(_sample_quote()))
    assert vars_["Aplicativo_Integracion"] == "AndinoPOS"
    assert vars_["Aplicativo"] == "AndinoPOS"
    assert vars_["integrator_app_name"] == "AndinoPOS"


def test_pinpad_y_aliases():
    vars_ = _run(_build_template_vars(_sample_quote()))
    assert vars_["Modelo_Pinpad"] == "Verifone VX820"
    assert vars_["Pinpad"] == "Verifone VX820"
    assert vars_["pinpad_model"] == "Verifone VX820"


def test_banco_patrocinador_y_aliases():
    vars_ = _run(_build_template_vars(_sample_quote()))
    assert vars_["Banco_Patrocinador"] == "Banco de Venezuela"
    assert vars_["sponsor_bank_name"] == "Banco de Venezuela"


def test_render_template_con_todas_las_variables():
    """Smoke test del flujo completo: template HTML → variables → output."""
    vars_ = _run(_build_template_vars(_sample_quote()))
    tpl = (
        "Cliente: {Nombre_Cliente}\n"
        "Cotización: {quote_number}\n"
        "Cajas: {Cantidad_Cajas}\n"
        "Integrador: {Integrador}\n"
        "Aplicativo: {Aplicativo_Integracion}\n"
        "Pinpad: {Modelo_Pinpad}\n"
        "Banco: {Banco_Patrocinador}\n"
        "Sede: {Nombre_Sucursal}\n"
    )
    rendered = _render(tpl, vars_)
    assert "Cajas: 12" in rendered, f"Cantidad_Cajas no se renderizó: {rendered}"
    assert "Integrador: Sistemas Andinos C.A." in rendered
    assert "Aplicativo: AndinoPOS" in rendered
    assert "Pinpad: Verifone VX820" in rendered
    assert "Banco: Banco de Venezuela" in rendered
    assert "Cliente: Inversiones ACME, C.A." in rendered
    assert "Sede: PYME" in rendered
    # No deben quedar tokens sin reemplazar
    assert "{" not in rendered or "}" not in rendered, f"Variables sin reemplazar: {rendered}"


def test_double_brace_template_support():
    """Soporte tanto {var} como {{var}}."""
    vars_ = _run(_build_template_vars(_sample_quote()))
    assert _render("Cajas: {{Cantidad_Cajas}}", vars_) == "Cajas: 12"
    assert _render("Cajas: {Cantidad_Cajas}", vars_) == "Cajas: 12"
