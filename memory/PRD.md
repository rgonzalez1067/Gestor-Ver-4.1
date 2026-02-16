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
- [x] CRUD Bancos (Venezuela, EE.UU., Fintechs)
- [x] CRUD Hardware
- [x] CRUD Servicios (4 campos de precio: Convencional y Outsourcing)
- [x] CRUD Cotizaciones con cálculo automático
- [x] Tasa de cambio BCV (consulta y actualización)
- [x] Endpoint para poblar bancos (/api/banks/seed)
- [x] Upload/descarga/eliminación de logo de empresa (GET público para login)
- [x] Generación de PDF para cotizaciones

### Frontend (React)
- [x] Login con Google OAuth + opción para crear cuenta
- [x] Logo de empresa visible en pantalla de Login
- [x] Dashboard con estadísticas y últimas cotizaciones
- [x] Gestión de Clientes con campo Segmento
- [x] Gestión de Bancos (grid de tarjetas)
- [x] Gestión de Hardware
- [x] Gestión de Servicios (tablas por categoría con 4 precios)
- [x] Wizard de creación de cotizaciones (4 pasos)
- [x] Configuración (upload logo + seed bancos)
- [x] Tasa de cambio (visualización y actualización)
- [x] Loading screens con fondo blanco y texto negro
- [x] Todos los fondos de pantalla en blanco
- [x] Branding: "Cotizador Merchant Server"

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
