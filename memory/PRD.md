# PRD — Gestor: Work Flow de Procesos Integrales

## Descripcion
Plataforma full-stack para gestion de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementacion.

## Stack Tecnologico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt
- **PDF**: reportlab (paginacion, multi-columna, word-wrap, anchos fijos)

## Funcionalidades Implementadas

### Modulo de Clientes
- CRUD completo con contactos CRM, Ficha Maestra v2.0 (4 cuadrantes)
- Bitacora de Inicio, OCR de RIF Digital, Importacion/Exportacion

### Modulo de Bancos y Entidades
- CRUD completo, Roadmap, Bitacora, Importacion masiva, Exportacion PDF

### Modulo de Nuevos Productos — Pipeline I+D
- Pipeline: Negociacion → DESA → SQA → IMPLE → Promovido

### Modulo de Integradores
- CRUD con importacion masiva, CRM tecnico, Bitacora

### Modulo de Cotizaciones
- Wizard multi-tipo, Protocolo de Excepcion, PDF, Segmentacion Pyme/Corp

### Modulo de Proyectos
- Generacion automatica desde cotizaciones

### Modulo de Inventarios
- **Almacenes y Stock**: CRUD, entradas, transferencias, salidas automaticas
- **Kardex y Trazabilidad**: Vista historial por producto, busqueda inversa por cliente
- **Alertas Stock Minimo**: Umbrales configurables por item
- **Nota de Entrega PDF**: Correlativo NE-YYYY-XXXX, 5 secciones, paginacion X/Y
- **Nota de Transferencia PDF**: Correlativo TRF-YYYY-XXXX, nota tecnica Pinpads
- **Precarga y Certificacion**: Cuarentena tecnica para entradas masivas
  - certification_status: "precarga" / "certificado"
  - Flujo: upload Excel → mismatch → resolucion
- **Carga Masiva Excel**: En Salida, Transferencia y Nota de Entrega
  - Validacion anti-duplicados: internos (filas repetidas) y contra BD
  - Ventana de auditoria con detalle de errores
  - VALIDADO: iteration_107
- **Logistica de Despacho**: Metodo envio obligatorio
  - Personalizada: Nombre, Cedula, Telefono receptor
  - Courier: ZOOM (Oficina), ZOOM (Casillero), MRW, Tealca, Domesa
  - VALIDADO: iteration_107
- **Transferencia → Precarga en Destino (2026-03-16)**: 
  - Al transferir A→B, entrada en B = certification_status "precarga"
  - Responsable de B debe certificar fisicamente antes de disponibilizar
  - VALIDADO: iteration_107
- **Multi-columna Seriales en PDFs**: 3 columnas para >4 seriales
  - Anchos fijos con wordWrap="CJK" para evitar overflow
  - VALIDADO: iteration_107

### Otros
- Dashboard KPIs, Tasa BCV, Gestion usuarios con roles/permisos

## Integraciones
- Resend (SIMULADO), WeasyPrint, reportlab, exchangedyn/dolarapi, openpyxl/pandas

## Backlog

### P1
- Herencia de cantidad_cajas a campo VTID en cotizaciones VPOS
- Verificacion Email y Recuperacion Contrasena
- Refactorizacion Quotes.jsx

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Integrators.jsx y Clients.jsx
