/* Regression coverage for audit findings; isolated renderer and fixture HTTP. */
const {app,BrowserWindow}=require('electron');
const fs=require('fs'),path=require('path');
const attachUnsaved=require('../desktop-unsaved');
const root=path.resolve(__dirname,'..'),out=path.join(root,'backend/studio-data/verification');
app.setPath('userData',path.join(out,'audit-fixes-profile'));app.disableHardwareAcceleration();
app.on('window-all-closed',()=>{});
app.whenReady().then(async()=>{
 const watchdog=setTimeout(()=>{fs.writeFileSync(path.join(out,'audit-fixes-error.txt'),'Timed out');app.exit(1)},60000);
 const win=new BrowserWindow({show:false,width:1366,height:900,webPreferences:{sandbox:true,contextIsolation:true,offscreen:true,backgroundThrottling:false}});
 attachUnsaved(win);
 try{
  await win.loadFile(path.join(root,'index.html'));await new Promise(r=>setTimeout(r,500));
  const result=await win.webContents.executeJavaScript(`(async()=>{
   const S=SmartEditStudio,E=SmartEditEditor,A=SmartEditSafety;let checks=0;const check=(x,m)=>{checks++;if(!x)throw Error(m)};
   const calls=[];let failSave=false,saved=[],jobs=[],saveGate=null;
   window.fetch=async(url,options={})=>{const route=new URL(url).pathname.replace('/api/studio','');calls.push({route,method:options.method});let data={};
    if(route==='/local-health')data={production_api:17};
    else if(route==='/projects')data=saved;
    else if(route==='/jobs')data=jobs;
    else if(route==='/storage-health')data={warnings:[{file:'damaged.json',kind:'projects'}]};
    else if(route.startsWith('/projects/')&&options.method==='PUT'){if(failSave)return new Response(JSON.stringify({detail:'Fixture disk error'}),{status:500});const p=JSON.parse(options.body);if(saveGate)await saveGate;saved=[p];data=p;}
    else if(route.endsWith('/metadata'))data={duration:10,kind:'video',has_audio:true};
    else if(route==='/assets')data={id:'c'.repeat(32),name:'fixture.mp4',duration:10,kind:'video'};
    return new Response(JSON.stringify(data));};
   const p={id:'a'.repeat(32),title:'Generated fixture',prompt:'A tree',language:'en',duration:10,duration_mode:'content',aspect_ratio:'16:9',resolution:'720p',generation_mode:'images',narration:false,captions:false,style:'natural',scenes:[{id:'b'.repeat(32),text:'One two three four',visual_prompt:'A tree',asset_id:'',media_kind:'image',start:0,end:10,speed:1,mute:false}]};
   const load=()=>{S.loadProject(structuredClone(p));AgentPipeline.state.scenes[0].renderedAsset={asset_id:'c'.repeat(32),duration:10};selectClip(1);};
   load();
   document.getElementById('clip-screen-text').value='KEEP GOING';
   document.getElementById('clip-fade-out').checked=true;
   await document.getElementById('clip-screen-text').closest('form').onsubmit(new Event('submit',{cancelable:true}));
   check(S.collect().scenes[0].overlay_text==='KEEP GOING'&&S.collect().scenes[0].fade_out,'Screen text/fade edit was dropped');
   const readyRoundTrip=structuredClone(S.collect());readyRoundTrip.auto_music='calm';S.loadProject(readyRoundTrip);selectClip(1);
   check(document.getElementById('clip-screen-text').value==='KEEP GOING'&&document.getElementById('editor-screen-text').textContent==='KEEP GOING','Screen text did not survive reload/preview');
   check(S.collect().auto_music==='calm','Automatic music preference did not survive reload');
   load();document.getElementById('custom-speed-input').value='2';await confirmSpeedChange();currentTime=2;await splitClipAtPlayhead();
   const split=S.collect();check(DURATION===5,'Timeline must stay 5s');check(split.scenes.reduce((n,s)=>n+(s.end-s.start)/s.speed,0)===5,'Export duration differs from timeline');check(split.scenes.every(s=>s.speed===2),'Split reset speed');
   undoEdit();check(AgentPipeline.state.scenes.length===1&&DURATION===5,'Undo split lost timing');redoEdit();check(S.collect().scenes.every(s=>s.speed===2),'Redo split lost speed');
   load();await toggleClipMute();currentTime=5;await splitClipAtPlayhead();check(S.collect().scenes.every(s=>s.mute),'Split unmuted generated speech');
   load();document.getElementById('custom-speed-input').value='2';await confirmSpeedChange();currentTime=2;await trimClipLeft();check(S.collect().scenes[0].speed===2&&DURATION===3,'Trim lost generated speed');
   load();const measured=AgentPipeline.state.scenes[0];measured.e=8;measured.renderedAsset.duration=8;S.updateViews('preview');selectClip(1);check(Number(document.getElementById('clip-source-out').value)===8,'Properties use planned instead of measured source length');E.setRange(0,8,1);check(DURATION===8,'Applying measured source range changes duration');
   load();await toggleClipMute();await A.save();check(!A.isDirty(),'Successful save still dirty');const copy=JSON.parse(JSON.stringify(saved[0]));await S.openSavedProject(copy,[]);check(!!E.info(AgentPipeline.state.scenes[0]),'Reopen lost rendered preview');check(S.collect().scenes[0].mute,'Reopen lost mute');
   AgentPipeline.state.scenes[0].text='A different narration';S.updateViews();check(!E.info(AgentPipeline.state.scenes[0]),'Changed narration reused stale preview');
   load();await toggleClipMute();check(A.isDirty()&&document.getElementById('project-save-status').textContent.includes('Unsaved'),'Dirty indicator missing');
   const target={...p,id:'d'.repeat(32),title:'Another project'};
   let pending=S.openSavedProject(target,[]);document.getElementById('unsaved-keep').click();await pending;check(S.getProject().id===p.id&&A.isDirty(),'Keep editing lost project');
   pending=S.openSavedProject(target,[]);document.getElementById('unsaved-discard').click();await pending;check(S.getProject().id===target.id&&!A.isDirty(),'Discard did not switch');
   load();await toggleClipMute();failSave=true;pending=S.openSavedProject(target,[]);await document.getElementById('unsaved-save').onclick();check(!!document.getElementById('unsaved-project-dialog')&&A.isDirty(),'Save failure dismissed protection');check(S.getProject().id===p.id,'Save failure replaced project');check(document.querySelector('#unsaved-project-dialog [role=alert]').textContent.includes('disk error'),'Save failure hidden');
   failSave=false;await document.getElementById('unsaved-save').onclick();await pending;check(saved[0].scenes[0].mute&&S.getProject().id===target.id,'Save and continue failed');
   load();const oldCopy=structuredClone(S.collect());await toggleClipMute();pending=S.openSavedProject(oldCopy,[]);await document.getElementById('unsaved-save').onclick();await pending;check(S.collect().scenes[0].mute&&!A.isDirty(),'Save then reopen same project reverted edits');
   load();await toggleClipMute();document.body.dispatchEvent(new KeyboardEvent('keydown',{code:'KeyS',ctrlKey:true,bubbles:true}));await new Promise(r=>setTimeout(r,20));check(!A.isDirty(),'Ctrl+S did not clear dirty state');
   load();await toggleClipMute();let releaseSave;saveGate=new Promise(r=>releaseSave=r);const firstSave=A.save();await new Promise(r=>setTimeout(r,20));
   AgentPipeline.state.scenes[0].text='Edit while save is in flight';S.updateViews();pending=S.openSavedProject(target,[]);const saveAndContinue=document.getElementById('unsaved-save').onclick();releaseSave();saveGate=null;await firstSave;await saveAndContinue;await pending;
   check(saved[0].scenes[0].text==='Edit while save is in flight'&&S.getProject().id===target.id,'Save and continue lost edits made during pending save');
   load();await toggleClipMute();saveGate=new Promise(r=>releaseSave=r);const saveBeforeUndo=A.save();await new Promise(r=>setTimeout(r,20));undoEdit();check(!A.isDirty(),'Undo did not restore initial save signature');
   pending=S.openSavedProject(target,[]);await new Promise(r=>setTimeout(r,20));check(S.getProject().id===p.id,'Project switched before pending save settled');releaseSave();saveGate=null;await saveBeforeUndo;await new Promise(r=>setTimeout(r,20));
   check(!!document.getElementById('unsaved-project-dialog')&&A.isDirty(),'Pending save overwrote disk state without protecting undo');document.getElementById('unsaved-keep').click();await pending;
   load();await toggleClipMute();await A.save();SmartEditBackend.selectedFile=new File(['fixture'],'fixture.mp4',{type:'video/mp4'});failSave=true;await openInEditorDirectly();
   check(A.isDirty()&&document.getElementById('project-save-status').textContent.includes('Unsaved'),'Failed initial import save incorrectly marked project saved');
   check(S.collect().scenes[0].asset_id==='c'.repeat(32),'Failed import save lost editable source');const importedId=S.getProject().id;undoEdit();check(S.getProject().id===importedId,'New import retained previous project undo history');failSave=false;await A.save();check(!A.isDirty(),'Failed import could not be saved on retry');
   document.getElementById('se-video-progress-modal')?.remove();
   load();currentTime=5;await splitClipAtPlayhead();check(A.isDirty(),'Split not marked dirty');undoEdit();check(!A.isDirty(),'Undo to saved state remains dirty');
   load();document.getElementById('custom-speed-input').value='4';await confirmSpeedChange();check(S.collect().scenes[0].speed===1,'Invalid speed applied');check([...document.querySelectorAll('.speed-preset-btn')].every(b=>+b.textContent.replace('x','')>=.5&&+b.textContent.replace('x','')<=2),'Invalid speed preset remains');
   for(const f of [{name:'large.mp4',size:500*1024*1024+1},{name:'movie.avi',size:1},{name:'empty.mp4',size:0}]){const count=calls.length;let rejected=false;try{await S.upload(f)}catch{rejected=true}check(rejected&&calls.length===count,'Bad file reached network');}
   load();const original=structuredClone(S.collect());const changed=structuredClone(original);changed.scenes[0].mute=true;saved=[changed];jobs=[{project_id:p.id,kind:'render',status:'completed',result:{project:original,video_url:'/older.mp4'}}];window.refreshStudioProjects();await new Promise(r=>setTimeout(r,30));check(document.querySelector('#studio-saved-projects a').textContent==='Download previous export','Old export presented as current');check(document.getElementById('studio-saved-projects').textContent.includes('could not be read'),'Storage recovery warning hidden');
   jobs[0].result.project=structuredClone(changed);window.refreshStudioProjects();await new Promise(r=>setTimeout(r,30));check(document.querySelector('#studio-saved-projects a').textContent==='Download MP4','Current export mislabeled');
   check(!/4K|60fps|99.4%|under 60|Pro Trial/.test(document.getElementById('view-landing').innerText),'Unsupported landing claims remain');
   check(document.getElementById('view-upload').textContent.includes('500 MiB'),'Upload limit missing');check(document.querySelectorAll('.creation-paths button').length===2,'Starting choices missing');
   load();await toggleClipMute();const evt=new Event('beforeunload',{cancelable:true});window.dispatchEvent(evt);check(evt.defaultPrevented,'Reload is not protected');
   const guideChoices=[...document.querySelectorAll('#creation-guide [onclick^="chooseCreationMode"]')];
   const guideModes=[['images',null],['hybrid',null],['motion',null],['avatar','illustrated'],['avatar','realistic']];
   const submissions=calls.filter(c=>['/plan','/generate','/render'].includes(c.route)).length;
   check(guideChoices.length===guideModes.length,'Missing guide mode choice');
   for(let i=0;i<guideModes.length;i++){guideChoices[i].click();const [mode,kind]=guideModes[i];check(currentView==='upload'&&document.getElementById('gen-video-mode').value===mode&&(!kind||document.getElementById('gen-presenter-kind').value===kind),'Guide selected wrong output type');}
   openCreationGuide();await new Promise(r=>setTimeout(r,50));check(currentView==='landing'&&document.activeElement.id==='creation-guide-title','Guide navigation or keyboard focus failed');
   check(calls.filter(c=>['/plan','/generate','/render'].includes(c.route)).length===submissions,'Reading/selecting guide started production');
   openCreationPath('ai');check(document.getElementById('gen-video-mode').value==='avatar'&&document.getElementById('gen-presenter-kind').value==='realistic','Returning to setup lost mode selection');
   chooseCreationMode('hybrid');
   return {passed:true,checks};
  })()`);
  await win.webContents.executeJavaScript("goTo('landing')");
  await new Promise(r=>setTimeout(r,400));
  fs.writeFileSync(path.join(out,'fixed-landing.png'),(await win.webContents.capturePage()).toPNG());
  await win.webContents.executeJavaScript("goTo('editor')");
  win.close();await new Promise(r=>setTimeout(r,400));
  fs.writeFileSync(path.join(out,'unsaved-project-dialog.png'),(await win.webContents.capturePage()).toPNG());
  if(win.isDestroyed())throw Error('Dirty window closed without confirmation');
  await win.webContents.executeJavaScript("document.getElementById('unsaved-keep').click()");await new Promise(r=>setTimeout(r,50));
  if(win.isDestroyed())throw Error('Keep editing did not protect window');
  win.close();await new Promise(r=>setTimeout(r,80));
  await win.webContents.executeJavaScript("document.getElementById('unsaved-save').click()");
  await new Promise(r=>setTimeout(r,120));if(!win.isDestroyed())throw Error('Save and close did not complete');
  result.checks+=3;result.nativeClose=true;
  fs.writeFileSync(path.join(out,'audit-fixes-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));clearTimeout(watchdog);app.exit(0);
 }catch(e){fs.writeFileSync(path.join(out,'audit-fixes-error.txt'),e.stack);console.error(e);app.exit(1);}
});

