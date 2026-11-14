import time, json
from sqlalchemy import select, func
from src.config.database import Session
from migrations.initial import migrate, seal_legacy_rows
from src.models import User, Dataset, Job, Report, Delivery, Audit, Fleet, FleetMember
from src.services.business import metadata, seed_records, analyze
from src.services.reports import deliver
from src.utils.security import hash_password
from src.utils.serialization import checksum


def _user(db, email, name, role):
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, name=name, role=role, password=hash_password('Demo123!'))
        db.add(user)
        db.flush()
    return user


def _fleet(db, code, name, owner):
    fleet = db.scalar(select(Fleet).where(Fleet.code == code))
    if not fleet:
        fleet = Fleet(code=code, name=name, owner_id=owner.id, created_at=time.time())
        db.add(fleet)
        db.flush()
    return fleet


def _member(db, fleet, user, role):
    membership = db.scalar(select(FleetMember).where(
        FleetMember.fleet_id == fleet.id, FleetMember.user_id == user.id))
    if not membership:
        db.add(FleetMember(fleet_id=fleet.id, user_id=user.id, role=role, created_at=time.time(), epoch=0))
        db.flush()


def _seed_fleet_data(db, fleet, owner, suffix, approved):
    m = metadata()
    rows = seed_records()
    dataset = db.scalar(select(Dataset).where(Dataset.fleet_id == fleet.id, Dataset.name == m['dataset_name']))
    if not dataset:
        dataset = Dataset(fleet_id=fleet.id, name=m['dataset_name'], source=m['short'] + suffix,
                          records=rows, checksum=checksum(rows), created_at=time.time())
        db.add(dataset)
        db.flush()
    job_name = ('基线复核 · ' if approved else '车队试算 · ') + m['name'] + suffix
    job = db.scalar(select(Job).where(Job.fleet_id == fleet.id, Job.name == job_name))
    if not job:
        params = {p['key']: p['default'] for p in m.get('parameters', [])}
        result = analyze(dataset.records, params)
        json.dumps(result, ensure_ascii=False, allow_nan=False)
        job = Job(fleet_id=fleet.id, name=job_name, dataset_id=dataset.id, params=params,
                  status='completed', result=result, created_by=owner.id,
                  created_at=time.time() - 3600, finished_at=time.time() - 3595, approved=approved)
        db.add(job)
        db.flush()
        report_name = ('每日业务复核简报' if approved else '车队试算简报') + suffix
        report = Report(fleet_id=fleet.id, name=report_name, job_id=job.id,
                        destination='业务复核组 · 本地收件箱', interval_seconds=86400,
                        next_run=time.time() + 86400, enabled=True, created_by=owner.id)
        db.add(report)
        db.flush()
        deliver(db, report)
    return dataset


def _seed_sealed_chain(db, owner):
    """An unowned pre-tenancy chain parked for the owner-only claim page."""
    m = metadata()
    name = '历史归档_压缩机寿命与在役截止.csv'
    if db.scalar(select(Dataset).where(Dataset.name == name)):
        return
    rows = seed_records()
    sealed_at = time.time() - 30 * 86400
    dataset = Dataset(fleet_id=None, name=name, source='历史导出-2025.csv', records=rows,
                      checksum=checksum(rows), created_at=sealed_at, sealed_at=sealed_at)
    db.add(dataset)
    db.flush()
    params = {p['key']: p['default'] for p in m.get('parameters', [])}
    result = analyze(dataset.records, params)
    job = Job(fleet_id=None, name='历史基线 · ' + m['name'], dataset_id=dataset.id, params=params,
              status='completed', result=result, created_by=owner.id, created_at=sealed_at,
              finished_at=sealed_at, approved=True, sealed_at=sealed_at)
    db.add(job)
    db.flush()
    report = Report(fleet_id=None, name='历史每日简报', job_id=job.id, destination='历史业务复核组',
                    interval_seconds=86400, next_run=sealed_at, enabled=True, sealed_at=sealed_at)
    db.add(report)
    db.flush()
    delivery = Delivery(fleet_id=None, report_id=report.id, created_at=sealed_at,
                        checksum=checksum(result), filename='legacy-report-archive.csv',
                        destination='历史业务复核组', sealed_at=sealed_at)
    db.add(delivery)


def seed():
    migrate()
    seal_legacy_rows()
    with Session() as db:
        admin = _user(db, 'admin@demo.local', '林知 · 业务负责人', 'admin')
        analyst = _user(db, 'analyst@demo.local', '陈舟 · 分析员', 'analyst')
        viewer = _user(db, 'viewer@demo.local', '周禾 · 观察员', 'viewer')
        fleet = _fleet(db, 'luwan', '鹭湾公交机务组', admin)
        _member(db, fleet, admin, 'admin')
        _member(db, fleet, analyst, 'analyst')
        _member(db, fleet, viewer, 'viewer')
        _seed_fleet_data(db, fleet, admin, '-202611.csv', approved=True)

        second_owner = _user(db, 'owner@qingyu.local', '顾岚 · 青屿负责人', 'admin')
        second_analyst = _user(db, 'analyst@qingyu.local', '方至 · 青屿分析员', 'analyst')
        second = _fleet(db, 'qingyu', '青屿客运机务组', second_owner)
        _member(db, second, second_owner, 'admin')
        _member(db, second, second_analyst, 'analyst')
        _member(db, second, admin, 'admin')
        _seed_fleet_data(db, second, second_owner, '-青屿副本.csv', approved=True)

        _seed_sealed_chain(db, admin)
        db.add(Audit(actor='seed', action='demo.baseline', detail={'fleets': [fleet.id, second.id]},
                     at=time.time(), fleet_id=fleet.id))
        db.commit()
        counts = {model.__tablename__: db.scalar(select(func.count()).select_from(model))
                  for model in [User, Fleet, FleetMember, Dataset, Job, Report, Delivery, Audit]}
        print(json.dumps(counts, ensure_ascii=False))
        return counts


if __name__ == '__main__':
    seed()
