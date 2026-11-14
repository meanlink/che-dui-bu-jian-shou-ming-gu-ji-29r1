from sqlalchemy import String, JSON, Double, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Dataset(Base):
    __tablename__ = 'datasets'
    __table_args__ = (UniqueConstraint('fleet_id', 'name', name='uq_dataset_fleet_name'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_id: Mapped[int | None] = mapped_column(ForeignKey('fleets.id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(200), default='manual.json')
    records: Mapped[list] = mapped_column(JSON)
    checksum: Mapped[str] = mapped_column(String(64))
    sealed_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    legacy_claim_id: Mapped[int | None] = mapped_column(ForeignKey('legacy_claims.id'), nullable=True)
    created_at: Mapped[float] = mapped_column(Double)
