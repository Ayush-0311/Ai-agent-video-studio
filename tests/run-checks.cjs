const {spawnSync}=require('child_process');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'backend/studio-data/verification');fs.mkdirSync(out,{recursive:true});
const python=path.join(root,'backend/.venv/Scripts/python.exe'),electron=path.join(root,'node_modules/electron/dist/electron.exe');
const selected=process.argv.slice(2),results=[];
const checks=[
 ['syntax',python,['tests/audit-static.py'],120000,'audit-static-results.json'],
 ['backend',python,['-m','unittest','discover','-s','backend','-p','test_*.py','-v'],240000],
 ['colab',python,['-m','unittest','discover','-s','colab','-p','test_*.py','-v'],120000],
 ['launcher','powershell.exe',['-NoProfile','-ExecutionPolicy','Bypass','-File','tests/desktop-launcher.ps1'],60000],
 ['runtime',python,['scripts/check_install.py'],60000],
 ['ui',electron,['tests/ui-smoke.cjs'],120000,'ui-result.json'],
 ['presenter',electron,['tests/presenter-ui.cjs'],60000,'presenter-ui-result.json'],
 ['recovery',electron,['tests/generation-recovery.cjs'],60000,'generation-recovery-result.json'],
 ['layout',electron,['tests/layout-audit.cjs'],60000,'layout-audit-result.json'],
 ['audit',electron,['tests/audit-fixes.cjs'],90000,'audit-fixes-result.json'],
 ['editor',electron,['tests/editor-e2e.cjs'],240000,'editor-e2e-result.json']
];
for(const [name,binary,args,timeout,artifact] of checks){
 if(selected.length&&!selected.includes(name))continue;
 console.log('Running '+name+'...');const started=Date.now();
 const run=spawnSync(binary,args,{cwd:root,windowsHide:true,encoding:'utf8',timeout,maxBuffer:8*1024*1024,env:{...process.env,PYTHONIOENCODING:'utf-8'}});
 fs.writeFileSync(path.join(out,'check-'+name+'.log'),(run.stdout||'')+(run.stderr||'')+(run.error?'\n'+run.error.stack:''));
 const file=artifact&&path.join(out,artifact),fresh=!file||(fs.existsSync(file)&&fs.statSync(file).mtimeMs>=started-1000);
 const passed=run.status===0&&!run.error&&fresh;results.push({name,passed,status:run.status,durationSeconds:Math.round((Date.now()-started)/100)/10,artifact:artifact||null});
 fs.writeFileSync(path.join(out,'checks-result.json'),JSON.stringify({passed:results.every(r=>r.passed),selected,results},null,2));
 console.log(name+': '+(passed?'PASS':'FAIL')+' ('+results.at(-1).durationSeconds+'s)');
 if(!passed){console.error((run.stdout||'')+(run.stderr||''));console.error('See '+path.join(out,'check-'+name+'.log'));process.exit(1);}
}
if(!results.length){console.error('No matching checks');process.exit(1);}
console.log('All '+results.length+' selected checks passed.');
