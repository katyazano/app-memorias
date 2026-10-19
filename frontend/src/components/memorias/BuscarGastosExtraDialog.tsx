import React, { useState } from 'react';
import { Search, Loader2, Plus, AlertCircle, Receipt, HardHat } from 'lucide-react';
import { Dialog } from '@/components/ui/Dialog';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { api } from '@/lib/api';
import { formatDate, formatMoney } from '@/lib/utils';
import type { Gasto, PagoRaya } from '@/types';

interface BuscarGastosExtraDialogProps {
  open: boolean;
  onClose: () => void;
  onAgregarGastos: (gastos: Gasto[]) => void;
  onAgregarRayas: (rayas: PagoRaya[]) => void;
  obraActualId: number;
  gastosYaAgregadosIds: number[];
  rayasYaAgregadasIds: number[];
}

export const BuscarGastosExtraDialog: React.FC<BuscarGastosExtraDialogProps> = ({
  open,
  onClose,
  onAgregarGastos,
  onAgregarRayas,
  obraActualId,
  gastosYaAgregadosIds,
  rayasYaAgregadasIds,
}) => {
  const [tipoBusqueda, setTipoBusqueda] = useState<'gastos' | 'rayas'>('gastos');
  const [q, setQ] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');

  const [resultadosGastos, setResultadosGastos] = useState<Gasto[]>([]);
  const [resultadosRayas, setResultadosRayas] = useState<PagoRaya[]>([]);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [gastosSeleccionados, setGastosSeleccionados] = useState<number[]>([]);
  const [rayasSeleccionadas, setRayasSeleccionadas] = useState<number[]>([]);
  const [busquedaRealizada, setBusquedaRealizada] = useState(false);

  const handleBuscar = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setCargando(true);
    setError(null);
    try {
      if (tipoBusqueda === 'gastos') {
        const res = await api.buscarGastos({
          q: q.trim() || undefined,
          desde: desde || undefined,
          hasta: hasta || undefined,
        });
        const setYa = new Set(gastosYaAgregadosIds);
        setResultadosGastos((res || []).filter((g) => !setYa.has(g.id)));
      } else {
        const res = await api.buscarRayas({
          q: q.trim() || undefined,
          desde: desde || undefined,
          hasta: hasta || undefined,
        });
        const setYa = new Set(rayasYaAgregadasIds);
        setResultadosRayas((res || []).filter((r) => !setYa.has(r.id)));
      }
      setBusquedaRealizada(true);
    } catch (err: any) {
      setError(err.message || 'Error al realizar la búsqueda');
    } finally {
      setCargando(false);
    }
  };

  const toggleSeleccionGasto = (id: number) => {
    setGastosSeleccionados((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const toggleSeleccionRaya = (id: number) => {
    setRayasSeleccionadas((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleConfirmar = () => {
    if (tipoBusqueda === 'gastos') {
      const seleccionados = resultadosGastos.filter((r) => gastosSeleccionados.includes(r.id));
      if (seleccionados.length > 0) onAgregarGastos(seleccionados);
    } else {
      const seleccionadas = resultadosRayas.filter((r) => rayasSeleccionadas.includes(r.id));
      if (seleccionadas.length > 0) onAgregarRayas(seleccionadas);
    }
    onClose();
  };

  const totalSeleccionados =
    tipoBusqueda === 'gastos' ? gastosSeleccionados.length : rayasSeleccionadas.length;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Agregar pagos de otra obra o fuera de rango"
      description="Busca y añade gastos, facturas o rayas registrados en el sistema para incluirlos en esta memoria."
      maxWidth="4xl"
    >
      <div className="space-y-4 p-6">
        {/* Selector de Tipo (Gastos / Rayas) */}
        <div className="flex border-b border-zinc-200">
          <button
            type="button"
            onClick={() => {
              setTipoBusqueda('gastos');
              setBusquedaRealizada(false);
            }}
            className={`flex items-center gap-1.5 py-2 px-4 text-xs font-semibold border-b-2 transition-all ${
              tipoBusqueda === 'gastos'
                ? 'border-stone-900 text-stone-900'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'
            }`}
          >
            <Receipt className="w-3.5 h-3.5" />
            <span>Facturas y Gastos</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setTipoBusqueda('rayas');
              setBusquedaRealizada(false);
            }}
            className={`flex items-center gap-1.5 py-2 px-4 text-xs font-semibold border-b-2 transition-all ${
              tipoBusqueda === 'rayas'
                ? 'border-stone-900 text-stone-900'
                : 'border-transparent text-zinc-500 hover:text-zinc-800'
            }`}
          >
            <HardHat className="w-3.5 h-3.5" />
            <span>Rayas de Albañilería</span>
          </button>
        </div>

        {/* Formulario de búsqueda */}
        <form onSubmit={handleBuscar} className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-zinc-700 mb-1">
              {tipoBusqueda === 'gastos'
                ? 'Buscar por concepto, proveedor o comprobante'
                : 'Buscar por trabajador, oficio, semana u obra'}
            </label>
            <div className="relative">
              <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder={
                  tipoBusqueda === 'gastos'
                    ? 'Ej. Cemento, Flete, Ferretería...'
                    : 'Ej. Juan Pérez, Albañil, Semana 42...'
                }
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">Desde</label>
            <input
              type="date"
              value={desde}
              onChange={(e) => setDesde(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">Hasta</label>
            <div className="flex gap-2">
              <input
                type="date"
                value={hasta}
                onChange={(e) => setHasta(e.target.value)}
                className="w-full px-3 py-1.5 text-xs rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-500"
              />
              <Button type="submit" size="sm" disabled={cargando} className="shrink-0">
                {cargando ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Buscar'}
              </Button>
            </div>
          </div>
        </form>

        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Tabla de resultados */}
        <div className="border border-zinc-200 rounded-lg overflow-hidden max-h-80 overflow-y-auto">
          {cargando ? (
            <div className="p-8 text-center text-xs text-zinc-500 flex flex-col items-center justify-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-stone-600" />
              <span>Buscando en el sistema...</span>
            </div>
          ) : busquedaRealizada &&
            (tipoBusqueda === 'gastos'
              ? resultadosGastos.length === 0
              : resultadosRayas.length === 0) ? (
            <div className="p-8 text-center text-xs text-zinc-500">
              No se encontraron {tipoBusqueda === 'gastos' ? 'gastos' : 'rayas'} con los criterios indicados (o ya están incluidos en esta memoria).
            </div>
          ) : !busquedaRealizada ? (
            <div className="p-8 text-center text-xs text-zinc-400">
              Ingresa un texto o rango de fechas y pulsa "Buscar" para encontrar registros.
            </div>
          ) : tipoBusqueda === 'gastos' ? (
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-600 font-semibold sticky top-0 uppercase text-[10px]">
                <tr>
                  <th className="py-2 px-3 w-8 text-center">
                    <input
                      type="checkbox"
                      checked={
                        resultadosGastos.length > 0 &&
                        gastosSeleccionados.length === resultadosGastos.length
                      }
                      onChange={() => {
                        if (gastosSeleccionados.length === resultadosGastos.length) {
                          setGastosSeleccionados([]);
                        } else {
                          setGastosSeleccionados(resultadosGastos.map((r) => r.id));
                        }
                      }}
                      className="rounded border-zinc-300 text-stone-800 focus:ring-stone-500"
                    />
                  </th>
                  <th className="py-2 px-3">Fecha</th>
                  <th className="py-2 px-3">Obra</th>
                  <th className="py-2 px-3">Proveedor</th>
                  <th className="py-2 px-3">Concepto</th>
                  <th className="py-2 px-3">Comprobante</th>
                  <th className="py-2 px-3">Método</th>
                  <th className="py-2 px-3 text-right">Importe</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {resultadosGastos.map((g) => {
                  const esDeOtraObra = g.obra_id !== obraActualId;
                  const isChecked = gastosSeleccionados.includes(g.id);
                  return (
                    <tr
                      key={g.id}
                      onClick={() => toggleSeleccionGasto(g.id)}
                      className={`cursor-pointer hover:bg-stone-50/70 transition-colors ${
                        isChecked ? 'bg-stone-50' : ''
                      }`}
                    >
                      <td className="py-2 px-3 text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSeleccionGasto(g.id)}
                          className="rounded border-zinc-300 text-stone-800 focus:ring-stone-500"
                        />
                      </td>
                      <td className="py-2 px-3 whitespace-nowrap text-zinc-600">
                        {formatDate(g.fecha)}
                      </td>
                      <td className="py-2 px-3 whitespace-nowrap">
                        {esDeOtraObra ? (
                          <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-700 border-blue-200">
                            {g.obra_nombre}
                          </Badge>
                        ) : (
                          <span className="text-zinc-500 text-[11px]">Misma obra</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-zinc-800 font-medium truncate max-w-[120px]">
                        {g.proveedor_nombre || '—'}
                      </td>
                      <td className="py-2 px-3 text-zinc-700 truncate max-w-[180px]">
                        {g.concepto_resumido}
                      </td>
                      <td className="py-2 px-3 text-zinc-500 font-mono text-[11px] truncate max-w-[100px]">
                        {g.comprobante || '—'}
                      </td>
                      <td className="py-2 px-3 capitalize text-zinc-600 text-[11px]">
                        {g.metodo_pago}
                      </td>
                      <td className="py-2 px-3 text-right font-mono font-semibold text-zinc-900 whitespace-nowrap">
                        {formatMoney(g.importe)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-600 font-semibold sticky top-0 uppercase text-[10px]">
                <tr>
                  <th className="py-2 px-3 w-8 text-center">
                    <input
                      type="checkbox"
                      checked={
                        resultadosRayas.length > 0 &&
                        rayasSeleccionadas.length === resultadosRayas.length
                      }
                      onChange={() => {
                        if (rayasSeleccionadas.length === resultadosRayas.length) {
                          setRayasSeleccionadas([]);
                        } else {
                          setRayasSeleccionadas(resultadosRayas.map((r) => r.id));
                        }
                      }}
                      className="rounded border-zinc-300 text-stone-800 focus:ring-stone-500"
                    />
                  </th>
                  <th className="py-2 px-3">Fecha Fin</th>
                  <th className="py-2 px-3">Semana</th>
                  <th className="py-2 px-3">Trabajador</th>
                  <th className="py-2 px-3">Oficio</th>
                  <th className="py-2 px-3">Detalle</th>
                  <th className="py-2 px-3 text-right">Importe</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {resultadosRayas.map((r) => {
                  const isChecked = rayasSeleccionadas.includes(r.id);
                  return (
                    <tr
                      key={r.id}
                      onClick={() => toggleSeleccionRaya(r.id)}
                      className={`cursor-pointer hover:bg-stone-50/70 transition-colors ${
                        isChecked ? 'bg-stone-50' : ''
                      }`}
                    >
                      <td className="py-2 px-3 text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSeleccionRaya(r.id)}
                          className="rounded border-zinc-300 text-stone-800 focus:ring-stone-500"
                        />
                      </td>
                      <td className="py-2 px-3 whitespace-nowrap text-zinc-600">
                        {formatDate(r.fecha_fin)}
                      </td>
                      <td className="py-2 px-3 whitespace-nowrap font-mono font-medium">
                        Semana {r.semana_numero}
                      </td>
                      <td className="py-2 px-3 text-zinc-900 font-medium">
                        {r.trabajador_nombre}
                      </td>
                      <td className="py-2 px-3 text-zinc-600">
                        {r.oficio || '—'}
                      </td>
                      <td className="py-2 px-3 text-zinc-500 font-mono text-[11px]">
                        {r.cantidad} {r.tipo === 'dia' ? 'días' : 'metros'} a ${r.tarifa}
                      </td>
                      <td className="py-2 px-3 text-right font-mono font-semibold text-zinc-900 whitespace-nowrap">
                        {formatMoney(r.importe)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer del diálogo */}
        <div className="flex items-center justify-between pt-2 border-t border-zinc-100">
          <div className="text-xs text-zinc-500">
            {totalSeleccionados > 0 ? (
              <span className="font-medium text-stone-800">
                {totalSeleccionados} registro(s) seleccionado(s)
              </span>
            ) : (
              <span>Ningún registro seleccionado</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              size="sm"
              disabled={totalSeleccionados === 0}
              onClick={handleConfirmar}
              className="flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>Agregar a la Memoria</span>
            </Button>
          </div>
        </div>
      </div>
    </Dialog>
  );
};
