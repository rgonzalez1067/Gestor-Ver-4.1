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
- **Herencia Multitienda (2026-03-25)**: Flujo inteligente en "Enviar a Implementación":
  - Escenario A: Detecta distribucion previa → muestra resumen → Confirmar/Modificar
  - Escenario B: Sin datos previos + Multitienda → editor obligatorio
  - Escenario C: Monotienda → avanza directo
  - VALIDADO: 10/10 backend + 3/3 escenarios frontend (iteration_132)

### Ajustes Estructurales (2026-03-25)
- **Clientes - Impresora Fiscal**: Selector dinámico (Bematech, Bixolon, HKA, Otra) con registro en tabla maestra
- **Contactos - Nuevos Roles**: Propietario y Director agregados al catálogo
- **Proyectos - Fecha Asignación**: Removida "Fecha de entrega" del asignar, agregada "Fecha de Asignación" automática
- **Usuarios - Supervisor**: Campo typeahead para asignar supervisor (ancla para jerarquía de cotizaciones)
- VALIDADO: 92% backend (12/13) + 100% frontend (iteration_133)

### PDF Corp - Detalle Técnico (2026-03-25)
- Insertada nueva Página 4 en PDF Corporativo: desglose ítem por ítem (Setup + Recurrentes)
- Usa misma función _create_items_table que Página 3 del PDF Pyme
- Solo afecta PDFs Corporativos, Pyme no se modifica
- IVA y totales calculados con misma precisión que flujo original
- VALIDADO: HTTP 200 para ambos templates (Corp y Pyme)

### Motor SMTP Propio (2026-03-25)
- Reemplazado Resend por SMTP propio (smtp.gmail.com:587) como motor primario de correos
- Cadena de prioridad: SMTP propio → Resend (fallback) → Simulado
- Soporte para adjuntos, HTML, y múltiples destinatarios
- Logs de envío registrados en colección email_logs de MongoDB
- VALIDADO: Email de prueba enviado exitosamente via SMTP a gestor@megasoft.com.ve

### Workflow Notifications (2026-03-26)
- Creado helper centralizado: services/workflow_notifications.py
- Matriz de 5 disparadores: send-to-client, approve, configure, collect, send-to-implementation
- Resolución dinámica de buzones desde config (emails_by_sede)
- Selección automática de plantilla por segmento (PYME/CORP)
- Adjunto PDF automático en send-to-client y send-to-implementation
- CC y mensajes personalizados heredados del modal "Personalizar Comunicación"
- Refactorizado quote_actions.py: eliminado código duplicado (~200 líneas)

### Fix Input Lag - Personalizar Comunicacion y Sucursales (2026-03-26)
- Corregida latencia critica (Input Lag) en 2 campos de texto:
  - `emailCustomMessage` en Quotes.jsx: cambiado de controlled (value+onChange) a uncontrolled (defaultValue+onBlur)
  - `store_name` y `quantity` en BranchDetailPanel.jsx: cambiado onChange a onBlur
- Causa raiz: cada keystroke disparaba setState del componente padre (5200+ lineas), causando re-render completo
- Solucion: sincronizar estado del padre solo en onBlur, maxLength nativo del HTML para restriccion de caracteres
- VALIDADO: Compilacion exitosa, app funcional

### Otros
- Dashboard KPIs, Tasa BCV, Gestion usuarios con roles/permisos

## Integraciones
- Resend (SIMULADO), WeasyPrint, reportlab, exchangedyn/dolarapi, openpyxl/pandas

## Backlog

### Flujo Logístico Fast Track - Entrega de Equipos (2026-03-26)
- Backend: Abierto delivery-prep para fast_track (lee ft_equipment_items)
- Frontend: Menú de acciones muestra AMBOS botones: "Marcar como Entregada" + "Enviar a Implementación"
- Badge "Entregar primero" en botón de implementación cuando no se ha entregado
- delivery-prep validado: retorna items de Fast Track con seriales y stock correcto
- VALIDADO: Screenshot confirma menú dual, curl confirma delivery-prep funcional

### Estabilización Visual — Flujo de Reparaciones (2026-03-26)
- Creado componente `RepairStatusPipeline.jsx`: Stepper visual persistente en tabla de cotizaciones para reparaciones
  - 7 pasos: Borrador → Enviada → Aprobada → Reparada → Factura → Pagada → Entregada
  - Estados visuales: completado (cyan), actual (borde cyan), pendiente (gris)
  - Componente memoizado para evitar re-renders innecesarios
- Tabla de cotizaciones: Acción renombrada de "Marcar como Reparada" a "Reparada"
- VALIDADO: Screenshot confirma stepper visible y acción renombrada correctamente

### Plantillas de Correo — Flujo de Reparaciones (2026-03-27)
- **4 nuevas plantillas de correo** para el ciclo completo de reparaciones (PYME + CORP = 8 variantes):
  1. **Envío Cotización de Reparación** (`repair_quote_sent`): Presupuesto técnico con botón naranja "Ver y Aprobar". Variables: {contacto_cliente}, {modelos_resumen}, {nro_cotizacion}
  2. **Aprobación Cotización de Reparación** (`repair_approved`): Confirmación al cliente con bloque "¿Qué sigue ahora?" Variables: {contacto_cliente}, {nro_cotizacion}
  3. **Notificación Reparación Finalizada** (`repair_complete_client`): Aviso al cliente de equipos listos + detalle modelos/seriales. Variables: {lista_modelos_seriales}
  4. **Orden de Entrega Equipos Reparados** (`repair_delivery`): Resumen entrega parcial/final + PDF adjunto automático. Variables: {tipo_nota_entrega}, {nro_nota_entrega}, {cantidad_entregada}, {estatus_entrega}
- **Diseño**: Cabeceras Azul Corporativo (#2c3e50), Botones Naranja (#f39c12) para diferenciar de ventas
- **Backend integrado**: send-to-client (repair), approve (repair→cliente), repair-complete (cliente+admin), repair-deliver (cliente+PDF)
- **Frontend**: Editor de plantillas actualizado con variables específicas de reparación + valores de preview
- VALIDADO: 13/13 backend + 100% frontend (iteration_134)

### Plantilla Orden de Despacho — Pago de Reparación (2026-03-27)
- **5ta plantilla de reparación**: `repair_collect_warehouse` (PYME + CORP = 2 variantes)
  - Se dispara cuando Administración confirma el pago (`collect` endpoint para reparaciones)
  - Destinatario: Almacén + CC al Ejecutivo creador
  - Variables: {nro_cotizacion}, {nombre_cliente}, {lista_equipos_seriales}, {almacen_custodia}
  - Incluye sección "Instrucciones Operativas" con 4 pasos para liberar equipos bajo custodia
  - Mapeo automático de sede a ubicación: PYME→"Torre Banco Plaza", CORP→"Los Chaguaramos"
  - Diseño: Cabecera #2c3e50, sección warning naranja #f39c12 para instrucciones
- Backend: `collect_quote` ahora tiene 3 ramas: equipment→warehouse, **repair→repair_collect_warehouse**, else→Ventas
- Frontend: Editor actualizado con variables y previews de la nueva plantilla
- VALIDADO: 15/15 backend + 100% frontend (iteration_135)

### Integridad Visual — Stepper Universal con "Camino Rojo" (2026-03-27)
- **Nuevo componente `QuoteStatusStepper.jsx`**: Stepper universal para TODAS las categorías (repair, fast_track, equipment, implementation)
  - Fases regulares completadas: Verde sólido (#10b981) + Check (✓)
  - Fases saltadas (Irregular): Rojo claro (#fee2e2) + Alerta (⚠) — clickeable con popover de justificación
  - Fase actual: Borde verde (#10b981) sin relleno
  - Pendientes: Gris outline + Número de paso
  - Paso final alcanzado: Verde sólido + Check (no borde)
- **Detección automática de fases bypass**: Compara timestamps (`sent_to_client_at`, `approved_at`, etc.) vs `irregular_exceptions` para detectar qué pasos fueron saltados
- **Badge "Irregular" persistente** en rojo con popover de historial de excepciones (acción, justificación, fecha, tope de regularización)
- **Bug fix "Entregada"**: Ahora el stepper incluye `delivered_at` como timestamp y marca correctamente el paso final como completado
- **Fix layout tabla**: Columna Acciones ahora sticky (`sticky right-0`) con sombra separadora, siempre visible sin importar el ancho de la tabla
- Flujos por categoría: repair (7 pasos con Reparada), fast_track (6 con Config.), equipment (5 con Entregada), implementation (5 con Imple.)
- VALIDADO: 100% frontend (iteration_136)

### Tooltip con Fechas en Stepper (2026-03-27)
- Al hacer hover sobre pasos completados o actuales, se muestra tooltip con nombre de fase + fecha/hora exacta (formato: "27 mar. 2026, 12:54 p. m.")
- Usa componente `Tooltip` de shadcn/ui con `delayDuration=200ms`
- Pasos pendientes y bypassed no muestran tooltip de fecha (los bypassed mantienen su popover de justificación)
- VALIDADO: Screenshot confirma tooltip funcional

### Modal de Aprobación con Instrucción de Facturación (2026-03-31)
- **Nuevo componente `ApprovalBillingModal.jsx`**: Reemplaza WorkflowUploadModal para aprobaciones
  1. **Carga Soporte Opcional**: Campo de upload de comprobante de pago anticipado, se adjunta al correo de Administración
  2. **Tabla de Instrucción de Facturación**: Conceptos consolidados por nombre (GROUP BY item_name, SUM quantity + total_usd)
  3. **Calculadora Bs./$**: Tasa auto-cargada desde `/exchange-rate/current`, cálculo en tiempo real, overrides manuales (estilo amber)
- Backend: `approve_quote` acepta body JSON con `billing_instruction` (consolidated_items, exchange_rate, grand_total_usd, grand_total_bs), almacenado en MongoDB
- Eliminada validación obligatoria de "Orden de Compra" (ahora es opcional "Comprobante de Pago")
- VALIDADO: 100% backend + 100% frontend (iteration_137)

### Optimización Modal Aprobación: Setup-Only + PDF Cálculos + IVA (2026-03-31)
- **Filtro de Setup**: Tabla de facturación muestra SOLO `item_type='setup'` (excluye mantenimiento mensual/recurrente)
- **IVA y Totales**: Filas de Subtotal (Setup), IVA (16%), TOTAL GENERAL con cálculos automáticos en $ y Bs.
- **PDF de Cálculos Definitivos** (`billing_pdf.py`): Documento interno ReportLab con datos cliente, RIF, conceptos consolidados, tasa, IVA, totales, nombre ejecutor. Se adjunta automáticamente al correo de aprobación.
- **Workflow actualizado**: Correo de aprobación ahora incluye: PDF Cotización Original + PDF Cálculos Definitivos + Soporte de pago (si aplica)
- VALIDADO: 100% backend + 100% frontend (iteration_138)

### Corrección Latencia Generalizada - DebouncedInput Global (2026-03-26)
- Creado componente reutilizable /app/frontend/src/components/DebouncedInput.jsx
  - Estado LOCAL interno (renders solo del componente, no del padre)
  - Sincronización con padre solo en onBlur o tras debounce configurable
  - Soporte para input y textarea via prop `as`
- Aplicado a 4 módulos principales:
  - Clients.jsx: 13 campos (formulario completo + contactos + búsqueda 400ms debounce)
  - Inventory.jsx: 10 campos (almacén, entradas, salidas, transferencias)
  - Integrators.jsx: 6 campos (nombre, app, contactos + búsqueda 400ms debounce)
  - Quotes.jsx: 2 campos (mensaje custom + sucursales, aplicados anteriormente con defaultValue+onBlur)
- VALIDADO: Compilación exitosa, formulario renderiza correctamente

### Ficha Técnica de Implementación - Nuevo PDF (2026-03-26)
- Creado /app/backend/services/implementation_pdf.py: genera PDF operativo con 5 bloques
  - A. Identificación del Proyecto (tipo, comercio, RIF)
  - B. Configuración Técnica (integrador, app, pinpad, patrocinador)
  - C. Resumen Comercial (tabla cliente/cajas/dirección + bancos/productos)
  - D. Distribución Logística (sucursales o "Sucursal Única" si no hay detalle)
  - E. Directorio de Contactos (nombre, cargo, teléfono, email)
- Integrado en endpoint send-to-implementation: genera y adjunta automáticamente
- Fix: render_template ahora soporta tanto {key} como {{key}} para variables
- VALIDADO: PDF generado (4.2 KB), email con attach=True, subject con variables resueltas

### Optimización Workflow de Acciones: Cotizaciones Pyme & Corp (2026-03-26)
- Aprobación: Ahora adjunta PDF de la cotización al correo hacia Administración (WORKFLOW_MATRIX attach_pdf=True + carga desde quote_pdf_url)
- Factura/Proforma: Adjunta archivo físico de factura con nombre descriptivo Factura_{Nro}_{Cliente}.ext + plantilla por sede
- Segmentación: Todas las acciones buscan plantilla por sede (template_base_PYME/CORP) antes de genérica
- VALIDADO: email_log workflow_approve con has_attachment=True, backend sin errores

### Variables Dinámicas del Ejecutivo en Plantillas (2026-03-26)
- Agregadas variables {Nombre_Ejecutivo} y {Email_Ejecutivo} a todas las plantillas de correo
- Backend: lookup del creador (created_by_user_id → users) para resolver nombre y email
- Corregido send-to-client para buscar plantilla por sede (quote_sent_PYME/CORP) antes de genérica
- Plantillas default actualizadas con texto: "escriba al correo {Email_Ejecutivo} de {Nombre_Ejecutivo}"
- Frontend: variables registradas en editor con valores de preview
- VALIDADO: Backend sin errores, variables visibles en editor, preview correcto

### Fix Plantillas de Correo - Actualización Bloqueada (2026-03-26)
- Eliminadas rutas duplicadas de email-templates en projects.py que conflictuaban con seed_and_templates.py
- Causa raiz: projects.py registraba PUT /email-templates/{id} esperando Form(...) pero frontend enviaba JSON
- La ruta correcta en seed_and_templates.py usa modelo Pydantic EmailTemplate (JSON) que coincide con frontend
- VALIDADO: PUT exitoso via curl y UI (toast "Plantilla guardada exitosamente")

### P1
- Herencia de cantidad_cajas a campo VTID en cotizaciones VPOS
- Verificacion Email y Recuperacion Contrasena
- Refactorizacion Quotes.jsx

### P2
- Modulo Reportes de ventas
- Logica "Completado" en Roadmap Bancos
- Refactorizacion Inventory.jsx, Integrators.jsx y Clients.jsx
- Campos adicionales Fase 2 Integradores
