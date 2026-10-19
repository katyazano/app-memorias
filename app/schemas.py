"""Esquemas Pydantic (entrada/salida de la API). El dinero siempre es Decimal;
en JSON se serializa como texto ("116634.40"), nunca como float."""
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import EstadoMemoria, EstadoObra, MetodoPago, OrigenGasto, TipoProveedor, TipoRaya
from app.types import money

Dinero = Annotated[Decimal, AfterValidator(money), Field(ge=0)]
Porcentaje = Annotated[Decimal, AfterValidator(money), Field(ge=0, le=100)]
Cantidad = Annotated[Decimal, AfterValidator(lambda v: v.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)), Field(gt=0)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- Obras ----------------
class ObraCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    ubicacion: str = Field("", max_length=255)
    propietario: str = Field("", max_length=255)
    porcentaje_honorarios: Porcentaje = Decimal("10")
    saldo_inicial_transferencias: Dinero = Decimal("0")
    saldo_inicial_efectivo: Dinero = Decimal("0")
    saldo_inicial_rayas: Dinero = Decimal("0")
    saldo_inicial_memorias_anteriores: Dinero = Decimal("0")
    # Compatibilidad hacia atrás
    saldo_inicial_acumulado: Optional[Dinero] = None
    saldo_inicial_gastado: Optional[Dinero] = None
    numero_ultima_memoria_previa: int = Field(0, ge=0)
    estado: EstadoObra = EstadoObra.EN_CURSO

    @model_validator(mode="after")
    def _backwards_compat(self) -> "ObraCreate":
        # Si se envió legacy acumulado pero no transferencias
        if self.saldo_inicial_acumulado is not None and self.saldo_inicial_transferencias == Decimal("0"):
            self.saldo_inicial_transferencias = self.saldo_inicial_acumulado
        # Si se envió legacy gastado pero no memorias anteriores
        if self.saldo_inicial_gastado is not None and self.saldo_inicial_memorias_anteriores == Decimal("0"):
            self.saldo_inicial_memorias_anteriores = self.saldo_inicial_gastado
        return self


class ObraUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    ubicacion: Optional[str] = Field(None, max_length=255)
    propietario: Optional[str] = Field(None, max_length=255)
    porcentaje_honorarios: Optional[Porcentaje] = None
    saldo_inicial_transferencias: Optional[Dinero] = None
    saldo_inicial_efectivo: Optional[Dinero] = None
    saldo_inicial_rayas: Optional[Dinero] = None
    saldo_inicial_memorias_anteriores: Optional[Dinero] = None
    saldo_inicial_acumulado: Optional[Dinero] = None
    saldo_inicial_gastado: Optional[Dinero] = None
    numero_ultima_memoria_previa: Optional[int] = Field(None, ge=0)
    estado: Optional[EstadoObra] = None


class ObraOut(ORM):
    id: int
    nombre: str
    ubicacion: str
    propietario: str
    porcentaje_honorarios: Decimal
    saldo_inicial_transferencias: Decimal = Decimal("0.00")
    saldo_inicial_efectivo: Decimal = Decimal("0.00")
    saldo_inicial_rayas: Decimal = Decimal("0.00")
    saldo_inicial_memorias_anteriores: Decimal = Decimal("0.00")
    saldo_inicial_acumulado: Decimal = Decimal("0.00")
    saldo_inicial_gastado: Decimal = Decimal("0.00")
    numero_ultima_memoria_previa: int = 0
    estado: EstadoObra


class ObraResumenCardOut(BaseModel):
    id: int
    nombre: str
    ubicacion: str
    propietario: str
    porcentaje_honorarios: Decimal
    saldo_inicial_transferencias: Decimal = Decimal("0.00")
    saldo_inicial_efectivo: Decimal = Decimal("0.00")
    saldo_inicial_rayas: Decimal = Decimal("0.00")
    saldo_inicial_memorias_anteriores: Decimal = Decimal("0.00")
    saldo_inicial_acumulado: Decimal = Decimal("0.00")
    saldo_inicial_gastado: Decimal = Decimal("0.00")
    numero_ultima_memoria_previa: int = 0
    estado: EstadoObra
    gastado_a_la_fecha: Decimal  # Gastado en memorias cerradas (+ saldo inicial memorias anteriores)
    total_gastado_registrado: Decimal = Decimal("0.00")  # Suma de gastos + rayas
    total_gastos_puros: Decimal = Decimal("0.00")  # Suma de facturas + notas + manuales
    total_rayas: Decimal = Decimal("0.00")  # Suma de pagos de raya
    numero_ultima_memoria: Optional[int] = None
    total_memorias: int
    total_gastos: int


# ---------------- Proveedores ----------------
def _rfc(v: str) -> str:
    v = (v or "").strip().upper()
    if not (10 <= len(v) <= 13) or not v.isalnum():
        raise ValueError("RFC inválido (10 a 13 caracteres alfanuméricos).")
    return v


class ProveedorCreate(BaseModel):
    tipo: TipoProveedor = TipoProveedor.CON_FACTURA
    rfc: Optional[str] = None
    razon_social: str = Field(min_length=1, max_length=255)
    alias: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def _validate_rfc_by_tipo(self) -> "ProveedorCreate":
        if self.tipo == TipoProveedor.CON_FACTURA:
            if not self.rfc or not self.rfc.strip():
                raise ValueError("El RFC es obligatorio para proveedores con factura.")
            self.rfc = _rfc(self.rfc)
        else:
            if self.rfc and self.rfc.strip():
                self.rfc = _rfc(self.rfc)
            else:
                self.rfc = None
        return self


class ProveedorUpdate(BaseModel):
    tipo: Optional[TipoProveedor] = None
    rfc: Optional[str] = None
    razon_social: Optional[str] = Field(None, min_length=1, max_length=255)
    alias: Optional[str] = Field(None, max_length=255)

    @field_validator("rfc")
    @classmethod
    def _v_rfc(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return _rfc(v) if v else None


class ProveedorOut(ORM):
    id: int
    tipo: TipoProveedor
    rfc: Optional[str]
    razon_social: str
    alias: Optional[str]
    nombre_memoria: str


# ---------------- Trabajadores ----------------
class TrabajadorCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    oficio: str = Field("", max_length=100)


class TrabajadorUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1, max_length=255)
    oficio: Optional[str] = Field(None, max_length=100)


class TrabajadorOut(ORM):
    id: int
    nombre: str
    oficio: str


# ---------------- Anticipos ----------------
class AnticipoCreate(BaseModel):
    importe: Dinero
    comprobante: str = Field("", max_length=100)
    fecha: date


class AnticipoUpdate(BaseModel):
    importe: Optional[Dinero] = None
    comprobante: Optional[str] = Field(None, max_length=100)
    fecha: Optional[date] = None


class AnticipoOut(ORM):
    id: int
    obra_id: int
    importe: Decimal
    comprobante: str
    fecha: date


# ---------------- Gastos / Facturas ----------------
class FacturaOut(ORM):
    id: int
    uuid: str
    serie: Optional[str]
    folio: Optional[str]
    subtotal: Decimal
    total: Decimal
    rfc_emisor: str
    forma_pago_sat: Optional[str]
    metodo_pago_sat: Optional[str]
    ruta_xml: str
    ruta_pdf: Optional[str]


class GastoManualCreate(BaseModel):
    fecha: date
    proveedor_id: Optional[int] = None
    concepto_resumido: str = Field(min_length=1, max_length=255)
    comprobante: str = Field("", max_length=100)
    tipo_comprobante: Optional[Literal["NOTA", "TICKET", "FACTURA", "RECIBO"]] = "NOTA"
    importe: Dinero
    metodo_pago: MetodoPago
    origen: Literal["manual", "nota"] = "manual"


class GastoUpdate(BaseModel):
    fecha: Optional[date] = None
    proveedor_id: Optional[int] = None
    concepto_resumido: Optional[str] = Field(None, min_length=1, max_length=255)
    comprobante: Optional[str] = Field(None, max_length=100)
    tipo_comprobante: Optional[Literal["NOTA", "TICKET", "FACTURA", "RECIBO"]] = None
    importe: Optional[Dinero] = None
    metodo_pago: Optional[MetodoPago] = None


class GastoOut(BaseModel):
    id: int
    obra_id: int
    obra_nombre: str
    fecha: date
    proveedor_id: Optional[int]
    proveedor_nombre: Optional[str]
    concepto_resumido: str
    comprobante: str
    tipo_comprobante: str = "NOTA"
    importe: Decimal
    metodo_pago: MetodoPago
    origen: OrigenGasto
    factura: Optional[FacturaOut] = None


class DuplicadoInfo(BaseModel):
    gasto_id: int
    obra_id: int
    obra_nombre: str
    fecha: date


class ErrorArchivo(BaseModel):
    archivo: str
    codigo: str
    detalle: str
    duplicado_de: Optional[DuplicadoInfo] = None


class ProveedorSugerido(BaseModel):
    rfc: str
    razon_social: str
    existente_id: Optional[int] = None
    alias: Optional[str] = None


class SugeridoGasto(BaseModel):
    fecha: date
    concepto_resumido: str
    comprobante: str
    metodo_pago: Optional[MetodoPago] = None  # None = el usuario debe elegirlo
    proveedor_alias: Optional[str] = None
    requiere_decision_metodo_pago: bool = False


class FacturaLeida(BaseModel):
    staging_id: str
    archivo_xml: str
    archivo_pdf: Optional[str] = None
    datos: Dict[str, Any]
    proveedor: ProveedorSugerido
    sugerido: SugeridoGasto
    requiere_decision_metodo_pago: bool = False


class UploadFacturasOut(BaseModel):
    items: List[FacturaLeida]
    errores: List[ErrorArchivo]


class FacturaConfirmarItem(BaseModel):
    staging_id: str
    metodo_pago: Optional[MetodoPago] = None
    fecha: Optional[date] = None
    concepto_resumido: Optional[str] = Field(None, min_length=1, max_length=255)
    comprobante: Optional[str] = Field(None, max_length=100)
    proveedor_alias: Optional[str] = Field(None, max_length=255)
    proveedor_razon_social: Optional[str] = Field(None, min_length=1, max_length=255)


class FacturasConfirmar(BaseModel):
    items: List[FacturaConfirmarItem] = Field(min_length=1)


# ---------------- Pagos de raya ----------------
class PagoRayaCreate(BaseModel):
    trabajador_id: int
    semana_numero: int = Field(ge=1)
    fecha_inicio: date
    fecha_fin: date
    tipo: TipoRaya
    cantidad: Cantidad
    tarifa: Dinero
    importe: Optional[Dinero] = None  # si no viene: cantidad * tarifa

    @model_validator(mode="after")
    def _fechas(self) -> "PagoRayaCreate":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio.")
        return self


class FilaSemanaRayaCreate(BaseModel):
    trabajador_id: int
    tipo: TipoRaya
    cantidad: Cantidad
    tarifa: Dinero
    importe: Optional[Dinero] = None


class PagosSemanaCreate(BaseModel):
    semana_numero: int = Field(ge=1)
    fecha_inicio: date
    fecha_fin: date
    filas: List[FilaSemanaRayaCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _fechas(self) -> "PagosSemanaCreate":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio.")
        return self


class PagoRayaUpdate(BaseModel):
    trabajador_id: Optional[int] = None
    semana_numero: Optional[int] = Field(None, ge=1)
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    tipo: Optional[TipoRaya] = None
    cantidad: Optional[Cantidad] = None
    tarifa: Optional[Dinero] = None
    importe: Optional[Dinero] = None


class PagoRayaOut(BaseModel):
    id: int
    obra_id: int
    trabajador_id: int
    trabajador_nombre: str
    oficio: str
    semana_numero: int
    fecha_inicio: date
    fecha_fin: date
    tipo: TipoRaya
    cantidad: Decimal
    tarifa: Decimal
    importe: Decimal


class TrabajadorPagosOut(BaseModel):
    trabajador: TrabajadorOut
    total_acumulado: Decimal
    pagos: List[PagoRayaOut]


# ---------------- Memorias ----------------
class RenglonMemoria(BaseModel):
    ref_tipo: Literal["gasto", "raya", "anticipo"]
    ref_id: int
    categoria: Literal["transferencia", "efectivo", "raya", "anticipo"]
    incluido: bool = True
    fecha: date
    proveedor: str = ""  # alias del proveedor (gasto) o nombre del trabajador (raya)
    concepto: str
    comprobante: str = ""
    tipo_comprobante: Optional[str] = None
    importe: Decimal
    es_externo: bool = False
    obra_origen: Optional[str] = None
    ya_incluido_en: Optional[str] = None  # aviso: ya está en otra memoria cerrada
    en_otro_borrador: Optional[str] = None  # aviso: está en otro borrador
    # fechas reales de semana (para rayas)
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    # solo rayas
    oficio: Optional[str] = None
    semana_numero: Optional[int] = None
    tipo_raya: Optional[TipoRaya] = None
    cantidad: Optional[Decimal] = None
    tarifa: Optional[Decimal] = None


class ItemSeleccion(BaseModel):
    ref_tipo: Literal["gasto", "raya", "anticipo"]
    ref_id: int
    incluido: bool


class PreviewIn(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    fecha_emision: Optional[date] = None
    ciudad: Optional[str] = "Zapopan, Jalisco"
    gastos_extra_ids: List[int] = []
    rayas_extra_ids: List[int] = []
    numero: Optional[int] = Field(None, ge=1)
    porcentaje_honorarios: Optional[Porcentaje] = None
    seleccion: Optional[List[ItemSeleccion]] = None

    @model_validator(mode="after")
    def _fechas(self) -> "PreviewIn":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio.")
        return self


class PreviewOut(BaseModel):
    obra_id: int
    numero_sugerido: int
    folio_sugerido: Optional[str] = None
    fecha_inicio: date
    fecha_fin: date
    fecha_emision: Optional[date] = None
    ciudad: Optional[str] = "Zapopan, Jalisco"
    porcentaje_honorarios: Decimal
    renglones: List[RenglonMemoria]
    anticipos: List[RenglonMemoria] = []
    rayas_posteriores: List[RenglonMemoria] = []
    totales: Dict[str, str]
    total_texto: str
    importe_factura_texto: Optional[str] = None
    gastado_a_la_fecha_texto: Optional[str] = None


class RenglonEdit(BaseModel):
    """Selección y ediciones del usuario sobre un renglón. Lo no enviado se toma de la BD."""

    ref_tipo: Literal["gasto", "raya", "anticipo"]
    ref_id: int
    incluido: bool = True
    proveedor: Optional[str] = None
    concepto: Optional[str] = Field(None, min_length=1, max_length=255)
    comprobante: Optional[str] = Field(None, max_length=100)
    tipo_comprobante: Optional[str] = None
    importe: Optional[Dinero] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    oficio: Optional[str] = None
    semana_numero: Optional[int] = None
    tipo_raya: Optional[TipoRaya] = None
    cantidad: Optional[Decimal] = None
    tarifa: Optional[Decimal] = None


class MemoriaGuardar(BaseModel):
    obra_id: int
    numero: Optional[int] = Field(None, ge=1)
    folio_factura_arquitecto: Optional[str] = None
    fecha_inicio: date
    fecha_fin: date
    fecha_emision: Optional[date] = None
    ciudad: Optional[str] = "Zapopan, Jalisco"
    porcentaje_honorarios: Optional[Porcentaje] = None  # por defecto el de la obra
    renglones: List[RenglonEdit]

    @model_validator(mode="after")
    def _fechas(self) -> "MemoriaGuardar":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio.")
        return self


class MemoriaResumenOut(BaseModel):
    id: int
    obra_id: int
    numero: int
    folio_factura_arquitecto: Optional[str] = None
    fecha_inicio: date
    fecha_fin: date
    fecha_emision: Optional[date] = None
    ciudad: Optional[str] = "Zapopan, Jalisco"
    porcentaje_honorarios_usado: Decimal
    estado: EstadoMemoria
    total_texto: str
    total_memoria: Optional[str] = None
    importe_factura_texto: Optional[str] = None
    gastado_a_la_fecha_texto: Optional[str] = None
    cerrada_at: Optional[datetime] = None


class MemoriaOut(MemoriaResumenOut):
    renglones: List[RenglonMemoria]
    anticipos: List[RenglonMemoria] = []
    totales: Dict[str, str]


# ---------------- Configuración ----------------
class ConfiguracionOut(BaseModel):
    clave: str
    valor: str


class ConfiguracionUpdate(BaseModel):
    valor: str


class RespaldoItem(BaseModel):
    nombre: str
    ruta: str
    tamano_bytes: int
    tamano_formateado: str
    fecha_creacion: str
    fecha_creacion_iso: str
    origen: str


class RespaldosInfoOut(BaseModel):
    carpeta_actual: str
    carpeta_configurada: Optional[str] = None
    respaldos: List[RespaldoItem]


class RestaurarRespaldoRequest(BaseModel):
    nombre_archivo: str


class RestablecerDatosRequest(BaseModel):
    confirmacion: str
