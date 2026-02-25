# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Sistema full-stack para gestión completa de cotizaciones con múltiples módulos CRUD, generación de PDF, sistema multi-sede, y gestión de usuarios.

## Stack Tecnológico
- **Backend:** FastAPI + MongoDB (Motor async)
- **Frontend:** React + Shadcn/UI + Tailwind CSS
- **PDF:** reportlab + PyPDF2
- **Auth:** JWT sessions con hash de contraseñas

## Arquitectura
```
/app/backend/server.py   → Monolito FastAPI (REQUIERE REFACTORIZACIÓN)
/app/frontend/src/        → React SPA
  ├── pages/              → Páginas principales
  ├── components/         → Componentes reutilizables
  └── utils/api.js        → Cliente Axios
```

## Módulos Implementados

### Completados
- [x] Autenticación JWT (login/registro con sedes)
- [x] CRUD Clientes
- [x] CRUD Bancos
- [x] CRUD Bienes y Servicios
- [x] CRUD Integradores
- [x] CRUD Medios de Pago
- [x] CRUD Dispositivos/Hardware
- [x] Gestión de Cotizaciones (implementación, equipos, reparaciones)
- [x] Ciclo de vida de cotizaciones (Borrador→Enviada→Aprobada→Facturada→Pagada→Entregada/Imple)
- [x] Generador de PDF dinámico con reportlab
- [x] Importación/Exportación Excel
- [x] Sistema Multi-Sede (TBP/LCH)
- [x] Gestión de Usuarios Pro (admin panel)
- [x] Tasa de Cambio
- [x] Configuración por sede
- [x] **Módulo Anexos** (25/Feb/2026) - Gestión de documentos por cotización con 4 categorías

### Módulo Anexos (Completado 25/Feb/2026)
- Backend: 4 endpoints (GET, POST, DELETE, DOWNLOAD) para gestión de archivos
- Frontend: Modal `AnexosModal.jsx` con categorías: Cotización Original, Orden de Compra, Factura, Otros
- Auto-guardado del PDF generado como "Cotización Original" al crear cotización
- Botón "Anexos" reemplaza botón "PDF" en tabla de cotizaciones
- "Descargar PDF" movido al menú dropdown de acciones
- Testing: 15/15 backend tests passed, frontend UI tests passed

## Pendiente / Backlog

### P1 - Alta Prioridad
- [ ] Verificar funcionalidad "Guardar con PDF" end-to-end
- [ ] Bug: Contadores del Dashboard no suman correctamente (recurrente)
- [ ] Verificación de email al registrarse (requiere API Key Resend)
- [ ] Recuperación de contraseña (requiere API Key Resend)
- [ ] **Refactorización backend/server.py** (CRÍTICO - 5800+ líneas)

### P2 - Media Prioridad
- [ ] Refactorización frontend (Settings.jsx, Users.jsx, Quotes.jsx)
- [ ] Módulo de Reportes avanzados

## Credenciales de Prueba
- Email: test_anexos@test.com / Password: Test1234! (admin)
- La base de datos MongoDB es volátil en el entorno de preview

## Integraciones 3rd Party
- Resend: Pendiente de configuración de API Key
- reportlab: Generación de PDF
- Shadcn/UI + Radix UI: Componentes React
- bcrypt: Hashing de contraseñas
- openpyxl/pandas: Manejo de Excel
