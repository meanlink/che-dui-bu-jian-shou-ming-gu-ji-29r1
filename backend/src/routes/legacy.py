from fastapi import APIRouter, Depends
from src.config.database import get_db
from src.middlewares.auth import current_scope, admin_only
from src.models import Fleet
from src.services import legacy
from src.services.audit import record
router=APIRouter(prefix='/legacy')
def _fleet_names(db):
    return {fleet.id:fleet.name for fleet in db.query(Fleet).all()}
@router.get('/chains')
def chains(scope=Depends(admin_only),db=Depends(get_db)):
    return legacy.sealed_chains(db,_fleet_names(db))
@router.get('/chains/{dataset_id}')
def chain(dataset_id:int,scope=Depends(admin_only),db=Depends(get_db)):
    return legacy.sealed_chain(db,dataset_id,_fleet_names(db))
@router.post('/chains/{dataset_id}/claim')
def claim(dataset_id:int,scope=Depends(admin_only),db=Depends(get_db)):
    summary,duplicate=legacy.claim_chain(db,scope.fleet,scope.user,dataset_id)
    record(db,scope.user.email,'legacy.claim',
           {'dataset':dataset_id,'claim':summary['claim']['id'] if summary['claim'] else None,
            'duplicate':duplicate,'counts':summary['counts']},fleet_id=scope.fleet_id)
    db.commit()
    return {**summary,'duplicate':duplicate}
