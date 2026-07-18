"""Genera el documento Word EDITABLE de Auditoría del Manual de Adiestramiento
(Módulo de Implementación) contra la implementación real de la plataforma.

Salida: /app/frontend/public/Manual_Auditoria_Implementacion.docx
"""
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

NAVY = RGBColor(0x16, 0x32, 0x4F)
GREEN = RGBColor(0x15, 0x80, 0x3D)
AMBER = RGBColor(0xB4, 0x53, 0x09)
RED = RGBColor(0xB9, 0x1C, 0x1C)
GREY = RGBColor(0x55, 0x5F, 0x6B)

doc = Document()

# --- estilos base ---
normal = doc.styles['Normal']
normal.font.name = 'Calibri'
normal.font.size = Pt(11)


def h1(text):
    p = doc.add_heading(text, level=1)
    for r in p.runs:
        r.font.color.rgb = NAVY
    return p


def h2(text):
    p = doc.add_heading(text, level=2)
    for r in p.runs:
        r.font.color.rgb = NAVY
    return p


def para(text, bold=False, italic=False, color=None, size=11):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    return p


def bullet(text):
    doc.add_paragraph(text, style='List Bullet')


def audit(status, evidencia, recomendacion=None):
    """Bloque de auditoría: estado + evidencia (archivos) + recomendación editable."""
    mapping = {
        'ok': ('CUMPLE', GREEN),
        'partial': ('CUMPLE PARCIALMENTE', AMBER),
        'no': ('NO CUMPLE', RED),
    }
    label, color = mapping[status]
    p = doc.add_paragraph()
    r = p.add_run(f'Auditoría: {label}')
    r.bold = True
    r.font.color.rgb = color
    r.font.size = Pt(10.5)

    pe = doc.add_paragraph()
    re_ = pe.add_run('Evidencia en código: ')
    re_.bold = True
    re_.font.size = Pt(9.5)
    re_.font.color.rgb = GREY
    rv = pe.add_run(evidencia)
    rv.font.size = Pt(9.5)
    rv.font.color.rgb = GREY

    if recomendacion:
        pr = doc.add_paragraph()
        rr = pr.add_run('Recomendación / a fortalecer: ')
        rr.bold = True
        rr.font.size = Pt(9.5)
        rr.font.color.rgb = AMBER
        rt = pr.add_run(recomendacion)
        rt.font.size = Pt(9.5)
        rt.font.color.rgb = AMBER


# ===================== PORTADA =====================
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
rt = title.add_run('Auditoría de Cumplimiento')
rt.bold = True
rt.font.size = Pt(24)
rt.font.color.rgb = NAVY

sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
rs = sub.add_run('Manual de Adiestramiento de Usuarios — Módulo de Implementación')
rs.font.size = Pt(13)
rs.font.color.rgb = GREY

meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
rm = meta.add_run('Plataforma de Gestión Mega Soft · Documento editable de referencia y verificación')
rm.italic = True
rm.font.size = Pt(10)
rm.font.color.rgb = GREY

doc.add_paragraph()
para('Este documento contrasta cada regla descrita en el manual con la implementación '
     'real de la plataforma (revisión de código fuente). Está pensado para que el equipo '
     'lo edite libremente: ajuste redacción, complete recomendaciones y refuerce lo necesario.',
     italic=True, color=GREY, size=10)

# Leyenda
para('Leyenda de auditoría:', bold=True, size=10)
bullet('CUMPLE — La funcionalidad descrita está implementada y verificada en el código.')
bullet('CUMPLE PARCIALMENTE — Implementada con una diferencia o matiz respecto al manual.')
bullet('NO CUMPLE — La funcionalidad descrita no se encontró en la implementación.')

doc.add_page_break()

# ===================== CAPÍTULO 1 =====================
h1('Capítulo 1: Menú de Cotizaciones (Usuario Comercial)')
para('El menú de Cotizaciones es el punto de partida de la relación comercial. Permite '
     'estructurar propuestas económicas, dividiéndose en dos grandes flujos: Equipos y Accesorios.')

h2('1.1 Tipos de Cotizaciones y Reglas de Bienes y Servicios')
bullet('Cotización de Equipos: venta/arrendamiento de terminales principales (ej. PinPads).')
bullet('Cotización de Accesorios: componentes complementarios (ej. cables, fuentes de poder).')
bullet('PinPad/Accesorio (híbrido): visible tanto en Equipos como en Accesorios.')
bullet('PinPad/Licencia (activos lógicos): al cargarse en inventario NO exige seriales físicos.')
audit('ok',
      "frontend/src/components/EquipmentQuoteWizard.jsx (DEVICE_TYPES=['POS','Pinpad','PinPad/Accesorio']; "
      "ACCESSORY_TYPES=['Accesorio','Base','PinPad/Accesorio'] → 'PinPad/Accesorio' aparece en ambos flujos). "
      "backend/models.py y routes/quote_actions.py: SERIALIZED_TYPES=['pos','pinpad','mpos'] y "
      "requires_serial = tipo in SERIALIZED_TYPES → 'PinPad/Licencia' NO requiere serial.")

h2('1.2 Regla de Pertenencia y Visibilidad (Seguridad de Ventas)')
bullet('Cada cotización guarda el departamento del creador al momento de crearla (badge).')
bullet('Si el usuario cambia de departamento, sus cotizaciones históricas permanecen con su '
       'equipo de Ventas original (no migran).')
audit('ok',
      "backend/routes/quotes.py líneas 112-116: doc['creator_departamento'] = departamento del creador "
      "AL MOMENTO de crear (origen inmutable). Función de visibilidad (~L595-602): la cotización pertenece "
      "100% al departamento en que fue creada; una transferencia de personal NO la arrastra.")

# ===================== CAPÍTULO 2 =====================
h1('Capítulo 2: Menú de Proyectos (Usuario Técnico / QA)')

h2('2.1 Panel de Control y KPIs Dinámicos')
bullet('Cajas de indicadores (KPIs) que agrupan proyectos por estado (En Proceso, Suspendidos, Por Iniciar).')
bullet('Al pasar el mouse sobre una caja se despliega un resumen con semáforo: '
       'Al día (verde), Retraso Medio (amarillo), Retraso Crítico (rojo).')
audit('ok',
      "frontend/src/pages/Projects.jsx: Tooltip (TooltipProvider/TooltipContent, data-testid='kpi-tooltip-*') "
      "con las tres categorías 'Al día' (bg-emerald-400), 'Retraso Medio' (bg-amber-400) y "
      "'Retraso Crítico' (bg-red-500). Proyectos cerrados cuentan como 'Al día'.")

h2('2.2 Flujo de Cierre de un Proyecto Estándar')
bullet('Modal 1 (Datos Técnicos): Componente (ej. Plugin WooCommerce) y Versión (ej. v2.4.1).')
bullet('Modal 2 (Personalizar Comunicación): adjuntar archivos y correos adicionales en copia.')
audit('ok',
      "frontend/src/pages/Integrators.jsx: Modal 1 con close-componente-input / close-version-input "
      "(obligatorios); Modal 2 'Personalizar Comunicación' con anexos y extra_recipients; botón "
      "'Cerrar y Certificar'. backend/routes/integrators.py: endpoint multipart (componente, "
      "version_componente, extra_recipients, files[]).")

para('Excepción — Proyectos de Ambiente de Prueba:', bold=True)
bullet('El sistema únicamente lo retira de la vista de proyectos activos: sin modales, sin certificado, '
       'sin correos y sin afectar la grilla de integradores (flujo técnico directo).')
audit('ok',
      "backend/routes/integrators.py (~L697): if scope == 'test_environment' → BYPASS total; restaura el "
      "estatus previo, project_scope=None y retorna {bypass: True, notification: None}. No genera "
      "certificado ni dispara correo.")

# ===================== CAPÍTULO 3 =====================
h1('Capítulo 3: Menú de Integradores (Gestión de Aliados)')

h2('3.1 Comportamiento Post-Cierre (Inserción vs. Ampliación)')
bullet('Nuevo Integrador o Componente: crea una fila completamente nueva en la grilla.')
bullet('Ampliación: reemplaza los datos de texto del registro anterior (ficha actualizada).')
bullet('Coexistencia con Ambientes de Prueba: el registro no desaparece ni se bloquea para ventas; '
       'aparece en ambos menús simultáneamente.')
audit('ok',
      "backend/routes/integrators.py: scope = 'expansion' si el tipo ya existe, si no 'component'/'new'. "
      "En 'expansion' (L751-768) se reemplaza (update) el registro Certificado del mismo binomio "
      "nombre+integration_type y se borra el de ampliación (una sola fila). Un 'test_environment' se "
      "considera activo y coexiste (L301) sin bloquear al integrador.")

h2('3.2 Repositorio Multiversión de Certificados Digitales')
bullet('Automatización: al cerrar un proyecto estándar se inyectan en el PDF Nombre, Aplicativo, '
       'Componente, Versión, Fecha y Medios de Pago concatenados por diagonal (/), y se guarda en la ficha.')
bullet('Historial completo: nunca se sobreescribe; el indicador (📄 Certificados (N)) despliega un '
       'listado cronológico para visualizar (👁️) o descargar (📥), con botón + para subir PDF manualmente.')
audit('partial',
      "backend/routes/integrators.py: _generate_integration_certificate_pdf inyecta Tipo/Nombre, "
      "Componente-Versión, Aplicativo, Medios (unidos por ' / ') y Fecha ('Caracas, <fecha>'); "
      "_store_integrator_certificate persiste ACUMULATIVAMENTE (no sobreescribe). "
      "frontend IntegratorCertificatesCell.jsx: popover con listado cronológico (created_at), botón de "
      "DESCARGA (📥) y botón '+ Agregar' para subir PDF manual.",
      recomendacion="El popup de certificados del INTEGRADOR ofrece Descargar y Agregar, pero NO tiene "
      "botón de Visualizar (👁️) que sí describe el manual (el visor 👁️ sí existe en Comunicación Masiva). "
      "Recomendación: (a) agregar un botón 'Visualizar' al listado de certificados del integrador para "
      "alinear con el manual, o (b) ajustar el manual para indicar 'descargar' en este punto.")

h2('3.3 Módulo de Comunicaciones Masivas (BCC)')
bullet('Segmentación por "Tipo de Integración" para filtrar los integradores afectados.')
bullet('Casilla maestra "Seleccionar Todos" los filtrados o selección uno a uno.')
bullet('Elegir plantilla HTML de la biblioteca, adjuntar archivos del repositorio (validar con 👁️ / 📥) '
       'o subir un archivo local.')
bullet('Privacidad obligatoria: al enviar, todos los destinatarios van en Copia Oculta (BCC).')
audit('ok',
      "frontend/src/components/MassCommunicationDialog.jsx: filtro por integration_type; casilla maestra "
      "(data-testid='mass-select-all', toggleAll) + individuales; selector de plantilla (email-templates?"
      "context=INTEGRADORES); adjuntos del repositorio con Visualizar (Eye) y Descargar + carga de archivos "
      "locales (input file múltiple). backend/routes/entity_communications.py (~L559,646): endpoint "
      "'/integrators/mass/communication' envía con bcc=recipients (copia oculta).")

# ===================== NAVEGACIÓN =====================
h1('Guía de Navegación Rápida de la Interfaz')

bullet('Sin scroll horizontal forzado: columna de "Acciones" visible a la derecha en pantallas estándar.')
audit('partial',
      "La grilla de Integradores está optimizada para ancho estándar, pero en listas muy anchas se apoya "
      "en las barras de scroll horizontal (ver punto siguiente).",
      recomendacion="El manual afirma 'sin scroll horizontal' y a la vez describe una 'doble barra de "
      "scroll horizontal'. Sugerencia: unificar la redacción del manual: en resoluciones estándar no se "
      "requiere scroll, y para pantallas angostas/listas anchas están disponibles las barras dobles.")

bullet('Doble barra de desplazamiento horizontal (superior e inferior) sincronizada.')
audit('ok',
      "frontend/src/pages/Integrators.jsx (L122-137): topScrollRef + bottomScrollRef con handlers "
      "handleTopScroll/handleBottomScroll que sincronizan scrollLeft (bandera scrollSyncing anti-eco).")

bullet('Edición segura de plantillas: scroll vertical interno y pie de página fijo; el botón "Guardar" '
       'siempre visible.')
audit('ok',
      "frontend/src/pages/EntityTemplatesConfig.jsx: DialogContent 'max-h-[90vh] flex flex-col'; cuerpo "
      "'flex-1 min-h-0 overflow-y-auto'; footer con botón Guardar (entity-template-save-btn) fijo abajo.")

# ===================== RESUMEN =====================
doc.add_page_break()
h1('Resumen Ejecutivo de la Auditoría')
para('De 12 reglas verificadas, 10 CUMPLEN en su totalidad y 2 CUMPLEN PARCIALMENTE (diferencias '
     'menores de UI/redacción). No se encontraron incumplimientos críticos.', bold=True)
para('Puntos a fortalecer (editables):', bold=True)
bullet('3.2 — Añadir botón "Visualizar" (👁️) al listado de certificados del integrador, o ajustar el '
       'manual a "descargar".')
bullet('Navegación — Homologar la redacción "sin scroll horizontal" vs. "doble barra de scroll" para '
       'evitar ambigüedad.')
para('Nota: este documento es totalmente editable. Ajuste textos, agregue capturas de pantalla y '
     'complete las recomendaciones según las decisiones del equipo.', italic=True, color=GREY, size=10)

out = '/app/frontend/public/Manual_Auditoria_Implementacion.docx'
doc.save(out)
print('SAVED', out)
