"""Optional standalone API. Files exist only in a temporary directory during audits.

The hosted Sites edition does not call this API. Deploy behind HTTPS. Configure
DATABASE_URL, KPI_ENCRYPTION_KEY and KPI_USERS_JSON before starting.
"""
import asyncio, hashlib, hmac, json, os, pathlib, subprocess, tempfile, uuid, zipfile
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from cryptography.fernet import Fernet
import psycopg
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from inspect_workbooks import extract

app=FastAPI(title='KPI Audit Engine',version='1.0.0',docs_url=None,redoc_url=None)
GATE=asyncio.Semaphore(2)
MAX_BYTES=20*1024*1024

def connection():
    return psycopg.connect(os.environ['DATABASE_URL'])

def encryption():
    return Fernet(os.environ['KPI_ENCRYPTION_KEY'].encode())

def user(authorization: Annotated[str|None,Header()]=None):
    if not authorization or not authorization.startswith('Bearer '):raise HTTPException(401,'Bearer token required')
    digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
    for u in json.loads(os.environ.get('KPI_USERS_JSON','[]')):
        if hmac.compare_digest(digest,u.get('token_sha256','')):return u
    raise HTTPException(401,'Invalid credentials')

def admin(u=Depends(user)):
    if u.get('role')!='admin':raise HTTPException(403,'Administrator role required')
    return u

def allowed(u,company):
    return u.get('role')=='admin' or company in u.get('companies',[])

def initialize():
    encryption()
    if not json.loads(os.environ.get('KPI_USERS_JSON','[]')):raise RuntimeError('Configure KPI_USERS_JSON; anonymous access is not supported')
    with connection() as c:
        c.execute('CREATE TABLE IF NOT EXISTS audits (id UUID PRIMARY KEY, owner_id TEXT NOT NULL, company TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL, expires_at TIMESTAMPTZ NOT NULL, ciphertext BYTEA NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS rulebooks (id INTEGER PRIMARY KEY CHECK (id=1), updated_at TIMESTAMPTZ NOT NULL, ciphertext BYTEA NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS audit_events (id UUID PRIMARY KEY, user_id TEXT NOT NULL, action TEXT NOT NULL, object_id TEXT, at TIMESTAMPTZ NOT NULL)')

@app.on_event('startup')
def startup():initialize()

def log(c,u,action,object_id=None):
    c.execute('INSERT INTO audit_events VALUES (%s,%s,%s,%s,%s)',(uuid.uuid4(),u['id'],action,object_id,datetime.now(timezone.utc)))

def purge(c):
    c.execute('DELETE FROM audits WHERE expires_at < NOW()')
    c.execute("DELETE FROM audit_events WHERE at < NOW() - INTERVAL '365 days'")

def validate_archive(path):
    try:
        with zipfile.ZipFile(path) as z:
            info=z.infolist()
            if len(info)>5000 or sum(i.file_size for i in info)>100*1024*1024 or any(i.file_size>40*1024*1024 for i in info):raise ValueError('Expanded archive limit exceeded')
            if 'xl/workbook.xml' not in z.namelist():raise ValueError('Missing workbook XML')
            if any(i.flag_bits & 1 for i in info):raise ValueError('Encrypted archives are unsupported')
    except (zipfile.BadZipFile,ValueError) as e:raise HTTPException(400,str(e))

def run_audit(paths,settings):
    # Isolated subprocess parses uploaded files; timeout bounds CPU use.
    with tempfile.TemporaryDirectory(prefix='kpi-parsed-') as tmp:
        job=pathlib.Path(tmp)/'job.json'
        job.write_text(json.dumps({'paths':[str(x) for x in paths],'settings':settings}))
        result=subprocess.run([sys.executable,str(ROOT/'api'/'worker.py'),str(job)],capture_output=True,text=True,timeout=90)
        if result.returncode:raise HTTPException(422,'Workbook parsing or validation failed. Check its structure and supported format.')
        return json.loads(result.stdout)

@app.get('/api/health')
def health():return {'status':'ok','version':'1.0.0'}

@app.post('/api/audits')
async def create_audit(files:Annotated[list[UploadFile],File()],u=Depends(user)):
    if u.get('role') not in ('admin','auditor'):raise HTTPException(403,'Auditor role required')
    if not 1<=len(files)<=6:raise HTTPException(400,'Upload one to six workbooks')
    settings={}
    with connection() as c:
        saved=c.execute('SELECT ciphertext FROM rulebooks WHERE id=1').fetchone()
        if saved:settings=json.loads(encryption().decrypt(bytes(saved[0])))
    async with GATE:
        with tempfile.TemporaryDirectory(prefix='kpi-upload-') as tmp:
            paths=[]
            for index,f in enumerate(files):
                name=pathlib.Path(f.filename or '').name
                if not name.lower().endswith('.xlsx'):raise HTTPException(400,'Only .xlsx files are supported')
                company=name.split(' G12')[0]
                if not allowed(u,company):raise HTTPException(403,'Company access not granted')
                # Separate directory avoids duplicate filename overwrite.
                folder=pathlib.Path(tmp)/str(index);folder.mkdir();p=folder/name
                size=0
                with p.open('wb') as stream:
                    while data:=await f.read(65536):
                        size+=len(data)
                        if size>MAX_BYTES:raise HTTPException(413,'Workbook exceeds 20 MB')
                        stream.write(data)
                validate_archive(p);paths.append(p)
            try:output=await asyncio.to_thread(run_audit,paths,settings)
            except subprocess.TimeoutExpired:raise HTTPException(408,'Workbook analysis timed out')
    now=datetime.now(timezone.utc);retention=max(1,min(365,int(os.environ.get('KPI_RETENTION_DAYS','30'))))
    with connection() as c:
        purge(c)
        for r in output['results']:
            uid=uuid.uuid4();r['id']=str(uid)
            c.execute('INSERT INTO audits VALUES (%s,%s,%s,%s,%s,%s)',(uid,u['id'],r['company'],now,now+timedelta(days=retention),encryption().encrypt(json.dumps(r).encode())))
            log(c,u,'audit.created',str(uid))
    return output

@app.get('/api/audits')
def list_audits(u=Depends(user)):
    with connection() as c:
        purge(c)
        if u.get('role')=='admin':rows=c.execute('SELECT id,company,created_at,expires_at FROM audits ORDER BY created_at DESC LIMIT 100').fetchall()
        else:rows=c.execute('SELECT id,company,created_at,expires_at FROM audits WHERE company=ANY(%s) ORDER BY created_at DESC LIMIT 100',(u.get('companies',[]),)).fetchall()
        return [dict(zip(['id','company','created_at','expires_at'],row)) for row in rows]

@app.get('/api/audits/{audit_id}')
def get_audit(audit_id:uuid.UUID,u=Depends(user)):
    with connection() as c:
        purge(c);row=c.execute('SELECT company,ciphertext FROM audits WHERE id=%s',(audit_id,)).fetchone()
        if not row or not allowed(u,row[0]):raise HTTPException(404,'Audit not found')
        log(c,u,'audit.read',str(audit_id))
        return json.loads(encryption().decrypt(bytes(row[1])))

@app.delete('/api/audits/{audit_id}',status_code=204)
def delete_audit(audit_id:uuid.UUID,u=Depends(user)):
    if u.get('role') not in ('admin','auditor'):raise HTTPException(403,'Auditor role required')
    with connection() as c:
        row=c.execute('SELECT company,owner_id FROM audits WHERE id=%s',(audit_id,)).fetchone()
        if not row or not allowed(u,row[0]):raise HTTPException(404,'Audit not found')
        if u.get('role')!='admin' and row[1]!=u['id']:raise HTTPException(403,'Only the owner or an administrator can delete an audit')
        c.execute('DELETE FROM audits WHERE id=%s',(audit_id,));log(c,u,'audit.deleted',str(audit_id))

@app.get('/api/rulebook')
def get_rules(u=Depends(user)):
    with connection() as c:
        row=c.execute('SELECT ciphertext FROM rulebooks WHERE id=1').fetchone()
        return json.loads(encryption().decrypt(bytes(row[0]))) if row else {'rules':None,'companyConfigs':{}}

@app.put('/api/rulebook')
def put_rules(body:dict,u=Depends(admin)):
    if len(json.dumps(body))>512000:raise HTTPException(413,'Rulebook too large')
    if not isinstance(body.get('rules'),list) or not isinstance(body.get('companyConfigs',{}),dict):raise HTTPException(422,'Expected rules array and companyConfigs object')
    with connection() as c:
        c.execute('INSERT INTO rulebooks VALUES (1,%s,%s) ON CONFLICT (id) DO UPDATE SET updated_at=EXCLUDED.updated_at,ciphertext=EXCLUDED.ciphertext',(datetime.now(timezone.utc),encryption().encrypt(json.dumps(body).encode())))
        log(c,u,'rulebook.updated')
    return {'saved':True}

app.mount('/',StaticFiles(directory=str(ROOT/'dist'),html=True),name='app')
