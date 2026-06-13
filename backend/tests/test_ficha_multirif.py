"""
Regresión VPOS Multi-RIF (Fase 4.5): la Ficha Técnica de Implementación debe
incluir el "Detalle de Tiendas y Sucursales" jerárquico (Cliente/RIF ->
Sucursales -> Cajas) cuando el proyecto/cotización es Multi-RIF, análogo a lo
que ya genera el PDF de cotización (pdf_generator._build_multirif_section).
"""
import io
from services.implementation_pdf import generate_implementation_pdf
from pdfminer.high_level import extract_text


def _multirif_quote():
    return {
        "quote_number": "COT-MR-001",
        "quote_type": "VPOS_MULTIRIF",
        "cantidad_cajas": 10,
        "is_multirif": True,
        "client_name": "Lote Banco X (Multi-RIF)",
        "multirif_distribution": [
            {
                "client_name": "Comercio A C.A.",
                "rif": "J-12345678-9",
                "boxes": 6,
                "stores": [
                    {"name": "Tienda Centro", "boxes": 4},
                    {"name": "Tienda Este", "boxes": 2},
                ],
            },
            {
                "client_name": "Comercio B C.A.",
                "rif": "J-98765432-1",
                "boxes": 4,
                "stores": [{"name": "Sucursal Norte", "boxes": 4}],
            },
        ],
    }


def test_ficha_includes_multirif_hierarchy():
    pdf = generate_implementation_pdf(_multirif_quote(), {"legal_name": "Banco X", "rif": "J-000"}, [], [])
    txt = extract_text(io.BytesIO(pdf))
    # Encabezado de la sección Multi-RIF
    assert "DETALLE DE TIENDAS Y SUCURSALES" in txt
    # RIFs y sucursales presentes
    assert "Comercio A C.A." in txt
    assert "J-12345678-9" in txt
    assert "Tienda Centro" in txt
    assert "Sucursal Norte" in txt
    # Total general = 6 + 4 = 10
    assert "TOTAL GENERAL" in txt


def test_ficha_falls_back_to_flat_branches_when_not_multirif():
    quote = {"quote_number": "COT-STD-001", "quote_type": "VPOS", "cantidad_cajas": 5}
    pdf = generate_implementation_pdf(quote, {"legal_name": "Cliente Z"}, [], [{"store_name": "Sede Unica", "quantity": 5}])
    txt = extract_text(io.BytesIO(pdf))
    assert "DISTRIBUCION LOGISTICA" in txt
    assert "DETALLE DE TIENDAS Y SUCURSALES" not in txt
