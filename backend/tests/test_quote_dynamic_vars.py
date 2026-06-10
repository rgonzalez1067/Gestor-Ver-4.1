"""Regresión: variables dinámicas a nivel de cotización para plantillas de correo.

Asegura que {Matriz_Bancos_Productos}, {Matriz_Sucursales} y {Patrocinador}
se resuelvan desde los datos de la cotización (antes llegaban vacíos).
"""
from services.quote_template_vars import build_quote_dynamic_vars


def test_matrix_bancos_from_additional_items():
    quote = {
        "additional_items": [
            {"bank_name": "Banco Mercantil", "item_name": "Tarjeta Crédito/Débito", "cantidad_cajas": 2},
            {"bank_name": "Banesco", "name": "C2P", "quantity": 1},
        ],
        "branch_details": [],
    }
    v = build_quote_dynamic_vars(quote, client_fantasy="Cliente Demo C.A.")
    mbp = v["Matriz_Bancos_Productos"]
    assert "Banco Mercantil" in mbp and "Banesco" in mbp
    assert "Tarjeta Crédito/Débito" in mbp and "C2P" in mbp
    assert "<table" in mbp


def test_matrix_bancos_fallback_to_services():
    quote = {
        "services": [
            {"item_type": "additional", "bank_name": "BNC", "item_name": "Pago Móvil", "cantidad_cajas": 3},
            {"item_type": "setup", "name": "Setup Inicial"},
        ],
    }
    v = build_quote_dynamic_vars(quote)
    assert "BNC" in v["Matriz_Bancos_Productos"]
    assert "Pago Móvil" in v["Matriz_Bancos_Productos"]


def test_matrix_sucursales_from_branch_details():
    quote = {
        "branch_details": [
            {"store_name": "Sucursal Norte", "quantity": 5},
            {"store_name": "Sucursal Sur", "quantity": 3},
        ],
    }
    v = build_quote_dynamic_vars(quote)
    ms = v["Matriz_Sucursales"]
    assert "Sucursal Norte" in ms and "Sucursal Sur" in ms
    assert "Total" in ms  # fila total cuando hay > 1 sucursal


def test_patrocinador_sponsored():
    quote = {
        "sponsored_implementation": True,
        "sponsoring_bank_name": "Banco Mercantil",
        "sponsoring_processor_name": "Megasoft",
    }
    v = build_quote_dynamic_vars(quote, client_fantasy="No Usar")
    assert v["Patrocinador"] == "Banco Mercantil - Megasoft"


def test_patrocinador_not_sponsored_uses_fantasy():
    quote = {"sponsored_implementation": False}
    v = build_quote_dynamic_vars(quote, client_fantasy="Cliente Demo C.A.", client_legal="CLIENTE DEMO CA")
    assert v["Patrocinador"] == "Cliente Demo C.A."
