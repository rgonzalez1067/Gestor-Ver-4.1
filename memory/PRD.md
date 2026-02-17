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
- [x] CRUD Bancos (Venezuela, EE.UU., Fintechs) con productos y disponibilidad por componente
- [x] Importación/Exportación de Bancos (CSV/PDF)
- [x] CRUD Hardware
- [x] CRUD Medios de Pago con campo `application_type`:
  - Solo Setup: gastos de implementación inicial
  - Solo Costos Recurrentes: cargos mensuales/periódicos  
  - Ambos: aplica a ambos tipos de cotización
- [x] Importación/Exportación de Medios de Pago (CSV/PDF)
- [x] CRUD Cotizaciones con tipo (VPOS/GATEWAY/MPOS/LINK)
- [x] Flujo especial VPOS: Cantidad de Cajas → Cliente → Medios de Pago con banco
- [x] Tasa de cambio BCV (consulta y actualización)
- [x] Upload/descarga/eliminación de logo de empresa
- [x] Generación de PDF para cotizaciones

### Frontend (React)
- [x] Login con Google OAuth + opción para crear cuenta
- [x] Logo de empresa visible en pantalla de Login
- [x] Colores de marca (verde #1B7D4E y azul #00447C)
- [x] Gestión de Medios de Pago / Servicios con:
  - Campo "Tipo de Aplicación" obligatorio antes de ingresar costos
  - Campos de costo condicionales según tipo seleccionado
  - Badge visual indicando el tipo de aplicación en la tabla
- [x] Wizard de cotizaciones con flujo especial VPOS
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

### Service
```json
{
  "service_id": "string",
  "category": "string",
  "name": "string",
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
- `GET/POST/PUT/DELETE /api/services` - CRUD Servicios
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
- Backend: 33/33 tests pasados (100%)
- Frontend: Login, OAuth, rutas protegidas, responsive funcionando

## Backlog / Tareas Futuras
- [ ] Módulo de reportes estadísticos
- [ ] Consultas avanzadas de cotizaciones
- [ ] Exportación masiva a Excel
- [ ] Notificaciones por email

---
**Última actualización:** Diciembre 2025
**Estado:** MVP Completo - Probado
