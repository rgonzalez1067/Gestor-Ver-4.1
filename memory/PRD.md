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
- **Motor de Reemplazo de Variables (Parser) ROBUSTO**:
  - 16 variables dinámicas con resolución completa
  - `_render_vars` ejecuta en TODOS los flujos: estándar, custom_html, custom_subject, adhoc
  - `_clean_html_in_braces` limpia HTML tags inyectados por el editor rico dentro de `{...}`
  - Cadena de fallback para Nombre_Cliente: `razon_social → legal_name → fantasy_name → nombre_comercial`
  - Implementador resuelto via `assigned_to_user_id` (no `assigned_to`)
  - `Datos_Contacto`: formato completo "Nombre | Tel: phone | Email: email"
- **Editor de Envío Final (Editable Preview)**:
  - Asunto y cuerpo HTML editables con resolución de variables al enviar
  - Soporte para pegar imágenes JPG/PNG (auto-upload a Object Storage)
  - Panel "Insertar Variable en el editor" con 16 variables clickeables
  - Los cambios NO afectan la plantilla base
- **VTIDs por Sucursal (Multitienda)**: Generación independiente por sucursal
- **Object Storage para Imágenes**: Upload automático, base64→URL conversion
- **Ancho Fluido en Emails**: width:95%; max-width:900px
- **Notificaciones Secuenciales** con prefijos dinámicos y CC
- **Asignación Simplificada**: Sin ticket en modal, fecha_asignacion automática
- **Candado de Seguridad**: Proyecto bloqueado si no tiene ticket_number

## Archivos Clave
- `/app/backend/routes/projects.py`
- `/app/backend/services/project_template_vars.py`
- `/app/backend/services/object_storage.py`
- `/app/backend/services/email_service.py`
- `/app/frontend/src/pages/ProjectDetail.jsx`
- `/app/frontend/src/pages/Projects.jsx`

## Backlog

### P1 (Próximos)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5300+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos
