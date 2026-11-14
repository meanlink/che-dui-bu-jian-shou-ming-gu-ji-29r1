from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.config.database import get_db
from src.models import User, Fleet, FleetMember
from src.utils.security import decode_token

bearer = HTTPBearer(auto_error=False)


def _user_from_token(token, db):
    if token is None:
        raise ValueError('missing token')
    payload = decode_token(token.credentials)
    user = db.get(User, int(payload['sub']))
    if user is None:
        raise ValueError('missing user')
    return user, payload


def authenticated(token: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    """Any signed-in user, independent of fleet context (used by login/fleet picker)."""
    try:
        user, _ = _user_from_token(token, db)
        return user
    except Exception:
        raise HTTPException(401, '登录已过期，请重新登录')


@dataclass(frozen=True)
class Scope:
    user: User
    fleet: Fleet
    membership: FleetMember

    @property
    def fleet_id(self) -> int:
        return self.fleet.id

    @property
    def role(self) -> str:
        return self.membership.role


def current_scope(token: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(get_db)):
    """Fleet-bound request context.

    The token names a membership and its epoch. Every request re-reads the
    membership, so revoking a member (or removing them) invalidates outstanding
    tokens immediately, even before they expire.
    """
    try:
        user, payload = _user_from_token(token, db)
        fleet_id = int(payload['fleet'])
        membership = db.get(FleetMember, int(payload['mem']))
        if (membership is None or membership.user_id != user.id or membership.fleet_id != fleet_id
                or membership.revoked_at is not None or membership.epoch != int(payload.get('epoch', -1))):
            raise ValueError('revoked membership')
        fleet = db.get(Fleet, fleet_id)
        if fleet is None:
            raise ValueError('missing fleet')
        return Scope(user=user, fleet=fleet, membership=membership)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, '登录已过期，请重新登录')


def can_write(scope: Scope = Depends(current_scope)):
    if scope.role not in ('admin', 'analyst'):
        raise HTTPException(403, '观察员只有读取权限')
    return scope


def admin_only(scope: Scope = Depends(current_scope)):
    if scope.role != 'admin':
        raise HTTPException(403, '需要业务负责人批准')
    return scope
