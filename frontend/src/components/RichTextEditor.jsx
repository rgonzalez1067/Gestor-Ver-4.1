import { useEffect } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import {
  Bold, Italic, Underline as UnderlineIcon, List, ListOrdered,
  AlignLeft, AlignCenter, AlignRight, Palette, Undo2, Redo2,
} from 'lucide-react';
import { cn } from '../lib/utils';

/**
 * RichTextEditor — Editor profesional basado en TipTap.
 * Props:
 *  - value: HTML string (controlado)
 *  - onChange(html, plainTextLength): callback con HTML y longitud de texto visible
 *  - maxChars: límite de texto visible (default 500)
 *  - placeholder: placeholder cuando está vacío
 *  - testid: data-testid root
 */
export function RichTextEditor({ value, onChange, maxChars = 500, placeholder, testid = 'rich-text-editor' }) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: false, codeBlock: false, blockquote: false, horizontalRule: false }),
      Underline,
      TextStyle,
      Color,
      TextAlign.configure({ types: ['paragraph'] }),
    ],
    content: value || '',
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none min-h-[110px] max-h-[260px] overflow-y-auto focus:outline-none px-3 py-2 text-sm',
        'data-testid': `${testid}-content`,
      },
    },
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      const plainText = editor.getText();
      // Hard-cap: si excede, recortamos el texto (TipTap no tiene CharacterCount por defecto sin extensión)
      if (plainText.length > maxChars) {
        // Revertir última transacción manteniendo foco
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

  if (!editor) return null;

  const plainLen = editor.getText().length;
  const pct = Math.min(100, (plainLen / maxChars) * 100);
  const counterColor = plainLen > maxChars * 0.9 ? 'text-orange-600' : 'text-slate-500';

  const Btn = ({ active, onClick, title, children, tid }) => (
    <button
      type="button"
      onMouseDown={(e) => { e.preventDefault(); onClick(); }}
      title={title}
      data-testid={tid}
      className={cn(
        'h-7 w-7 rounded inline-flex items-center justify-center text-slate-600 hover:bg-slate-200 transition',
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
        <Btn active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} title="Negrita (Ctrl+B)" tid={`${testid}-bold`}>
          <Bold size={14} />
        </Btn>
        <Btn active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} title="Cursiva (Ctrl+I)" tid={`${testid}-italic`}>
          <Italic size={14} />
        </Btn>
        <Btn active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} title="Subrayado (Ctrl+U)" tid={`${testid}-underline`}>
          <UnderlineIcon size={14} />
        </Btn>
        <span className="mx-1 h-4 w-px bg-slate-300" />
        <Btn active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()} title="Lista con viñetas" tid={`${testid}-bullet`}>
          <List size={14} />
        </Btn>
        <Btn active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Lista numerada" tid={`${testid}-ordered`}>
          <ListOrdered size={14} />
        </Btn>
        <span className="mx-1 h-4 w-px bg-slate-300" />
        <Btn active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} title="Alinear izquierda" tid={`${testid}-align-left`}>
          <AlignLeft size={14} />
        </Btn>
        <Btn active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} title="Alinear centro" tid={`${testid}-align-center`}>
          <AlignCenter size={14} />
        </Btn>
        <Btn active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} title="Alinear derecha" tid={`${testid}-align-right`}>
          <AlignRight size={14} />
        </Btn>
        <span className="mx-1 h-4 w-px bg-slate-300" />
        <label className="relative inline-flex items-center" title="Color de texto">
          <Palette size={14} className="text-slate-600" />
          <input
            type="color"
            onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
            className="absolute inset-0 opacity-0 cursor-pointer w-5 h-5"
            data-testid={`${testid}-color`}
          />
        </label>
        <span className="mx-1 h-4 w-px bg-slate-300" />
        <Btn onClick={() => editor.chain().focus().undo().run()} title="Deshacer (Ctrl+Z)" tid={`${testid}-undo`}>
          <Undo2 size={14} />
        </Btn>
        <Btn onClick={() => editor.chain().focus().redo().run()} title="Rehacer (Ctrl+Y)" tid={`${testid}-redo`}>
          <Redo2 size={14} />
        </Btn>
      </div>

      {/* Editor */}
      <EditorContent editor={editor} />
      {placeholder && plainLen === 0 && (
        <div className="px-3 pb-1 pt-0 -mt-10 text-sm text-slate-400 italic pointer-events-none">
          {placeholder}
        </div>
      )}

      {/* Counter */}
      <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-3 py-1">
        <div className="h-1 flex-1 bg-slate-200 rounded overflow-hidden mr-3">
          <div className={cn('h-full transition-all', pct > 90 ? 'bg-orange-500' : 'bg-indigo-500')} style={{ width: `${pct}%` }} />
        </div>
        <span className={cn('text-[11px] font-medium tabular-nums', counterColor)} data-testid={`${testid}-counter`}>
          {plainLen}/{maxChars}
        </span>
      </div>
    </div>
  );
}

/** Longitud de texto visible en un HTML. Sanitiza removiendo tags. */
export function htmlPlainLength(html) {
  if (!html) return 0;
  const s = String(html).replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
  return s.length;
}

export default RichTextEditor;
