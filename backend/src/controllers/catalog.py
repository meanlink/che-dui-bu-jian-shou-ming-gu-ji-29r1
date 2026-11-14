from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from src.config.database import get_db
from src.middlewares.auth import current_scope
from src.models import Dataset, Job, Report, Audit
from src.services.business import metadata
router=APIRouter()
@router.get('/meta')
def meta():return metadata()
@router.get('/overview')
def overview(db=Depends(get_db),scope=Depends(current_scope)):
    fid=scope.fleet_id
    return {'fleet':{'id':scope.fleet.id,'name':scope.fleet.name},
            'datasets':db.scalar(select(func.count()).select_from(Dataset).where(Dataset.fleet_id==fid)),
            'records':sum(len(d.records) for d in db.scalars(select(Dataset).where(Dataset.fleet_id==fid))),
            'jobs':db.scalar(select(func.count()).select_from(Job).where(Job.fleet_id==fid)),
            'approved':db.scalar(select(func.count()).select_from(Job).where(Job.fleet_id==fid,Job.approved==True)),
            'reports':db.scalar(select(func.count()).select_from(Report).where(Report.fleet_id==fid))}
@router.get('/audits')
def audits(db=Depends(get_db),scope=Depends(current_scope)):
    return [{'id':a.id,'actor':a.actor,'action':a.action,'detail':a.detail,'at':a.at}
            for a in db.scalars(select(Audit).where(Audit.fleet_id==scope.fleet_id).order_by(Audit.id.desc()).limit(50))]
