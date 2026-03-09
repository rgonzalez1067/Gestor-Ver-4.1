# PRD — Gestor: Work Flow de Procesos Integrales

## Descripción
Plataforma full-stack para gestión de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementación.

## Stack Tecnológico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt

## Funcionalidades Implementadas

### Módulo de Bancos y Entidades
- CRUD completo de bancos con logo upload
- Gestión de productos bancarios (VPOS, MPOS, PG, Link)
- Roadmap de integraciones por banco con pipeline visual de estatus
- **Bitácora de Evolución por Producto** (2026-03-09): Timeline de hitos técnicos por cada integración, con captura automática de fase, edición y eliminación
- **Consulta Global con Agrupamiento Dinámico** (2026-03-09): Reporte gerencial con opciones de agrupación (Por Banco, Por Producto, Por Fase) con encabezados intermedios y totales
- Importación masiva de bancos desde Excel/CSV
- Exportación a PDF
- Matriz de certificación con filtros interactivos

### Módulo de Integradores
- CRM técnico con contactos múltiples
- Bitácora de gestiones con alertas de compromisos vencidos
- Historial de evolución por integrador (timeline)
- Reporte de resumen con agrupación dinámica (fase, producto, modalidad)
- Importación masiva con upsert y validación

### Módulo de Clientes
- CRUD completo con contactos CRM
- Categorización comercial
- Bitácora de seguimiento

### Módulo de Cotizaciones
- Wizard de creación multi-tipo (Implementación VPOS/PG, Equipos, Reparaciones)
- Cálculo automático de costos setup y recurrentes
- Tabla de costos recurrentes Payment Gateway
- Workflow de estados (Borrador → Enviada → Aprobada → Facturada → Pagada → Entregada)
- Generación de PDF
- Sistema de anexos por categoría

### Módulo de Proyectos
- Generación automática desde cotizaciones aprobadas
- Asignación a implementadores
- Seguimiento de estado y prioridad
- Notas de seguimiento

### Otros
- Dashboard con KPIs
- Gestión de usuarios con roles y permisos
- Menú lateral abatible con estado persistente
- Tasa de cambio BCV

## Backlog Priorizado

### P1 (Próximas)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx`

### P2 (Futuras)
- Módulo de Reportes de ventas
- Lógica de "Completado" en Roadmap de Bancos (mover a Activos)
- Refactorización de `Integrators.jsx` (>1500 líneas)

## Integraciones de Terceros
- **Resend**: Email (SIMULADO)
- **reportlab/PyPDF2**: Generación PDF
- **pytesseract/pdf2image**: OCR
- **openpyxl/pandas**: Excel
- **xlsx** (frontend): Exportación Excel
