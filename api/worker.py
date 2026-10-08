import json,pathlib,subprocess,sys,tempfile,resource
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from inspect_workbooks import extract
resource.setrlimit(resource.RLIMIT_CPU,(75,75))
job=json.loads(pathlib.Path(sys.argv[1]).read_text())
with tempfile.TemporaryDirectory(prefix='kpi-engine-') as tmp:
    input_path=pathlib.Path(tmp)/'input.json'
    input_path.write_text(json.dumps({'workbooks':[extract(pathlib.Path(p)) for p in job['paths']],'settings':job['settings']},default=str))
    result=subprocess.run(['node','--max-old-space-size=512',str(ROOT/'api'/'run.mjs'),str(input_path)],capture_output=True,text=True,timeout=45)
    if result.returncode:raise RuntimeError('Validation engine failed')
    print(result.stdout)
