/**
 * Banner que indica la cantidad de cotizaciones en estado irregular
 * (con pasos saltados pendientes de regularización).
 */
export function IrregularQuotesBanner({ count, onClick }) {
  if (!count) return null;
  return (
    <div
      className="mb-4 flex items-center gap-3 bg-orange-50 border border-orange-200 rounded-lg px-4 py-3 cursor-pointer hover:bg-orange-100 transition-colors"
      onClick={onClick}
      data-testid="irregular-widget"
    >
      <div className="w-10 h-10 rounded-full bg-orange-500 text-white flex items-center justify-center font-bold text-lg shrink-0">
        {count}
      </div>
      <div>
        <p className="text-sm font-semibold text-orange-800">Cotizaciones en Estado Irregular</p>
        <p className="text-xs text-orange-600">Tienen pasos saltados pendientes de regularización</p>
      </div>
    </div>
  );
}

export default IrregularQuotesBanner;
