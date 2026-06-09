import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { TableKit } from '@tiptap/extension-table';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import Highlight from '@tiptap/extension-highlight';
import Link from '@tiptap/extension-link';
import {
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  List, ListOrdered, AlignLeft, AlignCenter, AlignRight, AlignJustify,
  Palette, Highlighter, Link as LinkIcon, Eye, X, Undo2, Redo2,
  Rows3, Trash2,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';

/**
 * Mapa por defecto de tokens → valores de ejemplo para Vista Previa.
 * El padre puede extenderlo vía la prop `exampleValues`.
 */
const DEFAULT_EXAMPLE_VALUES = {
  nombre: 'CLIENTE DEMO S.A.',
  rif: 'J-12345678-9',
  email: 'contacto@clientedemo.com',
  contacto: 'María Pérez',
  direccion: 'Av. Principal, Edificio Centro, Piso 3',
  telefono: '+58 212 555-0100',
  nombre_comercial: 'Cliente Demo',
  nombre_integrador: 'Integrador Demo',
  razon_social: 'Integrador Demo, C.A.',
  estado: 'Homologado',
  aplicativo: 'Demo App POS',
  fase: 'Producción',
  producto: 'Producto Demo',
  categoria: 'Software',
  desarrollador: 'Equipo I+D',
  sqa: 'Equipo QA',
  fecha_entrega: '31/03/2026',
  banco: 'Banco Mercantil',
  client_name: 'CLIENTE DEMO S.A.',
  client_rif: 'J-12345678-9',
  client_address: 'Av. Principal, Edificio Centro, Piso 3',
  quote_number: 'COT-2026-001',
  quote_type: 'VPOS',
  total_usd: '1,500.00',
  invoice_number: 'FAC-001234',
  company_name: 'Mega Soft Computación, C.A.',
  sede_name: 'PYME',
  approved_date: '24/02/2026',
  Nombre_Cliente: 'CLIENTE DEMO S.A.',
  Rif_Cliente: 'J-12345678-9',
  Contacto_Principal: 'María Pérez',
  Datos_Contacto: 'María Pérez · +58 212 555-0100 · contacto@clientedemo.com',
  Telefono_Contacto: '+58 212 555-0100',
  Email_Contacto: 'contacto@clientedemo.com',
  Cotizacion_Nro: 'COT-2026-001',
  nro_cotizacion: 'COT-2026-001',
  Monto_Total: '1,500.00',
  Referencia_Factura: 'FAC-EQ-2026-001',
  Nombre_Ejecutivo: 'Rafael González',
  Email_Ejecutivo: 'rgonzalez@megasoft.com.ve',
  Nombre_Implementador: 'Carlos Rodríguez',
  Correo_Implementador: 'crodriguez@meganexus.com',
  Telefono_Implementador: '+58 412 555-0123',
  Integrador: 'A2 Softway C.A.',
  Aplicativo_Integracion: 'A2 Softway POS',
  Nombre_Sucursal: 'Sede Norte',
  Cantidad_Cajas: '5',
  project_number: 'PRY-2026-03-001-PRI',
  ticket_number: '56785',
  Nro_Proyecto: 'PRY-2026-03-001-PRI',
  Ticket_Nro: '56785',
  Nro_Ticket: '56785',
  Fecha_Asignacion: '24/02/2026',
  Fecha_Desbloqueo_Ticket: '25/02/2026',
  Tipo_Proyecto: 'VPOS',
  bank_name: 'Banco Mercantil',
  notification_level: 'Primera Comunicación',
  notification_subject: 'Notificación de Implementación',
  assigned_to: 'Carlos Rodríguez',
  Direccion_Entrega: 'Av. Libertador, CC Galerías, Local 5',
  Modelo_Equipo: 'Verifone P400',
  Cantidad: '5',
  Banco_Destino: 'Banco Mercantil',
  Patrocinador: 'Banco Mercantil',
};

/** Reemplaza tokens {{var}} y {var} con valores de ejemplo (o [var] si no existe). */
export function substituteTokens(html, extra = {}) {
  const values = { ...DEFAULT_EXAMPLE_VALUES, ...(extra || {}) };
  let out = String(html || '');
  out = out.replace(/\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g, (_, k) => (values[k] !== undefined ? String(values[k]) : `[${k}]`));
  out = out.replace(/\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}/g, (_, k) => (values[k] !== undefined ? String(values[k]) : `[${k}]`));
  return out;
}

/** Devuelve el valor demo asociado a un token (o null si no existe). */
export function getExampleValue(token, extra = {}) {
  const values = { ...DEFAULT_EXAMPLE_VALUES, ...(extra || {}) };
  return values[token] !== undefined ? String(values[token]) : null;
}

const BG_COLORS = ['#FEF3C7', '#FECACA', '#BBF7D0', '#BFDBFE', '#E9D5FF', '#FCE7F3', '#FED7AA'];

/**
 * RichTextEditor — Editor WYSIWYG basado en TipTap.
 * Props:
 *  - value, onChange(html, plainTextLength)
 *  - maxChars (límite de texto visible, default 500)
 *  - hardLimit (default true): si true, revierte ediciones que superan maxChars.
 *      Para plantillas largas pase hardLimit={false} con maxChars alto (ej 20000).
 *  - placeholder, testid
 *  - showPreview (default false): muestra botón Vista Previa con substitución de tokens
 *  - exampleValues: objeto con tokens custom de la pantalla actual
 */
export const RichTextEditor = forwardRef(function RichTextEditor({
  value,
  onChange,
  maxChars = 500,
  hardLimit = true,
  placeholder,
  testid = 'rich-text-editor',
  showPreview = false,
  exampleValues = null,
  minHeight = 110,
  maxHeight = 260,
}, ref) {
  const [showHighlights, setShowHighlights] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: false, codeBlock: false, blockquote: false, horizontalRule: false, link: false, underline: false }),
      Underline,
      TableKit.configure({ table: { resizable: false, HTMLAttributes: { class: 'rte-table' } } }),
      TextStyle,
      Color,
      Highlight.configure({ multicolor: true }),
      TextAlign.configure({ types: ['paragraph'] }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank', class: 'text-blue-600 underline' },
      }),
    ],
    content: value || '',
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none focus:outline-none px-3 py-2 text-sm',
        style: `min-height:${minHeight}px;max-height:${maxHeight}px;overflow-y:auto;`,
        'data-testid': `${testid}-content`,
      },
    },
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const plainText = editor.getText();
      if (hardLimit && plainText.length > maxChars) {
        editor.commands.undo();
        return;
      }
      onChange && onChange(html, plainText.length);
    },
  });

  useEffect(() => {
    if (editor && value !== undefined && value !== editor.getHTML()) {
      editor.commands.setContent(value || '', false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Forzar re-render de la toolbar al cambiar la selección/contenido (TipTap v3 no
  // re-renderiza por sí solo), para que los estados activos y los controles de
  // tabla (Agregar/Eliminar fila) aparezcan al situar el cursor dentro de la matriz.
  const [, forceTick] = useState(0);
  useEffect(() => {
    if (!editor) return;
    const bump = () => forceTick((t) => t + 1);
    editor.on('selectionUpdate', bump);
    editor.on('transaction', bump);
    return () => {
      editor.off('selectionUpdate', bump);
      editor.off('transaction', bump);
    };
  }, [editor]);

  // Exponemos métodos imperativos para que el padre pueda insertar texto
  // (ej. variables {token}) en la posición exacta del cursor.
  useImperativeHandle(ref, () => ({
    insertText: (text) => {
      if (!editor || !text) return;
      editor.chain().focus().insertContent(String(text)).run();
    },
    focus: () => editor?.chain().focus().run(),
    getHTML: () => editor?.getHTML() || '',
  }), [editor]);

  if (!editor) return null;

  const plainLen = editor.getText().length;
  const pct = Math.min(100, (plainLen / maxChars) * 100);
  const overWarn = plainLen > maxChars * 0.9;
  const counterColor = plainLen >= maxChars ? 'text-rose-600' : overWarn ? 'text-orange-600' : 'text-slate-500';

  const addLink = () => {
    const previous = editor.getAttributes('link').href || '';
    const url = window.prompt('URL del enlace (incluya http:// o https://):', previous);
    if (url === null) return;
    if (url === '') { editor.chain().focus().extendMarkRange('link').unsetLink().run(); return; }
    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  };

  const Btn = ({ active, onClick, title, children, tid, disabled }) => (
    <button
      type="button"
      disabled={disabled}
      onMouseDown={(e) => { e.preventDefault(); if (!disabled) onClick(); }}
      title={title}
      data-testid={tid}
      className={cn(
        'h-7 w-7 rounded inline-flex items-center justify-center text-slate-600 hover:bg-slate-200 transition disabled:opacity-40',
        active && 'bg-indigo-100 text-indigo-700',
      )}
    >
      {children}
    </button>
  );

  return (
    <div className="border border-slate-300 rounded-md bg-white overflow-hidden" data-testid={testid}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-0.5 border-b border-slate-200 bg-slate-50 px-2 py-1">
        <Btn active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} title="Negrita (Ctrl+B)" tid={`${testid}-bold`}><Bold size={14} /></Btn>
        <Btn active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} title="Cursiva (Ctrl+I)" tid={`${testid}-italic`}><Italic size={14} /></Btn>
        <Btn active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} title="Subrayado (Ctrl+U)" tid={`${testid}-underline`}><UnderlineIcon size={14} /></Btn>
        <Btn active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()} title="Tachado" tid={`${testid}-strike`}><Strikethrough size={14} /></Btn>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()} title="Lista con viñetas" tid={`${testid}-bullet`}><List size={14} /></Btn>
        <Btn active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Lista numerada" tid={`${testid}-ordered`}><ListOrdered size={14} /></Btn>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} title="Alinear izquierda" tid={`${testid}-align-left`}><AlignLeft size={14} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} title="Alinear centro" tid={`${testid}-align-center`}><AlignCenter size={14} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} title="Alinear derecha" tid={`${testid}-align-right`}><AlignRight size={14} /></Btn>
        <Btn active={editor.isActive({ textAlign: 'justify' })} onClick={() => editor.chain().focus().setTextAlign('justify').run()} title="Justificar" tid={`${testid}-align-justify`}><AlignJustify size={14} /></Btn>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        {/* Color de fuente (native picker) */}
        <label className="relative inline-flex items-center justify-center h-7 w-7 rounded hover:bg-slate-200 cursor-pointer" title="Color de texto">
          <Palette size={14} className="text-slate-600" />
          <input
            type="color"
            onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
            className="absolute inset-0 opacity-0 cursor-pointer"
            data-testid={`${testid}-color`}
          />
        </label>

        {/* Color de fondo / Highlight (popover) */}
        <div className="relative">
          <Btn
            active={showHighlights || editor.isActive('highlight')}
            onClick={() => setShowHighlights((v) => !v)}
            title="Color de fondo (resaltar)"
            tid={`${testid}-highlight-toggle`}
          ><Highlighter size={14} /></Btn>
          {showHighlights && (
            <div
              className="absolute z-50 top-8 left-0 bg-white border border-slate-200 rounded-md shadow-lg p-1.5 flex gap-1"
              data-testid={`${testid}-highlight-palette`}
            >
              {BG_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { editor.chain().focus().toggleHighlight({ color: c }).run(); setShowHighlights(false); }}
                  className="w-5 h-5 rounded border border-slate-200 hover:scale-110 transition"
                  style={{ background: c }}
                  title={c}
                  data-testid={`${testid}-highlight-${c.replace('#', '')}`}
                />
              ))}
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => { editor.chain().focus().unsetHighlight().run(); setShowHighlights(false); }}
                className="text-[10px] text-slate-500 hover:text-slate-700 px-1"
                title="Quitar resaltado"
              >×</button>
            </div>
          )}
        </div>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn active={editor.isActive('link')} onClick={addLink} title="Insertar enlace" tid={`${testid}-link`}><LinkIcon size={14} /></Btn>

        <span className="mx-1 h-4 w-px bg-slate-300" />

        <Btn onClick={() => editor.chain().focus().undo().run()} title="Deshacer (Ctrl+Z)" tid={`${testid}-undo`}><Undo2 size={14} /></Btn>
        <Btn onClick={() => editor.chain().focus().redo().run()} title="Rehacer (Ctrl+Y)" tid={`${testid}-redo`}><Redo2 size={14} /></Btn>

        {/* Controles de tabla — para la Matriz de Bancos/Productos (activos dentro de una tabla) */}
        <span className="mx-1 h-4 w-px bg-slate-300" />
        <Btn disabled={!editor.can().addRowAfter?.()} onClick={() => editor.chain().focus().addRowAfter().run()} title="Agregar fila debajo" tid={`${testid}-table-add-row`}><Rows3 size={14} /></Btn>
        <Btn disabled={!editor.can().deleteRow?.()} onClick={() => editor.chain().focus().deleteRow().run()} title="Eliminar fila" tid={`${testid}-table-del-row`}><Trash2 size={14} /></Btn>

        {showPreview && (
          <>
            <span className="flex-1" />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPreviewOpen(true)}
              className="h-7 text-xs gap-1"
              data-testid={`${testid}-preview-btn`}
            >
              <Eye size={13} /> Vista Previa
            </Button>
          </>
        )}
      </div>

      {/* Estilos de tabla dentro del editor (Matriz de Bancos/Productos editable) */}
      <style>{`
        [data-testid="${testid}"] .ProseMirror table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 13px; table-layout: fixed; overflow: hidden; }
        [data-testid="${testid}"] .ProseMirror td, [data-testid="${testid}"] .ProseMirror th { border: 1px solid #d1d5db; padding: 6px 10px; vertical-align: top; position: relative; }
        [data-testid="${testid}"] .ProseMirror th { background: #2c3e50; color: #fff; text-align: left; font-weight: 600; }
        [data-testid="${testid}"] .ProseMirror .selectedCell:after { background: rgba(99,102,241,0.18); content: ""; position: absolute; inset: 0; pointer-events: none; }
        [data-testid="${testid}"] .ProseMirror table p { margin: 0; }
      `}</style>

      {/* Editor */}
      <EditorContent editor={editor} />
      {placeholder && plainLen === 0 && (
        <div className="px-3 pb-1 pt-0 -mt-10 text-sm text-slate-400 italic pointer-events-none">
          {placeholder}
        </div>
      )}

      {/* Counter */}
      <div className="flex items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-3 py-1">
        <div className="h-1 flex-1 bg-slate-200 rounded overflow-hidden">
          <div
            className={cn('h-full transition-all', pct >= 100 ? 'bg-rose-500' : pct > 90 ? 'bg-orange-500' : 'bg-indigo-500')}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={cn('text-[11px] font-medium tabular-nums whitespace-nowrap', counterColor)} data-testid={`${testid}-counter`}>
          {plainLen}/{maxChars}
        </span>
      </div>

      {showPreview && (
        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent className="max-w-2xl" data-testid={`${testid}-preview-dialog`}>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Eye className="text-blue-600" size={18} /> Vista Previa del Correo
              </DialogTitle>
            </DialogHeader>
            <div className="border rounded-lg p-4 bg-white max-h-[60vh] overflow-y-auto">
              <div
                className="prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: substituteTokens(editor.getHTML(), exampleValues) }}
                data-testid={`${testid}-preview-body`}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPreviewOpen(false)}>
                <X size={14} className="mr-1" /> Cerrar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
});

/** Longitud de texto visible en un HTML. Sanitiza removiendo tags. */
export function htmlPlainLength(html) {
  if (!html) return 0;
  const s = String(html).replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
  return s.length;
}

export default RichTextEditor;
