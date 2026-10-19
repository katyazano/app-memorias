export type EstadoObra = 'en_curso' | 'pausada' | 'concluida'
export type MetodoPago = 'transferencia' | 'efectivo'
export type OrigenGasto = 'xml' | 'manual' | 'nota'
export type TipoRaya = 'destajo' | 'dia'
export type EstadoMemoria = 'borrador' | 'cerrada'
export type TipoProveedor = 'con_factura' | 'sin_factura'

export interface Obra {
  id: number
  nombre: string
  ubicacion: string
  propietario: string
  porcentaje_honorarios: string
  saldo_inicial_transferencias: string
  saldo_inicial_efectivo: string
  saldo_inicial_rayas: string
  saldo_inicial_memorias_anteriores: string
  saldo_inicial_acumulado: string
  saldo_inicial_gastado: string
  numero_ultima_memoria_previa: number
  estado: EstadoObra
}

export interface ObraResumenCard {
  id: number
  nombre: string
  ubicacion: string
  propietario: string
  porcentaje_honorarios: string
  saldo_inicial_transferencias: string
  saldo_inicial_efectivo: string
  saldo_inicial_rayas: string
  saldo_inicial_memorias_anteriores: string
  saldo_inicial_acumulado: string
  saldo_inicial_gastado: string
  numero_ultima_memoria_previa: number
  estado: EstadoObra
  gastado_a_la_fecha: string
  total_gastado_registrado: string
  total_gastos_puros: string
  total_rayas: string
  numero_ultima_memoria?: number | null
  total_memorias: number
  total_gastos: number
}

export interface ObraCreate {
  nombre: string
  ubicacion?: string
  propietario?: string
  porcentaje_honorarios?: string
  saldo_inicial_transferencias?: string
  saldo_inicial_efectivo?: string
  saldo_inicial_rayas?: string
  saldo_inicial_memorias_anteriores?: string
  saldo_inicial_acumulado?: string
  saldo_inicial_gastado?: string
  numero_ultima_memoria_previa?: number
  estado?: EstadoObra
}

export interface ObraUpdate {
  nombre?: string
  ubicacion?: string
  propietario?: string
  porcentaje_honorarios?: string
  saldo_inicial_transferencias?: string
  saldo_inicial_efectivo?: string
  saldo_inicial_rayas?: string
  saldo_inicial_memorias_anteriores?: string
  saldo_inicial_acumulado?: string
  saldo_inicial_gastado?: string
  numero_ultima_memoria_previa?: number
  estado?: EstadoObra
}

export interface Proveedor {
  id: number
  tipo: TipoProveedor
  rfc?: string | null
  razon_social: string
  alias?: string | null
  nombre_memoria: string
}

export interface Trabajador {
  id: number
  nombre: string
  oficio: string
}

export interface Anticipo {
  id: number
  obra_id: number
  importe: string
  comprobante: string
  fecha: string
}

export interface PagoRaya {
  id: number
  obra_id: number
  trabajador_id: number
  trabajador_nombre: string
  oficio: string
  semana_numero: number
  fecha_inicio: string
  fecha_fin: string
  tipo: TipoRaya
  cantidad: string
  tarifa: string
  importe: string
}

export interface FilaSemanaRayaCreate {
  trabajador_id: number
  tipo: TipoRaya
  cantidad: string
  tarifa: string
  importe?: string
}

export interface PagosSemanaCreate {
  semana_numero: number
  fecha_inicio: string
  fecha_fin: string
  filas: FilaSemanaRayaCreate[]
}

export interface TrabajadorPagosOut {
  trabajador: Trabajador
  total_acumulado: string
  pagos: PagoRaya[]
}

export interface FacturaOut {
  id: number
  uuid: string
  serie?: string | null
  folio?: string | null
  subtotal: string
  total: string
  rfc_emisor: string
  forma_pago_sat?: string | null
  metodo_pago_sat?: string | null
  ruta_xml: string
  ruta_pdf?: string | null
}

export type TipoComprobante = 'NOTA' | 'TICKET' | 'FACTURA' | 'RECIBO'

export interface Gasto {
  id: number
  obra_id: number
  obra_nombre: string
  fecha: string
  proveedor_id?: number | null
  proveedor_nombre?: string | null
  concepto_resumido: string
  comprobante: string
  tipo_comprobante?: TipoComprobante | string
  importe: string
  metodo_pago: MetodoPago
  origen: OrigenGasto
  factura?: FacturaOut | null
}

export interface GastoManualCreate {
  fecha: string
  proveedor_id?: number | null
  concepto_resumido: string
  comprobante?: string
  tipo_comprobante?: TipoComprobante
  importe: string
  metodo_pago: MetodoPago
  origen?: 'manual' | 'nota'
}

export interface RenglonMemoria {
  ref_tipo: 'gasto' | 'raya' | 'anticipo'
  ref_id: number
  categoria: 'transferencia' | 'efectivo' | 'raya' | 'anticipo'
  incluido: boolean
  fecha: string
  proveedor: string
  concepto: string
  comprobante: string
  tipo_comprobante?: string | null
  importe: string
  es_externo: boolean
  obra_origen?: string | null
  ya_incluido_en?: string | null
  en_otro_borrador?: string | null
  fecha_inicio?: string | null
  fecha_fin?: string | null
  oficio?: string | null
  semana_numero?: number | null
  tipo_raya?: TipoRaya | null
  cantidad?: string | null
  tarifa?: string | null
}

export interface ItemSeleccion {
  ref_tipo: 'gasto' | 'raya' | 'anticipo'
  ref_id: number
  incluido: boolean
}

export interface PreviewOut {
  obra_id: number
  numero_sugerido: number
  folio_sugerido?: string | null
  fecha_inicio: string
  fecha_fin: string
  fecha_emision?: string | null
  ciudad?: string | null
  porcentaje_honorarios: string
  renglones: RenglonMemoria[]
  anticipos: RenglonMemoria[]
  rayas_posteriores?: RenglonMemoria[]
  totales: Record<string, string>
  total_texto: string
  importe_factura_texto?: string | null
  gastado_a_la_fecha_texto?: string | null
}

export interface MemoriaResumen {
  id: number
  obra_id: number
  numero: number
  folio_factura_arquitecto?: string | null
  fecha_inicio: string
  fecha_fin: string
  fecha_emision?: string | null
  ciudad?: string | null
  porcentaje_honorarios_usado: string
  estado: EstadoMemoria
  total_texto: string
  total_memoria?: string | null
  importe_factura_texto?: string | null
  gastado_a_la_fecha_texto?: string | null
  cerrada_at?: string | null
}

export interface Memoria extends MemoriaResumen {
  renglones: RenglonMemoria[]
  anticipos: RenglonMemoria[]
  totales: Record<string, string>
}

export interface Configuracion {
  clave: string
  valor: string
}

export interface DuplicadoInfo {
  gasto_id: number
  obra_id: number
  obra_nombre: string
  fecha: string
}

export interface ErrorArchivo {
  archivo: string
  codigo: string
  detalle: string
  duplicado_de?: DuplicadoInfo | null
}

export interface ProveedorSugerido {
  rfc: string
  razon_social: string
  existente_id?: number | null
  alias?: string | null
}

export interface SugeridoGasto {
  fecha: string
  concepto_resumido: string
  comprobante: string
  metodo_pago?: MetodoPago | null
  proveedor_alias?: string | null
  requiere_decision_metodo_pago: boolean
}

export interface FacturaLeida {
  staging_id: string
  archivo_xml: string
  archivo_pdf?: string | null
  datos: {
    uuid: string
    serie?: string | null
    folio?: string | null
    fecha: string
    subtotal: string
    total: string
    rfc_emisor: string
    nombre_emisor: string
    metodo_pago_sat?: string | null
    forma_pago_sat?: string | null
    conceptos?: any[]
  }
  proveedor: ProveedorSugerido
  sugerido: SugeridoGasto
  requiere_decision_metodo_pago: boolean
}

export interface UploadFacturasOut {
  items: FacturaLeida[]
  errores: ErrorArchivo[]
}

export interface FacturaConfirmarItem {
  staging_id: string
  metodo_pago: MetodoPago
  fecha?: string
  concepto_resumido?: string
  comprobante?: string
  proveedor_alias?: string
  proveedor_razon_social?: string
}

export interface RespaldoItem {
  nombre: string
  ruta: string
  tamano_bytes: number
  tamano_formateado: string
  fecha_creacion: string
  fecha_creacion_iso: string
  origen: string
}

export interface RespaldosInfoOut {
  carpeta_actual: string
  carpeta_configurada?: string | null
  respaldos: RespaldoItem[]
}

