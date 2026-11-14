import time
from sqlalchemy import select
from src.models import Audit


def record(db, actor, action, detail=None, fleet_id=None):
    db.add(Audit(actor=actor, action=action, detail=detail or {}, at=time.time(), fleet_id=fleet_id))
