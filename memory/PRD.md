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

### Otros
- Dashboard KPIs, Tasa BCV (operativa via exchangedyn/dolarapi)
- Gestion usuarios con roles/permisos, Menu lateral

## Reglas de Negocio Clave
- **Condicion cliente**: Define color visual. Prospecto=amarillo, Cliente=verde
- **Ejecutivo filtrado**: Solo usuarios con cargo 'Ejecutivo de Ventas Pyme' o 'Ejecutivo de Ventas Corporativas'
- **Cantidad de Cajas**: Se hereda a campo VTID en cotizaciones (pendiente implementar)
- **Aplicativo condicionado**: Se filtra segun integrador seleccionado
- **Estados Integracion Bancaria**: Solo PreProd, Primer Prod, Masificacion (migrados automaticamente desde estados antiguos)

## Integraciones
- Resend (SIMULADO), WeasyPrint, exchangedyn/dolarapi, openpyxl/pandas

## Backlog

### P1
- Herencia de cantidad_cajas a campo VTID en cotizaciones
- Verificacion Email y Recuperacion Contrasena
- Refactorizacion Quotes.jsx (4200+ lineas)

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Integrators.jsx (1500+ lineas)
- Fix warning HTML en QuotesTable (span/tbody)
