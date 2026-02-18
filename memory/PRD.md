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
- [ ] Módulo de reportes estadísticos
- [ ] Consultas avanzadas de cotizaciones
- [ ] Exportación masiva a Excel
- [ ] Notificaciones por email
- [ ] Recuperación de contraseña
- [ ] Refactorización del backend (dividir server.py monolítico)
- [ ] Refactorización del frontend (descomponer Quotes.jsx)

---
**Última actualización:** Febrero 2026
**Estado:** MVP Operativo - Lógica de Cotización y Exportar PDF IMPLEMENTADOS
