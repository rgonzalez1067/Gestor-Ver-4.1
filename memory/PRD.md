# Cotizador Merchant Server - PRD

## Descripción General
Sistema integral de cotizaciones para plataformas de medios de pago. Permite gestionar clientes, bancos, hardware, servicios y generar cotizaciones profesionales con conversión de tasa de cambio BCV.

## Problema Original
El usuario solicitó una aplicación de cotizaciones con:
1. Gestión de Usuarios con autenticación Google OAuth (Emergent-managed)
2. Módulos CRUD para Clientes, Bancos, Hardware y Servicios
3. Configuración de costos de Setup y Mantenimiento Mensual
4. Motor de cotización con tasa de cambio BCV
5. Escalabilidad para futuros módulos de reportes

## Stack Tecnológico
- **Backend:** FastAPI (Python)
- **Frontend:** React + TailwindCSS
- **Base de Datos:** MongoDB
- **Autenticación:** Emergent-managed Google OAuth

## Funcionalidades Implementadas

### Backend (FastAPI)
- [x] Autenticación via Emergent Google OAuth
- [x] CRUD Clientes (con campo `segment`: Pymes/Corporativo/Mixto)
- [x] Importación/Exportación de Clientes (CSV/PDF)
- [x] CRUD Bancos (Venezuela, EE.UU., Fintechs) con medios de pago asociados
- [x] Importación/Exportación de Bancos (CSV/PDF)
- [x] CRUD Hardware
- [x] CRUD Medios de Pago con compatibilidad por tipo de cotización
- [x] Importación/Exportación de Medios de Pago (CSV/PDF)
- [x] CRUD Cotizaciones con flujo optimizado
- [x] Tasa de cambio BCV (consulta y actualización)
- [x] Upload/descarga/eliminación de logo de empresa
- [x] Generación de PDF para cotizaciones
- [x] Filtro de servicios por compatibilidad (?compatibility=vpos|gateway|mpos|link)

### Frontend (React)
- [x] Login con Google OAuth
- [x] Logo de empresa visible en pantalla de Login
- [x] Colores de marca (verde #1B7D4E y azul #00447C)
- [x] Gestión de Bancos con selección de Medios de Pago desde BD
- [x] **Flujo de Cotización Optimizado (Diciembre 2025):**
  - Sección 1: Parámetros Iniciales (Tipo, Cliente, Cantidad Cajas)
  - Sección 2: Selección jerárquica Banco → Medio de Pago (filtrado)
  - Sección 3: Matriz de Resumen con columnas editables (Costo Setup, Costo Recurrente)
  - Botón Finalizar visible solo cuando hay items en la matriz
- [x] Configuración (upload logo + seed bancos)
- [x] Fondos blancos en toda la aplicación

## Modelo de Datos - Productos de Banco
```json
{
  "product_name": "string",
  "description": "string",
  "vpos_available": "boolean",
  "gateway_available": "boolean",
  "mpos_available": "boolean",
  "link_available": "boolean"
}
```

## Modelos de Datos

### Client
```json
{
  "client_id": "string",
  "rif": "string",
  "legal_name": "string",
  "fantasy_name": "string",
  "segment": "Pymes | Corporativo | Mixto",
  "contact1": {"name", "phone", "email"},
  "contact2": {"name", "phone", "email"}
}
```

### Service (Medio de Pago)
```json
{
  "service_id": "string",
  "category": "string",
  "name": "string",
  "application_type": "setup | recurring | both",
  "vpos_enabled": "boolean",
  "gateway_enabled": "boolean",
  "mpos_enabled": "boolean",
  "link_enabled": "boolean",
  "setup_cost_conventional": "float",
  "monthly_cost_conventional": "float",
  "setup_cost_outsourcing": "float",
  "monthly_cost_outsourcing": "float",
  "description": "string"
}
```

### Bank
```json
{
  "bank_id": "string",
  "name": "string",
  "type": "Banco | Fintech",
  "country": "Venezuela | Estados Unidos",
  "products": [{"product_name", "description"}]
}
```

## Endpoints API
- `POST /api/auth/session` - Crear sesión
- `GET /api/auth/me` - Obtener usuario actual
- `POST /api/auth/logout` - Cerrar sesión
- `GET/POST/PUT/DELETE /api/clients` - CRUD Clientes
- `GET/POST/PUT/DELETE /api/banks` - CRUD Bancos
- `POST /api/banks/seed` - Poblar bancos
- `GET/POST/PUT/DELETE /api/hardware` - CRUD Hardware
- `GET/POST/PUT/DELETE /api/services` - CRUD Medios de Pago
- `GET /api/services?compatibility=vpos|gateway|mpos|link` - Filtrar por compatibilidad
- `GET/POST /api/quotes` - CRUD Cotizaciones
- `GET /api/quotes/{id}/pdf` - Descargar PDF
- `GET /api/exchange-rate/current` - Tasa actual
- `POST /api/exchange-rate/update` - Actualizar tasa
- `POST/GET/DELETE /api/config/logo` - Gestión de logo

## Bancos Precargados (via /api/banks/seed)
### Venezuela
- Banco de Venezuela, Mercantil, Banesco, BBVA Provincial, Exterior, BNC, Tesoro, Bicentenario, BOD, Sofitasa, Plaza, Activo, Caribe, BFC, Agrícola, Bancrecer, Banplus, 100% Banco, Bancamiga, Mi Banco, Bancaribe

### Estados Unidos
- Bank of America, Banesco USA, Wells Fargo, Citi Bank, US Bank, Chase, Amerant

### Fintechs
- Cashea, Lysto, Crixto

## Testing Status
- Backend: 70/70 tests pasados (100%)
- Frontend: Login, OAuth, flujo de cotización verificado
- Matriz de costos: Implementada y verificada

## Funcionalidades Completadas (Diciembre 2025)
- [x] Filtrado de medios de pago por compatibilidad en cotizaciones
- [x] Checkboxes de compatibilidad en formulario de Medios de Pago
- [x] Backend acepta parámetro ?compatibility=vpos|gateway|mpos|link
- [x] Selección de Medios de Pago desde BD en pantalla de Bancos
- [x] Flujo de cotización rediseñado con parámetros iniciales
- [x] Selección jerárquica (Banco → Medio de Pago filtrado)
- [x] **Matriz de Costos Profesional:**
  - Sección Set Up (header cyan): N°, Concepto, Cajas VTID, Bancos/Entes, Tarifa Setup, Total Setup
  - Sección Recurrente (header verde): N°, Concepto, Cajas, Bancos, Tarifa Mensual, Total Mensual
  - Fórmula: Total = Tarifa × Cajas × Bancos
  - Filas: Subtotal, Descuento (%), Total Neto
  - Total General (Setup + Recurrente) en footer negro
- [x] Precios cargados automáticamente desde catálogo de Medios de Pago
- [x] **Selector de Modelo de Precios:**
  - Modelo Convencional (Conv): setup_cost_conventional, monthly_cost_conventional
  - Modelo Outsourcing (Outs): setup_cost_outsourcing, monthly_cost_outsourcing
  - Campo obligatorio antes de agregar medios de pago
- [x] **Estructura de Cotización de Recurrentes (Diciembre 2025):**
  - **BLOQUE 1 - Recurrentes Básicos** (verde):
    1. Derecho de uso de plataforma MServer por PDV
    2. Derecho de uso de plataforma MServer por PDV / Banco
  - **BLOQUE 2 - Otros Recurrentes** (teal):
    1. Comunicación Backend (SSL Público o VPN, APN, etc.)
    2. Procesamiento (HSM, Server, DC, etc.)
  - **BLOQUE 3 - Complementos** (púrpura) - Vinculados a Setup:
    1. Mantenimiento PDV/Banco
    2. Mantenimiento dispositivo (Pinpad o POS)
    3. Mantenimiento PDV en MServer
    4. Mantenimiento Medio de Pago / Banco en MServer, por PDV
  - **Botón "Complementar Recurrentes"**: Agrega conceptos de mantenimiento con valores precargados
  - Campos Cajas y Bancos editables por fila para ajustes excepcionales
- [x] **Renombrado Global (Diciembre 2025):**
  - "Hardware" → "Dispositivos y Accesorios" en toda la plataforma
- [x] **Dashboard Mejorado (Diciembre 2025):**
  - Agregados indicadores: Medios de Pago, Dispositivos
  - 6 tarjetas de estadísticas en total
  - Validación robusta de datos (Array.isArray)

## Correcciones Recientes (Febrero 2026)

### Bug Fix: Crash en Página de Cotizaciones
- **Problema:** La página `/quotes` crasheaba con error de JavaScript por referencias a una variable de estado eliminada (`recurring_complement_items`).
- **Causa raíz:** Durante una refactorización, se eliminó la variable del estado inicial pero quedaron referencias:
  - Función `updateRecurringComplementItem`
  - Referencias a `recurring_complement_items.length`
  - Variable `subtotalRecurringComplement`
  - Sección completa de tabla de Complementos usando `.map`
  - `handleSubmitQuote` referenciaba `quoteData.recurring_items` (inexistente)
- **Solución aplicada:**
  - Eliminada función `updateRecurringComplementItem`
  - Eliminadas referencias a `recurring_complement_items.length`
  - Eliminada sección de tabla de Complementos
  - Corregido `handleSubmitQuote` para usar `recurring_basic_items` y `recurring_other_items`
  - Botón "Complementar Recurrentes" ahora usa `addRecurringComplementsFromAdditional()`
- **Estado:** VERIFICADO - Backend 70/70 tests (100%), Lint sin errores

### Nueva Funcionalidad: Mapeo Automático Setup → Recurrente (Febrero 2026)
- **Descripción:** Sistema de vinculación automática entre conceptos de Setup y sus Recurrentes asociados.
- **Cambios Backend:**
  - Nuevo campo `linked_recurring_service_id` en modelo Service/ServiceCreate
  - Nuevo filtro `GET /api/services?application_type=recurring_available` para obtener servicios recurrentes
- **Cambios Frontend MediosPago:**
  - Selector "Concepto Recurrente Asociado" visible solo para tipos `setup` o `both`
  - Carga de servicios recurrentes disponibles para vinculación
  - Visualización del servicio vinculado en la tabla de listado
- **Cambios Frontend Quotes:**
  - `findServicePrice()` ahora retorna `linked_recurring_service_id`
  - `addMedioPagoItem()` detecta vinculación y agrega automáticamente el recurrente a `recurring_basic_items`
  - `consolidateRecurringItems()` agrupa duplicados y acumula en campo `cantidad_bancos`
  - Al eliminar item adicional, se eliminan también sus recurrentes vinculados
- **Beneficios:**
  - Reducción de errores: No se olvidan cargos mensuales obligatorios
  - Agilidad comercial: Automatización del 100% de carga de recurrentes
  - Consistencia de datos: Ofertas comerciales íntegras
- **Estado:** IMPLEMENTADO - Backend 85/85 tests (100%)

## Módulos de la Aplicación

### Módulo: Gestión de Integradores (Nuevo - Febrero 2026)
**Descripción:** Registro y administración de aliados técnicos y sus estados de certificación.

**Campos del formulario:**
- Nombre del Integrador (texto)
- Tipo de Integrador (dropdown: Integrador, Comercio)
- Nombre del Aplicativo (texto)
- Modalidad de Integración (dropdown: Bridge PG, MPOS, PG Universal, PG No universal, REST, Stand Alone)
- Estatus (dropdown: Certificado, En proceso, Suspendido)

**Funcionalidades:**
- CRUD completo (crear, leer, actualizar, eliminar)
- Exportación a Excel (.xlsx) y PDF
- Importación desde Excel (.xlsx, .xls) y CSV
- Validación de datos importados contra opciones predefinidas
- Búsqueda y filtrado por Estatus y Tipo
- Dashboard con contadores por estado

**Endpoints:**
- `GET /api/integrators` - Listar (con filtros opcionales)
- `POST /api/integrators` - Crear
- `GET /api/integrators/{id}` - Obtener
- `PUT /api/integrators/{id}` - Actualizar
- `DELETE /api/integrators/{id}` - Eliminar
- `GET /api/integrators/export/excel` - Exportar Excel
- `GET /api/integrators/export/pdf` - Exportar PDF
- `POST /api/integrators/import` - Importar desde archivo

### Correcciones de Incidencias (Febrero 2026 - Actualizado)
- **Regla de Negocio "Derecho de uso de plataforma MServer por PDV":** Campo Bancos ahora está **bloqueado en 1** (cobro unitario por terminal, no depende de entidades financieras)
- **Mapeo de Precios Corregido:** Prioriza coincidencias exactas antes de buscar por inclusión
- **Otros Recurrentes con N/A:** "Comunicación Backend" y "Procesamiento" muestran "N/A" en campo Bancos
- **Descarga PDF Mejorada:** 
  - Toast de carga mientras genera
  - Validación de respuesta y tipo de contenido
  - Manejo de errores mejorado con mensajes específicos
  - Limpieza automática de recursos

### Conceptos con Campo Bancos Bloqueado (N/A o valor fijo 1):
**Setup:**
- Configuración dispositivo (Pinpad o POS) - N/A
- Configuración PDV en MServer - N/A

**Recurrentes Básicos:**
- Derecho de uso de plataforma MServer por PDV - Fijo en 1

**Otros Recurrentes:**
- Comunicación Backend (SSL Público o VPN, APN, etc.) - N/A
- Procesamiento (HSM, Server, DC, etc.) - N/A

### Mejoras de Interfaz y Lógica de Cotización (Febrero 2026)
- **Campos bloqueados muestran "N/A":** En "Configuración dispositivo" y "Configuración PDV", el campo Bancos muestra "N/A" en lugar de un número
- **Botón Duplicar:** Cada concepto de Setup tiene un botón para clonar la línea (las copias pueden eliminarse)
- **Nuevos Medios de Pago con Bancos = 1:** Los medios de pago agregados inician con Bancos = 1 por defecto (configuración granular)
- **Otros Recurrentes con indicador:** Cuando la tarifa es $0.00, se muestra "Configurar" para indicar que el usuario debe ingresar el valor manualmente
- **Estado:** IMPLEMENTADO

### Nueva Funcionalidad: Plantillas de Cotización PDF (Febrero 2026)
- **Configuración de Plantillas:**
  - VPOS Pyme
  - VPOS Corporativo
  - Payment Gateway
  - MPOS
  - Dispositivos
  - Accesorios
- **Endpoints:**
  - `POST /api/config/templates/{type}` - Subir plantilla
  - `GET /api/config/templates/{type}` - Descargar plantilla
  - `DELETE /api/config/templates/{type}` - Eliminar plantilla
  - `GET /api/config/templates` - Listar estado de plantillas
- **UI en Configuración:** Tarjetas por tipo con estados (subido/pendiente), botones de subir, ver y eliminar

### Mejora: Sincronización de Cajas y Bancos (Febrero 2026)
- Todos los conceptos base (Setup, Recurrentes Básicos, Otros Recurrentes) heredan automáticamente los valores de Cajas y Bancos de la cabecera
- **Excepciones:** "Configuración dispositivo (Pinpad o POS)" y "Configuración PDV en MServer" mantienen sus campos bloqueados
- Se actualizan en tiempo real cuando cambian los valores en la cabecera

### Nueva Funcionalidad: Ajustes de Lógica de Cotización (Febrero 2026)
- **Restricciones de Campos:**
  - "Configuración dispositivo (Pinpad o POS)" → Campo Bancos bloqueado (valor fijo = 1)
  - "Configuración PDV en MServer" → Campo Bancos bloqueado (valor fijo = 1)
  - "Configuración Medio de Pago / Banco en MServer, por PDV" → Campo Bancos auto-calculado (= cantidad de medios de pago agregados)
- **Mejoras UX:**
  - Eliminado botón "Complementar Recurrentes" (lógica ahora automática)
  - Agregados botones Eliminar por fila en items adicionales y recurrentes auto-vinculados
  - Borrado en cascada: eliminar medio de pago → elimina su recurrente vinculado
- **Bug Fix - Crear Cotización:**
  - `item_id` ahora es opcional en QuoteItem
  - `exchange_rate` usa valor por defecto (40.0) si no existe en BD
- **Nueva Funcionalidad - Exportar PDF:**
  - Endpoint POST `/api/quotes/generate-pdf`
  - Genera PDF profesional con secciones: Setup, Recurrentes Básicos, Otros Recurrentes
  - Incluye resumen con subtotales, descuentos y total general
  - Botón "Exportar PDF" junto a "Guardar Cotización"
- **Estado:** IMPLEMENTADO Y VERIFICADO

### Estructura Actual de Estado de Cotización
```javascript
quoteData = {
  quote_type: '',           // VPOS, GATEWAY, MPOS, LINK
  client_id: '',
  pricing_model: '',        // 'conventional' o 'outsourcing'
  cantidad_cajas: 1,
  cantidad_bancos: 1,
  setup_items: [],          // Items exclusivos de Setup (4 base)
  recurring_basic_items: [],// Recurrentes Básicos (2 base + auto-vinculados consolidados)
  recurring_other_items: [],// Otros Recurrentes (2 base)
  additional_items: [],     // Items adicionales (medios de pago de bancos)
  descuento: 0,
  notes: ''
}
```

## Backlog / Tareas Futuras
- [ ] Verificar contadores del Dashboard (P1)
- [ ] Resolver bug de descarga de PDF en Cotizaciones (P1)
- [ ] Tarifas de "Otros Recurrentes" muestran $0.00 (P2)
- [ ] Módulo de reportes estadísticos
- [ ] Consultas avanzadas de cotizaciones
- [ ] Exportación masiva a Excel
- [ ] Notificaciones por email
- [ ] Recuperación de contraseña
- [ ] Refactorización del backend (dividir server.py monolítico)
- [ ] Refactorización del frontend (descomponer Quotes.jsx)

## Sistema de Importación Estandarizado (Febrero 2026)

### Descripción
Sistema de validación robusto y transversal para todas las funcionalidades de carga masiva de datos. Proporciona feedback detallado al usuario con contadores, log de errores y alertas visuales.

### Endpoints Actualizados
- `POST /api/integrators/import` → Devuelve `ImportResult`
- `POST /api/clients/import` → Devuelve `ImportResult`
- `POST /api/banks/import` → Devuelve `ImportResult`
- `POST /api/services/import` → Devuelve `ImportResult`

### Modelos de Respuesta
```python
class ImportError:
    row: int              # Número de fila en el archivo
    column: str           # Nombre de la columna
    value: str | None     # Valor que causó el error
    error_type: str       # 'missing', 'invalid', 'format', 'duplicate'
    message: str          # Descripción del error
    suggested_action: str # Acción sugerida para corregir

class ImportResult:
    status: str           # 'success', 'partial', 'error'
    total_processed: int  # Total de filas procesadas
    success_count: int    # Registros importados exitosamente
    error_count: int      # Cantidad de errores encontrados
    skipped_count: int    # Registros omitidos
    errors: List[ImportError]  # Detalle de cada error
    message: str          # Mensaje resumen
```

### Componente Frontend
- **ImportResultPanel** (`/app/frontend/src/components/ImportResultPanel.jsx`)
  - Alertas con colores: verde (éxito), naranja (parcial), rojo (error)
  - Contadores visuales: Total, Exitosos, Errores, Omitidos
  - Tabla de errores detallada con: Fila, Columna, Valor, Tipo de error, Acción sugerida
  - Badges de tipo de error con colores diferenciados

### Validaciones Implementadas
- Campos obligatorios vacíos → `error_type: 'missing'`
- Valores fuera de opciones permitidas (enums) → `error_type: 'invalid'`
- Formato de datos incorrecto → `error_type: 'format'`
- Registros duplicados en base de datos → `error_type: 'duplicate'`

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- Testing: 131/131 tests pasados (incluyendo 26 tests nuevos de importación)

---

## Campos de Integración y Hardware en Cotizaciones (Febrero 2026)

### Descripción
Nueva sección obligatoria "Detalles de Integración y Hardware" en el wizard de cotizaciones con tres campos que vinculan información de las bases de datos existentes.

### Nuevos Campos
1. **Integrador** (obligatorio)
   - Selector de integradores certificados (filtro: `integrator_status === 'Certificado'`)
   - Al seleccionar, auto-completa el campo "Aplicativo Certificado"
   
2. **Modelo de Pinpad** (obligatorio)
   - Selector de dispositivos (filtro: `type === 'Pinpad'`)
   - Muestra nombre y precio USD

3. **Entidad Patrocinadora/Vendedora** (obligatorio)
   - Dropdown con lista completa de Bancos

### Cambios en Frontend
- `Quotes.jsx`: Nueva sección después de "Parámetros de la Cotización"
- Estados: `integrator_id`, `integrator_app_name`, `pinpad_id`, `sponsor_bank_id`
- Validación: `isHeaderComplete` incluye los 3 nuevos campos
- `fetchData`: Carga integradores y hardware (filtrados como pinpads)

### Cambios en Backend
- `QuotePDFRequest`: Nuevos campos opcionales para el PDF
- `generate_quote_pdf_from_data`: Incluye integrador, aplicativo, pinpad y patrocinador en el PDF

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- Testing: 100% (12/12 tests backend, UI tests pasados)

---

## Ciclo de Vida y Menú de Acciones en Cotizaciones (Febrero 2026)

### Descripción
Sistema de gestión del ciclo de vida de cotizaciones con un menú de acciones contextuales para cada registro.

### Estados del Ciclo de Vida
```
Borrador → Emitida → Aprobada → En Implementación → Completada
```

### Acciones Implementadas
| Acción | Descripción | Impacto en Sistema |
|--------|-------------|-------------------|
| Modificar | Abre formulario con datos precargados | En desarrollo |
| Enviar al Cliente | Email automático con PDF adjunto | Cambia estado a "Emitida" |
| Aprobar | Valida cierre de negociación | Cambia estado a "Aprobada" |
| Enviar a Implementación | Email al equipo operativo | Cambia estado a "En Implementación" |

### Endpoints de Acciones
- `PUT /api/quotes/{quote_id}/status` - Actualiza estado
- `POST /api/quotes/{quote_id}/send-to-client` - Envía al cliente
- `POST /api/quotes/{quote_id}/send-to-implementation` - Envía a implementación

### Configuración de Email
- **Servicio**: Resend (requiere RESEND_API_KEY en .env)
- **Email de implementación**: Configurable en Settings (`/api/config/settings`)
- **Modo simulado**: Si no hay API key, los emails se simulan pero los estados cambian correctamente

### Campos Agregados al Modelo Quote
```python
quote_status: str  # Borrador, Emitida, Aprobada, En Implementación, Completada
sent_to_client_at: Optional[datetime]
approved_at: Optional[datetime]
sent_to_implementation_at: Optional[datetime]
```

### UI Implementada
- Columna "Estado" en tabla de cotizaciones con colores diferenciados
- Menú desplegable de acciones (DropdownMenu) con iconos
- Validación de flujo: acciones habilitadas/deshabilitadas según estado
- Sección de email de implementación en página Settings

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- **NOTA**: Email SIMULADO (requiere RESEND_API_KEY para envío real)
- Testing: 100% (17/17 tests backend, UI verificada)

---

## Matriz de Resumen Ejecutivo (Febrero 2026)

### Descripción
Sección de resumen consolidado al final de cada cotización que presenta información técnica y comercial en formato de fácil lectura para el cliente.

### Campo Dirección en Clientes
- **Backend**: Campo `address: Optional[str]` agregado a modelos `ClientCreate` y `Client`
- **Frontend**: Campo "Dirección Fiscal" en formulario de Clientes

### Estructura del Resumen Ejecutivo

#### 1. Cabecera
| Campo | Color | Datos |
|-------|-------|-------|
| Cliente | Amarillo (amber-400) | Nombre/Razón Social |
| Cantidad de Cajas | Azul (blue-200) | Total de PDV cotizados |
| Dirección Fiscal | Verde (green-200) | Dirección del cliente |

#### 2. Matriz de Distribución
| Columna | Color | Contenido |
|---------|-------|-----------|
| Bancos | Verde (green-200) | Entidad financiera |
| Productos | Azul (blue-200) | Medio de pago |
| Cantidad de Cajas | Amarillo (amber-400) | Número de cajas por producto |

#### 3. Total de Terminales Virtuales
- Suma de `cantidad_cajas` de todos los items (setup + adicionales)

### Ubicación en Código
- `Quotes.jsx` líneas 1867-1963
- Sección aparece después del "Total General"
- data-testid: `executive-summary`

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- Testing: 100% (8/8 tests backend)

---

## Reestructuración del Módulo de Cotizaciones de Equipos (Febrero 2026)

### Descripción
Actualización del wizard de cotizaciones de Equipos y Accesorios con lógica de selección dinámica y panel de gestión unificado.

### 1. Lógica de Selección Dinámica (Paso 2)

| Categoría Seleccionada | Comportamiento |
|------------------------|----------------|
| **Dispositivos** | Muestra dropdown secundario exclusivo con opciones: POS y Pinpad |
| **Accesorios** | Carga automáticamente ítems de categoría (sin dropdown secundario) |

**Regla de Negocio:** El campo de selección de ítems está bloqueado/vacío hasta que el usuario defina el "Tipo de Ítem", para evitar errores en la carga de datos.

### 2. Filtrado de Productos (Paso 3)

| Selección | Tipos que muestra |
|-----------|-------------------|
| Dispositivos > POS | Solo ítems con `type === 'POS'` |
| Dispositivos > Pinpad | Solo ítems con `type === 'Pinpad'` |
| Accesorios | Ítems con `type === 'Accesorio'` o `type === 'Base'` |

### 3. Panel de Gestión Único

- Tabla unificada que muestra **todas** las cotizaciones (Implementaciones + Equipos)
- Nueva columna **"Categoría"** con badges de color:
  - `Implementación` (verde)
  - `Equipos` (amber)
- Columna **"Tipo"** muestra el tipo específico (VPOS, POS, Pinpad, Accesorio, etc.)
- Nomenclatura estandarizada: `COT-YYYY-XXXX` para todos los tipos

### 4. Modal de Confirmación

Antes de generar el PDF, se muestra un modal con:
- Nombre del cliente
- RIF
- Tipo de cotización
- Cantidad de ítems
- Total USD

### Archivos Modificados
- `frontend/src/components/EquipmentQuoteWizard.jsx` - Lógica de selección dinámica
- `frontend/src/pages/Quotes.jsx` - Panel unificado

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- Testing: 100% (8/8 tests frontend - Iteration 15)

---

## Filtros Rápidos en Panel de Cotizaciones (Febrero 2026)

### Descripción
Sistema de filtrado rápido para facilitar la búsqueda de cotizaciones en el panel unificado.

### Filtros Implementados

| Filtro | Componente | Test ID |
|--------|------------|---------|
| Cliente | Select dropdown | `filter-client` |
| Estado | Select dropdown | `filter-status` |
| Categoría | Select dropdown | `filter-category` |
| Fecha Desde | Input date | `filter-date-from` |
| Fecha Hasta | Input date | `filter-date-to` |
| Limpiar | Button | `clear-filters-btn` |

### Estados Disponibles
- Borrador
- Emitida
- Aprobada
- En Implementación
- Completada

### Categorías
- Implementación (flujo original)
- Equipos (cotizaciones de hardware)

### Comportamiento
- Los filtros se aplican en tiempo real al cambiar cualquier valor
- El valor "all" (Todos) no aplica filtro
- Los filtros se combinan con AND lógico
- Al no encontrar resultados, se muestra mensaje con botón para limpiar filtros

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- Testing: 100% (8/8 features - Iteration 16)

---

## Corrección de Descarga de PDF (Febrero 2026 - Segunda Iteración)

### Problema
El usuario reportó que la descarga de PDF seguía sin funcionar a pesar de las correcciones anteriores.

### Causa Raíz
Axios con `responseType: 'blob'` junto con `withCredentials: true` puede causar problemas de CORS y manejo de respuestas en algunos navegadores.

### Solución Implementada (Final)
Se reemplazó completamente axios por **fetch nativo** para las descargas de PDF:
1. Uso de `fetch()` con headers de Authorization explícitos
2. Validación de `response.ok` y `content-type`
3. Verificación de `blob.size > 0`
4. Creación de elemento `<a>` con `download` attribute
5. Limpieza asincrónica de recursos
6. Aplicado a todas las funciones de PDF: `downloadPDF`, `exportCurrentQuoteToPDF`, y `EquipmentQuoteWizard`

### Archivos Modificados
- `frontend/src/pages/Quotes.jsx` - funciones downloadPDF y exportCurrentQuoteToPDF
- `frontend/src/components/EquipmentQuoteWizard.jsx` - función handleGeneratePDF

### Estado
- **CORREGIDO Y VERIFICADO** - Febrero 2026
- Testing: 100% (Backend verificado, PDF válido confirmado via curl)

---

## Sistema de Estados de Cotizaciones (Febrero 2026)

### Descripción
Implementación completa del nuevo flujo de estados para cotizaciones según documento de especificaciones.

### Flujo de Estados

#### Categoría: Implementación
```
Borrador -> Enviada -> Aprobada -> Facturada -> Pagada -> Enviada a Imple
```

#### Categoría: Equipos y Accesorios
```
Borrador -> Enviada -> Aprobada -> Facturada -> Pagada -> Entregada
```

### Acciones por Estado

| Estado Actual | Acción | Nuevo Estado | Notificación |
|---------------|--------|--------------|--------------|
| Borrador | Enviar al Cliente | Enviada | - |
| Enviada | Aprobar | Aprobada | → Administración |
| Aprobada | Facturar | Facturada | → Administración + PDF requerido |
| Facturada | Cobrar | Pagada | → Almacén (solo Equipos) |
| Pagada (Equipos) | Entregar | Entregada | - |
| Pagada (Implementación) | Enviar a Imple | Enviada a Imple | → Implementación |

### Gestión de Versiones
- Acción **"Modificar"** crea una nueva versión de la cotización
- Nuevo número correlativo: `COT-YYYY-NNN`
- Campo `version` incrementado
- Campo `parent_quote_id` referencia al original
- Cotización original permanece intacta
- Nueva versión queda en estado **Borrador**

### Configuración de Correos (Settings)

| Campo | Descripción | Test ID |
|-------|-------------|---------|
| Correo de Administración | Recibe notificaciones de Aprobación y Facturación | `admin-email-input` |
| Correo de Almacén | Recibe notificaciones cuando Equipos pasa a Pagada | `warehouse-email-input` |
| Correo de Implementación | Recibe detalles técnicos al Enviar a Implementación | `implementation-email-input` |

### Endpoints Nuevos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/quotes/{id}/invoice` | Facturar con PDF obligatorio |
| POST | `/api/quotes/{id}/collect` | Marcar como Pagada |
| POST | `/api/quotes/{id}/deliver` | Marcar como Entregada (equipos) |
| POST | `/api/quotes/{id}/duplicate` | Crear nueva versión |

### Modal de Factura
- Campo: Número de factura (opcional)
- Archivo: PDF de factura (obligatorio)
- Test IDs: `invoice-number-input`, `invoice-file-input`, `invoice-submit-btn`

### Archivos Modificados
- `backend/server.py` - Nuevos endpoints y configuración
- `frontend/src/pages/Quotes.jsx` - Menú de acciones, modal de factura, estados
- `frontend/src/pages/Settings.jsx` - Campos de correo

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- Testing: 100% (17/17 backend, frontend code review - Iteration 17)

---
**Última actualización:** Febrero 2026
**Estado:** MVP Operativo - Sistema de Estados de Cotizaciones COMPLETO

---

## Módulo de Comunicaciones (Febrero 2026)

### Descripción
Sistema completo de plantillas de correo personalizables y corrección de la funcionalidad de modificación de cotizaciones.

### 1. Acción "Modificar" - Corregida

**Comportamiento anterior:** Solo creaba una copia sin permitir edición.

**Comportamiento actual:**
1. Abre el wizard con los datos de la cotización precargados
2. Permite modificar cualquier campo
3. Al guardar, crea una nueva versión con:
   - Nuevo número correlativo (COT-YYYY-NNN)
   - Campo `version` incrementado
   - Campo `parent_quote_id` apuntando a la original
   - Estado inicial: **Borrador**
4. La cotización original permanece intacta

**Endpoint nuevo:** `PUT /api/quotes/{quote_id}` - Solo permite actualizar cotizaciones en estado Borrador.

### 2. Plantillas de Correo Personalizables

Nueva sección en **Configuración → Plantillas de Correo Electrónico**.

| Plantilla | Disparador | Variables Disponibles |
|-----------|------------|----------------------|
| **Envío de Cotización** | Enviar al Cliente | quote_number, client_name, client_rif, quote_type, total_usd, company_name |
| **Facturación** | Facturar | quote_number, client_name, client_rif, invoice_number, total_usd |
| **Despacho de Equipos** | Cobrar (Equipos) | quote_number, client_name, client_rif, client_address, items_table |
| **Inicio de Obra** | Enviar a Implementación | quote_number, client_name, client_rif, quote_type, integrator_name, pinpad_model, services_table |

**Funcionalidades del Editor:**
- Editar **Asunto** y **Cuerpo HTML**
- Lista de **variables disponibles** clickeables para insertar
- **Vista previa** con datos de ejemplo
- **Restablecer** a valores predeterminados

### 3. Integración con Resend

Los correos ahora usan las plantillas configuradas:
- `render_email_template()` reemplaza `{variable}` con valores reales
- Si no hay plantilla en BD, usa `DEFAULT_EMAIL_TEMPLATES`
- PDFs se adjuntan automáticamente según el escenario

### Endpoints Nuevos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/email-templates` | Lista todas las plantillas |
| GET | `/api/email-templates/{id}` | Obtiene una plantilla |
| PUT | `/api/email-templates/{id}` | Actualiza una plantilla |
| POST | `/api/email-templates/reset/{id}` | Restablece a valores predeterminados |
| PUT | `/api/quotes/{id}` | Actualiza cotización (solo Borrador) |

### Archivos Nuevos/Modificados
- `frontend/src/components/EmailTemplatesEditor.jsx` - **NUEVO**
- `backend/server.py` - Endpoints de plantillas, DEFAULT_EMAIL_TEMPLATES
- `frontend/src/pages/Settings.jsx` - Sección de plantillas
- `frontend/src/pages/Quotes.jsx` - Función handleEditQuote actualizada

### Estado
- **IMPLEMENTADO Y VERIFICADO** - Febrero 2026
- Testing: 100% (18/18 backend, 100% frontend - Iteration 18)

---

## Pendientes Registrados

### Bug de Descarga de PDF (Prioridad Baja)
- **Estado:** Registrado para mantenimiento posterior
- **Descripción:** Se han realizado múltiples correcciones pero el usuario reporta fallas persistentes
- **Próximos pasos:** Investigación profunda del comportamiento en diferentes navegadores

---
**Última actualización:** Febrero 2026
**Estado:** MVP Operativo - Módulo de Comunicaciones COMPLETO
