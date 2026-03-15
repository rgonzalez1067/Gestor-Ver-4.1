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
- Flujo Administrativo Flexible, PDF WeasyPrint, VPOS/MPOS, Parametros Dinamicos

### Modulo de Proyectos
- Generacion automatica desde cotizaciones

### Modulo de Inventarios
- **Fase 1-2**: Almacenes CRUD, Entradas con/sin seriales, Transferencias atomicas
- **Fase 3**: Salidas automaticas al entregar cotizacion + PDF
- **Kardex del Producto**: Drill-down con saldo resultante por movimiento
- **Trazabilidad de Salidas**: Popover "Ver Destinatario" con datos de cliente
- **Buscador Inverso por Cliente**: Busqueda de entregas por nombre
- **Alertas Stock Minimo**: Responsable de almacen, stock min configurable, trigger CheckStock, email HTML
- **Nota de Entrega PDF (2026-03-15)**: Rediseno completo del PDF de entrega:
  - Correlativo auto-incrementado NE-YYYY-XXXX (collection nota_entrega_counter)
  - 5 secciones: Info Documento, Cliente/Destino, Detalle Bienes, Control Logistico, Recepcion
  - Direccion multi-linea con word-wrap
  - Clasificacion Equipo vs Consumible
  - Campos: Transportado por, Guia/Placa
  - Contacto y telefono del cliente (desde contact1 o contacts CRM)
  - Proyecto asociado, Estatus "Despachado"
  - Pie de pagina: "Documento generado por MegaNexus - Trazabilidad de Inventario"
  - Soporte para logo PNG en esquina superior izquierda
  - DeliveryDialog actualizado con campos de transportista y guia/placa

### Otros
- Dashboard KPIs, Tasa BCV, Nomenclatura PYME/CORP, Tipo Corp
- Gestion usuarios con roles/permisos

## Reglas de Negocio Clave
- Condicion cliente: Prospecto=amarillo, Cliente=verde
- SERIALIZED_TYPES: ['pos', 'pinpad', 'mpos']
- Alerta stock: Saldo <= Stock Minimo AND min > 0 AND responsible_email exists
- Items Equipo: POS/Pinpad/MPOS. Resto: Consumible

## Integraciones
- Resend (SIMULADO), WeasyPrint, reportlab, exchangedyn/dolarapi, openpyxl/pandas

## Backlog

### P1
- Herencia de cantidad_cajas a campo VTID en cotizaciones
- Verificacion Email y Recuperacion Contrasena
- Refactorizacion Quotes.jsx (4400+ lineas)

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Integrators.jsx y Clients.jsx
