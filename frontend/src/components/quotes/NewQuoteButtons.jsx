import { Plus, ChevronDown, Users, Building2 } from 'lucide-react';
import { Button } from '../ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../ui/dropdown-menu';

/**
 * Barra de botones para crear nuevas cotizaciones, con visibilidad por
 * permisos especiales (rbac).
 */
export function NewQuoteButtons({ rbac, onOpenImpl, onOpenEquipment, onOpenRepair }) {
  if (!rbac.showButtons) return null;

  return (
    <div className="flex items-center gap-3 mb-6">
      {rbac.hasAnyImpl && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button data-testid="create-quote-button" className="bg-brand-green-600 hover:bg-brand-green-700 text-white">
              <Plus size={20} className="mr-2" />
              Implementaciones
              <ChevronDown size={16} className="ml-2" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            {rbac.hasImplPyme && (
              <DropdownMenuItem onClick={() => onOpenImpl('PYME')} className="py-3 cursor-pointer" data-testid="new-impl-pyme">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-emerald-100 flex items-center justify-center">
                    <Users size={16} className="text-emerald-700" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">Clientes Pymes</p>
                    <p className="text-xs text-slate-500">VPOS, MPOS, Gateway, Link de Pago</p>
                  </div>
                </div>
              </DropdownMenuItem>
            )}
            {rbac.hasImplCorp && (
              <DropdownMenuItem onClick={() => onOpenImpl('CORP')} className="py-3 cursor-pointer" data-testid="new-impl-corp">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
                    <Building2 size={16} className="text-blue-700" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">Clientes Corporativos</p>
                    <p className="text-xs text-slate-500">Proyectos de gran envergadura</p>
                  </div>
                </div>
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      {rbac.hasEquipos && (
        <Button
          onClick={onOpenEquipment}
          data-testid="create-equipment-quote-button"
          className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white"
        >
          <Plus size={20} className="mr-2" />
          Equipos y Accesorios
        </Button>
      )}

      {rbac.hasReparaciones && (
        <Button
          onClick={onOpenRepair}
          data-testid="create-repair-quote-button"
          className="bg-amber-600 hover:bg-amber-700 text-white"
        >
          <Plus size={20} className="mr-2" />
          Reparaciones
        </Button>
      )}
    </div>
  );
}

export default NewQuoteButtons;
