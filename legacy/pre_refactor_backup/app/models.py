import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TimestampMixin:
    """Mixin adding created_at and updated_at timezone-aware timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PaymentType(str, enum.Enum):
    """Supported payment types."""
    PAYROLL = "payroll"
    BANK_TRANSFER = "bank_transfer"
    MANUAL_NOTE = "manual_note"


class Project(TimestampMixin, Base):
    """Construction project entity."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="in_progress")

    # One-to-Many Relationships
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name='{self.name}' status='{self.status}'>"


class Supplier(TimestampMixin, Base):
    """Supplier providing construction materials and services."""

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    material_category: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # One-to-Many Relationship with Invoices
    invoices: Mapped[List["Invoice"]] = relationship(
        "Invoice",
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Supplier id={self.id} name='{self.name}' category='{self.material_category}'>"


class Worker(TimestampMixin, Base):
    """Worker / Contractor for labor and payroll tracking."""

    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., mason, electrician
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # One-to-Many Relationship with Payments
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="worker",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Worker id={self.id} full_name='{self.full_name}' role='{self.role}'>"


class Invoice(TimestampMixin, Base):
    """Invoice for materials and supplier expenses."""

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    concept: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pdf_s3_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    date_issued: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_parsed_automatically: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="invoices")
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="invoices")

    __table_args__ = (
        Index("ix_invoices_project_date_issued", "project_id", "date_issued"),
    )

    def __repr__(self) -> str:
        return f"<Invoice id={self.id} number='{self.invoice_number}' amount={self.amount}>"


class Payment(TimestampMixin, Base):
    """Payment record for payroll, transfers, and general notes."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type_enum", native_enum=True),
        nullable=False,
    )
    date_paid: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="payments")
    worker: Mapped[Optional["Worker"]] = relationship("Worker", back_populates="payments")

    __table_args__ = (
        Index("ix_payments_project_date_paid", "project_id", "date_paid"),
    )

    def __repr__(self) -> str:
        return f"<Payment id={self.id} type='{self.payment_type}' amount={self.amount}>"
