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
- [x] **Conceptos Base por Defecto (Diciembre 2025):**
  - **Setup EXCLUSIVO (4 conceptos)** - NO aparecen en recurrentes:
    1. Suscripción PDV/Banco
    2. Configuración dispositivo (Pinpad o POS)
    3. Configuración PDV en MServer
    4. Configuración Medio de Pago / Banco en MServer, por PDV
  - **Recurrentes EXCLUSIVO (2 conceptos)** - NO aparecen en setup:
    1. Suscripción Medio de Pago / Banco en MServer por PDV
    2. Hospedaje MServer
  - Campos Cajas y Bancos editables por fila para ajustes excepcionales
  - Items adicionales (de bancos) pueden tener ambos costos
- [x] **Dashboard Mejorado (Diciembre 2025):**
  - Agregados indicadores: Medios de Pago, Hardware
  - 6 tarjetas de estadísticas en total
  - Validación robusta de datos (Array.isArray)

## Backlog / Tareas Futuras
- [ ] Módulo de reportes estadísticos
- [ ] Consultas avanzadas de cotizaciones
- [ ] Exportación masiva a Excel
- [ ] Notificaciones por email
- [ ] Recuperación de contraseña
- [ ] Refactorización del backend (dividir server.py monolítico)

---
**Última actualización:** Diciembre 2025
**Estado:** MVP Completo - Probado con filtrado de compatibilidad
