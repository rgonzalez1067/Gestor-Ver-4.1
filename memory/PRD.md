# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Incluye módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV)

## Módulos Implementados

### Proyectos (Implementación)
- Matriz de implementación por banco/producto
- **Notificaciones Automatizadas con Prefijos Dinámicos**:
  - Envío 1: `[Primer Envío] + Asunto de la Plantilla`
  - Envío 2: `[Primer Recordatorio] + Asunto`
  - Envío 3: `[Segundo Recordatorio] + Asunto`
  - Envío 4+: `[Tercer Recordatorio] + Asunto`
  - Plantilla fija por tipo: `project_notify_client` (cliente) / `project_notify_bank` (banco)
  - El contenido se mantiene íntegro; solo cambia el prefijo del asunto
  - Historial visible con conteo y fechas en el diálogo
- **Variables dinámicas de plantillas** (10 variables + estándar):
  - `{Nombre_Cliente}`, `{Contacto_Principal}`, `{Nombre_Sucursal}`, `{Cantidad_Cajas}`
  - `{Integrador}`, `{Aplicativo_Integracion}`
  - `{Nombre_Implementador}`, `{Correo_Implementador}`, `{Telefono_Implementador}`
  - `{Matriz_Bancos_Productos}` (Tabla HTML)
- **Vista Previa de Email**: `POST preview-notification`, `POST preview-adhoc-email`, `GET template-variables`
- **Panel de Variables en Editor de Plantillas**: Sección separada para plantillas de proyecto, inserción en Asunto y Cuerpo

### Cotizaciones
- RBAC con `special_permissions`
- Wizard de Equipos/Accesorios con forcedMode

### Facturación
- Histórico de Tasas de Cambio (BCV API automatizado)
- PDF layout corregido

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks

### Administración
- RBAC: Roles + special_permissions
- Editor de Plantillas con panel de variables interactivo
- POST /api/email-templates para crear nuevas plantillas (fix 405)

## Archivos Clave
- `/app/backend/services/project_template_vars.py` — Resolución de variables
- `/app/backend/routes/projects.py` — Notificaciones con prefijos, preview, send
- `/app/backend/routes/seed_and_templates.py` — PROJECT_EMAIL_TEMPLATES, CRUD endpoints
- `/app/frontend/src/pages/ProjectDetail.jsx` — UI de notificaciones con historial
- `/app/frontend/src/components/EmailTemplatesEditor.jsx` — Editor con Panel de Variables

## Backlog

### P0 (Resuelto)
- ~~Notificaciones con prefijos dinámicos por conteo~~
- ~~Panel de Variables en Editor de Plantillas~~
- ~~Variables del Implementador~~
- ~~Fix Error 405~~
- ~~RBAC Quotes buttons~~

### P1 (Próximos)
- Herencia `cantidad_cajas` → campo VTID en VPOS
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5300+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos
