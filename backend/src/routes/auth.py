from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from src.config.database import get_db
from src.models import User
from src.utils.security import verify_password, token_for
from src.middlewares.auth import authenticated, current_scope
from src.services import fleets
from src.services.audit import record
router=APIRouter(prefix='/auth')
class Login(BaseModel):
    email:str=Field(max_length=150)
    password:str=Field(max_length=200)
    fleet_id:int|None=None
class Switch(BaseModel):
    fleet_id:int
def _session(db,user,membership):
    fleet=db.get(fleets.Fleet,membership.fleet_id)
    return {'access_token':token_for(user,membership.fleet_id,membership),
            'user':{'name':user.name,'role':membership.role,'email':user.email},
            'fleet':{'id':fleet.id,'code':fleet.code,'name':fleet.name},
            'fleets':fleets.fleet_options(db,user)}
@router.post('/login')
def login(data:Login, db=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email.strip().lower()))
    if not u or not verify_password(data.password,u.password): raise HTTPException(401,'账号或密码不正确')
    if data.fleet_id is None:
        membership=fleets.default_membership(db,u)
    else:
        membership=fleets.active_membership(db,u,data.fleet_id)
    record(db,u.email,'auth.login',{'fleet':membership.fleet_id},fleet_id=membership.fleet_id); db.commit()
    return _session(db,u,membership)
@router.get('/me')
def me(scope=Depends(current_scope),db=Depends(get_db)):
    u=scope.user
    return {'name':u.name,'role':scope.role,'email':u.email,
            'fleet':{'id':scope.fleet.id,'code':scope.fleet.code,'name':scope.fleet.name},
            'fleets':fleets.fleet_options(db,u)}
@router.post('/switch')
def switch(data:Switch,u=Depends(authenticated),db=Depends(get_db)):
    membership=fleets.active_membership(db,u,data.fleet_id)
    record(db,u.email,'auth.switch',{'fleet':data.fleet_id},fleet_id=data.fleet_id); db.commit()
    return _session(db,u,membership)
