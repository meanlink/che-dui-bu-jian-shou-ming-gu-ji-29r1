import time, os, csv, io, hashlib, json
from fastapi import HTTPException
from src.models import Job, Report, Delivery
from src.config.settings import ARTIFACT_DIR
def create(db, data, scope):
    j=db.get(Job,data.job_id)
    if not j or j.fleet_id!=scope.fleet_id:
        raise HTTPException(404,'分析任务不存在')
    if j.status!='completed' or not j.approved:
        raise HTTPException(409,'请先选择已完成且获批准的分析结果')
    r=Report(fleet_id=scope.fleet_id, name=data.name, job_id=j.id, destination=data.destination,
             interval_seconds=data.interval_seconds, next_run=time.time()+data.delay_seconds,
             enabled=True, created_by=scope.user.id)
    db.add(r); db.flush()
    return r
def visible(db, report_id, fleet_id):
    r=db.get(Report,report_id)
    if not r or r.fleet_id!=fleet_id: raise HTTPException(404,'分发计划不存在')
    return r
def visible_delivery(db, delivery_id, fleet_id):
    d=db.get(Delivery,delivery_id)
    if not d or d.fleet_id!=fleet_id: raise HTTPException(404,'归档不存在')
    return d
def deliver(db, report):
    j=db.get(Job,report.job_id)
    # A report may only ever render its own fleet's approved result.
    if not j or not j.approved or j.fleet_id is None or j.fleet_id!=report.fleet_id: return
    out=io.StringIO()
    out.write('﻿')
    table=j.result.get('table',{})
    cols=table.get('columns',[])
    writer=csv.writer(out)
    def safe(v):
        if isinstance(v,(int,float)) and not isinstance(v,bool): return v
        text=str(v)
        return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
    writer.writerow([safe(c['label']) for c in cols])
    for row in table.get('rows',[]): writer.writerow([safe(row.get(c['key'],'')) for c in cols])
    data=out.getvalue().encode('utf-8')
    delivery=Delivery(fleet_id=report.fleet_id, report_id=report.id, created_at=time.time(),
                      checksum=hashlib.sha256(data).hexdigest(), filename='', destination=report.destination)
    db.add(delivery); db.flush()
    delivery.filename=f'fleet-{report.fleet_id}-report-{report.id}-delivery-{delivery.id}.csv'
    os.makedirs(ARTIFACT_DIR,exist_ok=True)
    with open(os.path.join(ARTIFACT_DIR,delivery.filename),'wb') as f:f.write(data)
    with open(os.path.join(ARTIFACT_DIR,delivery.filename+'.json'),'w') as f:
        json.dump({'fleet':report.fleet_id,'job':j.name,'params':j.params,'result':j.result,'checksum':delivery.checksum},f,ensure_ascii=False,allow_nan=False)
    report.next_run=time.time()+report.interval_seconds
    return delivery
