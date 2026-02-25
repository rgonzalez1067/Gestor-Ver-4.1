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
  │   ├── AnexosModal.jsx → Modal de anexos con 5 categorías
  │   ├── WorkflowUploadModal.jsx → Modal de carga obligatoria para transiciones de estado
  │   └── ...
  └── utils/api.js        → Cliente Axios
```

## Módulos Implementados

### Completados
- [x] Autenticación JWT (login/registro con sedes)
- [x] CRUD Clientes, Bancos, Bienes y Servicios, Integradores, Medios de Pago, Hardware
- [x] Gestión de Cotizaciones (implementación, equipos, reparaciones)
- [x] Ciclo de vida de cotizaciones con validación de documentos
- [x] Generador de PDF dinámico con reportlab
- [x] Importación/Exportación Excel
- [x] Sistema Multi-Sede (TBP/LCH)
- [x] Gestión de Usuarios Pro (admin panel)
- [x] Tasa de Cambio y Configuración por sede
- [x] **Módulo Anexos** (25/Feb/2026) - 5 categorías de documentos
- [x] **Flujo de Estados Basado en Evidencias** (25/Feb/2026) - Validación obligatoria de documentos

### Flujo de Estados Basado en Evidencias (25/Feb/2026)
**Transiciones de estado con documentos obligatorios:**
| Estado | Documento Requerido | Categoría | Cantidad | Obligatorio |
|--------|-------------------|-----------|----------|-------------|
| Al crear | PDF cotización | Cotización | 1 | Sí |
| Aprobado | Orden de Compra | Orden de Compra | 1 | Sí |
| Facturado | Factura | Factura | 1 | Sí |
| Pagado | Comprobante(s) de Pago | Pagos | Múltiple | Sí |
| Cualquiera | Docs complementarios | Otros | Múltiple | No |

**Componentes:**
- `WorkflowUploadModal.jsx`: Modal genérico para carga obligatoria antes de transiciones
- `AnexosModal.jsx`: Panel de visualización de todos los documentos por categoría
- Backend: Validaciones 422 en endpoints approve/invoice/collect

**Testing:** 14/14 backend, 100% frontend (iteration_43)

## Pendiente / Backlog

### P1 - Alta Prioridad
- [ ] Bug: Contadores del Dashboard no suman correctamente (recurrente)
- [ ] Verificar funcionalidad "Guardar con PDF" end-to-end
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
- bcrypt, openpyxl, pandas
