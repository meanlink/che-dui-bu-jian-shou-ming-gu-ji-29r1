"""Fleet-isolation acceptance checks. Run from backend/ with:
    DATABASE_URL=sqlite:////tmp/tenancy-test.db python -m pytest tests -q
The test module configures its own throw-away database before importing the app.
"""
import os
import tempfile

DB_PATH = os.path.join(tempfile.mkdtemp(prefix='fleet-tenancy-'), 'test.db')
os.environ['DATABASE_URL'] = 'sqlite:///' + DB_PATH
os.environ['ARTIFACT_DIR'] = tempfile.mkdtemp(prefix='fleet-artifacts-')
os.environ['SEED_DEMO'] = 'false'

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from migrations.initial import migrate  # noqa: E402
from scripts.seed_demo import seed  # noqa: E402
from src.main import app  # noqa: E402
from src.config.database import Session  # noqa: E402
from src.models import Dataset, Delivery, Fleet, FleetMember, Job, Report  # noqa: E402


@pytest.fixture(scope='session', autouse=True)
def database():
    migrate()
    seed()


@pytest.fixture(scope='session')
def client():
    with TestClient(app) as c:
        yield c


def login(client, email, fleet_id=None):
    body = {'email': email, 'password': 'Demo123!'}
    if fleet_id is not None:
        body['fleet_id'] = fleet_id
    response = client.post('/auth/login', json=body)
    assert response.status_code == 200, response.text
    return response.json()


def auth(token):
    return {'Authorization': 'Bearer ' + token}


def fleets(db):
    return {fleet.code: fleet for fleet in db.query(Fleet).all()}


def test_login_returns_fleet_context_and_switch(client):
    session = login(client, 'admin@demo.local')
    assert session['fleet']['code'] == 'luwan'
    assert {f['code'] for f in session['fleets']} == {'luwan', 'qingyu'}
    with Session() as db:
        target = fleets(db)['qingyu'].id
    switched = client.post('/auth/switch', json={'fleet_id': target}, headers=auth(session['access_token']))
    assert switched.status_code == 200
    assert switched.json()['fleet']['code'] == 'qingyu'
    assert switched.json()['user']['role'] == 'admin'
    # Switching back is offered by the same endpoint.
    back = client.post('/auth/switch', json={'fleet_id': session['fleet']['id']},
                       headers=auth(session['access_token']))
    assert back.status_code == 200 and back.json()['fleet']['code'] == 'luwan'


def test_fleet_lists_are_isolated_and_foreign_ids_are_invisible(client):
    luwan = login(client, 'admin@demo.local')
    qingyu = login(client, 'owner@qingyu.local')
    with Session() as db:
        luwan_ids = {d.id for d in db.query(Dataset).filter(Dataset.fleet_id == luwan['fleet']['id'])}
        qingyu_ids = {d.id for d in db.query(Dataset).filter(Dataset.fleet_id == qingyu['fleet']['id'])}
        assert luwan_ids and qingyu_ids and not (luwan_ids & qingyu_ids)
        foreign_job = db.query(Job).filter(Job.fleet_id == qingyu['fleet']['id']).first().id
        foreign_report = db.query(Report).filter(Report.fleet_id == qingyu['fleet']['id']).first().id
        foreign_delivery = db.query(Delivery).filter(Delivery.fleet_id == qingyu['fleet']['id']).first().id

    luwan_datasets = client.get('/datasets', headers=auth(luwan['access_token'])).json()
    assert {d['id'] for d in luwan_datasets} == luwan_ids
    qingyu_datasets = client.get('/datasets', headers=auth(qingyu['access_token'])).json()
    assert {d['id'] for d in qingyu_datasets} == qingyu_ids

    # Direct id access across fleets is refused and indistinguishable from missing.
    assert client.get(f'/datasets/{next(iter(qingyu_ids))}', headers=auth(luwan['access_token'])).status_code == 404
    assert client.get(f'/jobs/{foreign_job}', headers=auth(luwan['access_token'])).status_code == 404
    assert client.post(f'/jobs/{foreign_job}/approve', headers=auth(luwan['access_token'])).status_code == 404
    assert client.post(f'/reports/{foreign_report}/toggle', headers=auth(luwan['access_token'])).status_code == 404
    assert client.get(f'/deliveries/{foreign_delivery}/download?format=csv',
                      headers=auth(luwan['access_token'])).status_code == 404
    assert client.get(f'/deliveries/{foreign_delivery}/download?format=json',
                      headers=auth(luwan['access_token'])).status_code == 404
    deliveries = client.get('/deliveries', headers=auth(luwan['access_token'])).json()
    assert deliveries and all(d['id'] != foreign_delivery for d in deliveries)
    assert client.get('/overview', headers=auth(luwan['access_token'])).json()['datasets'] == len(luwan_ids)


def test_cross_fleet_references_are_rejected(client):
    luwan = login(client, 'admin@demo.local')
    with Session() as db:
        foreign_dataset = db.query(Dataset).filter(Dataset.fleet_id != luwan['fleet']['id'],
                                                   Dataset.fleet_id.is_not(None)).first()
        foreign_job = db.query(Job).filter(Job.fleet_id != luwan['fleet']['id'],
                                           Job.fleet_id.is_not(None),
                                           Job.fleet_id.is_not(None)).first()
        foreign_delivery = db.query(Delivery).filter(Delivery.fleet_id != luwan['fleet']['id'],
                                                     Delivery.fleet_id.is_not(None)).first()
    response = client.post('/jobs', json={'name': '越队任务', 'dataset_id': foreign_dataset.id, 'params': {}},
                           headers=auth(luwan['access_token']))
    assert response.status_code == 404
    response = client.post('/reports', json={'name': '越队简报', 'job_id': foreign_job.id},
                           headers=auth(luwan['access_token']))
    assert response.status_code == 404
    assert client.get(f'/deliveries/{foreign_delivery.id}/download?format=json',
                      headers=auth(luwan['access_token'])).status_code == 404


def test_roles_remain_enforced_per_fleet(client):
    analyst = login(client, 'analyst@demo.local')
    viewer = login(client, 'viewer@demo.local')
    payload = {'name': '查看员越权批次', 'source': 'x.json',
               'records': [{'asset': f'A-{i}', 'model': 'AC-8', 'km': 1000 + i, 'failed': 0} for i in range(5)]}
    assert client.post('/datasets', json=payload, headers=auth(viewer['access_token'])).status_code == 403
    assert client.post('/datasets', json=payload, headers=auth(analyst['access_token'])).status_code == 201
    with Session() as db:
        job = db.query(Job).filter(Job.fleet_id == analyst['fleet']['id']).first()
    assert client.post(f'/jobs/{job.id}/approve', headers=auth(analyst['access_token'])).status_code == 403
    # Fleet ownership is admin-only, in both read and write directions.
    assert client.get('/fleets/members', headers=auth(analyst['access_token'])).status_code == 200
    assert client.get('/legacy/chains', headers=auth(analyst['access_token'])).status_code == 403
    assert client.post('/fleets/members', json={'email': 'new@x.local', 'password': 'Password1'},
                       headers=auth(analyst['access_token'])).status_code == 403


def test_removed_member_token_dies_and_pending_reports_stop(client):
    owner = login(client, 'owner@qingyu.local')
    analyst = login(client, 'analyst@qingyu.local')
    with Session() as db:
        from src.models import User
        fleet_id = owner['fleet']['id']
        analyst_user = db.query(User).filter(User.email == 'analyst@qingyu.local').first()
        admin_user = db.query(User).filter(User.email == 'owner@qingyu.local').first()
        analyst_membership = db.query(FleetMember).filter(FleetMember.user_id == analyst_user.id,
                                                          FleetMember.fleet_id == fleet_id).first()
        job = db.query(Job).filter(Job.fleet_id == fleet_id, Job.approved == True).first()  # noqa: E712
        assert job is not None
        # Give the analyst their own pending schedule so removal has something to stop.
        pending = Report(fleet_id=fleet_id, name='分析员待发简报', job_id=job.id, destination='临时收件箱',
                         interval_seconds=86400, next_run=0, enabled=True, created_by=analyst_user.id)
        db.add(pending)
        db.commit()
        pending_id = pending.id
        analyst_membership_id = analyst_membership.id
        admin_membership_id = db.query(FleetMember).filter(
            FleetMember.fleet_id == fleet_id, FleetMember.user_id == admin_user.id).first().id

    # Administrator of the same fleet removes the analyst.
    response = client.delete(f'/fleets/members/{analyst_membership_id}', headers=auth(owner['access_token']))
    assert response.status_code == 200 and response.json()['reports_disabled'] >= 1
    # Old analyst token is dead immediately, even though it has not expired.
    assert client.get('/datasets', headers=auth(analyst['access_token'])).status_code == 401
    assert client.get('/auth/me', headers=auth(analyst['access_token'])).status_code == 401
    with Session() as db:
        assert db.get(Report, pending_id).enabled is False
        # Other fleets' schedules are untouched.
        assert all(r.enabled for r in db.query(Report).filter(Report.fleet_id != fleet_id,
                                                              Report.created_by.is_not(None)))
    # The owner cannot remove themselves or the fleet owner.
    assert client.delete(f'/fleets/members/{admin_membership_id}', headers=auth(owner['access_token'])).status_code == 409
    # Re-adding restores access only through a fresh login.
    response = client.post('/fleets/members', json={'email': 'analyst@qingyu.local', 'role': 'analyst'},
                           headers=auth(owner['access_token']))
    assert response.status_code == 201
    assert client.get('/datasets', headers=auth(analyst['access_token'])).status_code == 401
    fresh = login(client, 'analyst@qingyu.local')
    assert client.get('/datasets', headers=auth(fresh['access_token'])).status_code == 200


def test_legacy_chain_is_sealed_owner_only_and_claim_is_whole_and_idempotent(client):
    owner = login(client, 'admin@demo.local')
    chains = client.get('/legacy/chains', headers=auth(owner['access_token'])).json()
    assert len(chains) == 1
    chain = chains[0]
    assert chain['claim'] is None
    assert chain['counts'] == {'records': 200, 'jobs': 1, 'reports': 1, 'deliveries': 1}
    # Sealed data is absent from ordinary fleet lists before claiming.
    luwan_datasets = {d['id'] for d in client.get('/datasets', headers=auth(owner['access_token'])).json()}
    assert chain['dataset_id'] not in luwan_datasets

    # A same-name batch in the target fleet would collide; prove the whole chain
    # stays untouched when the claim conflicts.
    with Session() as db:
        fleet = fleets(db)['luwan']
        db.add(Dataset(fleet_id=fleet.id, name=chain['name'], source='collision.json', records=[],
                       checksum='0' * 64, created_at=0))
        db.commit()
    conflict = client.post(f"/legacy/chains/{chain['dataset_id']}/claim", headers=auth(owner['access_token']))
    assert conflict.status_code == 409
    with Session() as db:
        assert db.get(Dataset, chain['dataset_id']).fleet_id is None
        assert db.query(Job).filter(Job.dataset_id == chain['dataset_id']).one().fleet_id is None
    with Session() as db:
        db.query(Dataset).filter(Dataset.fleet_id == fleet.id, Dataset.name == chain['name']).delete()
        db.commit()

    claimed = client.post(f"/legacy/chains/{chain['dataset_id']}/claim", headers=auth(owner['access_token']))
    assert claimed.status_code == 200 and claimed.json()['duplicate'] is False
    assert claimed.json()['claim']['fleet_id'] == owner['fleet']['id']
    # Whole chain moved together.
    with Session() as db:
        dataset = db.get(Dataset, chain['dataset_id'])
        assert dataset.fleet_id == owner['fleet']['id']
        for job in db.query(Job).filter(Job.dataset_id == dataset.id):
            assert job.fleet_id == owner['fleet']['id']
            for report in db.query(Report).filter(Report.job_id == job.id):
                assert report.fleet_id == owner['fleet']['id']
                assert all(d.fleet_id == owner['fleet']['id']
                           for d in db.query(Delivery).filter(Delivery.report_id == report.id))
    assert client.get('/legacy/chains', headers=auth(owner['access_token'])).json() == []
    assert chain['dataset_id'] in {d['id'] for d in client.get('/datasets', headers=auth(owner['access_token'])).json()}

    # Retrying the claim does not re-migrate or duplicate anything.
    again = client.post(f"/legacy/chains/{chain['dataset_id']}/claim", headers=auth(owner['access_token']))
    assert again.status_code == 200 and again.json()['duplicate'] is True
    with Session() as db:
        assert db.query(Job).filter(Job.dataset_id == chain['dataset_id']).count() == 1
        assert db.query(Report).join(Job, Report.job_id == Job.id).filter(
            Job.dataset_id == chain['dataset_id']).count() == 1

    # Another fleet's owner cannot claim an already-owned chain; nothing changes.
    other = login(client, 'owner@qingyu.local')
    blocked = client.post(f"/legacy/chains/{chain['dataset_id']}/claim", headers=auth(other['access_token']))
    assert blocked.status_code == 409
    with Session() as db:
        assert db.get(Dataset, chain['dataset_id']).fleet_id == owner['fleet']['id']


def test_worker_authorization_is_fleet_scoped():
    """The worker only computes when job and dataset share a fleet."""
    with Session() as db:
        fleet = fleets(db)['qingyu']
        dataset = db.query(Dataset).filter(Dataset.fleet_id == fleet.id).first()
        job = Job(fleet_id=fleet.id, name='越队计算', dataset_id=dataset.id, params={}, status='queued',
                  created_by=fleet.owner_id, created_at=0)
        db.add(job)
        db.commit()
        job_id = job.id
        # Simulate a tampered link: point the job at another fleet's dataset.
        other = db.query(Dataset).filter(Dataset.fleet_id != fleet.id, Dataset.fleet_id.is_not(None)).first()
        job.dataset_id = other.id
        db.commit()
    from src.worker import execute
    execute(job_id)
    with Session() as db:
        assert db.get(Job, job_id).status == 'failed'
        assert '禁止跨队计算' in db.get(Job, job_id).error


def test_audits_are_fleet_scoped(client):
    luwan = login(client, 'admin@demo.local')
    qingyu = login(client, 'owner@qingyu.local')
    luwan_actions = client.get('/audits', headers=auth(luwan['access_token'])).json()
    qingyu_actions = client.get('/audits', headers=auth(qingyu['access_token'])).json()
    assert luwan_actions and all(a['id'] != b['id'] for a in luwan_actions for b in qingyu_actions)
