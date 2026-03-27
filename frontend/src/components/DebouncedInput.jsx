import React, { useState, useCallback, useRef, useEffect, memo } from 'react';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';

/**
 * DebouncedInput — Campo de texto optimizado contra Input Lag.
 * 
 * Maneja estado LOCAL internamente. Solo sincroniza con el padre en:
 *   - onBlur (el usuario sale del campo)
 *   - Después de `debounceMs` ms sin teclear (si se proporciona)
 * 
 * Props:
 *   value        — valor controlado desde el padre
 *   onCommit     — fn(newValue) llamada en blur o tras debounce
 *   debounceMs   — (opcional) ms para debounce. 0 = solo onBlur
 *   as           — 'input' | 'textarea' (default: 'input')
 *   ...rest      — se pasan al Input/Textarea subyacente
 */
const DebouncedInput = memo(function DebouncedInput({
  value: externalValue,
  onCommit,
  debounceMs = 0,
  as = 'input',
  onChange: _externalOnChange, // extracted but NOT used during typing
  ...rest
}) {
  const [localValue, setLocalValue] = useState(externalValue ?? '');
  const timerRef = useRef(null);
  const committedRef = useRef(externalValue);

  // Sincronizar si el padre cambia el valor externamente (ej: reset de formulario)
  useEffect(() => {
    if (externalValue !== committedRef.current) {
      setLocalValue(externalValue ?? '');
      committedRef.current = externalValue;
    }
  }, [externalValue]);

  const commit = useCallback((val) => {
    committedRef.current = val;
    if (onCommit) onCommit(val);
  }, [onCommit]);

  const handleChange = useCallback((e) => {
    const val = e.target.value;
    setLocalValue(val);
    // NO se propaga onChange al padre — estado 100% local durante escritura
    if (debounceMs > 0) {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => commit(val), debounceMs);
    }
  }, [debounceMs, commit]);

  const handleBlur = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    commit(localValue);
  }, [localValue, commit]);

  // Cleanup timer on unmount
  useEffect(() => () => { if (timerRef.current) clearTimeout(timerRef.current); }, []);

  const Component = as === 'textarea' ? Textarea : Input;

  return (
    <Component
      {...rest}
      value={localValue}
      onChange={handleChange}
      onBlur={handleBlur}
    />
  );
});

export default DebouncedInput;
