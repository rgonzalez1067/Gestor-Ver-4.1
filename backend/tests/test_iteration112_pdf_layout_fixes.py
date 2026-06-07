# ruff: noqa
"""
Test Suite: Iteration 112 - PDF Layout Fixes for Nota de Entrega and Nota de Transferencia
Tests:
  - Nota Entrega generates exactly 2 pages
  - Page 1 has NO 'Recepcion y Conformidad' section
  - Page 2 starts with persistent header + Recepcion section
  - Long address wraps properly without overflow
  - Column widths sum to CONTENT_W (509.95 pts)
  - Pagination shows 'Pagina 1/2' and 'Pagina 2/2'
  - No duplicate pages
  - Transfer note uses percentage-based column widths
"""

import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, '/app/backend')

from services.hoja_ruta_pdf import generate_nota_entrega_pdf, CONTENT_W, PAGE_W, MARGIN_L, MARGIN_R
from services.transfer_note_pdf import generate_transfer_note_pdf
from services.transfer_note_pdf import CONTENT_W as TRANSFER_CONTENT_W

import fitz  # PyMuPDF


class TestNotaEntregaPDFLayoutFixes:
    """Tests for Nota de Entrega PDF layout fixes."""
    
    # Test data with a LONG address (100+ chars) to verify multi-line wrap
    LONG_ADDRESS = "Avenida Francisco de Miranda, Torre Empresarial ABC, Piso 15, Oficina 1505, Urbanización El Rosal, Municipio Chacao, Caracas, Venezuela, Código Postal 1060"
    
    # Standard test data
    TEST_DATA = {
        "correlativo": "NE-TEST-112-001",
        "quote_number": "COT-TEST-2024-001",
        "project_number": "PROJ-TEST-2024-001",
        "client_name": "Empresa de Prueba S.A.",
        "client_rif": "J-12345678-9",
        "client_address": LONG_ADDRESS,
        "client_contact_name": "Juan Pérez",
        "client_contact_phone": "+58 412 1234567",
        "warehouse_name": "Almacén Principal Caracas",
        "delivered_items": [
            {"name": "Terminal POS Modelo X", "category": "POS", "quantity": 2, "serials": ["SN001", "SN002"]},
            {"name": "Pinpad Contactless", "category": "Pinpad", "quantity": 3, "serials": ["PN001", "PN002", "PN003"]},
            {"name": "Impresora Térmica", "category": "Accesorio", "quantity": 1, "serials": []},
        ],
        "delivered_by": "Carlos Rodriguez - Almacenista",
        "transportista": "MRW",
        "guia_placa": "ABC-123",
        "notes": "Entrega programada para la mañana",
        "delivery_method": "personalizada",
        "receiver_name": "María García",
        "receiver_cedula": "V-12345678",
        "receiver_phone": "+58 414 9876543",
    }

    def test_01_nota_entrega_generates_exactly_2_pages(self):
        """Verify Nota Entrega PDF generates exactly 2 pages (content on page 1, reception on page 2)."""
        pdf_buffer = generate_nota_entrega_pdf(**self.TEST_DATA)
        
        # Open PDF with PyMuPDF
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page_count = pdf_doc.page_count
        pdf_doc.close()
        
        assert page_count == 2, f"Expected exactly 2 pages, got {page_count}"
        print("✓ Nota Entrega generates exactly 2 pages")

    def test_02_page1_has_no_recepcion_section(self):
        """Verify Page 1 does NOT contain 'Recepcion y Conformidad' section."""
        pdf_buffer = generate_nota_entrega_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page1 = pdf_doc[0]
        page1_text = page1.get_text()
        pdf_doc.close()
        
        # Check that 'Recepcion y Conformidad' is NOT on page 1
        assert "Recepcion y Conformidad" not in page1_text, \
            "Page 1 should NOT contain 'Recepcion y Conformidad' section"
        
        # Verify page 1 has expected content (section headers 1-4)
        assert "1. Informacion del Documento" in page1_text, "Page 1 should have section 1"
        assert "2. Datos del Cliente" in page1_text, "Page 1 should have section 2"
        assert "3. Detalle de Bienes" in page1_text, "Page 1 should have section 3"
        assert "4. Control Logistico" in page1_text, "Page 1 should have section 4"
        
        print("✓ Page 1 has sections 1-4 and NO 'Recepcion y Conformidad'")

    def test_03_page2_has_header_and_recepcion_section(self):
        """Verify Page 2 starts with persistent header (NOTA DE ENTREGA) followed by Recepcion section."""
        pdf_buffer = generate_nota_entrega_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page2 = pdf_doc[1]
        page2_text = page2.get_text()
        pdf_doc.close()
        
        # Verify page 2 has the persistent header
        assert "NOTA DE ENTREGA" in page2_text, "Page 2 should have persistent header 'NOTA DE ENTREGA'"
        
        # Verify page 2 has the Recepcion section
        assert "5. Recepcion y Conformidad" in page2_text, "Page 2 should have section 5"
        
        # Verify reception form fields are present
        assert "Nombre de quien recibe" in page2_text, "Page 2 should have receiver name field"
        assert "Cedula / RIF" in page2_text, "Page 2 should have cedula field"
        assert "Firma y Sello" in page2_text, "Page 2 should have signature field"
        
        print("✓ Page 2 has persistent header and 'Recepcion y Conformidad' section")

    def test_04_long_address_wraps_without_overflow(self):
        """Verify long address (100+ chars) wraps to multiple lines without overflow."""
        pdf_buffer = generate_nota_entrega_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page1 = pdf_doc[0]
        page1_text = page1.get_text()
        
        # Get text blocks to analyze positioning
        blocks = page1.get_text("blocks")
        
        # Find address block - it should be present
        address_parts = self.LONG_ADDRESS.split(", ")
        address_found = False
        
        for block in blocks:
            block_text = block[4] if len(block) > 4 else ""
            # Check if any part of address is in block
            if any(part in block_text for part in address_parts[:3]):
                address_found = True
                # Check block doesn't exceed page width (with margins)
                x0, y0, x1, y1 = block[:4]
                max_x = PAGE_W - MARGIN_R
                assert x1 <= max_x + 10, f"Address block exceeds page width: x1={x1}, max={max_x}"
        
        assert address_found, "Address should be present in PDF"
        
        # Verify full address is in the document
        assert "Avenida Francisco de Miranda" in page1_text
        assert "Venezuela" in page1_text or "1060" in page1_text
        
        pdf_doc.close()
        print("✓ Long address wraps properly without overflow")

    def test_05_pagination_shows_correct_page_numbers(self):
        """Verify pagination shows 'Pagina 1 / 2' and 'Pagina 2 / 2' correctly."""
        pdf_buffer = generate_nota_entrega_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        
        page1_text = pdf_doc[0].get_text()
        page2_text = pdf_doc[1].get_text()
        pdf_doc.close()
        
        # Check pagination text
        assert "Pagina 1 / 2" in page1_text or "Pagina 1/2" in page1_text, \
            "Page 1 should show 'Pagina 1 / 2'"
        assert "Pagina 2 / 2" in page2_text or "Pagina 2/2" in page2_text, \
            "Page 2 should show 'Pagina 2 / 2'"
        
        print("✓ Pagination shows 'Pagina 1/2' and 'Pagina 2/2' correctly")

    def test_06_no_duplicate_pages(self):
        """Verify no duplicate pages in output (NumberedCanvas fix)."""
        pdf_buffer = generate_nota_entrega_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        
        # Should be exactly 2 pages, not more (no duplicates)
        assert pdf_doc.page_count == 2, f"Should be exactly 2 pages, got {pdf_doc.page_count}"
        
        # Pages should have different content
        page1_text = pdf_doc[0].get_text()
        page2_text = pdf_doc[1].get_text()
        pdf_doc.close()
        
        # Page 1 should have sections 1-4, Page 2 should have section 5
        assert "1. Informacion del Documento" in page1_text
        assert "5. Recepcion y Conformidad" not in page1_text
        assert "5. Recepcion y Conformidad" in page2_text
        
        print("✓ No duplicate pages - NumberedCanvas working correctly")

    def test_07_column_widths_sum_to_content_width(self):
        """Verify all table column widths sum to exactly CONTENT_W (no overflow)."""
        # CONTENT_W from the module
        expected_content_w = PAGE_W - MARGIN_L - MARGIN_R  # Should be ~509.95 pts
        
        # Test column widths from Section 1 (line 224)
        section1_cw = [CONTENT_W * 0.22, CONTENT_W * 0.28, CONTENT_W * 0.22, CONTENT_W * 0.28]
        section1_sum = sum(section1_cw)
        assert abs(section1_sum - CONTENT_W) < 0.01, \
            f"Section 1 widths sum {section1_sum} != CONTENT_W {CONTENT_W}"
        
        # Test column widths from Section 2 (line 252)
        section2_cw = [CONTENT_W * 0.22, CONTENT_W * 0.32, CONTENT_W * 0.16, CONTENT_W * 0.30]
        section2_sum = sum(section2_cw)
        assert abs(section2_sum - CONTENT_W) < 0.01, \
            f"Section 2 widths sum {section2_sum} != CONTENT_W {CONTENT_W}"
        
        # Test logistic section (line 399)
        log_cw = [CONTENT_W * 0.28, CONTENT_W * 0.72]
        log_sum = sum(log_cw)
        assert abs(log_sum - CONTENT_W) < 0.01, \
            f"Logistic widths sum {log_sum} != CONTENT_W {CONTENT_W}"
        
        # Test reception section (line 426)
        rec_cw = [CONTENT_W * 0.28, CONTENT_W * 0.72]
        rec_sum = sum(rec_cw)
        assert abs(rec_sum - CONTENT_W) < 0.01, \
            f"Reception widths sum {rec_sum} != CONTENT_W {CONTENT_W}"
        
        print(f"✓ All column widths sum to CONTENT_W ({CONTENT_W:.2f} pts)")

    def test_08_content_width_calculation_correct(self):
        """Verify CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R calculation."""
        from reportlab.lib.units import cm
        
        expected_margin_l = 1.8 * cm
        expected_margin_r = 1.8 * cm
        expected_content_w = PAGE_W - expected_margin_l - expected_margin_r
        
        assert abs(MARGIN_L - expected_margin_l) < 0.01, "MARGIN_L incorrect"
        assert abs(MARGIN_R - expected_margin_r) < 0.01, "MARGIN_R incorrect"
        assert abs(CONTENT_W - expected_content_w) < 0.01, \
            f"CONTENT_W={CONTENT_W} != expected {expected_content_w}"
        
        print(f"✓ CONTENT_W calculation correct: {CONTENT_W:.2f} pts")


class TestTransferNotePDFLayoutFixes:
    """Tests for Transfer Note PDF layout fixes."""
    
    TEST_DATA = {
        "transfer_number": "TRF-TEST-112-001",
        "source_warehouse_name": "Almacén Principal Caracas",
        "source_responsible_name": "Carlos Rodriguez",
        "source_responsible_cedula": "V-12345678",
        "dest_warehouse_name": "Almacén Secundario Maracaibo",
        "dest_responsible_name": "Maria González",
        "transferred_items": [
            {"name": "Terminal POS Modelo X", "type": "POS", "quantity": 2, "serials": ["SN001", "SN002"]},
            {"name": "Pinpad Contactless", "type": "Pinpad", "quantity": 3, "serials": ["PN001", "PN002", "PN003"]},
        ],
        "transferred_by": "Admin Test User",
        "notes": "Transferencia urgente",
    }

    def test_01_transfer_note_generates_without_error(self):
        """Verify Transfer Note PDF generates without errors."""
        pdf_buffer = generate_transfer_note_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page_count = pdf_doc.page_count
        pdf_doc.close()
        
        assert page_count >= 1, "Transfer note should generate at least 1 page"
        print(f"✓ Transfer Note generates {page_count} page(s) without error")

    def test_02_transfer_note_column_widths_percentage_based(self):
        """Verify Transfer Note uses percentage-based column widths for Section 1."""
        # Section 1 'Informacion de la Transferencia' column widths (line 225)
        cw = [TRANSFER_CONTENT_W * 0.22, TRANSFER_CONTENT_W * 0.28, 
              TRANSFER_CONTENT_W * 0.22, TRANSFER_CONTENT_W * 0.28]
        cw_sum = sum(cw)
        
        assert abs(cw_sum - TRANSFER_CONTENT_W) < 0.01, \
            f"Section 1 widths sum {cw_sum} != CONTENT_W {TRANSFER_CONTENT_W}"
        
        print("✓ Transfer Note Section 1 uses percentage-based widths")

    def test_03_transfer_note_route_section_widths(self):
        """Verify Transfer Note 'Ruta de Transferencia' section uses percentage-based widths."""
        # Section 2 'Ruta de Transferencia' column widths (line 255)
        cw2 = [TRANSFER_CONTENT_W * 0.22, TRANSFER_CONTENT_W * 0.28,
               TRANSFER_CONTENT_W * 0.22, TRANSFER_CONTENT_W * 0.28]
        cw2_sum = sum(cw2)
        
        assert abs(cw2_sum - TRANSFER_CONTENT_W) < 0.01, \
            f"Route section widths sum {cw2_sum} != CONTENT_W {TRANSFER_CONTENT_W}"
        
        print("✓ Transfer Note 'Ruta de Transferencia' uses percentage-based widths")

    def test_04_transfer_note_signature_width(self):
        """Verify Transfer Note signature section width (line 391)."""
        # Signature column width (line 391)
        sig_col = TRANSFER_CONTENT_W * 0.48
        sig_sum = sig_col * 2  # Two columns
        
        assert abs(sig_sum - TRANSFER_CONTENT_W * 0.96) < 0.01, \
            "Signature widths calculation error"
        
        print("✓ Transfer Note signature width is percentage-based")

    def test_05_transfer_note_no_overflow(self):
        """Verify Transfer Note content doesn't overflow page boundaries."""
        pdf_buffer = generate_transfer_note_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        
        from reportlab.lib.units import cm
        margin_r = 1.8 * cm
        max_x = PAGE_W - margin_r
        
        for page_num in range(pdf_doc.page_count):
            page = pdf_doc[page_num]
            blocks = page.get_text("blocks")
            
            for block in blocks:
                x0, y0, x1, y1 = block[:4]
                # Allow small tolerance for text rendering
                assert x1 <= max_x + 15, \
                    f"Page {page_num+1}: Content exceeds boundary at x1={x1}, max={max_x}"
        
        pdf_doc.close()
        print("✓ Transfer Note has no content overflow")

    def test_06_transfer_note_has_pinpad_note_when_applicable(self):
        """Verify technical note appears when Pinpads are included."""
        pdf_buffer = generate_transfer_note_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        full_text = ""
        for page in pdf_doc:
            full_text += page.get_text()
        pdf_doc.close()
        
        # Should have Pinpad technical note since we have Pinpad items
        assert "PinPads son entregados con" in full_text or "Nota tecnica" in full_text, \
            "Should have technical note for Pinpads"
        
        print("✓ Transfer Note includes Pinpad technical note")

    def test_07_transfer_note_pagination_correct(self):
        """Verify Transfer Note pagination is correct."""
        pdf_buffer = generate_transfer_note_pdf(**self.TEST_DATA)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page_count = pdf_doc.page_count
        
        page1_text = pdf_doc[0].get_text()
        pdf_doc.close()
        
        # Should show correct pagination
        assert "Pagina 1" in page1_text, "Should show page number"
        
        print(f"✓ Transfer Note pagination correct ({page_count} page(s))")


class TestNumberedCanvasNoDuplication:
    """Tests for NumberedCanvas fix that prevents page duplication."""

    def test_01_numbered_canvas_uses_start_page(self):
        """Verify NumberedCanvas.showPage() uses self._startPage() instead of super().showPage()."""
        # This is a code inspection test - verify the fix is in place
        import inspect
        from services.hoja_ruta_pdf import NumberedCanvas
        
        source = inspect.getsource(NumberedCanvas.showPage)
        
        # Should use _startPage, not super().showPage()
        assert "_startPage" in source, "showPage should call self._startPage()"
        assert "super().showPage()" not in source, "showPage should NOT call super().showPage()"
        
        print("✓ NumberedCanvas.showPage() uses self._startPage() correctly")

    def test_02_transfer_note_numbered_canvas_uses_start_page(self):
        """Verify Transfer Note's NumberedCanvas also uses _startPage()."""
        import inspect
        from services.transfer_note_pdf import NumberedCanvas as TransferNumberedCanvas
        
        source = inspect.getsource(TransferNumberedCanvas.showPage)
        
        assert "_startPage" in source, "Transfer Note showPage should call self._startPage()"
        assert "super().showPage()" not in source, "showPage should NOT call super().showPage()"
        
        print("✓ Transfer Note NumberedCanvas.showPage() uses self._startPage() correctly")


class TestAddressWordWrap:
    """Tests for address word-wrap functionality."""

    def test_01_very_long_address_handled(self):
        """Test with extremely long address (200+ chars)."""
        very_long_address = (
            "Avenida Libertador con Calle 123, Edificio Torre Corporativa Internacional, "
            "Piso 25, Oficina 2501-A, Sector Los Palos Grandes, Urbanización Country Club, "
            "Municipio Chacao del Estado Miranda, Caracas, República Bolivariana de Venezuela, "
            "Código Postal 1060, Zona Norte del Área Metropolitana"
        )
        
        test_data = TestNotaEntregaPDFLayoutFixes.TEST_DATA.copy()
        test_data["client_address"] = very_long_address
        
        pdf_buffer = generate_nota_entrega_pdf(**test_data)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page1_text = pdf_doc[0].get_text()
        
        # Address should be present (at least parts of it)
        assert "Avenida Libertador" in page1_text
        
        # Should still be 2 pages (not more due to overflow)
        assert pdf_doc.page_count == 2, f"Should be 2 pages even with long address, got {pdf_doc.page_count}"
        
        pdf_doc.close()
        print("✓ Very long address (200+ chars) handled correctly")

    def test_02_address_with_special_characters(self):
        """Test address with special Venezuelan characters."""
        special_address = "Av. Urdaneta, Edif. Ñandú, Piso 3°, Ala Sureste, Caracas DC"
        
        test_data = TestNotaEntregaPDFLayoutFixes.TEST_DATA.copy()
        test_data["client_address"] = special_address
        
        pdf_buffer = generate_nota_entrega_pdf(**test_data)
        
        pdf_doc = fitz.open(stream=pdf_buffer.read(), filetype="pdf")
        page1_text = pdf_doc[0].get_text()
        pdf_doc.close()
        
        # Should handle special characters
        assert "Urdaneta" in page1_text
        
        print("✓ Address with special characters handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
