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
- **Flujo Transaccional Seguro (Fix P0 — Feb 2026)**:
  - Orden: PDF → Proyecto → Email (sin emails fantasma)
  - `_create_project_from_quote` restaurada con cuerpo completo
  - Búsqueda de equipos diferenciada: Fast Track por quote_id, VPOS/MPOS por RIF+estatus
  - Si falla PDF o proyecto, se retorna error 500 sin enviar email
- **Flujo Extendido PYME (Feb 2026)**:
  - Activado cuando `client_segment` es PYME o el `quote_number` contiene '-PYME'
  - **Servidor de Instalación**: Dropdown (Multicomercio MSC / MSC2 / Otro + texto libre). Guardado en `project.server_name`
  - **Protocolo Pinpads**: Pregunta cerrada Sí/No.
    - No: conversión directa sin equipos
    - Sí: Dropdown de modelos (hardware con type POS/Pinpad y asset_type='Bien') → Búsqueda en Salidas de Inventario (últimos 15 días, por RIF cliente + modelo) → Selección de seriales
  - Datos guardados en `project.pinpad_serials[]`
  - **PDF actualizado**: Secciones "Servidor de Instalación" y "Modelo y Seriales de POS/Pinpad"
  - **ProjectDetail actualizado**: Widgets de servidor y pinpads vinculados
  - **Variables de email**: `{Modelo_Seriales_POS}`, `{Servidor_Instalacion}`
  - **Endpoints nuevos**: `GET /api/quotes/{id}/pinpad-models`, `GET /api/quotes/{id}/inventory-serials?model_id=X`
- **Motor de Reemplazo de Variables ROBUSTO**:
  - 19 variables dinámicas (incluye nuevas: Modelo_Seriales_POS, Servidor_Instalacion)
  - `_clean_html_in_braces` limpia tags HTML inyectados por el editor rico
- **Editor de Envío Final**: Editable con soporte de imágenes (Object Storage)
- **VTIDs por Sucursal**: Generación independiente por sucursal
- **Notificaciones Secuenciales** con prefijos dinámicos y CC
- **Asignación Simplificada** + Candado de Seguridad

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
- `/app/backend/services/implementation_pdf.py`
- `/app/frontend/src/pages/ProjectDetail.jsx`
- `/app/frontend/src/pages/Quotes.jsx`

## Historial Reciente
- **Abr 2026**: Homologación del panel de Variables en el editor de Plantillas de Cotizaciones (Quotes.jsx). Se reemplazó la sección básica "Variables rápidas" con un Diccionario de Variables categorizado (Cliente, Cotización, Ejecutivo, Facturación) con iconos, descripciones y click-to-copy, idéntico al de ProjectDetail.jsx.

## Backlog

### P1 (Próximos)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5800+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+)
