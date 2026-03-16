# PRD — Gestor: Work Flow de Procesos Integrales

## Descripcion
Plataforma full-stack para gestion de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementacion.

## Stack Tecnologico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt

## Funcionalidades Implementadas

### Modulo de Clientes
- CRUD completo con contactos CRM, Ficha Maestra v2.0 (4 cuadrantes)
- Bitacora de Inicio, OCR de RIF Digital, Importacion/Exportacion

### Modulo de Bancos y Entidades
- CRUD completo, Roadmap, Bitacora, Importacion masiva, Exportacion PDF
- Estados: PreProd, Primer Prod, Masificacion

### Modulo de Nuevos Productos — Pipeline I+D
- Pipeline: Negociacion → DESA → SQA → IMPLE → Promovido
- Hand-off automatico, Log Auditoria, Bitacora, Notificaciones simuladas

### Modulo de Integradores
- CRUD con importacion masiva, CRM tecnico, Bitacora

### Modulo de Cotizaciones
- Wizard multi-tipo (VPOS/PG, Equipos, Reparaciones)
- Flujo Administrativo Flexible con Protocolo de Excepcion
- PDF con WeasyPrint, Segmentacion VPOS/MPOS, Parametros Dinamicos
- **Segmentacion Pyme/Corp (2026-03-15)**: Boton dropdown "Nueva Implementacion" con dos opciones:
  - Clientes Pymes (verde): Flujos estandarizados y agiles
  - Clientes Corporativos (azul): Proyectos de gran envergadura
  - Campo `client_segment` (PYME/CORP) en modelo Quote y Project
  - Badge de segmento en wizard, columna Segmento en tabla, filtro por segmento

### Modulo de Proyectos
- Generacion automatica desde cotizaciones, hereda client_segment

### Modulo de Inventarios
- Fases 1-3: Almacenes, Entradas, Transferencias, Salidas automaticas
- Kardex, Trazabilidad, Buscador Inverso, Alertas Stock Minimo
- **Nota de Entrega PDF (2026-03-15)**: PDF profesional con correlativo NE-YYYY-XXXX
  - 5 secciones: Info Documento, Cliente/Destino, Detalle Bienes, Control Logistico, Recepcion
  - Paginacion "Pagina X de Y" con encabezados persistentes en todas las paginas
  - **VALIDADO (2026-03-16)**: 20/20 tests pasaron - testing_agent iteration_104

### Otros
- Dashboard KPIs, Tasa BCV, Nomenclatura PYME/CORP, Tipo Corp
- Gestion usuarios con roles/permisos

## Integraciones
- Resend (SIMULADO), WeasyPrint, reportlab, exchangedyn/dolarapi, openpyxl/pandas

## Backlog

### P1
- Herencia de cantidad_cajas a campo VTID en cotizaciones VPOS
- Verificacion Email y Recuperacion Contrasena
- Refactorizacion Quotes.jsx (4400+ lineas)
- Campos especificos Corp: Nro. Contrato Marco, SLA, etc.

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Integrators.jsx y Clients.jsx
