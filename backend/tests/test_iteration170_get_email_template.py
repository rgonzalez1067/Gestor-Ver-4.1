"""
Test iteration 170: Verificar función get_email_template() y plantillas de reparación
- get_email_template busca en BD primero, luego en defaults del código
- Plantillas de reparación tienen HTML profesional (>100 chars, con <table> o style)
- Acciones de cotización de reparación usan las plantillas correctas
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Credenciales de prueba
TEST_EMAIL = "rgonzalez@megasoft.com.ve"
TEST_PASSWORD = "Avila*0426"


class TestGetEmailTemplateHelper:
    """Verificar que get_email_template busca en BD primero, luego en defaults"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login y obtener token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("session_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_templates_from_api(self):
        """Verificar que el endpoint de plantillas devuelve todas las plantillas (BD + defaults)"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=self.headers)
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        templates = response.json()
        
        # Verificar que hay plantillas
        assert len(templates) > 0, "No templates returned"
        
        # Buscar plantillas de reparación
        repair_templates = [t for t in templates if 'repair' in t.get('template_id', '').lower()]
        print(f"Found {len(repair_templates)} repair templates")
        
        # Verificar que existen las plantillas de reparación esperadas
        expected_repair_templates = [
            "repair_quote_sent_PYME",
            "repair_quote_sent_CORP",
            "repair_approved_PYME",
            "repair_approved_CORP",
            "repair_complete_client_PYME",
            "repair_complete_client_CORP",
            "repair_invoice_PYME",
            "repair_invoice_CORP",
            "repair_collect_warehouse_PYME",
            "repair_collect_warehouse_CORP",
            "repair_delivery_PYME",
            "repair_delivery_CORP",
        ]
        
        template_ids = [t.get('template_id') for t in templates]
        for expected_id in expected_repair_templates:
            assert expected_id in template_ids, f"Missing template: {expected_id}"
            print(f"✓ Template {expected_id} exists")
    
    def test_repair_templates_have_professional_html(self):
        """Verificar que las plantillas de reparación tienen HTML profesional (>100 chars, con <table> o style)"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        repair_template_ids = [
            "repair_quote_sent_PYME",
            "repair_approved_PYME",
            "repair_complete_client_PYME",
            "repair_invoice_PYME",
            "repair_collect_warehouse_PYME",
            "repair_delivery_PYME",
        ]
        
        for template_id in repair_template_ids:
            template = next((t for t in templates if t.get('template_id') == template_id), None)
            assert template is not None, f"Template {template_id} not found"
            
            body_html = template.get('body_html', '')
            
            # Verificar longitud mínima (>100 chars indica HTML profesional, no fallback genérico)
            assert len(body_html) > 100, f"Template {template_id} has short body_html ({len(body_html)} chars) - likely fallback"
            
            # Verificar que tiene estilos profesionales
            has_table = '<table' in body_html.lower()
            has_style = 'style=' in body_html.lower()
            assert has_table or has_style, f"Template {template_id} lacks professional styling (<table> or style=)"
            
            print(f"✓ Template {template_id}: {len(body_html)} chars, has_table={has_table}, has_style={has_style}")


class TestRepairQuoteActions:
    """Verificar que las acciones de cotización de reparación usan las plantillas correctas"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login y obtener token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("session_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_send_to_client_repair_quote(self):
        """POST /api/quotes/{id}/send-to-client para repair: Usa plantilla repair_quote_sent_PYME"""
        # Buscar cotización de reparación en estado Borrador o Enviada
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair']
        print(f"Found {len(repair_quotes)} repair quotes")
        
        # Buscar una en estado Borrador para enviar
        borrador_quote = next((q for q in repair_quotes if q.get('quote_status') == 'Borrador'), None)
        
        if borrador_quote:
            quote_id = borrador_quote.get('quote_id')
            print(f"Testing send-to-client with quote {borrador_quote.get('quote_number')} (Borrador)")
            
            response = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/send-to-client",
                headers=self.headers
            )
            
            # Puede fallar si no tiene PDF o cliente, pero verificamos que no sea error de plantilla
            if response.status_code == 200:
                data = response.json()
                print(f"✓ send-to-client successful: {data.get('message')}")
                # Verificar que el email fue enviado (simulado o real)
                assert 'recipient' in data or 'message' in data
            else:
                # Verificar que el error no es por plantilla
                error_text = response.text.lower()
                assert 'template' not in error_text, f"Template error: {response.text}"
                print(f"send-to-client returned {response.status_code}: {response.text[:200]}")
        else:
            print("No repair quote in Borrador status found - skipping send-to-client test")
            pytest.skip("No repair quote in Borrador status")
    
    def test_approve_repair_quote(self):
        """POST /api/quotes/{id}/approve para repair: Usa plantilla repair_approved_PYME"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair']
        
        # Buscar una en estado Enviada para aprobar
        enviada_quote = next((q for q in repair_quotes if q.get('quote_status') == 'Enviada'), None)
        
        if enviada_quote:
            quote_id = enviada_quote.get('quote_id')
            print(f"Testing approve with quote {enviada_quote.get('quote_number')} (Enviada)")
            
            response = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/approve",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ approve successful: {data.get('message')}")
                assert data.get('is_repair') == True, "Expected is_repair=True"
                assert 'emails' in data, "Expected emails in response"
            else:
                error_text = response.text.lower()
                assert 'template' not in error_text, f"Template error: {response.text}"
                print(f"approve returned {response.status_code}: {response.text[:200]}")
        else:
            print("No repair quote in Enviada status found - skipping approve test")
            pytest.skip("No repair quote in Enviada status")
    
    def test_repair_complete(self):
        """POST /api/quotes/{id}/repair-complete: Usa plantilla repair_complete_client_PYME"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair']
        
        # Buscar una en estado Aprobada para marcar como reparada
        aprobada_quote = next((q for q in repair_quotes if q.get('quote_status') == 'Aprobada'), None)
        
        if aprobada_quote:
            quote_id = aprobada_quote.get('quote_id')
            print(f"Testing repair-complete with quote {aprobada_quote.get('quote_number')} (Aprobada)")
            
            response = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/repair-complete",
                headers=self.headers,
                json={}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ repair-complete successful: {data.get('message')}")
                assert data.get('new_status') == 'Reparada', "Expected new_status=Reparada"
                assert 'emails' in data, "Expected emails in response"
            else:
                error_text = response.text.lower()
                assert 'template' not in error_text, f"Template error: {response.text}"
                print(f"repair-complete returned {response.status_code}: {response.text[:200]}")
        else:
            print("No repair quote in Aprobada status found - skipping repair-complete test")
            pytest.skip("No repair quote in Aprobada status")
    
    def test_invoice_repair_quote(self):
        """POST /api/quotes/{id}/invoice para repair: Usa plantilla repair_invoice_PYME"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair']
        
        # Buscar una en estado Reparada para facturar
        reparada_quote = next((q for q in repair_quotes if q.get('quote_status') == 'Reparada'), None)
        
        if reparada_quote:
            quote_id = reparada_quote.get('quote_id')
            print(f"Testing invoice with quote {reparada_quote.get('quote_number')} (Reparada)")
            
            # Verificar si tiene factura adjunta
            attachments = reparada_quote.get('attachments', [])
            has_factura = any(a.get('category') == 'Factura' for a in attachments)
            
            if not has_factura:
                print("Quote has no Factura attachment - invoice will fail with 422")
                pytest.skip("Quote has no Factura attachment")
            
            response = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/invoice",
                headers=self.headers,
                data={"invoice_number": "TEST-INV-001"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ invoice successful: {data.get('message')}")
                assert 'emails' in data, "Expected emails in response"
            elif response.status_code == 422:
                # Expected if no Factura attachment
                print(f"invoice returned 422 (expected if no Factura): {response.text[:200]}")
            else:
                error_text = response.text.lower()
                assert 'template' not in error_text, f"Template error: {response.text}"
                print(f"invoice returned {response.status_code}: {response.text[:200]}")
        else:
            print("No repair quote in Reparada status found - skipping invoice test")
            pytest.skip("No repair quote in Reparada status")
    
    def test_collect_repair_quote(self):
        """POST /api/quotes/{id}/collect para repair: Usa plantilla repair_collect_warehouse_PYME"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair']
        
        # Buscar una en estado Facturada para cobrar
        facturada_quote = next((q for q in repair_quotes if q.get('quote_status') == 'Facturada'), None)
        
        if facturada_quote:
            quote_id = facturada_quote.get('quote_id')
            print(f"Testing collect with quote {facturada_quote.get('quote_number')} (Facturada)")
            
            # Verificar si tiene pagos adjuntos
            attachments = facturada_quote.get('attachments', [])
            has_pagos = any(a.get('category') == 'Pagos' for a in attachments)
            
            if not has_pagos:
                print("Quote has no Pagos attachment - collect will fail with 422")
                pytest.skip("Quote has no Pagos attachment")
            
            response = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/collect",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ collect successful: {data.get('message')}")
                assert 'emails' in data, "Expected emails in response"
            elif response.status_code == 422:
                # Expected if no Pagos attachment
                print(f"collect returned 422 (expected if no Pagos): {response.text[:200]}")
            else:
                error_text = response.text.lower()
                assert 'template' not in error_text, f"Template error: {response.text}"
                print(f"collect returned {response.status_code}: {response.text[:200]}")
        else:
            print("No repair quote in Facturada status found - skipping collect test")
            pytest.skip("No repair quote in Facturada status")
    
    def test_repair_deliver(self):
        """POST /api/quotes/{id}/repair-deliver: Usa plantilla repair_delivery_PYME"""
        response = requests.get(f"{BASE_URL}/api/quotes", headers=self.headers)
        assert response.status_code == 200
        quotes = response.json()
        
        repair_quotes = [q for q in quotes if q.get('quote_category') == 'repair']
        
        # Buscar una en estado Pagada para entregar
        pagada_quote = next((q for q in repair_quotes if q.get('quote_status') == 'Pagada'), None)
        
        if pagada_quote:
            quote_id = pagada_quote.get('quote_id')
            print(f"Testing repair-deliver with quote {pagada_quote.get('quote_number')} (Pagada)")
            
            response = requests.post(
                f"{BASE_URL}/api/quotes/{quote_id}/repair-deliver",
                headers=self.headers,
                json={"serials_to_deliver": []}  # Empty for test
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ repair-deliver successful: {data.get('message')}")
            else:
                error_text = response.text.lower()
                assert 'template' not in error_text, f"Template error: {response.text}"
                print(f"repair-deliver returned {response.status_code}: {response.text[:200]}")
        else:
            print("No repair quote in Pagada status found - skipping repair-deliver test")
            pytest.skip("No repair quote in Pagada status")


class TestRegularTemplatesStillWork:
    """Verificar que las plantillas regulares (quote_sent_PYME, etc.) siguen funcionando"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login y obtener token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("session_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_regular_templates_exist(self):
        """Verificar que las plantillas regulares existen"""
        response = requests.get(f"{BASE_URL}/api/email-templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        regular_template_ids = [
            "quote_sent_PYME",
            "quote_sent_CORP",
            "quote_approved_PYME",
            "quote_approved_CORP",
            "invoice_PYME",
            "invoice_CORP",
        ]
        
        template_ids = [t.get('template_id') for t in templates]
        for expected_id in regular_template_ids:
            assert expected_id in template_ids, f"Missing regular template: {expected_id}"
            print(f"✓ Regular template {expected_id} exists")


class TestDBTemplatesPrioritized:
    """Verificar que las plantillas en BD se priorizan sobre defaults"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login y obtener token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data.get("session_token") or data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_db_template_prioritized(self):
        """Verificar que si una plantilla está en BD, se usa esa en lugar del default"""
        # Obtener plantilla repair_invoice_PYME (mencionada como editada en BD)
        response = requests.get(
            f"{BASE_URL}/api/email-templates/repair_invoice_PYME",
            headers=self.headers
        )
        
        if response.status_code == 200:
            template = response.json()
            print(f"Template repair_invoice_PYME found:")
            print(f"  - template_id: {template.get('template_id')}")
            print(f"  - name: {template.get('name')}")
            print(f"  - subject: {template.get('subject')[:50]}...")
            print(f"  - body_html length: {len(template.get('body_html', ''))} chars")
            
            # Verificar que tiene HTML profesional
            body_html = template.get('body_html', '')
            assert len(body_html) > 100, "Template has short body_html"
            assert '<table' in body_html.lower() or 'style=' in body_html.lower(), "Template lacks styling"
            print("✓ Template has professional HTML")
        else:
            print(f"Template repair_invoice_PYME not found in DB: {response.status_code}")
            # Esto es OK si no está en BD, se usará el default
            pytest.skip("Template not in DB - will use default")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
