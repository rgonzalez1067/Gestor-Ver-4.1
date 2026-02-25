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
/app/frontend/src/
  ├── pages/
  │   ├── Dashboard.jsx      → Dashboard con widget de Alertas de Seguimiento
  │   ├── Clients.jsx        → CRM completo: multi-sede, contactos, bitácora
  │   ├── Quotes.jsx         → Cotizaciones con anexos y workflow de estados
  │   └── ...
  ├── components/
  │   ├── AnexosModal.jsx    → Modal de anexos con 5 categorías
  │   ├── WorkflowUploadModal.jsx → Modal de carga obligatoria para transiciones
  │   └── ...
  └── utils/api.js
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
- [x] **Flujo de Estados Basado en Evidencias** (25/Feb/2026)
- [x] **Módulo Clientes & CRM Evolucionado** (25/Feb/2026) - 4 bloques

### CRM Evolucionado (25/Feb/2026)
**Bloque 1: Estructura Multi-Sede**
- RIF + Sucursal como llave compuesta única
- Permite mismo RIF con diferente sucursal
- Tabla de clientes muestra columna Sucursal

**Bloque 2: Matriz de Contactos Dinámica**
- Contactos ilimitados por cliente (array dinámico)
- 5 roles: Administrativo, Financiero, Técnico, Cuentas por Pagar, Operativo
- Formulario con agregar/eliminar contactos

**Bloque 3: Bitácora de Eventos y Seguimiento**
- Colección `client_logs` en MongoDB (tipo log, no editable)
- Campos: fecha_contacto, detalle, acción, fecha_seguimiento
- Toggle de completado, ordenamiento por fecha

**Bloque 4: Dashboard de Alertas**
- Widget con semáforo de prioridad
- 🔴 Rojo: Seguimientos atrasados
- 🟡 Amarillo: Programados para hoy
- 🟢 Verde: Próximos 7 días
- Click en alerta → navega a ficha del cliente con bitácora abierta

**Testing:** 11/11 backend, 100% frontend (iteration_44)

## Pendiente / Backlog

### P1 - Alta Prioridad
- [ ] Bug: Contadores del Dashboard no suman correctamente (parcialmente resuelto con rewrite)
- [ ] Verificar funcionalidad "Guardar con PDF" end-to-end
- [ ] Verificación de email al registrarse (requiere API Key Resend)
- [ ] Recuperación de contraseña (requiere API Key Resend)
- [ ] **Refactorización backend/server.py** (CRÍTICO - 6000+ líneas)

### P2 - Media Prioridad
- [ ] Refactorización frontend (Settings.jsx, Users.jsx, Quotes.jsx)
- [ ] Módulo de Reportes avanzados

## Credenciales de Prueba
- Email: test_anexos@test.com / Password: Test1234! (admin)
- La base de datos MongoDB es volátil en el entorno de preview

## Integraciones 3rd Party
- Resend: Pendiente de API Key
- reportlab, bcrypt, openpyxl, pandas
- Shadcn/UI + Radix UI
