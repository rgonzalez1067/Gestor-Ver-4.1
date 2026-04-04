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
