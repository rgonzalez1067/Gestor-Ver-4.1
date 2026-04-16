# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela.

## Módulos Implementados

### Clientes
- CRUD completo de clientes con bitácora, contactos, sucursales
- **Comunicaciones a Clientes** (/clients/communications):
  - Plantillas de Correo (CRUD con context=CLIENTES, independiente de Proyectos)
  - Documentos de Comunicación (subida/eliminación)
  - Envío de emails con variables dinámicas y adjuntos
  - Vista previa de correos con resolución de variables

### Cotizaciones
- Creación, edición con control de versiones
- PDF dinámico regenerado automáticamente
- Total USD = Inversión Inicial (Setup + Equipos), sin recurrentes
- Justificación obligatoria para modificaciones

### Proyectos
- Gestión de proyectos de integración
- Plantillas y notificaciones propias (context=PROJECTS)
- Notas de entrega, roadmap por banco

### Inventarios
- Kardex con movimientos en Bolívares (Bs.)
- Mayor de Activos (PEPS/FIFO) desglosado LCH/TBP

### Contactos Iniciales
- Campo "Referido Por"
- API externa protegida por API Key (/api/external/contacts)

### Otros
- Taller de Equipos en Reparación (con eliminación Admin)
- Gestión de Bancos, Integradores, Servicios
- Tasa de Cambio, Nuevos Productos
- Script de migración (db_migrate.py)

## Archivos Clave
- `/app/frontend/src/pages/ClientTemplatesConfig.jsx` — Config plantillas/docs clientes
- `/app/frontend/src/components/ClientEmailDialog.jsx` — Diálogo email clientes
- `/app/backend/routes/client_communications.py` — Backend comunicaciones clientes
- `/app/backend/routes/seed_and_templates.py` — CRUD plantillas email (model: template_id + body_html)
- `/app/frontend/src/pages/AssetLedgerReport.jsx` — Reporte PEPS
- `/app/backend/routes/external_api.py` — API pública externa
- `/app/backend/db_migrate.py` — Script migración

## Backlog
- **P1**: Sistema de Notificaciones Push (campana en header, alertas tiempo real)
- **P2**: Reportes de Ventas
- **P2**: Lógica "Completado" en Roadmap Bancos
- **P2**: Refactorización monolitos (ProjectDetail.jsx ~1800 líneas, quote_actions.py ~2900 líneas, Quotes.jsx ~3000 líneas)
