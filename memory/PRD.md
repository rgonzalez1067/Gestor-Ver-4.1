# Cotizador Merchant Server - PRD

## Descripción General
Sistema integral de cotizaciones para plataformas de medios de pago. Permite gestionar clientes, bancos, hardware, servicios y generar cotizaciones profesionales con conversión de tasa de cambio BCV.

## Estado Actual: MVP Operativo ✅

## Stack Tecnológico
- **Backend:** FastAPI (Python)
- **Frontend:** React + TailwindCSS + Shadcn/UI
- **Base de Datos:** MongoDB
- **Autenticación:** Emergent-managed Google OAuth
- **Email:** Resend (configurable desde UI)
- **PDF:** ReportLab

---

## Correcciones Realizadas - 19 Febrero 2026

### 1. Bug Fix: Items Adicionales no se cargan en Modificar ✅
**Problema:** Los conceptos adicionales/agregados en Setup no se cargaban al editar una cotización.

**Solución:**
- Backend: Agregados campos `bank_id`, `bank_name`, `tarifa_setup`, `tarifa_recurrente` al modelo `QuoteItem`
- Frontend: Nueva función `mapAdditionalItem()` que mapea correctamente los campos específicos de items adicionales
- Frontend: `handleSubmitQuote` y `handleSaveEditedQuote` ahora preservan estos campos

### 2. Bug Fix: Descarga de PDF no funcionaba ✅
**Problema:** El sistema mostraba "descargado exitosamente" pero el archivo no se descargaba realmente.

**Solución:**
- Implementación de 3 métodos de fallback en `downloadPDF()`:
  1. Descarga directa con blob URL y elemento `<a>`
  2. Apertura en nueva pestaña (fallback)
  3. Iframe invisible como último recurso
- Mejor manejo de errores y logging para debugging

### 3. Feature: Configuración de Motor de Correos (Resend) ✅
**Problema:** No existía sección para configurar la API Key de Resend.

**Solución:**
- Backend: Agregado campo `resend_api_key` al modelo `AppSettings`
- Backend: Endpoint GET/PUT `/api/config/settings` maneja la API key con enmascaramiento
- Backend: Helper `get_resend_api_key()` para obtener key de BD o env
- Frontend: Nueva sección "Motor de Correos (Resend)" en Settings con:
  - Campo de entrada para API Key
  - Toggle para mostrar/ocultar la key
  - Indicador de estado (configurada/no configurada)
  - API Key enmascarada después de guardar

---

## Funcionalidades Implementadas

### Módulo de Cotizaciones
- [x] CRUD completo de cotizaciones
- [x] Dos categorías: Implementaciones y Equipos/Accesorios
- [x] Panel unificado con filtros por cliente, estado, categoría, fecha
- [x] Wizard de creación con pasos guiados
- [x] Modificar cotización (crea nueva versión)
- [x] Generación y descarga de PDF
- [x] Duplicar cotización

### Flujo de Estados
- Borrador → Enviada al Cliente → Aprobada → Facturada → Pagada → Entregada/Enviada a Implementación
- Notificaciones automáticas por email en cada transición

### Módulos CRUD
- [x] Clientes (con segmento: Pymes/Corporativo/Mixto)
- [x] Bancos (Venezuela, EE.UU., Fintechs)
- [x] Hardware (dispositivos de pago)
- [x] Medios de Pago/Servicios
- [x] Integradores
- [x] Importación/Exportación masiva

### Configuración
- [x] Logo de empresa
- [x] Correos de notificación (Admin, Almacén, Implementación)
- [x] **Motor de Correos Resend (NUEVO)**
- [x] Plantillas de correo personalizables
- [x] Plantillas PDF por tipo de cotización

---

## Modelos de Datos Clave

### QuoteItem (Actualizado)
```python
class QuoteItem(BaseModel):
    item_type: str
    item_id: Optional[str]
    item_name: str
    quantity: int
    unit_price_usd: float
    total_usd: float
    cantidad_cajas: Optional[int]
    cantidad_bancos: Optional[int]
    # Campos para items adicionales
    bank_id: Optional[str]
    bank_name: Optional[str]
    tarifa_setup: Optional[float]
    tarifa_recurrente: Optional[float]
```

### AppSettings (Actualizado)
```python
class AppSettings(BaseModel):
    implementation_email: Optional[EmailStr]
    admin_email: Optional[EmailStr]
    warehouse_email: Optional[EmailStr]
    resend_api_key: Optional[str]  # NUEVO
```

---

## Endpoints API Principales

### Cotizaciones
- `POST /api/quotes` - Crear cotización
- `GET /api/quotes` - Listar cotizaciones
- `PUT /api/quotes/{id}` - Actualizar (solo Borrador)
- `POST /api/quotes/{id}/duplicate` - Duplicar/Nueva versión
- `GET /api/quotes/{id}/pdf` - Descargar PDF

### Estados
- `POST /api/quotes/{id}/send-to-client` - Enviar al cliente
- `POST /api/quotes/{id}/approve` - Aprobar
- `POST /api/quotes/{id}/invoice` - Facturar
- `POST /api/quotes/{id}/collect` - Marcar como pagada
- `POST /api/quotes/{id}/deliver` - Marcar como entregada
- `POST /api/quotes/{id}/send-to-implementation` - Enviar a implementación

### Configuración
- `GET/PUT /api/config/settings` - Configuración general (incluye Resend API Key)
- `GET/POST/DELETE /api/config/logo` - Logo de empresa
- `GET/PUT /api/email-templates` - Plantillas de correo

---

## Backlog / Tareas Pendientes

### P2 - Media Prioridad
- [ ] Contadores del Dashboard no suman correctamente (bug recurrente)
- [ ] Refactorización del backend (dividir server.py monolítico)
- [ ] Refactorización del frontend (descomponer Quotes.jsx)

### P3 - Baja Prioridad
- [ ] Módulo de Reportes estadísticos
- [ ] Recuperación de contraseña
- [ ] Exportación masiva a Excel

---

## Testing Status
- Backend: 12/12 tests PASSED ✅
- Frontend: 12/12 features verificadas ✅
- Test reports: `/app/test_reports/iteration_21.json`

## Archivos Clave
- `/app/backend/server.py` - Backend monolítico
- `/app/frontend/src/pages/Quotes.jsx` - Panel de cotizaciones
- `/app/frontend/src/pages/Settings.jsx` - Configuración

---
**Última actualización:** 19 Febrero 2026
**Estado:** MVP Operativo - 3 Bugs Críticos Corregidos ✅
