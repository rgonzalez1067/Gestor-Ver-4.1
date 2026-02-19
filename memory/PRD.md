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
- **Email:** Resend

## Funcionalidades Implementadas

### Backend (FastAPI)
- [x] Autenticación via Emergent Google OAuth
- [x] CRUD Clientes (con campo `segment`: Pymes/Corporativo/Mixto)
- [x] Importación/Exportación de Clientes (CSV/PDF)
- [x] CRUD Bancos (Venezuela, EE.UU., Fintechs) con medios de pago asociados
- [x] CRUD Hardware
- [x] CRUD Medios de Pago con compatibilidad por tipo de cotización
- [x] CRUD Cotizaciones con flujo optimizado
- [x] Tasa de cambio BCV
- [x] Upload/descarga/eliminación de logo de empresa
- [x] Generación de PDF para cotizaciones
- [x] Sistema de estados de cotización avanzado
- [x] Plantillas de correo personalizables

### Frontend (React)
- [x] Login con Google OAuth
- [x] Panel de cotizaciones unificado (Implementaciones + Equipos)
- [x] Filtros rápidos por cliente, estado, categoría y fecha
- [x] Flujo de estados completo (Borrador → Enviada → Aprobada → Facturada → Pagada → Entregada/Enviada a Imple)
- [x] Módulo de plantillas de correo en Configuración
- [x] Wizard de equipos con selección dinámica
- [x] **Funcionalidad "Modificar Cotización" (CORREGIDA - Feb 2026)**

## Correcciones Recientes (Febrero 2026)

### Bug Fix: Funcionalidad "Modificar Cotización" - CORREGIDO ✅
**Fecha:** 19 Febrero 2026

**Problemas reportados:**
1. Al guardar, la modificación sobrescribía la cotización original en lugar de crear una nueva versión
2. El formulario de edición no precargaba correctamente todos los datos (cantidad de cajas, bancos, precios)

**Solución implementada:**

**Backend (`server.py`):**
- Agregados campos `cantidad_cajas` y `cantidad_bancos` al modelo `QuoteItem`
- Agregados campos `cantidad_cajas` y `cantidad_bancos` al modelo `Quote`
- Agregados campos `cantidad_cajas` y `cantidad_bancos` al modelo `QuoteCreate`
- Agregados campos `cantidad_cajas` y `cantidad_bancos` al modelo `QuoteUpdate`
- Modificado `create_quote` para guardar estos campos a nivel de cotización

**Frontend (`Quotes.jsx`):**
- `handleSubmitQuote`: Ahora envía `cantidad_cajas` y `cantidad_bancos` tanto a nivel de cotización como por cada item de servicio
- `handleEditQuote`: Lee correctamente `cantidad_cajas` y `cantidad_bancos` del backend (tanto a nivel cotización como por servicio)
- `handleSaveEditedQuote`: Usa `POST /quotes/{id}/duplicate` para crear nueva versión y luego `PUT /quotes/{new_id}` para actualizarla

**Resultado:**
- Al modificar una cotización, se crea una nueva versión (nuevo número correlativo COT-YYYY-NNN)
- La cotización original permanece intacta
- Todos los datos se precargan correctamente incluyendo cantidad de cajas, bancos y tarifas
- Testing: 11/11 tests backend PASSED ✅

## Endpoints API Clave

### Cotizaciones
- `POST /api/quotes` - Crear cotización (incluye cantidad_cajas, cantidad_bancos)
- `GET /api/quotes` - Listar cotizaciones
- `GET /api/quotes/{id}` - Obtener cotización
- `PUT /api/quotes/{id}` - Actualizar cotización (solo Borrador)
- `POST /api/quotes/{id}/duplicate` - Crear nueva versión
- `GET /api/quotes/{id}/pdf` - Descargar PDF
- `POST /api/quotes/{id}/send-to-client` - Enviar al cliente
- `POST /api/quotes/{id}/invoice` - Facturar
- `POST /api/quotes/{id}/collect` - Cobrar
- `POST /api/quotes/{id}/deliver` - Entregar (equipos)
- `POST /api/quotes/{id}/send-to-implementation` - Enviar a implementación

### Plantillas de Correo
- `GET /api/email-templates` - Lista plantillas
- `PUT /api/email-templates/{id}` - Actualizar plantilla
- `POST /api/email-templates/reset/{id}` - Restablecer plantilla

## Modelos de Datos

### QuoteItem (Actualizado)
```json
{
  "item_type": "string",
  "item_id": "string (optional)",
  "item_name": "string",
  "quantity": "int",
  "unit_price_usd": "float",
  "total_usd": "float",
  "cantidad_cajas": "int (optional)",
  "cantidad_bancos": "int (optional)"
}
```

### Quote (Actualizado)
```json
{
  "quote_id": "string",
  "quote_number": "string",
  "client_id": "string",
  "quote_category": "implementation | equipment",
  "quote_type": "VPOS | GATEWAY | MPOS | LINK",
  "pricing_model": "conventional | outsourcing",
  "services": "List[QuoteItem]",
  "cantidad_cajas": "int (optional)",
  "cantidad_bancos": "int (optional)",
  "version": "int",
  "parent_quote_id": "string (optional)",
  "quote_status": "Borrador | Enviada | Aprobada | Facturada | Pagada | Entregada | Enviada a Imple"
}
```

## Backlog / Tareas Pendientes

### P1 - Alta Prioridad
- [ ] **Bug de descarga de PDF** - El usuario reporta que muestra "descargado exitosamente" pero no descarga el archivo
- [ ] Configuración de motor de correos (Resend/SMTP) en Settings
- [ ] Contadores del Dashboard no suman correctamente

### P2 - Media Prioridad
- [ ] Refactorización del backend (dividir server.py monolítico)
- [ ] Refactorización del frontend (descomponer Quotes.jsx)
- [ ] Módulo de reportes estadísticos

### P3 - Baja Prioridad
- [ ] Recuperación de contraseña
- [ ] Exportación masiva a Excel

## Testing Status
- Backend: Tests de "Modificar Cotización" - 11/11 PASSED ✅
- Frontend: Verificado con Playwright ✅
- Test files: `/app/backend/tests/test_modificar_cotizacion.py`

## Archivos Clave
- `/app/backend/server.py` - Backend monolítico FastAPI
- `/app/frontend/src/pages/Quotes.jsx` - Componente principal de cotizaciones
- `/app/frontend/src/pages/Settings.jsx` - Configuración y plantillas
- `/app/frontend/src/components/EmailTemplatesEditor.jsx` - Editor de plantillas

---
**Última actualización:** 19 Febrero 2026
**Estado:** MVP Operativo - Funcionalidad "Modificar Cotización" CORREGIDA ✅
