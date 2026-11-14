from sqlalchemy import String, Double, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class Fleet(Base):
    """A tenant. Business records never move between fleets through normal APIs."""

    __tablename__ = 'fleets'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[float] = mapped_column(Double)


class FleetMember(Base):
    """Active or revoked membership. Revocation bumps epoch and kills old tokens."""

    __tablename__ = 'fleet_members'
    __table_args__ = (UniqueConstraint('fleet_id', 'user_id', name='uq_fleet_member'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fleet_id: Mapped[int] = mapped_column(ForeignKey('fleets.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[float] = mapped_column(Double)
    revoked_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    epoch: Mapped[int] = mapped_column(Integer, default=0)


class LegacyClaim(Base):
    """One immutable claim record per sealed association chain (root dataset)."""

    __tablename__ = 'legacy_claims'
    id: Mapped[int] = mapped_column(primary_key=True)
    chain_root: Mapped[int] = mapped_column(Integer, unique=True)
    fleet_id: Mapped[int] = mapped_column(ForeignKey('fleets.id'), index=True)
    claimed_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    actor: Mapped[str] = mapped_column(String(150))
    claimed_at: Mapped[float] = mapped_column(Double)
    records: Mapped[int] = mapped_column(Integer, default=0)
    jobs: Mapped[int] = mapped_column(Integer, default=0)
    reports: Mapped[int] = mapped_column(Integer, default=0)
    deliveries: Mapped[int] = mapped_column(Integer, default=0)
