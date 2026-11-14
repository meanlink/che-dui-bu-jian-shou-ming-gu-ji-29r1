from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Job, Dataset
from src.schemas.job import JobInput
from src.middlewares.auth import current_scope, can_write, admin_only
from src.services import jobs
from src.services.audit import record
from src.utils.serialization import job_dict
router=APIRouter(prefix='/jobs')
@router.get('')
def listing(db=Depends(get_db),scope=Depends(current_scope)):
    return [job_dict(j) for j in db.scalars(select(Job).where(
        Job.fleet_id==scope.fleet_id).order_by(Job.id.desc()).limit(100))]
@router.post('',status_code=201)
def create(data:JobInput,db=Depends(get_db),scope=Depends(can_write)):
    j=jobs.create(db,data,scope)
    record(db,scope.user.email,'job.create',{'id':j.id,'params':j.params},fleet_id=scope.fleet_id)
    db.commit(); jobs.enqueue(j.id); return job_dict(j)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),scope=Depends(current_scope)):
    j=jobs.visible(db,id,scope.fleet_id)
    return job_dict(j)
@router.post('/{id}/approve')
def approve(id:int,db=Depends(get_db),scope=Depends(admin_only)):
    j=jobs.visible(db,id,scope.fleet_id)
    if j.status!='completed':raise HTTPException(409,'仅已完成结果可以批准')
    j.approved=True; record(db,scope.user.email,'job.approve',{'id':id},fleet_id=scope.fleet_id); db.commit()
    return job_dict(j)
