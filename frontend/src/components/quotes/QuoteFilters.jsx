import { Filter, X, Search } from 'lucide-react';
import { Button } from '../ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Label } from '../ui/label';
import { Input } from '../ui/input';

const QUOTE_FILTER_CATEGORIES = [
  // Implementación desglosada por tipo de cotización
  { id: 'implementation', name: 'Implementación (todas)' },
  { id: 'implementation:VPOS', name: '  · Implementación VPOS', indent: true },
  { id: 'implementation:MPOS', name: '  · Implementación MPOS', indent: true },
  { id: 'implementation:FAST_TRACK', name: '  · Implementación MPOS Integrada', indent: true },
  { id: 'implementation:GATEWAY', name: '  · Implementación PG', indent: true },
  { id: 'implementation:LINK_PAGO', name: '  · Implementación Link de Pago', indent: true },
  { id: 'equipment', name: 'Equipos y Accesorios' },
  { id: 'repair', name: 'Reparaciones' },
];

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
          <Select value={filterClient} onValueChange={setFilterClient}>
            <SelectTrigger className="h-9 bg-white" data-testid="filter-client">
              <SelectValue placeholder="Todos los clientes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los clientes</SelectItem>
              {clients.map((client) => (
                <SelectItem key={client.client_id} value={client.client_id}>
                  {client.legal_name || client.fantasy_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
              <SelectItem value="Reparada">Reparada</SelectItem>
              <SelectItem value="Facturada">Facturada</SelectItem>
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
