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
- **Ficha Maestra v2.0** (2026-03-11): Layout 4 cuadrantes (2x2 grid)
  - Q1 Estatus y Definicion Legal: Condicion (Prospecto/Cliente con color dinamico verde/amarillo), RIF, Nombre Juridico/Fantasia, Grupo Economico, Segmento
  - Q2 Capacidad Operativa: Cantidad Tiendas, Cantidad Cajas, Categoria Comercial
  - Q3 Ubicacion y Sedes: Direccion Fiscal, Sucursal, Direccion Sucursal
  - Q4 Gestion y Soluciones: Ejecutivo Propietario (dropdown filtrado por cargo Ejecutivo), Integrador/Aplicativo (dropdowns vinculados), Tipo Servicio (multi-select)
- Bitacora de Inicio (registrar primer contacto)
- Sanitizacion automatica de RIF
- Tabla responsiva con DropdownMenu + badge Condicion
- OCR de RIF Digital, Importacion/Exportacion

### Modulo de Bancos y Entidades
- CRUD completo con logo, productos bancarios, Roadmap
- Bitacora de Evolucion, Consulta Global con Agrupamiento
- Importacion masiva, Exportacion PDF, Matriz certificacion
- **Optimizacion Flujo Integracion (2026-02-20)**: Estados simplificados de 6 a 3: `PreProd`, `Primer Prod`, `Masificacion`
- Notificacion simulada (MOCKED) por email al equipo de ventas al cambiar estado de integracion
- Migracion automatica de estados antiguos en runtime (STATUS_MIGRATION map)

### Modulo de Nuevos Productos — Pipeline I+D (2026-02-20)
- CRUD completo de productos en desarrollo pre-despliegue
- Pipeline de estados: Negociacion → DESA → SQA → IMPLE → Promovido
- **Seleccion de Medio de Pago desde Catalogo Maestro** (dropdown, no texto libre)
- Seleccion de Banco Patrocinador/Socio al crear producto
- **Hand-off automatico**: Al cambiar a IMPLE, inserta integracion en banco con estado PreProd y marca producto como Promovido
- **Log de Auditoria de Transiciones (StatusTransitionLog)**: Registra estado anterior, nuevo, fecha/hora, usuario, dias en fase anterior
- Bitacora de Evolucion propia con timeline unificado (hitos manuales + transiciones automaticas)
- Notificaciones simuladas (MOCKED): incluyen fecha exacta y lead time por fase
- Stats cards por fase + seccion visual de Promovidos

### Modulo de Integradores
- CRUD con importacion masiva, CRM tecnico
- Bitacora de gestiones, Historial evolucion, Reporte agrupado
- Endpoint dropdown para selectores ligeros

### Modulo de Cotizaciones
- Wizard multi-tipo (VPOS/PG, Equipos, Reparaciones)
- Flujo Administrativo Flexible con Protocolo de Excepcion
- PDF con WeasyPrint + logo empresa, PDF equipos como anexo automatico
- Flujo de regularizacion (facturar/cobrar post-entrega)

### Modulo de Proyectos
- Generacion automatica desde cotizaciones, Persistencia Irregular
- Asignacion dinamica, Cambiar Estado rapido

### Modulo de Inventarios (2026-03-14)
- **Fase 1: Gestion de Almacenes** — CRUD almacenes con nombre, ubicacion, notas
- **Fase 2: Entradas y Transferencias** — Entradas de stock (con/sin seriales), validacion de hardware critico (POS/Pinpad/MPOS), transferencias atomicas entre almacenes, historial de movimientos, carga de seriales desde Excel
- **Fase 3: Salidas Automaticas y Hoja de Ruta (2026-03-14)** — Al entregar cotizacion de equipos ("Entregada"), el stock se deduce automaticamente del almacen seleccionado. UI con DeliveryDialog para seleccionar almacen y seriales. Generacion de PDF "Hoja de Ruta" archivado en anexos de cotizacion y cliente.
  - Endpoint `GET /api/quotes/{id}/delivery-prep` para preparar datos de entrega
  - Endpoint `POST /api/quotes/{id}/deliver` con {warehouse_id, delivery_items, notes}
  - Generador PDF: `/app/backend/services/hoja_ruta_pdf.py`
  - Componente frontend: `/app/frontend/src/components/quotes/DeliveryDialog.jsx`

### Otros
- **Segmentacion VPOS/MPOS (2026-03-13)**: Tipos de cotizacion separados. MPOS: pricing fijo Outsourcing, sin VPN, integrador opcional, hardware filtrado a POS (no Pinpads)
- **Parametros Dinamicos VPOS (2026-03-13)**: Toggles Si/No para 'Configuracion PinPads' y 'Requiere VPN'. Recalculo en tiempo real. Solo aplica a VPOS.
- Dashboard KPIs, Tasa BCV (operativa via exchangedyn/dolarapi)
- **Nomenclatura Sedes (2026-02-20)**: TBP renombrado a PYME, LCH renombrado a CORP
- **Tipo Corp (2026-03-13)**: Nuevo campo obligatorio en Medios de Pago. Valores: 'Derecho de Uso', 'Apoyo Tecnico', 'Soporte y Monitoreo'. Propagado a integraciones de Bancos y Nuevos Productos.
- Gestion usuarios con roles/permisos, Menu lateral

## Reglas de Negocio Clave
- **Condicion cliente**: Define color visual. Prospecto=amarillo, Cliente=verde
- **Ejecutivo filtrado**: Solo usuarios con cargo 'Ejecutivo de Ventas Pyme' o 'Ejecutivo de Ventas Corporativas'
- **Cantidad de Cajas**: Se hereda a campo VTID en cotizaciones (pendiente implementar)
- **Aplicativo condicionado**: Se filtra segun integrador seleccionado
- **Estados Integracion Bancaria**: Solo PreProd, Primer Prod, Masificacion
- **SERIALIZED_TYPES**: ['pos', 'pinpad', 'mpos'] — requieren seriales en inventario

## Integraciones
- Resend (SIMULADO), WeasyPrint, exchangedyn/dolarapi, openpyxl/pandas, reportlab (PDF Hoja de Ruta)

## Backlog

### P1
- Herencia de cantidad_cajas a campo VTID en cotizaciones
- Verificacion Email y Recuperacion Contrasena
- Refactorizacion Quotes.jsx (4400+ lineas)

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Integrators.jsx y Clients.jsx
- Fix warning HTML en QuotesTable (span/tbody)
