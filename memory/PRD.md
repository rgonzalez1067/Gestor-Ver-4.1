# PRD — Gestor: Work Flow de Procesos Integrales

## Descripcion
Plataforma full-stack para gestion de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementacion.

## Stack Tecnologico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt
- **PDF**: reportlab (paginacion, multi-columna, encabezados persistentes)

## Funcionalidades Implementadas

### Modulo de Clientes
- CRUD completo con contactos CRM, Ficha Maestra v2.0 (4 cuadrantes)
- Bitacora de Inicio, OCR de RIF Digital, Importacion/Exportacion

### Modulo de Bancos y Entidades
- CRUD completo, Roadmap, Bitacora, Importacion masiva, Exportacion PDF

### Modulo de Nuevos Productos — Pipeline I+D
- Pipeline: Negociacion → DESA → SQA → IMPLE → Promovido
- Hand-off automatico, Log Auditoria, Bitacora

### Modulo de Integradores
- CRUD con importacion masiva, CRM tecnico, Bitacora

### Modulo de Cotizaciones
- Wizard multi-tipo (VPOS/PG, Equipos, Reparaciones)
- Flujo Administrativo Flexible con Protocolo de Excepcion
- PDF con WeasyPrint, Segmentacion VPOS/MPOS, Parametros Dinamicos
- Segmentacion Pyme/Corp con campo client_segment

### Modulo de Proyectos
- Generacion automatica desde cotizaciones, hereda client_segment

### Modulo de Inventarios
- **Fases 1-3**: Almacenes, Entradas, Transferencias, Salidas automaticas
- **Kardex y Trazabilidad**: Vista historial por producto, busqueda inversa por cliente
- **Alertas Stock Minimo**: Umbrales configurables por item
- **Nota de Entrega PDF**: Correlativo NE-YYYY-XXXX, 5 secciones, paginacion X/Y
- **Nota de Transferencia PDF**: Correlativo TRF-YYYY-XXXX, nota tecnica Pinpads
- **Precarga y Certificacion (2026-03-16)**: Cuarentena tecnica para entradas masivas
  - Campo certification_status: "precarga" (cuarentena) / "certificado" (disponible)
  - Precargas NO suman al stock disponible
  - Boton "Certificar" con flujo: upload Excel → validacion mismatch → resolucion
  - Opciones: actualizar con Excel o mantener original
  - VALIDADO: 13/13 tests (iteration_106)
- **Carga Masiva por Excel (2026-03-16)**: Seleccion de seriales desde archivo
  - Upload Excel en dialogos de Salida y Transferencia
  - Validacion automatica contra stock disponible
  - Ventana de auditoria con seriales erroneos
  - Endpoint validate-serials-stock con respuesta detallada
  - VALIDADO: iteration_106
- **Logistica de Despacho (2026-03-16)**: Metodo de envio obligatorio
  - Entrega Personalizada: Nombre, Cedula, Telefono receptor
  - Courier: ZOOM (Oficina), ZOOM (Casillero), MRW, Tealca + Oficina destino
  - Datos reflejados en seccion 4 del PDF Nota de Entrega
  - VALIDADO: iteration_106
- **Multi-columna Seriales en PDFs (2026-03-16)**: 3 columnas para >4 seriales
  - Reduce paginas significativamente en documentos con alto volumen
  - Aplicado a Nota de Entrega y Nota de Transferencia
  - VALIDADO: iteration_106

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

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Integrators.jsx y Clients.jsx
- Campos especificos Corp: Nro. Contrato Marco, SLA
