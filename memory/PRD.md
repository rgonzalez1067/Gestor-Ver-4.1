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
- CRUD completo con importación masiva (upsert)
- CRM técnico con contactos múltiples
- Bitácora de gestiones con alertas de compromisos vencidos y **combo de contacto** (dropdown + escritura libre)
- Historial de evolución por integrador con **persona de contacto** (reemplazó campo Fase)
- Reporte de resumen con agrupación dinámica
- Tabla simplificada: eliminadas columnas "Estatus" y "Fase" (2026-03-09)
- Formulario simplificado: eliminado campo "Fase de Integración" (2026-03-09)

### Módulo de Clientes
- CRUD completo con contactos CRM
- Categorización comercial
- Bitácora de seguimiento

### Módulo de Cotizaciones
- Wizard de creación multi-tipo (Implementación VPOS/PG, Equipos, Reparaciones)
- Cálculo automático de costos setup y recurrentes
- Tabla de costos recurrentes Payment Gateway
- Workflow de estados (Borrador → Enviada → Aprobada → Facturada → Pagada → Entregada)
- **Flujo Administrativo Flexible** (2026-03-10): Todos los botones activos sin bloqueo por estado. Modal de Protocolo de Excepción con justificación y fecha de regularización. Audit log, badge "Irregular" naranja, widget contador
- Generación de PDF profesional con WeasyPrint + template HTML
- Sistema de anexos por categoría

### Módulo de Proyectos
- Generación automática desde cotizaciones aprobadas
- Asignación a implementadores con lógica dinámica **Asignar/Reasignar** (2026-03-09): muestra responsable actual, requiere fecha y motivo en reasignación
- **Cambiar Estado rápido** (2026-03-09): diálogo con opciones visuales, fecha y comentario documentado en bitácora automática
- Seguimiento de estado, prioridad y matriz de implementación
- Notas de seguimiento y bitácora de proyecto

### Otros
- Dashboard con KPIs
- Gestión de usuarios con roles y permisos
- Menú lateral abatible con estado persistente
- Tasa de cambio BCV

## Integraciones de Terceros
- **Resend**: Email (SIMULADO)
- **reportlab/PyPDF2**: Generación PDF
- **pytesseract/pdf2image**: OCR
- **openpyxl/pandas**: Excel
- **xlsx** (frontend): Exportación Excel

## Backlog Priorizado

### P1 (Próximas)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx`

### P2 (Futuras)
- Módulo de Reportes de ventas
- Lógica de "Completado" en Roadmap de Bancos (mover a Activos)
- Refactorización de `Integrators.jsx` (>1500 líneas)

## Integraciones de Terceros
