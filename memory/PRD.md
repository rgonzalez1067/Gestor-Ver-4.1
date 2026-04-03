# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV), Emergent Object Storage (imágenes)

## Módulos Implementados

### Proyectos (Implementación)
- Matriz de implementación por banco/producto
- **Notificaciones Automatizadas con Prefijos Dinámicos**:
  - [Primer Envío] → [Primer Recordatorio] → [Segundo Recordatorio] → [Tercer Recordatorio]
- **Data Binding Correcto de Destinatarios**:
  - Cliente: emails de `contacts[]`
  - Banco: email de `contact_email` o `contacts[]`
- **Destinatarios Adicionales (CC)**: Campo manual separado por coma
- **Variables dinámicas** (16 variables): Nombre_Cliente, Contacto_Principal, Datos_Contacto, Nombre_Sucursal, Cantidad_Cajas, Integrador, Aplicativo_Integracion, Nombre_Implementador, Correo_Implementador, Telefono_Implementador, Matriz_Bancos_Productos, Lista_VTID, project_number, ticket_number, quote_number, Tipo_Comercio
- **Hidratación de Variables Corregida**:
  - Implementador: `assigned_to_user_id` (antes usaba `assigned_to` que no existe)
  - Cliente: fallback chain `razon_social → legal_name → fantasy_name → nombre_comercial → name`
  - Contacto: `full_name → first_name/last_name → nombre/apellido → email`
  - `Datos_Contacto`: formato completo "Nombre | Tel: phone | Email: email"
- **Editor de Envío Final (Editable Preview)**:
  - Asunto y cuerpo HTML editables
  - Soporte para pegar imágenes JPG/PNG (Ctrl+V) — se suben a Object Storage automáticamente
  - Soporte para arrastrar archivos de imagen
  - Botón "Imagen" para insertar desde disco
  - **Panel "Insertar Variable en el editor"**: Re-inserción de variables al cursor
  - Los cambios NO afectan la plantilla base
  - Base64 imágenes se convierten a URLs públicas antes de enviar
- **VTIDs por Sucursal (Multitienda)**:
  - Generación independiente por sucursal con prefijo y número de inicio propios
  - Visualización agrupada por nombre de sucursal
  - Variable `{Lista_VTID}` agrupa VTIDs por sucursal en HTML
- **Object Storage para Imágenes**:
  - Endpoint `POST /api/projects/upload-image` sube a Emergent Object Storage
  - Endpoint `GET /api/projects/images/{filename}` sirve sin auth (para email clients)
  - Conversión automática de base64→URL en el flujo de envío
- **Ancho Fluido en Emails**: width:95%; max-width:900px
- **Asignación Simplificada**: Sin ticket en modal, fecha_asignacion automática
- **Candado de Seguridad**: Proyecto bloqueado si no tiene ticket_number

### Cotizaciones
- RBAC con `special_permissions`

### Facturación
- Tasas de Cambio BCV automatizadas

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks

## Archivos Clave
- `/app/backend/routes/projects.py`
- `/app/backend/services/project_template_vars.py`
- `/app/backend/services/object_storage.py`
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
- Refactorización componentes monolíticos (ProjectDetail.jsx 1600+, Inventory.jsx, Integrators.jsx, Clients.jsx)
