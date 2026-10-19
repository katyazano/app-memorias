import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Settings,
  Save,
  Download,
  HardDrive,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Cpu,
  RefreshCw,
  FolderOpen,
  RotateCcw,
  Trash2,
  Archive,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { Skeleton } from '@/components/ui/Skeleton'
import { api } from '@/lib/api'
import type { RespaldoItem } from '@/types'
import { FRONTEND_BUILD_VERSION } from '@/version'

export function ConfiguracionPage() {
  const queryClient = useQueryClient()
  const [folio, setFolio] = useState<string>('')
  const [guardadoFolioExitoso, setGuardadoFolioExitoso] = useState(false)
  const [errorFolio, setErrorFolio] = useState('')

  // Carpeta de respaldos
  const [carpetaRespaldos, setCarpetaRespaldos] = useState<string>('')
  const [guardadoCarpetaExitoso, setGuardadoCarpetaExitoso] = useState(false)
  const [errorCarpeta, setErrorCarpeta] = useState('')

  // Modales
  const [respaldoParaRestaurar, setRespaldoParaRestaurar] = useState<RespaldoItem | null>(null)
  const [modalRestaurarOpen, setModalRestaurarOpen] = useState(false)
  const [modalRestablecerOpen, setModalRestablecerOpen] = useState(false)
  const [textoConfirmacionRestablecer, setTextoConfirmacionRestablecer] = useState('')

  // Estados de carga / feedback
  const [mensajeGlobalExito, setMensajeGlobalExito] = useState('')
  const [mensajeGlobalError, setMensajeGlobalError] = useState('')

  // 1. Consulta del estado de salud y versión del backend
  const { data: healthData, refetch: refetchHealth } = useQuery({
    queryKey: ['health'],
    queryFn: () => api.getHealth(),
  })

  const backendVersion = healthData?.version_build?.version_codigo
  const hayDesincronizacion = Boolean(
    healthData && (!healthData.version_build || backendVersion !== FRONTEND_BUILD_VERSION)
  )

  // 2. Consulta del último folio
  const { data: configFolio, isLoading: isLoadingFolio } = useQuery({
    queryKey: ['configuracion', 'ultimo_folio_factura_arquitecto'],
    queryFn: () => api.getConfiguracion('ultimo_folio_factura_arquitecto'),
  })

  React.useEffect(() => {
    if (configFolio) {
      setFolio(configFolio.valor || '0')
    }
  }, [configFolio])

  // 3. Consulta de lista de respaldos e información de carpeta
  const {
    data: infoRespaldos,
    isLoading: isLoadingRespaldos,
    refetch: refetchRespaldos,
  } = useQuery({
    queryKey: ['respaldos'],
    queryFn: () => api.getRespaldos(),
  })

  React.useEffect(() => {
    if (infoRespaldos?.carpeta_configurada !== undefined) {
      setCarpetaRespaldos(infoRespaldos.carpeta_configurada || '')
    }
  }, [infoRespaldos])

  // Mutación para guardar el folio
  const guardarFolioMutation = useMutation({
    mutationFn: (nuevoValor: string) =>
      api.updateConfiguracion('ultimo_folio_factura_arquitecto', nuevoValor),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['configuracion', 'ultimo_folio_factura_arquitecto'] })
      setGuardadoFolioExitoso(true)
      setErrorFolio('')
      setTimeout(() => setGuardadoFolioExitoso(false), 3000)
    },
    onError: (err: any) => {
      setErrorFolio(err.message || 'Error al guardar el folio')
    },
  })

  const handleGuardarFolio = (e: React.FormEvent) => {
    e.preventDefault()
    const valNum = parseInt(folio.trim(), 10)
    if (isNaN(valNum) || valNum < 0) {
      setErrorFolio('El folio debe ser un número entero mayor o igual a 0.')
      return
    }
    guardarFolioMutation.mutate(String(valNum))
  }

  // Mutación para guardar carpeta de respaldos
  const guardarCarpetaMutation = useMutation({
    mutationFn: (nuevaRuta: string) =>
      api.updateConfiguracion('carpeta_respaldos', nuevaRuta),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['respaldos'] })
      setGuardadoCarpetaExitoso(true)
      setErrorCarpeta('')
      setTimeout(() => setGuardadoCarpetaExitoso(false), 3000)
    },
    onError: (err: any) => {
      setErrorCarpeta(err.message || 'Error al validar o guardar la carpeta')
    },
  })

  const handleGuardarCarpeta = (e: React.FormEvent) => {
    e.preventDefault()
    setErrorCarpeta('')
    guardarCarpetaMutation.mutate(carpetaRespaldos.trim())
  }

  // Mutación para generar respaldo manual
  const generarRespaldoMutation = useMutation({
    mutationFn: () => api.generarRespaldoManual(),
    onSuccess: (res) => {
      refetchRespaldos()
      setMensajeGlobalExito(res.mensaje)
      setMensajeGlobalError('')
      setTimeout(() => setMensajeGlobalExito(''), 4000)
    },
    onError: (err: any) => {
      setMensajeGlobalError(err.message || 'Error al generar respaldo')
    },
  })

  // Mutación para restaurar respaldo
  const restaurarMutation = useMutation({
    mutationFn: (nombreArchivo: string) => api.restaurarRespaldo(nombreArchivo),
    onSuccess: (res) => {
      setModalRestaurarOpen(false)
      setRespaldoParaRestaurar(null)
      queryClient.invalidateQueries()
      setMensajeGlobalExito(res.mensaje + ` (Copia preventiva creada: ${res.respaldo_previo})`)
      setMensajeGlobalError('')
      setTimeout(() => setMensajeGlobalExito(''), 6000)
    },
    onError: (err: any) => {
      setMensajeGlobalError(err.message || 'Error al restaurar respaldo')
    },
  })

  // Mutación para restablecer a datos vacíos
  const restablecerMutation = useMutation({
    mutationFn: (conf: string) => api.restablecerDatosVacios(conf),
    onSuccess: (res) => {
      setModalRestablecerOpen(false)
      setTextoConfirmacionRestablecer('')
      queryClient.invalidateQueries()
      setMensajeGlobalExito(res.mensaje + ` (Copia preventiva creada: ${res.respaldo_previo})`)
      setMensajeGlobalError('')
      setTimeout(() => setMensajeGlobalExito(''), 6000)
    },
    onError: (err: any) => {
      setMensajeGlobalError(err.message || 'Error al restablecer los datos')
    },
  })

  const handleDescargarArchivo = (nombreArchivo: string) => {
    const a = document.createElement('a')
    a.href = `/api/configuracion/sistema/respaldos/descargar/${encodeURIComponent(nombreArchivo)}`
    a.download = nombreArchivo
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const getBadgeOrigen = (origen: string) => {
    switch (origen.toLowerCase()) {
      case 'diario':
        return <Badge variant="default">Diario Automático</Badge>
      case 'cierre':
      case 'cierre_memoria':
        return <Badge variant="success">Cierre de Memoria</Badge>
      case 'manual':
        return <Badge variant="outline">Manual</Badge>
      case 'pre_restauracion':
      case 'pre':
        return <Badge variant="warning">Pre-Restauración</Badge>
      case 'pre_restablecer':
        return <Badge variant="warning">Pre-Restablecimiento</Badge>
      default:
        return <Badge variant="muted">{origen}</Badge>
    }
  }

  return (
    <div className="max-w-5xl space-y-6 pb-12">
      {/* Encabezado */}
      <div>
        <h1 className="text-xl font-bold font-serif text-zinc-900 tracking-tight">
          Configuración del Sistema
        </h1>
        <p className="text-xs text-zinc-500 mt-0.5">
          Ajusta los parámetros operativos del despacho, gestiona respaldos automáticos y administra la base de datos local.
        </p>
      </div>

      {/* Banner de Sincronización */}
      {hayDesincronizacion && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 text-amber-900 shadow-xs flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold uppercase tracking-wide">
              Desincronización de Versión Detectada
            </h3>
            <p className="text-xs text-amber-800 leading-relaxed">
              El proceso del backend en ejecución (versión{' '}
              <code className="font-mono font-bold bg-amber-100 px-1 py-0.5 rounded">
                {backendVersion || 'desconocida / desactualizada'}
              </code>
              {healthData?.version_build?.arranque
                ? `, iniciado el ${healthData.version_build.arranque}`
                : ''}
              ) no coincide con la versión del frontend compilado (versión{' '}
              <code className="font-mono font-bold bg-amber-100 px-1 py-0.5 rounded">
                {FRONTEND_BUILD_VERSION}
              </code>
              ).
            </p>
            <p className="text-xs font-semibold text-amber-900 mt-1">
              Para aplicar las últimas correcciones en descargas de Excel/PDF y lógica de negocio, es necesario reiniciar el servidor backend.
            </p>
          </div>
        </div>
      )}

      {/* Alertas de Éxito o Error Globales */}
      {mensajeGlobalExito && (
        <div className="bg-emerald-50 border border-emerald-300 rounded-lg p-3 text-emerald-900 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{mensajeGlobalExito}</span>
        </div>
      )}

      {mensajeGlobalError && (
        <div className="bg-red-50 border border-red-300 rounded-lg p-3 text-red-900 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{mensajeGlobalError}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Tarjeta 1: Folio de Factura del Arquitecto */}
        <div className="bg-white border border-zinc-200 rounded-lg p-5 shadow-2xs space-y-4">
          <div className="flex items-center space-x-2.5 pb-3 border-b border-zinc-100">
            <div className="p-2 bg-zinc-100 rounded text-zinc-700">
              <Settings className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">
                Folio de Factura del Arquitecto
              </h2>
              <p className="text-[11px] text-zinc-500">
                Control correlativo de los honorarios cobrados
              </p>
            </div>
          </div>

          <p className="text-xs text-zinc-600 leading-relaxed">
            Al cerrar una memoria con un número de factura del arquitecto, este valor se incrementará automáticamente.
            También puedes ajustarlo manualmente aquí:
          </p>

          {isLoadingFolio ? (
            <Skeleton className="h-9 w-full" />
          ) : (
            <form onSubmit={handleGuardarFolio} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Último folio utilizado
                </label>
                <div className="relative">
                  <input
                    type="number"
                    min="0"
                    value={folio}
                    onChange={(e) => {
                      setFolio(e.target.value)
                      setGuardadoFolioExitoso(false)
                    }}
                    className="w-full px-3 py-2 border border-zinc-200 rounded-md font-mono text-sm font-bold text-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white"
                  />
                  <span className="absolute right-3 top-2.5 text-[11px] text-zinc-400 font-medium">
                    Siguiente sugerido: {parseInt(folio || '0', 10) + 1}
                  </span>
                </div>
              </div>

              {errorFolio && (
                <p className="text-xs text-red-600 flex items-center">
                  <AlertCircle className="w-3.5 h-3.5 mr-1" />
                  {errorFolio}
                </p>
              )}

              {guardadoFolioExitoso && (
                <p className="text-xs text-emerald-700 flex items-center font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                  Folio actualizado correctamente.
                </p>
              )}

              <Button type="submit" size="sm" disabled={guardarFolioMutation.isPending}>
                <Save className="w-3.5 h-3.5 mr-1.5" />
                {guardarFolioMutation.isPending ? 'Guardando...' : 'Guardar Folio'}
              </Button>
            </form>
          )}
        </div>

        {/* Tarjeta 2: Carpeta de Almacenamiento de Respaldos */}
        <div className="bg-white border border-zinc-200 rounded-lg p-5 shadow-2xs space-y-4">
          <div className="flex items-center space-x-2.5 pb-3 border-b border-zinc-100">
            <div className="p-2 bg-zinc-100 rounded text-zinc-700">
              <FolderOpen className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">
                Ubicación de Respaldos
              </h2>
              <p className="text-[11px] text-zinc-500">
                Directorio en disco externo, OneDrive o unidad local
              </p>
            </div>
          </div>

          <p className="text-xs text-zinc-600 leading-relaxed">
            Puedes elegir una carpeta en un disco externo o servicio en la nube (OneDrive, Google Drive, Dropbox) para que tus copias de seguridad queden fuera de la computadora:
          </p>

          <form onSubmit={handleGuardarCarpeta} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">
                Ruta de la carpeta de respaldos
              </label>
              <input
                type="text"
                placeholder="Por defecto: data/respaldos (deja vacío para restablecer)"
                value={carpetaRespaldos}
                onChange={(e) => {
                  setCarpetaRespaldos(e.target.value)
                  setGuardadoCarpetaExitoso(false)
                }}
                className="w-full px-3 py-2 border border-zinc-200 rounded-md font-mono text-xs text-zinc-900 focus:outline-none focus:ring-1 focus:ring-zinc-900 bg-white"
              />
              <p className="text-[11px] text-zinc-500 mt-1 truncate" title={infoRespaldos?.carpeta_actual}>
                Carpeta activa:{' '}
                <span className="font-mono text-zinc-700">{infoRespaldos?.carpeta_actual || 'data/respaldos'}</span>
              </p>
            </div>

            {errorCarpeta && (
              <p className="text-xs text-red-600 flex items-center">
                <AlertCircle className="w-3.5 h-3.5 mr-1" />
                {errorCarpeta}
              </p>
            )}

            {guardadoCarpetaExitoso && (
              <p className="text-xs text-emerald-700 flex items-center font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                Ubicación de respaldos guardada y verificada.
              </p>
            )}

            <Button type="submit" size="sm" variant="outline" disabled={guardarCarpetaMutation.isPending}>
              <Save className="w-3.5 h-3.5 mr-1.5" />
              {guardarCarpetaMutation.isPending ? 'Validando...' : 'Guardar Ubicación'}
            </Button>
          </form>
        </div>
      </div>

      {/* Tarjeta 3: Respaldos Automáticos y Restauración */}
      <div className="bg-white border border-zinc-200 rounded-lg p-5 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 border-b border-zinc-100 gap-3">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-zinc-100 rounded text-zinc-700">
              <HardDrive className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">
                Copias de Seguridad (Últimos 10 Respaldos)
              </h2>
              <p className="text-[11px] text-zinc-500">
                Copias diarias automáticas, al cerrar cada memoria y manuales
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchRespaldos()}
              className="text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1 text-zinc-500" />
              Actualizar
            </Button>
            <Button
              size="sm"
              onClick={() => generarRespaldoMutation.mutate()}
              disabled={generarRespaldoMutation.isPending}
            >
              <Archive className="w-3.5 h-3.5 mr-1.5" />
              {generarRespaldoMutation.isPending ? 'Generando...' : 'Generar Respaldo Ahora'}
            </Button>
          </div>
        </div>

        <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-md text-xs text-zinc-600 flex items-start gap-2.5">
          <ShieldCheck className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
          <div className="space-y-0.5">
            <p className="font-medium text-zinc-800">
              Rotación automática segura
            </p>
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              El sistema genera automáticamente un respaldo diario al iniciar la aplicación y otro cada vez que cierras una memoria. Siempre se conservan las últimas 10 copias más recientes para optimizar el espacio sin perder historial.
            </p>
          </div>
        </div>

        {/* Tabla de Respaldos */}
        {isLoadingRespaldos ? (
          <Skeleton className="h-32 w-full" />
        ) : !infoRespaldos?.respaldos || infoRespaldos.respaldos.length === 0 ? (
          <div className="text-center py-8 text-zinc-400 text-xs border border-dashed border-zinc-200 rounded-md">
            No se han generado copias de seguridad en esta carpeta aún.
          </div>
        ) : (
          <div className="overflow-x-auto border border-zinc-200 rounded-md">
            <table className="w-full text-xs text-left">
              <thead className="bg-zinc-50 border-b border-zinc-200 text-zinc-600 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="px-3 py-2">Archivo</th>
                  <th className="px-3 py-2">Fecha y Hora</th>
                  <th className="px-3 py-2">Tipo / Origen</th>
                  <th className="px-3 py-2 text-right">Tamaño</th>
                  <th className="px-3 py-2 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 font-mono">
                {infoRespaldos.respaldos.map((r) => (
                  <tr key={r.nombre} className="hover:bg-zinc-50/70 transition-colors">
                    <td className="px-3 py-2 text-zinc-900 font-medium truncate max-w-[220px]" title={r.nombre}>
                      {r.nombre}
                    </td>
                    <td className="px-3 py-2 text-zinc-600 font-sans">
                      {r.fecha_creacion}
                    </td>
                    <td className="px-3 py-2 font-sans">
                      {getBadgeOrigen(r.origen)}
                    </td>
                    <td className="px-3 py-2 text-right text-zinc-600">
                      {r.tamano_formateado}
                    </td>
                    <td className="px-3 py-2 text-right space-x-1.5 font-sans">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDescargarArchivo(r.nombre)}
                        className="h-7 px-2 text-xs text-zinc-700 hover:text-zinc-900"
                        title="Descargar archivo .zip"
                      >
                        <Download className="w-3.5 h-3.5 mr-1" />
                        Descargar
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setRespaldoParaRestaurar(r)
                          setModalRestaurarOpen(true)
                        }}
                        className="h-7 px-2 text-xs text-amber-700 hover:text-amber-900 hover:bg-amber-50 border-amber-200"
                        title="Restaurar base de datos y archivos desde esta copia"
                      >
                        <RotateCcw className="w-3.5 h-3.5 mr-1 text-amber-600" />
                        Restaurar
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Tarjeta 4: Zona de Peligro - Restablecer a datos vacíos */}
      <div className="bg-red-50/40 border border-red-200 rounded-lg p-5 shadow-2xs space-y-4">
        <div className="flex items-center space-x-2.5 pb-3 border-b border-red-100">
          <div className="p-2 bg-red-100 rounded text-red-700">
            <Trash2 className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-red-950">
              Primer Uso: Restablecer a Datos Vacíos
            </h2>
            <p className="text-[11px] text-red-600">
              Limpiar obras y comprobantes de prueba antes de registrar obras reales
            </p>
          </div>
        </div>

        <div className="space-y-2 text-xs text-red-900 leading-relaxed">
          <p>
            Esta acción elimina <strong>todas las obras, facturas, rayas, gastos y archivos</strong> actualmente cargados en el sistema, dejando la base de datos limpia para comenzar a trabajar.
          </p>
          <p className="text-[11px] text-red-700 font-medium">
            Por seguridad, el sistema genera automáticamente un respaldo completo previo antes de proceder con el borrado.
          </p>
        </div>

        <div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setTextoConfirmacionRestablecer('')
              setModalRestablecerOpen(true)
            }}
            className="border-red-300 text-red-700 hover:bg-red-100 hover:text-red-900"
          >
            <Trash2 className="w-3.5 h-3.5 mr-1.5" />
            Restablecer a Datos Vacíos
          </Button>
        </div>
      </div>

      {/* Tarjeta 5: Estado y Versión del Sistema */}
      <div className="bg-white border border-zinc-200 rounded-lg p-5 shadow-2xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-100">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-zinc-100 rounded text-zinc-700">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">
                Estado y Versión del Sistema
              </h2>
              <p className="text-[11px] text-zinc-500">
                Verificación de sincronización entre el motor backend y la interfaz compilada
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetchHealth()}
            className="text-xs text-zinc-600 hover:text-zinc-900"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Actualizar estado
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-md space-y-2">
            <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
              Versiones Activas
            </span>
            <div className="text-xs font-mono font-semibold text-zinc-800">
              Backend: {backendVersion || (healthData ? 'Desactualizado (sin version_build)' : 'Consultando...')} · Frontend: {FRONTEND_BUILD_VERSION}
            </div>
            <div className="text-[11px] text-zinc-600">
              {hayDesincronizacion ? (
                <span className="text-amber-700 font-semibold flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" /> Requiere reinicio del backend
                </span>
              ) : (
                <span className="text-emerald-700 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Backend y Frontend sincronizados
                </span>
              )}
            </div>
          </div>

          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-md space-y-1">
            <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
              Detalles del Motor
            </span>
            <div className="text-[11px] text-zinc-600">
              <strong className="text-zinc-800">Arranque del servidor:</strong>{' '}
              {healthData?.version_build?.arranque || '—'}
            </div>
            <div className="text-[11px] text-zinc-600">
              <strong className="text-zinc-800">Esquema de BD:</strong>{' '}
              {healthData?.version_build?.esquema || '—'}
            </div>
            <div className="text-[11px] text-zinc-600">
              <strong className="text-zinc-800">Motor de datos:</strong>{' '}
              {healthData?.database?.toUpperCase() || 'SQLITE'} local (127.0.0.1)
            </div>
          </div>
        </div>
      </div>

      {/* MODAL DE CONFIRMACIÓN: RESTAURACIÓN */}
      <Dialog
        open={modalRestaurarOpen}
        onClose={() => {
          if (!restaurarMutation.isPending) {
            setModalRestaurarOpen(false)
            setRespaldoParaRestaurar(null)
          }
        }}
        title="Confirmar Restauración de Respaldo"
        description="Esta acción reemplazará la información actual por el contenido del respaldo seleccionado."
      >
        <div className="p-5 space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-900 space-y-1">
            <p className="font-semibold flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              Atención: Los datos actuales serán reemplazados
            </p>
            <p className="text-[11px] text-amber-800 leading-relaxed">
              Vas a restaurar el archivo <strong className="font-mono">{respaldoParaRestaurar?.nombre}</strong> ({respaldoParaRestaurar?.fecha_creacion}).
            </p>
            <p className="text-[11px] text-amber-800 leading-relaxed font-medium">
              Por tu seguridad, antes de iniciar la restauración crearemos un respaldo preventivo automático de toda la base de datos actual.
            </p>
          </div>

          {restaurarMutation.isError && (
            <p className="text-xs text-red-600 flex items-center gap-1">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {(restaurarMutation.error as any)?.message || 'Error al restaurar el respaldo'}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-zinc-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setModalRestaurarOpen(false)
                setRespaldoParaRestaurar(null)
              }}
              disabled={restaurarMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              size="sm"
              onClick={() => {
                if (respaldoParaRestaurar) {
                  restaurarMutation.mutate(respaldoParaRestaurar.nombre)
                }
              }}
              disabled={restaurarMutation.isPending}
            >
              <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
              {restaurarMutation.isPending ? 'Restaurando...' : 'Confirmar y Restaurar'}
            </Button>
          </div>
        </div>
      </Dialog>

      {/* MODAL DE CONFIRMACIÓN: RESTABLECER A DATOS VACÍOS */}
      <Dialog
        open={modalRestablecerOpen}
        onClose={() => {
          if (!restablecerMutation.isPending) {
            setModalRestablecerOpen(false)
            setTextoConfirmacionRestablecer('')
          }
        }}
        title="Restablecer a Datos Vacíos"
        description="Doble confirmación obligatoria para vaciar el sistema."
      >
        <div className="p-5 space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-md p-3 text-xs text-red-900 space-y-1.5">
            <p className="font-semibold flex items-center gap-1.5 text-red-950">
              <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
              ¿Estás seguro de que deseas vaciar todos los datos?
            </p>
            <p className="text-[11px] text-red-800 leading-relaxed">
              Se eliminarán todas las obras registradas, facturas XML, comprobantes PDF, rayas y memorias de gastos. El folio de facturación del arquitecto se reiniciará en 0.
            </p>
            <p className="text-[11px] text-red-900 font-semibold leading-relaxed">
              El sistema generará automáticamente un respaldo de seguridad completo antes de borrar.
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-zinc-700">
              Para continuar, escribe exactamente <span className="font-mono font-bold text-red-600">BORRAR TODO</span>:
            </label>
            <input
              type="text"
              value={textoConfirmacionRestablecer}
              onChange={(e) => setTextoConfirmacionRestablecer(e.target.value)}
              placeholder="BORRAR TODO"
              className="w-full px-3 py-2 border border-zinc-300 rounded-md font-mono text-xs text-zinc-900 focus:outline-none focus:ring-1 focus:ring-red-600 uppercase"
              autoFocus
            />
          </div>

          {restablecerMutation.isError && (
            <p className="text-xs text-red-600 flex items-center gap-1">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {(restablecerMutation.error as any)?.message || 'Error al restablecer los datos'}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-zinc-100">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setModalRestablecerOpen(false)
                setTextoConfirmacionRestablecer('')
              }}
              disabled={restablecerMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              size="sm"
              onClick={() => {
                restablecerMutation.mutate(textoConfirmacionRestablecer)
              }}
              disabled={
                textoConfirmacionRestablecer.trim() !== 'BORRAR TODO' ||
                restablecerMutation.isPending
              }
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              <Trash2 className="w-3.5 h-3.5 mr-1.5" />
              {restablecerMutation.isPending ? 'Restableciendo...' : 'Restablecer Todo a Datos Vacíos'}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
