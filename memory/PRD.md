# PRD - Cotizador Merchant Server

## Descripcion
Sistema integral de cotizaciones para plataformas de medios de pago. Full-stack: FastAPI + React + MongoDB.

## Funcionalidades Implementadas

### Modulos Core
1. Autenticacion: Registro/Login, roles (admin/user), sedes (TBP/LCH)
2. Gestion de Clientes (CRM): Multi-sede, contactos, bitacora, importacion Excel, busqueda server-side
3. Bancos y Medios de Pago: CRUD con productos, gateway_available flag
4. Integradores: Gestion, filtro por modalidad PG
5. Hardware: Pinpads, dispositivos, accesorios

### Sistema de Cotizaciones
6. Tipos: VPOS/MPOS, Payment Gateway, Link de Pago (desactivado)
7. Payment Gateway: Filtro integradores PG, validacion concepto-banco muchos-a-muchos, PDF 4 paginas
8. Nomenclatura: COT-AAAA-MM-NNN-SEDE atomica
9. Anexos y Workflow de Estados
10. Dashboard con alertas

### PDF y Previsualizacion
- Previsualizacion PDF: Modal con iframe, botones Descargar/Cerrar
- PDF VPOS con template dinamico + 4 paginas anexo estatico (Info relevante, Condiciones contratacion, Condiciones pago, Datos pago)
- PDF PG 4 paginas: Portada, Matriz Configuracion, Recurrentes (centrada), T&C

### Persistencia y Edicion
- Race condition fix con refs prevCajasRef/prevBancosRef
- Metadata persistence: lockBancos, autoBancos, bancosOverride, totalOverride
- MongoDB Indexes en clients y quotes

### Correos de Notificacion por Sede (2026-03-03)
- Correo de Ventas por sede: TBP y LCH con campo propio
- Backend: approve_quote, invoice_quote notifican a ventas de la sede
- Backend: collect_quote usa warehouse email per-sede

### Paginas Estaticas PDF VPOS (2026-03-03)
- Anexo VPOS 4 paginas en /backend/static_pdfs/anexo_vpos.pdf
- Se agregan automaticamente al final de cada PDF VPOS
- PDFs de Payment Gateway NO se ven afectados

### Extraccion Automatica de RIF Digital (2026-03-04)
- Endpoint POST /api/clients/parse-rif: sube PDF SENIAT, extrae RIF, Razon Social, Direccion Fiscal
- Parsing con PyPDF2 + regex (patron [JGVEP]\d{9}, texto post-RIF, texto post "DOMICILIO FISCAL")
- Validacion de duplicados: si RIF existe, ofrece agregar nueva sucursal
- Frontend: boton "Cargar desde RIF Digital", barra de progreso, auto-fill con resaltado amarillo
- Testing: 6/6 backend + todos los elementos UI verificados (iteration_58)

## Pendientes
- P0: Refactorizacion backend server.py (6900+ lineas)
- P1: Refactorizacion frontend Quotes.jsx (4300+ lineas)
- P1: Verificacion Email / Recuperacion Contrasena (Resend API)
- P2: Bug contadores Dashboard
- P2: Modulo de Reportes
