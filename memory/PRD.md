# PRD - Cotizador Merchant Server

## Problema Original
Aplicación de cotizaciones para una plataforma de pagos (Mega Soft). Sistema full-stack para gestión completa de cotizaciones con múltiples módulos CRUD, generación de PDF, sistema multi-sede, y gestión de usuarios.

## Stack Tecnológico
- **Backend:** FastAPI + MongoDB (Motor async)
- **Frontend:** React + Shadcn/UI + Tailwind CSS
- **PDF:** reportlab + PyPDF2
- **Auth:** JWT sessions con hash de contraseñas

## Módulos Implementados

### Completados
- [x] Autenticación JWT (login/registro con sedes)
- [x] CRUD completo (Clientes CRM, Bancos, Bienes/Servicios, Integradores, Medios Pago, Hardware)
- [x] Gestión de Cotizaciones con ciclo de vida completo
- [x] Generador de PDF dinámico con reportlab
- [x] Importación/Exportación Excel con plantillas descargables
- [x] Sistema Multi-Sede (TBP/LCH)
- [x] Gestión de Usuarios Pro
- [x] Módulo Anexos con 5 categorías
- [x] Flujo de Estados Basado en Evidencias
- [x] Módulo Clientes & CRM Evolucionado (multi-sede, contactos, bitácora, alertas)
- [x] **Nomenclatura COT-AAAA-MM-NNN-SEDE** (25/Feb/2026)
  - Contador atómico independiente por sede y mes
  - TBP y LCH con secuencias separadas
  - Archivos en Anexos usan nomenclatura: COT-..._OrdenCompra.pdf, _Factura.pdf, _Pago_1.pdf

## Pendiente / Backlog

### P1 - Alta Prioridad
- [ ] Verificar funcionalidad "Guardar con PDF" end-to-end
- [ ] Verificación de email (requiere API Key Resend)
- [ ] Recuperación de contraseña (requiere API Key Resend)
- [ ] **Refactorización backend/server.py** (CRÍTICO - 6000+ líneas)

### P2 - Media Prioridad
- [ ] Refactorización frontend
- [ ] Módulo de Reportes avanzados

## Credenciales de Prueba
- TBP: test_anexos@test.com / Test1234! (admin)
- LCH: test_lch@test.com / Test1234!

## Test Reports
- iteration_42: Anexos module (15/15)
- iteration_43: Workflow state transitions (14/14)
- iteration_44: CRM evolution (11/11)
- iteration_45: Client import (13/13)
- iteration_46: Quote naming convention (14/14)
