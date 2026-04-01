# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Incluye módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV)

## Módulos Implementados

### Clientes
- CRUD completo con RIF, contactos, segmentos

### Cotizaciones
- Wizard de Equipos/Accesorios con forcedMode
- RBAC con `special_permissions` (cotizaciones:reparaciones, cotizaciones:equipos, etc.)
- PDF generation con ReportLab

### Facturación
- ApprovalBillingModal con DatePicker retroactivo
- Histórico de Tasas de Cambio (BCV API automatizado)
- PDF layout corregido para montos altos en Bs.

### Proyectos (Implementación)
- Matriz de implementación por banco/producto
- Notificaciones secuenciales (Primera Comunicación → Seguimiento 1-3 → Escalamiento)
- **Variables dinámicas de plantillas**:
  - `{Nombre_Cliente}` → clientes.razon_social
  - `{Contacto_Principal}` → contactos.full_name (primer contacto)
  - `{Nombre_Sucursal}` → stores.name (multi-sucursal)
  - `{Cantidad_Cajas}` → stores.box_count (desglose por sucursal)
  - `{Integrador}` → proyecto.integrator_name
  - `{Aplicativo_Integracion}` → proyecto.integrator_app_name
  - `{Nombre_Implementador}` → usuario asignado (nombre)
  - `{Correo_Implementador}` → usuario asignado (email)
  - `{Telefono_Implementador}` → usuario asignado (teléfono)
  - `{Matriz_Bancos_Productos}` → Tabla HTML Banco|Producto|Cantidad
- **Vista Previa de Email**:
  - `POST /api/projects/{id}/preview-notification`
  - `POST /api/projects/{id}/preview-adhoc-email`
  - `GET /api/projects/{id}/template-variables` (18 tags)
  - Modal con variables resueltas y HTML renderizado
  - Chips clickeables de variables en "Otras Notificaciones"
- **Panel de Variables en Editor de Plantillas**:
  - Sección "Plantillas de Proyecto (Implementación)" separada de sedes
  - Panel con "INSERTAR EN ASUNTO" y "INSERTAR EN CUERPO"
  - 19 variables disponibles por tipo de plantilla
  - Inserción con un clic en asunto o cuerpo del HTML
- Plantillas globales: `project_notify_client`, `project_notify_bank`
- Endpoint POST /api/email-templates para crear nuevas plantillas (fix error 405)

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks para Bitácora
- Auto-assignment modals

### Administración
- RBAC: Roles + special_permissions
- Editor de Plantillas de Email con variables dinámicas por tipo

## Archivos Clave
- `/app/backend/services/project_template_vars.py` — Resolución de variables dinámicas (10 vars + estándar)
- `/app/backend/routes/projects.py` — Endpoints de notificaciones, preview, variables
- `/app/backend/routes/seed_and_templates.py` — PROJECT_EMAIL_TEMPLATES, POST/PUT/GET endpoints
- `/app/frontend/src/pages/ProjectDetail.jsx` — UI de proyecto con preview modal
- `/app/frontend/src/components/EmailTemplatesEditor.jsx` — Editor con Panel de Variables
- `/app/frontend/src/pages/Quotes.jsx` — Cotizaciones con RBAC
- `/app/frontend/src/hooks/usePermission.js` — Hook RBAC

## Backlog

### P0 (Resuelto)
- ~~RBAC Quotes buttons visibility bug~~ (Fix: "write" → "edit" en DB)
- ~~Variables dinámicas + Vista Previa de email~~
- ~~Panel de Variables en Editor de Plantillas~~
- ~~Error 405 al guardar plantillas~~
- ~~Variables del Implementador ({Nombre_Implementador}, {Correo_Implementador}, {Telefono_Implementador})~~

### P1 (Próximos)
- Herencia `cantidad_cajas` → campo VTID en VPOS
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5300+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización de componentes monolíticos (Inventory, Integrators, Clients)
