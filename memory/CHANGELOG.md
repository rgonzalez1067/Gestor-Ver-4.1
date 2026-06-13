# CHANGELOG — MegaNexus

## 2026-06-13 — Nueva función: carga vía Excel de la distribución Multi-RIF (Tiendas/Sucursales)

- **Backend (`quotes.py`)**: 2 endpoints nuevos:
  - `GET /quotes/multirif/excel-template` → plantilla .xlsx (hoja "Distribucion" + hoja "Instrucciones") con columnas `RIF Cliente | Nombre Sucursal | Cajas`.
  - `POST /quotes/multirif/parse-excel` (multipart `file` + `global_boxes`) → parsea, valida y devuelve `{ok, distribution, errors, warnings, summary}` SIN persistir. Agrupa por RIF (busca el Cliente por RIF), calcula cajas del RIF = suma de sus sucursales.
- **Reporte de errores documentado (fila por fila)**: RIF/sucursal vacíos, Cajas no numérica o ≤0, RIF sin Cliente registrado, sucursal duplicada en el mismo RIF, columnas faltantes / archivo ilegible. Advertencia (no bloquea) si total de cajas ≠ Cajas Globales del lote.
- **Frontend (`MultiRifDistributionPanel.jsx`)**: barra con "Plantilla" (descarga .xlsx) y "Cargar Excel" (input oculto). Al cargar sin errores, **reemplaza** la distribución (`onChange`); muestra `ImportReport` con éxito/advertencias/errores (con número de fila) y resumen (RIFs/sucursales/cajas). Disponible en estado colapsado y expandido.
- **Validado**: curl (plantilla 2 hojas, parseo válido, 4 tipos de error con fila, advertencia por mismatch, resumen) + testing agent (iteration_81, 5/5 escenarios en el wizard VPOS Multi-RIF).


## 2026-06-13 — Fix de rendimiento: latencia al capturar tiendas en proyectos Multi-RIF

- **Causa raíz**: los inputs de la matriz por tienda (`StoreBankSection.jsx`) disparaban la actualización en **cada tecla** (`onChange`), y cada edición ejecutaba un `fetchProject()` que **recargaba TODO el proyecto** (documento grande en Multi-RIF) + re-render completo del árbol. La cascada hacía 4 PUT + 1 GET por dígito.
- **Solución (frontend)**:
  - `StoreBankSection.jsx`: nuevo `QtyInput` con estado local → la escritura es instantánea y se **persiste solo en blur/Enter** (no por tecla).
  - `ProjectDetail.jsx`: `patchStoreMatrixLocal` aplica una **actualización local optimista** (parchea la celda + rollup) en lugar de `fetchProject()` en los 4 handlers de tienda (quantity, cascade, fill, toggle). En error se hace `fetchProject()` para resync.
- **Solución (backend `projects.py` · `update_store_matrix_phase`)**: el PUT ahora retorna `expected/processed/completed` + `rollup_progress`, para que el frontend actualice sin recargar.
- **Validado (iteration_80)**: 100% — escritura fluida, persistencia tras F5, cascada propaga a las 4 fases, botón "T" completa, avance global se actualiza sin recargar. Sin pérdida de datos ni parpadeo.


## 2026-06-13 — Fix: Reporte de Carga (PDF) de Proyectos no contemplaba Multi-RIF

- **Causa (backend `projects.py` · `projects_workload_pdf`)**: los proyectos `quote_type='VPOS_MULTIRIF'` mostraban Cajas "—" (el gate era `qt in ("VPOS","MPOS")`), no sumaban a la carga del implementador, no tenían badge/etiqueta de tipo y no aparecían en la agrupación/filtro por Tipo. Además, en Multi-RIF `cantidad_cajas` viene vacío (el total vive en `rifs`/`stores`).
- **Solución**: nuevos helpers `_counts_cajas` (incluye VPOS_MULTIRIF) y `_project_total_cajas` (cae a `box_count` y a la suma de `rifs.box_count`). Se mapeó VPOS_MULTIRIF en `_TYPE_LABEL`("VPOS-MR")/`_TYPE_FULL_LABEL`("VPOS Multi-RIF")/`_TYPE_BADGE_CSS` y se agregó al `type_order`. El PVV se calcula con el total de cajas correcto. La línea "Filtros aplicados: Tipo" usa la etiqueta completa.
- **Frontend (`WorkloadReportFiltersModal.jsx`)**: el filtro "Tipo de Proyecto" ahora incluye "VPOS Multi-RIF" (chip `filter-type-VPOS_MULTIRIF`) con etiquetas amigables.
- **Validado (curl/PDF)**: prj_e586608e3579 ahora aparece con Cajas=28, PVV=168, badge VPOS-MR; agrupación por Implementador y por Tipo correctas; filtro `quote_type=VPOS_MULTIRIF` OK.


## 2026-06-13 — Mejora: desplegable de usuarios To/CC agrupado por equipo

- **Frontend (`InternalEmailInput.jsx`)**: el desplegable de usuarios internos ahora agrupa por equipo con encabezados sticky y conteo: **Dirección / Ventas / Implementación / Otros** (`TEAM_SECTIONS` + useMemo `grouped`). Solo se muestran las secciones no vacías; al filtrar por texto se re-agrupa. testids: `${testId}-group-<key>`.
- **Validado (iteration_79)**: 100% — TO/CC con headers Dirección(2)/Ventas(6)/Implementación(11), sin 'Otros' (profile strategic), filtro 'gonz' re-agrupa, selección OK.

## 2026-06-13 — Fix: lista de emails (To/CC) en Notificaciones de Proyecto venía corta

- **Causa raíz (frontend `InternalEmailInput.jsx`)**: el dropdown de usuarios internos limitaba a **8** resultados (`.slice(0, 8)`), por lo que aunque el backend devolvía 19 usuarios estratégicos, solo se mostraban 8. Se eliminó el cap: con query vacío muestra TODA la lista y al escribir muestra TODAS las coincidencias (contenedor `max-h-52` con scroll).
- **Backend (`entity_communications.py` · `_is_strategic_profile`)**: filtro `profile=strategic` ahora más robusto e inclusivo — TODO el Equipo de Ventas (cualquier subárea, `dept` empieza por "ventas"), TODA Implementación (cualquier cargo) y Dirección/Directores. Antes excluía Implementación con cargos fuera de {Implementador, Coordinador, Gerente}.
- **Validado**: pytest `tests/test_internal_emails_filter.py` 4/4 + testing agent (iteration_78): TO=19, CC=19, scroll real, filtro 'gonz'=3 coincidencias, selección + chip OK.


## 2026-06-13 — Variable {Matriz_Avance_Proyecto} + Pegado de imágenes en el editor enriquecido

### Variable dinámica {Matriz_Avance_Proyecto}
- **Backend (`project_template_vars.py`)**: nuevos `_phase_cell_value`, `_avance_phase_table`, `_avance_store_block`, `_build_avance_matrix_html`. Registrada en el dict de variables y en el catálogo (`projects.py`). Reglas por celda: Cumplida → `100%` · En proceso → `% real` (processed/expected) · No iniciada → `—`. Jerarquía: Estándar = Banco→Producto→Fases; Multitienda/Multi-RIF antepone Tienda/Sucursal (en Multi-RIF agrupa por RIF). Cabecera con KPI **Avance Global** = `rollup_progress.global_progress` (igual al dashboard). Excluida de los mapas simples de variables (es HTML grande) pero presente en el catálogo.
- **Frontend**: agregada a `templateVariables.js` (+ preview HTML), `EmailTemplatesEditor.jsx` (4 listas de proyecto), `projectConstants.js` ALL_TOKENS (chip clickeable en notificaciones) y `RichTextEditor.jsx` DEFAULT_EXAMPLE_VALUES (Vista Previa de toolbar).
- **Validado**: pytest `tests/test_matriz_avance_proyecto.py` (3/3) + curl `preview-adhoc-email` sobre prj_e586608e3579 (KPI 23%, bloques por RIF/Sucursal, celdas 100%/—) + testing agent (render correcto en Vista Previa del modal).

### Pegado de imágenes (Ctrl+V / drag&drop / botón) en RichTextEditor
- **Frontend (`RichTextEditor.jsx`)**: extensión TipTap `Image`; props `enableImagePaste`(default true) + `imageUploadUrl`(`/projects/upload-image`); `handlePaste`/`handleDrop` capturan el Blob, lo suben e insertan `<img>` con URL absoluta en el cursor; botón de imagen en la toolbar (`${testid}-image`) + input file (`${testid}-image-input`); toast de estado. Disponible en TODAS las plantillas (Notificaciones, Clientes, Cotizaciones, Integradores).
- **Backend (`projects.py` · `upload_image`)**: nueva compresión ligera con Pillow (`_compress_image`): reescala a máx 1600px y recomprime (JPEG q82 / WEBP q82 / PNG optimize; GIF intacto) para aligerar correos.
- **Validado**: curl upload (3000x2000 → ≤1600px, servido HTTP 200) + testing agent (inserción end-to-end 100%, `<img>` con src `/api/projects/images/...`).


## 2026-06-13 — Fix: Actualizaciones individuales por tienda bloqueadas en Multi-RIF ("Este proyecto no es multitienda")

- **Backend (`projects.py` · `update_store_matrix_phase`, línea ~1727)**: `PUT /projects/{id}/stores/{store_id}/matrix/phase` rechazaba `project_type != "multistore"` → "Este proyecto no es multitienda". Esto bloqueaba TODAS las ediciones por celda en el árbol Multi-RIF (cantidad, cascada, marcar fase, toggle), que usan ese mismo endpoint. Ahora acepta `("multistore", "multirif")`. El handler ya opera genéricamente sobre `stores` y recalcula rollup.
- **Permisos**: este endpoint no tenía restricción de rol (solo exige `client_notified`), por lo que admin/implementador puede editar a cualquier nivel. La matriz principal sigue siendo de solo lectura en la UI (locks) para multitienda/Multi-RIF, por diseño.
- **Validado (curl)**: PUT store matrix phase sobre prj_e586608e3579 (Marquez, Configurado, Tarjeta de Crédito/Débito 5/5) → HTTP 200 "Fase de tienda actualizada".

## 2026-06-13 — Fix: Actualización Masiva bloqueada en proyectos Multi-RIF ("Solo proyectos multitienda")

- **Backend (`projects.py` · `batch_update_multistore_matrix`, línea ~1831)**: la validación rechazaba todo proyecto con `project_type != "multistore"`, devolviendo "Solo proyectos multitienda" al aplicar en un proyecto `multirif` (aunque el botón/modal ya se mostraban tras el fix de Fase 5). Ahora acepta `("multistore", "multirif")`. El resto de la lógica (matriz por tienda, rollup, bitácora) es genérica y funciona igual.
- **Validado E2E (curl)**: POST batch-update sobre prj_e586608e3579 (RIF Brasero, fase Recibido, 6 medios, 2 tiendas) → HTTP 200 "Actualización masiva aplicada a 2 tienda(s)". Avance reflejado: Marquez/Centro 25% (1/4 fases), rollup global 12.5%.


## 2026-06-13 — VPOS Multi-RIF · % de avance por RIF (modal Actualización Masiva + árbol)

- **Modal "Actualización Masiva" (`BatchUpdateModal.jsx`)**: el Select de RIF ahora muestra un chip de % por opción (`batch-rif-pct-<rif_id>` y `batch-rif-pct-all`), una mini barra de avance del alcance seleccionado (`batch-rif-progress` / `batch-rif-progress-pct`) y un chip de % por cada tienda en la lista. Avance ponderado por cajas (mismo criterio que el backend/árbol).
- **Árbol Multi-RIF (`MultiRifTree.jsx`)**: cada nodo RIF añade un chip de % con colores semáforo (`multirif-rif-pct-<rif_id>`) junto a la barra existente.
- **Colores semáforo**: 0% rojo · <50% ámbar · ≥50% verde. Reutiliza `weightedProgress`/`calcStoreProgress`. Backend sin cambios.
- **Validado (iteration_76)**: 100% — chips y barra renderizan con valores 0-100 y color correcto; regresión de filtrado Fase 5 intacta (proyecto con matriz vacía → todo 0%/rojo, correcto).


## 2026-06-13 — VPOS Multi-RIF · Fase 4.5 (corrección de bypass) + Ficha Técnica + Fase 5 (filtro RIF en Actualización Masiva)

### Corrección del bypass agresivo (Enviar a Implementación)
- **Frontend (`Quotes.jsx` · `openMultistoreDialog`)**: se REVIRTIÓ el early-return que enviaba directo a implementación. Ahora para `VPOS_MULTIRIF`: abre el wizard, setea `is_multistore=true` + `projectTypeImpl='vpos_mpos'` y enruta a `multistorePhase='pinpad_question'`. Se omite ÚNICAMENTE el modal "¿Es Multitienda?" y se MANTIENEN obligatorios los pasos: Pinpads → Impresora Fiscal → Datos Consolidados (Servidor/Servi) → Confirmación de Implementador. El flujo no-Multi-RIF queda intacto (regresión validada).
- **Frontend (`QuoteModals.jsx` · fase `pinpad_question`)**: el botón "Atrás" cierra el wizard cuando la cotización es `VPOS_MULTIRIF` (es el primer paso), en vez de navegar a fases inexistentes ('collect'/'ask').
- **Validado (iteration_73)**: al "Enviar a Implementación" de un VPOS_MULTIRIF aparece la fase Pinpads (no envío directo). 3/3 tests críticos frontend ✓.

### Ficha Técnica PDF jerárquica Multi-RIF
- **Backend (`implementation_pdf.py`)**: nuevo helper `_build_multirif_table` + render de "DETALLE DE TIENDAS Y SUCURSALES (Multi-RIF)" (Cliente/RIF → Sucursales → Cajas + TOTAL GENERAL) en la sección de Distribución Logística cuando `quote.multirif_distribution` existe (en send-time el campo viene del quote; el formato coincide). Fallback a la tabla plana de sucursales para proyectos normales.
- **Backend (`projects.py` · `download_ficha_tecnica`)**: construye `multirif_distribution` desde `project.rifs` + `project.stores` (agrupando por `rif_id`).
- **Validado**: pytest `tests/test_ficha_multirif.py` (2/2) + curl live de `GET /projects/prj_e586608e3579/ficha-tecnica` → 3 RIFs (Brasero/Barako/Carbon), TOTAL GENERAL=28.

### Fase 5 — Filtro en cascada por RIF en "Actualización Masiva"
- **Frontend (`BatchUpdateModal.jsx`)**: nuevo Select de RIF (Fase → Banco → RIF → Tiendas). Opción "Todos los RIFs" vs RIF específico; al elegir un RIF, la lista "Tiendas a procesar" filtra por `store.rif_id`. Solo se muestra en proyectos Multi-RIF (`project.rifs.length>0`).
- **Frontend (`ProjectDetail.jsx`)**: estados `batchRif`, `handleBatchRifChange` (resetea selección de tiendas), `getBatchFilteredStores`, `toggleAllBatchStores` acotado a tiendas filtradas. **Fix de gating**: el botón "Actualización Masiva" ahora se muestra con `(isMultistore || isMultiRif)` (antes solo `isMultistore`, ocultaba el botón en proyectos `project_type='multirif'`). Backend sin cambios (recibe `store_ids` ya acotados).
- **Validado (iteration_74 detectó gating oculto → corregido → iteration_75)**: 100% del flujo Fase 5 (botón visible, modal, filtrado 4→2→1→1→4, reset de selección) ✓.


## 2026-06-13 — VPOS Multi-RIF · Bypass del modal "¿Es Multitienda?" en Enviar a Implementación

- **Frontend (`Quotes.jsx`)**: `openMultistoreDialog` ahora hace **early-return** cuando `quote_type === 'VPOS_MULTIRIF'`: omite el modal "¿Es Multitienda?" y llama directo a `handleSendToImplementation` (preservando `exceptionInfo` para el flujo irregular). Para el resto de tipos, el modal tradicional Sí/No se mantiene intacto.
- **Integridad de payload**: para Multi-RIF, `handleSendToImplementation` declara `is_multirif:true` + `is_multistore:true` en el body (SIN `stores`), para no enrutar al multistore plano y conservar `project_type="multirif"`.
- **Backend (`quote_actions.py`)**: `SendToImplementationRequest` acepta `is_multirif`; se preserva el `client_name` sintético del Banco para Multi-RIF. El backend solo arma multistore plano con `is_multistore && stores`, por lo que Multi-RIF mantiene su jerarquía de 3 niveles (lo construye `_create_project_from_quote` desde `multirif_distribution`).
- **Validado E2E (backend)**: POST send-to-implementation con body de bypass → HTTP 200 y proyecto creado con `project_type="multirif"`, RIFs/sucursales correctos y nombre del Banco. QA #1 (avanza sin modal) y QA #3 (integridad jerarquía) ✓. QA #2 (modal tradicional preservado) por código sin cambios en esa rama.


## 2026-06-13 — VPOS Multi-RIF · FASE 4: Variables de correo (Distribución + Avance)

Dos variables dinámicas para las plantillas de correo (notificación inicial vs. avances):
- **`{Matriz_MultiRif_Distribucion}`**: tabla HTML jerárquica Cliente (RIF) → Sucursales → Cajas + TOTAL GENERAL. Para la notificación inicial.
- **`{Matriz_MultiRif_Avance}`**: misma tabla + columna **Avance %** por Sucursal, por RIF (ponderado por cajas) y Global. Para correos de avance.
- Implementadas en `project_template_vars.py` (`_build_multirif_distribution_html(with_progress)`, `_multirif_store_progress`, `_multirif_weighted_progress`). Fases canónicas = Recibido/Configurado/Testeado/En Producción.
- Catalogadas en el editor: `projects.py` (endpoint de variables), `templateVariables.js`, `EmailTemplatesEditor.jsx`. Fallback "No aplica" para proyectos no Multi-RIF.
- **Validado:** render directo — jerarquía correcta, TOTAL GENERAL=10, avances 33%/50%/0%/Global 20% (coinciden con el árbol de Fase 3).


## 2026-06-13 — VPOS Multi-RIF · FASE 3: Proyecto "Multi-RIF" + tracking de 3 niveles (P0)

- **Conversión (`quote_transitions._create_project_from_quote`)**: cuando la cotización tiene `is_multirif`, crea proyecto `project_type="multirif"` con: `rifs[]` (metadata del cliente jurídico: rif_id, client_id, rif, client_name, box_count) y `stores[]` **planos** etiquetados con `rif_id` (reutilizan los endpoints/UX multitienda existentes). Cada store recibe una copia profunda (`copy.deepcopy`) de la `implementation_matrix`. La matriz principal es la unión.
- **Nuevo componente `MultiRifTree.jsx`**: árbol colapsable de 3 niveles **Proyecto Global → RIF → Sucursal** con barras de **progreso fraccionado** (verde al 100%). Progreso ponderado por nº de cajas: store = fases completadas/4; RIF = Σ(store×cajas)/Σcajas; Global = ídem global. Cada sucursal se expande al editor de matriz reutilizando `StoreBankSection` (endpoint `/projects/{id}/stores/{storeId}/matrix/phase`).
- **ProjectDetail**: `isMultiRif`; la matriz principal usa modo rollup (solo lectura) como multitienda; se renderiza `MultiRifTree` cuando `project_type==='multirif'` y el cliente fue notificado.
- **Validado:** conversión backend (unit: multirif, 2 RIFs, 3 stores con rif_id e independencia de matrices) + UI (árbol renderizado, progreso 3 niveles correcto 20%/33%/50%, expansión y editor de matriz por sucursal). Pendiente cosmético: warning hidratación.


## 2026-06-13 — VPOS Multi-RIF · PDF de cotización (cliente=Banco + Detalle de Tiendas)

Ajuste del PDF de cotización para Multi-RIF (previo a Fase 3):
- **Portada y Página 2 (Datos del Cliente):** el nombre del cliente ahora es el **nombre del Banco de adquirencia**. Hidratación autoritativa server-side: `hydrate_pdf_request` resuelve el banco desde `sponsoring_bank_id` y fija `cliente_nombre` (y limpia RIF/contacto/dirección) cuando `is_multirif`.
- **Página 5 — "Detalle de Tiendas y Sucursales":** nuevo método `_build_multirif_section()` en `pdf_generator.py` que renderiza una tabla jerárquica Cliente(RIF) → Sucursales → Cajas con TOTAL GENERAL. Invocado en `generate_vpos` (PYME) y `generate_vpos_corp` (CORP).
- `TemplateQuotePDFRequest` extendido con `is_multirif`, `multirif_distribution`, `sponsoring_bank_id/name`. `create_quote_with_pdf` propaga estos campos al `pdf_request`. Frontend (`buildTemplatePdfData` + pdfData inline) envía cliente=banco y la distribución.
- **Validado:** PDF generado directamente y extraído — portada/página 2 = "Banco de Venezuela", sección jerárquica correcta, TOTAL GENERAL = 10.


## 2026-06-13 — VPOS Multi-RIF · FASE 2: Motor de distribución anidada + barra de progreso + limpiezas (P0)

- **Nuevo componente `MultiRifDistributionPanel.jsx`**: motor de distribución Global→RIF→Tienda. Buscador de Cliente/RIF (≥2 chars sobre nombre/RIF), cajas por RIF, sub-sucursales (nombre+cajas). Exporta `validateMultiRif(dist, globalBoxes)`.
- **"Reel" de saldos**: Σsucursales ≤ cajas del RIF (error inline `multirif-rif-error-{i}`); ΣRIFs ≤ Cajas Globales. **Guardado bloqueado** hasta distribuir el 100% (validación en `handleSubmitQuote` con toast).
- **Barra de progreso en vivo** (`multirif-progress-bar` + badge): "asignadas / globales", **azul/ámbar** (faltan), **verde** al 100% ("¡Lote distribuido al 100%!"), **roja** si excede.
- **Ambos paneles disponibles** en Multi-RIF: "Detalle de Sucursales" (convencional) + "Detalle de Tiendas/Sucursales (Multi-RIF)".
- **Persistencia**: `multirif_distribution` `[{client_id, rif, client_name, boxes, stores:[{name,boxes}]}]` enviado en el payload y guardado en la cotización.
- **Limpiezas Fase 1 (solo Multi-RIF)**: ocultos el campo **Bancos/Entes** (siempre 1 banco) y la pregunta **¿Exento de IVA?** (ningún banco exento). Regresión VPOS normal intacta.
- **Validado:** testing_agent iter72 — backend 2/2 pytest, frontend 100% (Reel 12/10 rojo, 5+5 verde, sucursal 6>5 error, bloqueo 7/10). Pendiente cosmético: warning hidratación `data-ve-dynamic`.


## 2026-06-13 — VPOS Multi-RIF · FASE 1: Entrada Comercial + Fundamento de datos (P0, épico 5 fases)

Nueva línea de producto "VPOS Multi-RIF" (lote bancario para múltiples RIFs). Fase 1 entregada:
- **Nuevo tipo `VPOS_MULTIRIF`** en `constants.js` (QUOTE_TYPES), disponible en flujos Pyme y Corporativo.
- **Lógica invertida en el wizard** (`QuoteWizardDialog.jsx`): al elegir el tipo se omite el selector de **Cliente** y se exige **Banco (Adquirencia)** (`multirif-bank-select`); patrocinio **implícito = Sí** (banco = patrocinador absoluto, bloque `multirif-implicit-sponsor` reemplaza la pregunta Sí/No); etiqueta **"Cajas Globales (Lote)"**; el banco de **Medios de Pago se hereda y bloquea** (useEffect → `handleBankSelect`, `select-bank` disabled), filtrando productos de esa entidad; IVA exento conservado.
- **Flags** (`Quotes.jsx`): `isMultiRif`, `isVPOS` lo incluye (pricing = VPOS convencional); `isHeaderComplete` para multi-rif exige `sponsoring_bank_id` en lugar de `client_id`; payload `/quotes/create-with-pdf` envía `client_id:null` + `is_multirif:true`.
- **Backend** (`quotes.py`, `models.py`): `QuoteCreateWithPDF.client_id` ahora opcional; `create-with-pdf` genera `client_name` sintético **"Lote &lt;Banco&gt; (Multi-RIF)"** y persiste `is_multirif` + `multirif_distribution` (placeholder Fase 2). Modelo `Quote` extendido con `is_multirif`/`multirif_distribution`.
- **Validado:** testing_agent iter71 — backend 4/4 pytest, frontend 100% (Pyme + Corp invertidos, regresión VPOS intacta). Pendiente cosmético: warning hidratación `data-ve-dynamic` en QuotesTable (preexistente).

### Roadmap pendiente VPOS Multi-RIF
- **Fase 2 (P0):** Motor de distribución anidada Global→RIF→Tienda + validación de saldos ("Reel"): botón "Detalle de Tiendas/Sucursales (Multi-RIF)", buscador de Cliente/RIF con cajas, sub-sucursales (nombre+cajas), reglas Σtiendas≤RIF y ΣRIFs≤Global, bloqueo hasta 100%. Persistir en `multirif_distribution`.
- **Fase 3 (P0):** Conversión a proyecto tipo "Multi-RIF" + tracking 3 niveles (árbol colapsable Proyecto→RIFs→Sucursales, progreso fraccionado).
- **Fase 4 (P1):** Notificaciones — variable `{Matriz_MultiRif_Distribucion}` (tabla jerárquica Cliente(RIF)→Sucursales→Cajas).
- **Fase 5 (P1):** Actualización Masiva con filtros en cascada (Fase→Banco→RIF→Tiendas), "Todos los RIFs" vs RIF específico.


## 2026-06-13 — Edición Maestra: diff de auditoría en bitácora

Mejora de trazabilidad sobre los overrides de admin (`projects.py` → `master_override_project`):
- Nuevo helper `_master_diff()` que compara los valores anteriores del proyecto contra el override y produce una lista de cambios `{field, label, old, new}` (campos escalares, Estado, Tipo, Banco Patrocinador, Hardware, y resumen Bancos/Productos vía `_summarize_matrix`; en multitienda, diff por tienda).
- La bitácora (`type='master_override'`) ahora guarda: texto legible "N campo(s) modificado(s) por {admin}: Estado: 'X' → 'Y'; ..." **y** la estructura `changes` para trazabilidad programática. Respuesta incluye `changes_count`.
- Validado por curl: detecta solo los campos realmente cambiados (Ticket/Estado/Bancos-Productos) e ignora los iguales.


## 2026-06-13 — Edición Maestra (Super-Admin Overrides) en Módulo de Proyectos (P0)

Función de edición global/permisiva exclusiva para rol Administrador:
- **RBAC:** endpoint `PUT /api/projects/{id}/master-override` bloqueado con **403** para no-admin; icono de **lápiz** (`master-edit-btn-{id}`) visible solo si `isAdmin`, colocado **inmediatamente a la izquierda de la papelera** en la columna Acciones (`Projects.jsx`).
- **Modal `MasterEditDialog.jsx`** (nuevo componente): todos los campos en modo escritura. Dropdowns dinámicos: **Estado** (catálogo 7 estados + valor legacy actual), **Tipo de Proyecto** (VPOS/MPOS/GATEWAY/LINK), **Banco Patrocinador** (catálogo `/banks`). Editor relacional **Banco↔Productos** con multi-selección de medios de pago **filtrados por el Tipo de Proyecto** (flags `vpos_available`/`mpos_available`/`gateway_available`/`link_available`). **Hardware** multi-select desde `/hardware`. **Multitienda**: pestañas por tienda.
- **Override relacional consistente (backend):** reconstruye `banks[]`, `services[]` (items `additional`, preservando precios de los que coinciden) e `implementation_matrix` (preservando datos de fase de pares banco/producto sin cambios). En multitienda reconstruye cada `stores[].implementation_matrix` y la matriz principal como **unión** de las tiendas. Sin registros huérfanos; Ficha Técnica sigue generándose OK. Auditoría en `notes` + `bitacora` (`type='master_override'`).
- **Validado:** testing_agent iter70 — backend 5/5 pytest, frontend 100% (RBAC, posición del icono, dropdowns, filtro de productos por tipo, impacto relacional single + multitienda, ficha técnica). Sin regresiones. Pendiente cosmético: warnings de hidratación `data-ve-dynamic` (preexistente).


## 2026-06-12 — Gestión de Estados, Auditoría de Cierre/Suspensión y Optimización Visual de la Bandeja de Proyectos (P0)

Reingeniería del módulo Proyectos. Reglas confirmadas por el usuario (incluida opción b: el modal de justificación también aplica al reactivar/reabrir):
- **Estado "Anulado":** agregado a `PROJECT_STATUSES` y `PROJECT_MANUAL_STATUSES` (`backend/models.py`).
- **Endpoint `PUT /api/projects/{id}/status` convertido a multipart/form-data** (`backend/routes/projects.py`): campos `new_status` (req), `note`, `change_date`, `file` (opcional). Ahora escribe nota corta (compat) + entrada de bitácora `type='status_change'` con `new_status` y `attachments` (anexo guardado vía `save_pdf_dual` en `/uploads/status_changes/{pid}/`). Modelo `ProjectStatusUpdate` eliminado (dead code).
- **Modal de Justificación (`Projects.jsx`):** comentario OBLIGATORIO (botón Confirmar deshabilitado sin texto) + anexo OPCIONAL. Usa `FormData`. Opción "En Gestión (Reactivar)" visible solo para proyectos en estado cerrado/pausado.
- **Toast recordatorio** "Recuerde cerrar el Ticket en el portal" + aviso ámbar dentro del modal al seleccionar Culminado/Anulado.
- **Filtro por defecto "Activos (ocultar cerrados)"** oculta Suspendido/Culminado/Implementado parcial/Anulado. Opción "Todos los estados" disponible.
- **Nueva columna "Envío a Imple"** (`sent_to_implementation_at`).
- **Eliminación ABSOLUTA de "Proceso Irregular":** KPI card (ahora 5 cards), opción de filtro y badge de fila removidos.
- **Validado:** testing_agent iter69 — backend 4/4 pytest (`test_iteration69_project_status_audit.py`), frontend 100% UI. Sin regresiones. Único pendiente: warnings de hidratación `data-ve-dynamic` (cosmético, sistémico, no bloqueante).


## 2026-06-10 — Fix: producto duplicado ("Débito Inmediato") en Productos por Banco (Proyectos Directos)

El usuario reportó que en el reel de Distribución de Cajas (Proyectos Directos), "Débito Inmediato" aparecía duplicado en los bancos que lo tienen (y, en producción, en todos los bancos).

- Causa: el array `products` de un banco podía contener el mismo `product_name` repetido (en preview: Banco de Venezuela, Banco Plaza, Bancaribe tenían un producto duplicado). El frontend renderiza `bank.products` sin deduplicar.
- Backend `routes/banks.py`: nuevo helper `dedupe_bank_products(bank)` que fusiona productos por `product_name` (OR de banderas `vpos/gateway/mpos/link_available`, conserva primer valor no vacío del resto). Aplicado en `get_banks` y `get_bank_detail` (dedup en lectura → ninguna vista muestra duplicados, también en producción tras redeploy).
- Frontend `DirectProjectCreation.jsx`: `reelBankProducts` ahora deduplica por `product_name` (guard defensivo).
- Limpieza de datos (preview): se persistió la deduplicación en 3 bancos (Banco de Venezuela 8→7, Banco Plaza 10→9, Bancaribe 9→8). Verificado: 0 bancos con duplicados; "Débito Inmediato" solo en los 2 bancos que lo tienen (Banco Plaza, R4), no en todos.
- Pendiente producción: el dedup en lectura oculta duplicados, pero si producción tiene "Débito Inmediato" agregado erróneamente como entrada ÚNICA en bancos que no deberían tenerlo, eso requiere limpieza de datos (quitarlo desde la ficha del banco) ya que no es posible saber automáticamente qué bancos deberían tenerlo.


## 2026-06-10 — PDF Payment Gateway: IVA y Total con IVA en la página 3

Requerimiento del usuario: insertar en la página 3 (INVERSIÓN EN SETUP / ARRANQUE) del PDF de la cotización Payment Gateway el valor del IVA y el total después del IVA.

- `services/pdf_generator.py` `generate_pg()` (~L1752): la tabla de setup de la página 3 antes solo mostraba "TOTAL SETUP" (= subtotal sin IVA). Ahora muestra 3 filas de totales: **SUBTOTAL SETUP**, **IVA (16%)** (o **IVA (Exento)** $0.00 según `iva_exempt`) y **TOTAL SETUP (CON IVA)**. La fila de Total con IVA queda resaltada (azul claro); subtotal e IVA con fondo gris. Zebra de detalle ajustada para excluir las 3 filas de totales.
- Validado generando el PDF PG en proceso (5 páginas): IVA 16% → Subtotal $150 / IVA $24 / Total $174; IVA exento → IVA $0 / Total $150.
- Nota: el endpoint `POST /quotes/{id}/regenerate-pdf` falla (500) para cotizaciones antiguas con `pinpad_model`/`sponsor_bank_name` = None (error de validación Pydantic preexistente, ajeno a este cambio) — posible fix futuro: coaccionar None→"" en `regenerate_quote_pdf`.


## 2026-06-10 — Fix: espaciado correo vs Vista Previa + borrado de plantillas

Dos problemas reportados (PREVIEW). Ambos probados por testing_agent (iteration_56): 4/4 PASS.

**1) Espaciado entre líneas (Gmail) ≠ Vista Previa**
- Causa: las plantillas usan `<p>` y `<p></p>`; la Vista Previa usaba `prose prose-sm` (Tailwind, compacto) pero el correo se enviaba como HTML crudo y Gmail aplica márgenes grandes por defecto a `<p>`.
- Backend `services/email_service.py`: nueva `normalize_email_html(html)` que inyecta `style="margin:0 0 10px 0;line-height:1.5"` en línea a cada `<p>` (sin pisar estilos existentes) y envuelve el cuerpo con tipografía base (Arial 14px, line-height 1.5). Aplicada en `send_email` antes del footer.
- Frontend: nueva clase `.email-render` en `index.css` (mismo espaciado). Los contenedores de Vista Previa (`RichTextEditor.jsx` preview body y `EmailPreviewDialog.jsx`) y el canvas del editor (`.ProseMirror p`) usan ahora ese espaciado en lugar de `prose prose-sm`. Vista Previa y correo quedan homologados (margin 0 0 10px, line-height 1.5). [El render real en Gmail no se puede validar automáticamente].

**2) No se podían eliminar plantillas**
- Causa: las plantillas por defecto (semilla) NO existen en BD; al borrarlas `delete_one` devolvía 0 → 404 → "Error eliminando plantilla".
- Backend `routes/seed_and_templates.py`: `delete_email_template` ahora, si la plantilla no está en BD pero es una semilla conocida (PROJECT_EMAIL_TEMPLATES/EMAIL_TEMPLATES_BY_SEDE/DEFAULT_EMAIL_TEMPLATES), registra un tombstone en `deleted_default_templates` y devuelve 200. `get_email_templates` excluye las tombstoned. `create`/`update`/`reset` limpian el tombstone (permite re-agregarlas). `reset` ahora también contempla PROJECT_EMAIL_TEMPLATES.
- Verificado: borrado de plantilla por defecto (`project_notify_bank`) y custom funcionan, desaparecen y no reaparecen tras refrescar.


## 2026-06-10 — Fix URGENTE: variables de Cotización faltaban en el editor de plantillas del MÓDULO PROYECTOS

El usuario seguía sin ver variables de Cotización (ej. `abreviaturas_medios_pago`) en plantillas de Proyectos. **Causa raíz**: el módulo de Proyectos (botón "Plantillas" en `/projects`) usa un editor DISTINTO — `components/projects/TemplatesAdminDialog.jsx` con su PROPIO diccionario `VAR_GROUPS` — separado del editor de `/settings` (`EmailTemplatesEditor.jsx`) que sí se había homologado. `VAR_GROUPS` no tenía ninguna variable de Cotización.

- `TemplatesAdminDialog.jsx` `VAR_GROUPS`: ahora 6 grupos (49 variables). Nuevos: **"Cotización / Ventas"** (Cotizacion_Nro, quote_number, quote_type, total_usd, Monto_Total, invoice_number, approved_date, abreviaturas_medios_pago, Banco_Patrocinador, company_name, sede_name, Nombre_Ejecutivo, Email_Ejecutivo) y **"Despacho / Equipos / Reparación"** (Modelo_Equipo, Cantidad, Modelo_Pinpad, items_table, services_table, Direccion_Entrega, Lista_Seriales, lista_modelos_seriales, lista_equipos_seriales, modelos_resumen, almacen_custodia). Se agregó `Nombre_Fantasia` y `client_address` al grupo Cliente.
- `projectConstants.js` `ALL_TOKENS` (autocompletado al escribir `{` en TemplateBodyEditor): homologado con todas las variables de Cotización.
- `ProjectDetail.jsx`: las 2 listas inline de "Otras Notificaciones" ahora usan `ALL_TOKENS` (homologación automática).
- `EmailPreviewDialog.jsx`: `QUICK_VARS` ahora deriva de `ALL_TOKENS`.
- Probado por testing_agent (iteration_55): 5/5 PASS. Diálogo "Plantillas" de /projects muestra 49 chips en 6 grupos; click en `abreviaturas_medios_pago` inserta `{abreviaturas_medios_pago}`.



El usuario reportó que NO veía variables de Cotizaciones (ej. `abreviaturas_medios_pago`) en las plantillas de Proyectos. Causa: la homologación previa llenó la sección "Variables de esta plantilla" (`getTemplateVariables`), pero el panel categorizado prominente ("Panel de Variables" / `VARIABLE_CATEGORIES`) no listaba esas variables.

- `components/EmailTemplatesEditor.jsx` `VARIABLE_CATEGORIES`:
  - Categoría "Financiero (Ventas)": agregadas `approved_date`, `abreviaturas_medios_pago`, `Banco_Patrocinador`.
  - Categoría "Implementación (Técnico)": agregado alias `Modelo_Pinpad` (ya tenía Matriz_Sucursales y Patrocinador).
  - Nueva categoría "Despacho / Reparación / Equipos" (icono Box): `Modelo_Equipo`, `Cantidad`, `Lista_Seriales`, `lista_modelos_seriales`, `lista_equipos_seriales`, `modelos_resumen`, `almacen_custodia`.
  - `ICON_MAP` ampliado con `Box`.
- Nota: la variable correcta es `{abreviaturas_medios_pago}` (plural). El backend ya la resuelve en proyectos (verificado: `TDC-TDD/C2P/C@mbioP2C`). El panel categorizado es el mismo para Cotizaciones y Proyectos, por lo que ambos cuerpos quedan homologados también en la vista categorizada.

## 2026-06-10 — Homologación de variables Cotizaciones ↔ Proyectos en plantillas

Requerimiento del usuario: inyectar todas las variables de las plantillas de Cotizaciones en las de Proyectos y dejar ambos cuerpos homologados.

- **Backend (núcleo)** `services/project_template_vars.py` → `resolve_project_template_vars`: ahora hace `return {**quote_vars, **variables}`, donde `quote_vars = _build_template_vars(cotización_original or proyecto)`. Para proyectos regulares se construye desde la cotización (`quote_id` en `quotes`); para Proyectos Directos (`dq_*`, sin cotización en `quotes`) cae al propio proyecto (best-effort). Las variables del proyecto tienen prioridad en claves compartidas. Validado: `Cotizacion_Nro` (COT real), `Nombre_Ejecutivo`, `Email_Ejecutivo`, `Monto_Total`, `abreviaturas_medios_pago`, `company_name`, etc., ahora se resuelven en plantillas de Proyectos.
- **Frontend** `components/EmailTemplatesEditor.jsx`: nueva const `HOMOLOGATED_VARS` (unión deduplicada de TODAS las `BASE_TEMPLATE_VARIABLES` + `VARIABLE_CATEGORIES`). `getTemplateVariables` ahora devuelve `baseVars + SHARED_VARS + HOMOLOGATED_VARS` (deduplicado), de modo que el picker "Variables de esta plantilla" muestra el MISMO conjunto (73 variables) en ambos cuerpos. Se corrigió además `Nombre_Fantasia` faltante en `SHARED_VARS`.
- Probado por testing_agent (iteration_54): 5/5 PASS. Plantillas de Proyecto exponen variables de Cotización (Cotizacion_Nro, Nombre_Ejecutivo, Monto_Total, Nombre_Fantasia, abreviaturas_medios_pago) y las de Cotización exponen variables de Proyecto (Nombre_Implementador, Correo_Implementador, Matriz_Bancos_Productos, Lista_VTID). Click inserta placeholder y el hover-preview funciona en ambos. 73 chips idénticos en ambos.


## 2026-06-10 — Ticket flexible (duplicados con confirmación) + Bancos alfabéticos + variable {Nombre_Fantasia}

Tres requerimientos del usuario. Los 3 probados por testing_agent (iteration_53): 3/3 PASS.

**1) Flexibilizar unicidad del Nro de Ticket de Proyecto**
- Antes `PUT /api/projects/{id}/ticket` bloqueaba con error 400 si el ticket ya existía en otro proyecto.
- Ahora: `TicketNumberUpdate.confirm_duplicate: bool = False`. Si el ticket existe en otro proyecto y `confirm_duplicate=false` → HTTP 409 con `detail={code:'ticket_duplicate', existing_client_fantasy, existing_project_number, message}` (incluye el Nombre de Fantasía del cliente del otro proyecto). Con `confirm_duplicate=true` permite guardar.
- Frontend `ProjectDetail.jsx`: `handleSaveTicket(confirmDuplicate)` captura el 409 y abre un `AlertDialog` (`ticket-duplicate-dialog`) con el mensaje y nombre de fantasía; "Sí, asignar de todos modos" reenvía con `confirm_duplicate=true`. (testids: ticket-duplicate-message/cancel/confirm).

**2) Dropdowns de Bancos en orden alfabético**
- `routes/banks.py` `get_banks`: `banks.sort(key=name.casefold())` antes de devolver. Como TODOS los selectores consumen `/banks`, quedan ordenados globalmente (Cotizaciones, Proyectos Directos, etc.). Verificado: 33 bancos alfabéticos.

**3) Nueva variable {Nombre_Fantasia}**
- Carga el campo `fantasy_name` del cliente. Agregada en los 3 motores: `notification_engine.py` y `workflow_notifications.py` (cotizaciones) y `project_template_vars.py` (proyectos), con fallback a la razón social si no hay fantasía.
- Frontend `EmailTemplatesEditor.jsx`: `Nombre_Fantasia` en `SHARED_VARS` (picker de todas las plantillas) + categoría "Cliente" + ejemplo del preview. También añadida a las listas inline de variables en `ProjectDetail.jsx` (2 lugares) y `EmailPreviewDialog.jsx`.

Nota: persisten warnings de hydration preexistentes (`<tr>`/`<span>`/`<tbody>`) NO relacionados — backlog.


## 2026-06-10 — Mini-preview por hover de variables tipo tabla en el editor de plantillas

Mejora solicitada por el usuario. En el editor de Plantillas de Correo (`EmailTemplatesEditor.jsx`, dentro de `/settings`), al pasar el mouse sobre los chips de variables de tipo tabla/HTML aparece una mini-vista previa de la tabla con datos de ejemplo.

- Nueva constante a nivel de módulo `VARIABLE_PREVIEW_HTML` con el HTML de ejemplo de: `Matriz_Bancos_Productos`, `Matriz_Sucursales`, `items_table`, `services_table`.
- Nuevo componente `MiniPreview` que envuelve el chip con `HoverCard` (shadcn `./ui/hover-card`) solo cuando la variable tiene preview; el resto se renderiza igual. Aplicado en el panel categorizado (`master-var-*`) y en "Variables de esta plantilla" (`spec-var-*`). HoverCard expone `data-testid=var-preview-<key>`.
- El clic del chip (insertar/copiar variable) sigue funcionando (HoverCardTrigger asChild no rompe el onClick).
- Dedupe: `openPreview` (vista previa completa) ahora hace spread de `VARIABLE_PREVIEW_HTML` en `exampleValues` en lugar de mantener copias separadas del HTML (atiende comentario de code review sobre drift).
- Probado por testing_agent (iteration_52): 6/6 aserciones PASS (preview de ambas matrices con tabla y datos, variables no-tabla sin preview, clic sigue insertando, sin regresiones).
- Nota: persisten warnings de hydration preexistentes en `/settings` (`<span>` dentro de `<tbody>` / `<tr>` dentro de `<span>`) NO causados por este cambio — quedan en backlog.


## 2026-06-10 — Variables dinámicas de Cotización en plantillas (Matriz_Bancos_Productos, Matriz_Sucursales, Patrocinador)

El usuario reportó que en las plantillas de Cotizaciones no se cargaba `{Matriz_Bancos_Productos}` y pidió que TODAS las variables que dependen de la cotización estén disponibles, en particular las nuevas `{Patrocinador}` y `{Matriz_Sucursales}`.

Causa raíz: los dos motores que renderizan correos de cotización (`notification_engine._build_template_vars` dinámico y `workflow_notifications.py` legacy) no producían esas variables (solo existían en el entorno de Proyectos via `project_template_vars.py`).

- Nuevo helper compartido `services/quote_template_vars.py` → `build_quote_dynamic_vars(quote, client_fantasy, client_legal)`. Reutiliza `_build_matrix_html` y `_build_stores_matrix_html` de `project_template_vars`. Construye:
  - `Matriz_Bancos_Productos`: desde `additional_items` (o fallback `services[item_type=additional]`), agrupado banco→producto con cantidades.
  - `Matriz_Sucursales`: desde `branch_details [{store_name, quantity}]`, con fila Total; fallback a Sede Principal + cantidad_cajas.
  - `Patrocinador`: "Banco - Procesador" si es patrocinada; si no, nombre de fantasía del cliente (mismo criterio que Proyectos).
- Inyectado en ambos motores: `notification_engine._build_template_vars` (captura `fantasy_name` y mergea las 3 vars) y `workflow_notifications.py` (idem). Resuelto end-to-end (verificado con cotizaciones reales).
- Frontend `EmailTemplatesEditor.jsx`: las 3 variables se agregaron a `SHARED_VARS` (con dedupe por key, así aparecen en el picker de TODAS las plantillas sin duplicar las de Proyecto), a la categoría lateral "Implementación (Técnico)" y a los ejemplos del Preview.
- Verificación de gap Cotizaciones vs Proyectos: el resto de variables exclusivas de Proyecto (Nombre/Correo/Telefono_Implementador, Lista_VTID, Modelo_Seriales_*, Servidor_Instalacion, project_number, ticket_number, etc.) son a nivel de Proyecto y no derivan de una cotización; no faltan variables de cotización adicionales.
- Test de regresión: `backend/tests/test_quote_dynamic_vars.py` (5/5 PASS).


## 2026-06-10 — Campo "Bancos o Entes" editable en Item 1 (Suscripción PDV/Banco)

Requerimiento del usuario (Setup del asistente de Cotización). Antes el Item 1 "Suscripción PDV/Banco" mostraba la columna "Bancos o Entes" como SOLO LECTURA (heredaba el número de bancos del header "Bancos/Entes" de la solicitud original). Por dinámica del negocio ahora debe ser editable.

- `QuoteWizardDialog.jsx` (rama `item.inheritBancos` del Setup, ~línea 1392): se reemplazó el `<div>` de solo lectura por un `<Input>` editable (`data-testid=setup-bancos-inherit-<index>`). Default = valor heredado del header. Al editar manualmente un valor distinto, se marca `item.bancosManual=true` (borde/ícono ámbar, override) y se limpia `totalOverride` para recalcular Total (tarifa × cajas × bancos). Si se reescribe el valor del header, vuelve a estado heredado (azul).
- `Quotes.jsx` (useEffect de propagación header→items, ~línea 630): se agregó `&& !item.bancosManual` para que los cambios del header NO pisen una edición manual del Item 1.
- Alcance: solo el Item 1 del Setup. El item recurrente equivalente ("Derecho de uso de plataforma MServer por PDV / Banco") permanece de solo lectura (no estaba en el requerimiento).
- Probado por testing_agent (iteration_51): 7/7 aserciones PASS (editable, herencia default, propagación mientras no hay override, override manual con indicador ámbar, recálculo de Total, header no pisa el override, reescribir valor del header re-hereda).

### Extensión (mismo día) — Recurrente también editable
A solicitud del usuario, se aplicó el MISMO patrón editable al item recurrente "Derecho de uso de plataforma MServer por PDV / Banco" (rama `inheritBancos` de Recurrentes Básicos, `QuoteWizardDialog.jsx` ~L1644, `data-testid=recurring-basic-bancos-inherit-<index>`) y se añadió `&& !item.bancosManual` a la propagación de Recurrentes Básicos en `Quotes.jsx`. Ahora Setup y Recurrente quedan consistentes: ambos heredan por defecto del header y permiten override manual. Mismo patrón ya validado 7/7 para el Setup.



## 2026-06-10 — Destinatarios Dinámicos por Sesión + Acción "Respuesta del Implementador"

Requerimiento de 2 partes (P0). Ambas partes completadas y probadas (backend curl end-to-end + frontend testing agent iteration_50, 100% PASS).

**Parte 1 — Destinatarios Dinámicos por Sesión**
- Dos nuevos tipos de destinatario en los selectores de configuración de notificaciones:
  - `session_user` ("Usuario generador") → el usuario web activo que dispara la acción (sesión `current_user`).
  - `session_executive` ("Ejecutivo generador") → el ejecutivo creador de la cotización/proyecto (`created_by_user_id`).
- Backend `notification_engine.try_dispatch`: resuelve `session_user` desde `current_user` y `session_executive` desde el creador de la cotización (fallback a `Email_Ejecutivo`). Canal inbox válido cuando hay `user_id` interno.
- Backend `other_actions_engine.dispatch_other_action`: nuevo param `executive_user_id`; resuelve ambos tipos; inbox sólo con `user_id`.
- Validaciones relajadas en `routes/action_notifications.py` (client_field/user/session_user/session_executive) y `routes/other_actions_config.py` (user/session_user/session_executive; user_id sólo exigido para type=user).
- Frontend: `ActionNotificationsConfig.jsx` (selector Tipo con 4 opciones; canal disponible para tipos de sesión) y `OtherActionsConfig.jsx` (nuevo selector Tipo con 3 opciones; user_id sólo requerido para "Usuario interno").

**Parte 2 — Acción "Respuesta del Implementador" (id=implementer_response)**
- Registrada en `OTHER_ACTIONS` (`routes/other_actions_config.py`) → aparece en *Configuración de Otras Acciones*.
- Disparador en background en `PUT /api/projects/{id}/ticket` (`routes/projects.py`): helper `_dispatch_implementer_response`. Se dispara sólo en transición de `ticket_number` vacío → valor y cuando el ejecutor es Implementador (admin permitido para QA). Usa `asyncio.create_task` (no bloquea la respuesta). El "Ejecutivo generador" se resuelve al `created_by_user_id` del proyecto.
- Verificado: registrar ticket despachó `sent_count=2` (session_user=quien registra vía email, session_executive=creador vía inbox). Si el admin no configura la acción, `dispatch_other_action` no envía nada (cero regresión).


## 2026-06-10 — Multi-remitente extendido a todas las áreas

A solicitud del usuario, el esquema de remitente por área (que existía solo para Proyectos e Integradores) se amplió a TODAS las áreas que envían correo, configurables desde *Configuración → Remitentes de Correo*.

- Nuevas áreas: **Cotizaciones PYME**, **Cotizaciones Corporativas**, **Comunicaciones a Clientes**, **Contactos Iniciales**, **Nuevos Productos**, **Inventarios** (además de Proyectos e Integradores).
- `email_service.py`: helper `resolve_sender_for_quote(quote)` elige `cotizaciones_corp` o `cotizaciones_pyme` según `client_segment`.
- Cableado: `quote_actions.py` (8 envíos: repair/FT config/repair complete) y `quote_serials.py` usan el remitente de Cotizaciones por segmento; `client_communications.py` → comunicaciones_clientes; `initial_contact_communications.py` → contactos_iniciales; `new_products.py` → nuevos_productos; `inventory.py` → inventarios.
- `settings.py`: `EMAIL_SENDER_AREAS` con las 8 áreas. La UI las renderiza dinámicamente (sin cambios de estructura).
- Verificado: GET lista 8 áreas; asignar Cotizaciones Corp resuelve al alias y PYME al default; 4 tests `tests/test_email_senders.py` (incl. `resolve_sender_for_quote` por segmento). Config dejada vacía (default) hasta que el admin configure direcciones reales.
- Nota de infraestructura (sigue vigente): con Gmail/Workspace, cada dirección debe estar verificada como "Enviar como" o ser alias de la cuenta SMTP autenticada, de lo contrario Gmail reescribe el From.


## 2026-06-10 — Múltiples remitentes de correo por área (multi-sender)

Solicitud: poder enviar desde más de una dirección remitente. Decisión del usuario: mismo dominio @megasoft.com.ve, remitente fijado automáticamente por área (Proyectos e Integradores), administrado solo por Admin.

- `services/email_service.py`: `resolve_sender_for_area(area)` (con caché ~60s e `invalidate_senders_cache`) lee `db.config{type:email_senders}` y devuelve el remitente asignado al área o `SENDER_EMAIL` por defecto.
- `routes/settings.py`: `GET/PUT /api/config/email-senders` (PUT solo Admin). Valida que todas las direcciones pertenezcan al dominio institucional (mismo que SENDER_EMAIL); guarda lista de remitentes + asignaciones por área.
- Cableado: `routes/projects.py` (notificaciones a Cliente/Banco y Otras Notificaciones) usa `resolve_sender_for_area('proyectos')`; `routes/integrators.py` (asignación y nuevo proyecto de integración) usa `'integradores'`.
- Frontend: nueva página `EmailSendersConfig.jsx` (`/settings/email-senders`) + tarjeta Admin en Settings. Gestión de direcciones (etiqueta/correo/activo) y selector de asignación por área.
- Verificado: GET/PUT (incl. rechazo de dominio ajeno 400), resolver (3 tests `tests/test_email_senders.py`), y E2E real — una notificación de Proyectos salió desde el remitente asignado (registrado en `email_logs`). Config de prueba reseteada a vacío (default) para no forzar buzones inexistentes; el admin define las direcciones reales en la UI.


## 2026-06-09 — Descuentos en PDF de cotizaciones Corporativas

Solicitud: en cotizaciones de clientes Corporativos, reflejar en las matrices de Setup y Recurrente el % de descuento y el monto calculado, restándolo del total (antes no aparecían en el PDF).

- `services/pdf_generator.py`: `_create_items_table` ahora acepta `discount_pct`. Cuando hay descuento, el bloque de totales muestra: Subtotal → **Descuento (X%)** (monto negativo, resaltado en verde) → **Subtotal Neto** → IVA (16%, calculado sobre el neto) → Total. `generate_vpos_corp` (Página 4) pasa `descuento_setup` y `descuento_recurrente` a las tablas SETUP y RECURRENTES MENSUALES.
- El frontend ya enviaba `descuento_setup`/`descuento_recurrente` en `pdf_data` (`buildTemplatePdfData`) y la descarga los lee del registro, por lo que el descuento aparece tanto en vista previa como en el PDF descargado.
- Verificado: render de Página 4 muestra Setup $318→-$31.80(10%)→$286.20 neto→IVA $45.79→Total $331.99 y Recurrente con 5%. Tests: `tests/test_corp_quote_discount_pdf.py` (2 passed). Sin cambios para PYME (default `discount_pct=0`).


## 2026-06-09 — Nuevas variables de plantillas de Proyectos

Solicitud: crear variables para Nombre/Email del Implementador y una Matriz de Sucursales.

- **`{Nombre_Implementador}`** y **`{Correo_Implementador}`**: YA existían (resueltas desde el usuario asignado al proyecto). Se confirmaron operativas.
- **`{Matriz_Sucursales}` (NUEVA):** tabla HTML con columnas *Sucursal* y *Cantidad de Cajas* por cada sucursal del proyecto (+ fila Total si hay más de una). Fallback a Sede Principal/cajas de servicios para proyectos PYME sin sucursales explícitas.
  - Backend: `services/project_template_vars.py` — helper `_build_stores_matrix_html()` + clave `Matriz_Sucursales` en `resolve_project_template_vars`. Registrada en `template-variables` y excluida del panel plano de variables (como `Matriz_Bancos_Productos`).
  - Frontend: agregada a los chips de variables de "Otras Notificaciones" y Notificaciones a Bancos/Clientes, al picker de `TemplatesAdminDialog`, a `ALL_TOKENS` (projectConstants) y al `exampleValues` de `RichTextEditor` (preview en editor).
- Verificado por curl: `Matriz_Sucursales` aparece en available_tags y `preview-adhoc` la renderiza como tabla (token reemplazado).


## 2026-06-09 — Adjuntos en Notificaciones a Bancos/Clientes (iter49)

Extensión solicitada: agregar Cargar Archivos / Cargar Imágenes / Adjuntar Matriz al flujo de Notificaciones a Cliente/Banco (antes solo en "Otras Notificaciones"). Verificado: testing agent iter49 100% frontend + backend por curl (envío real status 'sent' con adjunto + matriz).

- `projects.py`: `POST /projects/{id}/send-notification` convertido a **multipart** (Form + `files` + `attach_matrix`). Helper `_send_sequential_notification` ahora acepta `extra_attachments` (los adjunta al correo vía `send_email`) y `attach_matrix` (agrega la tabla de la matriz al cuerpo HTML). Los adjuntos se guardan en `uploads/notif_emails/{id}` y se registra `attachments_count` en el historial.
- `ProjectDetail.jsx`: estado `notifFiles`/`notifAttachMatrix` + `notifFileInputRef`; panel `notif-attachments-panel` en el modal de notificaciones (botones `notif-attach-files-btn`, `notif-attach-images-btn`, `notif-attach-matrix-btn`). `sendNotification` y el camino Vista Previa→Enviar (`sendFromPreview`, rama sequential) ahora usan FormData multipart para propagar adjuntos + matriz + `to_override`/`template_id`.


## 2026-06-09 — Paquete multidominio: Contactos, Canal Gateway, Mensajería, Branding (iter48)

Verificado E2E (testing agent iter48: 9/9 backend, frontend 100%). Tests: `/app/backend/tests/test_iter48_meganexus_package.py`.

### A) Bug fix — Canal de Cotizaciones Gateway Corporativo
- `quotes.py`: nuevo helper `_resolve_client_segment(client_id, quote_type, fallback)`. Para `GATEWAY`/`LINK_PAGO` el segmento se hereda de la ficha del CLIENTE (`segment='Corporativo'` → `CORP`), no de la sede del ejecutivo. Aplicado en `create_quote` y `create_quote_with_pdf`. Solo afecta cotizaciones NUEVAS (sin migración de históricas).

### B) Borrado masivo/selectivo en Centro de Mensajes
- `inbox.py`: nuevo `POST /api/inbox/batch-delete` (soft-delete por `message_ids`, aislado por usuario).
- `InboxCenter.jsx`: checkbox por fila (`inbox-select-{id}`), 'Seleccionar todo' (`inbox-select-all`), barra con botón papelera (`inbox-bulk-delete-btn`, activo solo con ≥1 selección) y modal de confirmación con conteo (`inbox-bulk-delete-dialog`).

### C) Edición admin-only en 'Contacto Inicial'
- `initial_contacts.py`: nuevo `PUT /api/initial-contacts/{id}` (RBAC: solo admin → 403 a otros). Edita contacto/empresa/teléfono/email/sede/notas, valida sede, registra traza en `bitacora` (action='edited' con deltas).
- `InitialContacts.jsx`: botón 'Editar' (`edit-btn-{id}`) visible solo si `role==='admin'` + modal `edit-contact-modal`.

### D) Homologación de 'Otras Notificaciones'
- `ProjectDetail.jsx`: el modal adhoc se rediseñó para clonar el look & feel del flujo de Notificaciones a Bancos/Clientes (tabla de contactos con checkboxes + 'Seleccionar todos', tarjeta azul de composición, chips TO, input de correo manual, selector de plantilla que carga `body_html`, editor enriquecido con `tableRowActions`, variables colapsables). **Se conservaron** las capacidades potentes: Cargar Archivos, Cargar Imágenes y Adjuntar Matriz de Distribución.

### E) Branding white-label
- `public/index.html`: título → `CRM Gestor - Mega Soft`; removido el badge 'Made with Emergent' (`#emergent-badge`) y meta description actualizada.

### Nota / bug colateral corregido
- Al añadir el PUT de edición se había borrado por accidente el decorador `@router.post('/initial-contacts/{id}/assign')`; el testing agent lo restauró. Verificado.
- Pendiente opcional (sugerido por el usuario): agregar Cargar Archivos/Imágenes/Matriz también al flujo de Notificaciones a Bancos/Clientes (requiere cambios en `send-notification` backend).


## 2026-06-09 — Manejo de Proyectos: 4 requerimientos Frontend (iter47)

Backend ya estaba listo (sesiones previas). Esta sesión implementó el Frontend y validó E2E (testing agent iter47: 5/5 backend + flujos frontend al 100%).

### T1 (P0) — Bug "Otras Notificaciones": cuerpo en blanco al elegir plantilla
- `ProjectDetail.jsx`: `handleTemplateSelect` ahora lee `tpl.body_html || tpl.body || ''` (antes leía `tpl.body`, vacío para plantillas de proyecto).
- Reemplazado el `<Textarea>` del mensaje por `<RichTextEditor>` (data-testid `email-message`), con `maxChars=20000`, `hardLimit={false}`. Removido el límite legacy de 1000 caracteres en `handleSendAdhocEmail`. El backend ya respeta el HTML vía `_adhoc_message_to_html`.

### T2 (P1) — Botón global "Plantillas" en `Projects.jsx`
- Montado `TemplatesAdminDialog` + estado/funciones (emailTemplates, fetchTemplates, openTemplatesAdmin, handleSaveTemplate, handleDeleteTemplate) en `Projects.jsx`.
- Botón en cabecera (data-testid `projects-templates-btn`) gated por `canEdit` (admin o usuarios con edición total en proyectos), según decisión del usuario.
- Se DEJÓ también el botón en el Detalle del Proyecto (`manage-templates-btn`) — el usuario pidió mantenerlo en ambos.

### T3 (P1) — Descarga de Ficha Técnica
- `ProjectDetail.jsx`: nuevo botón en cabecera (data-testid `download-ficha-tecnica-btn`) + handler `downloadFichaTecnica` que hace `GET /api/projects/{id}/ficha-tecnica` con `responseType: 'blob'` y dispara la descarga del PDF.

### T4 (P1) — Multiselect de medios de pago en Actualización Masiva
- `BatchUpdateModal.jsx`: el producto único (string) pasó a checkboxes múltiples (`batch-products-list`, `batch-product-checkbox-{prod}`) dependientes del banco seleccionado.
- `ProjectDetail.jsx`: estado `batchProduct` → `batchProducts` (array), `toggleBatchProduct`, `handleBatchBankChange` (preselecciona todos los medios del banco). Payload envía `product_names` (array) al endpoint que ya lo soporta.

### Notas
- Las URLs de preview viejas del handoff están dormidas; URL correcta del entorno: `https://rif-desglose.preview.emergentagent.com`.
- Pendiente opcional (a11y polish): agregar `<DialogDescription>` a `templates-dialog` y `batch-update-dialog`. Hydration warnings preexistentes del instrumentador (no del código).


## 2026-06-09 — Borrado de filas "fricción cero" en {Matriz_Bancos_Productos}

### Requerimiento
Eliminación ágil de filas de la matriz dentro del editor de notificación: icono de
papelera por fila, hover en rojo, un solo clic sin confirmación, transición suave,
borrado local/efímero (jamás la BD), y HTML limpio (sin la papelera) en el correo.

### Implementación (`RichTextEditor.jsx` + `index.css`)
- Nueva extensión ProseMirror `TableRowActions` (activada por prop `tableRowActions`):
  - **Widget decorations**: una papelera (`matrix-row-delete`) por fila de datos —
    nunca se serializa en `getHTML()`, por lo que no viaja en el correo.
  - **Scope a la matriz**: solo decora la tabla cuyo encabezado contiene
    "Producto / Servicio" (no las tablas de Datos del Cliente/Banco/Implementación);
    excluye la fila de encabezado.
  - **Borrado fiable vía event delegation** (`handleDOMEvents.mousedown`): el handler
    resuelve el rango PM de la fila **síncronamente** (posAtDOM sobre la última celda,
    sin widget) y lo captura en closure; tras 160 ms de transición despacha
    `tr.delete(from, to)`. Esto resolvió 4 causas raíz sucesivas (listener del widget
    recreado por PM, `posAtDOM(tr)=-1`, `trEl` huérfano post-recomposición).
  - CSS global (`.rte-actions`): gutter para la columna de acción, hover de fila en
    rojo (#ef4444), animación `rte-row-removing`.

### Verificación
- Testing agent iter46: **frontend 100% de criterios críticos**, `retest_needed:False`.
  Borrado 3→2→1, scope solo matriz (3 papeleras), hover rojo, un clic sin diálogo,
  sin errores de consola, integridad de BD (recarga→3 filas), Vista Previa con solo
  las filas conservadas. Iteraciones 42-45 documentan la depuración del borrado.


## 2026-06-09 — {Matriz_Bancos_Productos} editable + variable {Patrocinador}

### Requerimiento
(A) Corregir que `{Matriz_Bancos_Productos}` no se poblaba; (B) hacerla editable en
el editor enriquecido de la notificación (editar celdas + eliminar fila), local sin
tocar la BD; (C) nueva variable condicional `{Patrocinador}`.

### Implementación
- **Backend (`project_template_vars.py`)**: nueva variable `{Patrocinador}` — si el
  proyecto es patrocinado (`sponsored_implementation` + `sponsoring_bank_name`) →
  `Banco` o `Banco - Procesador`; si no → Nombre de Fantasía del cliente (fallback a
  nombre/razón social).
- **Backend (`projects.py`)**:
  - **Bug fix crítico** en `_clean_html_in_braces`: el limpiador consumía etiquetas HTML
    adyacentes a las variables, corrompiendo tablas que seguían a una variable
    (ej. `{Patrocinador}<table>`). Reescrito para limpiar solo DENTRO de las llaves.
  - `_style_email_tables`: re-aplica bordes email-safe a tablas sin estilo (la matriz
    editada en TipTap pierde estilos inline). Aplicado en send y preview.
- **Frontend (`RichTextEditor.jsx`)**: añadido `TableKit` (@tiptap/extension-table) →
  las tablas se renderizan y editan; toolbar con "Agregar fila"/"Eliminar fila"; CSS de
  tabla; `StarterKit` con `link:false, underline:false` (evita duplicados en TipTap v3);
  re-render de toolbar en `selectionUpdate`/`transaction` (v3 no re-renderiza solo).
- **Frontend (`ProjectDetail.jsx`)**: `injectMatrix()` sustituye el token
  `{Matriz_Bancos_Productos}` por la tabla real (matrix_html de `/template-variables`) al
  abrir/cambiar plantilla, volviéndola editable in-situ. Chips `{Patrocinador}` añadidos.
- **TemplatesAdminDialog**: `{Patrocinador}` agregado al diccionario de variables.

### Verificación
- 15 pytest PASS (incl. `tests/test_matrix_and_patrocinador.py`).
- Testing agent Iter40 (backend 100%) + Iter41 RETEST frontend 100% (8/8): matriz
  renderiza como tabla poblada, controles de tabla presentes, eliminar/editar fila
  funcionan, preview con tabla modificada, sin warning de duplicados. `retest_needed:False`.


## 2026-06-09 — Plantilla Preferida + Texto Enriquecido en Notificaciones de Proyecto

### Requerimiento
Migrar las notificaciones de Manejo de Proyectos al motor de Texto Enriquecido y
precargar la "Plantilla Preferida" por destino al abrir cada uno de los 3 botones
(Cliente / Banco / Cliente+Banco), manteniendo el dropdown activo para override.

### Implementación
- **Backend (`projects.py`)**:
  - `_resolve_notification_email(..., override_template_id)`: la plantilla seleccionada
    controla asunto y cuerpo en las 3 ramas (client/bank/bank_client). El prefijo por
    conteo (`[Primer Envío]`, etc.) se conserva.
  - `_get_notification_template`: resuelve la plantilla desde la BD o desde los defaults
    de Proyecto (Texto Enriquecido).
  - `send-notification` y `preview-notification` aceptan `template_id` + `custom_html`
    (cuerpo editado) y re-renderizan variables `{Variable}`.
  - **Preferencias por destino** en `db.config` (`type='project_notification_preferences'`):
    `GET/PUT /api/project-notification-preferences` (solo una preferida por destino).
- **Backend (`seed_and_templates.py`)**: `GET /api/email-templates?context=IMPLEMENTACION`
  ahora incluye las plantillas de Proyecto por defecto (`project_notify_*`).
- **Frontend (`ProjectDetail.jsx`)**: el modal de notificación secuencial ahora trae un
  Dropdown de plantillas (`notif-template-select`) precargado con la preferida (badge
  `★ Preferida`), un editor enriquecido editable (`notif-body-editor`) que se actualiza al
  cambiar de plantilla, y un botón `Marcar preferida` (`mark-preferred-btn`). Vista Previa
  y Enviar usan el contenido del editor + `template_id`.

### Verificación
- 5 pytest `tests/test_project_notification_preferred.py` PASS.
- Testing agent Iter39: backend 100% (5/5 unit + 7/7 HTTP e2e), frontend 100% en flujos
  validados (modal único Cliente+Banco, dropdown, cambio de plantilla actualiza editor,
  marcar preferida persiste y se precarga al reabrir). Sin bugs críticos/menores.

### Nota
- En proyectos con UN solo banco, el botón "Notificaciones a Cliente" (`notifications-btn`)
  se reemplaza por "Notificación Única (Cliente y Banco)" (`notif-bank-client-btn`) — diseño
  preexistente. Warnings de hidratación `data-ve-dynamic` son preexistentes (plataforma).


## 2026-06-09 — P0 Homologación + Aislamiento RBAC del Motor de PDF (Opción A)

### Requerimiento
Previsualizar, Exportar y Guardar deben generar EL MISMO PDF para todos los modelos
(VPOS, MPOS, Payment Gateway, Link de Pago), independientemente del RBAC del usuario.
Antes, usuarios con permisos limitados no cargaban catálogos en el frontend →
`buildTemplatePdfData` enviaba nombres vacíos → PDFs con campos en blanco.

### Solución (server-side desde IDs)
- **`pdf_generator.py`**: `TemplateQuotePDFRequest` ahora acepta IDs opcionales
  (`client_id`, `integrator_id`, `pinpad_id`, `sponsor_bank_id`, `sponsor_processor_id`).
- **`quotes.py`**: nueva función única `hydrate_pdf_request(data)` que resuelve los
  nombres AUTORITATIVOS desde Mongo (`clients`, `integrators`, `hardware`, `banks`)
  usando los IDs. Se invoca en los 3 disparadores: `preview-pdf-with-template`,
  `generate-pdf-with-template` y `create-with-pdf` (rama `data.pdf_data`, con relleno
  de IDs desde el top-level de la cotización).
- **`Quotes.jsx`**: `buildTemplatePdfData` ahora incluye SIEMPRE los IDs en el payload
  (además de los nombres como fallback legacy).

### Verificación
- 4 pytest unitarios `tests/test_pdf_hydration_rbac.py` (hidratación, convergencia
  admin==RBAC, no-op sin IDs, etiqueta "Sin integrador") → PASS.
- E2E: payload con nombres VACÍOS + IDs → PDF contiene cliente/banco/integrador/pinpad reales.
- Previsualizar vs Exportar: 9 páginas, texto idéntico (difieren solo en IDs internos de
  subset de fuentes de ReportLab, invisibles para el usuario).
- Testing agent Iter38: backend 7/7, frontend smoke OK, sin regresiones, `retest_needed:false`.

### Pendiente menor (cosmético, fuera de alcance P0)
- `create-with-pdf` puede retornar `client_name` con commercial vs legal_name en el JSON
  (el PDF sale correcto). Warning de hidratación `data-ve-dynamic` en QuotesTable (preexistente).


## 2026-06-08 — FIX PDF Payment Gateway: recurrentes + paridad Guardar/Previsualizar/Exportar

### Bugs reportados
1. La tabla de "Costos Recurrentes Mensuales" NO se insertaba en el PDF al GUARDAR.
2. El PDF al Guardar difería del de Previsualizar y Exportar (versiones distintas).

### Causa raíz
- `handleSubmitPGQuote` (Quotes.jsx) enviaba `pdf_data: null` a `create-with-pdf`, cayendo en
  la rama backend MÍNIMA (custom, sin la tabla rica) en vez de la rama canónica `data.pdf_data`.
- Previsualizar y Exportar construían cada uno su propio `pdfData` con campos distintos
  (Preview sin `branch_details`/`(vinculado a)`; etc.) → 3 PDFs diferentes.

### Fix (frontend, DRY)
- **Nuevo `buildTemplatePdfData(quoteNumber)`** en Quotes.jsx: único builder del payload
  `TemplateQuotePDFRequest` (incluye `pg_recurring_cost.rangos` desde `getPgFullRecurringTable()`).
- **Guardar** ahora envía `pdf_data: buildTemplatePdfData('')` → cae en la rama canónica del
  backend (DynamicQuotePDFGenerator + append_pg_static_pages + stamp).
- **Previsualizar** y **Exportar** reusan el mismo `buildTemplatePdfData()` → eliminan el drift.

### Verificación (curl + extracción de texto del PDF + testing agent iter37)
- PDF guardado, preview y export: los TRES contienen "COSTOS RECURRENTES MENSUALES".
- Preview y Export: **bytes idénticos** (1,058,188), 8 páginas → output idéntico garantizado.
- UI: Previsualizar retornó 200, 0 errores de runtime tras el refactor.

### Nota
- Deuda de lint pre-existente en Quotes.jsx (react-hooks/immutability, set-state-in-effect) NO
  relacionada con este cambio; la app compila OK (webpack). Pendiente refactor dedicado.



## 2026-06-08 — FIX bug fantasma "(failed)" al crear cotizaciones (PG + Reparaciones)

### Causa raíz (confirmada por testing agent iter34-36)
- El POST create-with-pdf se mostraba "(failed)" / `net::ERR_ABORTED` a ~1.12s aunque el
  **backend SÍ creaba la cotización** (~2s, atómico server-side).
- **Disparador:** `frontend/src/utils/api.js` → ante un 401 en CUALQUIER endpoint
  concurrente (notifications/inbox polling, WS), `handleSessionExpired` ejecutaba
  `window.location.href='/login'` a los 600ms → **navegaba y abortaba el XHR del submit en vuelo**.
- El `toast.error` genérico hacía creer al usuario que falló → reintentaba → duplicados (COT-038..043).

### Fixes aplicados (frontend)
1. **`api.js`**: contador `inFlightCritical` (`markCriticalStart/End`, regex de endpoints
   críticos). `redirectWhenIdle` **difiere** `window.location.href='/login'` hasta que terminen
   los POST críticos (create-with-pdf / generate-equipment-pdf) o pasen 15s → ya no aborta el submit.
2. **`EquipmentQuoteWizard.jsx`**: el `fetch` de generate-equipment-pdf se envuelve con
   `markCriticalStart/End` (mismo blindaje para Reparaciones).
3. **Mensajes claros**: en `Quotes.jsx` y `EquipmentQuoteWizard.jsx`, si `!error.response`
   (conexión interrumpida) → `toast.warning('...la cotización pudo haberse creado, verifique el listado')`
   en vez del error engañoso, + refresco automático.
4. **Botón recurrentes**: `QuoteWizardDialog.jsx` L1218 — la sección "Costos Recurrentes" y su
   botón ahora aparecen con `isPaymentGateway && isHeaderComplete && pgRecurringCostsTable`
   (sin requerir setup items); el botón queda deshabilitado con hint si no hay medios de pago.

### Pendiente / recomendación
- 401 intermitentes durante sesión activa → revisar TTL del JWT / refresh proactivo (cambio de
  auth — requiere integración dedicada).
- Opcional: usar `navigate()` de react-router en vez de `window.location.href` para no abortar
  tampoco los XHR no críticos.



## 2026-06-08 — Cont. BUGFIX Cotizaciones + diagnóstico mejorado

### Fix backend confirmado (repair con modelos)
- `quotes.py` L1833: `{total_units}` → `{_total_units}` (NameError → 500). Verificado 200+PDF.

### Diagnóstico del "error fantasma" (PG y Reparaciones)
- Evidencia DIRECTA del navegador (testing agent Iter34): frontend y backend son **same-origin**
  en el preview → **NO es CORS**. POST /api/quotes/create-with-pdf [GATEWAY] devuelve **200**
  desde el navegador real (crea la cotización). El backend tiene éxito en ambos endpoints.
- **Causa del mensaje de error visible:** los `catch` del frontend mostraban mensajes genéricos
  ("Error al crear cotización Payment Gateway" / "Verifique su conexión") que **ocultaban el
  error real** del backend (un 4xx/5xx o una excepción JS al procesar la respuesta/descarga).
- **Fix aplicado:** ambos `catch` ahora exponen el detalle real:
  - `Quotes.jsx` handleSubmitPGQuote → `error.response?.data?.detail || error.message`.
  - `EquipmentQuoteWizard.jsx` → `error.message` (revela TypeError o interrupción de transferencia).
- Deuda técnica conocida: CORS `allow_origins=['*']` + `allow_credentials=True` (inválido por spec,
  pero inofensivo mientras sea same-origin). Considerar `allow_origin_regex='.*'`.



## 2026-06-08 — BUGFIX P0: Creación de Cotizaciones Reparaciones (y verificación PG)

### Bug crítico Reparaciones (reportado en producción) ✅ FIXED
- **Causa raíz:** `backend/routes/quotes.py` línea 1833 — la f-string del resumen por
  modelo usaba `{total_units}` pero la variable definida (línea 1816) es `_total_units`
  → `NameError` en runtime → HTTP 500 al crear cotización de Reparación CON `repair_models`
  (POST /api/quotes/generate-equipment-pdf). El path legacy (bulk_serials) no entraba al
  bloque y por eso no fallaba.
- **Fix:** `{total_units}` → `{_total_units}`. Verificado: 200 + application/pdf con y sin repair_models.
- Test regresivo: `/app/backend/tests/test_quotes_critical_fix.py` (3/3 PASS).
- Testing agent Iter33: backend 3/3 pytest, frontend 10/10 smoke. Sin 5xx.

### Payment Gateway — verificado sin bug propio en preview
- POST /api/quotes/create-with-pdf con quote_type=GATEWAY crea cotización + PDF (200) en preview.
- El error de PG en producción fue probablemente colateral del 500 de Reparaciones o ya resuelto.
  Requiere **redeploy** para llevar el fix a producción.



## 2026-06-08 — Reel mejorado + verificación Patrocinante (Iter32)

### Reel de Distribución — mejoras UX (Proyectos Directos) ✅
- Nuevo campo "Número de cajas (por producto)" (`dp-reel-quantity`): se precarga con la
  "Cantidad de Cajas" de la cabecera y se sincroniza mientras no se edite manualmente
  (`reelQtyTouched` useRef); editable por lote.
- Botón "Seleccionar todos / Quitar todos" (`dp-reel-select-all`).
- "Agregar al Reel" ahora crea UNA línea por cada producto marcado, cada una con el
  número de cajas indicado (sin merge). Tras agregar, limpia la selección y mantiene el
  banco para continuar el siguiente lote.
- Testing agent Iter32: 13/13 frontend PASS.

### Verificación "Banco Patrocinante" (Definición Comercial) ✅ (sin bug en preview)
- Reproducción E2E (UI→API→DB→ProjectDetail): al elegir Procesador y banco vinculado,
  se guarda `patrocinador_label = "Procesador — Banco"` y se muestra completo en la Ficha
  Técnica (`project-detail-patrocinador`) y en el PDF ("Patrocinador de la Implementacion").
  No se detectó bug en preview. Si persiste en producción → requiere redeploy (código stale/caché).


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

## 2026-06 — Paridad absoluta de variables en editores de plantillas (P0)
- Creado `/app/frontend/src/components/email/templateVariables.js` como FUENTE ÚNICA DE VERDAD:
  exporta `VARIABLE_CATEGORIES` (6 grupos, 67 variables), `VARIABLE_ICON_MAP` y `VARIABLE_PREVIEW_HTML`.
- `EmailTemplatesEditor.jsx` (Configuración) y `projects/TemplatesAdminDialog.jsx` (Proyectos)
  ahora importan el catálogo compartido; se eliminaron las listas locales duplicadas/desfasadas
  (`VARIABLE_CATEGORIES` y `VAR_GROUPS`).
- Se agregaron 3 variables que faltaban: `Nro_Proyecto`, `Tipo_Proyecto`, `Fecha_Asignacion`.
- Resultado (Testing agent Iter57): paridad EXACTA 100% — 67 chips idénticos en ambos paneles,
  mismos 6 grupos y mismo orden. Cualquier variable nueva debe agregarse SOLO en templateVariables.js.

## 2026-06 — Buscador de variables + inserción según cursor (mejora UX)
- Ambos editores de plantillas (Configuración y Proyectos) tienen ahora un BUSCADOR
  que filtra los chips por key/label/categoría (data-testid `master-var-search` y `var-search`),
  con mensaje "sin resultados" cuando no hay coincidencias.
- INSERCIÓN POR CURSOR: la variable se inserta en el campo activo (Asunto o Cuerpo) en la
  posición exacta del cursor. Antes siempre caía en el cuerpo.
  - Configuración: `activeField` controlado por onFocus de subject/body (textarea + input).
  - Proyectos: subject Input (id `project-tpl-subject`) + `onFocusCapture` sobre el wrapper
    del RichTextEditor (TipTap). `insertVar()` inserta en asunto (selectionStart) o en el
    editor TipTap (insertText en el cursor).
  - Indicador visual "Insertando en: Asunto/Cuerpo" en ambos paneles.
- Verificado por testing agent (Iter58): 100% frontend. Paridad 67 vars/6 grupos intacta.

## 2026-06 — Reingeniería del Ciclo de Vida de Proyectos (P0)
- **Nuevo catálogo de estados** (reemplaza al anterior): Por asignar · Asignado · En Gestión · Suspendido · Implementado parcial · Culminado. `models.PROJECT_STATUSES` + `PROJECT_MANUAL_STATUSES`.
- **Máquina de estados (automatización)**:
  - Creación (cotización y directo) → 'Por asignar' (o 'Asignado' si la ficha del cliente trae Implementador).
  - Asignar Implementador → 'Asignado' (mantiene 'En Gestión' si ya hay ticket — regla de reasignación).
  - Guardar Nro de Ticket → 'En Gestión' (respeta estados manuales).
  - Manuales: Suspendido / Implementado parcial / Culminado (botón 'Cambiar estado', solo estas 3).
- **Auditoría de queries**: dashboard counts, filtros de grilla/stats, reportes HTML, `sponsor_reports.py`, `notification_scheduler.py` (assigned-not-started='Asignado', stalled='En Gestión'), bulk-reassign.
- **Migración de datos**: `scripts/migrate_project_statuses.py` ejecutado → 76 proyectos remapeados (20 Por asignar, 35 Asignado, 21 En Gestión).
- **Nueva variable {Estado_Proyecto}**: en diccionario compartido (Cotizaciones + Proyectos), `project_template_vars.py` y `notification_engine.py` (busca proyecto por quote_id). Inyecta texto plano del estado.
- **Bug fix Vista Previa (EmailPreviewDialog)**: el cuerpo era contentEditable con `dangerouslySetInnerHTML`; cualquier re-render (p.ej. editar Asunto) re-aplicaba el HTML original y borraba ediciones. Fix: `innerHTML` imperativo vía useEffect SOLO cuando cambia el html de origen (lastHtmlRef). Las ediciones del cuerpo ahora persisten al editar el Asunto.
- Frontend: `Projects.jsx` (STATUS_CONFIG, STATUS_TRANSITIONS, matchStatus, stats chips), `ProjectDetail.jsx` (badge), `BulkReassignModal.jsx`, `templateVariables.js`.
- Verificado: testing agent Iter59 → backend 9/9 pytest, frontend validado. Sin regresiones.

## 2026-06 — Fix Vista Previa (cuerpo vacío) + prefijo al final del asunto
- **Bug Vista Previa (EmailPreviewDialog):** el fix imperativo anterior (useEffect+innerHTML) dejaba el cuerpo VACÍO al abrir. Cambiado a `key={sourceHtml}` + `dangerouslySetInnerHTML={{__html: previewData.html}}`: el contenido se muestra al abrir/regenerar la vista previa, y como editar el Asunto NO cambia `previewData.html`, React no re-monta el contentEditable → las ediciones manuales del cuerpo persisten.
- **Prefijo de secuencia al FINAL del asunto:** en notificaciones a Cliente y Banco, '[Primer Envío]'/'[Primer Recordatorio]'/etc. ahora se concatena al final: `f"{raw_subject} [{prefix_label}]"` (client, bank_client, bank — ramas plantilla y fallback en projects.py L716-838).
- Verificado: testing agent Iter60 → backend 3/3 API, fix de UI confirmado por revisión de código.

## 2026-06 — Optimización de latencia de escritura (Multitienda + Instrucciones)
- **Causa:** el estado vivía en Quotes.jsx (componente enorme); cada tecla en inputs controlados por el padre re-renderizaba todo el modal QuoteModals → latencia.
- **Fix Multitienda:** nuevos componentes memo a nivel de módulo en QuoteModals.jsx:
  - `MultistoreRow` (filas heredadas editables): estado LOCAL + debounce 200ms en el nombre + flush en blur; ref extName/extBox evita reset por sync.
  - `MultistoreAddForm` (agregar tienda): estado LOCAL, propaga al padre solo al Agregar/Enter (callback `appendStore`).
  - Handlers estables `commitStore`/`removeStore`/`appendStore` (functional updates).
- **Fix Instrucciones (Enviar a Implementación):** `handleInstrChange` propaga al padre con debounce 250ms (cache en `implLatestRef`) + `flushInstr` síncrono en `onBlur` del contenedor del RichTextEditor → escribir ya no re-renderiza el modal por tecla y no se pierde texto al continuar.
- Verificado: testing agent Iter61 → 100% frontend, funcionalidad intacta, sin pérdida de datos.
- Deuda técnica menor: `addMultistoreStore`/`multistoreNewStore` en Quotes.jsx quedaron obsoletos (la UI usa MultistoreAddForm); eliminar en limpieza futura.

## 2026-06 — Sincronización Set Up → Costos Recurrentes Básicos (cantidad de cajas)
- Helper `propagateBoxesToRecurring` (Quotes.jsx): al cambiar "Número de Cajas" de un ítem de Set Up, propaga el valor al ítem gemelo de Recurrentes Básicos identificado por `sourceServiceId`/`linkedSetupId`/`linkedTo` (y, como fallback, mismo `medio_pago_name` solo para recurrentes SIN vínculo explícito).
- `updateSetupItem` y `updateAdditionalItem` llaman al helper cuando field='cantidad_cajas' (>0), en un ÚNICO setState (sin parpadeo). Limpia `totalOverride` del gemelo para forzar recálculo.
- Flujo UNIDIRECCIONAL: `updateRecurringBasicItem` NO propaga de vuelta a Set Up.
- Recálculo automático de subtotales/totales (son derivados reactivos de quoteData).
- Verificado: testing agent Iter62 → sincronización + recálculo (subtotal $378→$408 al cambiar 10→25 cajas) + independencia + unidireccionalidad. 100%.

## 2026-06 — Homologación de destinatarios + "Para" editable (Modal Notificaciones Proyectos)
- **CC como tokens:** se reemplazó el campo CC de texto plano (comas) por el componente de tokens del cotizador: `InternalEmailInput` (lista buscable de usuarios internos) + botón "+" para externos (Enter o clic) + chips removibles. Estado nuevo `additionalRecipientsList` (array).
- **"Para" (TO) editable en caliente:** input con autocompletar + "+" (`notif-to-input`/`notif-add-to-btn`) para agregar/corregir el correo principal como token, sin alterar el maestro de Cliente/Banco (efímero por envío).
- **Filtro forzado por roles (backend):** `GET /users/internal-emails?profile=strategic` (helper `_is_strategic_profile`) incluye SOLO Directores (cualquier depto), Ventas Pyme/Corporativas, e Implementación (Implementador/Coordinador/Gerente). Aplica SOLO al modal de Proyectos (`InternalEmailInput profile="strategic"`); el cotizador queda sin filtrar. Verificado: 39 totales → 19 estratégicos.
- **Entrega:** `send-notification` usa `to_override` como TO real (correo corregido) y `additional_recipients` como CC.
- `InternalEmailInput` ahora acepta props `profile` (filtra fetch) y `onEnter`.
- Verificado: testing agent Iter63 → backend 4/4, frontend flujo crítico 100%. Test nuevo: backend/tests/test_internal_emails_filter.py.
- Pendiente menor: agregar data-testid al botón final de envío del modal para E2E.

## 2026-06 — Grupos de destinatarios CC reutilizables (Modal Notificaciones Proyectos)
- Nuevos endpoints (entity_communications.py, colección db.cc_groups): GET/POST/DELETE /api/cc-groups. POST deduplica emails (case-insensitive), exige ≥1 válido, 400 si nombre vacío; upsert por nombre (name_lower). Grupos compartidos por el equipo.
- UI en la tarjeta CC del modal de notificación (ProjectDetail.jsx): enlace 'Guardar selección como grupo' (aparece con tokens CC) → input de nombre + Guardar; lista de chips de grupos (cc-group-{id}) con contador, aplicar (merge+dedupe) y eliminar. Carga vía GET al montar.
- Verificado: testing agent Iter64 → backend 7/7 pytest, frontend E2E 100% (guardar/aplicar/persistencia/eliminar). Test: backend/tests/test_cc_groups.py.
- Backlog menor (sugerencia QA): índice único en cc_groups.name_lower; re-fetch de grupos al abrir el modal.

## 2026-06-12 — Homologación modal "Otras Notificaciones" (Adhoc) con CC + Grupos CC
- **Backend** (`projects.py` → `send_adhoc_email`): el endpoint `POST /api/projects/{id}/send-adhoc-email` ahora acepta `additional_recipients` (Form, JSON array) como CC; filtra inválidos, pasa `cc=(cc_list or None)` a `send_email`. Respuesta incluye `cc` y conteo TO+CC. Bitácora persiste `email_detail.cc` y el texto incluye `CC: ...` solo si hay CC. Retrocompatible (sin el campo → cc=[]).
- **Frontend** (`ProjectDetail.jsx`): el modal Adhoc se homologó con el de Notificaciones — campo TO ahora usa `InternalEmailInput` (profile="strategic") en lugar de input plano+datalist; nueva sección CC con tokens (`adhoc-cc-input`), chips removibles y Grupos CC reutilizables (compartidos, endpoints `/api/cc-groups`). `openEmailDialog` resetea el estado CC; envío directo y desde Vista Previa incluyen `additional_recipients`. Se eliminó el estado `internalUsers` (ya no usado).
- Verificado: testing agent Iter65 → backend 7/7 pytest, frontend E2E 100%. Test: `backend/tests/test_adhoc_email_cc.py`.

## 2026-06-12 — Nueva opción "Datos de Imple" (Implementación) con cascada multisucursal
- **Backend** (`clients.py`): `GET /api/implementation/default-coordinator` (resuelve dinámicamente el usuario con perfil "Coordinador de Administracion"); `PUT /api/clients/{id}/imple-data` aplica 5 campos (tipo_servicio=Componentes, integrador, aplicativo, implementador, coordinador) y los replica EN CASCADA a todas las sucursales del mismo RIF (`update_many({rif})`). Modelo `ImpleDataUpdate` en `models.py`. NO incluye Ejecutivo Propietario.
- **RBAC**: módulo `datos_imple` agregado a `permissions_catalog.py` (grupo gestion_implementacion) → aparece en la matriz de perfiles, niveles Inactivo/Consulta/Edición Total.
- **Frontend**: nueva página `pages/DatosImple.jsx` (tabla de clientes con buscador por nombre/RIF/implementador + modal de edición de solo 5 campos, precarga dinámica de Coordinador, aviso de cascada). Ítem en Sidebar `/datos-imple`, ruta en App.js, mapeos en `usePermission.js`.
- Verificado Iter67: cascada en 6 sucursales (RIF J505366220), independencia entre RIF distintos, ausencia de Ejecutivo Propietario, precarga de coordinador. Test: `backend/tests/test_iteration67_datos_imple.py`.

## 2026-06-12 — Reingeniería "Patrocinador de Pinpads" (Proyectos Directos)
- **UI** (`DirectProjectCreation.jsx`): el campo "Patrocinador de Pinpads" ahora es un control de 3 opciones excluyentes — `dp-pinpad-provider`: "El cliente" / "Infraestructura" / "Un Banco". "Un Banco" muestra el selector Procesador→Banco existente (`dp-pinpad-bank`); las otras muestran nota informativa.
- **Backend** (`direct_projects.py`): nuevo campo `pinpad_provider` ('client'|'infrastructure'|'bank'; vacío legacy→bank). Inyecta en la Ficha (Sección B, fila Patrocinador de Pinpads) la glosa "Los Pinpads son suministrados por el Cliente/Infraestructura" (vía sponsor_bank_name) o el banco/procesador estándar. Persiste `pinpad_provider` en el proyecto.
- **Notificación**: nueva acción configurable `notify_infrastructure_pinpads` (catálogo `action_notifications.py`, permitida en `proyectos_directos`). Al crear un Proyecto Directo con provider='infrastructure' se dispara vía el motor (con Ficha Técnica adjunta), igual mecanismo que "Enviar a Implementación". Config sembrada: destinatario dept. Infraestructura (Martín Ochoa), canal inbox — el admin la ajusta en Configuración → Notificaciones.
- Verificado Iter68: 5/5 backend + UI 3 escenarios. Test: `backend/tests/test_iteration68_pinpad_provider.py`.

## 2026-06-13 · Fix P0: Reporte de Avance ahora soporta Multi-RIF
- Causa raíz: el agente previo solo corrigió 1 de 4 compuertas. Faltaba incluir 'multirif' en: catálogos de filtros (project_reports.py L203), encabezado por tienda del PDF (is_multi L280) y agrupación/filtro de tienda en el modal (ProjectProgressReportDialog.jsx L92).
- Fix: extendidas las 4 compuertas a `in ('multistore','multirif')`.
- Bug MEDIO adicional (hallado por testing_agent iter82): tiendas con mismo nombre ("Altamira" x2) colapsaban en un solo grupo por agrupar por label. Solucionado agrupando por `store_id` (backend `_build_matrix_rows` añade `store_id`; PDF y frontend `groupedRows` agrupan por store_id).
- Validado: JSON avance (4 grupos distintos, 2 Altamira separadas), PDF 200/application/pdf (prj_e586608e3579 30KB, prj_5c3999532fcc 32KB, 2 headers Altamira confirmados por extracción), modal UI verificado por testing_agent (frontend 95%, store filter habilitado, agrupación por tienda OK).
- Pendiente P3 (no bloqueante): hydration warnings `<span data-ve-dynamic>` dentro de <tbody>/<tr> (wrapper de instrumentación de plataforma) y warning a11y Radix en el dialog.
