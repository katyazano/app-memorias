import React from 'react';
import { Loader2, ArrowLeft, ArrowRight, Save } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { formatMoney } from '@/lib/utils';

interface TotalesStickyFooterProps {
  totales: Record<string, string> | null;
  recalculando: boolean;
  guardando: boolean;
  onVolver: () => void;
  onGuardarBorrador: () => void;
  onContinuar: () => void;
  modoBorrador?: boolean;
}

export const TotalesStickyFooter: React.FC<TotalesStickyFooterProps> = ({
  totales,
  recalculando,
  guardando,
  onVolver,
  onGuardarBorrador,
  onContinuar,
}) => {
  if (!totales) return null;

  const tieneAnticipos =
    totales.anticipos_total &&
    parseFloat(totales.anticipos_total) > 0;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-zinc-200 shadow-xl transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-2.5">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-3">
          {/* Métricas clave de cálculo */}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs">
            {recalculando && (
              <div className="flex items-center gap-1.5 text-stone-500 font-medium animate-pulse">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-stone-600" />
                <span>Calculando...</span>
              </div>
            )}

            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-semibold text-zinc-400">Transferencias</span>
              <span className="font-mono font-medium text-zinc-800">
                {formatMoney(totales.transferencias)}
              </span>
            </div>

            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-semibold text-zinc-400">Efectivo</span>
              <span className="font-mono font-medium text-zinc-800">
                {formatMoney(totales.efectivo)}
              </span>
            </div>

            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-semibold text-zinc-400">Rayas</span>
              <span className="font-mono font-medium text-zinc-800">
                {formatMoney(totales.rayas)}
              </span>
            </div>

            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-semibold text-zinc-400">
                Honorarios ({totales.porcentaje_honorarios || '0'}%)
              </span>
              <span className="font-mono font-medium text-zinc-800">
                {formatMoney(totales.honorarios)}
              </span>
            </div>

            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-semibold text-zinc-400">IVA 16%</span>
              <span className="font-mono font-medium text-zinc-800">
                {formatMoney(totales.iva)}
              </span>
            </div>

            <div className="h-7 w-[1px] bg-zinc-200 hidden md:block" />

            <div className="flex flex-col bg-stone-100/80 px-2.5 py-0.5 rounded border border-stone-200">
              <span className="text-[10px] uppercase font-bold text-stone-700">Total Memoria</span>
              <span className="font-mono font-bold text-sm text-stone-900">
                {formatMoney(totales.total_memoria)}
              </span>
            </div>

            <div className="flex flex-col">
              <span className="text-[10px] uppercase font-semibold text-zinc-400">Cobrado</span>
              <span className="font-mono font-medium text-zinc-800">
                {formatMoney(totales.cobrado)}
              </span>
            </div>

            {tieneAnticipos && (
              <>
                <div className="flex flex-col">
                  <span className="text-[10px] uppercase font-semibold text-zinc-400">Anticipos</span>
                  <span className="font-mono font-medium text-stone-700">
                    -{formatMoney(totales.anticipos_total)}
                  </span>
                </div>

                {parseFloat(totales.saldo_a_favor || '0') >= 0 ? (
                  <div className="flex flex-col bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    <span className="text-[10px] uppercase font-bold text-emerald-700 whitespace-nowrap">
                      Saldo a favor del arquitecto
                    </span>
                    <span className="font-mono font-bold text-xs text-emerald-900">
                      {formatMoney(totales.saldo_a_favor)}
                    </span>
                  </div>
                ) : (
                  <div className="flex flex-col bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    <span className="text-[10px] uppercase font-bold text-amber-800 whitespace-nowrap">
                      Anticipo pendiente de aplicar
                    </span>
                    <span className="font-mono font-bold text-xs text-amber-900">
                      {formatMoney(Math.abs(parseFloat(totales.saldo_a_favor || '0')))}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Botones de acción */}
          <div className="flex items-center gap-1.5 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={onVolver}
              className="flex items-center gap-1 text-xs px-2.5 py-1"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Volver a Datos</span>
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={onGuardarBorrador}
              disabled={guardando}
              className="flex items-center gap-1 text-xs px-2.5 py-1 border-stone-300"
            >
              {guardando ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Save className="w-3.5 h-3.5" />
              )}
              <span>Guardar Borrador</span>
            </Button>

            <Button
              size="sm"
              onClick={onContinuar}
              className="flex items-center gap-1 text-xs bg-stone-900 hover:bg-stone-800 text-white shadow-xs"
            >
              <span>Continuar a Vista Previa</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
