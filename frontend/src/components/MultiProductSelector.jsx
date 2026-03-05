import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';
import { ChevronDown, Search, CheckSquare, Square, Plus, X } from 'lucide-react';

export const MultiProductSelector = ({
  products = [],
  existingItems = [],
  bankName = '',
  onAdd,
  disabled = false,
  duplicateKey = 'product_name', // field to check duplicates
  existingKey = 'medio_pago_name', // field in existing items
  existingBankKey = 'bank_name', // field for bank name in existing items
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(new Set());
  const containerRef = useRef(null);

  // Close on click outside
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Reset when products change
  useEffect(() => {
    setSelected(new Set());
    setSearch('');
  }, [products]);

  // Filter products by search and mark duplicates
  const filteredProducts = useMemo(() => {
    const q = search.toLowerCase();
    return products
      .filter(p => p.product_name.toLowerCase().includes(q))
      .map(p => {
        const isDuplicate = existingItems.some(
          item => item[existingKey] === p[duplicateKey] && item[existingBankKey] === bankName
        );
        return { ...p, isDuplicate };
      });
  }, [products, search, existingItems, bankName, duplicateKey, existingKey, existingBankKey]);

  const selectableProducts = filteredProducts.filter(p => !p.isDuplicate);

  const toggleProduct = (productName) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(productName)) next.delete(productName);
      else next.add(productName);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === selectableProducts.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(selectableProducts.map(p => p.product_name)));
    }
  };

  const handleAdd = () => {
    const selectedProducts = products.filter(p => selected.has(p.product_name));
    if (selectedProducts.length === 0) return;
    onAdd(selectedProducts);
    setSelected(new Set());
    setIsOpen(false);
    setSearch('');
  };

  const allSelected = selectableProducts.length > 0 && selected.size === selectableProducts.length;

  if (disabled || products.length === 0) {
    return (
      <div className="relative" ref={containerRef}>
        <button
          disabled
          className="w-full flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-400 cursor-not-allowed"
          data-testid="multi-product-trigger"
        >
          <span>{!disabled ? 'Sin productos disponibles' : 'Seleccione banco primero'}</span>
          <ChevronDown size={16} />
        </button>
      </div>
    );
  }

  return (
    <div className="relative" ref={containerRef}>
      {/* Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between rounded-md border border-slate-300 bg-white px-3 py-2 text-sm hover:border-slate-400 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
        data-testid="multi-product-trigger"
      >
        <span className={selected.size > 0 ? 'text-slate-900 font-medium' : 'text-slate-500'}>
          {selected.size > 0 ? `${selected.size} producto(s) seleccionado(s)` : 'Seleccione medios de pago...'}
        </span>
        <ChevronDown size={16} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Selected tags */}
      {selected.size > 0 && !isOpen && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {[...selected].map(name => (
            <span key={name} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-200">
              {name.length > 30 ? name.substring(0, 30) + '...' : name}
              <X size={12} className="cursor-pointer hover:text-red-500" onClick={() => toggleProduct(name)} />
            </span>
          ))}
        </div>
      )}

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-lg shadow-lg max-h-80 overflow-hidden" data-testid="multi-product-dropdown">
          {/* Search */}
          <div className="p-2 border-b border-slate-100">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar producto..."
                className="pl-8 h-8 text-sm"
                data-testid="multi-product-search"
                autoFocus
              />
            </div>
          </div>

          {/* Select All */}
          <div className="px-2 py-1.5 border-b border-slate-100 flex items-center justify-between">
            <button
              onClick={toggleAll}
              className="flex items-center gap-2 text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors"
              data-testid="multi-product-select-all"
            >
              {allSelected ? <CheckSquare size={14} /> : <Square size={14} />}
              {allSelected ? 'Deseleccionar Todo' : 'Seleccionar Todo'}
            </button>
            <span className="text-xs text-slate-400">{selectableProducts.length} disponibles</span>
          </div>

          {/* Products list */}
          <div className="overflow-y-auto max-h-44 p-1">
            {filteredProducts.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-3">Sin resultados</p>
            ) : (
              filteredProducts.map(product => (
                <label
                  key={product.product_name}
                  className={`flex items-center gap-2.5 px-2 py-1.5 rounded cursor-pointer text-sm transition-colors ${
                    product.isDuplicate
                      ? 'opacity-40 cursor-not-allowed bg-slate-50'
                      : selected.has(product.product_name)
                        ? 'bg-blue-50 text-blue-900'
                        : 'hover:bg-slate-50'
                  }`}
                  data-testid={`multi-product-item-${product.product_name}`}
                >
                  <Checkbox
                    checked={selected.has(product.product_name)}
                    onCheckedChange={() => !product.isDuplicate && toggleProduct(product.product_name)}
                    disabled={product.isDuplicate}
                    className="h-4 w-4"
                  />
                  <span className="flex-1 truncate">{product.product_name}</span>
                  {product.isDuplicate && (
                    <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full shrink-0">Ya agregado</span>
                  )}
                </label>
              ))
            )}
          </div>

          {/* Add button */}
          <div className="p-2 border-t border-slate-100">
            <Button
              onClick={handleAdd}
              disabled={selected.size === 0}
              className="w-full h-8 text-sm bg-blue-600 hover:bg-blue-700"
              data-testid="multi-product-add-btn"
            >
              <Plus size={14} className="mr-1.5" />
              Agregar {selected.size > 0 ? `${selected.size} Medio(s) de Pago` : 'a Cotización'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
