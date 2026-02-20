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

## Implementaciones Realizadas - 20 Febrero 2026

### 1. Eliminación Global Sin Restricciones ✅

**Cambio solicitado:** La función de eliminar debe estar disponible en cualquier estado (Borrador, Enviada, Aprobada, Facturada, etc.) como función de mantenimiento básica.

**Implementación:**
- Backend: Endpoint `DELETE /api/quotes/{quote_id}` ya NO valida el estado
- Frontend: DropdownMenuItem "Eliminar Cotización" ya NO tiene atributo `disabled`
- Se puede eliminar cotizaciones en cualquier etapa del proceso

### 2. Campos Opcionales (Pinpad y Entidad Patrocinadora) ✅

**Cambio solicitado:** Los campos "Modelo de Pinpad" y "Entidad Patrocinadora" deben ser opcionales, no obligatorios.

**Implementación:**
- Labels actualizados de `*` (obligatorio) a `(Opcional)`
- Nuevas opciones en selectores: "Sin Pinpad" y "Sin Entidad Patrocinadora"
- Validación `isHeaderComplete` ya NO requiere estos campos
- Solo se requiere: tipo de cotización, cliente, modelo de pricing e integrador
- El formulario envía string vacío cuando se selecciona "Sin..." en lugar de "none"

---

## Funcionalidades Implementadas (Completo)

### Módulo de Cotizaciones
- [x] CRUD completo (Create, Read, Update, Delete)
- [x] **Eliminar en cualquier estado** (función de mantenimiento)
- [x] **Campos opcionales** (Pinpad, Entidad Patrocinadora)
- [x] Dos categorías: Implementaciones y Equipos/Accesorios
- [x] Panel unificado con filtros
- [x] Wizard de creación con pasos guiados
- [x] Modificar cotización (crea nueva versión)
- [x] Eliminar conceptos individuales con recálculo
- [x] Generación y descarga de PDF
- [x] Duplicar cotización

### Flujo de Estados
- Borrador → Enviada → Aprobada → Facturada → Pagada → Entregada/Enviada a Imple
- Notificaciones automáticas por email
- **Eliminación disponible en todos los estados**

### Módulos CRUD
- [x] Clientes (con segmento)
- [x] Bancos (Venezuela, EE.UU., Fintechs)
- [x] Hardware/Dispositivos (estilo tabla)
- [x] Medios de Pago/Servicios
- [x] Integradores
- [x] Importación/Exportación masiva

### Configuración
- [x] Logo de empresa
- [x] Correos de notificación
- [x] Motor de Correos Resend (API Key configurable)
- [x] Plantillas de correo personalizables
- [x] Plantillas PDF

---

## Endpoints API

### Cotizaciones
- `POST /api/quotes` - Crear (Pinpad/Sponsor opcionales)
- `GET /api/quotes` - Listar
- `PUT /api/quotes/{id}` - Actualizar
- `DELETE /api/quotes/{id}` - **Eliminar (cualquier estado)**
- `POST /api/quotes/{id}/duplicate` - Duplicar
- `GET /api/quotes/{id}/pdf` - PDF

---

## Backlog / Tareas Pendientes

### P2 - Media Prioridad
- [ ] Contadores del Dashboard no suman correctamente
- [ ] Refactorización del backend (dividir server.py)
- [ ] Refactorización del frontend (descomponer Quotes.jsx)

### P3 - Baja Prioridad
- [ ] Módulo de Reportes
- [ ] Recuperación de contraseña
- [ ] Exportación masiva a Excel

---

## Testing Status
- Backend: 100% (7/7 tests passed) ✅
- Frontend: 100% (10/10 features verified) ✅
- Test reports: `/app/test_reports/iteration_23.json`
- Test files: `/app/backend/tests/test_iteration23_optional_fields_and_delete.py`

---
**Última actualización:** 20 Febrero 2026
**Estado:** MVP Operativo - CRUD Completo con Flexibilidad ✅
