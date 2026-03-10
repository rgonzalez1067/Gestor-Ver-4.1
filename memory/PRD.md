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
- Bitacora de Evolucion por Producto
- Consulta Global con Agrupamiento Dinamico
- Importacion masiva de bancos desde Excel/CSV
- Exportacion a PDF
- Matriz de certificacion con filtros interactivos

### Modulo de Integradores
- CRUD completo con importacion masiva (upsert)
- CRM tecnico con contactos multiples
- Bitacora de gestiones con alertas de compromisos vencidos
- Historial de evolucion por integrador
- Reporte de resumen con agrupacion dinamica

### Modulo de Clientes
- CRUD completo con contactos CRM
- Categorizacion comercial
- Bitacora de seguimiento
- **OCR de RIF Digital** con sanitizacion automatica
- **Sanitizacion de RIF** (2026-03-10): Funcion sanitize_rif() elimina guiones, espacios y caracteres especiales. J-00000000-0 -> J000000000. Aplicado en create, update y parse OCR
- **Tabla responsiva** (2026-03-10): Acciones en DropdownMenu (Escanear RIF, Descargar RIF, Editar, Eliminar) con Bitacora como boton independiente. Columnas con ancho fijo y overflow-x-auto

### Modulo de Cotizaciones
- Wizard de creacion multi-tipo (VPOS/PG, Equipos, Reparaciones)
- Calculo automatico de costos setup y recurrentes
- Workflow de estados flexible con Protocolo de Excepcion
- **Flujo Administrativo Flexible**: Todos los botones activos. Modal de excepcion. Audit log, badge "Irregular", widget contador
- **Flujo de regularizacion** (2026-03-10): Permite facturar/cobrar cotizaciones ya entregadas via excepcion
- Generacion de PDF profesional con WeasyPrint + logo de empresa
- **PDF de equipos vinculado como anexo** (2026-03-10): Endpoint unificado genera PDF, lo guarda en servidor y crea cotizacion con anexo automatico
- **Fix UI freeze** (2026-03-10): resetWizard y onClose en finally block

### Modulo de Proyectos
- Generacion automatica desde cotizaciones (trigger al enviar a implementacion)
- Persistencia de Proceso Irregular (herencia de is_irregular, filtro y badge)
- Asignacion a implementadores con logica dinamica Asignar/Reasignar
- Cambiar Estado rapido
- Seguimiento de estado, prioridad y matriz de implementacion

### Otros
- Dashboard con KPIs
- Gestion de usuarios con roles y permisos
- Menu lateral abatible
- Tasa de cambio BCV

## Integraciones de Terceros
- **Resend**: Email (SIMULADO)
- **WeasyPrint**: PDF desde HTML
- **reportlab/PyPDF2**: PDF alternativo
- **openpyxl/pandas**: Excel

## Backlog Priorizado

### P1 (Proximas)
- Verificacion de Email y Recuperacion de Contrasena
- Refactorizacion de Quotes.jsx (4200+ lineas)

### P2 (Futuras)
- Modulo de Reportes de ventas
- Logica de "Completado" en Roadmap de Bancos
- Refactorizacion de Integrators.jsx (1500+ lineas)
