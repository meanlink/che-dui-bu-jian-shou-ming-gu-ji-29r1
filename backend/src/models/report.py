from sqlalchemy import String, Double, ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_id: Mapped[int | None] = mapped_column(ForeignKey('fleets.id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    destination: Mapped[str] = mapped_column(String(120))
    interval_seconds: Mapped[int]
    next_run: Mapped[float] = mapped_column(Double)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    sealed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    legacy_claim_id: Mapped[int | None] = mapped_column(ForeignKey('legacy_claims.id'), nullable=True)
class Delivery(Base):
    __tablename__ = 'deliveries'
    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_id: Mapped[int | None] = mapped_column(ForeignKey('fleets.id'), nullable=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey('reports.id'))
    created_at: Mapped[float] = mapped_column(Double)
    checksum: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(160))
    destination: Mapped[str] = mapped_column(String(120))
    sealed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    legacy_claim_id: Mapped[int | None] = mapped_column(ForeignKey('legacy_claims.id'), nullable=True)
