# PRD — Gestor: Work Flow de Procesos Integrales

## Descripcion
Plataforma full-stack para gestion de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementacion.

## Stack Tecnologico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt

## Funcionalidades Implementadas

### Modulo de Clientes
- CRUD completo con contactos CRM
- Ficha Maestra v2.0: Layout 4 cuadrantes (2x2 grid)
- Bitacora de Inicio, Sanitizacion automatica de RIF, OCR de RIF Digital, Importacion/Exportacion

### Modulo de Bancos y Entidades
- CRUD completo con logo, productos bancarios, Roadmap
- Bitacora de Evolucion, Consulta Global, Importacion masiva, Exportacion PDF, Matriz certificacion
- Estados simplificados: PreProd, Primer Prod, Masificacion

### Modulo de Nuevos Productos — Pipeline I+D
- Pipeline: Negociacion → DESA → SQA → IMPLE → Promovido
- Hand-off automatico a Bancos, Log de Auditoria de Transiciones
- Bitacora de Evolucion, Stats cards, Notificaciones simuladas

### Modulo de Integradores
- CRUD con importacion masiva, CRM tecnico, Bitacora

### Modulo de Cotizaciones
- Wizard multi-tipo (VPOS/PG, Equipos, Reparaciones)
- Flujo Administrativo Flexible con Protocolo de Excepcion
- PDF con WeasyPrint, Segmentacion VPOS/MPOS, Parametros Dinamicos

### Modulo de Proyectos
- Generacion automatica desde cotizaciones, Persistencia Irregular

### Modulo de Inventarios
- **Fase 1: Gestion de Almacenes** — CRUD almacenes con nombre, ubicacion, notas, responsable
- **Fase 2: Entradas y Transferencias** — Entradas con/sin seriales, transferencias atomicas, historial
- **Fase 3: Salidas Automaticas y Hoja de Ruta** — DeliveryDialog, PDF archivado en anexos
- **Kardex del Producto** — Drill-down con saldo resultante por movimiento
- **Trazabilidad de Salidas** — Popover "Ver Destinatario" con cliente, RIF, cotizacion, seriales
- **Buscador Inverso por Cliente** — Busqueda de entregas historicas por nombre de cliente
- **Sistema de Alertas de Stock Minimo (2026-03-15)**:
  - Responsable de Almacen: Dropdown de usuarios, vincula email para alertas
  - Stock Minimo por item: Campo editable inline por item/almacen (collection min_stock_config)
  - Motor de Alertas: Trigger CheckStock despues de cada salida y transferencia
  - Plantilla de correo HTML con datos de almacen, producto, stock actual vs minimo
  - Visual: Saldo en rojo, punto pulsante, fondo rojo para items bajo minimo
  - Seguridad: Stock minimo negativo no permitido (400)

### Otros
- Dashboard KPIs, Tasa BCV, Nomenclatura PYME/CORP, Tipo Corp
- Gestion usuarios con roles/permisos

## Reglas de Negocio Clave
- Condicion cliente: Prospecto=amarillo, Cliente=verde
- Ejecutivo filtrado por cargo
- SERIALIZED_TYPES: ['pos', 'pinpad', 'mpos']
- Alerta stock: Saldo <= Stock Minimo AND Stock Minimo > 0 AND responsible_email exists

## Integraciones
- Resend (SIMULADO), WeasyPrint, exchangedyn/dolarapi, openpyxl/pandas, reportlab

## Backlog

### P1
- Herencia de cantidad_cajas a campo VTID en cotizaciones
- Verificacion Email y Recuperacion Contrasena
- Refactorizacion Quotes.jsx (4400+ lineas)

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Integrators.jsx y Clients.jsx
