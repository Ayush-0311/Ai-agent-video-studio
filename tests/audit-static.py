import ast,json,sys,tempfile,subprocess
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'backend'))
import studio
from fastapi import FastAPI
from fastapi.testclient import TestClient
output={}; files=[p for folder in ['backend','colab','scripts','tests'] for p in (root/folder).glob('*.py')]
for p in files: ast.parse(p.read_text('utf-8-sig'),filename=str(p))
output['python_syntax_files']=len(files)
js=[root/'main.js',root/'desktop-downloads.js',root/'desktop-unsaved.js']+[p for folder in ['frontend','agents','tests'] for p in (root/folder).rglob('*') if p.suffix in ('.js','.cjs')]
for p in js: subprocess.run(['node','--check',str(p)],check=True,capture_output=True)
output['javascript_syntax_files']=len(js)
old=studio.DATA
with tempfile.TemporaryDirectory() as temp:
 studio.DATA=Path(temp);(studio.DATA/'jobs').mkdir();(studio.DATA/'jobs'/'bad.json').write_text('{')
 studio.install(FastAPI(),{});output['corrupt_job']={'startup_survived':True,'original_retained':(studio.DATA/'jobs'/'bad.json').read_text()=='{'}
 (studio.DATA/'jobs'/'bad.json').unlink();app=FastAPI();studio.install(app,{})
 (studio.DATA/'projects').mkdir();(studio.DATA/'projects'/'bad.json').write_text('{')
 response=TestClient(app,raise_server_exceptions=False).get('/api/studio/projects');output['corrupt_project_http_status']=response.status_code
assert response.status_code==200, 'Corrupt project blocks healthy records'
studio.DATA=old
(root/'backend/studio-data/verification/audit-static-results.json').write_text(json.dumps(output,indent=2))
print(json.dumps(output))
