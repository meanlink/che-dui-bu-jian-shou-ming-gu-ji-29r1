from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Dataset
from src.schemas.dataset import DatasetInput
from src.middlewares.auth import current_scope, can_write
from src.services import datasets
from src.services.audit import record
from src.utils.serialization import dataset_dict
router=APIRouter(prefix='/datasets')
@router.get('')
def listing(db=Depends(get_db),scope=Depends(current_scope)):
    return [dataset_dict(d) for d in db.scalars(select(Dataset).where(
        Dataset.fleet_id==scope.fleet_id).order_by(Dataset.id.desc()))]
@router.post('',status_code=201)
def create(data:DatasetInput,db=Depends(get_db),scope=Depends(can_write)):
    d=datasets.create(db,data,scope.fleet_id)
    record(db,scope.user.email,'dataset.create',{'id':d.id,'rows':len(d.records)},fleet_id=scope.fleet_id)
    db.commit(); return dataset_dict(d)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),scope=Depends(current_scope)):
    d=datasets.visible(db,id,scope.fleet_id)
    return {**dataset_dict(d),'records':d.records}
