# PRD — Gestor MegaNexus

## Descripción General
Plataforma interna de gestión operativa para MegaNexus Venezuela. Módulos de Clientes, Cotizaciones, Facturación, Proyectos de Implementación, Inventario, Integradores, Bancos, Pipeline de Nuevos Productos, y administración de usuarios/roles.

## Arquitectura
- **Frontend**: React + Shadcn/UI + TailwindCSS
- **Backend**: FastAPI + MongoDB
- **Integraciones**: OpenAI (Emergent LLM Key), Gmail SMTP, Exchangedyn API (BCV), Emergent Object Storage

## Módulos Implementados

### Proyectos (Implementación)
- Matriz de implementación por banco/producto
- **Vinculación Logística en "Enviar a Implementación"**:
  - Modal con selector de Tipo de Proyecto: POS Fast Track / VPOS-MPOS / Payment Gateway
  - POS Fast Track: carga automática de seriales desde cotización (taller_equipos)
  - VPOS/MPOS: busca equipos entregados al cliente por RIF (auto + selección manual)
  - Payment Gateway: omite sección de equipos (flujo digital)
  - Equipos seleccionados se persisten en `project.equipments[]`
  - Tipo de Proyecto visible en ficha del proyecto (`project_type_impl`)
  - Sección "Modelo y Seriales de Equipos" en ProjectDetail
  - Variable `{Modelo_Seriales_Equipos}` para plantillas de email (tabla HTML Modelo-Serial)
- **Flujo Transaccional Seguro (Fix P0 — Feb 2026)**:
  - Orden: PDF → Proyecto → Email (sin emails fantasma)
  - `_create_project_from_quote` restaurada con cuerpo completo
  - Búsqueda de equipos diferenciada: Fast Track por quote_id, VPOS/MPOS por RIF+estatus
  - Si falla PDF o proyecto, se retorna error 500 sin enviar email
- **Flujo Extendido PYME (Feb 2026)**:
  - Activado cuando `client_segment` es PYME o el `quote_number` contiene '-PYME'
  - **Servidor de Instalación**: Dropdown (Multicomercio MSC / MSC2 / Otro + texto libre). Guardado en `project.server_name`
  - **Protocolo Pinpads**: Pregunta cerrada Sí/No.
    - No: conversión directa sin equipos
    - Sí: Dropdown de modelos (hardware con type POS/Pinpad y asset_type='Bien') → Búsqueda en Salidas de Inventario (últimos 15 días, por RIF cliente + modelo) → Selección de seriales
  - Datos guardados en `project.pinpad_serials[]`
  - **PDF actualizado**: Secciones "Servidor de Instalación" y "Modelo y Seriales de POS/Pinpad"
  - **ProjectDetail actualizado**: Widgets de servidor y pinpads vinculados
  - **Variables de email**: `{Modelo_Seriales_POS}`, `{Servidor_Instalacion}`
  - **Endpoints nuevos**: `GET /api/quotes/{id}/pinpad-models`, `GET /api/quotes/{id}/inventory-serials?model_id=X`
- **Motor de Reemplazo de Variables ROBUSTO**:
  - 19 variables dinámicas (incluye nuevas: Modelo_Seriales_POS, Servidor_Instalacion)
  - `_clean_html_in_braces` limpia tags HTML inyectados por el editor rico
- **Editor de Envío Final**: Editable con soporte de imágenes (Object Storage)
- **VTIDs por Sucursal**: Generación independiente por sucursal
- **Notificaciones Secuenciales** con prefijos dinámicos y CC
- **Asignación Simplificada** + Candado de Seguridad

### Cotizaciones
- RBAC con `special_permissions`
- Flujo de excepción para pasos saltados

### Facturación
- Tasas de Cambio BCV automatizadas

### Pipeline Nuevos Productos
- Governance: "Responsable Activo" write-locks

## Archivos Clave
- `/app/backend/routes/projects.py`
- `/app/backend/routes/quote_actions.py`
- `/app/backend/services/project_template_vars.py`
- `/app/backend/services/object_storage.py`
- `/app/backend/services/implementation_pdf.py`
- `/app/frontend/src/pages/ProjectDetail.jsx`
- `/app/frontend/src/pages/Quotes.jsx`

## Historial Reciente
- **Abr 2026**: Notificación "Enviar a Implementación" para Cotizaciones de Implementación:
  - Verificado y corregido flujo de notificación al ejecutar "Enviar a Implementación"
  - Plantilla: `implementation_PYME` (Envío a Implementación Sede Pyme)
  - Destinatario: `implementation_email` global de `app_settings` (Correo de Implementación General)
  - PDF de Ficha Técnica adjunto automáticamente ✅
  - Normalización de sede en template_vars: TBP → PYME (cosmético en asunto/cuerpo del email)
  - Variable `{Nombre_Sucursal}` agregada al motor de notificaciones
  - Formulario de recolección de datos técnicos intacto (sin cambios en frontend)
- **Abr 2026**: Botón "Configuración" siempre visible en Fast Track:
  - Botón "Configuración" siempre visible en el menú de acciones para cotizaciones Fast Track
  - Orden fijo: Aprobación → Configuración → Factura / Proforma
  - Comportamiento dual: si status="Aprobada" → Marcar como Configurada; otro status → Abrir wizard de edición
  - Propósito: acceso permanente a Detalles de Integración y Hardware en cualquier etapa del ciclo
- **Abr 2026**: Plantilla "Aprobación de Cotización Fast Track (Pyme)":
  - Nueva plantilla `fast_track_approved_PYME` en BD (template_id)
  - Layout maestro 900px con header #003366, secciones de Datos de Cotización y Detalles de Hardware
  - Variables: {Cotizacion_Nro}, {Nombre_Cliente}, {Rif_Cliente}, {Monto_Total}, {Modelo_Equipo}, {Cantidad}
  - Registrada en EmailTemplatesEditor con ícono violeta y variables editables
- **Abr 2026**: Matriz de Notificaciones exclusiva POS Stand Alone (Fast Track):
  - 5 acciones reconfiguradas en `quote_actions.py`:
    - Aprobación → Admin + Operaciones + plantilla `fast_track_approved_PYME`
    - Factura → Ventas PYME + plantilla `equipment_invoice_PYME`
    - Configurada → Almacén PYME + mensaje "Equipos configurados por Operaciones"
    - Cobranza → Almacén PYME + plantilla `equipment_delivery_PYME` (Orden de Entrega)
    - Marcada para Entregar → Ventas PYME + mensaje "Equipos listos" + Nota de Entrega PDF
  - Enviar Cotización y Enviar a Implementación ya funcionaban correctamente (sin cambios)
- **Abr 2026**: Optimización de Inventario (Fecha de Adquisición + Costo Ponderado + FIFO):
  - Campo "Fecha de Adquisición" (DatePicker, obligatorio) en formulario de entrada
  - Renombrado "Costo Prom." → "Costo Ponderado" en tabla de stock
  - Cálculo de Costo Promedio Ponderado: CP = (V_exist × CP_prev + V_entry × C_entry) / V_total
  - Lógica FIFO para salidas: seriales ordenados por fecha de adquisición más antigua
  - Archivos modificados: `inventory.py`, `models.py`, `Inventory.jsx`
- **Abr 2026**: Prerregistro de Seriales (Fast Track):
  - Nueva acción "Prerregistro de Seriales" en menú Fast Track (posición: después de Configuración)
  - Modal con buscador de seriales filtrado por modelo de equipo y almacén
  - Validación: cantidad exacta de seriales = demanda de la cotización
  - Estado "preasignado" en colección `serial_assignments` (bloquea serial para otras cotizaciones)
  - Al "Marcar como Entregada": transición preasignado → asignado + movimiento de salida en inventario
  - Notificación automática a Operaciones sede PYME con plantilla `serial_preassignment_PYME`
  - Archivos: `quote_actions.py`, `inventory.py`, `PreassignSerialsModal.jsx`, `QuotesTable.jsx`, `Quotes.jsx`
- **Abr 2026**: Workflow Exclusivo de Notificaciones para Equipos PYME:
  - 4 acciones cableadas con plantillas y buzones correctos:
    1. Enviar Cotización → Todos los emails del cliente → `equipment_sent_PYME`
    2. Aprobación → Admin sede PYME → `equipment_approved_PYME`
    3. Factura/Proforma → Ventas sede PYME → `equipment_invoice_PYME`
    4. Cobranza → Almacén sede PYME → `equipment_collect_PYME`
  - Variables resueltas: {Nombre_Cliente}, {Cotizacion_Nro}, {Monto_Total}, {Referencia_Factura}
  - Flujo aislado de implementaciones (solo aplica cuando quote_category='equipment')
- **Abr 2026**: Columna "C.U. Bs." en PDF de Facturación:
  - Agregada columna "C.U. Bs." (Costo Unitario = Total Bs. / Cantidad) en `billing_pdf.py`
  - Aplica a ambos PDFs: Implementación (encabezado "Concepto") y Equipos (encabezado "Equipo / Accesorio")
  - 6 columnas: Concepto, Cant., Monto($), Tasa, C.U. Bs., Total(Bs.)
  - Título de sección dinámico: "Equipos y Accesorios Cotizados" vs "Conceptos de Setup y Productos Consolidados"
- **Abr 2026**: Columna "Costo Unitario Bs." en Modal de Aprobación:
  - Nueva columna "C.U. Bs." (Total Bs. / Cantidad) en tabla de facturación
  - Aplica a ambos flujos: Implementación y Equipos/Accesorios
  - Encabezado de tabla con fondo oscuro y texto blanco
  - Modal expandido a max-w-4xl para acomodar 6 columnas
- **Abr 2026**: Fix Modal Aprobación Cotización de Equipos:
  - Corregido cruce de contexto: modal ahora lee `equipment_items` en vez de `services` para categoría "equipment"
  - Título dinámico: "Aprobación de Cotización de Equipos y Accesorios" vs "Aprobación de Cotización"
  - Tabla: encabezado "Equipo / Accesorio", subtotal "Equipos y Accesorios"
  - Anexos: "Orden de Compra / Autorización" para equipos vs "Comprobante de Aprobación" para implementación
  - Cálculo correcto en Bs. basado en total hardware × tasa BCV
- **Abr 2026**: Corrección Sistema de Referidores — Lista Maestra + Cascada:
  - Mantenida la lista maestra original (Correo de Ventas, Integrador, Directores, Corporativo, etc.)
  - Agregadas nuevas opciones: Ventas Directas, Página Web, Redes Sociales, Alianzas Externas, Banco, Cliente Referidor
  - Campo unificado "Origen del Cliente" (14 opciones) con cascada condicional
  - Solo "Banco" y "Cliente Referidor" activan dropdowns secundarios
  - Plantilla de importación actualizada con columnas: Origen Tipo, Referidor Nombre, Referidor ID
- **Abr 2026**: Sistema Dinámico de Referidores en Ficha de Clientes (primera versión):
  - Nuevo selector de dos niveles: Tipo de Referidor (Banco/Cliente Existente/Otro) + campo dinámico
  - Banco → dropdown con 30 instituciones financieras de la BD `banks`
  - Cliente Existente → dropdown buscable de 315+ clientes registrados
  - Otro → campo de texto libre para fuentes no categorizadas
  - Nuevos campos BD: `referidor_tipo`, `referidor_id` (FK polimórfica), `referidor_nombre`
  - Endpoint `/api/clients/referidor-options` para alimentar dropdowns
  - Plantilla de importación actualizada con columnas `Referidor Tipo` y `Referidor Identificador`
  - Validación cruzada en importación: BANCO→verifica existencia en BD, CLIENTE→verifica RIF existente
- **Abr 2026**: Plantillas de Correo para Ventas de Equipos (10 templates):
  - 5 plantillas base × 2 segmentos (PYME/CORP) = 10 templates en `email_templates`
  - Plantillas: equipment_sent, equipment_approved, equipment_invoice, equipment_collect, equipment_delivery
  - Layout Maestro: 900px, header azul #003366, footer gris #edf2f7
  - Variables: {Nombre_Cliente}, {Cotizacion_Nro}, {Monto_Total}, {Referencia_Factura}, {Direccion_Entrega}, {items_table}
  - Backend: `template_base_override` en `send_workflow_notification` para selección automática por categoría
  - Frontend: `EQUIPMENT_TEMPLATE_TYPES` en EmailTemplatesEditor con iconos y colores diferenciados
- **Abr 2026**: Ajuste Workflow Cobranza PYME:
  - Acción `collect` dispara template `comprobante_pago_PYME` con variables `{Nombre_Cliente}`, `{Cotizacion_Nro}`
  - Correo dirigido a buzón Ventas Sede PYME (`emails_by_sede[PYME].sales`)
  - Normalización de sede: TBP → PYME (legacy)
  - Registro de audit trail en `status_history` de la cotización con detalle de destinatario
- **Abr 2026**: Centralización de gestión de plantillas de correo:
  - Eliminado botón "Plantillas de Correo" del módulo de Cotizaciones (Quotes.jsx)
  - Editor maestro en Configuración potenciado con sidebar de Variables Dinámicas categorizado (Cliente, Financiero, Ejecutivo, Implementación)
  - Tokens CSS mejorados: fondo `#EBF8FF`, texto `#2C5282`, sin sobreimpresión
- **Abr 2026**: Optimización Fast Track — Captura Unificada de Hardware:
  - Nuevo dropdown obligatorio "Modelo de POS / PINPAD" en Detalles de Integración para Fast Track
  - Combina dispositivos POS + Pinpads (11 items filtrados por clasificación "Bien")
  - Tabla read-only en "Equipos a Despachar" sincronizada desde Integración (Modelo, Tipo, Cant., Precio, Subtotal)
  - Hardware sumado al TOTAL GENERAL: Implementación (Servicios) + Equipos (Hardware)
  - Backend: `ft_equipment_items` y `ft_hardware_subtotal` almacenados en cotización y sumados al `total_usd`
- **Abr 2026**: Optimización Ingreso a Inventario:
  - Excluidos items de Mantenimiento del dropdown de Entrada de Inventario
  - Seriales obligatorios solo para POS/Pinpad con clasificación "Bien" (activos físicos rastreables)
  - Items tipo Servicio muestran solo Cantidad y Costo (sin seriales ni Precarga)
  - Regla aplicada a Entrada, Salida y Transferencia

## Backlog

### P1 (Próximos)
- Verificación de Email y Recuperación de Contraseña
- Refactorización de `Quotes.jsx` (5800+ líneas)

### P2 (Futuro)
- Módulo de Reportes de Ventas
- Lógica "Completado" en Roadmap Bancos
- Refactorización componentes monolíticos (`ProjectDetail.jsx` 1800+)
