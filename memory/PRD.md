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
  - Cliente: emails de `contacts[]` de la ficha (no placeholders)
  - Banco: email de `contact_email` o `contacts[]`
  - UI muestra destinatarios resueltos como chips verdes
- **Destinatarios Adicionales (CC)**:
  - Campo de texto para agregar correos CC separados por coma
  - Backend procesa TO (DB) + CC (manuales) por separado
  - Historial registra tanto TO como CC
- **Variables dinámicas** (14 variables): Nombre_Cliente, Contacto_Principal, Nombre_Sucursal, Cantidad_Cajas, Integrador, Aplicativo_Integracion, Nombre_Implementador, Correo_Implementador, Telefono_Implementador, Matriz_Bancos_Productos, Lista_VTID, project_number, ticket_number, quote_number
- **Vista Previa de Email** con variables resueltas
- **Panel de Variables en Editor de Plantillas**: Inserción en Asunto y Cuerpo
- **Asignación Simplificada**: Sin ticket en modal, fecha_asignacion automática
- **Candado de Seguridad**: Proyecto bloqueado si no tiene ticket_number registrado, input para desbloquear
- **Generador VTID**: Terminales virtuales secuenciales (prefijo + 3 dígitos), persistidos en BD, sección visual en ProjectDetail

### Cotizaciones
- RBAC con `special_permissions`

### Facturación
- Tasas de Cambio BCV automatizadas

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks

## Archivos Clave
- `/app/backend/services/project_template_vars.py`
- `/app/backend/services/email_service.py` (soporte CC)
- `/app/backend/routes/projects.py`
- `/app/backend/routes/seed_and_templates.py`
- `/app/frontend/src/pages/ProjectDetail.jsx`
- `/app/frontend/src/components/EmailTemplatesEditor.jsx`

## Backlog

### P1 (Próximos)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5300+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (ProjectDetail.jsx, Inventory.jsx, Integrators.jsx, Clients.jsx)
