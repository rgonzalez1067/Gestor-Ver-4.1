# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV), Emergent Object Storage

## Módulos Implementados

### Proyectos (Implementación)
- Matriz de implementación por banco/producto
- **Vinculación Logística en "Enviar a Implementación"**:
  - Modal con selector de Tipo de Proyecto: POS Fast Track / VPOS-MPOS / Payment Gateway
  - POS Fast Track: carga automática de seriales desde cotización (taller_equipos)
  - VPOS/MPOS: busca equipos entregados al cliente por RIF (auto + selección manual)
  - Payment Gateway: omite sección de equipos (flujo digital)
  - Equipos seleccionados se persisten en `project.equipments[]`
  - Tipo de Proyecto visible en ficha del proyecto (`project_type_impl`)
  - Sección "Modelo y Seriales de Equipos" en ProjectDetail
  - Variable `{Modelo_Seriales_Equipos}` para plantillas de email (tabla HTML Modelo-Serial)
- **Motor de Reemplazo de Variables ROBUSTO**:
  - 17 variables dinámicas con resolución completa
  - `_clean_html_in_braces` limpia tags HTML inyectados por el editor rico
  - Cadena de fallback para Nombre_Cliente, Implementador correctamente vinculado
- **Editor de Envío Final**: Editable con soporte de imágenes (Object Storage)
- **VTIDs por Sucursal**: Generación independiente por sucursal
- **Notificaciones Secuenciales** con prefijos dinámicos y CC
- **Asignación Simplificada** + Candado de Seguridad
- **Ancho Fluido en Emails**: width:95%; max-width:900px

### Cotizaciones
- RBAC con `special_permissions`
- Flujo de excepción para pasos saltados

### Facturación
- Tasas de Cambio BCV automatizadas

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks

## Archivos Clave
- `/app/backend/routes/projects.py`
- `/app/backend/routes/quote_actions.py`
- `/app/backend/services/project_template_vars.py`
- `/app/backend/services/object_storage.py`
- `/app/frontend/src/pages/ProjectDetail.jsx`
- `/app/frontend/src/pages/Quotes.jsx`

## Backlog

### P1 (Próximos)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5400+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos
- Ficha Técnica PDF con equipos vinculados
