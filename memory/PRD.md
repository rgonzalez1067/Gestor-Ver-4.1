# Cotizador Merchant Server - PRD

## Descripción General
Sistema integral de cotizaciones para plataformas de medios de pago.

## Estado Actual: MVP Operativo ✅

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

### P2 - Media Prioridad
- [ ] Contadores del Dashboard (Issue recurrente - no abordado aún)
- [ ] Refactorización del backend (dividir `server.py` en módulos)
- [ ] Refactorización del frontend (descomponer `Quotes.jsx`)
- [ ] Módulo de Reportes
- [ ] Recuperación de contraseña

---

## Testing Status
- Backend: 100% ✅
- Frontend: 100% ✅
- Test report: `/app/test_reports/iteration_27.json`

---
**Última actualización:** 20 Diciembre 2025
**Estado:** MVP Operativo - Flujo de Estados y Acciones del Menú Verificados ✅
