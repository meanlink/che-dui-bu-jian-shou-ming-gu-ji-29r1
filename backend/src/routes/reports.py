import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from src.config.database import get_db
from src.config.settings import ARTIFACT_DIR
from src.models import Report, Delivery
from src.schemas.report import ReportInput
from src.middlewares.auth import current_scope, admin_only
from src.services import reports
from src.services.audit import record
from src.utils.serialization import report_dict, delivery_dict
router=APIRouter()
@router.get('/reports')
def listing(db=Depends(get_db),scope=Depends(current_scope)):
    return [report_dict(r) for r in db.scalars(select(Report).where(
        Report.fleet_id==scope.fleet_id).order_by(Report.id.desc()))]
@router.post('/reports',status_code=201)
def create(data:ReportInput,db=Depends(get_db),scope=Depends(admin_only)):
    r=reports.create(db,data,scope)
    record(db,scope.user.email,'report.schedule',{'id':r.id,'destination':r.destination},fleet_id=scope.fleet_id)
    db.commit()
    return report_dict(r)
@router.post('/reports/{id}/toggle')
def toggle(id:int,db=Depends(get_db),scope=Depends(admin_only)):
    r=reports.visible(db,id,scope.fleet_id)
    r.enabled=not r.enabled;record(db,scope.user.email,'report.toggle',{'id':id,'enabled':r.enabled},fleet_id=scope.fleet_id);db.commit()
    return report_dict(r)
@router.get('/deliveries')
def deliveries(db=Depends(get_db),scope=Depends(current_scope)):
    return [delivery_dict(d) for d in db.scalars(select(Delivery).where(
        Delivery.fleet_id==scope.fleet_id).order_by(Delivery.id.desc()).limit(100))]
@router.get('/deliveries/{id}/download')
def download(id:int,format:str='csv',db=Depends(get_db),scope=Depends(current_scope)):
    d=reports.visible_delivery(db,id,scope.fleet_id)
    if format not in ('csv','json'):raise HTTPException(422,'支持 CSV 或 JSON')
    filename=d.filename+('.json' if format=='json' else '')
    p=os.path.join(ARTIFACT_DIR,filename)
    if not os.path.exists(p):raise HTTPException(404,'归档文件不存在，请重新安排分发')
    return FileResponse(p,filename=filename,media_type='application/json' if format=='json' else 'text/csv; charset=utf-8')
