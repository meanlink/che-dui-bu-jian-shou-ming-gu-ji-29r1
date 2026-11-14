from sqlalchemy import String, Double, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Audit(Base):
    __tablename__ = 'audits'
    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_id: Mapped[int | None] = mapped_column(ForeignKey('fleets.id'), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(150))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[float] = mapped_column(Double)
