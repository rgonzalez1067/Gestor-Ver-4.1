# Cotizador Merchant Server - PRD

## Descripción General
Sistema integral de cotizaciones para plataformas de medios de pago.

## Estado Actual: MVP Operativo ✅

---

## NUEVA FUNCIONALIDAD - 23 Febrero 2026

### 1. GENERADOR DE PDF CON FLUJO DINÁMICO (v3)
Sistema de generación de cotizaciones con estructura comercial y fiscal optimizada:

**Estructura del Documento:**
| Página | Sección | Contenido |
|--------|---------|-----------|
| 1 | Portada | Título + Subtítulo (negrita) separados, Info cliente, Nro. cotización |
| 2 | Cuerpo | Carta presentación, Resumen Ejecutivo (Cliente/Cajas/Dirección), Tabla Bancos/Productos/Cajas |
| 3+ | Costos | Setup y Recurrentes con desglose fiscal: Subtotal → IVA 16% → Total |
| 3+ | Resumen Inversión | Totales con descuento (antes de IVA) |
| Última | Términos | Vigencia 5 días hábiles, Tiempos sujetos a bancos |

**Ajustes Fiscales:**
- Cada tabla incluye: **Subtotal, IVA (16%), Total**
- Descuento se resta del subtotal ANTES de calcular IVA
- Ejemplo: Si Setup=$1000, Descuento=$200 → Subtotal=$800 → IVA=$128 → Total=$928

**Cambios vs v2:**
- Eliminado: "Matriz de Distribución" 
- Añadido: Tabla "Bancos/Productos/Cajas"
- Vigencia: 5 días hábiles (antes 30)
- Términos: Párrafo sobre tiempos bancarios

**Verificación (iteration_40.json):** 100% Backend ✅ (26/26 tests)

---

### 2. ACTUALIZACIÓN UI BOTÓN DE COTIZACIÓN
- **Nombre anterior**: "Nueva Cotización de Equipos"
- **Nombre nuevo**: "Nueva Cotización: Equipos, Accesorios y Reparaciones"

### 2. NUEVO TIPO DE COTIZACIÓN: REPARACIONES
Al seleccionar "Reparaciones" en el wizard, se habilitan campos adicionales:
- Descripción de la falla (textarea, obligatorio)
- Número de serie del equipo a reparar (input)
- Fecha estimada de entrega (date picker)

### 3. CATEGORÍAS DE FILTRO ACTUALIZADAS
Nueva estructura jerárquica según anexo del usuario:
| Categoría | Descripción |
|-----------|-------------|
| Implementaciones | Servicios de instalación, configuración o puesta en marcha |
| Equipos | Venta de hardware principal (Laptops, Servidores, etc.) |
| Accesorios | Periféricos y complementos (Mouses, cables, teclados) |
| Reparaciones | Mano de obra técnica y servicios de mantenimiento correctivo |

### 4. IMPORTACIÓN/EXPORTACIÓN DE DATOS
Módulo "Bienes y Servicios" ahora incluye:
- **Botón Importar**: Abre modal para cargar archivos Excel/CSV
- **Botón Exportar**: Menú desplegable con opciones:
  - Exportar a Excel (.xlsx)
  - Exportar a PDF

**Endpoints Backend:**
| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/hardware/import` | POST | Importa datos desde Excel/CSV |
| `/api/hardware/export/excel` | GET | Exporta a Excel |
| `/api/hardware/export/pdf` | GET | Exporta a PDF |
| `/api/hardware/template` | GET | Descarga plantilla de ejemplo |

### Verificación (iteration_37.json): 100% Backend y Frontend ✅

---

## SISTEMA DE AUTENTICACIÓN - 22 Febrero 2026

### Implementación Completada:
Nuevo sistema de autenticación con email/contraseña reemplazando Google OAuth.

### Funcionalidades:
1. **Pantalla Unificada** (`/login`): Pestañas para alternar entre Login y Registro
2. **Registro de Usuario**: Nombre, Apellido, Cédula, Email, Contraseña
3. **Validaciones**: Nombre (solo letras), Cédula (6-15 dígitos), Contraseña (mín 8 chars)
4. **Icono de Ojo**: Toggle para mostrar/ocultar contraseña
5. **Primer Usuario = Admin**: El primer usuario registrado obtiene rol admin automáticamente
6. **Panel de Admin** (`/admin/users`): Gestión de usuarios y matriz de permisos

### Módulos con Permisos:
| Módulo | Permisos |
|--------|----------|
| Cotizaciones | Ninguno / Leer / Editar |
| Clientes | Ninguno / Leer / Editar |
| Bancos | Ninguno / Leer / Editar |
| Medios de Pago | Ninguno / Leer / Editar |
| Bienes y Servicios | Ninguno / Leer / Editar |
| Integradores | Ninguno / Leer / Editar |
| Configuración | Ninguno / Leer / Editar |

### Pendientes:
- ⏳ Verificación de email al registrarse (requiere Resend API)
- ⏳ Recuperación de contraseña (requiere Resend API)

### Verificación (iteration_36.json): 100% Backend y Frontend ✅

---

## AJUSTE LÓGICA MODIFICAR COTIZACIÓN - 22 Febrero 2026

### Problema Reportado:
1. Ciertos conceptos heredaban número de bancos incorrecto (debían mostrar "N/A")
2. Al modificar cotización, los conceptos NO preservaban su cantidad_bancos original de BD
3. "Derecho de uso... / Banco" mostraba N/A cuando debía mostrar número

### Conceptos que muestran N/A en Bancos (lockBancos) - SOLO ESTOS 5:
- Derecho de uso de plataforma MServer por PDV (SIN "/ Banco")
- Configuración dispositivo (Pinpad o POS)
- Configuración PDV en MServer
- Comunicación Backend (SSL Público o VPN, APN, etc.)
- Procesamiento (HSM, Server, DC, etc.)

**NOTA**: "Derecho de uso de plataforma MServer por PDV / Banco" SÍ muestra número de bancos

### Reglas de Propagación:
| Campo | Comportamiento |
|-------|----------------|
| **CAJAS** | Se propaga a TODOS los items sin excepción |
| **BANCOS** | Respeta: lockBancos, isAutoLinked, isFromDB |

### Solución Implementada:
1. `shouldLockBancos()` excluye nombres con "/ banco"
2. useEffect: CAJAS siempre se propaga, BANCOS respeta flags
3. `isFromDB: true` - Items de BD preservan BANCOS pero reciben CAJAS

### Verificación (iteration_35.json) - 100% ✅

---

## CORRECCIÓN DESCARGA PDF - 22 Febrero 2026

### Problema Reportado:
- La descarga de PDF mostraba "PDF descargado correctamente" pero el archivo no llegaba a la carpeta de descargas
- Afectaba todos los módulos (Cotizaciones, Clientes, Bancos)

### Causa Raíz:
- El código anterior no esperaba a que el elemento `<a>` estuviera en el DOM antes de disparar el click
- El timeout de limpieza era muy corto (1 segundo)

### Solución Implementada:
1. Reescrita la función `downloadPDF` en `Quotes.jsx` con:
   - Logging detallado con prefijo `[PDF Download]`
   - Control de toast con `toastId`
   - `await setTimeout(100ms)` antes del click
   - Timeout de 3 segundos antes de limpiar

### Verificación (iteration_30.json):
- ✅ Backend: 10/10 tests pasados
- ✅ Frontend: Descarga verificada con Playwright
- ✅ PDFs válidos (3020 bytes, header %PDF-1.4)
- ✅ Módulos verificados: Cotizaciones, Clientes, Bancos, Medios de Pago

---

## CORRECCIÓN CRÍTICA - 21 Diciembre 2025

### Problema Reportado:
- Las funciones de Aprobación y Eliminación no ejecutaban los procesos lógicos esperados
- Se requería modal de confirmación (pop-up) en lugar de eliminación directa

### Solución Implementada:
1. **Modales AlertDialog**: Reemplazados todos los `window.confirm` por componentes `AlertDialog` de Shadcn
2. **Aprobar**: Muestra modal con mensaje sobre envío de email usando plantilla "Cotización Aprobada"
3. **Eliminar**: Muestra modal con advertencia "Esta acción no se puede deshacer" en rojo
4. **Cobrar**: Muestra modal confirmando cambio de estado a "Pagada"

### Verificación (iteration_28.json):
- ✅ Modal de Aprobar funcionando
- ✅ Modal de Eliminar funcionando  
- ✅ Modal de Cobrar funcionando
- ✅ APIs backend funcionando (approve, collect, delete)
- ✅ Flujo de estados completo verificado
- Backend: 100% ✅
- Frontend: 100% ✅

---

## Flujo de Estados (Completo)

```
Borrador → Enviada → Aprobada (email admin) → 
Facturada (PDF req.) → Pagada → Enviada a Imple (email implementación)
```

| Acción | Estado Requerido | Estado Resultante | Notificación |
|--------|------------------|-------------------|--------------|
| Enviar al Cliente | Borrador | Enviada | Email cliente |
| Aprobar | Enviada | Aprobada | Email admin |
| Facturar | Aprobada | Facturada | - |
| Cobrar | Facturada | Pagada | Email almacén (equipos) |
| Enviar a Imple | Pagada | Enviada a Imple | Email implementación |

---

## Modales de Confirmación Estandarizados (iteration_29.json)

Todos los módulos CRUD ahora tienen AlertDialog de confirmación para eliminación:

| Módulo | Dialog Title | Advertencia | Validación Backend |
|--------|-------------|-------------|-------------------|
| Cotizaciones | ¿Eliminar Cotización? | "Esta acción no se puede deshacer" | N/A |
| Clientes | ¿Eliminar Cliente? | "Podría afectar cotizaciones, facturas" | Verifica cotizaciones vinculadas |
| Bancos | ¿Eliminar Banco? | "Podría afectar medios de pago, cotizaciones" | Verifica cotizaciones vinculadas |
| Medios de Pago | ¿Eliminar Medio de Pago? | "Podría afectar bancos, cotizaciones" | Verifica cotizaciones y bancos |
| Dispositivos | ¿Eliminar Dispositivo? | "Podría afectar cotizaciones de equipos" | Verifica cotizaciones vinculadas |
| Integradores | ¿Eliminar Integrador? | "Podría afectar cotizaciones, configuraciones" | Verifica cotizaciones vinculadas |

**Comportamiento estándar:**
1. Click en botón eliminar → Abre AlertDialog con advertencia
2. Click "Cancelar" → Cierra el dialog sin acción
3. Click "Eliminar" → Ejecuta DELETE API → Toast de éxito/error
4. Si hay datos vinculados → Backend retorna HTTP 400 con mensaje descriptivo

---

## Backlog

### P1 - Alta Prioridad
- [ ] Verificación de email al registrarse (bloqueado - requiere Resend API key)
- [ ] Recuperación de contraseña (bloqueado - requiere Resend API key)

### P2 - Media Prioridad
- [ ] Contadores del Dashboard (Issue recurrente - no abordado aún)
- [ ] Refactorización del backend (dividir `server.py` en módulos)
- [ ] Refactorización del frontend (descomponer `Quotes.jsx`)
- [ ] Módulo de Reportes avanzados
- [ ] Importación/Exportación en otros módulos (Clientes, Bancos, etc.)

---

## Testing Status
- Backend: 100% ✅
- Frontend: 100% ✅
- Test reports: 
  - `/app/test_reports/iteration_37.json` (Categorías y Import/Export)
  - `/app/test_reports/iteration_40.json` (PDF v3 con ajustes estructurales)

---
**Última actualización:** 23 Febrero 2026
**Estado:** MVP Operativo - Generador de PDF con Desglose Fiscal v3 ✅
