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
- **Variables dinámicas de plantillas** (Feb 2026):
  - `{Nombre_Cliente}` → clientes.razon_social
  - `{Contacto_Principal}` → contactos.full_name (primer contacto)
  - `{Nombre_Sucursal}` → stores.name (multi-sucursal)
  - `{Cantidad_Cajas}` → stores.box_count (desglose por sucursal)
  - `{Integrador}` → proyecto.integrator_name
  - `{Matriz_Bancos_Productos}` → Tabla HTML Banco|Producto|Cantidad
- **Vista Previa de Email** (Feb 2026):
  - Endpoint `POST /api/projects/{id}/preview-notification`
  - Endpoint `POST /api/projects/{id}/preview-adhoc-email`
  - Endpoint `GET /api/projects/{id}/template-variables`
  - Modal de vista previa con variables resueltas
  - Chips clickeables de variables en "Otras Notificaciones"
- Plantillas registradas en EmailTemplatesEditor: `project_notify_client`, `project_notify_bank`

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks para Bitácora
- Auto-assignment modals

### Administración
- RBAC: Roles + special_permissions
- Editor de Plantillas de Email con variables dinámicas por tipo

## Archivos Clave
- `/app/backend/services/project_template_vars.py` — Resolución de variables dinámicas
- `/app/backend/routes/projects.py` — Endpoints de notificaciones, preview, variables
- `/app/frontend/src/pages/ProjectDetail.jsx` — UI de proyecto con preview modal
- `/app/frontend/src/components/EmailTemplatesEditor.jsx` — Editor de plantillas
- `/app/frontend/src/pages/Quotes.jsx` — Cotizaciones con RBAC
- `/app/frontend/src/hooks/usePermission.js` — Hook RBAC

## Backlog

### P0 (Resuelto)
- ~~RBAC Quotes buttons visibility bug~~ ✅ (Fix: "write" → "edit" en DB)
- ~~Variables dinámicas + Vista Previa de email~~ ✅

### P1 (Próximos)
- Herencia `cantidad_cajas` → campo VTID en VPOS
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5300+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización de componentes monolíticos (Inventory, Integrators, Clients)
