import { useState, useMemo } from 'react';
import { Filter, X, Search, ChevronDown } from 'lucide-react';
import { Button } from '../ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';

const QUOTE_FILTER_CATEGORIES = [
  // Implementación desglosada por tipo de cotización
  { id: 'implementation', name: 'Implementación (todas)' },
  { id: 'implementation:VPOS', name: '  · Implementación VPOS', indent: true },
  { id: 'implementation:MPOS', name: '  · Implementación MPOS', indent: true },
  { id: 'implementation:FAST_TRACK', name: '  · Implementación MPOS (Imple + POS)', indent: true },
  { id: 'implementation:GATEWAY', name: '  · Implementación PG', indent: true },
  { id: 'implementation:LINK_PAGO', name: '  · Implementación Link de Pago', indent: true },
  { id: 'implementation:LINK_PAGO:link_pago', name: '      › Solo Link de Pago', indent: true },
  { id: 'implementation:LINK_PAGO:tokenizador', name: '      › Solo Tokenizador', indent: true },
  { id: 'implementation:LINK_PAGO:ambos', name: '      › Solo Link/Tokenizador', indent: true },
  { id: 'equipment', name: 'Equipos y Accesorios' },
  { id: 'repair', name: 'Reparaciones' },
];

// Buscador predictivo de clientes (input text + listado filtrado)
// Reemplaza el Select estándar para evitar scroll manual con muchos clientes.
const ClientSearchableSelect = ({ clients, value, onChange }) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  // Agrupar por legal_name (mismo nombre → un solo item con todos los IDs)
  const groups = useMemo(() => {
    const acc = {};
    (clients || []).forEach((c) => {
      const key = (c.legal_name || c.fantasy_name || '').trim().toUpperCase();
      if (!key) return;
      (acc[key] = acc[key] || { name: c.legal_name || c.fantasy_name, ids: [] }).ids.push(c.client_id);
    });
    return Object.values(acc).sort((a, b) => a.name.localeCompare(b.name, 'es', { sensitivity: 'base' }));
  }, [clients]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return groups;
    return groups.filter((g) => g.name.toLowerCase().includes(q));
  }, [groups, query]);

  // Texto a mostrar en el trigger según el value seleccionado
  const selectedLabel = useMemo(() => {
    if (!value || value === 'all') return 'Todos los clientes';
    const found = groups.find((g) => g.ids.join(',') === value);
    return found ? found.name : 'Cliente filtrado';
  }, [value, groups]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="h-9 w-full px-3 rounded-md border border-input bg-white flex items-center justify-between text-sm hover:bg-slate-50"
          data-testid="filter-client">
          <span className="truncate text-left">{selectedLabel}</span>
          <ChevronDown size={14} className="text-slate-400 shrink-0 ml-2" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-0" align="start">
        <div className="p-2 border-b">
          <div className="relative">
            <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar cliente..."
              className="h-8 pl-7 text-sm"
              data-testid="filter-client-search" />
          </div>
        </div>
        <div className="max-h-64 overflow-y-auto py-1" data-testid="filter-client-options">
          <button
            type="button"
            className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${(!value || value === 'all') ? 'bg-slate-50 font-medium' : ''}`}
            onClick={() => { onChange('all'); setOpen(false); setQuery(''); }}
            data-testid="filter-client-option-all">
            Todos los clientes
          </button>
          {filtered.length === 0 && (
            <p className="px-3 py-3 text-xs text-slate-400 text-center">Sin coincidencias</p>
          )}
          {filtered.map((g) => {
            const v = g.ids.join(',');
            const isSel = v === value;
            return (
              <button
                key={v}
                type="button"
                className={`w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100 ${isSel ? 'bg-blue-50 text-blue-700 font-medium' : ''}`}
                onClick={() => { onChange(v); setOpen(false); setQuery(''); }}
                data-testid={`filter-client-option-${v}`}>
                {g.name}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export const QuoteFilters = ({
  clients,
  filterClient, setFilterClient,
  filterStatus, setFilterStatus,
  filterCategory, setFilterCategory,
  filterSegment, setFilterSegment,
  filterDateFrom, setFilterDateFrom,
  filterDateTo, setFilterDateTo,
}) => {
  const clearFilters = () => {
    setFilterClient('');
    setFilterStatus('');
    setFilterCategory('');
    setFilterSegment('');
    setFilterDateFrom('');
    setFilterDateTo('');
  };

  const hasFilters = filterClient || filterStatus || filterCategory || filterSegment || filterDateFrom || filterDateTo;

  return (
    <div className="bg-slate-50 rounded-lg p-4 mb-4 border border-slate-200" data-testid="quote-filters">
      <div className="flex items-center gap-2 mb-3">
        <Filter size={18} className="text-slate-500" />
        <span className="font-medium text-slate-700">Filtros Rápidos</span>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}
            className="text-red-500 hover:text-red-700 ml-auto" data-testid="clear-filters-btn">
            <X size={14} className="mr-1" /> Limpiar filtros
          </Button>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
        <div>
          <Label className="text-xs text-slate-500 mb-1 block">Cliente</Label>
          <ClientSearchableSelect clients={clients} value={filterClient} onChange={setFilterClient} />
        </div>

        <div>
          <Label className="text-xs text-slate-500 mb-1 block">Estado</Label>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="h-9 bg-white" data-testid="filter-status">
              <SelectValue placeholder="Todos los estados" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los estados</SelectItem>
              <SelectItem value="Borrador">Borrador</SelectItem>
              <SelectItem value="Enviada">Enviada</SelectItem>
              <SelectItem value="Aprobada">Aprobada</SelectItem>
              <SelectItem value="Preasign">Preasign (Seriales Reservados)</SelectItem>
              <SelectItem value="Reparada">Reparada</SelectItem>
              <SelectItem value="Facturada">Facturada</SelectItem>
              <SelectItem value="Validar Pago">Validar Pago</SelectItem>
              <SelectItem value="Pagada">Pagada</SelectItem>
              <SelectItem value="Entregada">Entregada (Equipos)</SelectItem>
              <SelectItem value="Enviada a Imple">Enviada a Imple</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label className="text-xs text-slate-500 mb-1 block">Categoría</Label>
          <Select value={filterCategory} onValueChange={setFilterCategory}>
            <SelectTrigger className="h-9 bg-white" data-testid="filter-category">
              <SelectValue placeholder="Todas las categorías" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las categorías</SelectItem>
              {QUOTE_FILTER_CATEGORIES.map((cat) => (
                <SelectItem key={cat.id} value={cat.id}>{cat.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label className="text-xs text-slate-500 mb-1 block">Segmento</Label>
          <Select value={filterSegment} onValueChange={setFilterSegment}>
            <SelectTrigger className="h-9 bg-white" data-testid="filter-segment">
              <SelectValue placeholder="Todos" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="PYME">Pyme</SelectItem>
              <SelectItem value="CORP">Corporativo</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label className="text-xs text-slate-500 mb-1 block">Desde</Label>
          <Input type="date" value={filterDateFrom} onChange={(e) => setFilterDateFrom(e.target.value)}
            className="h-9 bg-white" data-testid="filter-date-from" />
        </div>

        <div>
          <Label className="text-xs text-slate-500 mb-1 block">Hasta</Label>
          <Input type="date" value={filterDateTo} onChange={(e) => setFilterDateTo(e.target.value)}
            className="h-9 bg-white" data-testid="filter-date-to" />
        </div>
      </div>
    </div>
  );
};
