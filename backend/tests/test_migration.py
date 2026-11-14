"""Upgrade path: a pre-tenancy database must be sealed in place, then claimable.

Run in a subprocess so module-level DATABASE_URL/engine caches cannot leak
between tests (the tenancy suite imports the app engine eagerly).
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _create_old_schema(path):
    connection = sqlite3.connect(path)
    connection.executescript('''
        CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(150) UNIQUE, name VARCHAR(80),
                            role VARCHAR(20), password VARCHAR(300));
        CREATE TABLE datasets (id INTEGER PRIMARY KEY, name VARCHAR(160) UNIQUE, source VARCHAR(200),
                               records JSON, checksum VARCHAR(64), created_at DOUBLE);
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, name VARCHAR(160), dataset_id INTEGER,
                           params JSON, status VARCHAR(20), result JSON, error VARCHAR(1000),
                           approved BOOLEAN, created_by INTEGER, created_at DOUBLE, finished_at DOUBLE);
        CREATE TABLE reports (id INTEGER PRIMARY KEY, name VARCHAR(160), job_id INTEGER,
                              destination VARCHAR(120), interval_seconds INTEGER, next_run DOUBLE,
                              enabled BOOLEAN);
        CREATE TABLE deliveries (id INTEGER PRIMARY KEY, report_id INTEGER, created_at DOUBLE,
                                 checksum VARCHAR(64), filename VARCHAR(160), destination VARCHAR(120));
        CREATE TABLE audits (id INTEGER PRIMARY KEY, actor VARCHAR(150), action VARCHAR(80),
                             detail JSON, at DOUBLE);
        INSERT INTO users VALUES (1, 'old@demo.local', '旧负责人', 'admin', 'x');
        INSERT INTO datasets VALUES (1, '旧批次', 'old.csv', '[{"asset":"A","model":"AC-8","km":1,"failed":0}]',
                                     'abc', 100);
        INSERT INTO jobs VALUES (1, '旧分析', 1, '{"model":"AC-8"}', 'completed', '{}', '', 1, 1, 100, 101);
        INSERT INTO reports VALUES (1, '旧简报', 1, '旧收件箱', 86400, 50, 1);
        INSERT INTO deliveries VALUES (1, 1, 50, 'def', 'old.csv', '旧收件箱');
        INSERT INTO audits VALUES (1, 'old@demo.local', 'dataset.create', '{}', 100);
    ''')
    connection.commit()
    connection.close()


def test_old_database_is_upgraded_and_sealed():
    directory = tempfile.mkdtemp(prefix='fleet-legacy-')
    path = os.path.join(directory, 'legacy.db')
    _create_old_schema(path)
    script = '''
from migrations.initial import migrate
from src.config.database import Session
from src.models import Dataset, Job, Report, Delivery
from sqlalchemy import inspect
from src.config.database import engine
migrate()
migrate()
columns = {c["name"] for c in inspect(engine).get_columns("datasets")}
assert {"fleet_id", "sealed_at", "legacy_claim_id"} <= columns, columns
with Session() as db:
    rows = [db.get(Dataset, 1), db.get(Job, 1), db.get(Report, 1), db.get(Delivery, 1)]
    assert all(row.fleet_id is None for row in rows), [r.fleet_id for r in rows]
    assert all(row.sealed_at is not None for row in rows), [r.sealed_at for r in rows]
    assert db.query(Dataset).count() == 1
    assert db.query(Job).count() == 1
print("upgraded")
'''
    environment = {**os.environ, 'DATABASE_URL': 'sqlite:///' + path,
                   'ARTIFACT_DIR': os.path.join(directory, 'artifacts'), 'SEED_DEMO': 'false'}
    result = subprocess.run([sys.executable, '-c', script], cwd=BACKEND, env=environment,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'upgraded' in result.stdout
    # The legacy batch name is no longer globally unique: each fleet may add
    # its own batch with the same name.
    connection = sqlite3.connect(path)
    connection.execute("INSERT INTO fleets (code, name, owner_id, created_at) VALUES ('a','A',1,0),('b','B',1,0)")
    connection.execute("INSERT INTO datasets (fleet_id, name, source, records, checksum, created_at)"
                       " VALUES (1,'同名批次','a.json','[]','c',0),(2,'同名批次','b.json','[]','d',0)")
    connection.commit()
    assert connection.execute("SELECT COUNT(*) FROM datasets WHERE name='同名批次'").fetchone()[0] == 2
    connection.close()
