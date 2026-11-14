"""Historical (pre-tenancy) data: sealing, owner-only review, whole-chain claim."""
import time
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.models import Dataset, Job, Report, Delivery, LegacyClaim


def _chain(db, dataset_id):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, '历史批次不存在')
    jobs = list(db.scalars(select(Job).where(Job.dataset_id == dataset.id).order_by(Job.id)))
    job_ids = [job.id for job in jobs]
    reports = list(db.scalars(select(Report).where(Report.job_id.in_(job_ids)).order_by(Report.id))) if job_ids else []
    report_ids = [report.id for report in reports]
    deliveries = (list(db.scalars(select(Delivery).where(Delivery.report_id.in_(report_ids)).order_by(Delivery.id)))
                  if report_ids else [])
    return dataset, jobs, reports, deliveries


def _rows(dataset, jobs, reports, deliveries):
    return [dataset, *jobs, *reports, *deliveries]


def summarize(db, dataset, jobs, reports, deliveries, fleet_names):
    claim = db.scalar(select(LegacyClaim).where(LegacyClaim.chain_root == dataset.id))
    return {
        'dataset_id': dataset.id,
        'name': dataset.name,
        'source': dataset.source,
        'rows': len(dataset.records or []),
        'checksum': dataset.checksum,
        'created_at': dataset.created_at,
        'sealed_at': dataset.sealed_at,
        'jobs': [{'id': job.id, 'name': job.name, 'status': job.status, 'approved': job.approved}
                 for job in jobs],
        'reports': [{'id': report.id, 'name': report.name, 'destination': report.destination,
                     'enabled': report.enabled, 'next_run': report.next_run} for report in reports],
        'deliveries': [{'id': delivery.id, 'filename': delivery.filename,
                        'destination': delivery.destination, 'created_at': delivery.created_at}
                       for delivery in deliveries],
        'counts': {'records': len(dataset.records or []), 'jobs': len(jobs),
                   'reports': len(reports), 'deliveries': len(deliveries)},
        'claim': None if claim is None else {
            'id': claim.id, 'fleet_id': claim.fleet_id,
            'fleet': fleet_names.get(claim.fleet_id, str(claim.fleet_id)),
            'claimed_by': claim.claimed_by, 'actor': claim.actor, 'claimed_at': claim.claimed_at,
        },
    }


def sealed_chains(db, fleet_names):
    """Chains not yet owned by any fleet. Read-only; visible to fleet owners only."""
    datasets = list(db.scalars(select(Dataset).where(
        Dataset.fleet_id.is_(None), Dataset.sealed_at.is_not(None)).order_by(Dataset.id.desc())))
    result = []
    for dataset in datasets:
        _, jobs, reports, deliveries = _chain(db, dataset.id)
        result.append(summarize(db, dataset, jobs, reports, deliveries, fleet_names))
    return result


def sealed_chain(db, dataset_id, fleet_names):
    dataset, jobs, reports, deliveries = _chain(db, dataset_id)
    if dataset.fleet_id is not None:
        # Already owned (by this or another fleet): not a sealed chain any more.
        raise HTTPException(404, '历史批次不存在')
    return summarize(db, dataset, jobs, reports, deliveries, fleet_names)


def _conflict(detail):
    raise HTTPException(409, detail)


def claim_chain(db, fleet, user, dataset_id):
    """Claim one complete sealed chain into the caller's fleet.

    All checks run before any write; the chain is either migrated in full or not
    at all. A successful retry by the same fleet is a no-op and never duplicates
    rows or claims.
    """
    dataset, jobs, reports, deliveries = _chain(db, dataset_id)
    rows = _rows(dataset, jobs, reports, deliveries)

    existing = db.scalar(select(LegacyClaim).where(LegacyClaim.chain_root == dataset.id))
    if existing is not None:
        if existing.fleet_id != fleet.id:
            _conflict('该历史关联链已归属其他车队，整链保持不变')
        # Same fleet retry: idempotent, no rows are touched.
        return summarize(db, dataset, jobs, reports, deliveries, {fleet.id: fleet.name}), True
    if dataset.fleet_id is not None and dataset.fleet_id != fleet.id:
        # A chain already living in another fleet is not historical data here;
        # answer as if it does not exist rather than confirming it.
        raise HTTPException(404, '历史批次不存在')

    owners = {row.fleet_id for row in rows if row.fleet_id is not None}
    if owners - {fleet.id}:
        _conflict('关联链中已有数据归属其他车队，整链保持不变')
    if owners == {fleet.id} and all(row.fleet_id == fleet.id for row in rows):
        # Rows were already migrated without a claim marker (e.g. interrupted
        # legacy import). Record the claim once so the chain is not migrated twice.
        claim_row = LegacyClaim(chain_root=dataset.id, fleet_id=fleet.id, claimed_by=user.id,
                                actor=user.email, claimed_at=time.time(),
                                records=len(dataset.records or []), jobs=len(jobs),
                                reports=len(reports), deliveries=len(deliveries))
        db.add(claim_row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            _conflict('该历史关联链已被其他负责人认领，整链保持不变')
        return summarize(db, dataset, jobs, reports, deliveries, {fleet.id: fleet.name}), True

    if db.scalar(select(Dataset).where(Dataset.fleet_id == fleet.id, Dataset.name == dataset.name,
                                       Dataset.id != dataset.id)):
        _conflict('目标车队已有同名数据批次，整链保持不变')

    claim_row = LegacyClaim(chain_root=dataset.id, fleet_id=fleet.id, claimed_by=user.id,
                            actor=user.email, claimed_at=time.time(),
                            records=len(dataset.records or []), jobs=len(jobs),
                            reports=len(reports), deliveries=len(deliveries))
    db.add(claim_row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        _conflict('该历史关联链已被其他负责人认领，整链保持不变')

    for row in rows:
        if row.fleet_id is not None and row.fleet_id != fleet.id:
            db.rollback()
            _conflict('关联链中已有数据归属其他车队，整链保持不变')
        row.fleet_id = fleet.id
        row.legacy_claim_id = claim_row.id
        # Claiming lifts the park: the chain becomes ordinary fleet data.
        row.sealed_at = None
        if isinstance(row, Report) and row.next_run <= time.time():
            # A long-sealed schedule must not fire a backlog the moment it is
            # claimed; the next delivery happens one interval from now.
            row.next_run = time.time() + row.interval_seconds
    try:
        db.flush()
    except IntegrityError:
        # A concurrent claim or a name collision rolled back the whole chain.
        db.rollback()
        _conflict('认领冲突，整条关联链保持不变')
    return summarize(db, dataset, jobs, reports, deliveries, {fleet.id: fleet.name}), False
