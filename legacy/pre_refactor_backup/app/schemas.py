import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models import PaymentType


# ==========================================
# Base Schema Configuration
# ==========================================
class OrmBaseModel(BaseModel):
    """Modelo base de Pydantic V2 con soporte para ORM y población por nombre/alias."""
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        validate_assignment=True,
    )


class TimestampSchema(BaseModel):
    """Esquema para marcas de tiempo de auditoría."""
    created_at: datetime = Field(..., description="Fecha y hora de creación")
    updated_at: datetime = Field(..., description="Fecha y hora de última modificación")


# ==========================================
# Supplier (Proveedor) Schemas
# ==========================================
class SupplierBase(BaseModel):
    name: str = Field(
        ...,
        max_length=255,
        description="Nombre o razón social del proveedor",
    )
    material_category: str = Field(
        ...,
        max_length=100,
        description="Categoría de material o servicio (ej. Concreto, Acero, Plomería)",
    )
    contact_details: Optional[str] = Field(
        None,
        description="Datos de contacto (teléfono, correo, dirección)",
    )


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    material_category: Optional[str] = Field(None, max_length=100)
    contact_details: Optional[str] = None


class SupplierResponse(SupplierBase, TimestampSchema, OrmBaseModel):
    id: uuid.UUID


# ==========================================
# Worker (Trabajador / Contratista) Schemas
# ==========================================
class WorkerBase(BaseModel):
    full_name: str = Field(
        ...,
        max_length=255,
        description="Nombre completo del trabajador o cuadrilla",
    )
    role: str = Field(
        ...,
        max_length=100,
        description="Oficio o puesto (ej. Maestro de Obra, Albañil, Electricista)",
    )
    daily_rate: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Sueldo o tarifa diaria pactada",
    )

    @field_validator("daily_rate")
    @classmethod
    def validate_daily_rate(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("El sueldo diario no puede ser un valor negativo.")
        return v


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=100)
    daily_rate: Optional[Decimal] = Field(None, ge=0, decimal_places=2)


class WorkerResponse(WorkerBase, TimestampSchema, OrmBaseModel):
    id: uuid.UUID


class WorkerSummaryResponse(WorkerBase, TimestampSchema, OrmBaseModel):
    id: uuid.UUID
    total_payroll_accumulated: Decimal = Field(default=Decimal("0.00"), description="Total de nómina acumulada pagada al trabajador")
    total_payments_count: int = Field(default=0, description="Total de pagos de nómina registrados")
    last_payment_date: Optional[date] = Field(None, description="Fecha del último pago registrado")


# ==========================================
# Project (Proyecto de Construcción) Schemas
# ==========================================
class ProjectBase(BaseModel):
    name: str = Field(
        ...,
        max_length=255,
        description="Nombre de la obra o proyecto",
    )
    client_name: str = Field(
        ...,
        max_length=255,
        description="Nombre del cliente o propietario",
    )
    start_date: date = Field(
        ...,
        description="Fecha de inicio del proyecto",
    )
    status: str = Field(
        default="in_progress",
        max_length=50,
        description="Estado de la obra (ej. in_progress, completed, paused)",
    )


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    client_name: Optional[str] = Field(None, max_length=255)
    start_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)


class ProjectResponse(ProjectBase, TimestampSchema, OrmBaseModel):
    id: uuid.UUID


# ==========================================
# Payment (Pagos, Nóminas y Gastos) Schemas
# ==========================================
class PaymentBase(BaseModel):
    project_id: uuid.UUID = Field(
        ...,
        description="Identificador único del proyecto asociado",
    )
    worker_id: Optional[uuid.UUID] = Field(
        None,
        description="Identificador del trabajador (requerido únicamente para nómina)",
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Monto pagado o dispersado",
    )
    payment_type: PaymentType = Field(
        ...,
        description="Tipo de pago: payroll (nómina), bank_transfer (transferencia), manual_note (nota/efectivo)",
    )
    date_paid: date = Field(
        ...,
        description="Fecha en que se realizó el pago",
    )
    description: Optional[str] = Field(
        None,
        description="Detalle, concepto o justificación del gasto",
    )

    @field_validator("amount")
    @classmethod
    def validate_payment_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("El monto del pago debe ser mayor a $0.00.")
        return v


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    worker_id: Optional[uuid.UUID] = None
    amount: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    payment_type: Optional[PaymentType] = None
    date_paid: Optional[date] = None
    description: Optional[str] = None


class PaymentResponse(PaymentBase, TimestampSchema, OrmBaseModel):
    id: uuid.UUID
    worker: Optional[WorkerResponse] = None
    project: Optional[ProjectResponse] = None


# ==========================================
# Invoice (Facturas CFDI) - The Parser Bridge
# ==========================================
class InvoiceBase(BaseModel):
    project_id: uuid.UUID = Field(
        ...,
        description="Identificador del proyecto al que se imputa el gasto",
    )
    supplier_id: Optional[uuid.UUID] = Field(
        None,
        description="Identificador del proveedor emisor de la factura",
    )
    supplier_name: Optional[str] = Field(
        None,
        max_length=255,
        validation_alias=AliasChoices("proveedor", "supplier_name"),
        description="Nombre o razón social del proveedor emisor",
    )
    invoice_number: str = Field(
        ...,
        max_length=100,
        validation_alias=AliasChoices("comprobante", "invoice_number"),
        description="Folio Fiscal UUID o número de comprobante",
    )
    concept: str = Field(
        ...,
        max_length=255,
        validation_alias=AliasChoices("concepto", "concept"),
        description="Descripción o concepto de los materiales/servicios facturados",
    )
    amount: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        validation_alias=AliasChoices("importe", "amount"),
        description="Importe total facturado",
    )
    pdf_s3_url: Optional[str] = Field(
        None,
        max_length=1024,
        description="Enlace al archivo PDF almacenado en S3",
    )
    date_issued: date = Field(
        ...,
        validation_alias=AliasChoices("fecha", "date_issued"),
        description="Fecha de emisión del comprobante fiscal",
    )
    is_parsed_automatically: bool = Field(
        default=False,
        description="Indica si los datos fueron extraídos automáticamente vía OCR/CFDI",
    )

    @field_validator("concept", mode="before")
    @classmethod
    def normalize_concept(cls, v: Any) -> str:
        """Permite recibir el concepto como string o como lista desde el extractor CFDI."""
        if isinstance(v, list):
            joined = ", ".join(str(item) for item in v if item)
            return joined[:255] if joined else "Materiales / Servicios"
        if isinstance(v, str):
            return v.strip()[:255]
        return "Materiales / Servicios"

    @field_validator("date_issued", mode="before")
    @classmethod
    def parse_date_issued(cls, v: Any) -> Any:
        """Convierte strings de fecha ISO (YYYY-MM-DD) a objeto date."""
        if isinstance(v, str):
            try:
                return date.fromisoformat(v.split("T")[0])
            except ValueError:
                raise ValueError(f"Formato de fecha inválido: '{v}'. Debe ser YYYY-MM-DD.")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v: Any) -> Any:
        """Valida y convierte el importe numérico a Decimal con 2 decimales."""
        if v is None:
            return Decimal("0.00")
        try:
            dec = Decimal(str(v))
            if dec < 0:
                raise ValueError("El importe de la factura no puede ser negativo.")
            return dec
        except Exception:
            raise ValueError(f"El importe '{v}' no es un número válido.")


class InvoiceCreate(InvoiceBase):
    """
    Esquema para crear facturas.
    Soporta instanciación directa desde el diccionario en español del extractor CFDI:
    InvoiceCreate(**{'comprobante': '...', 'fecha': '...', 'importe': 1500.0, 'concepto': '...'})
    """
    model_config = ConfigDict(populate_by_name=True)


class InvoiceUpdate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    supplier_id: Optional[uuid.UUID] = None
    invoice_number: Optional[str] = Field(None, max_length=100)
    concept: Optional[str] = Field(None, max_length=255)
    amount: Optional[Decimal] = Field(None, ge=0, decimal_places=2)
    pdf_s3_url: Optional[str] = Field(None, max_length=1024)
    date_issued: Optional[date] = None
    is_parsed_automatically: Optional[bool] = None


class InvoiceResponse(InvoiceBase, TimestampSchema, OrmBaseModel):
    id: uuid.UUID
    supplier: Optional[SupplierResponse] = None


# ==========================================
# Memory Report Aggregation (Memoria de Obra)
# ==========================================
class MemorySummary(BaseModel):
    """Resumen financiero consolidado con honorarios e IVA según la estructura exacta del arquitecto."""
    # 1. Subtotales Base
    subtotal_transferencias: Decimal = Field(
        default=Decimal("0.00"),
        description="Suma total de transferencias bancarias de la memoria",
    )
    subtotal_efectivo: Decimal = Field(
        default=Decimal("0.00"),
        description="Suma total de facturas de proveedores y notas de gasto en efectivo",
    )
    subtotal_rayas: Decimal = Field(
        default=Decimal("0.00"),
        description="Suma total de nóminas y rayas de mano de obra",
    )

    # 2. Lógica de Facturación y Honorarios del Arquitecto
    honorarios: Decimal = Field(
        default=Decimal("0.00"),
        description="Honorarios del 10% sobre el total de gastos (Transferencias + Efectivo + Rayas)",
    )
    subtotal_factura_arquitecto: Decimal = Field(
        default=Decimal("0.00"),
        description="Subtotal de la factura del arquitecto: Rayas + Honorarios",
    )
    iva: Decimal = Field(
        default=Decimal("0.00"),
        description="IVA 16% calculado únicamente sobre el subtotal de la factura del arquitecto",
    )
    importe_factura_arquitecto: Decimal = Field(
        default=Decimal("0.00"),
        description="Importe total de la factura del arquitecto: Subtotal Factura + IVA",
    )
    total_a_reembolsar: Decimal = Field(
        default=Decimal("0.00"),
        description="Cobrado / Saldo a mi favor: Importe Factura + Efectivo",
    )
    gran_total_obra: Decimal = Field(
        default=Decimal("0.00"),
        description="Gran total de la obra: Subtotal Transferencias + Total a Reembolsar",
    )

    monto_en_letras: str = Field(
        default="",
        description="Importe expresado en texto oficial en pesos mexicanos",
    )

    # Campos retrocompatibles y contadores
    total_transferencias: Decimal = Field(default=Decimal("0.00"))
    total_notas_facturas: Decimal = Field(default=Decimal("0.00"))
    total_rayas: Decimal = Field(default=Decimal("0.00"))
    total_gastos_directos: Decimal = Field(default=Decimal("0.00"))
    honorarios_transferencias: Decimal = Field(default=Decimal("0.00"))
    honorarios_notas_facturas: Decimal = Field(default=Decimal("0.00"))
    honorarios_rayas: Decimal = Field(default=Decimal("0.00"))
    total_honorarios: Decimal = Field(default=Decimal("0.00"))
    subtotal_honorarios_rayas: Decimal = Field(default=Decimal("0.00"))
    iva_honorarios: Decimal = Field(default=Decimal("0.00"))
    importe_honorarios_iva: Decimal = Field(default=Decimal("0.00"))
    gran_total: Decimal = Field(default=Decimal("0.00"))
    total_invoices_amount: Decimal = Field(default=Decimal("0.00"))
    total_payments_amount: Decimal = Field(default=Decimal("0.00"))
    total_expenses: Decimal = Field(default=Decimal("0.00"))
    invoices_count: int = Field(default=0)
    payments_count: int = Field(default=0)


class MemoryReportResponse(OrmBaseModel):
    """Esquema de respuesta para la Memoria de Obra bi-semanal."""
    project_id: uuid.UUID = Field(..., description="ID del proyecto")
    project_name: str = Field(..., description="Nombre de la obra")
    client_name: str = Field(..., description="Nombre del cliente")
    location: str = Field(default="Zapopan, Jalisco", description="Ubicación de la obra")
    memoria_number: str = Field(default="01", description="Número consecutivo de memoria")
    start_date: date = Field(..., description="Fecha inicial del periodo de memoria")
    end_date: date = Field(..., description="Fecha final del periodo de memoria")
    date_formatted: str = Field(default="", description="Fecha de emisión en formato formal")
    summary: MemorySummary = Field(..., description="Totales financieros agregados")
    invoices: List[InvoiceResponse] = Field(
        default_factory=list,
        description="Lista detallada de facturas en el periodo",
    )
    payments: List[PaymentResponse] = Field(
        default_factory=list,
        description="Lista detallada de pagos en el periodo",
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "MemoryReportResponse":
        if self.start_date > self.end_date:
            raise ValueError("La fecha inicial no puede ser posterior a la fecha final del periodo.")
        return self


# ==========================================
# Compilación Personalizada e Interactiva de Memorias
# ==========================================
class CustomMemoryItemInvoice(BaseModel):
    id: Optional[Union[uuid.UUID, str]] = None
    invoice_number: str = "CFDI-001"
    concept: str = "Materiales / Servicios"
    amount: Decimal = Decimal("0.00")
    date_issued: date
    supplier_name: Optional[str] = None
    pdf_s3_url: Optional[str] = None


class CustomMemoryItemPayment(BaseModel):
    id: Optional[Union[uuid.UUID, str]] = None
    payment_type: PaymentType = PaymentType.MANUAL_NOTE
    description: str = "Gasto"
    amount: Decimal = Decimal("0.00")
    date_paid: date
    worker_name: Optional[str] = None
    project_name: Optional[str] = None
    is_external: bool = False


class CustomMemoryPayload(BaseModel):
    memoria_number: str = Field(default="01", description="Número consecutivo de memoria")
    location: str = Field(default="Zapopan, Jalisco", description="Ubicación de la obra")
    start_date: date = Field(..., description="Fecha inicial del periodo")
    end_date: date = Field(..., description="Fecha final del periodo")
    invoices: List[CustomMemoryItemInvoice] = Field(default_factory=list)
    payments: List[CustomMemoryItemPayment] = Field(default_factory=list)


# Backward-compatible alias exports
ProjectOut = ProjectResponse
SupplierOut = SupplierResponse
WorkerOut = WorkerResponse
PaymentOut = PaymentResponse
InvoiceOut = InvoiceResponse
ProjectMemoryOut = MemoryReportResponse
ProjectMemorySummary = MemorySummary

