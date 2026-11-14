from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.config.database import get_db
from src.middlewares.auth import current_scope, admin_only
from src.models import FleetMember
from src.services import fleets
from src.services.audit import record
router=APIRouter(prefix='/fleets')
class MemberInput(BaseModel):
    email:str=Field(max_length=150)
    name:str=Field(default='',max_length=80)
    password:str=Field(default='',max_length=200)
    role:str=Field(default='viewer',max_length=20)
class RoleInput(BaseModel):
    role:str=Field(max_length=20)
@router.get('')
def listing(scope=Depends(current_scope),db=Depends(get_db)):
    return {'current':{'id':scope.fleet.id,'code':scope.fleet.code,'name':scope.fleet.name,'role':scope.role},
            'fleets':fleets.fleet_options(db,scope.user)}
@router.get('/members')
def members(scope=Depends(current_scope),db=Depends(get_db)):
    rows=fleets.list_members(db,scope.fleet_id)
    if scope.role!='admin':
        rows=[{k:v for k,v in row.items() if k!='email'} for row in rows]
    return rows
@router.post('/members',status_code=201)
def add(data:MemberInput,scope=Depends(admin_only),db=Depends(get_db)):
    membership,user=fleets.add_member(db,scope.fleet,data.email,data.name,data.password,data.role)
    record(db,scope.user.email,'fleet.member.add',
           {'membership':membership.id,'user':user.email,'role':membership.role},fleet_id=scope.fleet_id)
    db.commit()
    return next(row for row in fleets.list_members(db,scope.fleet_id) if row['membership_id']==membership.id)
@router.patch('/members/{membership_id}')
def change_role(membership_id:int,data:RoleInput,scope=Depends(admin_only),db=Depends(get_db)):
    membership=fleets.update_role(db,scope.fleet,membership_id,data.role)
    record(db,scope.user.email,'fleet.member.role',{'membership':membership.id,'role':data.role},fleet_id=scope.fleet_id)
    db.commit()
    return next(row for row in fleets.list_members(db,scope.fleet_id) if row['membership_id']==membership_id)
@router.delete('/members/{membership_id}')
def remove(membership_id:int,scope=Depends(admin_only),db=Depends(get_db)):
    membership,stopped=fleets.remove_member(db,scope.fleet,membership_id,scope.user.id)
    record(db,scope.user.email,'fleet.member.remove',
           {'membership':membership.id,'reports_disabled':stopped},fleet_id=scope.fleet_id)
    db.commit()
    return {'removed':membership.id,'reports_disabled':stopped}
