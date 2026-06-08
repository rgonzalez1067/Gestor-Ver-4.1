# CHANGELOG — MegaNexus

## 2026-06-08 — Ajustes Proyectos Directos + Mapeo Tipo de Proyecto (Iter31)

### 1. Mapeo "Tipo de Proyecto" en Ficha Técnica (PDF) — P0 ✅
- `backend/services/implementation_pdf.py` (~141-156): nuevo mapeo determinístico por `quote_type.upper()`.
  Valores SEPARADOS por tipo (ya NO existe "VPOS / MPOS" combinado):
  - VPOS → VPOS · MPOS/FAST_TRACK → MPOS · GATEWAY → Payment Gateway
  - LINK_PAGO/LINK → Link de Pago · VPOS_MPOS (legacy) → VPOS
- La UI (`ProjectDetail.jsx` ~979) ya mapeaba correcto; solo el PDF tenía el combinado.
- Test: `/app/backend/tests/test_iter31_implementation_pdf_type_mapping.py` (8/8 PASS).

### 2. Modelo de Pinpad en carga de seriales (Proyectos Directos) — P0 ✅
- `DirectProjectCreation.jsx` `doSubmit`: `payload.pinpad_serials` mapea cada serial
  heredando `form.pinpad_model` cuando la fila no trae modelo. Cubre las 3 vías
  (Excel, lote TextArea, manual). La Matriz de Seriales de la Ficha Técnica ya
  muestra `pp.modelo` (ProjectDetail ~1237) y el PDF (`implementation_pdf.py` ~219).

### 3. Reel de Distribución — UX tipo Cotizador (multiselect por banco) — P1 ✅
- `DirectProjectCreation.jsx`: nuevo panel `dp-reel-selector` (Select de Banco +
  checkboxes de productos disponibles filtrados por tipo de proyecto + botón
  "Agregar al Reel" `dp-reel-add-selected`). Permite agregar múltiples productos a la vez.
  Merge automático de duplicados banco+producto (suma quantity).
- `boxes_grid` ahora inicia vacío (`[]`); grilla muestra filas Banco/Producto como texto,
  Cantidad editable y botón eliminar. Estructura enviada al backend `boxes_grid` intacta.
- Removido `productsForBank` y `addBoxRow` (sin uso). Lint limpio.

### Estado
- Testing agent Iter31: backend 100% (8/8 pytest), frontend Reel 100% (6/6). Sin regresiones.
- Warning de hydration en /direct-projects es preexistente (wrapper `data-ve-dynamic` de plataforma).

### Deuda técnica pendiente
- `DirectProjectCreation.jsx` > 1200 líneas → considerar split (HardwareCard, ReelCard, TechConfigCard).
- `QuoteWizardDialog.jsx` > 2300 líneas → fragmentar por fases.
