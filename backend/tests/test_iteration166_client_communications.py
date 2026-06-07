# ruff: noqa
"""
Test iteration 166: Verificación de correcciones en módulo de Comunicaciones a Clientes
1) Adjuntos se pasan correctamente a send_email (attachments como bytes)
2) Variables se resuelven en preview-email
3) Bitácora almacena created_at como ISO datetime completo
"""
import pytest
import requests
import os
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestClientCommunicationsFixes:
    """Tests para las 3 correcciones del módulo de comunicaciones a clientes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login y obtener token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("session_token")
        assert token, "No session_token in response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Obtener un cliente existente para pruebas
        clients_resp = self.session.get(f"{BASE_URL}/api/clients")
        assert clients_resp.status_code == 200
        clients = clients_resp.json()
        if clients:
            self.test_client = clients[0]
        else:
            # Crear cliente de prueba si no existe
            create_resp = self.session.post(f"{BASE_URL}/api/clients", json={
                "rif": "J-TEST166-0",
                "legal_name": "TEST_Cliente Prueba 166",
                "fantasy_name": "TEST_Prueba 166",
                "segment": "Pymes",
                "condicion": "Prospecto",
                "sucursal": "Principal",
                "contacts": [{
                    "full_name": "Juan Pérez",
                    "email": "juan@test166.com",
                    "phone": "0412-1234567",
                    "role": "Administrativo"
                }],
                "address": "Av. Principal, Caracas"
            })
            assert create_resp.status_code in [200, 201], f"Failed to create test client: {create_resp.text}"
            self.test_client = create_resp.json()
        
        yield
        
        # Cleanup: eliminar cliente de prueba si lo creamos
        if self.test_client.get("rif") == "J-TEST166-0":
            try:
                self.session.delete(f"{BASE_URL}/api/clients/{self.test_client['client_id']}")
            except:
                pass

    # ==================== TEST 1: Adjuntos en send_email ====================
    
    def test_send_email_with_internal_document_attachment(self):
        """Verifica que los documentos internos se adjuntan correctamente al email"""
        client_id = self.test_client["client_id"]
        
        # Primero subir un documento interno de prueba
        files = {
            'file': ('TEST_doc166.txt', b'Contenido de prueba para adjunto', 'text/plain')
        }
        data = {
            'name': 'TEST_Documento 166',
            'description': 'Documento de prueba para adjuntos',
            'category': 'General'
        }
        
        # Cambiar headers para multipart
        headers = {"Authorization": self.session.headers.get("Authorization")}
        upload_resp = requests.post(
            f"{BASE_URL}/api/client-documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        assert upload_resp.status_code == 200, f"Failed to upload document: {upload_resp.text}"
        doc = upload_resp.json()
        doc_id = doc["document_id"]
        
        try:
            # Enviar email con el documento interno adjunto
            email_data = {
                'recipients': json.dumps(['test@example.com']),
                'subject': 'TEST_Email con adjunto interno',
                'message': 'Este es un mensaje de prueba con adjunto interno',
                'internal_doc_ids': json.dumps([doc_id])
            }
            
            send_resp = requests.post(
                f"{BASE_URL}/api/clients/{client_id}/send-email",
                data=email_data,
                headers=headers
            )
            
            assert send_resp.status_code == 200, f"Failed to send email: {send_resp.text}"
            result = send_resp.json()
            
            # Verificar que se contó el adjunto
            assert result.get("attachments_count", 0) >= 1, "Attachment count should be at least 1"
            assert "status" in result
            print(f"Email enviado con {result.get('attachments_count')} adjunto(s)")
            
        finally:
            # Cleanup: eliminar documento de prueba
            self.session.delete(f"{BASE_URL}/api/client-documents/{doc_id}")
    
    def test_send_email_with_external_file_attachment(self):
        """Verifica que los archivos externos se adjuntan correctamente"""
        client_id = self.test_client["client_id"]
        
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        # Enviar email con archivo externo
        files = {
            'files': ('TEST_external166.txt', b'Contenido externo de prueba', 'text/plain')
        }
        data = {
            'recipients': json.dumps(['test@example.com']),
            'subject': 'TEST_Email con adjunto externo',
            'message': 'Este es un mensaje de prueba con adjunto externo',
            'internal_doc_ids': json.dumps([])
        }
        
        send_resp = requests.post(
            f"{BASE_URL}/api/clients/{client_id}/send-email",
            files=files,
            data=data,
            headers=headers
        )
        
        assert send_resp.status_code == 200, f"Failed to send email: {send_resp.text}"
        result = send_resp.json()
        
        assert result.get("attachments_count", 0) >= 1, "External attachment should be counted"
        print(f"Email con adjunto externo enviado: {result.get('attachments_count')} adjunto(s)")

    # ==================== TEST 2: Resolución de variables en preview ====================
    
    def test_preview_email_resolves_variables(self):
        """Verifica que preview-email resuelve las variables del cliente"""
        client_id = self.test_client["client_id"]
        client_name = self.test_client.get("legal_name") or self.test_client.get("fantasy_name", "")
        client_rif = self.test_client.get("rif", "")
        
        # Obtener contacto si existe
        contacts = self.test_client.get("contacts", [])
        contact_name = contacts[0].get("name", contacts[0].get("full_name", "")) if contacts else ""
        
        # Enviar preview con variables
        preview_data = {
            "subject": "Estimado {nombre}, su RIF es {rif}",
            "message": "Hola {contacto}, le escribimos desde {direccion}"
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/clients/{client_id}/preview-email",
            json=preview_data
        )
        
        assert resp.status_code == 200, f"Preview failed: {resp.text}"
        result = resp.json()
        
        # Verificar que las variables fueron reemplazadas
        assert "{nombre}" not in result.get("subject", ""), "Variable {nombre} should be resolved"
        assert "{rif}" not in result.get("subject", ""), "Variable {rif} should be resolved"
        
        # Verificar que el nombre del cliente aparece en el subject
        if client_name:
            assert client_name in result.get("subject", ""), f"Client name '{client_name}' should appear in subject"
        
        print(f"Preview resuelto - Subject: {result.get('subject')}")
        print(f"Preview resuelto - Message: {result.get('message')[:100]}...")

    def test_preview_email_resolves_double_braces(self):
        """Verifica que preview-email resuelve variables con doble llave {{variable}}"""
        client_id = self.test_client["client_id"]
        
        preview_data = {
            "subject": "Cliente: {{nombre}}",
            "message": "RIF: {{rif}}, Email: {{email}}"
        }
        
        resp = self.session.post(
            f"{BASE_URL}/api/clients/{client_id}/preview-email",
            json=preview_data
        )
        
        assert resp.status_code == 200, f"Preview failed: {resp.text}"
        result = resp.json()
        
        # Verificar que las variables con doble llave fueron reemplazadas
        assert "{{nombre}}" not in result.get("subject", ""), "Variable {{nombre}} should be resolved"
        assert "{{rif}}" not in result.get("message", ""), "Variable {{rif}} should be resolved"
        
        print(f"Preview con doble llave resuelto - Subject: {result.get('subject')}")

    # ==================== TEST 3: Bitácora con created_at ISO datetime ====================
    
    def test_log_entry_has_iso_datetime_created_at(self):
        """Verifica que las entradas de bitácora tienen created_at como ISO datetime completo"""
        client_id = self.test_client["client_id"]
        
        # Crear una entrada de bitácora
        log_data = {
            "client_id": client_id,
            "detail": "TEST_Entrada de prueba 166 para verificar created_at",
            "action": "Llamada",
            "follow_up_date": None,
            "contacted_person": "Juan Pérez"
        }
        
        resp = self.session.post(f"{BASE_URL}/api/clients/{client_id}/logs", json=log_data)
        assert resp.status_code in [200, 201], f"Failed to create log: {resp.text}"
        log_entry = resp.json()
        
        # Verificar que created_at existe y es ISO datetime
        assert "created_at" in log_entry, "Log entry should have created_at field"
        created_at = log_entry["created_at"]
        
        # Verificar formato ISO (debe incluir hora)
        assert "T" in created_at, f"created_at should be ISO format with time: {created_at}"
        
        # Intentar parsear como datetime
        try:
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            assert parsed.hour is not None, "Should have hour component"
            assert parsed.minute is not None, "Should have minute component"
            assert parsed.second is not None, "Should have second component"
            print(f"created_at válido: {created_at} -> {parsed}")
        except ValueError as e:
            pytest.fail(f"created_at is not valid ISO datetime: {created_at} - {e}")
        
        # Cleanup: obtener logs y verificar que el nuestro está ahí
        logs_resp = self.session.get(f"{BASE_URL}/api/clients/{client_id}/logs")
        assert logs_resp.status_code == 200
        logs = logs_resp.json()
        
        # Verificar que todos los logs tienen created_at con hora
        for log in logs:
            if log.get("created_at"):
                assert "T" in log["created_at"], f"All logs should have ISO datetime: {log.get('created_at')}"

    def test_send_email_creates_log_with_iso_datetime(self):
        """Verifica que enviar email crea entrada de bitácora con created_at ISO"""
        client_id = self.test_client["client_id"]
        
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        # Enviar email (esto debe crear entrada en bitácora automáticamente)
        data = {
            'recipients': json.dumps(['test@example.com']),
            'subject': 'TEST_Email para verificar bitácora 166',
            'message': 'Mensaje de prueba',
            'internal_doc_ids': json.dumps([])
        }
        
        send_resp = requests.post(
            f"{BASE_URL}/api/clients/{client_id}/send-email",
            data=data,
            headers=headers
        )
        
        assert send_resp.status_code == 200, f"Failed to send email: {send_resp.text}"
        
        # Obtener logs y verificar el más reciente
        logs_resp = self.session.get(f"{BASE_URL}/api/clients/{client_id}/logs")
        assert logs_resp.status_code == 200
        logs = logs_resp.json()
        
        # Buscar el log de comunicación enviada
        comm_logs = [l for l in logs if "Comunicación enviada" in l.get("action", "")]
        assert len(comm_logs) > 0, "Should have at least one communication log"
        
        latest_log = comm_logs[0]  # Los logs vienen ordenados por fecha desc
        assert "created_at" in latest_log, "Communication log should have created_at"
        assert "T" in latest_log["created_at"], f"created_at should be ISO: {latest_log['created_at']}"
        
        print(f"Log de comunicación creado con created_at: {latest_log['created_at']}")

    # ==================== TEST: Plantillas CLIENTES ====================
    
    def test_get_client_templates(self):
        """Verifica que se pueden obtener plantillas con context=CLIENTES"""
        resp = self.session.get(f"{BASE_URL}/api/email-templates?context=CLIENTES")
        assert resp.status_code == 200, f"Failed to get templates: {resp.text}"
        templates = resp.json()
        
        # Verificar estructura de plantillas
        print(f"Encontradas {len(templates)} plantillas para CLIENTES")
        for tpl in templates[:3]:  # Mostrar primeras 3
            print(f"  - {tpl.get('name')}: {tpl.get('subject', '')[:50]}")

    def test_create_and_use_client_template(self):
        """Verifica flujo completo: crear plantilla y usarla en preview"""
        # Crear plantilla de prueba
        template_data = {
            "template_id": "cli_tpl_test166",
            "name": "TEST_Plantilla 166",
            "subject": "Estimado {nombre}, información importante",
            "body_html": "<p>Hola {contacto},</p><p>Su RIF es {rif}.</p>",
            "context": "CLIENTES",
            "is_active": True
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/email-templates", json=template_data)
        
        # Puede fallar si ya existe, intentar obtenerla
        if create_resp.status_code not in [200, 201]:
            # Buscar si ya existe
            templates_resp = self.session.get(f"{BASE_URL}/api/email-templates?context=CLIENTES")
            templates = templates_resp.json()
            existing = [t for t in templates if t.get("template_id") == "cli_tpl_test166"]
            if existing:
                template = existing[0]
            else:
                pytest.fail(f"Failed to create template: {create_resp.text}")
        else:
            template = create_resp.json()
        
        try:
            # Usar la plantilla en preview
            client_id = self.test_client["client_id"]
            preview_data = {
                "subject": template.get("subject", ""),
                "message": template.get("body_html", template.get("body", ""))
            }
            
            preview_resp = self.session.post(
                f"{BASE_URL}/api/clients/{client_id}/preview-email",
                json=preview_data
            )
            
            assert preview_resp.status_code == 200
            result = preview_resp.json()
            
            # Verificar que las variables fueron resueltas
            assert "{nombre}" not in result.get("subject", "")
            assert "{contacto}" not in result.get("message", "")
            assert "{rif}" not in result.get("message", "")
            
            print(f"Plantilla usada exitosamente - Subject resuelto: {result.get('subject')}")
            
        finally:
            # Cleanup
            self.session.delete(f"{BASE_URL}/api/email-templates/cli_tpl_test166")


class TestClientDocuments:
    """Tests para documentos de comunicación de clientes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "rgonzalez@megasoft.com.ve",
            "password": "Avila*0426"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("session_token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield

    def test_list_client_documents(self):
        """Verifica que se pueden listar documentos de comunicación"""
        resp = self.session.get(f"{BASE_URL}/api/client-documents")
        assert resp.status_code == 200
        docs = resp.json()
        print(f"Encontrados {len(docs)} documentos de comunicación")

    def test_upload_and_delete_document(self):
        """Verifica subida y eliminación de documento"""
        headers = {"Authorization": self.session.headers.get("Authorization")}
        
        # Subir documento
        files = {'file': ('TEST_doc_upload166.pdf', b'%PDF-1.4 test content', 'application/pdf')}
        data = {'name': 'TEST_Documento Upload 166', 'description': 'Test', 'category': 'General'}
        
        upload_resp = requests.post(
            f"{BASE_URL}/api/client-documents/upload",
            files=files,
            data=data,
            headers=headers
        )
        
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
        doc = upload_resp.json()
        
        assert "document_id" in doc
        assert doc["name"] == "TEST_Documento Upload 166"
        
        # Eliminar documento
        del_resp = self.session.delete(f"{BASE_URL}/api/client-documents/{doc['document_id']}")
        assert del_resp.status_code == 200
        print("Documento subido y eliminado exitosamente")
