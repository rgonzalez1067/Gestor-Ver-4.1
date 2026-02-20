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

### 1. Funciones de Eliminación Activadas ✅

**Backend:**
- Nuevo endpoint `DELETE /api/quotes/{quote_id}` que solo permite eliminar cotizaciones en estado "Borrador"
- Validación de estado antes de eliminar con mensaje de error apropiado

**Frontend Cotizaciones:**
- Nueva opción "Eliminar Cotización" en menú desplegable (ícono rojo Trash2)
- Opción deshabilitada para cotizaciones que no están en estado Borrador
- Confirmación antes de eliminar con mensaje descriptivo

**Frontend Wizard de Cotización:**
- Botón de eliminar en TODOS los conceptos de Setup (sin restricción isDefault)
- Botón de eliminar en TODOS los conceptos de Recurrentes Básicos
- Botón de eliminar en TODOS los conceptos de Otros Recurrentes
- Confirmación antes de cada eliminación
- Recálculo automático de totales al eliminar cualquier concepto

### 2. Rediseño de Dispositivos y Accesorios ✅

**Antes:** Vista de tarjetas (cards) en grid
**Ahora:** Vista de tabla estilo MediosPago con:
- Columnas: Dispositivo/Accesorio, Tipo, Precio Efectivo, Precio Bs/USD, Acciones
- Badges de tipo con colores: Pinpad(azul), POS(verde), Cable(amarillo), Base(morado), Accesorio(gris)
- Botones Editar y Eliminar en columna de acciones
- Resumen por tipo de dispositivo al final de la página
- Consistencia visual con el resto de la aplicación

---

## Funcionalidades Implementadas (Completo)

### Módulo de Cotizaciones
- [x] CRUD completo de cotizaciones (Create, Read, Update, **DELETE**)
- [x] Dos categorías: Implementaciones y Equipos/Accesorios
- [x] Panel unificado con filtros por cliente, estado, categoría, fecha
- [x] Wizard de creación con pasos guiados
- [x] Modificar cotización (crea nueva versión)
- [x] **Eliminar cotización (solo Borradores)**
- [x] **Eliminar conceptos individuales con recálculo**
- [x] Generación y descarga de PDF
- [x] Duplicar cotización

### Flujo de Estados
- Borrador → Enviada al Cliente → Aprobada → Facturada → Pagada → Entregada/Enviada a Implementación
- Notificaciones automáticas por email en cada transición

### Módulos CRUD
- [x] Clientes (con segmento: Pymes/Corporativo/Mixto)
- [x] Bancos (Venezuela, EE.UU., Fintechs)
- [x] **Hardware/Dispositivos (rediseñado a tabla)**
- [x] Medios de Pago/Servicios
- [x] Integradores
- [x] Importación/Exportación masiva

### Configuración
- [x] Logo de empresa
- [x] Correos de notificación (Admin, Almacén, Implementación)
- [x] Motor de Correos Resend (API Key configurable)
- [x] Plantillas de correo personalizables
- [x] Plantillas PDF por tipo de cotización

---

## Endpoints API (Actualizados)

### Cotizaciones
- `POST /api/quotes` - Crear cotización
- `GET /api/quotes` - Listar cotizaciones
- `PUT /api/quotes/{id}` - Actualizar (solo Borrador)
- `DELETE /api/quotes/{id}` - **NUEVO: Eliminar (solo Borrador)**
- `POST /api/quotes/{id}/duplicate` - Duplicar/Nueva versión
- `GET /api/quotes/{id}/pdf` - Descargar PDF

### Hardware
- `GET /api/hardware` - Listar dispositivos
- `POST /api/hardware` - Crear dispositivo
- `PUT /api/hardware/{id}` - Actualizar dispositivo
- `DELETE /api/hardware/{id}` - Eliminar dispositivo ✅

---

## Backlog / Tareas Pendientes

### P2 - Media Prioridad
- [ ] Contadores del Dashboard no suman correctamente
- [ ] Refactorización del backend (dividir server.py monolítico)
- [ ] Refactorización del frontend (descomponer Quotes.jsx)

### P3 - Baja Prioridad
- [ ] Módulo de Reportes estadísticos
- [ ] Recuperación de contraseña
- [ ] Exportación masiva a Excel

---

## Testing Status
- Backend: 10/10 tests PASSED ✅
- Frontend: 11/11 features verificadas ✅
- Test reports: `/app/test_reports/iteration_22.json`

## Archivos Clave Modificados
- `/app/backend/server.py` - Nuevo endpoint DELETE quotes
- `/app/frontend/src/pages/Quotes.jsx` - Funciones de eliminación
- `/app/frontend/src/pages/Hardware.jsx` - Rediseñado a tabla

---
**Última actualización:** 20 Febrero 2026
**Estado:** MVP Operativo - Funciones CRUD Completas ✅
