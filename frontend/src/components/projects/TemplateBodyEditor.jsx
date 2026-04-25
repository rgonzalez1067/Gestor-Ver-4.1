import { useState, useRef } from 'react';
import { ALL_TOKENS } from './projectConstants';

/**
 * Editor de cuerpo de plantilla con resaltado de tokens y autocompletado.
 *
 * Mientras el usuario escribe, si abre `{`, sugiere los tokens disponibles
 * (`Nombre_Cliente`, `Rif_Cliente`, etc.). Tokens completos se resaltan en azul
 * en una capa de fondo absoluta, mientras el textarea queda transparente encima.
 *
 * Aislado en componente propio para que el monolito ProjectDetail.jsx no se
 * re-renderice por cada tecla del editor.
 */
export const TemplateBodyEditor = ({ value, onChange }) => {
  const textareaRef = useRef(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [suggestIdx, setSuggestIdx] = useState(0);
  const [cursorPos, setCursorPos] = useState(0);
  const [braceStart, setBraceStart] = useState(-1);

  const handleChange = (e) => {
    const val = e.target.value;
    const pos = e.target.selectionStart;
    onChange(val);
    setCursorPos(pos);

    // Detect if we're inside a `{...` token being typed
    const before = val.slice(0, pos);
    const lastBrace = before.lastIndexOf('{');
    const lastClose = before.lastIndexOf('}');
    if (lastBrace > lastClose) {
      const partial = before.slice(lastBrace + 1);
      if (!/\s/.test(partial) && partial.length <= 40) {
        const filtered = ALL_TOKENS.filter(t => t.toLowerCase().startsWith(partial.toLowerCase()));
        setSuggestions(filtered);
        setSuggestIdx(0);
        setBraceStart(lastBrace);
        setShowSuggestions(filtered.length > 0);
        return;
      }
    }
    setShowSuggestions(false);
  };

  const insertSuggestion = (token) => {
    const before = value.slice(0, braceStart);
    const after = value.slice(cursorPos);
    const newVal = before + `{${token}}` + after;
    onChange(newVal);
    setShowSuggestions(false);
    setTimeout(() => {
      if (textareaRef.current) {
        const newPos = before.length + token.length + 2;
        textareaRef.current.selectionStart = newPos;
        textareaRef.current.selectionEnd = newPos;
        textareaRef.current.focus();
      }
    }, 0);
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setSuggestIdx(i => Math.min(i + 1, suggestions.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSuggestIdx(i => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter' || e.key === 'Tab') {
      if (suggestions[suggestIdx]) { e.preventDefault(); insertSuggestion(suggestions[suggestIdx]); }
    }
    else if (e.key === 'Escape') { setShowSuggestions(false); }
  };

  const renderHighlighted = () => {
    if (!value) return null;
    const parts = value.split(/(\{[A-Za-z_]+\})/g);
    return parts.map((part, i) =>
      /^\{[A-Za-z_]+\}$/.test(part)
        ? <mark key={i} className="bg-blue-100 text-blue-700 rounded px-0.5 font-mono text-[11px] border border-blue-200" style={{ color: 'transparent', background: 'rgba(219,234,254,0.7)', borderRadius: '3px', padding: '1px 2px' }}>{part}</mark>
        : <span key={i} style={{ color: 'transparent' }}>{part}</span>
    );
  };

  return (
    <div className="relative mt-1" data-testid="template-body-editor">
      <div className="absolute inset-0 pointer-events-none p-3 text-sm whitespace-pre-wrap break-words overflow-hidden font-sans leading-[1.625] select-none"
        aria-hidden="true" style={{ zIndex: 0 }}>
        {renderHighlighted()}
      </div>
      <textarea ref={textareaRef} value={value} onChange={handleChange} onKeyDown={handleKeyDown}
        placeholder="Contenido de la plantilla... Escribe { para autocompletar variables"
        className="w-full text-sm min-h-[200px] resize-y border border-slate-200 rounded-lg p-3 bg-transparent relative focus:ring-2 focus:ring-blue-300 focus:border-blue-400 outline-none leading-[1.625]"
        style={{ zIndex: 1, color: '#1e293b', caretColor: '#1e293b' }}
        data-testid="template-body" />
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 bg-white border border-blue-200 rounded-lg shadow-lg max-h-48 overflow-y-auto w-64 left-4"
          style={{ top: '60px' }} data-testid="token-autocomplete">
          {suggestions.map((s, i) => (
            <button key={s} className={`w-full text-left px-3 py-1.5 text-xs font-mono hover:bg-blue-50 transition-colors ${i === suggestIdx ? 'bg-blue-50 text-blue-700' : 'text-slate-700'}`}
              onMouseDown={(e) => { e.preventDefault(); insertSuggestion(s); }}
              data-testid={`suggest-${s}`}>
              <span className="text-blue-400">{'{'}</span>{s}<span className="text-blue-400">{'}'}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default TemplateBodyEditor;
