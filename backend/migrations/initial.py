"""Schema evolution for fleet tenancy.

Fresh databases are created directly from the models. Existing (pre-tenancy)
databases are upgraded in place: fleet/claim columns are added, the old global
dataset-name uniqueness is replaced by per-fleet uniqueness, and every row that
has no fleet yet is sealed. Sealing is the precondition for owner-only historical
claims: sealed rows are visible to the owner in the claim view only and are
never mutated by normal business APIs.
"""
import time
import logging
from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models  # noqa: F401  (register mappings)

LEGACY_TABLES = ('datasets', 'jobs', 'reports', 'deliveries', 'audits')
ADDED_COLUMNS = {
    'datasets': [('fleet_id', 'INTEGER'), ('sealed_at', 'DOUBLE'), ('legacy_claim_id', 'INTEGER')],
    'jobs': [('fleet_id', 'INTEGER'), ('sealed_at', 'DOUBLE'), ('legacy_claim_id', 'INTEGER')],
    'reports': [('fleet_id', 'INTEGER'), ('sealed_at', 'DOUBLE'), ('legacy_claim_id', 'INTEGER'), ('created_by', 'INTEGER')],
    'deliveries': [('fleet_id', 'INTEGER'), ('sealed_at', 'DOUBLE'), ('legacy_claim_id', 'INTEGER')],
    'audits': [('fleet_id', 'INTEGER')],
}


def _add_column(table, column, sql_type):
    dialect = engine.dialect.name
    ddl = f'ALTER TABLE {table} ADD COLUMN {column} {sql_type}'
    try:
        with engine.begin() as connection:
            connection.execute(text(ddl))
        return True
    except Exception:
        if dialect == 'sqlite':
            # SQLite only accepts one added column per statement but this is
            # already one column; a genuine failure should surface.
            raise
        logging.warning('Could not add %s.%s (may already exist)', table, column)
        return False


def upgrade_schema():
    inspector = inspect(engine)
    for table, columns in ADDED_COLUMNS.items():
        if table not in inspector.get_table_names():
            continue
        existing = {column['name'] for column in inspector.get_columns(table)}
        for name, sql_type in columns:
            if name not in existing:
                _add_column(table, name, sql_type)
    _relax_global_dataset_name_uniqueness()


def _relax_global_dataset_name_uniqueness():
    """Legacy DBs had a global UNIQUE(name). Fleet-scoped batches need (fleet_id, name)."""
    inspector = inspect(engine)
    if 'datasets' not in inspector.get_table_names():
        return
    if engine.dialect.name == 'postgresql':
        constraints = inspector.get_unique_constraints('datasets')
        indexes = inspector.get_indexes('datasets')
        with engine.begin() as connection:
            for constraint in constraints:
                if constraint.get('column_names') == ['name']:
                    connection.execute(text(f'ALTER TABLE datasets DROP CONSTRAINT IF EXISTS {constraint["name"]}'))
            for index in indexes:
                if index.get('unique') and index.get('column_names') == ['name']:
                    connection.execute(text(f'DROP INDEX IF EXISTS {index["name"]}'))
            # Existing tables are not touched by create_all, so add the
            # fleet-scoped uniqueness explicitly. NULL fleets stay distinct,
            # which keeps several sealed chains with the same name possible.
            connection.execute(text(
                'CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_fleet_name '
                'ON datasets (fleet_id, name)'))
    elif engine.dialect.name == 'sqlite':
        # SQLite cannot drop an inline UNIQUE constraint; recreate the table with
        # the fleet-scoped constraint instead of the global one.
        with engine.begin() as connection:
            sql = connection.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='datasets'"
            )).scalar() or ''
            if 'name VARCHAR(160) UNIQUE' not in sql:
                return
            # Keep other tables' foreign keys pointing at the recreated name.
            connection.execute(text('PRAGMA legacy_alter_table=ON'))
            connection.execute(text('ALTER TABLE datasets RENAME TO datasets_legacy_unique'))
            Base.metadata.tables['datasets'].create(connection)
            columns = [column['name'] for column in inspect(engine).get_columns('datasets_legacy_unique')]
            connection.execute(text(
                f'INSERT INTO datasets ({", ".join(columns)}) SELECT {", ".join(columns)} FROM datasets_legacy_unique'
            ))
            connection.execute(text('DROP TABLE datasets_legacy_unique'))


def seal_legacy_rows():
    """Seal anything not yet assigned to a fleet. Idempotent and run before claim."""
    now = time.time()
    with engine.begin() as connection:
        for table in LEGACY_TABLES:
            column = 'sealed_at' if table != 'audits' else 'fleet_id'
            if column == 'sealed_at':
                statement = f'UPDATE {table} SET sealed_at=:now WHERE fleet_id IS NULL AND sealed_at IS NULL'
            else:
                # Audits carry no seal marker; only their fleet link is relevant.
                continue
            result = connection.execute(text(statement), {'now': now})
            if result.rowcount:
                logging.info('Sealed %s legacy %s rows', result.rowcount, table)


def migrate():
    upgrade_schema()
    Base.metadata.create_all(engine)
    upgrade_schema()
    seal_legacy_rows()


if __name__ == '__main__':
    migrate()
