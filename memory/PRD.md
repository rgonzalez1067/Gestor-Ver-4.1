# PRD — Gestor: Work Flow de Procesos Integrales

## Descripcion
Plataforma full-stack para gestion de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementacion.

## Stack Tecnologico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt

## Funcionalidades Implementadas

### Modulo de Bancos y Entidades
- CRUD completo de bancos con logo upload
- Gestion de productos bancarios (VPOS, MPOS, PG, Link)
- Roadmap de integraciones por banco con pipeline visual de estatus
- Bitacora de Evolucion por Producto (2026-03-09)
- Consulta Global con Agrupamiento Dinamico (2026-03-09)
- Importacion masiva de bancos desde Excel/CSV
- Exportacion a PDF
- Matriz de certificacion con filtros interactivos

### Modulo de Integradores
- CRUD completo con importacion masiva (upsert)
- CRM tecnico con contactos multiples
- Bitacora de gestiones con alertas de compromisos vencidos y combo de contacto
- Historial de evolucion por integrador con persona de contacto
- Reporte de resumen con agrupacion dinamica
- Tabla simplificada (2026-03-09)

### Modulo de Clientes
- CRUD completo con contactos CRM
- Categorizacion comercial
- Bitacora de seguimiento

### Modulo de Cotizaciones
- Wizard de creacion multi-tipo (VPOS/PG, Equipos, Reparaciones)
- Calculo automatico de costos setup y recurrentes
- Tabla de costos recurrentes Payment Gateway
- Workflow de estados (Borrador -> Enviada -> Aprobada -> Facturada -> Pagada -> Entregada)
- **Flujo Administrativo Flexible** (2026-03-10): Todos los botones activos. Modal de Protocolo de Excepcion. Audit log, badge "Irregular", widget contador
- Generacion de PDF profesional con WeasyPrint + template HTML
- **Logo de empresa en PDF de equipos** (2026-03-10): El logo de Configuracion se embebe en el header del PDF
- Sistema de anexos por categoria
- **Fix: mark_quote_irregular null array** (2026-03-10)
- **Fix: PDF de equipos no se guardaba como anexo** (2026-03-10): Endpoint unificado que genera PDF, lo guarda, crea cotizacion y vincula anexo automaticamente
- **Fix: UI freeze tras generar PDF de equipos** (2026-03-10): resetWizard y onClose en finally block

### Modulo de Proyectos
- Generacion automatica desde cotizaciones aprobadas
- **Trigger Cotizacion -> Proyecto** (2026-03-10): Creacion automatica al enviar a implementacion
- **Persistencia de Proceso Irregular** (2026-03-10): Herencia de is_irregular, filtro y badge en Proyectos
- Asignacion a implementadores con logica dinamica Asignar/Reasignar
- Cambiar Estado rapido
- Seguimiento de estado, prioridad y matriz de implementacion
- Notas de seguimiento y bitacora de proyecto

### Otros
- Dashboard con KPIs
- Gestion de usuarios con roles y permisos
- Menu lateral abatible con estado persistente
- Tasa de cambio BCV

## Integraciones de Terceros
- **Resend**: Email (SIMULADO)
- **WeasyPrint**: Generacion de PDF desde HTML
- **reportlab/PyPDF2**: Generacion/Manipulacion de PDF
- **openpyxl/pandas**: Excel

## Backlog Priorizado

### P1 (Proximas)
- Verificacion de Email y Recuperacion de Contrasena
- Refactorizacion de `Quotes.jsx` (4200+ lineas)

### P2 (Futuras)
- Modulo de Reportes de ventas
- Logica de "Completado" en Roadmap de Bancos
- Refactorizacion de `Integrators.jsx` (1500+ lineas)
