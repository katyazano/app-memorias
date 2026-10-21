import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  FileText,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  Plus,
  ArrowRight,
  ArrowLeft,
  Building,
  CheckSquare,
  Square,
  ChevronRight,
  User,
  MapPin,
  Percent,
  Hash,
  Printer,
  Lock,
  Edit2,
  Check,
  X,
  ExternalLink,
  FileDown,
  FileSpreadsheet,
  Loader2,
} from 'lucide-react';
import {
  useParams as useRouterParams,
  useNavigate as useRouterNavigate,
  useSearchParams as useRouterSearchParams,
  Link as RouterLink,
} from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Dialog } from '@/components/ui/Dialog';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatDate, formatMoney, formatMoneySimple, formatRangoSemana, formatFechaLarga, formatTextoEnLetra, formatFolioFactura } from '@/lib/utils';
import { BuscarGastosExtraDialog } from '@/components/memorias/BuscarGastosExtraDialog';
import { TotalesStickyFooter } from '@/components/memorias/TotalesStickyFooter';
import { FallbackPdfModal } from '@/components/FallbackPdfModal';
import type { Obra, PreviewOut, RenglonMemoria, Gasto, PagoRaya, MemoriaResumen, Memoria } from '@/types';

type TabCategoria = 'transferencia' | 'efectivo' | 'raya' | 'anticipo';

export function AsistenteMemoriaPage() {
  const { id } = useRouterParams<{ id: string }>();
  const obraId = Number(id);
  const navigate = useRouterNavigate();
  const [searchParams] = useRouterSearchParams();
  const borradorIdParam = searchParams.get('borrador_id');

  const queryClient = useQueryClient();

  // Paso activo (1 = Datos, 2 = Selección, 3 = Vista Previa y Cierre)
  const [paso, setPaso] = useState<1 | 2 | 3>(1);

  // Datos de la Obra
  const { data: obra, isLoading: cargandoObra } = useQuery<Obra>({
    queryKey: ['obra', obraId],
    queryFn: () => api.getObra(obraId),
    enabled: !!obraId,
  });

  // Lista de memorias existentes para detectar borradores
  const { data: memoriasExistentes } = useQuery<MemoriaResumen[]>({
    queryKey: ['memorias', obraId],
    queryFn: () => api.getMemoriasDeObra(obraId),
    enabled: !!obraId,
  });

  const borradorGuardado = useMemo(() => {
    return (memoriasExistentes || []).find((m) => m.estado === 'borrador');
  }, [memoriasExistentes]);

  // Formulario Paso 1: Datos
  const hoyStr = new Date().toISOString().split('T')[0];
  const [memoriaIdActivo, setMemoriaIdActivo] = useState<number | null>(
    borradorIdParam ? Number(borradorIdParam) : null
  );
  const [memoriaEstado, setMemoriaEstado] = useState<'borrador' | 'cerrada'>('borrador');

  const [numero, setNumero] = useState<number>(1);
  const [fechaInicio, setFechaInicio] = useState<string>('');
  const [fechaFin, setFechaFin] = useState<string>(hoyStr);
  const [fechaEmision, setFechaEmision] = useState<string>(hoyStr);
  const [ciudad, setCiudad] = useState<string>('Zapopan, Jalisco');
  const [porcentajeHonorarios, setPorcentajeHonorarios] = useState<string>('10.00');
  const [folioFactura, setFolioFactura] = useState<string>('');

  // Verificación de folio usado
  const [folioVerif, setFolioVerif] = useState<{
    usado: boolean;
    memoria_numero?: number;
    obra_nombre?: string;
    estado?: string;
  } | null>(null);

  // Inicializar fechas por defecto (primer día del mes actual a hoy)
  useEffect(() => {
    if (!fechaInicio) {
      const now = new Date();
      const primerDiaMes = new Date(now.getFullYear(), now.getMonth(), 1)
        .toISOString()
        .split('T')[0];
      setFechaInicio(primerDiaMes);
    }
  }, [fechaInicio]);

  // Precargar porcentaje de honorarios cuando se cargue la obra
  useEffect(() => {
    if (obra && obra.porcentaje_honorarios && !borradorIdParam) {
      setPorcentajeHonorarios(obra.porcentaje_honorarios);
    }
  }, [obra, borradorIdParam]);

  // Obtener preview inicial de sugeridos cuando obra esté lista
  const { data: previewInicial } = useQuery<PreviewOut>({
    queryKey: ['preview-sugeridos', obraId],
    queryFn: () =>
      api.previewMemoria(obraId, {
        fecha_inicio: fechaInicio || hoyStr,
        fecha_fin: fechaFin || hoyStr,
      }),
    enabled: !!obraId && !borradorIdParam,
  });

  useEffect(() => {
    if (previewInicial && !borradorIdParam) {
      if (previewInicial.numero_sugerido) {
        setNumero(previewInicial.numero_sugerido);
      }
      if (previewInicial.folio_sugerido && !folioFactura) {
        setFolioFactura(previewInicial.folio_sugerido);
      }
    }
  }, [previewInicial, borradorIdParam]);

  // Reanudar un borrador específico si se solicita
  const reanudarBorrador = async (borradorId: number) => {
    try {
      const b = await api.getMemoria(borradorId);
      setMemoriaIdActivo(b.id);
      setMemoriaEstado(b.estado as 'borrador' | 'cerrada');
      setNumero(b.numero);
      setFechaInicio(b.fecha_inicio);
      setFechaFin(b.fecha_fin);
      if (b.fecha_emision) setFechaEmision(b.fecha_emision);
      if (b.ciudad) setCiudad(b.ciudad);
      setPorcentajeHonorarios(b.porcentaje_honorarios_usado);
      setFolioFactura(b.folio_factura_arquitecto || '');
      setRenglones(b.renglones || []);
      setTotales(b.totales || null);
      setTotalTexto(b.total_texto || '');
      if (b.importe_factura_texto) setImporteFacturaTexto(b.importe_factura_texto);
      if (b.gastado_a_la_fecha_texto || b.totales?.gastado_a_la_fecha_texto) {
        setGastadoFechaTexto(b.gastado_a_la_fecha_texto || b.totales?.gastado_a_la_fecha_texto || '');
      }
      setPaso(2);
    } catch (e) {
      console.error('Error al cargar borrador', e);
    }
  };

  useEffect(() => {
    if (borradorIdParam) {
      reanudarBorrador(Number(borradorIdParam));
    }
  }, [borradorIdParam]);

  // Comprobar si el folio ya está en uso (con debounce)
  useEffect(() => {
    if (!folioFactura || folioFactura.trim() === '') {
      setFolioVerif(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.verificarFolio(
          folioFactura.trim(),
          memoriaIdActivo || undefined
        );
        setFolioVerif(res);
      } catch (err) {
        console.error('Error verificando folio', err);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [folioFactura, memoriaIdActivo]);

  // ----------------------------------------------------
  // PASO 2: Renglones, Selección y Cálculo reactivo
  // ----------------------------------------------------
  const [tabActiva, setTabActiva] = useState<TabCategoria>('transferencia');
  const [renglones, setRenglones] = useState<RenglonMemoria[]>([]);
  const [gastosExtraIds, setGastosExtraIds] = useState<number[]>([]);
  const [rayasExtraIds, setRayasExtraIds] = useState<number[]>([]);
  const [rayasPosteriores, setRayasPosteriores] = useState<RenglonMemoria[]>([]);
  const [totales, setTotales] = useState<Record<string, string> | null>(null);
  const [totalTexto, setTotalTexto] = useState<string>('');
  const [importeFacturaTexto, setImporteFacturaTexto] = useState<string>('');
  const [gastadoFechaTexto, setGastadoFechaTexto] = useState<string>('');
  const [recalculando, setRecalculando] = useState<boolean>(false);
  const [modalGastosExtraAbierto, setModalGastosExtraAbierto] = useState<boolean>(false);

  const [avisoGuardado, setAvisoGuardado] = useState<string | null>(null);
  const [errorGuardado, setErrorGuardado] = useState<string | null>(null);

  // Modal de confirmación de cierre
  const [modalCerrarAbierto, setModalCerrarAbierto] = useState<boolean>(false);
  const [cerrandoMemoria, setCerrandoMemoria] = useState<boolean>(false);

  // Cargar preview oficial del backend al ingresar al Paso 2
  const cargarPreviewBackend = async (
    overrideSeleccion?: { ref_tipo: 'gasto' | 'raya' | 'anticipo'; ref_id: number; incluido: boolean }[],
    overrideRayasExtra?: number[],
    overrideGastosExtra?: number[]
  ) => {
    if (!obraId || !fechaInicio || !fechaFin) return;
    setRecalculando(true);
    try {
      const data = await api.previewMemoria(obraId, {
        fecha_inicio: fechaInicio,
        fecha_fin: fechaFin,
        gastos_extra_ids: overrideGastosExtra !== undefined ? overrideGastosExtra : gastosExtraIds,
        rayas_extra_ids: overrideRayasExtra !== undefined ? overrideRayasExtra : rayasExtraIds,
        numero: numero,
        porcentaje_honorarios: porcentajeHonorarios,
        seleccion: overrideSeleccion,
      });

      setRenglones(data.renglones);
      setRayasPosteriores(data.rayas_posteriores || []);
      setTotales(data.totales);
      setTotalTexto(data.total_texto);
      if (data.importe_factura_texto) setImporteFacturaTexto(data.importe_factura_texto);
      if (data.gastado_a_la_fecha_texto || data.totales?.gastado_a_la_fecha_texto) {
        setGastadoFechaTexto(data.gastado_a_la_fecha_texto || data.totales?.gastado_a_la_fecha_texto || '');
      }
    } catch (err: any) {
      console.error('Error calculando preview', err);
      setErrorGuardado(err.message || 'Error al calcular la memoria');
    } finally {
      setRecalculando(false);
    }
  };

  // Cargar al entrar al Paso 2 si aún no tenemos renglones
  useEffect(() => {
    if (paso === 2 && renglones.length === 0) {
      cargarPreviewBackend();
    }
  }, [paso]);

  // Recálculo con debounce cuando el usuario marca o desmarca
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleToggleRenglon = (ref_tipo: 'gasto' | 'raya' | 'anticipo', ref_id: number) => {
    const target = renglones.find((r) => r.ref_tipo === ref_tipo && r.ref_id === ref_id);
    if (target?.ya_incluido_en) {
      return;
    }
    const nuevosRenglones = renglones.map((r) => {
      if (r.ref_tipo === ref_tipo && r.ref_id === ref_id) {
        return { ...r, incluido: !r.incluido };
      }
      return r;
    });

    setRenglones(nuevosRenglones);

    // Enviar la selección completa al backend para cálculo exacto en Decimal
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      const seleccionPayload = nuevosRenglones.map((r) => ({
        ref_tipo: r.ref_tipo,
        ref_id: r.ref_id,
        incluido: r.incluido,
      }));
      cargarPreviewBackend(seleccionPayload);
    }, 250);
  };

  const handleSeleccionarTodosTab = (incluir: boolean) => {
    const nuevosRenglones = renglones.map((r) => {
      if (r.categoria === tabActiva) {
        if (incluir && r.ya_incluido_en) {
          return { ...r, incluido: false };
        }
        return { ...r, incluido: incluir };
      }
      return r;
    });

    setRenglones(nuevosRenglones);

    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      const seleccionPayload = nuevosRenglones.map((r) => ({
        ref_tipo: r.ref_tipo,
        ref_id: r.ref_id,
        incluido: r.incluido,
      }));
      cargarPreviewBackend(seleccionPayload);
    }, 200);
  };

  // Agregar gastos seleccionados del modal extra
  const handleAgregarGastosExtra = (nuevosGastos: Gasto[]) => {
    const nuevosIds = nuevosGastos.map((g) => g.id);
    const listaCompleta = Array.from(new Set([...gastosExtraIds, ...nuevosIds]));
    setGastosExtraIds(listaCompleta);
    cargarPreviewBackend(undefined, undefined, listaCompleta);
  };

  // Agregar rayas seleccionadas del modal extra
  const handleAgregarRayasExtra = (nuevasRayas: PagoRaya[]) => {
    const nuevosIds = nuevasRayas.map((r) => r.id);
    const listaCompleta = Array.from(new Set([...rayasExtraIds, ...nuevosIds]));
    setRayasExtraIds(listaCompleta);
    cargarPreviewBackend(undefined, listaCompleta, undefined);
  };

  // Agregar rayas posteriores que terminan después del periodo
  const handleAgregarRayasPosteriores = () => {
    const postIds = rayasPosteriores.map((r) => r.ref_id);
    const listaCompleta = Array.from(new Set([...rayasExtraIds, ...postIds]));
    setRayasExtraIds(listaCompleta);
    cargarPreviewBackend(undefined, listaCompleta, undefined);
  };

  // Guardar Borrador
  const guardarMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        obra_id: obraId,
        numero: numero,
        folio_factura_arquitecto: folioFactura.trim() || null,
        fecha_inicio: fechaInicio,
        fecha_fin: fechaFin,
        fecha_emision: fechaEmision,
        ciudad: ciudad,
        porcentaje_honorarios: porcentajeHonorarios,
        renglones: renglones.map((r) => ({
          ref_tipo: r.ref_tipo,
          ref_id: r.ref_id,
          incluido: r.incluido,
          proveedor: r.proveedor,
          concepto: r.concepto,
          comprobante: r.comprobante,
          importe: r.importe,
          tipo_comprobante: r.tipo_comprobante,
          fecha_inicio: r.fecha_inicio,
          fecha_fin: r.fecha_fin,
          oficio: r.oficio,
          cantidad: r.cantidad,
          tarifa: r.tarifa,
          tipo_raya: r.tipo_raya,
          semana_numero: r.semana_numero,
        })),
      };

      if (memoriaIdActivo) {
        return api.actualizarMemoria(memoriaIdActivo, payload);
      } else {
        return api.guardarMemoria(payload);
      }
    },
    onSuccess: (memoriaGuardada) => {
      setMemoriaIdActivo(memoriaGuardada.id);
      queryClient.invalidateQueries({ queryKey: ['memorias', obraId] });
      setAvisoGuardado('Borrador guardado correctamente.');
      setErrorGuardado(null);
      setTimeout(() => setAvisoGuardado(null), 3500);
    },
    onError: (err: any) => {
      setErrorGuardado(err.message || 'Error al guardar el borrador');
    },
  });

  // Cerrar Memoria
  const handleConfirmarCerrar = async () => {
    setCerrandoMemoria(true);
    setErrorGuardado(null);
    try {
      // Guardar primero para asegurar snapshot sincrónico
      const memGuardada = await guardarMutation.mutateAsync();
      const memCerrada = await api.cerrarMemoria(memGuardada.id);
      setMemoriaEstado('cerrada');
      setModalCerrarAbierto(false);
      queryClient.invalidateQueries({ queryKey: ['memorias', obraId] });
      queryClient.invalidateQueries({ queryKey: ['configuracion'] });
      // Redirigir a la vista de impresión oficial de la memoria cerrada
      navigate(`/memorias/${memCerrada.id}/imprimir`);
    } catch (err: any) {
      setErrorGuardado(err.message || 'Error al cerrar la memoria.');
      setModalCerrarAbierto(false);
    } finally {
      setCerrandoMemoria(false);
    }
  };

  const [descargandoPdf, setDescargandoPdf] = useState(false);
  const [descargandoExcel, setDescargandoExcel] = useState(false);
  const [fallbackModalMemoriaId, setFallbackModalMemoriaId] = useState<number | null>(null);
  const [fallbackModalError, setFallbackModalError] = useState<string | null>(null);

  const handleDescargarPdfPaso3 = async () => {
    let id = memoriaIdActivo;
    try {
      setDescargandoPdf(true);
      setErrorGuardado(null);
      if (!id) {
        const mem = await guardarMutation.mutateAsync();
        id = mem.id;
      }
      await api.descargarPdf(id);
    } catch (err: any) {
      const msg = err.message || 'Error al descargar el PDF';
      setErrorGuardado(msg);
      if (id) {
        setFallbackModalMemoriaId(id);
        setFallbackModalError(msg);
      }
    } finally {
      setDescargandoPdf(false);
    }
  };

  const handleDescargarExcelPaso3 = async () => {
    try {
      setDescargandoExcel(true);
      setErrorGuardado(null);
      let id = memoriaIdActivo;
      if (!id) {
        const mem = await guardarMutation.mutateAsync();
        id = mem.id;
      }
      await api.descargarExcel(id);
    } catch (err: any) {
      setErrorGuardado(err.message || 'Error al descargar el Excel');
    } finally {
      setDescargandoExcel(false);
    }
  };

  // ----------------------------------------------------
  // PASO 3: Ediciones Inline en Vista Previa
  // ----------------------------------------------------
  const [filaEditando, setFilaEditando] = useState<string | null>(null);
  const [editProveedor, setEditProveedor] = useState<string>('');
  const [editConcepto, setEditConcepto] = useState<string>('');
  const [editComprobante, setEditComprobante] = useState<string>('');

  const iniciarEdicionFila = (r: RenglonMemoria) => {
    if (memoriaEstado === 'cerrada') return;
    const key = `${r.ref_tipo}-${r.ref_id}`;
    setFilaEditando(key);
    setEditProveedor(r.proveedor || '');
    setEditConcepto(r.concepto || '');
    setEditComprobante(r.comprobante || '');
  };

  const guardarEdicionFila = (ref_tipo: string, ref_id: number) => {
    const nuevos = renglones.map((r) => {
      if (r.ref_tipo === ref_tipo && r.ref_id === ref_id) {
        return {
          ...r,
          proveedor: editProveedor.trim(),
          concepto: editConcepto.trim(),
          comprobante: editComprobante.trim(),
        };
      }
      return r;
    });
    setRenglones(nuevos);
    setFilaEditando(null);
  };

  const renglonesPorTab = useMemo(() => {
    return renglones.filter((r) => r.categoria === tabActiva);
  }, [renglones, tabActiva]);

  const conteoTabs = useMemo(() => {
    const contar = (cat: TabCategoria) => {
      const items = renglones.filter((r) => r.categoria === cat);
      const inc = items.filter((r) => r.incluido).length;
      return { total: items.length, incluidos: inc };
    };
    return {
      transferencia: contar('transferencia'),
      efectivo: contar('efectivo'),
      raya: contar('raya'),
      anticipo: contar('anticipo'),
    };
  }, [renglones]);

  interface SemanaAgrupadaLocal {
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

  // Agrupaciones para el Paso 3 (Vista Previa Carta)
  const previewAgrupado = useMemo(() => {
    const inc = renglones.filter((r) => r.incluido);
    const transf = inc.filter((r) => r.categoria === 'transferencia');
    const efec = inc.filter((r) => r.categoria === 'efectivo');
    const ray = inc.filter((r) => r.categoria === 'raya');
    const ant = inc.filter((r) => r.categoria === 'anticipo');

    const anioMem = fechaInicio ? parseInt(String(fechaInicio).slice(0, 4), 10) || 2026 : 2026;
    const mapaSem: Record<number, SemanaAgrupadaLocal> = {};
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
      rayas: ray,
      anticipos: ant,
      rayasPorSemana: semList,
    };
  }, [renglones]);

  if (cargandoObra) {
    return (
      <div className="p-8 max-w-5xl mx-auto space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!obra) {
    return (
      <div className="p-8 max-w-md mx-auto text-center text-zinc-600">
        <p>No se encontró la obra especificada.</p>
        <RouterLink to="/" className="text-stone-800 underline mt-4 inline-block">
          Volver a obras
        </RouterLink>
      </div>
    );
  }

  const saldoNum = parseFloat(totales?.saldo_a_favor || '0');
  const anticiposNum = parseFloat(totales?.anticipos_total || '0');
  const tieneAnticipos = anticiposNum > 0;
  const mostrarMemoriasAnteriores =
    numero > 1 || parseFloat(totales?.gastado_memorias_anteriores || '0') > 0;

  return (
    <div className="min-h-screen bg-stone-50 pb-28">
      {/* Encabezado y Breadcrumbs */}
      <div className="bg-white border-b border-zinc-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-1.5 text-xs text-zinc-500 mb-1">
                <RouterLink to="/" className="hover:text-zinc-900 transition-colors">
                  Obras
                </RouterLink>
                <span>/</span>
                <RouterLink to={`/obras/${obra.id}`} className="hover:text-zinc-900 transition-colors font-medium">
                  {obra.nombre}
                </RouterLink>
                <span>/</span>
                <span className="text-zinc-800 font-medium">Asistente de Memoria</span>
              </div>
              <h1 className="text-xl font-bold font-serif text-zinc-900 flex items-center gap-2">
                <span>Asistente de Memoria de Gastos — {obra.nombre}</span>
                {memoriaIdActivo && (
                  <Badge
                    variant="outline"
                    className={`text-xs ${
                      memoriaEstado === 'cerrada'
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
                        : 'bg-amber-50 text-amber-800 border-amber-300'
                    }`}
                  >
                    {memoriaEstado === 'cerrada' ? `Memoria #${numero} Cerrada` : `Editando Borrador #${numero}`}
                  </Badge>
                )}
              </h1>
            </div>

            {/* Stepper / Indicador de Pasos */}
            <div className="flex items-center gap-2 text-xs">
              <div
                onClick={() => setPaso(1)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full cursor-pointer transition-all ${
                  paso === 1
                    ? 'bg-stone-900 text-white font-semibold shadow-xs'
                    : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
                }`}
              >
                <span className="w-4 h-4 rounded-full bg-stone-700/50 flex items-center justify-center text-[10px]">
                  1
                </span>
                <span>Datos</span>
              </div>

              <ChevronRight className="w-4 h-4 text-zinc-400" />

              <div
                onClick={() => {
                  if (fechaInicio && fechaFin) {
                    setPaso(2);
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full cursor-pointer transition-all ${
                  paso === 2
                    ? 'bg-stone-900 text-white font-semibold shadow-xs'
                    : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
                }`}
              >
                <span className="w-4 h-4 rounded-full bg-stone-700/50 flex items-center justify-center text-[10px]">
                  2
                </span>
                <span>Selección</span>
              </div>

              <ChevronRight className="w-4 h-4 text-zinc-400" />

              <div
                onClick={() => {
                  if (fechaInicio && fechaFin) {
                    guardarMutation.mutate();
                    setPaso(3);
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full cursor-pointer transition-all ${
                  paso === 3
                    ? 'bg-stone-900 text-white font-semibold shadow-xs'
                    : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200'
                }`}
              >
                <span className="w-4 h-4 rounded-full bg-stone-700/50 flex items-center justify-center text-[10px]">
                  3
                </span>
                <span>Vista Previa y Cierre</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-6">
        {/* Banner de Borrador Existente si no se ha cargado */}
        {!memoriaIdActivo && borradorGuardado && paso === 1 && (
          <div className="mb-6 p-4 bg-amber-50/80 border border-amber-200 rounded-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-amber-900">
                  Se encontró un borrador guardado para esta obra: Memoria #{borradorGuardado.numero}
                </p>
                <p className="text-xs text-amber-700">
                  Periodo del {formatDate(borradorGuardado.fecha_inicio)} al {formatDate(borradorGuardado.fecha_fin)}.
                  Puedes reanudarlo para conservar tus selecciones previas o iniciar uno nuevo.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                size="sm"
                variant="outline"
                onClick={() => reanudarBorrador(borradorGuardado.id)}
                className="text-xs border-amber-300 bg-white hover:bg-amber-100/50 text-amber-900"
              >
                Reanudar Borrador #{borradorGuardado.numero}
              </Button>
            </div>
          </div>
        )}

        {/* Notificaciones de éxito o error */}
        {avisoGuardado && (
          <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-md text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            <span>{avisoGuardado}</span>
          </div>
        )}

        {errorGuardado && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{errorGuardado}</span>
          </div>
        )}

        {/* ========================================================
            PASO 1: FORMULARIO DE DATOS DE LA MEMORIA
           ======================================================== */}
        {paso === 1 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 bg-white rounded-lg border border-zinc-200 shadow-2xs p-6 space-y-6">
              <div>
                <h2 className="text-base font-semibold text-zinc-900 mb-1">
                  Paso 1: Parámetros de la Memoria
                </h2>
                <p className="text-xs text-zinc-500">
                  Define el número de memoria, rango de fechas y los datos que encabezarán el formato de liquidación.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Número de Memoria <span className="text-red-500">*</span>
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-2 text-xs font-mono font-bold text-zinc-400">#</span>
                    <input
                      type="number"
                      min={1}
                      value={numero}
                      onChange={(e) => setNumero(parseInt(e.target.value, 10) || 1)}
                      className="w-full pl-8 pr-3 py-1.5 text-xs font-mono font-bold rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-600"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Folio de Factura del Arquitecto
                  </label>
                  <input
                    type="text"
                    value={folioFactura}
                    onChange={(e) => setFolioFactura(e.target.value)}
                    placeholder="Ej. 52"
                    className="w-full px-3 py-1.5 text-xs font-mono rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-600"
                  />
                  {folioVerif?.usado && (
                    <div className="mt-1 flex items-start gap-1 text-[11px] text-amber-700 bg-amber-50 p-1.5 rounded border border-amber-200">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      <span>
                        Aviso: El folio <strong>"{folioFactura}"</strong> ya fue utilizado en la Memoria #{folioVerif.memoria_numero} de {folioVerif.obra_nombre} ({folioVerif.estado}).
                      </span>
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Fecha de Inicio de Periodo <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={fechaInicio}
                    onChange={(e) => setFechaInicio(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-600"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Fecha de Fin de Periodo <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="date"
                    value={fechaFin}
                    onChange={(e) => setFechaFin(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-600"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Fecha de Emisión de la Memoria
                  </label>
                  <input
                    type="date"
                    value={fechaEmision}
                    onChange={(e) => setFechaEmision(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-600"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Ciudad / Plaza
                  </label>
                  <input
                    type="text"
                    value={ciudad}
                    onChange={(e) => setCiudad(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-600"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">
                    Porcentaje de Honorarios (%) para esta Memoria
                  </label>
                  <div className="flex items-center gap-2 max-w-xs">
                    <div className="relative w-full">
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        value={porcentajeHonorarios}
                        onChange={(e) => setPorcentajeHonorarios(e.target.value)}
                        className="w-full pl-3 pr-8 py-1.5 text-xs font-mono font-semibold rounded-md border border-zinc-300 focus:outline-none focus:ring-1 focus:ring-stone-600"
                      />
                      <span className="absolute right-3 top-2 text-xs font-semibold text-zinc-400">%</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-zinc-100 flex items-center justify-between">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate(`/obras/${obra.id}`)}
                  className="text-xs"
                >
                  Cancelar
                </Button>

                <Button
                  size="sm"
                  onClick={() => {
                    if (!fechaInicio || !fechaFin) {
                      setErrorGuardado('Debes especificar fecha de inicio y fin.');
                      return;
                    }
                    setErrorGuardado(null);
                    setPaso(2);
                    cargarPreviewBackend();
                  }}
                  className="flex items-center gap-1.5 text-xs bg-stone-900 hover:bg-stone-800 text-white"
                >
                  <span>Continuar a Selección de Gastos</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </div>

            <div className="space-y-4">
              <div className="bg-white rounded-lg border border-zinc-200 shadow-2xs p-5 space-y-3 text-xs">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                  Información de la Obra
                </h3>
                <div>
                  <span className="text-zinc-500 block text-[11px]">Nombre de Obra:</span>
                  <span className="font-semibold text-zinc-900 text-sm">{obra.nombre}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[11px]">Propietario / Cliente:</span>
                  <span className="text-zinc-800 font-medium">{obra.propietario || 'No especificado'}</span>
                </div>
                <div>
                  <span className="text-zinc-500 block text-[11px]">Ubicación:</span>
                  <span className="text-zinc-700">{obra.ubicacion || 'No especificada'}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================
            PASO 2: SELECCIÓN DE GASTOS Y REVISIÓN DE RUBROS
           ======================================================== */}
        {paso === 2 && (
          <div className="space-y-4">
            <div className="bg-white border border-zinc-200 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-2xs">
              <div className="flex flex-wrap items-center gap-3 text-xs">
                <Badge variant="outline" className="font-mono text-xs font-bold bg-stone-100 text-stone-900">
                  Memoria #{numero}
                </Badge>
                <div className="text-zinc-600 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-zinc-400" />
                  <span>
                    Periodo: <strong>{formatDate(fechaInicio)}</strong> al <strong>{formatDate(fechaFin)}</strong>
                  </span>
                </div>
                <div className="text-zinc-600 flex items-center gap-1">
                  <Percent className="w-3.5 h-3.5 text-zinc-400" />
                  <span>
                    Honorarios: <strong>{porcentajeHonorarios}%</strong>
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPaso(1)}
                  className="text-xs text-zinc-600"
                >
                  Editar Parámetros
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setModalGastosExtraAbierto(true)}
                  className="text-xs flex items-center gap-1.5 border-stone-300 text-stone-800 bg-stone-50 hover:bg-stone-100"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Agregar de otra obra o fuera de rango</span>
                </Button>
              </div>
            </div>

            {/* Aviso de Semanas que terminan después del periodo */}
            {tabActiva === 'raya' && rayasPosteriores.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-amber-900">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                  <span>
                    <strong>{rayasPosteriores.length} registro(s) de raya</strong> empiezan en el periodo pero terminan después (fecha de pago {formatDate(rayasPosteriores[0]?.fecha)}).
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleAgregarRayasPosteriores}
                  className="text-xs border-amber-300 bg-white hover:bg-amber-100 text-amber-900 shrink-0"
                >
                  Agregar a esta memoria
                </Button>
              </div>
            )}

            {/* Pestañas de categorías */}
            <div className="border-b border-zinc-200 flex items-center gap-2 overflow-x-auto bg-white px-2 pt-2 rounded-t-lg">
              <button
                type="button"
                onClick={() => setTabActiva('transferencia')}
                className={`flex items-center gap-2 py-2.5 px-4 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                  tabActiva === 'transferencia'
                    ? 'border-stone-900 text-stone-900 font-semibold'
                    : 'border-transparent text-zinc-500 hover:text-zinc-800'
                }`}
              >
                <span>Transferencias</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                    tabActiva === 'transferencia'
                      ? 'bg-stone-900 text-white'
                      : 'bg-zinc-100 text-zinc-600'
                  }`}
                >
                  {conteoTabs.transferencia.incluidos}/{conteoTabs.transferencia.total}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setTabActiva('efectivo')}
                className={`flex items-center gap-2 py-2.5 px-4 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                  tabActiva === 'efectivo'
                    ? 'border-stone-900 text-stone-900 font-semibold'
                    : 'border-transparent text-zinc-500 hover:text-zinc-800'
                }`}
              >
                <span>Efectivo (Notas y Facturas)</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                    tabActiva === 'efectivo'
                      ? 'bg-stone-900 text-white'
                      : 'bg-zinc-100 text-zinc-600'
                  }`}
                >
                  {conteoTabs.efectivo.incluidos}/{conteoTabs.efectivo.total}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setTabActiva('raya')}
                className={`flex items-center gap-2 py-2.5 px-4 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                  tabActiva === 'raya'
                    ? 'border-stone-900 text-stone-900 font-semibold'
                    : 'border-transparent text-zinc-500 hover:text-zinc-800'
                }`}
              >
                <span>Rayas de Albañilería</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                    tabActiva === 'raya'
                      ? 'bg-stone-900 text-white'
                      : 'bg-zinc-100 text-zinc-600'
                  }`}
                >
                  {conteoTabs.raya.incluidos}/{conteoTabs.raya.total}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setTabActiva('anticipo')}
                className={`flex items-center gap-2 py-2.5 px-4 text-xs font-medium border-b-2 transition-all whitespace-nowrap ${
                  tabActiva === 'anticipo'
                    ? 'border-stone-900 text-stone-900 font-semibold'
                    : 'border-transparent text-zinc-500 hover:text-zinc-800'
                }`}
              >
                <span>Anticipos Recibidos</span>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono ${
                    tabActiva === 'anticipo'
                      ? 'bg-stone-900 text-white'
                      : 'bg-zinc-100 text-zinc-600'
                  }`}
                >
                  {conteoTabs.anticipo.incluidos}/{conteoTabs.anticipo.total}
                </span>
              </button>
            </div>

            <div className="bg-white border-x border-b border-zinc-200 px-4 py-2.5 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSeleccionarTodosTab(true)}
                  className="text-xs text-zinc-700 hover:text-zinc-900 flex items-center gap-1"
                >
                  <CheckSquare className="w-3.5 h-3.5" />
                  <span>Seleccionar todo</span>
                </Button>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSeleccionarTodosTab(false)}
                  className="text-xs text-zinc-700 hover:text-zinc-900 flex items-center gap-1"
                >
                  <Square className="w-3.5 h-3.5" />
                  <span>Deseleccionar todo</span>
                </Button>
              </div>

              <div className="text-zinc-500 text-[11px]">
                {renglonesPorTab.length} registro(s) en este rubro
              </div>
            </div>

            {/* Tabla de selección */}
            <div className="bg-white border border-zinc-200 rounded-b-lg overflow-hidden shadow-2xs">
              {renglonesPorTab.length === 0 ? (
                <div className="p-12 text-center text-xs text-zinc-500 space-y-2">
                  <p className="font-medium text-zinc-700">
                    No hay registros de {tabActiva} en el periodo seleccionado.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-600 font-semibold uppercase text-[10px]">
                      <tr>
                        <th className="py-2.5 px-4 w-10 text-center">Incluir</th>
                        <th className="py-2.5 px-4 w-24">Fecha</th>
                        <th className="py-2.5 px-4">
                          {tabActiva === 'raya' ? 'Trabajador / Oficio' : 'Proveedor'}
                        </th>
                        <th className="py-2.5 px-4">Concepto</th>
                        <th className="py-2.5 px-4 min-w-[140px] whitespace-nowrap">Comprobante</th>
                        <th className="py-2.5 px-4 w-36">Estado / Origen</th>
                        <th className="py-2.5 px-4 text-right w-28">Importe</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100 font-normal text-zinc-800">
                      {renglonesPorTab.map((r) => {
                        const esCerrado = !!r.ya_incluido_en;
                        return (
                          <tr
                            key={`${r.ref_tipo}-${r.ref_id}`}
                            className={`transition-colors ${
                              esCerrado
                                ? 'bg-zinc-50/60 text-zinc-400'
                                : r.incluido
                                ? 'hover:bg-zinc-50/60'
                                : 'bg-zinc-50/30 text-zinc-500'
                            }`}
                          >
                            <td className="py-2.5 px-4 text-center">
                              <input
                                type="checkbox"
                                checked={r.incluido}
                                disabled={esCerrado}
                                onChange={() => handleToggleRenglon(r.ref_tipo, r.ref_id)}
                                className={`rounded border-zinc-300 text-stone-800 focus:ring-stone-500 w-4 h-4 ${
                                  esCerrado ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'
                                }`}
                              />
                            </td>
                            <td className="py-2.5 px-4 whitespace-nowrap text-zinc-600 font-mono text-[11px]">
                              {formatDate(r.fecha)}
                            </td>
                            <td className="py-2.5 px-4 font-medium text-zinc-900">
                              {r.proveedor || '—'}
                              {r.oficio && (
                                <span className="text-[10px] text-zinc-500 block font-normal">
                                  {r.oficio}
                                </span>
                              )}
                            </td>
                            <td className="py-2.5 px-4 text-zinc-700">
                              {r.concepto}
                            </td>
                            <td className="py-2.5 px-4 font-mono text-zinc-600 text-[11px] min-w-[140px] whitespace-nowrap">
                              {r.comprobante || '—'}
                            </td>
                            <td className="py-2.5 px-4 whitespace-nowrap space-x-1">
                              {esCerrado && (
                                <Badge
                                  variant="outline"
                                  className="text-[10px] bg-amber-50 text-amber-800 border-amber-300 font-medium"
                                >
                                  {r.ya_incluido_en}
                                </Badge>
                              )}
                              {r.en_otro_borrador && !esCerrado && (
                                <Badge
                                  variant="outline"
                                  className="text-[10px] bg-yellow-50 text-yellow-800 border-yellow-300 font-medium"
                                >
                                  {r.en_otro_borrador}
                                </Badge>
                              )}
                              {r.es_externo && (
                                <Badge
                                  variant="outline"
                                  className="text-[10px] bg-blue-50 text-blue-700 border-blue-200 font-medium"
                                >
                                  Obra: {r.obra_origen || 'Externa'}
                                </Badge>
                              )}
                            </td>
                            <td className="py-2.5 px-4 text-right font-mono font-semibold text-zinc-900 whitespace-nowrap">
                              {formatMoney(r.importe)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================
            PASO 3: VISTA PREVIA EDITABLE Y CIERRE (FORMATO CARTA)
           ======================================================== */}
        {paso === 3 && (
          <div className="space-y-6">
            {/* Barra de control superior del Paso 3 */}
            <div className="bg-white border border-zinc-200 rounded-lg p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-2xs">
              <div className="flex items-center gap-2 text-xs">
                <span className="font-bold text-zinc-800 uppercase">Vista Previa Oficial:</span>
                <span className="text-zinc-500">
                  Haz clic en cualquier proveedor, concepto o comprobante para editarlo exclusivamente en esta memoria.
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPaso(2)}
                  className="text-xs flex items-center gap-1"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Volver a Selección</span>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => guardarMutation.mutate()}
                  disabled={guardarMutation.isPending}
                  className="text-xs"
                >
                  Guardar Borrador
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  disabled={descargandoPdf}
                  onClick={handleDescargarPdfPaso3}
                  className="text-xs flex items-center gap-1 border-stone-300"
                >
                  {descargandoPdf ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <FileDown className="w-3.5 h-3.5 text-red-600" />
                  )}
                  <span>Descargar PDF</span>
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  disabled={descargandoExcel}
                  onClick={handleDescargarExcelPaso3}
                  className="text-xs flex items-center gap-1 border-stone-300"
                >
                  {descargandoExcel ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                  )}
                  <span>Descargar Excel</span>
                </Button>

                {memoriaIdActivo && (
                  <RouterLink to={`/memorias/${memoriaIdActivo}/imprimir`} target="_blank">
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs flex items-center gap-1 border-stone-300"
                    >
                      <Printer className="w-3.5 h-3.5" />
                      <span>Imprimir Hoja Carta</span>
                      <ExternalLink className="w-3 h-3 text-zinc-400" />
                    </Button>
                  </RouterLink>
                )}

                {memoriaEstado === 'borrador' && (
                  <Button
                    size="sm"
                    onClick={() => setModalCerrarAbierto(true)}
                    className="text-xs flex items-center gap-1 bg-emerald-700 hover:bg-emerald-800 text-white"
                  >
                    <Lock className="w-3.5 h-3.5" />
                    <span>Cerrar Memoria</span>
                  </Button>
                )}
              </div>
            </div>

            {/* Hoja 1: Parte del Cliente (Página 1) */}
            <div className="max-w-[216mm] mx-auto bg-white border border-zinc-200 shadow-md p-8 sm:p-10 space-y-4 text-[10.5px]">
              <div className="border-b-2 border-zinc-900 pb-3 flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-xl font-bold font-serif tracking-tight text-zinc-900 uppercase">
                      MEMORIA {String(numero).padStart(2, '0')}
                    </h1>
                    {memoriaEstado === 'borrador' && (
                      <span className="text-[9.5px] font-bold px-2 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 rounded uppercase tracking-wider">
                        BORRADOR
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-bold text-zinc-700 uppercase mt-0.5">
                    OBRA: {obra.nombre.toUpperCase()}
                  </p>
                  <p className="text-[10px] text-zinc-600 uppercase">
                    UBICACIÓN: {obra.ubicacion?.toUpperCase() || 'NO ESPECIFICADA'}
                  </p>
                  <p className="text-[10px] text-zinc-600 uppercase">
                    PROPIETARIO: {obra.propietario?.toUpperCase() || 'NO ESPECIFICADO'}
                  </p>
                </div>

                <div className="text-right text-[10px] space-y-0.5">
                  <p className="font-semibold text-zinc-900 uppercase">FECHA: {formatDate(fechaEmision)}</p>
                  <p className="text-zinc-600 uppercase">CIUDAD: {ciudad.toUpperCase()}</p>
                  <p className="text-zinc-600 uppercase font-mono">
                    PERIODO: {formatDate(fechaInicio)} AL {formatDate(fechaFin)}
                  </p>
                  {folioFactura && (
                    <p className="text-zinc-800 font-mono font-semibold uppercase">
                      FACTURA ARQ: {formatFolioFactura(folioFactura)}
                    </p>
                  )}
                </div>
              </div>

              {/* TABLA 1: TRANSFERENCIAS */}
              <div className="space-y-1">
                <table className="w-full text-left border-collapse">
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
                    {previewAgrupado.transferencias.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                          SIN PAGOS POR TRANSFERENCIA EN EL PERIODO
                        </td>
                      </tr>
                    ) : (
                      previewAgrupado.transferencias.map((r) => {
                        const isEditing = filaEditando === `${r.ref_tipo}-${r.ref_id}`;
                        return (
                          <tr
                            key={`prev-t-${r.ref_tipo}-${r.ref_id}`}
                            onClick={() => !isEditing && iniciarEdicionFila(r)}
                            className="hover:bg-amber-50/50 cursor-pointer transition-colors"
                          >
                            <td className="py-1 px-1.5 uppercase font-medium">
                              {isEditing ? (
                                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                                  <input
                                    type="text"
                                    placeholder="PROVEEDOR"
                                    value={editProveedor}
                                    onChange={(e) => setEditProveedor(e.target.value)}
                                    className="w-28 border border-stone-400 px-1 py-0.5 rounded text-[9px] uppercase font-bold"
                                  />
                                  <span className="text-zinc-400">:</span>
                                  <input
                                    type="text"
                                    placeholder="CONCEPTO"
                                    value={editConcepto}
                                    onChange={(e) => setEditConcepto(e.target.value)}
                                    className="w-48 border border-stone-400 px-1 py-0.5 rounded text-[9px] uppercase"
                                  />
                                </div>
                              ) : (
                                <>
                                  {r.proveedor ? `${r.proveedor.toUpperCase()}: ` : ''}
                                  {r.concepto?.toUpperCase()}
                                </>
                              )}
                            </td>
                            <td className="py-1 px-1.5 font-mono text-[9px] uppercase">
                              {isEditing ? (
                                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                                  <input
                                    type="text"
                                    value={editComprobante}
                                    onChange={(e) => setEditComprobante(e.target.value)}
                                    className="w-20 border border-stone-400 px-1 py-0.5 rounded text-[9px] uppercase"
                                  />
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      guardarEdicionFila(r.ref_tipo, r.ref_id);
                                    }}
                                    className="p-0.5 bg-emerald-600 text-white rounded hover:bg-emerald-700"
                                    title="Guardar"
                                  >
                                    <Check className="w-3 h-3" />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setFilaEditando(null);
                                    }}
                                    className="p-0.5 bg-zinc-300 text-zinc-700 rounded hover:bg-zinc-400"
                                    title="Cancelar"
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                </div>
                              ) : (
                                r.comprobante?.toUpperCase() || '—'
                              )}
                            </td>
                            <td className="py-1 px-1.5 font-mono text-[9px]">{formatDate(r.fecha)}</td>
                            <td className="py-1 px-1.5 text-right font-mono font-medium">
                              {formatMoneySimple(r.importe)}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-zinc-800 font-bold bg-zinc-50 text-[10px]">
                      <td colSpan={3} className="py-1 px-1.5 text-right uppercase">
                        PAGOS TRANSFER. DE ESTA MEMORIA:
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono">
                        {formatMoneySimple(totales?.transferencias)}
                      </td>
                    </tr>
                  </tfoot>
                </table>

                {/* BLOQUE INDEPENDIENTE: RESUMEN DE TRANSFERENCIAS */}
                <div className="pt-1.5 pb-0.5">
                  <div className="border border-zinc-300 bg-zinc-50/60 p-2 text-[9.5px] max-w-sm ml-auto space-y-1">
                    <div className="font-bold uppercase text-zinc-800 border-b border-zinc-200 pb-0.5 text-[9px]">
                      RESUMEN DE TRANSFERENCIAS
                    </div>
                    <div className="flex justify-between font-mono text-[9px]">
                      <span className="text-zinc-600 uppercase">ACUMULADO A LA FECHA:</span>
                      <span className="font-semibold">
                        {formatMoneySimple(totales?.transferencias_memorias_anteriores || '0.00')}
                      </span>
                    </div>
                    <div className="flex justify-between font-mono text-[9px]">
                      <span className="text-zinc-600 uppercase">DE ESTA MEMORIA:</span>
                      <span className="font-semibold">{formatMoneySimple(totales?.transferencias)}</span>
                    </div>
                    <div className="flex justify-between font-mono text-[9.5px] font-bold border-t border-zinc-200 pt-0.5">
                      <span className="uppercase text-zinc-800">TOTAL:</span>
                      <span>{formatMoneySimple(totales?.acumulado_transferencias)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* TABLA 2: NOTAS Y FACTURAS EN EFECTIVO */}
              <div className="space-y-1 pt-1">
                <table className="w-full text-left border-collapse">
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
                    {previewAgrupado.efectivo.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                          SIN GASTOS EN EFECTIVO EN EL PERIODO
                        </td>
                      </tr>
                    ) : (
                      previewAgrupado.efectivo.map((r) => {
                        const isEditing = filaEditando === `${r.ref_tipo}-${r.ref_id}`;
                        return (
                          <tr
                            key={`prev-e-${r.ref_tipo}-${r.ref_id}`}
                            onClick={() => !isEditing && iniciarEdicionFila(r)}
                            className="hover:bg-amber-50/50 cursor-pointer transition-colors"
                          >
                            <td className="py-1 px-1.5 uppercase font-medium">
                              {isEditing ? (
                                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                                  <input
                                    type="text"
                                    placeholder="PROVEEDOR"
                                    value={editProveedor}
                                    onChange={(e) => setEditProveedor(e.target.value)}
                                    className="w-28 border border-stone-400 px-1 py-0.5 rounded text-[9px] uppercase font-bold"
                                  />
                                  <span className="text-zinc-400">:</span>
                                  <input
                                    type="text"
                                    placeholder="CONCEPTO"
                                    value={editConcepto}
                                    onChange={(e) => setEditConcepto(e.target.value)}
                                    className="w-48 border border-stone-400 px-1 py-0.5 rounded text-[9px] uppercase"
                                  />
                                </div>
                              ) : (
                                <>
                                  {r.proveedor ? `${r.proveedor.toUpperCase()}: ` : ''}
                                  {r.concepto?.toUpperCase()}
                                </>
                              )}
                            </td>
                            <td className="py-1 px-1.5 font-mono text-[9px] uppercase">
                              {isEditing ? (
                                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                                  <input
                                    type="text"
                                    value={editComprobante}
                                    onChange={(e) => setEditComprobante(e.target.value)}
                                    className="w-20 border border-stone-400 px-1 py-0.5 rounded text-[9px] uppercase"
                                  />
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      guardarEdicionFila(r.ref_tipo, r.ref_id);
                                    }}
                                    className="p-0.5 bg-emerald-600 text-white rounded hover:bg-emerald-700"
                                    title="Guardar"
                                  >
                                    <Check className="w-3 h-3" />
                                  </button>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setFilaEditando(null);
                                    }}
                                    className="p-0.5 bg-zinc-300 text-zinc-700 rounded hover:bg-zinc-400"
                                    title="Cancelar"
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                </div>
                              ) : (
                                r.comprobante?.toUpperCase() || '—'
                              )}
                            </td>
                            <td className="py-1 px-1.5 font-mono text-[9px]">{formatDate(r.fecha)}</td>
                            <td className="py-1 px-1.5 text-right font-mono font-medium">
                              {formatMoneySimple(r.importe)}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-zinc-800 font-bold bg-zinc-50 text-[10px]">
                      <td colSpan={3} className="py-1 px-1.5 text-right uppercase">
                        TOTAL NOTAS Y FACTURAS EN EFECTIVO:
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono">
                        {formatMoneySimple(totales?.efectivo)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {/* TABLA 3: RAYAS */}
              <div className="space-y-1 pt-1">
                <table className="w-full text-left border-collapse">
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
                    {previewAgrupado.rayasPorSemana.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                          SIN RAYAS DE ALBAÑILERÍA EN EL PERIODO
                        </td>
                      </tr>
                    ) : (
                      previewAgrupado.rayasPorSemana.map((s) => (
                        <tr key={`prev-sem-${s.semana}`}>
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
                        {formatMoneySimple(totales?.rayas)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {/* CIERRE DE LA HOJA: ORDEN EXACTO DEL EXCEL MEMORIA 01 */}
              <div className="pt-2 border-t-2 border-zinc-900">
                <div className="max-w-md ml-auto space-y-1 font-mono text-[10px]">
                  <div className="flex justify-between py-0.5 border-b border-zinc-100">
                    <span className="uppercase font-sans font-medium text-zinc-700">
                      HONORARIOS {totales?.porcentaje_honorarios}% (PAGOS TRANSF.)
                    </span>
                    <span>{formatMoneySimple(totales?.hon_transferencias)}</span>
                  </div>

                  <div className="flex justify-between py-0.5 border-b border-zinc-100">
                    <span className="uppercase font-sans font-medium text-zinc-700">
                      HONORARIOS {totales?.porcentaje_honorarios}% (PAGOS EFECTIVO)
                    </span>
                    <span>{formatMoneySimple(totales?.hon_efectivo)}</span>
                  </div>

                  <div className="flex justify-between py-0.5 border-b border-zinc-100">
                    <span className="uppercase font-sans font-medium text-zinc-700">
                      HONORARIOS {totales?.porcentaje_honorarios}% (PAGOS DE RAYAS)
                    </span>
                    <span>{formatMoneySimple(totales?.hon_rayas)}</span>
                  </div>

                  <div className="flex justify-between py-0.5 border-b border-zinc-200 font-bold">
                    <span className="uppercase font-sans">SUBTOTAL</span>
                    <span>{formatMoneySimple(totales?.subtotal)}</span>
                  </div>

                  <div className="flex justify-between py-0.5 border-b border-zinc-100">
                    <span className="uppercase font-sans font-medium text-zinc-700">IVA 16%</span>
                    <span>{formatMoneySimple(totales?.iva)}</span>
                  </div>

                  {/* IMPORTE DE ESTA MEMORIA F-XXX */}
                  <div className="py-1 border-b border-zinc-300">
                    <div className="flex justify-between font-bold text-zinc-900">
                      <span className="uppercase font-sans">
                        {folioFactura
                          ? `IMPORTE DE ESTA MEMORIA ${formatFolioFactura(folioFactura)}`
                          : 'IMPORTE DE ESTA MEMORIA (FACTURA)'}
                      </span>
                      <span>{formatMoneySimple(totales?.importe_factura)}</span>
                    </div>
                    {importeFacturaTexto && (
                      <p className="text-[8.5px] text-zinc-600 uppercase text-right mt-0.5 italic">
                        {formatTextoEnLetra(importeFacturaTexto)}
                      </p>
                    )}
                  </div>

                  {/* IMPORTE DE ESTA MEMORIA (TOTAL) */}
                  <div className="py-1 border-b-2 border-zinc-800 bg-zinc-50/70 px-1.5 -mx-1.5">
                    <div className="flex justify-between text-[11px] font-bold text-zinc-950">
                      <span className="uppercase font-sans">IMPORTE DE ESTA MEMORIA:</span>
                      <span>{formatMoneySimple(totales?.total_memoria)}</span>
                    </div>
                    {totalTexto && (
                      <p className="text-[8.5px] text-zinc-700 uppercase text-right mt-0.5 italic">
                        {formatTextoEnLetra(totalTexto)}
                      </p>
                    )}
                  </div>

                  {/* IMPORTE DE MEMORIAS ANTERIORES: (si numero > 1 o hay acumulado) */}
                  {(numero > 1 || parseFloat(totales?.gastado_memorias_anteriores || '0') > 0) && (
                    <div className="flex justify-between py-0.5 border-b border-zinc-100 text-zinc-600">
                      <span className="uppercase font-sans">
                        IMPORTE DE MEMORIAS ANTERIORES:
                      </span>
                      <span>{formatMoneySimple(totales?.gastado_memorias_anteriores || '0')}</span>
                    </div>
                  )}

                  {/* IMPORTE DE MEMORIA 01 A {N}: (siempre visible) */}
                  <div className="flex justify-between py-0.5 border-b border-zinc-100 text-zinc-700">
                    <span className="uppercase font-sans">
                      IMPORTE DE MEMORIA 01 A {String(numero).padStart(2, '0')}:
                    </span>
                    <span>{formatMoneySimple(totales?.gastado_a_la_fecha)}</span>
                  </div>

                  {/* GASTADO A LA FECHA */}
                  <div className="py-1 border-t border-zinc-300">
                    <div className="flex justify-between text-[11px] font-bold text-zinc-900">
                      <span className="uppercase font-sans">GASTADO A LA FECHA:</span>
                      <span>{formatMoneySimple(totales?.gastado_a_la_fecha)}</span>
                    </div>
                    {(gastadoFechaTexto || totales?.gastado_a_la_fecha_texto) && (
                      <p className="text-[8.5px] text-zinc-600 uppercase text-right mt-0.5 italic">
                        {formatTextoEnLetra(gastadoFechaTexto || totales?.gastado_a_la_fecha_texto)}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* TABLA 4: ANTICIPOS RECIBIDOS (solo si hay anticipos) */}
              {previewAgrupado.anticipos.length > 0 && (
                <div className="space-y-1 pt-2">
                  <div className="bg-zinc-800 text-white px-2 py-1 font-bold text-[10px] uppercase tracking-wider flex justify-between">
                    <span>ANTICIPOS RECIBIDOS:</span>
                    <span>IMPORTE</span>
                  </div>

                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-zinc-300 text-[9px] uppercase font-bold text-zinc-700 bg-zinc-50">
                        <th className="py-1 px-1.5 w-24">FECHA:</th>
                        <th className="py-1 px-1.5">COMPROBANTE:</th>
                        <th className="py-1 px-1.5 text-right w-28">IMPORTE:</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 text-[9.5px]">
                      {previewAgrupado.anticipos.map((a) => (
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
                          {formatMoneySimple(totales?.anticipos_total)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}

              {/* PIE DE PÁGINA EN MAYÚSCULAS CON FORMATO LARGO */}
              <div className="pt-4 text-center text-[10px] font-bold uppercase tracking-wide text-zinc-700">
                {formatFechaLarga(ciudad, fechaEmision)}
              </div>
            </div>

            {/* Hoja 2: Parte del Arquitecto (Página 2) */}
            <div className="max-w-[216mm] mx-auto bg-white border border-zinc-200 shadow-md p-8 sm:p-10 space-y-3.5 text-[10px] sm:text-[10.5px]">
              {/* Encabezado Arquitecto */}
              <div className="border-b-2 border-zinc-900 pb-2">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold font-serif uppercase tracking-tight text-zinc-900">
                    RESUMEN MEMORIA {String(numero).padStart(2, '0')}:
                  </h2>
                  {memoriaEstado === 'borrador' && (
                    <span className="text-[9px] font-bold px-1.5 py-0.5 bg-amber-100 text-amber-900 border border-amber-300 rounded uppercase tracking-wider">
                      BORRADOR
                    </span>
                  )}
                </div>
                <p className="text-[9.5px] text-zinc-600 uppercase font-mono mt-0.5">
                  OBRA: {obra.nombre.toUpperCase()} · FECHA: {formatDate(fechaEmision)}
                </p>
              </div>

              {/* Cuadro Financiero del Arquitecto */}
              <div className="bg-stone-50 border border-stone-200 p-3 rounded space-y-2 text-[10px]">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Columna Izquierda: Honorarios */}
                  <div className="space-y-1 font-mono">
                    <div className="text-[9.5px] font-bold uppercase text-zinc-800 font-sans border-b border-stone-200 pb-0.5">
                      HONORARIOS:
                    </div>
                    <div className="flex justify-between text-[10px]">
                      <span className="font-sans text-zinc-700 uppercase">HONORARIOS:</span>
                      <span className="font-bold">{formatMoneySimple(totales?.honorarios)}</span>
                    </div>
                    <div className="flex justify-between text-[10px]">
                      <span className="font-sans text-zinc-700 uppercase">IVA TOTAL 16%:</span>
                      <span>{formatMoneySimple(totales?.iva)}</span>
                    </div>
                    <div className="flex justify-between text-[10.5px] font-bold text-zinc-900 pt-0.5 border-t border-stone-200">
                      <span className="font-sans uppercase">TOTAL HONORARIOS:</span>
                      <span>
                        {formatMoneySimple(
                          totales?.total_honorarios ||
                            (parseFloat(totales?.honorarios || '0') + parseFloat(totales?.iva || '0')).toFixed(2)
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
                      <span>{formatMoneySimple(totales?.efectivo)}</span>
                    </div>
                    <div className="flex justify-between text-[10px]">
                      <span className="font-sans text-zinc-700 uppercase">NÓMINA:</span>
                      <span>{formatMoneySimple(totales?.rayas)}</span>
                    </div>
                    <div className="flex justify-between text-[10.5px] font-bold text-zinc-900 pt-0.5 border-t border-stone-200">
                      <span className="font-sans uppercase">COBRADO:</span>
                      <span>{formatMoneySimple(totales?.cobrado)}</span>
                    </div>
                  </div>
                </div>

                {/* Fila de Anticipos y Saldo a Favor / Anticipo Pendiente */}
                {tieneAnticipos && (
                  <div className="pt-2 border-t border-stone-200 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                    <div className="text-[10px]">
                      <span className="text-zinc-600 uppercase font-medium">ANTICIPOS: </span>
                      <span className="font-mono font-bold text-zinc-800">
                        -{formatMoneySimple(totales?.anticipos_total)}
                      </span>
                    </div>

                    {saldoNum >= 0 ? (
                      <div className="bg-emerald-50 text-emerald-900 border border-emerald-300 px-3 py-1 rounded text-xs font-bold flex items-center gap-1.5">
                        <span className="uppercase">SALDO A MI FAVOR:</span>
                        <span className="font-mono">{formatMoneySimple(totales?.saldo_a_favor)}</span>
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
                <div className="bg-zinc-800 text-white px-2 py-1 font-bold text-[10px] uppercase tracking-wider flex justify-between">
                  <span>RECUPERACIÓN DE CAJA CHICA.</span>
                  <span>TOTAL: {formatMoneySimple(totales?.efectivo)}</span>
                </div>

                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-zinc-300 text-[9px] uppercase font-bold text-zinc-700 bg-zinc-50">
                      <th className="py-1 px-1.5">CONCEPTO:</th>
                      <th className="py-1 px-1.5 w-32">COMPROBANTE:</th>
                      <th className="py-1 px-1.5 w-20">FECHA:</th>
                      <th className="py-1 px-1.5 text-right w-24">IMPORTE:</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 text-[9px]">
                    {previewAgrupado.efectivo.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-2 text-center text-zinc-400 italic">
                          SIN MOVIMIENTOS DE CAJA CHICA
                        </td>
                      </tr>
                    ) : (
                      previewAgrupado.efectivo.map((r) => (
                        <tr key={`arch-e-${r.ref_id}`}>
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
                        {formatMoneySimple(totales?.efectivo)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>

              {/* DETALLE DE DESTAJOS/RAYAS POR SEMANA */}
              <div className="space-y-3 pt-2">
                <div className="bg-zinc-800 text-white px-2 py-1 font-bold text-[10px] uppercase tracking-wider flex justify-between">
                  <span>DETALLE DE DESTAJOS/RAYAS POR SEMANA:</span>
                  <span>TOTAL NÓMINA: {formatMoneySimple(totales?.rayas)}</span>
                </div>

                {previewAgrupado.rayasPorSemana.length === 0 ? (
                  <div className="py-2 text-center text-zinc-400 italic text-[9.5px]">
                    SIN REGISTRO DE RAYAS EN EL PERIODO
                  </div>
                ) : (
                  previewAgrupado.rayasPorSemana.map((sem) => (
                    <div
                      key={`det-sem-${sem.semana}`}
                      className="border border-zinc-200 rounded overflow-hidden"
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
        )}
      </div>

      {/* Modal para Buscar y Agregar Gastos/Rayas de otra obra o fuera de rango */}
      <BuscarGastosExtraDialog
        open={modalGastosExtraAbierto}
        onClose={() => setModalGastosExtraAbierto(false)}
        onAgregarGastos={handleAgregarGastosExtra}
        onAgregarRayas={handleAgregarRayasExtra}
        obraActualId={obraId}
        gastosYaAgregadosIds={renglones.filter((r) => r.ref_tipo === 'gasto').map((r) => r.ref_id)}
        rayasYaAgregadasIds={renglones.filter((r) => r.ref_tipo === 'raya').map((r) => r.ref_id)}
      />

      {/* Modal de Confirmación de Cierre */}
      <Dialog
        open={modalCerrarAbierto}
        onClose={() => setModalCerrarAbierto(false)}
        title={`Cerrar Memoria #${numero}`}
        description="Esta acción congelará los totales y marcará todos los gastos incluidos como liquidados."
        maxWidth="md"
      >
        <div className="space-y-4 p-6">
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1">
            <p className="font-semibold flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
              <span>Confirmación de Cierre Oficial</span>
            </p>
            <p className="text-[11px] leading-relaxed">
              Una vez cerrada, la memoria no se podrá modificar. Los gastos, nóminas de raya y anticipos incluidos quedarán liquidados y congelados en el snapshot.
            </p>
          </div>

          {/* Tarjeta resumen de la memoria a cerrar */}
          <div className="bg-stone-50 border border-stone-200 rounded-lg p-3 text-xs space-y-2">
            <h4 className="font-bold text-zinc-800 uppercase text-[11px] border-b border-stone-200 pb-1">
              Resumen de la Memoria #{numero}
            </h4>
            <div className="grid grid-cols-2 gap-2 text-[11.5px]">
              <div>
                <span className="text-zinc-500 block">Número de memoria:</span>
                <span className="font-semibold text-zinc-900">Memoria #{numero}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Folio Factura:</span>
                <span className="font-semibold text-zinc-900 font-mono">
                  {folioFactura ? formatFolioFactura(folioFactura) : 'Sin folio'}
                </span>
              </div>
              <div>
                <span className="text-zinc-500 block">Periodo:</span>
                <span className="font-semibold text-zinc-900 font-mono">
                  {formatDate(fechaInicio)} al {formatDate(fechaFin)}
                </span>
              </div>
              <div>
                <span className="text-zinc-500 block">Renglones incluidos:</span>
                <span className="font-semibold text-zinc-900 font-mono">
                  {renglones.filter((r) => r.incluido).length} renglones seleccionados
                </span>
              </div>
            </div>
            <div className="pt-2 border-t border-stone-200 flex justify-between items-center text-sm font-bold text-zinc-900">
              <span>Total de la Memoria:</span>
              <span className="font-mono text-base text-stone-900">
                {formatMoneySimple(totales?.total_memoria)}
              </span>
            </div>
          </div>

          {folioVerif?.usado && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-900 space-y-1">
              <p className="font-semibold flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-red-700 shrink-0" />
                <span>Advertencia de Folio de Factura Duplicado</span>
              </p>
              <p className="text-[11px] leading-relaxed">
                El folio de factura <strong>"{folioFactura}"</strong> ya fue utilizado previamente en la Memoria #{folioVerif.memoria_numero} de {folioVerif.obra_nombre}.
              </p>
            </div>
          )}

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-zinc-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setModalCerrarAbierto(false)}
              disabled={cerrandoMemoria}
              className="text-xs"
            >
              Cancelar
            </Button>
            <Button
              size="sm"
              onClick={handleConfirmarCerrar}
              disabled={cerrandoMemoria}
              className="text-xs bg-emerald-700 hover:bg-emerald-800 text-white flex items-center gap-1.5"
            >
              {cerrandoMemoria ? 'Cerrando memoria...' : 'Confirmar y Cerrar Memoria'}
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Modal alternativo de guardado directo en PDF */}
      <FallbackPdfModal
        open={fallbackModalMemoriaId !== null}
        onClose={() => setFallbackModalMemoriaId(null)}
        memoriaId={fallbackModalMemoriaId}
        errorMessage={fallbackModalError}
      />

      {/* Barra Fija Inferior con Totales (Paso 2) */}
      {paso === 2 && (
        <TotalesStickyFooter
          totales={totales}
          recalculando={recalculando}
          guardando={guardarMutation.isPending}
          onVolver={() => setPaso(1)}
          onGuardarBorrador={() => guardarMutation.mutate()}
          onContinuar={() => {
            guardarMutation.mutate();
            setPaso(3);
          }}
        />
      )}
    </div>
  );
}
export default AsistenteMemoriaPage;
