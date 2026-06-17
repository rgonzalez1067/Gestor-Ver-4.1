import { Boxes, Network } from 'lucide-react';

/**
 * Mini Tablero de Avance Operativo.
 *
 * Refleja en tiempo real el avance del despliegue en dos dimensiones:
 *  - Ecosistema Físico (Cajas configuradas / asignadas)
 *  - Ecosistema Digital (PVV configurados / asignados)
 *
 * Es 100% reactivo: recibe los totales ya agregados sobre el MISMO set de
 * proyectos filtrado que la grilla.
 *
 * Restricción de color (crítica): PROHIBIDO el rojo (reservado para alertas de
 * compromisos vencidos). Se usan bloques sólidos de alto contraste: teal/cyan
 * para lo físico e indigo/azul para lo digital.
 */
const pct = (conf, asig) => (asig > 0 ? Math.min(100, Math.round((conf / asig) * 100)) : 0);

const DualCard = ({ icon: Icon, title, subtitle, configured, assigned, gradient, testid }) => {
  const p = pct(configured, assigned);
  return (
    <div
      className={`relative overflow-hidden rounded-xl p-4 text-white shadow-lg ${gradient}`}
      data-testid={testid}
    >
      <div className="absolute -right-4 -top-4 opacity-10">
        <Icon size={88} strokeWidth={1.5} />
      </div>
      <div className="relative">
        <div className="flex items-center gap-2">
          <Icon size={18} className="text-white/90" />
          <span className="text-sm font-bold uppercase tracking-wide">{title}</span>
        </div>
        <p className="text-[11px] text-white/70 mt-0.5">{subtitle}</p>

        <div className="flex items-end gap-2 mt-3">
          <span className="text-4xl font-extrabold leading-none tabular-nums" data-testid={`${testid}-configured`}>
            {configured}
          </span>
          <span className="text-2xl font-semibold text-white/60 leading-none pb-0.5">
            / <span data-testid={`${testid}-assigned`}>{assigned}</span>
          </span>
        </div>

        <div className="flex items-center justify-between text-[11px] font-medium text-white/80 mt-3 mb-1">
          <span>Configurad{title.includes('PVV') ? 'os' : 'as'}</span>
          <span className="tabular-nums" data-testid={`${testid}-pct`}>{p}%</span>
          <span>Asignad{title.includes('PVV') ? 'os' : 'as'}</span>
        </div>
        <div className="h-2.5 w-full rounded-full bg-white/25 overflow-hidden">
          <div
            className="h-full rounded-full bg-white transition-all duration-500"
            style={{ width: `${p}%` }}
            data-testid={`${testid}-bar`}
          />
        </div>
      </div>
    </div>
  );
};

export const OperationalBoard = ({ metrics, count }) => {
  const m = metrics || { cajasAsig: 0, cajasConf: 0, pvvAsig: 0, pvvConf: 0 };
  return (
    <div className="mb-4" data-testid="operational-board">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          Mini Tablero de Avance Operativo
        </span>
        <span className="text-[11px] text-slate-400">
          · {count} proyecto{count === 1 ? '' : 's'} en vista
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <DualCard
          icon={Boxes}
          title="Avance Físico"
          subtitle="Cajas desplegadas (hardware)"
          configured={m.cajasConf}
          assigned={m.cajasAsig}
          gradient="bg-gradient-to-br from-teal-600 to-cyan-700"
          testid="board-fisico"
        />
        <DualCard
          icon={Network}
          title="Avance Digital · PVV"
          subtitle="Puntos de Venta Virtuales (Cajas × Bancos × Productos)"
          configured={m.pvvConf}
          assigned={m.pvvAsig}
          gradient="bg-gradient-to-br from-indigo-600 to-blue-700"
          testid="board-digital"
        />
      </div>
    </div>
  );
};

export default OperationalBoard;
