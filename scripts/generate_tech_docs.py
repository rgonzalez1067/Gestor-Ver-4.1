"""Genera el PAQUETE DE DOCUMENTACIÓN TÉCNICA (10 documentos Word) + un índice HTML.
Escanea el código real para extraer endpoints y colecciones.

Salida: /app/frontend/public/tech-docs/*.docx  +  index.html
"""
import os
import re
import glob
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

OUT = '/app/frontend/public/tech-docs'
os.makedirs(OUT, exist_ok=True)
BACKEND = '/app/backend'

NAVY = RGBColor(0x14, 0x2A, 0x45)
BLUE = RGBColor(0x1D, 0x4E, 0xD8)
GREY = RGBColor(0x4B, 0x55, 0x63)
GREEN = RGBColor(0x15, 0x80, 0x3D)
AMBER = RGBColor(0xB4, 0x53, 0x09)


class Doc:
    def __init__(self, title, subtitle):
        self.d = Document()
        self.d.styles['Normal'].font.name = 'Calibri'
        self.d.styles['Normal'].font.size = Pt(11)
        t = self.d.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = t.add_run(title); r.bold = True; r.font.size = Pt(24); r.font.color.rgb = NAVY
        s = self.d.add_paragraph(); s.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rs = s.add_run(subtitle); rs.font.size = Pt(12); rs.font.color.rgb = GREY
        m = self.d.add_paragraph(); m.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rm = m.add_run('Plataforma de Gestión Mega Soft · Documentación Técnica')
        rm.italic = True; rm.font.size = Pt(9); rm.font.color.rgb = GREY
        self.d.add_paragraph()

    def h1(self, t):
        p = self.d.add_heading(t, level=1)
        for r in p.runs: r.font.color.rgb = NAVY
    def h2(self, t):
        p = self.d.add_heading(t, level=2)
        for r in p.runs: r.font.color.rgb = BLUE
    def h3(self, t):
        p = self.d.add_heading(t, level=3)
        for r in p.runs: r.font.color.rgb = NAVY
    def p(self, t, italic=False, color=None, size=11, bold=False):
        pr = self.d.add_paragraph(); r = pr.add_run(t)
        r.italic = italic; r.bold = bold; r.font.size = Pt(size)
        if color: r.font.color.rgb = color
    def b(self, t):
        self.d.add_paragraph(t, style='List Bullet')
    def n(self, t):
        self.d.add_paragraph(t, style='List Number')
    def code(self, t):
        pr = self.d.add_paragraph(); r = pr.add_run(t)
        r.font.name = 'Consolas'; r.font.size = Pt(9.5); r.font.color.rgb = RGBColor(0x24,0x29,0x2E)
    def table(self, headers, rows, widths=None):
        tb = self.d.add_table(rows=1, cols=len(headers)); tb.style = 'Light Grid Accent 1'
        for i, h in enumerate(headers):
            c = tb.rows[0].cells[i]; c.text = ''
            rr = c.paragraphs[0].add_run(h); rr.bold = True; rr.font.size = Pt(9.5)
        for row in rows:
            cells = tb.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = ''
                rr = cells[i].paragraphs[0].add_run(str(val)); rr.font.size = Pt(9)
        if widths:
            for row in tb.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Inches(w)
    def note(self, kind, t):
        icons = {'tip': ('Consejo: ', GREEN), 'note': ('Nota: ', BLUE), 'warn': ('Importante: ', AMBER)}
        pre, col = icons[kind]
        pr = self.d.add_paragraph(); r = pr.add_run(pre); r.bold = True; r.font.color.rgb = col; r.font.size = Pt(10.5)
        r2 = pr.add_run(t); r2.font.size = Pt(10.5); r2.font.color.rgb = col
    def save(self, fname):
        path = os.path.join(OUT, fname); self.d.save(path); return path


# ---------- extracción de datos reales ----------
def scan_endpoints():
    result = {}
    for f in sorted(glob.glob(os.path.join(BACKEND, 'routes', '*.py'))):
        name = os.path.basename(f)
        eps = []
        txt = open(f, encoding='utf-8', errors='ignore').read()
        for m in re.finditer(r'@router\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']', txt):
            eps.append((m.group(1).upper(), m.group(2)))
        if eps:
            result[name] = eps
    return result


COLLECTIONS = [
    ('users', 'Usuarios del sistema (credenciales, rol, departamento, permisos).'),
    ('user_sessions', 'Sesiones activas (session_token, expiración, conexiones).'),
    ('clients', 'Clientes / comercios, jerarquía matriz-sucursal y datos fiscales.'),
    ('quotes', 'Cotizaciones (equipos, accesorios, reparaciones) y su ciclo de vida.'),
    ('quote_history', 'Bitácora de cambios de estado y excepciones por cotización.'),
    ('quote_custom_actions', 'Acciones personalizadas por cotización.'),
    ('quote_action_overrides', 'Overrides de control de acceso por acción/email.'),
    ('projects', 'Proyectos de implementación post-venta y su seguimiento/SLA.'),
    ('integrators', 'Registro maestro de integradores/comercios certificados.'),
    ('integration_certificates', 'Certificados PDF multiversión por integrador.'),
    ('banks', 'Bancos y sus integraciones/evolución.'),
    ('hardware', 'Catálogo de equipos/hardware.'),
    ('services', 'Catálogo de servicios/bienes.'),
    ('commercial_categories', 'Categorías comerciales de clientes.'),
    ('inventory_movements', 'Movimientos de inventario (entradas/salidas).'),
    ('warehouses', 'Almacenes.'),
    ('serial_assignments', 'Asignación de seriales a cotizaciones/entregas.'),
    ('serial_blacklist', 'Seriales bloqueados/inhabilitados.'),
    ('taller_equipos', 'Equipos en reparación (taller).'),
    ('new_products', 'Nuevos productos y su evolución de fase.'),
    ('new_product_evolution', 'Historial de fases de nuevos productos.'),
    ('email_templates', 'Plantillas de correo por contexto.'),
    ('config', 'Configuraciones del sistema (footer, remitentes, plantilla PDF base, etc.).'),
    ('action_notification_configs', 'Config. dinámica de acciones de cotizaciones.'),
    ('other_action_configs', 'Config. de otras acciones (nuevos productos, integración).'),
    ('notifications', 'Notificaciones push/campana.'),
    ('inbox_messages', 'Centro de mensajes interno.'),
    ('conversations', 'Conversaciones del centro de mensajes.'),
    ('conversation_messages', 'Mensajes de cada conversación.'),
    ('initial_contacts', 'Contactos iniciales (pipeline pre-venta).'),
    ('client_logs', 'Gestiones/bitácora de clientes.'),
    ('client_documents', 'Documentos de clientes.'),
    ('entity_documents', 'Documentos del repositorio corporativo (integradores/comunicaciones).'),
    ('cc_groups', 'Grupos de destinatarios en copia (CC).'),
    ('holidays', 'Días festivos del calendario laboral.'),
    ('profiles', 'Perfiles de permisos.'),
    ('password_reset_tokens', 'Tokens de restablecimiento de contraseña.'),
    ('email_verification_tokens', 'Tokens de verificación de correo.'),
    ('exchange_rates', 'Tasas de cambio.'),
    ('bitacora', 'Bitácora general / auditoría.'),
]

ENV_KEYS = [
    ('MONGO_URL', 'backend', 'Cadena de conexión a MongoDB.'),
    ('DB_NAME', 'backend', 'Nombre de la base de datos.'),
    ('REACT_APP_BACKEND_URL', 'frontend', 'URL pública del backend (ingress). El frontend SIEMPRE la usa.'),
    ('APP_ENV', 'backend', 'Entorno de ejecución (dev/prod).'),
    ('APP_NAME', 'backend', 'Nombre de la aplicación.'),
    ('SMTP_HOST', 'backend', 'Servidor SMTP para envío de correos.'),
    ('SMTP_PORT', 'backend', 'Puerto SMTP.'),
    ('SMTP_USER', 'backend', 'Usuario SMTP.'),
    ('SMTP_PASSWORD', 'backend', 'Contraseña SMTP.'),
    ('SENDER_EMAIL', 'backend', 'Correo remitente por defecto.'),
    ('RESEND_API_KEY', 'backend', 'API key de Resend (proveedor de correo alterno).'),
    ('EXTERNAL_API_KEY', 'backend', 'API key para la API externa (/api/external/*).'),
    ('EMERGENT_LLM_KEY', 'backend', 'Clave universal para integraciones LLM (si aplica).'),
]

FRONT_ROUTES = [
    '/dashboard', '/clients', '/clients/communications', '/initial-contacts', '/quotes',
    '/historical-quotes', '/reports/sales', '/reports/sponsors', '/projects', '/projects/:projectId',
    '/direct-projects', '/integrators', '/integrators/communications', '/new-products',
    '/new-products/communications', '/banks', '/banks/:bankId', '/banks/integrations/report',
    '/hardware', '/inventory', '/inventory/accounting-report', '/inventory/asset-ledger',
    '/inventory/invoiced-exits', '/taller-equipos', '/commercial-categories', '/medios-pago',
    '/condiciones-banco-mediopago', '/exchange-rate', '/admin/users', '/admin/profiles',
    '/settings', '/settings/action-notifications', '/settings/other-actions', '/settings/project-sla',
    '/settings/notifications', '/settings/email-senders', '/settings/email-footer',
    '/settings/work-calendar', '/settings/backup-center', '/settings/connected-users',
    '/login', '/login-google', '/reset-password', '/verify-email',
]

DOCS_INDEX = []  # (filename, title, desc)


def register(fname, title, desc):
    DOCS_INDEX.append((fname, title, desc))


# ============================================================
# 01 — ARQUITECTURA
# ============================================================
def doc_arquitectura():
    d = Doc('Documento de Arquitectura', 'Visión general del sistema (SAD)')
    d.h1('1. Resumen')
    d.p('Plataforma full-stack para la gestión del ciclo de vida comercial y técnico de los '
        'aliados de Mega Soft. Cubre cotizaciones, proyectos de implementación, integradores, '
        'inventario, catálogos, comunicaciones y reportes.')
    d.h1('2. Stack tecnológico')
    d.b('Frontend: React (SPA) + Tailwind CSS + ShadcnUI. Enrutamiento con React Router.')
    d.b('Backend: FastAPI (Python), servidor gestionado por Supervisor (uvicorn).')
    d.b('Base de datos: MongoDB (driver asíncrono Motor).')
    d.b('Generación de PDF: pdfplumber (lectura de anclas) + reportlab (dibujo).')
    d.b('Correo: SMTP (y Resend como alterno).')
    d.h1('3. Topología y enrutamiento')
    d.p('Los servicios corren dentro de un contenedor en Kubernetes:')
    d.b('Backend: 0.0.0.0:8001 (interno). Frontend: 3000 (interno).')
    d.b('Todas las rutas de API llevan el prefijo /api y el ingress las enruta al puerto 8001.')
    d.b('Las rutas sin /api van al frontend (puerto 3000).')
    d.code('Navegador → Ingress → (/api/*) → FastAPI:8001 → MongoDB\n'
           '                    → (resto)  → React:3000')
    d.note('warn', 'El frontend debe usar SIEMPRE process.env.REACT_APP_BACKEND_URL; el backend '
           'usa MONGO_URL/DB_NAME desde variables de entorno. No se hardcodean URLs ni credenciales.')
    d.h1('4. Módulos funcionales principales')
    d.b('Cotizaciones (comercial): propuestas de Equipos, Accesorios y Reparaciones.')
    d.b('Proyectos (técnico/QA): seguimiento post-venta, SLA y cierre/certificación.')
    d.b('Integradores (aliados): registro maestro, certificados multiversión, comunicación masiva.')
    d.b('Catálogos: bancos, hardware, servicios, categorías comerciales, medios de pago.')
    d.b('Inventario y Taller: movimientos, seriales, almacenes, equipos en reparación.')
    d.b('Configuración: plantillas, remitentes, notificaciones, SLA, respaldos, calendario.')
    d.h1('5. Integraciones y componentes transversales')
    d.b('Motor de certificados PDF (ver documento dedicado).')
    d.b('Motor de notificaciones y plantillas (ver documento dedicado).')
    d.b('Centro de mensajes interno (inbox) y notificaciones push.')
    d.b('API externa protegida por API key (/api/external/*).')
    register('01_Arquitectura.docx', 'Arquitectura del Sistema', 'Visión general, stack, topología y módulos.')
    d.save('01_Arquitectura.docx')


# ============================================================
# 02 — MODELO DE DATOS
# ============================================================
def doc_datos():
    d = Doc('Modelo de Datos', 'Diccionario de colecciones MongoDB')
    d.h1('1. Introducción')
    d.p('La persistencia usa MongoDB. A continuación se listan las colecciones principales '
        'detectadas en el código y su propósito. Los identificadores se exponen como cadenas '
        '(el _id de Mongo se serializa a texto en la API).')
    d.note('note', 'Convención: al leer se transforma _id → id; al escribir se usan modelos '
           'Pydantic. No se retornan documentos crudos de Mongo en la API.')
    d.h1('2. Colecciones')
    d.table(['Colección', 'Propósito'], COLLECTIONS, widths=[2.1, 4.4])
    d.h1('3. Relaciones clave')
    d.b('quotes → clients: una cotización referencia a un cliente (y su sucursal).')
    d.b('quotes → projects: al enviar a implementación se genera/enlaza un proyecto.')
    d.b('projects → integrators: al cerrar un proyecto estándar se inserta/actualiza el integrador.')
    d.b('integrators → integration_certificates: historial multiversión de certificados por integrador.')
    d.b('banks → (integraciones/evolución): subdocumentos y logs de evolución.')
    d.b('users → profiles: los permisos pueden derivar de perfiles.')
    register('02_Modelo_Datos.docx', 'Modelo de Datos', 'Diccionario de colecciones MongoDB y relaciones.')
    d.save('02_Modelo_Datos.docx')


# ============================================================
# 03 — API REFERENCE (auto-scan)
# ============================================================
def doc_api():
    eps = scan_endpoints()
    total = sum(len(v) for v in eps.values())
    d = Doc('Referencia de API', f'{total} endpoints REST · prefijo /api')
    d.h1('1. Convenciones')
    d.b('Todos los endpoints se exponen bajo el prefijo /api.')
    d.b('Autenticación por session_token (cabecera Authorization: Bearer <token>).')
    d.b('Formato de datos: JSON (multipart/form-data para subida de archivos).')
    d.note('note', 'Este listado se genera automáticamente escaneando los decoradores @router '
           'de cada módulo del backend, por lo que refleja el estado real del código.')
    d.h1(f'2. Endpoints por módulo ({total} en total)')
    for fname in sorted(eps.keys()):
        rows = [[m, '/api' + p] for (m, p) in eps[fname]]
        d.h3(f'{fname}  ({len(rows)})')
        d.table(['Método', 'Ruta'], rows, widths=[1.0, 5.5])
    register('03_API_Reference.docx', 'Referencia de API', f'{total} endpoints REST agrupados por módulo.')
    d.save('03_API_Reference.docx')


# ============================================================
# 04 — MOTOR DE CERTIFICADOS PDF
# ============================================================
def doc_pdf():
    d = Doc('Motor de Certificados PDF', 'Generación del Certificado de Integración (V7)')
    d.h1('1. Enfoque')
    d.p('El certificado se produce sobre una PLANTILLA PDF base almacenada en la colección '
        '"config". El motor lee las coordenadas de frases-ancla estáticas del PDF con pdfplumber '
        'y luego superpone (overlay) el texto dinámico con reportlab, fusionando ambas capas.')
    d.code('Plantilla base (config) → pdfplumber (anclas x,y) → reportlab (overlay) → merge → PDF final')
    d.h1('2. Función principal')
    d.b('backend/routes/integrators.py → _generate_integration_certificate_pdf(...).')
    d.b('Helpers: _find_phrase / _find_phrase_first (localizan anclas), _fit_font (auto-ajuste), '
        '_baseline (línea base), _draw_centered (centrado).')
    d.h1('3. Reglas de inyección (V7)')
    d.table(['Elemento', 'Ancla / posición', 'Estilo'], [
        ['Tipo de Integrador', 'Tras "Certifica al"', 'Times New Roman 28pt regular'],
        ['Nombre del Integrador', 'Línea inferior, centrado', 'Times New Roman 28pt Bold'],
        ['Componente - Versión', 'Línea en blanco del cuerpo (centrado)', 'Arial (Helvetica) 19pt Bold'],
        ['Nombre del Aplicativo', 'Línea en blanco inferior (centrado)', 'Arial 19pt Bold'],
        ['Medios de pago', 'Tras "Medios de pago certificados:"', 'Arial 19pt Bold, máx 3 líneas'],
        ['Fecha', 'Tras "Caracas,"', 'Times New Roman 16pt regular'],
    ], widths=[1.7, 2.7, 2.1])
    d.h1('4. Algoritmo de medios de pago (auto-escala)')
    d.b('Se concatenan los medios con " / " y se envuelven por palabras (word-wrap).')
    d.b('Fuente base 19pt; si excede 3 líneas, reduce el tamaño dinámicamente (hasta ~9pt) '
        'hasta que quepan sin truncar información.')
    d.b('Margen derecho de seguridad (~715pt) para no desbordar la página (842×595).')
    d.h1('5. Persistencia y multiversión')
    d.b('_store_integrator_certificate guarda cada PDF en integration_certificates (acumulativo).')
    d.b('Nunca se sobreescribe: cada cierre estándar añade una nueva versión al historial.')
    d.note('warn', 'El motor es sensible a la plantilla base: si cambian las frases-ancla, deben '
           'revisarse las coordenadas. Validar siempre con un PDF de prueba tras cambiar la plantilla.')
    register('04_Motor_Certificados_PDF.docx', 'Motor de Certificados PDF', 'Inyección por anclas, estilos V7 y auto-escala.')
    d.save('04_Motor_Certificados_PDF.docx')


# ============================================================
# 05 — NOTIFICACIONES Y PLANTILLAS
# ============================================================
def doc_notif():
    d = Doc('Notificaciones y Plantillas', 'Motor de correos, variables y acciones')
    d.h1('1. Plantillas de correo')
    d.b('Se almacenan en la colección email_templates, organizadas por contexto (ej. INTEGRADORES).')
    d.b('El editor de plantillas toma su paleta de variables de una fuente única en el frontend '
        '(templateVariables.js → VARIABLE_CATEGORIES).')
    d.h1('2. Sustitución de variables (_render)')
    d.b('services/notification_engine.py → _render(text, vars) reemplaza {Variable} y {{Variable}}.')
    d.b('Ejemplo: {Interfaz_Integrada} = "Componente - Versión" (idéntico al del certificado).')
    d.h1('3. Acciones configurables')
    d.b('action_notification_configs: acciones de Cotizaciones (destinatarios/plantilla por acción).')
    d.b('other_action_configs: otras acciones (Nuevos Productos, Proyectos de Integración).')
    d.b('El catálogo de variables por acción se expone vía /api/other-actions/catalog.')
    d.h1('4. Envío de correo')
    d.b('SMTP configurable por variables de entorno (SMTP_HOST/PORT/USER/PASSWORD, SENDER_EMAIL).')
    d.b('Comunicación masiva a integradores: envío en BCC (copia oculta) para preservar privacidad.')
    d.b('Adjuntos desde el repositorio (entity_documents) o archivos locales.')
    register('05_Notificaciones_Plantillas.docx', 'Notificaciones y Plantillas', 'Motor de correo, variables y BCC.')
    d.save('05_Notificaciones_Plantillas.docx')


# ============================================================
# 06 — GUÍA FRONTEND
# ============================================================
def doc_front():
    d = Doc('Guía de Frontend', 'Estructura de la SPA React')
    d.h1('1. Organización')
    d.b('frontend/src/pages/ — páginas (46 aprox.).')
    d.b('frontend/src/components/ — componentes reutilizables (49 aprox.) + subcarpetas (quotes, email, ui).')
    d.b('frontend/src/components/ui/ — componentes base ShadcnUI.')
    d.h1('2. Rutas de la aplicación')
    d.table(['Ruta', 'Ruta'], [[FRONT_ROUTES[i], FRONT_ROUTES[i+1] if i+1 < len(FRONT_ROUTES) else '']
             for i in range(0, len(FRONT_ROUTES), 2)], widths=[3.25, 3.25])
    d.h1('3. Convenciones')
    d.b('Todo elemento interactivo lleva data-testid en kebab-case (facilita QA y automatización).')
    d.b('Llamadas a API vía cliente axios usando REACT_APP_BACKEND_URL + /api.')
    d.b('Estilos con Tailwind; toasts con sonner; iconos con lucide-react.')
    d.b('Páginas: export default; componentes: export const.')
    register('06_Guia_Frontend.docx', 'Guía de Frontend', 'Estructura, rutas y convenciones de la SPA React.')
    d.save('06_Guia_Frontend.docx')


# ============================================================
# 07 — MATRIZ DE PERMISOS
# ============================================================
def doc_permisos():
    d = Doc('Matriz de Permisos', 'Roles, departamentos y control de acceso (RBAC)')
    d.h1('1. Modelo de acceso')
    d.b('Cada usuario tiene un rol (ej. admin) y un departamento.')
    d.b('Permisos por grupos de menú, permisos específicos y permisos especiales (special_permissions).')
    d.b('Perfiles (profiles) permiten reutilizar conjuntos de permisos.')
    d.h1('2. Permisos especiales detectados')
    d.table(['Permiso', 'Descripción'], [
        ['cotizaciones:equipos', 'Acceso al flujo de cotizaciones de equipos.'],
        ['integradores:mass_comm', 'Uso de la Comunicación Masiva a integradores.'],
        ['reportes_ventas:executive_summary', 'Ver el resumen ejecutivo de reportes de ventas.'],
    ], widths=[2.6, 3.9])
    d.h1('3. Administración de usuarios (endpoints)')
    d.b('/api/admin/users (CRUD, estado, rol, permisos, permisos especiales, almacén, supervisor).')
    d.b('/api/admin/users/{id}/reset-password y /audit (auditoría por usuario).')
    d.b('/api/admin/executives/orphaned y /reassign (reasignación de ejecutivos).')
    d.h1('4. Reglas de negocio relevantes')
    d.b('Pertenencia de cotizaciones al departamento del creador (inmutable ante transferencias).')
    d.b('Overrides de acción por email estable (quote_action_overrides).')
    d.note('note', 'Recomendación: completar esta matriz con la lista exacta de acciones por rol '
           'según las políticas internas; la base técnica ya está implementada.')
    register('07_Matriz_Permisos.docx', 'Matriz de Permisos', 'RBAC: roles, permisos especiales y administración.')
    d.save('07_Matriz_Permisos.docx')


# ============================================================
# 08 — RUNBOOK DESPLIEGUE
# ============================================================
def doc_runbook():
    d = Doc('Runbook de Despliegue y Operación', 'Servicios, variables y troubleshooting')
    d.h1('1. Servicios (Supervisor)')
    d.b('backend — FastAPI en 0.0.0.0:8001 (uvicorn).')
    d.b('frontend — React dev server en 3000.')
    d.b('mongodb — base de datos local.')
    d.code('sudo supervisorctl status\nsudo supervisorctl restart backend\nsudo supervisorctl restart frontend')
    d.note('warn', 'Reinicia servicios solo tras cambios en .env o instalación de dependencias; '
           'el hot-reload cubre los cambios de código normales.')
    d.h1('2. Variables de entorno')
    d.table(['Clave', 'Ámbito', 'Descripción'], ENV_KEYS, widths=[2.0, 1.0, 3.5])
    d.note('note', 'No eliminar las claves protegidas (MONGO_URL, DB_NAME, REACT_APP_BACKEND_URL). '
           'Sin valores por defecto: la ausencia de configuración debe fallar de inmediato.')
    d.h1('3. Health checks')
    d.b('Backend: GET /api/external/health (o cualquier endpoint público).')
    d.b('Frontend: carga de la SPA en la URL pública.')
    d.h1('4. Logs')
    d.code('tail -n 100 /var/log/supervisor/backend.err.log\n'
           'tail -n 100 /var/log/supervisor/frontend.out.log')
    d.h1('5. Troubleshooting común')
    d.b('Backend no levanta: revisar backend.err.log (imports/dependencias faltantes).')
    d.b('Errores 502/blank: verificar que el servicio esté RUNNING en supervisor.')
    d.b('CORS/URL: confirmar REACT_APP_BACKEND_URL y prefijo /api en las rutas.')
    d.b('Correo no sale: validar SMTP_* y SENDER_EMAIL.')
    register('08_Runbook_Despliegue.docx', 'Runbook de Despliegue', 'Servicios, variables, logs y troubleshooting.')
    d.save('08_Runbook_Despliegue.docx')


# ============================================================
# 09 — GUÍA DE QA
# ============================================================
def doc_qa():
    d = Doc('Guía de QA', 'Casos de prueba de flujos críticos')
    d.h1('1. Credenciales de prueba')
    d.b('Admin: rgonzalez@megasoft.com.ve / admin123.')
    d.b('Usuario Equipos: agodoy@megasoft.com.ve / Test1234!.')
    d.h1('2. Flujos críticos a verificar')
    d.h3('Cotizaciones')
    d.n('Crear cotización (Equipos Corp/Pyme, Accesorios, Reparación) y validar totales.')
    d.n('Recorrer el ciclo de estados (Borrador → Enviada → Aprobada → Implementación → Entrega).')
    d.n('Regularizar una cotización en estado irregular (dry-run + aplicar).')
    d.n('Restaurar anexos ZIP y verificar barra de progreso, contadores y ETA.')
    d.h3('Proyectos')
    d.n('Verificar KPIs y el tooltip de semáforo (Al día / Retraso Medio / Retraso Crítico).')
    d.n('Asignar y reasignar (individual y por lote) con motivo obligatorio.')
    d.n('Cerrar proyecto estándar (Modal 1 Componente/Versión + Modal 2 comunicación).')
    d.n('Cerrar proyecto Ambiente de Prueba: confirmar bypass total (sin certificado ni correos).')
    d.h3('Integradores')
    d.n('Verificar inserción vs. ampliación tras cierres de proyecto.')
    d.n('Certificados multiversión: listar, descargar y agregar PDF manual.')
    d.n('Comunicación masiva: filtrar por tipo, seleccionar todos, plantilla, adjuntos y envío BCC.')
    d.note('tip', 'Todos los elementos interactivos exponen data-testid, lo que permite automatizar '
           'estos flujos con Playwright de forma estable.')
    register('09_Guia_QA.docx', 'Guía de QA', 'Casos de prueba de los flujos críticos con credenciales.')
    d.save('09_Guia_QA.docx')


# ============================================================
# 10 — SEGURIDAD
# ============================================================
def doc_seguridad():
    d = Doc('Documentación de Seguridad', 'Autenticación, acceso y privacidad')
    d.h1('1. Autenticación')
    d.b('Login por email/contraseña; el backend responde con un session_token.')
    d.b('El token se envía en la cabecera Authorization: Bearer <token>.')
    d.b('Sesiones registradas en user_sessions (expiración/limpieza).')
    d.b('Flujos de recuperación y verificación por token (password_reset_tokens, email_verification_tokens).')
    d.h1('2. Control de acceso')
    d.b('RBAC por rol, departamento, permisos y permisos especiales (ver Matriz de Permisos).')
    d.b('Endpoints administrativos bajo /api/admin protegidos por rol admin.')
    d.h1('3. Privacidad de datos')
    d.b('Comunicación masiva en BCC: ningún destinatario ve a los demás.')
    d.b('Pertenencia de cotizaciones por departamento; visibilidad controlada por área.')
    d.h1('4. Manejo de archivos')
    d.b('Subida por multipart y almacenamiento persistente; descargas autenticadas.')
    d.b('Validación de rutas en importación de ZIP (evita traversal con "..").')
    d.h1('5. Buenas prácticas')
    d.b('Credenciales y URLs solo desde variables de entorno (nunca hardcode).')
    d.b('API externa protegida por EXTERNAL_API_KEY.')
    d.note('warn', 'Ante incidentes de autenticación, revisar logs del backend y la colección '
           'user_sessions; nunca sugerir "limpiar caché" como solución de fondo.')
    register('10_Seguridad.docx', 'Seguridad', 'Autenticación, RBAC, privacidad BCC y manejo de archivos.')
    d.save('10_Seguridad.docx')


# ============================================================
def build_index():
    rows = ''.join(
        f'<li><a href="/tech-docs/{f}">{t}</a><span>{desc}</span></li>' for (f, t, desc) in DOCS_INDEX)
    html = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Documentación Técnica · Mega Soft</title>
<style>
  body{{font-family:Segoe UI,Calibri,Arial,sans-serif;background:#0f1b2d;color:#e8eef5;margin:0;padding:48px 20px}}
  .wrap{{max-width:820px;margin:0 auto}}
  h1{{color:#fff;font-size:30px;margin:0 0 6px}}
  p.sub{{color:#93a4bd;margin:0 0 32px}}
  ul{{list-style:none;padding:0;margin:0;display:grid;gap:14px}}
  li{{background:#16294a;border:1px solid #24406e;border-radius:14px;padding:18px 20px;transition:.2s}}
  li:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,.35);border-color:#3b82f6}}
  li a{{color:#7db3ff;font-size:18px;font-weight:600;text-decoration:none;display:block}}
  li span{{color:#93a4bd;font-size:13px;display:block;margin-top:4px}}
  footer{{color:#5b6b85;font-size:12px;margin-top:36px;text-align:center}}
</style></head><body><div class="wrap">
<h1>Documentación Técnica</h1>
<p class="sub">Plataforma de Gestión Mega Soft · descargables en Word (.docx)</p>
<ul>{rows}</ul>
<footer>Generado automáticamente a partir del código fuente.</footer>
</div></body></html>"""
    open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)


if __name__ == '__main__':
    doc_arquitectura()
    doc_datos()
    doc_api()
    doc_pdf()
    doc_notif()
    doc_front()
    doc_permisos()
    doc_runbook()
    doc_qa()
    doc_seguridad()
    build_index()
    print('GENERADOS:', len(DOCS_INDEX), 'documentos + index.html en', OUT)
    for f, t, _ in DOCS_INDEX:
        print(' -', f)
