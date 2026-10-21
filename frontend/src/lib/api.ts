import type {
  Anticipo,
  Configuracion,
  Gasto,
  GastoManualCreate,
  Memoria,
  MemoriaResumen,
  Obra,
  ObraCreate,
  ObraResumenCard,
  ObraUpdate,
  PagoRaya,
  PreviewOut,
  Proveedor,
  Trabajador,
  TrabajadorPagosOut,
  UploadFacturasOut,
  FacturaConfirmarItem,
  RespaldoItem,
  RespaldosInfoOut,
} from '@/types'

const BASE_URL = '/api'

const NOMBRES_CAMPOS: Record<string, string> = {
  nombre: 'Nombre',
  rfc: 'RFC',
  razon_social: 'Razón social',
  alias: 'Alias comercial',
  porcentaje_honorarios: 'Porcentaje de honorarios',
  saldo_inicial_transferencias: 'Saldo inicial de transferencias',
  saldo_inicial_efectivo: 'Saldo inicial de efectivo',
  saldo_inicial_rayas: 'Saldo inicial de rayas',
  saldo_inicial_memorias_anteriores: 'Importe de memorias anteriores',
  numero_ultima_memoria_previa: 'Número de última memoria previa',
  estado: 'Estado',
  tipo: 'Tipo',
  trabajador_id: 'Trabajador',
  semana_numero: 'Número de semana',
  fecha_inicio: 'Fecha de inicio',
  fecha_fin: 'Fecha de fin',
  cantidad: 'Cantidad',
  tarifa: 'Tarifa',
  importe: 'Importe',
  fecha: 'Fecha',
  comprobante: 'Comprobante / Folio',
  concepto: 'Concepto',
  concepto_resumido: 'Concepto resumido',
  metodo_pago: 'Método de pago',
  origen: 'Origen del gasto',
  filas: 'Renglones de la semana',
  valor: 'Valor',
}

function traducirErrorValidacion(item: any): string {
  if (typeof item === 'string') return item
  const campoRaw = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : ''
  const nombreCampo = NOMBRES_CAMPOS[campoRaw] || campoRaw || 'Campo'
  let msg = item.msg || 'Dato no válido'

  // Limpiar prefijo Pydantic habitual: "Value error, ..."
  if (msg.startsWith('Value error,')) {
    msg = msg.replace('Value error,', '').trim()
  } else if (msg.includes('Field required') || msg.includes('missing')) {
    msg = 'es obligatorio'
  } else if (msg.includes('greater than or equal to')) {
    msg = 'debe ser mayor o igual al valor permitido'
  } else if (msg.includes('greater than 0')) {
    msg = 'debe ser mayor a 0'
  } else if (msg.includes('less than or equal to')) {
    msg = 'supera el límite permitido'
  } else if (msg.includes('Input should be a valid integer')) {
    msg = 'debe ser un número entero'
  } else if (msg.includes('Input should be a valid number')) {
    msg = 'debe ser un número válido'
  }

  return `${nombreCampo}: ${msg}`
}

async function request<T>(endpoint: string, options: RequestInit = {}, accionDescriptiva?: string): Promise<T> {
  const url = `${BASE_URL}${endpoint}`
  const headers = new Headers(options.headers || {})

  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(url, { ...options, headers })
  } catch (netErr: any) {
    const prefijo = accionDescriptiva ? `No se pudo ${accionDescriptiva}. ` : ''
    throw new Error(`${prefijo}Error de conexión con el servidor (http://127.0.0.1:8000). Comprueba que el backend esté ejecutándose.`)
  }

  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`
    let technicalDetails = ''

    try {
      const errJson = await response.json()
      if (errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail
        } else if (Array.isArray(errJson.detail)) {
          // Errores 422 de validación de FastAPI/Pydantic
          const mensajes = errJson.detail.map(traducirErrorValidacion)
          errorDetail = mensajes.join(' · ')
        } else if (typeof errJson.detail === 'object') {
          errorDetail = errJson.detail.mensaje || errJson.detail.detail || JSON.stringify(errJson.detail)
          technicalDetails = errJson.detail.detalles_tecnicos || errJson.detail.detalles || ''
        }
      }
      if (errJson.detalles_tecnicos) {
        technicalDetails = errJson.detalles_tecnicos
      }
    } catch {
      // Usar statusText
    }

    if (response.status === 500) {
      if (
        errorDetail.includes('500') ||
        errorDetail.includes('Internal Server Error') ||
        errorDetail.includes('Error interno')
      ) {
        errorDetail = 'No se pudo guardar la factura. Los detalles técnicos se guardaron en el registro.'
      }
    }

    const prefijo = accionDescriptiva && response.status !== 500 ? `No se pudo ${accionDescriptiva}: ` : ''
    const err = new Error(`${prefijo}${errorDetail}`) as any
    err.status = response.status
    err.detallesTecnicos = technicalDetails
    throw err
  }

  if (response.status === 204) {
    return null as T
  }

  return response.json()
}

export const api = {
  // Obras
  getObras: () => request<Obra[]>('/obras', {}, 'cargar la lista de obras'),
  getObrasResumen: () => request<ObraResumenCard[]>('/obras/resumen', {}, 'cargar el resumen de obras'),
  getObra: (id: number) => request<Obra>(`/obras/${id}`, {}, 'obtener los datos de la obra'),
  getObraResumen: (id: number) => request<ObraResumenCard>(`/obras/${id}/resumen`, {}, 'obtener el resumen de la obra'),
  createObra: (data: ObraCreate) =>
    request<Obra>('/obras', { method: 'POST', body: JSON.stringify(data) }, 'crear la obra'),
  updateObra: (id: number, data: ObraUpdate) =>
    request<Obra>(`/obras/${id}`, { method: 'PATCH', body: JSON.stringify(data) }, 'actualizar la obra'),
  deleteObra: (id: number, forzar: boolean = false) =>
    request<void>(`/obras/${id}?forzar=${forzar}`, { method: 'DELETE' }, 'eliminar la obra'),
  getMemoriasDeObra: (obraId: number) =>
    request<MemoriaResumen[]>(`/obras/${obraId}/memorias`, {}, 'cargar las memorias de la obra'),

  // Gastos
  getGastosDeObra: (obraId: number) =>
    request<Gasto[]>(`/obras/${obraId}/gastos`, {}, 'cargar los gastos de la obra'),
  createGastoManual: (obraId: number, data: GastoManualCreate) =>
    request<Gasto>(`/obras/${obraId}/gastos`, { method: 'POST', body: JSON.stringify(data) }, 'registrar el gasto manual'),
  updateGasto: (id: number, data: Partial<Gasto>) =>
    request<Gasto>(`/gastos/${id}`, { method: 'PATCH', body: JSON.stringify(data) }, 'actualizar el gasto'),
  deleteGasto: (id: number) =>
    request<void>(`/gastos/${id}`, { method: 'DELETE' }, 'eliminar el gasto'),
  buscarGastos: (params: { q?: string; excluir_obra?: number; desde?: string; hasta?: string }) => {
    const qry = new URLSearchParams()
    if (params.q) qry.append('q', params.q)
    if (params.excluir_obra) qry.append('excluir_obra', params.excluir_obra.toString())
    if (params.desde) qry.append('desde', params.desde)
    if (params.hasta) qry.append('hasta', params.hasta)
    return request<Gasto[]>(`/gastos/buscar?${qry.toString()}`, {}, 'buscar gastos')
  },

  // Facturas
  subirFacturas: (obraId: number, files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    return request<UploadFacturasOut>(`/obras/${obraId}/facturas`, { method: 'POST', body: fd }, 'cargar las facturas')
  },
  confirmarFacturas: (obraId: number, items: FacturaConfirmarItem[]) =>
    request<Gasto[]>(
      `/obras/${obraId}/facturas/confirmar`,
      { method: 'POST', body: JSON.stringify({ items }) },
      'confirmar y guardar las facturas'
    ),

  // Rayas
  getRayasDeObra: (obraId: number) =>
    request<PagoRaya[]>(`/obras/${obraId}/rayas`, {}, 'cargar las rayas de la obra'),
  createRaya: (obraId: number, data: any) =>
    request<PagoRaya>(`/obras/${obraId}/rayas`, { method: 'POST', body: JSON.stringify(data) }, 'registrar el pago de raya'),
  createRayasSemana: (obraId: number, data: any) =>
    request<PagoRaya[]>(
      `/obras/${obraId}/rayas/semana`,
      { method: 'POST', body: JSON.stringify(data) },
      'guardar la nómina semanal de rayas'
    ),
  updateRaya: (id: number, data: any) =>
    request<PagoRaya>(`/rayas/${id}`, { method: 'PATCH', body: JSON.stringify(data) }, 'actualizar el pago de raya'),
  deleteRaya: (id: number) =>
    request<void>(`/rayas/${id}`, { method: 'DELETE' }, 'eliminar el pago de raya'),
  buscarRayas: (params: { q?: string; excluir_obra?: number; desde?: string; hasta?: string }) => {
    const qry = new URLSearchParams()
    if (params.q) qry.append('q', params.q)
    if (params.excluir_obra) qry.append('excluir_obra', params.excluir_obra.toString())
    if (params.desde) qry.append('desde', params.desde)
    if (params.hasta) qry.append('hasta', params.hasta)
    return request<PagoRaya[]>(`/rayas/buscar?${qry.toString()}`, {}, 'buscar pagos de raya')
  },

  // Anticipos
  getAnticiposDeObra: (obraId: number) =>
    request<Anticipo[]>(`/obras/${obraId}/anticipos`, {}, 'cargar los anticipos'),
  createAnticipo: (obraId: number, data: { importe: string; comprobante: string; fecha: string }) =>
    request<Anticipo>(
      `/obras/${obraId}/anticipos`,
      { method: 'POST', body: JSON.stringify(data) },
      'registrar el anticipo'
    ),
  updateAnticipo: (id: number, data: Partial<Anticipo>) =>
    request<Anticipo>(`/anticipos/${id}`, { method: 'PATCH', body: JSON.stringify(data) }, 'actualizar el anticipo'),
  deleteAnticipo: (id: number) =>
    request<void>(`/anticipos/${id}`, { method: 'DELETE' }, 'eliminar el anticipo'),

  // Trabajadores
  getTrabajadores: () => request<Trabajador[]>('/trabajadores', {}, 'cargar el catálogo de trabajadores'),
  createTrabajador: (data: { nombre: string; oficio: string }) =>
    request<Trabajador>('/trabajadores', { method: 'POST', body: JSON.stringify(data) }, 'registrar el trabajador'),
  getPagosTrabajador: (id: number) =>
    request<TrabajadorPagosOut>(`/trabajadores/${id}/pagos`, {}, 'obtener el historial del trabajador'),

  // Proveedores
  getProveedores: (q?: string) =>
    request<Proveedor[]>(`/proveedores${q ? `?q=${encodeURIComponent(q)}` : ''}`, {}, 'cargar los proveedores'),
  createProveedor: (data: Partial<Proveedor> & { razon_social: string }) =>
    request<Proveedor>('/proveedores', { method: 'POST', body: JSON.stringify(data) }, 'registrar el proveedor'),
  updateProveedor: (id: number, data: Partial<Proveedor>) =>
    request<Proveedor>(`/proveedores/${id}`, { method: 'PATCH', body: JSON.stringify(data) }, 'actualizar el proveedor'),

  // Memorias
  verificarFolio: (folio: string, excluirMemoriaId?: number) => {
    const qry = new URLSearchParams({ folio });
    if (excluirMemoriaId) qry.append('excluir_memoria_id', excluirMemoriaId.toString());
    return request<{
      usado: boolean;
      memoria_id?: number;
      memoria_numero?: number;
      obra_nombre?: string;
      estado?: string;
    }>(`/memorias/verificar-folio?${qry.toString()}`, {}, 'verificar el folio de factura');
  },
  previewMemoria: (
    obraId: number,
    data: {
      fecha_inicio: string;
      fecha_fin: string;
      gastos_extra_ids?: number[];
      rayas_extra_ids?: number[];
      numero?: number;
      porcentaje_honorarios?: string;
      seleccion?: { ref_tipo: 'gasto' | 'raya' | 'anticipo'; ref_id: number; incluido: boolean }[];
    }
  ) =>
    request<PreviewOut>(
      `/obras/${obraId}/memorias/preview`,
      { method: 'POST', body: JSON.stringify(data) },
      'generar la vista previa de la memoria'
    ),
  guardarMemoria: (data: any) =>
    request<Memoria>('/memorias', { method: 'POST', body: JSON.stringify(data) }, 'guardar la memoria'),
  actualizarMemoria: (id: number, data: any) =>
    request<Memoria>(`/memorias/${id}`, { method: 'PUT', body: JSON.stringify(data) }, 'actualizar la memoria'),
  getMemoria: (id: number) =>
    request<Memoria>(`/memorias/${id}`, {}, 'cargar el detalle de la memoria'),
  cerrarMemoria: (id: number) =>
    request<Memoria>(`/memorias/${id}/cerrar`, { method: 'POST' }, 'cerrar la memoria'),
  reabrirMemoria: (id: number) =>
    request<Memoria>(`/memorias/${id}/reabrir`, { method: 'POST' }, 'reabrir la memoria'),
  descargarPdf: async (memoriaId: number) => {
    const res = await fetch(`${BASE_URL}/memorias/${memoriaId}/pdf`);
    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      let mensaje = 'Error al generar el PDF en el servidor.';
      let codigo = 'error_desconocido';
      let rutasProbadas: string[] | undefined = undefined;
      let navegador: string | undefined = undefined;

      if (errData?.detail) {
        if (typeof errData.detail === 'string') {
          mensaje = errData.detail;
        } else if (typeof errData.detail === 'object') {
          mensaje = errData.detail.mensaje || errData.detail.detail || mensaje;
          codigo = errData.detail.codigo || codigo;
          rutasProbadas = errData.detail.rutas_probadas;
          navegador = errData.detail.navegador;
        }
      }

      const err: any = new Error(mensaje);
      err.codigo = codigo;
      err.rutasProbadas = rutasProbadas;
      err.navegador = navegador;
      err.memoriaId = memoriaId;
      throw err;
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition');
    let filename = `MEMORIA-${memoriaId}.pdf`;
    if (disposition) {
      const matchUtf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const matchPlain = disposition.match(/filename="?([^";]+)"?/);
      if (matchUtf8 && matchUtf8[1]) {
        try {
          filename = decodeURIComponent(matchUtf8[1]);
        } catch {
          filename = matchUtf8[1];
        }
      } else if (matchPlain && matchPlain[1]) {
        filename = matchPlain[1];
      }
    }
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },
  descargarExcel: async (memoriaId: number) => {
    const res = await fetch(`${BASE_URL}/memorias/${memoriaId}/xlsx`);
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || 'Error al generar el Excel en el servidor.');
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition');
    let filename = `MEMORIA-${memoriaId}.xlsx`;
    if (disposition) {
      const matchUtf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
      const matchPlain = disposition.match(/filename="?([^";]+)"?/);
      if (matchUtf8 && matchUtf8[1]) {
        try {
          filename = decodeURIComponent(matchUtf8[1]);
        } catch {
          filename = matchUtf8[1];
        }
      } else if (matchPlain && matchPlain[1]) {
        filename = matchPlain[1];
      }
    }
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },

  // Configuración
  getConfiguracion: (clave: string) =>
    request<Configuracion>(`/configuracion/${clave}`, {}, 'consultar la configuración'),
  updateConfiguracion: (clave: string, valor: string) =>
    request<Configuracion>(
      `/configuracion/${clave}`,
      { method: 'PUT', body: JSON.stringify({ valor }) },
      'actualizar la configuración'
    ),

  // Respaldos y Mantenimiento del Sistema
  getRespaldos: () =>
    request<RespaldosInfoOut>('/configuracion/sistema/respaldos', {}, 'cargar la lista de respaldos'),
  generarRespaldoManual: () =>
    request<{ status: string; mensaje: string; nombre: string; ruta: string }>(
      '/configuracion/sistema/respaldos/generar',
      { method: 'POST' },
      'generar respaldo manual'
    ),
  restaurarRespaldo: (nombre_archivo: string) =>
    request<{ status: string; mensaje: string; respaldo_previo: string }>(
      '/configuracion/sistema/respaldos/restaurar',
      { method: 'POST', body: JSON.stringify({ nombre_archivo }) },
      'restaurar el respaldo'
    ),
  restablecerDatosVacios: (confirmacion: string) =>
    request<{ status: string; mensaje: string; respaldo_previo: string }>(
      '/configuracion/sistema/restablecer-datos-vacios',
      { method: 'POST', body: JSON.stringify({ confirmacion }) },
      'restablecer datos del sistema'
    ),

  // Ciclo de vida: Heartbeat y Apagado
  enviarHeartbeat: async () => {
    try {
      await fetch('/api/sistema/heartbeat', { method: 'POST' })
    } catch {
      // Ignorar fallos de red puntuales en heartbeat
    }
  },
  apagarSistema: async () => {
    const res = await fetch('/api/sistema/apagar', { method: 'POST' })
    if (!res.ok) {
      throw new Error(`Error ${res.status} al apagar el sistema`)
    }
    return res.json() as Promise<{ status: string; mensaje: string }>
  },

  // Estado del sistema y versiones
  abrirCarpetaLogs: () =>
    request<{ status: string; ruta: string }>('/sistema/abrir-logs', { method: 'POST' }),

  getHealth: async () => {
    const res = await fetch('/health');
    if (!res.ok) {
      throw new Error(`Error ${res.status} al consultar salud del backend`);
    }
    return res.json() as Promise<{
      status: string;
      app: string;
      database: string;
      version_build?: {
        arranque: string;
        arranque_iso: string;
        esquema: string;
        version_codigo: string;
      };
    }>;
  },
}
