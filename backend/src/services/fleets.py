import time
from fastapi import HTTPException
from sqlalchemy import select, update
from src.models import Fleet, FleetMember, Report, User
from src.constants.enums import Role
from src.utils.security import hash_password

ROLE_VALUES = {role.value for role in Role}


def memberships(db, user):
    return list(db.scalars(
        select(FleetMember).where(FleetMember.user_id == user.id, FleetMember.revoked_at.is_(None))
        .order_by(FleetMember.fleet_id)
    ))


def fleet_options(db, user):
    result = []
    for membership in memberships(db, user):
        fleet = db.get(Fleet, membership.fleet_id)
        if fleet is None:
            continue
        result.append({'id': fleet.id, 'code': fleet.code, 'name': fleet.name, 'role': membership.role,
                       'membership_id': membership.id})
    return result


def default_membership(db, user):
    options = memberships(db, user)
    if not options:
        raise HTTPException(403, '该账号尚未加入任何车队，请联系业务负责人')
    return options[0]


def active_membership(db, user, fleet_id):
    membership = db.scalar(select(FleetMember).where(
        FleetMember.user_id == user.id, FleetMember.fleet_id == fleet_id, FleetMember.revoked_at.is_(None)))
    if membership is None:
        raise HTTPException(403, '该账号不属于此车队')
    return membership


def ensure_fleet(db, code, name, owner_id):
    fleet = db.scalar(select(Fleet).where(Fleet.code == code))
    if fleet is None:
        fleet = Fleet(code=code, name=name, owner_id=owner_id, created_at=time.time())
        db.add(fleet)
        db.flush()
    return fleet


def ensure_membership(db, fleet, user, role):
    membership = db.scalar(select(FleetMember).where(
        FleetMember.fleet_id == fleet.id, FleetMember.user_id == user.id))
    if membership is None:
        membership = FleetMember(fleet_id=fleet.id, user_id=user.id, role=role, created_at=time.time(), epoch=0)
        db.add(membership)
        db.flush()
    elif membership.revoked_at is not None:
        membership.revoked_at = None
        membership.role = role
        membership.epoch += 1
    return membership


def list_members(db, fleet_id):
    rows = []
    for membership in db.scalars(select(FleetMember).where(
            FleetMember.fleet_id == fleet_id, FleetMember.revoked_at.is_(None)).order_by(FleetMember.id)):
        user = db.get(User, membership.user_id)
        if user is None:
            continue
        rows.append({'membership_id': membership.id, 'user_id': user.id, 'name': user.name,
                     'email': user.email, 'role': membership.role, 'created_at': membership.created_at})
    return rows


def add_member(db, fleet, email, name, password, role):
    if role not in ROLE_VALUES:
        raise HTTPException(422, '角色只能是 admin、analyst 或 viewer')
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        if not password or len(password) < 8:
            raise HTTPException(422, '新成员需设置至少 8 位初始密码')
        user = User(email=email, name=(name or email.split('@')[0])[:80], role=role, password=hash_password(password))
        db.add(user)
        db.flush()
    else:
        existing = db.scalar(select(FleetMember).where(
            FleetMember.fleet_id == fleet.id, FleetMember.user_id == user.id, FleetMember.revoked_at.is_(None)))
        if existing is not None:
            raise HTTPException(409, '该账号已是本车队成员')
    membership = ensure_membership(db, fleet, user, role)
    return membership, user


def update_role(db, fleet, membership_id, role):
    if role not in ROLE_VALUES:
        raise HTTPException(422, '角色只能是 admin、analyst 或 viewer')
    membership = db.scalar(select(FleetMember).where(
        FleetMember.fleet_id == fleet.id, FleetMember.id == membership_id, FleetMember.revoked_at.is_(None)))
    if membership is None:
        raise HTTPException(404, '成员不存在')
    if membership.user_id == fleet.owner_id and role != Role.admin.value:
        raise HTTPException(409, '车队负责人必须保留负责人角色')
    membership.role = role
    return membership


def remove_member(db, fleet, membership_id, actor_user_id):
    membership = db.scalar(select(FleetMember).where(
        FleetMember.fleet_id == fleet.id, FleetMember.id == membership_id, FleetMember.revoked_at.is_(None)))
    if membership is None:
        raise HTTPException(404, '成员不存在')
    if membership.user_id == fleet.owner_id:
        raise HTTPException(409, '不能移出车队负责人')
    if membership.user_id == actor_user_id:
        raise HTTPException(409, '不能移出当前登录账号')
    membership.revoked_at = time.time()
    membership.epoch += 1
    stopped = db.execute(update(Report).where(
        Report.fleet_id == fleet.id, Report.created_by == membership.user_id,
        Report.enabled.is_(True), Report.sealed_at.is_(None)).values(enabled=False))
    return membership, stopped.rowcount or 0
