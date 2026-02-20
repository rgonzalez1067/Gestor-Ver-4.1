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

## Implementación del Flujo de Estados - 20 Febrero 2026

### Flujo de Aprobación, Facturación y Cierre ✅

| Acción | Estado Resultante | Trigger/Requisito |
|--------|------------------|-------------------|
| Enviar al Cliente | Enviada | Email al cliente |
| **Aprobar** | **Aprobada** | **Email a Administración** |
| Facturar | Facturada | PDF de factura obligatorio |
| Cobrar | Pagada | Verificación de pago |
| Enviar a Implementación | Enviada a Imple | Email a Implementación (solo si Pagada) |

### Detalles de Implementación:

1. **Nuevo Endpoint `POST /quotes/{id}/approve`**
   - Valida que la cotización esté en estado "Enviada"
   - Cambia estado a "Aprobada"
   - Registra timestamp `approved_at`
   - Envía email automático a Administración (admin_email)
   - Usa plantilla "quote_approved"

2. **Validación en `POST /send-to-implementation`**
   - Ahora requiere que la cotización esté en estado "Pagada"
   - Rechaza con HTTP 400 si no cumple la condición

3. **Nueva Plantilla de Email "quote_approved"**
   - Asunto: "[APROBADA] Cotización #{quote_number} - Lista para Facturar"
   - Notifica a Administración que la cotización está lista para facturar
   - Incluye: número de cotización, cliente, tipo, total

---

## Funcionalidades Implementadas

### Módulo de Cotizaciones
- [x] CRUD completo
- [x] Eliminar en cualquier estado
- [x] Campos opcionales (Pinpad, Entidad Patrocinadora)
- [x] Flujo de estados completo con validaciones
- [x] Notificaciones automáticas por email
- [x] Generación y descarga de PDF

### Flujo de Estados (Actualizado)
```
Borrador → Enviada (email cliente) → Aprobada (email admin) → 
Facturada (PDF obligatorio) → Pagada → Enviada a Imple (email implementación)
```

### Emails Automáticos
1. **quote_sent** - Al cliente cuando se envía la cotización
2. **quote_approved** - A Administración cuando se aprueba (NUEVO)
3. **invoice** - A Administración cuando se factura
4. **warehouse** - A Almacén cuando equipos están pagados
5. **implementation** - A Implementación cuando se envía el proyecto

---

## Endpoints API (Actualizados)

### Estados de Cotización
- `POST /api/quotes/{id}/send-to-client` - Enviar al cliente (Borrador → Enviada)
- `POST /api/quotes/{id}/approve` - **NUEVO: Aprobar + Email Admin** (Enviada → Aprobada)
- `POST /api/quotes/{id}/invoice` - Facturar con PDF (Aprobada → Facturada)
- `POST /api/quotes/{id}/collect` - Cobrar (Facturada → Pagada)
- `POST /api/quotes/{id}/send-to-implementation` - Enviar a Imple (solo desde Pagada)
- `POST /api/quotes/{id}/deliver` - Entregar equipos (Pagada → Entregada)

---

## Backlog / Tareas Pendientes

### P2 - Media Prioridad
- [ ] Contadores del Dashboard no suman correctamente
- [ ] Refactorización del backend (dividir server.py)
- [ ] Refactorización del frontend (descomponer Quotes.jsx)

### P3 - Baja Prioridad
- [ ] Módulo de Reportes
- [ ] Recuperación de contraseña

---

## Testing Status
- Backend: 100% (11/11 tests passed) ✅
- Test file: `/app/backend/tests/test_iteration25_approve_flow.py`

---
**Última actualización:** 20 Febrero 2026
**Estado:** MVP Operativo - Flujo de Estados Completo ✅
