# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV)

## Módulos Implementados

### Proyectos (Implementación)
- Matriz de implementación por banco/producto
- **Notificaciones Automatizadas con Prefijos Dinámicos**:
  - [Primer Envío] → [Primer Recordatorio] → [Segundo Recordatorio] → [Tercer Recordatorio]
  - Plantilla fija; solo el prefijo del asunto cambia por conteo
- **Data Binding Correcto de Destinatarios**:
  - Cliente: emails de `contacts[]` de la ficha
  - Banco: email de `contact_email` o `contacts[]`
- **Destinatarios Adicionales (CC)**: Campo manual separado por coma
- **Variables dinámicas** (15 variables): Nombre_Cliente, Contacto_Principal, Nombre_Sucursal, Cantidad_Cajas, Integrador, Aplicativo_Integracion, Nombre_Implementador, Correo_Implementador, Telefono_Implementador, Matriz_Bancos_Productos, Lista_VTID, project_number, ticket_number, quote_number, Tipo_Comercio
- **Editor de Envío Final (Editable Preview)**:
  - Asunto editable en input
  - Cuerpo HTML editable (contentEditable)
  - Soporte para pegar imágenes JPG/PNG desde portapapeles (Ctrl+V)
  - Soporte para arrastrar archivos de imagen al editor
  - Botón "Imagen" para insertar archivos desde disco
  - Los cambios NO afectan la plantilla base — solo el envío actual
  - Botón "Enviar Correo" envía con `custom_html` y `custom_subject`
  - Aplica a TODAS las notificaciones (secuenciales + ad-hoc)
- **Panel de Variables Disponibles**:
  - Panel colapsable en diálogos de notificación secuencial y ad-hoc
  - Tags clickeables que copian la variable al portapapeles
- **VTIDs por Sucursal (Multitienda)**:
  - Generación independiente por sucursal con prefijo y número de inicio propios
  - Visualización agrupada por nombre de sucursal
  - Eliminación individual por sucursal
  - Proyectos de tienda única mantienen generación a nivel de proyecto
  - Variable `{Lista_VTID}` incluye VTIDs agrupados por sucursal en HTML
- **Ancho Fluido en Emails**: width:95%; max-width:900px (antes 600px fijo)
- **Asignación Simplificada**: Sin ticket en modal, fecha_asignacion automática
- **Candado de Seguridad**: Proyecto bloqueado si no tiene ticket_number
- **Vista Previa de Email** con variables resueltas

### Cotizaciones
- RBAC con `special_permissions`

### Facturación
- Tasas de Cambio BCV automatizadas

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks

## Archivos Clave
- `/app/backend/routes/projects.py`
- `/app/backend/services/project_template_vars.py`
- `/app/backend/services/email_service.py`
- `/app/backend/routes/seed_and_templates.py`
- `/app/frontend/src/pages/ProjectDetail.jsx`
- `/app/frontend/src/pages/Projects.jsx`
- `/app/frontend/src/components/EmailTemplatesEditor.jsx`

## Backlog

### P1 (Próximos)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5300+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (ProjectDetail.jsx 1600+ líneas, Inventory.jsx, Integrators.jsx, Clients.jsx)
