"""Modelo de datos local (SQLite). Todo el dinero es Decimal (ver app/types.py)."""
import enum
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.types import DecimalText


def _enum(e: type[enum.Enum], name: str) -> Enum:
    """Enum guardado como texto (valor en minúsculas), sin tipo nativo."""
    return Enum(e, name=name, native_enum=False, values_callable=lambda x: [m.value for m in x])


class EstadoObra(str, enum.Enum):
    EN_CURSO = "en_curso"
    PAUSADA = "pausada"
    CONCLUIDA = "concluida"


class MetodoPago(str, enum.Enum):
    TRANSFERENCIA = "transferencia"
    EFECTIVO = "efectivo"


class OrigenGasto(str, enum.Enum):
    XML = "xml"
    MANUAL = "manual"
    NOTA = "nota"


class TipoRaya(str, enum.Enum):
    DESTAJO = "destajo"  # cantidad = metros
    DIA = "dia"  # cantidad = días


class EstadoMemoria(str, enum.Enum):
    BORRADOR = "borrador"
    CERRADA = "cerrada"


class TipoProveedor(str, enum.Enum):
    CON_FACTURA = "con_factura"
    SIN_FACTURA = "sin_factura"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Obra(TimestampMixin, Base):
    __tablename__ = "obras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ubicacion: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    propietario: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Porcentaje (10 = 10%). Propio de cada obra.
    porcentaje_honorarios: Mapped[Decimal] = mapped_column(
        DecimalText(2), nullable=False, default=Decimal("10.00")
    )
    # Saldos iniciales para obras en curso previas al sistema:
    saldo_inicial_transferencias: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False, default=Decimal("0.00"))
    saldo_inicial_efectivo: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False, default=Decimal("0.00"))
    saldo_inicial_rayas: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False, default=Decimal("0.00"))
    saldo_inicial_memorias_anteriores: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False, default=Decimal("0.00"))

    # Compatibilidad hacia atrás (alias properties / getters)
    numero_ultima_memoria_previa: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estado: Mapped[EstadoObra] = mapped_column(_enum(EstadoObra, "estado_obra"), nullable=False, default=EstadoObra.EN_CURSO)

    # Columnas en base de datos para SQLite y compatibilidad hacia atrás:
    _saldo_inicial_acumulado: Mapped[Decimal] = mapped_column(
        "saldo_inicial_acumulado", DecimalText(2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )
    _saldo_inicial_gastado: Mapped[Decimal] = mapped_column(
        "saldo_inicial_gastado", DecimalText(2), nullable=False, default=Decimal("0.00"), server_default="0.00"
    )

    @property
    def saldo_inicial_acumulado(self) -> Decimal:
        return self.saldo_inicial_transferencias

    @saldo_inicial_acumulado.setter
    def saldo_inicial_acumulado(self, val: Decimal):
        self.saldo_inicial_transferencias = val
        self._saldo_inicial_acumulado = val

    @property
    def saldo_inicial_gastado(self) -> Decimal:
        return self.saldo_inicial_memorias_anteriores

    @saldo_inicial_gastado.setter
    def saldo_inicial_gastado(self, val: Decimal):
        self.saldo_inicial_memorias_anteriores = val
        self._saldo_inicial_gastado = val

    gastos: Mapped[List["Gasto"]] = relationship(back_populates="obra", cascade="all, delete-orphan")
    pagos_raya: Mapped[List["PagoRaya"]] = relationship(back_populates="obra", cascade="all, delete-orphan")
    anticipos: Mapped[List["Anticipo"]] = relationship(back_populates="obra", cascade="all, delete-orphan")
    memorias: Mapped[List["Memoria"]] = relationship(back_populates="obra", cascade="all, delete-orphan")


class Proveedor(TimestampMixin, Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[TipoProveedor] = mapped_column(
        _enum(TipoProveedor, "tipo_proveedor"), nullable=False, default=TipoProveedor.CON_FACTURA
    )
    rfc: Mapped[Optional[str]] = mapped_column(String(13), nullable=True, unique=True, index=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nombre comercial que aparece en la memoria; editable y reutilizable.
    alias: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    gastos: Mapped[List["Gasto"]] = relationship(back_populates="proveedor")

    @property
    def nombre_memoria(self) -> str:
        return (self.alias or "").strip() or self.razon_social


class Gasto(TimestampMixin, Base):
    __tablename__ = "gastos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    obra_id: Mapped[int] = mapped_column(ForeignKey("obras.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    proveedor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True)
    concepto_resumido: Mapped[str] = mapped_column(String(255), nullable=False)
    comprobante: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    tipo_comprobante: Mapped[str] = mapped_column(String(20), nullable=False, default="NOTA")
    importe: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False)
    metodo_pago: Mapped[MetodoPago] = mapped_column(_enum(MetodoPago, "metodo_pago"), nullable=False)
    origen: Mapped[OrigenGasto] = mapped_column(_enum(OrigenGasto, "origen_gasto"), nullable=False)

    obra: Mapped["Obra"] = relationship(back_populates="gastos")
    proveedor: Mapped[Optional["Proveedor"]] = relationship(back_populates="gastos")
    factura: Mapped[Optional["Factura"]] = relationship(back_populates="gasto", cascade="all, delete-orphan", uselist=False)

    __table_args__ = (Index("ix_gastos_obra_fecha", "obra_id", "fecha"),)


class Factura(TimestampMixin, Base):
    __tablename__ = "facturas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gasto_id: Mapped[int] = mapped_column(ForeignKey("gastos.id", ondelete="CASCADE"), nullable=False, unique=True)
    uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    serie: Mapped[Optional[str]] = mapped_column(String(25), nullable=True)
    folio: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False)
    total: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False)
    rfc_emisor: Mapped[str] = mapped_column(String(13), nullable=False)
    forma_pago_sat: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    metodo_pago_sat: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    ruta_xml: Mapped[str] = mapped_column(String(500), nullable=False)
    ruta_pdf: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    gasto: Mapped["Gasto"] = relationship(back_populates="factura")


class Trabajador(TimestampMixin, Base):
    __tablename__ = "trabajadores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    oficio: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    pagos: Mapped[List["PagoRaya"]] = relationship(back_populates="trabajador")


class PagoRaya(TimestampMixin, Base):
    __tablename__ = "pagos_raya"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    obra_id: Mapped[int] = mapped_column(ForeignKey("obras.id", ondelete="CASCADE"), nullable=False, index=True)
    trabajador_id: Mapped[int] = mapped_column(ForeignKey("trabajadores.id", ondelete="RESTRICT"), nullable=False, index=True)
    semana_numero: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo: Mapped[TipoRaya] = mapped_column(_enum(TipoRaya, "tipo_raya"), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(DecimalText(3), nullable=False)  # metros o días
    tarifa: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False)
    importe: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False)

    obra: Mapped["Obra"] = relationship(back_populates="pagos_raya")
    trabajador: Mapped["Trabajador"] = relationship(back_populates="pagos")


class Anticipo(TimestampMixin, Base):
    __tablename__ = "anticipos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    obra_id: Mapped[int] = mapped_column(ForeignKey("obras.id", ondelete="CASCADE"), nullable=False, index=True)
    importe: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False)
    comprobante: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    fecha: Mapped[date] = mapped_column(Date, nullable=False)

    obra: Mapped["Obra"] = relationship(back_populates="anticipos")


class Memoria(TimestampMixin, Base):
    __tablename__ = "memorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    obra_id: Mapped[int] = mapped_column(ForeignKey("obras.id", ondelete="CASCADE"), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    porcentaje_honorarios_usado: Mapped[Decimal] = mapped_column(DecimalText(2), nullable=False)
    estado: Mapped[EstadoMemoria] = mapped_column(_enum(EstadoMemoria, "estado_memoria"), nullable=False, default=EstadoMemoria.BORRADOR)
    # Renglones y totales congelados (JSON; los importes van como texto Decimal).
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    total_texto: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    folio_factura_arquitecto: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fecha_emision: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False, default="Zapopan, Jalisco")
    cerrada_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    obra: Mapped["Obra"] = relationship(back_populates="memorias")

    __table_args__ = (UniqueConstraint("obra_id", "numero", name="uq_memoria_obra_numero"),)


class Configuracion(TimestampMixin, Base):
    __tablename__ = "configuraciones"

    clave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False, default="")


class RegistroAuditoria(TimestampMixin, Base):
    __tablename__ = "registros_auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    accion: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    memoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("memorias.id", ondelete="SET NULL"), nullable=True)
    obra_id: Mapped[Optional[int]] = mapped_column(ForeignKey("obras.id", ondelete="CASCADE"), nullable=True)
    detalles: Mapped[str] = mapped_column(Text, nullable=False, default="")

