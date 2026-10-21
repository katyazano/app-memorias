import React, { useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Printer, ArrowLeft, Loader2, AlertCircle, FileDown, FileSpreadsheet } from 'lucide-react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { formatDate, formatMoneySimple, formatRangoSemana, formatFechaLarga, formatTextoEnLetra, formatFolioFactura } from '@/lib/utils';
import type { Memoria, RenglonMemoria } from '@/types';

interface SemanaAgrupada {
  semana: number;
  tipo: string;
  rangoFechas: string;
  total: number;
  trabajadores: {
    id: number;
    trabajador: string;
    oficio: string;
    tipo: string;
    cantidad: string;
    tarifa: string;
    importe: string;
  }[];
}

export function MemoriaImprimirPage() {
  const { id } = useParams<{ id: string }>();
  const memoriaId = Number(id);

  const [descargandoPdf, setDescargandoPdf] = useState(false);
  const [descargandoExcel, setDescargandoExcel] = useState(false);
  const [errorDescarga, setErrorDescarga] = useState<string | null>(null);

  const { data: memoria, isLoading, error } = useQuery<Memoria>({
    queryKey: ['memoria', memoriaId],
    queryFn: () => api.getMemoria(memoriaId),
    enabled: !!memoriaId,
  });

  const { data: obra } = useQuery({
    queryKey: ['obra', memoria?.obra_id],
    queryFn: () => (memoria?.obra_id ? api.getObra(memoria.obra_id) : null),
    enabled: !!memoria?.obra_id,
  });

  // Agrupaciones de renglones incluidos
  const { transferencias, efectivo, anticipos, rayasPorSemana } = useMemo(() => {
    if (!memoria || !memoria.renglones) {
      return { transferencias: [], efectivo: [], anticipos: [], rayasPorSemana: [] };
    }
    const inc = memoria.renglones.filter((r) => r.incluido);
    const transf = inc.filter((r) => r.categoria === 'transferencia');
    const efec = inc.filter((r) => r.categoria === 'efectivo');
    const ray = inc.filter((r) => r.categoria === 'raya');
    const ant = (memoria.anticipos || inc.filter((r) => r.categoria === 'anticipo')).filter(
      (r) => r.incluido
    );

    const anioMem = memoria?.fecha_inicio ? parseInt(String(memoria.fecha_inicio).slice(0, 4), 10) || 2026 : 2026;
    const mapaSem: Record<number, SemanaAgrupada> = {};
    ray.forEach((r) => {
      const s = r.semana_numero || 0;
      if (!mapaSem[s]) {
        mapaSem[s] = {
          semana: s,
          tipo: r.tipo_raya === 'dia' ? 'POR DÍA' : 'DESTAJO',
          rangoFechas: formatRangoSemana(r.fecha_inicio, r.fecha_fin, s, anioMem),
          total: 0,
          trabajadores: [],
        };
      } else if ((!mapaSem[s].rangoFechas || mapaSem[s].rangoFechas === '—') && (r.fecha_inicio || r.fecha_fin)) {
        mapaSem[s].rangoFechas = formatRangoSemana(r.fecha_inicio, r.fecha_fin, s, anioMem);
      }
      mapaSem[s].total += parseFloat(r.importe) || 0;
      // Si la semana tiene diferentes tipos
      const tipoActual = r.tipo_raya === 'dia' ? 'POR DÍA' : 'DESTAJO';
      if (mapaSem[s].tipo !== tipoActual && !mapaSem[s].tipo.includes('/')) {
        mapaSem[s].tipo = 'DESTAJO / POR DÍA';
      }

      mapaSem[s].trabajadores.push({
        id: r.ref_id,
        trabajador: r.proveedor || '',
        oficio: r.oficio || 'ALBAÑILERÍA',
        tipo: r.tipo_raya === 'dia' ? 'DÍAS' : 'METROS',
        cantidad: r.cantidad || '0',
        tarifa: r.tarifa || '0.00',
        importe: r.importe,
      });
    });

    const semList = Object.values(mapaSem).sort((a, b) => a.semana - b.semana);

    return {
      transferencias: transf,
      efectivo: efec,
      anticipos: ant,
      rayasPorSemana: semList,
    };
  }, [memoria]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white p-6">
        <div className="flex flex-col items-center gap-2 text-stone-600">
          <Loader2 className="w-6 h-6 animate-spin text-stone-900" />
          <span className="text-xs font-mono">Cargando memoria para impresión...</span>
        </div>
      </div>
    );
  }

  if (error || !memoria) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white p-6">
        <div className="max-w-md p-6 bg-red-50 border border-red-200 rounded-lg text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-red-600 mx-auto" />
          <h2 className="text-sm font-bold text-red-900">Error al cargar la memoria</h2>
          <p className="text-xs text-red-700">No se pudo recuperar el documento para imprimir.</p>
          <Link to="/" className="inline-block text-xs text-stone-800 underline">
            Volver al inicio
          </Link>
        </div>
      </div>
    );
  }

  const totales = memoria.totales || {};
  const cobradoNum = parseFloat(totales.cobrado || '0');
  const anticiposNum = parseFloat(totales.anticipos_total || '0');
  const saldoNum = parseFloat(totales.saldo_a_favor || '0');
  const tieneAnticipos = anticiposNum > 0;
  const fechaEmisionEfectiva = memoria.fecha_emision || memoria.fecha_fin;
  const ciudadEfectiva = memoria.ciudad || 'Zapopan, Jalisco';
  const mostrarMemoriasAnteriores =
    memoria.numero > 1 || parseFloat(totales.gastado_memorias_anteriores || '0') > 0;

  const handleDescargarPdf = async () => {
    try {
      setDescargandoPdf(true);
      setErrorDescarga(null);
      await api.descargarPdf(memoria.id);
    } catch (err: any) {
      setErrorDescarga(err.message || 'Error al descargar el PDF');
    } finally {
      setDescargandoPdf(false);
    }
  };

  const handleDescargarExcel = async () => {
    try {
      setDescargandoExcel(true);
      setErrorDescarga(null);
      await api.descargarExcel(memoria.id);
    } catch (err: any) {
      setErrorDescarga(err.message || 'Error al descargar el Excel');
    } finally {
      setDescargandoExcel(false);
    }
  };

  return (
    <div className="bg-zinc-100 min-h-screen py-6 print:p-0 print:bg-white text-zinc-900 font-sans">
      {/* Estilos de impresión profesionales */}
      <style>{`
        @media print {
          @page {
            size: letter portrait;
            margin: 12mm;
          }
          body {
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          thead {
            display: table-header-group;
          }
          tr {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          tfoot {
            display: table-row-group !important;
            break-inside: avoid;
            page-break-inside: avoid;
          }
          .print-break-page {
            break-before: page;
            page-break-before: always;
          }
          .print-avoid-break {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          .tabla-impresion td, .tabla-impresion th {
            padding-top: 2px !important;
            padding-bottom: 2px !important;
            line-height: 1.15 !important;
          }
          .cierre-con-rayas {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          .no-copy-header {
            user-select: none !important;
            -webkit-user-select: none !important;
            -moz-user-select: none !important;
            -ms-user-select: none !important;
            pointer-events: none !important;
          }
        }
        .no-copy-header {
          user-select: none !important;
          -webkit-user-select: none !important;
          -moz-user-select: none !important;
          -ms-user-select: none !important;
          pointer-events: none !important;
        }
      `}</style>

      {/* Barra superior de acciones (oculta al imprimir) */}
      <div className="max-w-[216mm] mx-auto mb-4 px-4 space-y-2 no-print">
        <div className="flex items-center justify-between">
          <Link
            to={`/obras/${memoria.obra_id}`}
            className="inline-flex items-center gap-1.5 text-xs text-zinc-600 hover:text-zinc-900 font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Volver a la Obra</span>
          </Link>

          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={descargandoPdf}
              onClick={handleDescargarPdf}
              className="flex items-center gap-1.5 text-xs text-zinc-700 hover:text-zinc-900 border-zinc-300 bg-white shadow-2xs"
            >
              {descargandoPdf ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileDown className="w-3.5 h-3.5 text-red-600" />
              )}
              <span>Descargar PDF</span>
            </Button>

            <Button
              size="sm"
              variant="outline"
              disabled={descargandoExcel}
              onClick={handleDescargarExcel}
              className="flex items-center gap-1.5 text-xs text-zinc-700 hover:text-zinc-900 border-zinc-300 bg-white shadow-2xs"
            >
              {descargandoExcel ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
              )}
              <span>Descargar Excel</span>
            </Button>

            <Button
              size="sm"
              onClick={() => window.print()}
              className="flex items-center gap-1.5 text-xs bg-stone-900 text-white hover:bg-stone-800 shadow-sm"
            >
              <Printer className="w-4 h-4" />
              <span>Imprimir Hoja Carta</span>
            </Button>
          </div>
        </div>

        {errorDescarga && (
          <div className="p-3 bg-amber-50 border border-amber-200 text-amber-900 text-xs rounded-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
            <div className="space-y-1">
              <p className="font-semibold text-amber-950 flex items-center gap-1.5">
                <Printer className="w-4 h-4 text-amber-700" />
                No se pudo generar el archivo PDF automáticamente desde el servidor
              </p>
              <p className="text-amber-800">
                {errorDescarga} — Puedes obtener tu PDF de inmediato: presiona <strong className="text-amber-950 font-bold">Ctrl + P</strong> y elige la opción <strong className="text-amber-950 font-bold">"Guardar como PDF"</strong> (tamaño Carta).
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                size="sm"
                onClick={() => window.print()}
                className="bg-amber-700 hover:bg-amber-800 text-white text-xs inline-flex items-center gap-1.5"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>Guardar como PDF (Ctrl+P)</span>
              </Button>
              <button
                onClick={() => setErrorDescarga(null)}
                className="text-amber-800 hover:text-amber-950 font-bold px-2 py-1 text-sm rounded hover:bg-amber-100"
                title="Cerrar aviso"
              >
                ×
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Contenedor tamaño Carta */}
      <div className="relative max-w-[216mm] mx-auto bg-white shadow-lg print:shadow-none print:m-0 print:w-full">
        {/* Marca de agua si es borrador (aparece en pantalla e impresión) */}
        {memoria.estado === 'borrador' && (
          <div className="pointer-events-none fixed inset-0 flex items-center justify-center z-50 overflow-hidden select-none opacity-[0.06] print:opacity-[0.08]">
            <span className="text-8xl sm:text-9xl font-black text-red-600 uppercase tracking-widest rotate-[-30deg] border-8 border-red-600 py-6 px-16 rounded-3xl">
              BORRADOR
            </span>
          </div>
        )}

        {/* ========================================================
            PÁGINA 1: CLIENTE (Formato 1:1 con Excel MEMORIA 01)
           ======================================================== */}
        <div className="p-8 sm:p-10 text-[10px] sm:text-[10.5px] leading-tight space-y-3.5 print:p-0">
          {/* Encabezado Principal */}
          <div className="border-b-2 border-zinc-900 pb-2.5">
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold font-serif tracking-tight text-zinc-900 uppercase">
                    MEMORIA {String(memoria.numero).padStart(2, '0')}
                  </h1>
                  {memoria.estado === 'borrador' && (
                    <span className="text-[9.5px] font-bold px-2 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 rounded uppercase tracking-wider">
                      BORRADOR
                    </span>
                  )}
                </div>
                <p className="text-xs font-bold text-zinc-800 uppercase mt-0.5">
                  OBRA: {obra?.nombre?.toUpperCase() || `OBRA #${memoria.obra_id}`}
                </p>
                <p className="text-[10px] text-zinc-600 uppercase">
                  UBICACIÓN: {obra?.ubicacion?.toUpperCase() || 'NO ESPECIFICADA'}
                </p>
                <p className="text-[10px] text-zinc-600 uppercase">
                  PROPIETARIO: {obra?.propietario?.toUpperCase() || 'NO ESPECIFICADO'}
                </p>
              </div>

              <div className="text-right text-[10px] space-y-0.5">
                <p className="font-semibold text-zinc-900 uppercase">
                  FECHA: {formatDate(fechaEmisionEfectiva)}
                </p>
                <p className="text-zinc-600 uppercase">CIUDAD: {ciudadEfectiva.toUpperCase()}</p>
                <p className="text-zinc-600 uppercase font-mono">
                  PERIODO: {formatDate(memoria.fecha_inicio)} AL {formatDate(memoria.fecha_fin)}
                </p>
                {memoria.folio_factura_arquitecto && (
                  <p className="text-zinc-800 font-mono font-semibold uppercase">
                    FACTURA ARQ: {formatFolioFactura(memoria.folio_factura_arquitecto)}
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* TABLA 1: TRANSFERENCIAS */}
          <div className="space-y-1">
            <table className="w-full text-left border-collapse tabla-impresion">
              <thead>
                <tr className="bg-zinc-800 text-white text-[10px] uppercase font-bold tracking-wider">
                  <th colSpan={3} className="py-1 px-2 font-bold h-5 leading-normal">
                    TRANSFERENCIAS:
                  </th>
                  <th className="py-1 px-2 text-right font-bold h-5 leading-normal">
                    IMPORTE
                  </th>
                </tr>
                <tr className="border-b border-zinc-300 text-[9px] uppercase font-bold text-zinc-700 bg-zinc-50">
                  <th className="py-1 px-1.5">CONCEPTO:</th>
                  <th className="py-1 px-1.5 w-32">COMPROBANTE:</th>
                  <th className="py-1 px-1.5 w-20">FECHA:</th>
                  <th className="py-1 px-1.5 text-right w-24">IMPORTE:</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 text-[9.5px]">
                {transferencias.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                      SIN PAGOS POR TRANSFERENCIA EN EL PERIODO
                    </td>
                  </tr>
                ) : (
                  transferencias.map((r) => (
                    <tr key={`t-${r.ref_tipo}-${r.ref_id}`}>
                      <td className="py-1 px-1.5 uppercase font-medium">
                        {r.proveedor ? `${r.proveedor.toUpperCase()}: ` : ''}
                        {r.concepto?.toUpperCase()}
                      </td>
                      <td className="py-1 px-1.5 font-mono text-[9px] uppercase">
                        {r.comprobante?.toUpperCase() || '—'}
                      </td>
                      <td className="py-1 px-1.5 font-mono text-[9px]">{formatDate(r.fecha)}</td>
                      <td className="py-1 px-1.5 text-right font-mono font-medium">
                        {formatMoneySimple(r.importe)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-zinc-800 font-bold bg-zinc-50 text-[10px]">
                  <td colSpan={3} className="py-1 px-1.5 text-right uppercase">
                    PAGOS TRANSFER. DE ESTA MEMORIA:
                  </td>
                  <td className="py-1 px-1.5 text-right font-mono">
                    {formatMoneySimple(totales.transferencias)}
                  </td>
                </tr>
              </tfoot>
            </table>

            {/* BLOQUE INDEPENDIENTE: RESUMEN DE TRANSFERENCIAS */}
            <div className="pt-1.5 pb-0.5 print-avoid-break">
              <div className="border border-zinc-300 bg-zinc-50/60 p-2 text-[9.5px] max-w-sm ml-auto space-y-1">
                <div className="font-bold uppercase text-zinc-800 border-b border-zinc-200 pb-0.5 text-[9px]">
                  RESUMEN DE TRANSFERENCIAS
                </div>
                <div className="flex justify-between font-mono text-[9px]">
                  <span className="text-zinc-600 uppercase">ACUMULADO A LA FECHA:</span>
                  <span className="font-semibold">
                    {formatMoneySimple(totales.transferencias_memorias_anteriores || '0.00')}
                  </span>
                </div>
                <div className="flex justify-between font-mono text-[9px]">
                  <span className="text-zinc-600 uppercase">DE ESTA MEMORIA:</span>
                  <span className="font-semibold">{formatMoneySimple(totales.transferencias)}</span>
                </div>
                <div className="flex justify-between font-mono text-[9.5px] font-bold border-t border-zinc-200 pt-0.5">
                  <span className="uppercase text-zinc-800">TOTAL:</span>
                  <span>{formatMoneySimple(totales.acumulado_transferencias)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* TABLA 2: NOTAS Y FACTURAS EN EFECTIVO */}
          <div className="space-y-1 pt-1">
            <table className="w-full text-left border-collapse tabla-impresion">
              <thead>
                <tr className="bg-zinc-800 text-white text-[10px] uppercase font-bold tracking-wider">
                  <th colSpan={3} className="py-1 px-2 font-bold h-5 leading-normal">
                    NOTAS Y FACTURAS EN EFECTIVO:
                  </th>
                  <th className="py-1 px-2 text-right font-bold h-5 leading-normal">
                    IMPORTE
                  </th>
                </tr>
                <tr className="border-b border-zinc-300 text-[9px] uppercase font-bold text-zinc-700 bg-zinc-50">
                  <th className="py-1 px-1.5">CONCEPTO:</th>
                  <th className="py-1 px-1.5 w-32">COMPROBANTE:</th>
                  <th className="py-1 px-1.5 w-20">FECHA:</th>
                  <th className="py-1 px-1.5 text-right w-24">IMPORTE:</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 text-[9.5px]">
                {efectivo.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                      SIN GASTOS EN EFECTIVO EN EL PERIODO
                    </td>
                  </tr>
                ) : (
                  efectivo.map((r) => (
                    <tr key={`e-${r.ref_tipo}-${r.ref_id}`}>
                      <td className="py-1 px-1.5 uppercase font-medium">
                        {r.proveedor ? `${r.proveedor.toUpperCase()}: ` : ''}
                        {r.concepto?.toUpperCase()}
                      </td>
                      <td className="py-1 px-1.5 font-mono text-[9px] uppercase">
                        {r.comprobante?.toUpperCase() || '—'}
                      </td>
                      <td className="py-1 px-1.5 font-mono text-[9px]">{formatDate(r.fecha)}</td>
                      <td className="py-1 px-1.5 text-right font-mono font-medium">
                        {formatMoneySimple(r.importe)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-zinc-800 font-bold bg-zinc-50 text-[10px]">
                  <td colSpan={3} className="py-1 px-1.5 text-right uppercase">
                    TOTAL NOTAS Y FACTURAS EN EFECTIVO:
                  </td>
                  <td className="py-1 px-1.5 text-right font-mono">
                    {formatMoneySimple(totales.efectivo)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* TABLA 3: RAYAS POR SEMANA + CIERRE EN UN BLOQUE PARA EVITAR HUÉRFANOS */}
          <div className="cierre-con-rayas print-avoid-break">
            <div className="space-y-1 pt-1">
              <table className="w-full text-left border-collapse tabla-impresion">
                <thead>
                  <tr className="bg-zinc-800 text-white text-[10px] uppercase font-bold tracking-wider">
                    <th colSpan={3} className="py-1 px-2 font-bold h-5 leading-normal">
                      RAYAS:
                    </th>
                    <th className="py-1 px-2 text-right font-bold h-5 leading-normal">
                      IMPORTE
                    </th>
                  </tr>
                  <tr className="border-b border-zinc-300 text-[9px] uppercase font-bold text-zinc-700 bg-zinc-50">
                    <th className="py-1 px-1.5">CONCEPTO:</th>
                    <th className="py-1 px-1.5 w-32">COMPROBANTE:</th>
                    <th className="py-1 px-1.5 w-28">FECHA:</th>
                    <th className="py-1 px-1.5 text-right w-24">IMPORTE:</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 text-[9.5px]">
                  {rayasPorSemana.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                        SIN RAYAS DE ALBAÑILERÍA EN EL PERIODO
                      </td>
                    </tr>
                  ) : (
                    rayasPorSemana.map((s) => (
                      <tr key={`sem-${s.semana}`}>
                        <td className="py-1 px-1.5 font-semibold uppercase">
                          SEMANA # {s.semana}
                        </td>
                        <td className="py-1 px-1.5 font-mono text-[9px] uppercase font-medium">
                          {s.tipo}
                        </td>
                        <td className="py-1 px-1.5 font-mono text-[9px] text-zinc-700 uppercase">
                          {s.rangoFechas}
                        </td>
                        <td className="py-1 px-1.5 text-right font-mono font-medium">
                          {formatMoneySimple(s.total)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-zinc-800 font-bold bg-zinc-50 text-[10px]">
                    <td colSpan={3} className="py-1 px-1.5 text-right uppercase">
                      SUBTOTAL:
                    </td>
                    <td className="py-1 px-1.5 text-right font-mono">
                      {formatMoneySimple(totales.rayas)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>

            {/* CIERRE DE LA HOJA: ORDEN EXACTO DEL EXCEL MEMORIA 01 */}
            <div className="pt-2 border-t-2 border-zinc-900 print-avoid-break">
              <div className="max-w-md ml-auto space-y-1 font-mono text-[10px]">
                <div className="flex justify-between py-0.5 border-b border-zinc-100">
                  <span className="uppercase font-sans font-medium text-zinc-700">
                    HONORARIOS {totales.porcentaje_honorarios}% (PAGOS TRANSF.)
                  </span>
                  <span>{formatMoneySimple(totales.hon_transferencias)}</span>
                </div>

                <div className="flex justify-between py-0.5 border-b border-zinc-100">
                  <span className="uppercase font-sans font-medium text-zinc-700">
                    HONORARIOS {totales.porcentaje_honorarios}% (PAGOS EFECTIVO)
                  </span>
                  <span>{formatMoneySimple(totales.hon_efectivo)}</span>
                </div>

                <div className="flex justify-between py-0.5 border-b border-zinc-100">
                  <span className="uppercase font-sans font-medium text-zinc-700">
                    HONORARIOS {totales.porcentaje_honorarios}% (PAGOS DE RAYAS)
                  </span>
                  <span>{formatMoneySimple(totales.hon_rayas)}</span>
                </div>

                <div className="flex justify-between py-0.5 border-b border-zinc-200 font-bold">
                  <span className="uppercase font-sans">SUBTOTAL</span>
                  <span>{formatMoneySimple(totales.subtotal)}</span>
                </div>

                <div className="flex justify-between py-0.5 border-b border-zinc-100">
                  <span className="uppercase font-sans font-medium text-zinc-700">IVA 16%</span>
                  <span>{formatMoneySimple(totales.iva)}</span>
                </div>

                {/* IMPORTE DE ESTA MEMORIA F-XXX */}
                <div className="py-1 border-b border-zinc-300">
                  <div className="flex justify-between font-bold text-zinc-900">
                    <span className="uppercase font-sans">
                      {memoria.folio_factura_arquitecto
                        ? `IMPORTE DE ESTA MEMORIA ${formatFolioFactura(memoria.folio_factura_arquitecto)}`
                        : 'IMPORTE DE ESTA MEMORIA (FACTURA)'}
                    </span>
                    <span>{formatMoneySimple(totales.importe_factura)}</span>
                  </div>
                  {(memoria.importe_factura_texto || totales.importe_factura_texto) && (
                    <p className="text-[8.5px] text-zinc-600 uppercase text-right mt-0.5 italic">
                      {formatTextoEnLetra(memoria.importe_factura_texto || totales.importe_factura_texto)}
                    </p>
                  )}
                </div>

                {/* IMPORTE DE ESTA MEMORIA (TOTAL) */}
                <div className="py-1 border-b-2 border-zinc-800 bg-zinc-50/70 px-1.5 -mx-1.5">
                  <div className="flex justify-between text-[11px] font-bold text-zinc-950">
                    <span className="uppercase font-sans">IMPORTE DE ESTA MEMORIA:</span>
                    <span>{formatMoneySimple(totales.total_memoria)}</span>
                  </div>
                  {(memoria.total_texto || totales.total_texto) && (
                    <p className="text-[8.5px] text-zinc-700 uppercase text-right mt-0.5 italic">
                      {formatTextoEnLetra(memoria.total_texto || totales.total_texto)}
                    </p>
                  )}
                </div>

                {/* IMPORTE DE MEMORIAS ANTERIORES: (si numero > 1 o hay acumulado) */}
                {(memoria.numero > 1 || parseFloat(totales.gastado_memorias_anteriores || '0') > 0) && (
                  <div className="flex justify-between py-0.5 border-b border-zinc-100 text-zinc-600">
                    <span className="uppercase font-sans">
                      IMPORTE DE MEMORIAS ANTERIORES:
                    </span>
                    <span>{formatMoneySimple(totales.gastado_memorias_anteriores || '0')}</span>
                  </div>
                )}

                {/* IMPORTE DE MEMORIA 01 A {N}: (siempre visible) */}
                <div className="flex justify-between py-0.5 border-b border-zinc-100 text-zinc-700">
                  <span className="uppercase font-sans">
                    IMPORTE DE MEMORIA 01 A {String(memoria.numero).padStart(2, '0')}:
                  </span>
                  <span>{formatMoneySimple(totales.gastado_a_la_fecha)}</span>
                </div>

                {/* GASTADO A LA FECHA */}
                <div className="py-1 border-t border-zinc-300">
                  <div className="flex justify-between text-[11px] font-bold text-zinc-900">
                    <span className="uppercase font-sans">GASTADO A LA FECHA:</span>
                    <span>{formatMoneySimple(totales.gastado_a_la_fecha)}</span>
                  </div>
                  {(memoria.gastado_a_la_fecha_texto || totales.gastado_a_la_fecha_texto) && (
                    <p className="text-[8.5px] text-zinc-600 uppercase text-right mt-0.5 italic">
                      {formatTextoEnLetra(memoria.gastado_a_la_fecha_texto || totales.gastado_a_la_fecha_texto)}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* TABLA 4: ANTICIPOS RECIBIDOS (solo si hay anticipos) */}
          {anticipos.length > 0 && (
            <div className="space-y-1 pt-2 print-avoid-break">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-zinc-800 text-white text-[10px] uppercase font-bold tracking-wider">
                    <th colSpan={2} className="py-1 px-2 font-bold h-5 leading-normal">
                      ANTICIPOS RECIBIDOS:
                    </th>
                    <th className="py-1 px-2 text-right font-bold h-5 leading-normal">
                      IMPORTE
                    </th>
                  </tr>
                  <tr className="border-b border-zinc-300 text-[9px] uppercase font-bold text-zinc-700 bg-zinc-50">
                    <th className="py-1 px-1.5 w-24">FECHA:</th>
                    <th className="py-1 px-1.5">COMPROBANTE:</th>
                    <th className="py-1 px-1.5 text-right w-28">IMPORTE:</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 text-[9.5px]">
                  {anticipos.map((a) => (
                    <tr key={`ant-${a.ref_tipo}-${a.ref_id}`}>
                      <td className="py-1 px-1.5 font-mono text-[9px]">{formatDate(a.fecha)}</td>
                      <td className="py-1 px-1.5 font-mono text-[9px] uppercase">
                        {a.comprobante?.toUpperCase() || 'ANTICIPO'}
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono font-medium">
                        {formatMoneySimple(a.importe)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-zinc-800 font-bold bg-zinc-50 text-[10px]">
                    <td colSpan={2} className="py-1 px-1.5 text-right uppercase">
                      TOTAL ANTICIPOS RECIBIDOS:
                    </td>
                    <td className="py-1 px-1.5 text-right font-mono">
                      {formatMoneySimple(totales.anticipos_total)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}

          {/* PIE DE PÁGINA EN MAYÚSCULAS CON FORMATO LARGO */}
          <div className="pt-4 text-center text-[10px] font-bold uppercase tracking-wide text-zinc-700 print-avoid-break">
            {formatFechaLarga(ciudadEfectiva, fechaEmisionEfectiva)}
          </div>
        </div>

        {/* ========================================================
            PÁGINA 2: ARQUITECTO (Liquidación Interna y Recuperación)
            Salto de página forzado en impresión
           ======================================================== */}
        <div className="p-8 sm:p-10 text-[10px] sm:text-[10.5px] leading-tight space-y-3.5 print:p-0 print-break-page border-t-4 border-zinc-900 print:border-t-0">
          {/* Encabezado Arquitecto */}
          <div className="border-b-2 border-zinc-900 pb-2">
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold font-serif uppercase tracking-tight text-zinc-900">
                RESUMEN MEMORIA {String(memoria.numero).padStart(2, '0')}:
              </h2>
              {memoria.estado === 'borrador' && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 rounded uppercase tracking-wider">
                  BORRADOR
                </span>
              )}
            </div>
            <p className="text-[9.5px] text-zinc-600 uppercase font-mono mt-0.5">
              OBRA: {obra?.nombre?.toUpperCase() || `OBRA #${memoria.obra_id}`} · FECHA: {formatDate(fechaEmisionEfectiva)}
            </p>
          </div>

          {/* Cuadro Financiero del Arquitecto */}
          <div className="bg-stone-50 border border-stone-200 p-3 rounded space-y-2 text-[10px] print-avoid-break">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Columna Izquierda: Honorarios */}
              <div className="space-y-1 font-mono">
                <div className="text-[9.5px] font-bold uppercase text-zinc-800 font-sans border-b border-stone-200 pb-0.5">
                  HONORARIOS:
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="font-sans text-zinc-700 uppercase">HONORARIOS:</span>
                  <span className="font-bold">{formatMoneySimple(totales.honorarios)}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="font-sans text-zinc-700 uppercase">IVA TOTAL 16%:</span>
                  <span>{formatMoneySimple(totales.iva)}</span>
                </div>
                <div className="flex justify-between text-[10.5px] font-bold text-zinc-900 pt-0.5 border-t border-stone-200">
                  <span className="font-sans uppercase">TOTAL HONORARIOS:</span>
                  <span>
                    {formatMoneySimple(
                      totales.total_honorarios ||
                        (parseFloat(totales.honorarios || '0') + parseFloat(totales.iva || '0')).toFixed(2)
                    )}
                  </span>
                </div>
              </div>

              {/* Columna Derecha: Liquidación de Efectivo y Nómina */}
              <div className="space-y-1 font-mono">
                <div className="text-[9.5px] font-bold uppercase text-zinc-800 font-sans border-b border-stone-200 pb-0.5">
                  REEMBOLSO DE GASTOS:
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="font-sans text-zinc-700 uppercase">NOTAS EN EFECTIVO:</span>
                  <span>{formatMoneySimple(totales.efectivo)}</span>
                </div>
                <div className="flex justify-between text-[10px]">
                  <span className="font-sans text-zinc-700 uppercase">NÓMINA:</span>
                  <span>{formatMoneySimple(totales.rayas)}</span>
                </div>
                <div className="flex justify-between text-[10.5px] font-bold text-zinc-900 pt-0.5 border-t border-stone-200">
                  <span className="font-sans uppercase">COBRADO:</span>
                  <span>{formatMoneySimple(totales.cobrado)}</span>
                </div>
              </div>
            </div>

            {/* Fila de Anticipos y Saldo a Favor / Anticipo Pendiente */}
            {tieneAnticipos && (
              <div className="pt-2 border-t border-stone-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                <div className="text-[10px]">
                  <span className="text-zinc-600 uppercase font-medium">ANTICIPOS: </span>
                  <span className="font-mono font-bold text-zinc-800">
                    -{formatMoneySimple(totales.anticipos_total)}
                  </span>
                </div>

                {saldoNum >= 0 ? (
                  <div className="bg-emerald-50 text-emerald-900 border border-emerald-300 px-3 py-1 rounded text-xs font-bold flex items-center gap-1.5">
                    <span className="uppercase">SALDO A MI FAVOR:</span>
                    <span className="font-mono">{formatMoneySimple(totales.saldo_a_favor)}</span>
                  </div>
                ) : (
                  <div className="bg-amber-50 text-amber-900 border border-amber-300 px-3 py-1 rounded text-xs font-bold flex items-center gap-1.5">
                    <span className="uppercase">ANTICIPO PENDIENTE DE APLICAR:</span>
                    <span className="font-mono">{formatMoneySimple(Math.abs(saldoNum))}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* RECUPERACIÓN DE CAJA CHICA (NOTAS DETALLADAS) */}
          <div className="space-y-1 pt-1">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-zinc-800 text-white text-[10px] uppercase font-bold tracking-wider">
                  <th colSpan={3} className="py-1 px-2 font-bold h-5 leading-normal">
                    RECUPERACIÓN DE CAJA CHICA.
                  </th>
                  <th className="py-1 px-2 text-right font-bold h-5 leading-normal">
                    TOTAL: {formatMoneySimple(totales.efectivo)}
                  </th>
                </tr>
                <tr className="border-b border-zinc-300 text-[9px] uppercase font-bold text-zinc-700 bg-zinc-50">
                  <th className="py-1 px-1.5">CONCEPTO:</th>
                  <th className="py-1 px-1.5 w-32">COMPROBANTE:</th>
                  <th className="py-1 px-1.5 w-20">FECHA:</th>
                  <th className="py-1 px-1.5 text-right w-24">IMPORTE:</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 text-[9px]">
                {efectivo.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                      SIN MOVIMIENTOS DE CAJA CHICA
                    </td>
                  </tr>
                ) : (
                  efectivo.map((r) => (
                    <tr key={`det-efec-${r.ref_tipo}-${r.ref_id}`}>
                      <td className="py-1 px-1.5 uppercase font-medium">
                        {r.proveedor ? `${r.proveedor.toUpperCase()}: ` : ''}
                        {r.concepto?.toUpperCase()}
                      </td>
                      <td className="py-1 px-1.5 font-mono uppercase">
                        {r.comprobante?.toUpperCase() || '—'}
                      </td>
                      <td className="py-1 px-1.5 font-mono">{formatDate(r.fecha)}</td>
                      <td className="py-1 px-1.5 text-right font-mono font-medium">
                        {formatMoneySimple(r.importe)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                <tr className="border-t border-zinc-800 font-bold bg-zinc-50 text-[9.5px]">
                  <td colSpan={3} className="py-1 px-1.5 text-right uppercase">
                    TOTAL:
                  </td>
                  <td className="py-1 px-1.5 text-right font-mono">
                    {formatMoneySimple(totales.efectivo)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>

          {/* DETALLE DE DESTAJOS/RAYAS POR SEMANA */}
          <div className="space-y-3 pt-2">
            <div className="bg-zinc-800 text-white px-2 py-1 font-bold text-[10px] uppercase tracking-wider flex justify-between">
              <span>DETALLE DE DESTAJOS/RAYAS POR SEMANA:</span>
              <span>TOTAL NÓMINA: {formatMoneySimple(totales.rayas)}</span>
            </div>

            {rayasPorSemana.length === 0 ? (
              <div className="py-2 text-center text-zinc-400 italic text-[9.5px]">
                SIN REGISTRO DE RAYAS EN EL PERIODO
              </div>
            ) : (
              rayasPorSemana.map((sem) => (
                <div
                  key={`det-sem-${sem.semana}`}
                  className="border border-zinc-200 rounded overflow-hidden print-avoid-break"
                >
                  <div className="bg-zinc-100 px-2 py-1 font-bold text-[9.5px] uppercase flex justify-between items-center border-b border-zinc-200">
                    <span>
                      SEMANA #{sem.semana} ({sem.rangoFechas})
                    </span>
                    <span className="font-mono text-zinc-800">
                      SUBTOTAL: {formatMoneySimple(sem.total)}
                    </span>
                  </div>

                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-zinc-200 text-[8.5px] uppercase font-bold text-zinc-600 bg-zinc-50/50">
                        <th className="py-0.5 px-1.5">TRABAJADOR</th>
                        <th className="py-0.5 px-1.5 w-32">OFICIO</th>
                        <th className="py-0.5 px-1.5 w-24">CANTIDAD</th>
                        <th className="py-0.5 px-1.5 text-right w-20">TARIFA</th>
                        <th className="py-0.5 px-1.5 text-right w-24">IMPORTE</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100 text-[9px]">
                      {sem.trabajadores.map((t) => (
                        <tr key={`t-raya-${t.id}`}>
                          <td className="py-0.5 px-1.5 uppercase font-medium">
                            {t.trabajador.toUpperCase()}
                          </td>
                          <td className="py-0.5 px-1.5 uppercase text-zinc-600">{t.oficio}</td>
                          <td className="py-0.5 px-1.5 font-mono text-[8.5px]">
                            {t.cantidad} {t.tipo}
                          </td>
                          <td className="py-0.5 px-1.5 text-right font-mono">${t.tarifa}</td>
                          <td className="py-0.5 px-1.5 text-right font-mono font-semibold">
                            {formatMoneySimple(t.importe)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default MemoriaImprimirPage;
