# PRD — Gestor: Work Flow de Procesos Integrales

## Descripcion
Plataforma full-stack para gestion de cotizaciones, clientes, bancos, medios de pago, dispositivos, integradores y proyectos de implementacion.

## Stack Tecnologico
- **Backend**: FastAPI + MongoDB (motor_asyncio)
- **Frontend**: React + Shadcn/UI + Tailwind CSS
- **Auth**: JWT con bcrypt
- **PDF**: reportlab (paginacion, multi-columna, word-wrap, anchos porcentuales, PageBreak)

## Funcionalidades Implementadas

### Modulo de Clientes
- CRUD completo con contactos CRM, Ficha Maestra v2.0 (4 cuadrantes)
- Bitacora de Inicio, OCR de RIF Digital, Importacion/Exportacion
- **Plantilla Importacion Actualizada (2026-03-17)**: 24 columnas (A-X), 3 hojas Excel (Plantilla, Instrucciones, Valores Validos). Validaciones: regex RIF, lookup ejecutivos/integradores, formato fecha, numeros, valores permitidos. Mensajes error: "Fila X, Col Y (Campo): descripcion + accion sugerida". Descarga CSV errores. VALIDADO: 15/15 backend + 7/7 frontend (iter_110)

### Modulo de Bancos y Entidades
- CRUD completo, Roadmap, Bitacora, Importacion masiva, Exportacion PDF
- **Sincronizacion con Pipeline I+D (2026-03-16)**:
  - Mirroring: productos en Negociacion/DESA/SQA visibles en roadmap del banco
  - Fase A (read-only): selectores bloqueados con Lock + "Gestionado en I+D"
  - Fase B (editable): PreProd -> Primer Prod -> Masificacion desde Bancos
  - Link bidireccional: source_product_id en integracion
  - Sync bidireccional: cambios en banco actualizan bank_integration_status en new_product
  - Validacion backend: rechaza cambios desde Bancos si producto en Fase A (403)
  - Pipeline visual extendido: Negoc -> DESA -> SQA -> PreProd -> Primer Prod -> Masificacion
  - Badge "I+D" para items provenientes del pipeline
  - VALIDADO: 17/17 tests (iteration_108)

### Modulo de Nuevos Productos — Pipeline I+D
- Pipeline: Negociacion -> DESA -> SQA -> IMPLE -> Promovido
- Hand-off automatico con source_product_id, Log Auditoria, Bitacora

### Modulo de Integradores
- CRUD con importacion masiva, CRM tecnico, Bitacora
- **Tablero de Asignacion Gerencial (2026-03-17)**:
  - Flujo de creacion sin gestor obligatorio (asignacion posterior)
  - Endpoint PUT /api/integrators/{id}/assign con notificacion email (SIMULADA)
  - Dropdown inline en tabla para asignar gestor a proyectos pendientes
  - Stat card "Sin Asignar" en panel de estadisticas (5 cards)
  - Formulario de creacion sin campo Gestor; edicion con campo Gestor
  - VALIDADO: 11/11 backend + 6/6 frontend tests (iteration_109)
- **Reestructuracion Fase 1/Fase 2 (2026-03-17)**:
  - Fase 1 (Creacion): Solo datos tecnicos: Nombre, Tipo Integracion, Tipo Integrador, Aplicativo, Contactos Tecnicos
  - Fase 2 (Gestion/Edicion): Modalidad, Categoria, Gestor, Implementador, Estatus
  - Nuevo campo "Implementador" con dropdown filtrado por cargo "Implementador" en BD
  - Endpoint GET /api/auth/implementadores para listar usuarios implementadores
  - Endpoint PUT /api/integrators/{id}/assign-implementador con confirmacion y email con contactos tecnicos
  - Colores tabla: amarillo = sin implementador, azul = con implementador en ejecucion
  - Stats: Total, Certificados, En Ejecucion, Sin Implementador, Suspendidos
  - VALIDADO: 8/8 backend + 9/9 frontend tests (iteration_111)

### Modulo de Cotizaciones
- Wizard multi-tipo, Protocolo de Excepcion, PDF, Segmentacion Pyme/Corp
- **Optimizacion (2026-03-18)**: Regularizacion de estados (pasos omitidos ejecutables sin retroceder estado), terminologia actualizada (Aprobacion, Factura/Proforma, Cobranza), modal envio con mensaje personalizado (200 chars) + CC dinamicos. VALIDADO iter_113
- **Bug Fix "Enviar a Implementacion" (2026-03-18)**: Corregido caso faltante en confirmEmailAndProceed() que bloqueaba la accion. VALIDADO iter_114
- **Categorizacion de Equipos y Condiciones Legales (2026-03-20)**:
  - Dividida categoria "Equipos" (Dispositivo) en "Equipos Verifone" y "Equipos Morefun" en EquipmentQuoteWizard
  - Eliminado dropdown de subtipo POS/Pinpad; ahora 4 categorias planas: Verifone, Morefun, Accesorios, Reparaciones
  - PDFs de condiciones legales almacenados en /app/backend/static_pdfs/ (4 archivos)
  - Funcion append_equipment_conditions en config.py anexa automaticamente el PDF de condiciones al generar cotizacion
  - Diferenciacion por sede para Verifone: PYME→condiciones TBP, CORP→condiciones LCH
  - Endpoint generate-equipment-pdf actualizado con nuevos type_labels y logica de anexion
  - Flujo de Implementacion (VPOS/MPOS/Gateway) NO modificado
  - VALIDADO: 10/10 backend + 6/6 frontend (iteration_119)

### Modulo de Proyectos - Detalle de Implementacion
- Tickets, progreso, matriz de implementacion, multitienda
- **Mejora Header (2026-03-21)**: Rediseño del header en 3 bloques: Datos del Proyecto, Implementacion, Avance y Acciones. Mejor jerarquia visual, alineacion y espaciado. VALIDADO iter_120
- **Carga Masiva de Seriales para Reparaciones (2026-03-21)**:
  - Nuevo endpoint POST /api/quotes/validate-repair-serials: sube Excel, extrae seriales, valida vs inventario
  - VALIDADO: 13/13 backend + frontend OK (iteration_121)
- **Flujo Ciclico Multi-Modelo para Reparaciones (2026-03-22)**:
  - Reingenieria completa del flujo de reparaciones: ciclo Modelo > Cantidad > Seriales > Confirmar
  - Selector de modelos POS/Pinpad del inventario con buscador
  - Validacion de cuota: seriales deben coincidir con cantidad declarada
  - Soporte para multiples modelos en una misma orden
  - Ingreso manual y masivo (Excel) de seriales por modelo
  - PDF: Anexo de Seriales por modelo entre cotizacion y condiciones legales
  - Nota de advertencia al final del anexo sobre verificacion de modelos/cantidades
  - VALIDADO: 17/17 backend + frontend OK (iteration_122)
- **Segmentacion Catalogo Bien/Servicio (2026-03-22)**:
  - Nuevo campo asset_type (Bien/Servicio) en modelo Hardware, obligatorio al crear/editar
  - Filtrado automatico: Reparaciones y Implementaciones solo muestran items con asset_type='Bien'
  - Hardware.jsx: columna Clasificacion con badges teal/purple, selector en formulario
  - VALIDADO: 14/14 backend + frontend OK (iteration_123)
- **Fix Plantillas (2026-03-21)**: Corregido error critico al cargar plantillas (body_html vs body). Toast de error si falla la carga. VALIDADO iter_120

### Modulo de Proyectos
- Generacion automatica desde cotizaciones
- **Flujo Multitienda (2026-03-18)**:
  - Dialogo al enviar a implementacion: "Es Multitienda? Si/No"
  - Si "Si": recoleccion ciclica de tiendas (nombre + cajas) hasta sum == total cotizacion
  - Backend: project_type='multistore', stores=[{store_id, name, box_count, implementation_matrix, status}]
  - Endpoint PUT /api/projects/{id}/stores/{store_id}/matrix/phase para matrices independientes
  - Frontend: Badge "Multitienda (N)" en tabla de proyectos
  - Frontend: Tabs por tienda en detalle con matrices de seguimiento independientes
  - VALIDADO: 8/8 backend + 7/7 frontend (iteration_114)
- **Reingenieria Matriz de Implementacion + Notificaciones (2026-03-19)**:
  - Hito 1 Hard Stop: Boton "Notificar Cliente" en cabecera. Si no ejecutado, matriz bloqueada (grayed out con Lock)
  - Hito 2: Notificacion consolidada a bancos (1 email por banco con todos sus productos)
  - Endpoint POST /api/projects/{id}/notify-client con email simulado al cliente
  - Endpoint POST /api/projects/{id}/notify-bank con email consolidado al banco
  - Endpoint GET /api/projects/{id}/rollup para avance automatico
  - Proyecto Single: 5 fases editables + notificacion consolidada por banco
  - Proyecto Multitienda: Matriz principal read-only con barras de progreso (Roll-up)
  - Tiendas: 4 fases sin "Notificado" (Recibido, Configurado, Testeado, En Produccion)
  - Avance automatico: promedio ponderado de avances de tiendas -> rollup_progress
  - Hub de Comunicaciones: Placeholder para plantillas HTML futuras
  - VALIDADO: 16/16 backend + 13/13 frontend (iteration_115)
- **Ticket + Email Ad-hoc + Progreso Estandarizado (2026-03-19)**:
  - Numero de Ticket obligatorio al asignar proyecto (campo en dialogo, validacion unicidad)
  - Ticket reemplaza nro de proyecto en pantalla principal cuando existe
  - Busqueda por ticket en tabla de proyectos
  - Ticket incluido automaticamente en asunto/cuerpo de todos los emails
  - Modulo de Comunicacion Flexible: email ad-hoc con destinatarios dinamicos, asunto personalizado, mensaje (500 chars max), adjuntos (archivos e imagenes), auto-registro en bitacora
  - Endpoint POST /api/projects/{id}/send-adhoc-email con FormData multipart
  - Progreso estandarizado: calculo de avance % para proyectos single igual que multitienda
  - Barra de progreso en tabla principal para TODOS los proyectos
  - GET /api/projects/{id}/rollup ahora soporta single y multistore
  - VALIDADO: 14/14 backend + 8/8 frontend (iteration_116)
- **Modulo de Comunicaciones Avanzado (2026-03-20)**:
  - Notificaciones Secuenciales: 4 niveles (Primera Comunicacion, 1er Recordatorio, 2do Recordatorio, 3er Recordatorio)
  - Activacion secuencial estricta (nivel N requiere N-1 ejecutado). Bancos requieren cliente notificado.
  - Asunto dinamico por nivel. Registro en bitacora con contenido completo (email_detail).
  - "Otras Notificaciones" (ex "Enviar Correo"): 1000 chars, ventana grande, dropdown plantillas predefinidas
  - Panel Admin CRUD plantillas de correo (GET/POST/PUT/DELETE /api/email-templates)
  - Contactos sugeridos del Cliente y Bancos del proyecto al abrir dialog
  - Boton "Adjuntar Matriz de Seguimiento" genera tabla HTML del estatus actual
  - Visualizacion de contenido de correo en Bitacora: boton "Ver Correo" abre dialogo con contenido completo
  - Endpoint POST /api/projects/{id}/send-notification (unificado, secuencial)
  - Endpoint GET /api/projects/{id}/notification-history
  - Endpoint GET /api/projects/{id}/suggested-contacts
  - VALIDADO: 18/18 backend + 12/12 frontend (iteration_117)
- **Ajustes Criticos Plantillas y Notificaciones (2026-03-20)**:
  - Fix bug Editar plantillas: campo body_content unificado en POST y PUT
  - UX plantillas: dialogo expandido max-w-4xl, layout 2 columnas (lista + formulario), botones Editar/Eliminar visibles
  - Conteo chars: limite 1000 solo para cuerpo del mensaje, matrix_html enviado como campo separado
  - Destinatarios en diálogo Notificaciones: muestra emails del cliente/banco automaticamente
  - Contactos sugeridos en Otras Notificaciones: se cargan al abrir dialogo
  - VALIDADO: 10/10 backend + 7/7 frontend (iteration_118)

### Modulo de Inventarios
- Almacenes, Stock, Entradas, Transferencias, Salidas automaticas
- Kardex, Trazabilidad, Busqueda inversa, Alertas Stock Minimo
- Precarga/Certificacion con cuarentena tecnica
- Carga masiva Excel con validacion anti-duplicados
- Logistica de Despacho (Personalizada/Courier) con Domesa
- Transferencia -> Precarga obligatoria en destino
- Multi-columna seriales en PDFs, anchos porcentuales, word-wrap
- Nota de Entrega PDF (NE-YYYY-XXXX) y Nota de Transferencia PDF (TRF-YYYY-XXXX)
- **Correcciones PDF Layout (2026-03-18)**:
  - Fix overflow lateral: table-layout fixed con anchos porcentuales (CONTENT_W * 0.XX)
  - Direccion multi-linea con ParagraphStyle wordWrap='CJK' (2-3 lineas)
  - PageBreak forzado: Seccion 5 "Recepcion y Conformidad" inicia en pagina 2
  - Encabezado persistente en paginas 2+ (logo + titulo + info compacta)
  - Fix NumberedCanvas: _startPage() en vez de super().showPage() (elimina duplicacion)
  - Paginacion "Pagina X/Y" correcta en ambos documentos
  - VALIDADO: 19/19 backend tests (iteration_112)

### Logica Condicional VPOS Stand Alone (2026-03-23)
- Campo "Modelo de POS" oculto para Fast Track (solo visible MPOS regular)
- Seccion "Equipos a Despachar" condicional: solo visible si Patrocinador = "Mega Soft"
- Cambiar patrocinador de Mega Soft a otro limpia ftEquipmentItems automaticamente
- PDF dinamico: Pagina 5 equipos solo se genera si patrocinador es Mega Soft
- Bug fix: Nota de Entrega para Fast Track usa ft_equipment_items cuando no hay warehouse
- Bug fix (testing agent): ft_equipment_items ahora se almacena en DB (modelo y creacion)
- VALIDADO: 8/8 backend + frontend verificado (iteration_127)

### PDF Corporativo v2 — Reestructuracion y Rediseno (2026-03-23)
- **Nueva estructura PDF para clientes Corporativos (client_segment='CORP')**:
  - Pag 1: Portada (mantener)
  - Pag 2: Resumen Ejecutivo / Alcance (mantener)
  - Pag 3: NUEVA pagina con desglose financiero agrupado (fusiona antiguas pags 3+4)
  - Pag 4+: Condicional equipos Fast Track (si aplica)
  - Anexo: "Anexo Cotizacion Corporativa" (reemplaza paginas 6-9 estandar de terminos)
- **Tabla "Costos de Implementacion"** en Pagina 3:
  - Columnas: Concepto | Hardware y Software (Derecho de Uso) | Consultoria (Apoyo tecnico / Soporte y Monitoreo) | Total
  - Filas: Set-up, * Recurrentes, Total
  - Agrupacion automatica por campo `tipo_corp` de medios_de_pago
  - Notas: "Montos no incluyen IVA", resaltado amarillo del total, nota sobre recurrentes
- **Backend**: Nuevo metodo generate_vpos_corp() en pdf_generator.py, append_corporate_static_pages() en config.py
- **Frontend**: campo tipo_corp incluido en pdfData, client_segment pasado a TemplateQuotePDFRequest
- **Modelo**: QuotePDFItem ahora acepta campo opcional tipo_corp (retrocompatible)
- **Archivo**: anexo_corporativa.pdf almacenado en /app/backend/static_pdfs/
- VALIDADO: 10/11 tests (1 skip transiente), regression PYME y Gateway OK (iteration_128)

### PDF Hibrido Fast Track (2026-03-23)
- Pagina adicional "COTIZACION DE EQUIPOS" insertada entre Resumen de Inversion y Terminos
- Tabla profesional: Descripcion, Tipo, Cantidad, P. Unitario, Total + Subtotal/IVA/Total
- Frontend: Seccion "Equipos a Despachar" en wizard Fast Track con selector de hardware del catalogo
- ft_equipment_items enviados en pdf_data y guardados en la cotizacion
- Fix: COLOR_AZUL_OSCURO constante faltante en pdf_generator (aplicado por testing agent)
- VALIDADO: PDF 10 paginas con contenido de equipos en pagina 5

### Flujo POS Stand Alone Fast Track (2026-03-23)
- **Nueva categoria `fast_track`** con quote_type `FAST_TRACK`
- Pipeline: Borrador → Enviada → Aprobada → Configurada → Facturada → Pagada → Entregada
- Aprobacion notifica a Operaciones (no Admin) con plantilla "Configuracion de Equipos (Pyme)"
- Nuevo endpoint `POST /api/quotes/{id}/configure`: cambia a "Configurada" y notifica Admin
- Hereda comportamiento MPOS: outsourcing, sin VPN
- Defaults editables: Integrador="Sin integrador", Patrocinador="Mega Soft"
- Frontend: badge violeta "Fast Track", boton "Marcar como Configurada" con icono Settings
- Facturacion acepta "Configurada" como estado previo valido para fast_track
- Entrega habilitada para fast_track
- VALIDADO: 14/14 backend + 100% frontend (iteration_126)

### Pantalla de Control de Equipos en Custodia - Taller (2026-03-22)
- **Nueva pagina `/taller-equipos`**: Vista de solo lectura para trazabilidad de equipos de terceros en taller
  - Tabla: Serial, Modelo, Cliente, Cotizacion Origen (enlace), Estatus (badge), Fecha Ingreso, Dias en Taller
  - Stats cards: Total, En Reparacion, Entregados, Alerta (+15 dias)
  - Filtros rapidos: busqueda por serial/cliente/modelo, selector estatus, rango de fechas
  - Alerta visual roja para equipos >15 dias en reparacion
  - Exportacion a Excel (.xlsx) con formato profesional
  - Modal de historial al clic en serial (detalle equipo, cotizacion origen, recibido por, timeline de estados)
  - Paginacion (25 items/pagina)
- **Backend**: dias_en_taller y alerta_retraso calculados en servidor, endpoint historial, export Excel con openpyxl
- **Menu lateral**: Nueva opcion "Equipos en Reparacion" con icono Wrench bajo Inventarios
- VALIDADO: 6/6 endpoints backend + frontend screenshot OK

### Modulo de Trazabilidad de Activos en Reparacion y Despacho (2026-03-22)
- **Coleccion `taller_equipos`**: Nueva entidad de persistencia para equipos en custodia del taller
  - Campos: serial, modelo, modelo_id, client_id, client_name, quote_id, quote_number, estatus, fecha_ingreso, fecha_entrega
- **Trigger en Aprobacion**: Al aprobar cotizacion de reparacion, se insertan automaticamente todos los seriales en taller_equipos con estatus "En reparacion"
- **Endpoint GET /api/quotes/{id}/repair-delivery-prep**: Obtiene equipos en reparacion del cliente agrupados por modelo
- **Endpoint POST /api/quotes/{id}/repair-deliver**: Procesa entrega de equipos reparados, genera Nota de Entrega PDF, actualiza estatus a "Entregado"
- **Endpoint GET /api/taller-equipos**: Consulta general de equipos en taller con filtros por client_id y estatus
- **Componente RepairDeliveryDialog**: Interfaz de seleccion de equipos con checkboxes por modelo, metodo de envio, datos de receptor
- **Flujo completo**: Aprobar → seriales ingresan a taller → Reparada → Facturada → Pagada → Entregada (seleccion + PDF + update masivo)
- VALIDADO: 12/12 backend + 100% frontend (iteration_125)

### Modulo de Cotizaciones — Flujo de Reparaciones (2026-03-22)
- **Reingenieria del Flujo de Estados para Reparaciones**:
  - Nuevo estado "Reparada" entre "Aprobada" y "Facturada" exclusivo para cotizaciones de reparacion
  - Pipeline reparaciones: Borrador -> Enviada -> Aprobada -> Reparada -> Facturada -> Pagada -> Entregada
  - Aprobacion de reparaciones: NO envia notificacion a Administracion (aprobacion silenciosa)
  - Nuevo endpoint POST /api/quotes/{quote_id}/repair-complete: cambia a "Reparada" y envia notificacion a Admin
  - Facturacion de reparaciones acepta "Reparada" como estado previo valido (sin requerir excepcion)
  - Entrega habilitada para cotizaciones de reparacion (ademas de equipos)
  - Frontend: badge cyan para estado "Reparada", boton "Marcar como Reparada" en menu contextual
  - VALIDADO: 13/13 backend + 100% frontend (iteration_124)

### Sistema RBAC Centralizado (2026-03-24)
- **Middleware HTTP en server.py**: Intercepta todas las peticiones y valida permisos por módulo
- **Lógica**: none→403 en todo, read→solo GET, edit→acceso completo, admin→bypass total
- **ROUTE_MODULE_MAP**: Mapeo de prefijos API a módulos de permisos (12 módulos)
- **Frontend**: Hook `usePermission`, `ProtectedRoute` bloquea páginas, `Sidebar` oculta menús sin acceso
- **Admin**: Panel de permisos por usuario en `/admin/users`
- **Bug fix**: Colección `db.sessions` corregida a `db.user_sessions` en middleware (causa raíz del fallo)
- **Enforcing Read-Only en Frontend (2026-03-24)**:
  - Todos los módulos auditados: Clientes, Bancos, Hardware, MediosPago, Integradores, Cotizaciones, Proyectos, NuevosProductos, Inventarios, Configuración
  - Botones crear/editar/eliminar/importar ocultos para permiso "read" vía `canEdit` de `usePermission`
  - Campos de entrada (ej: min_stock en inventarios) deshabilitados para "read"
  - QuotesTable recibe `canEdit` como prop para ocultar acciones del pipeline
  - Matriz de permisos (AdminUsers): sticky headers/columns, zebra striping, hover de fila
- VALIDADO: 24/24 backend + 100% frontend (iteration_129)

### Evolución ABAC — Permisos Avanzados (2026-03-25)
**Pilar 1: Permisos Especiales (Overrides)**
- Campo `special_permissions` (array) en modelo de usuario: ej. `["integradores:create"]`
- Middleware RBAC verifica overrides antes de bloquear: user con `read + integradores:create` → puede POST
- Admin UI: Checkbox por override en Gestión de Usuarios

**Pilar 2: Visibilidad Jerárquica de Cotizaciones**
- Ejecutivo → solo sus propias cotizaciones
- Coordinador → sus cotizaciones + Ejecutivos del mismo departamento
- Gerente → todas las cotizaciones de su departamento
- Director/Admin → todas las cotizaciones sin filtro
- Filtro basado en campo `cargo` y `departamento` del usuario

**Pilar 3: Jurisdicción de Inventario**
- Campo `almacen_asignado` (warehouse_id) en perfil de usuario
- Backend: `validate_warehouse_jurisdiction()` en todos los endpoints de escritura (entry/exit/transfer/min-stock)
- Frontend: `canEditWarehouse` = canEdit AND (no almacén asignado OR almacén coincide)
- Badge "Solo lectura (no asignado)" cuando el usuario tiene edit pero está en almacén ajeno
- Admin UI: Dropdown de almacén asignado por usuario

**Mejora adicional**: Degradación elegante en Cotizaciones — `.catch(() => [])` en Promise.all para módulos secundarios con 403
- VALIDADO: 19/19 backend + 100% frontend (iteration_130)

### Detalle de Sucursales para Cotizaciones (2026-03-25)
- **Panel BranchDetailPanel**: Componente opcional para cotizaciones VPOS/MPOS/Fast Track
  - Entrada manual de sucursales (nombre + cantidad)
  - Importacion masiva via Excel (columnas: Nombre Tienda | Cantidad)
  - Validacion de cantidades: total sucursales debe coincidir con total equipos cotizados
  - Indicadores visuales de estado de validacion (verde/rojo)
- **PDF**: Nueva pagina "Relacion de Tiendas" generada automaticamente cuando existen branch_details
- **Data Bridge**: branch_details de cotizacion se heredan como stores de proyecto multitienda al enviar a implementacion
- **Bug fix critico**: Campo branch_details faltaba en modelo QuoteCreateWithPDF (corregido)
- **Bug fix PDF (2026-03-25)**: Corregidos 3 errores que causaban caida total de generacion PDF:
  1. Imports faltantes de reportlab en quotes.py (SimpleDocTemplate, Table, etc.)
  2. HexColor sin prefijo colors. en tabla de sucursales de pdf_generator.py
  3. branch_details no incluido en exportCurrentQuoteToPDF del frontend
- **Fix Data Source (2026-03-25)**: Cambiada fuente de verdad de totalEquipment en BranchDetailPanel de Resumen Ejecutivo a Parametros de Cotizacion (cantidad_cajas)
- VALIDADO: 10/10 backend tests (iteration_131) + 3/3 escenarios PDF manuales

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
- Refactorizacion Inventory.jsx, Integrators.jsx y Clients.jsx
- Campos adicionales Fase 2 Integradores
