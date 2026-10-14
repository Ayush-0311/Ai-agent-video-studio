const {app,BrowserWindow}=require('electron');
const fs=require('fs'),path=require('path');
const out=path.resolve(__dirname,'../backend/studio-data/verification');
app.disableHardwareAcceleration();app.setPath('userData',path.join(out,'presenter-ui-profile'));
app.whenReady().then(async()=>{
 const watchdog=setTimeout(()=>{fs.writeFileSync(path.join(out,'presenter-ui-error.txt'),'Timed out');app.exit(1)},30000);
 const win=new BrowserWindow({show:false,width:1366,height:900,webPreferences:{sandbox:true,contextIsolation:true,offscreen:true,backgroundThrottling:false}});
 try{
  await win.loadFile(path.resolve(__dirname,'../index.html'));
  const result=await win.webContents.executeJavaScript(`(async()=>{
   let checks=0;const check=(value,message)=>{checks++;if(!value)throw Error(message)};
   const el=id=>document.getElementById(id), requests=[];let available=false;
   // Old clip preferences must never leak into automatic-avatar requests.
   localStorage.setItem('smarteditPresenterAsset',JSON.stringify({id:'e'.repeat(32),name:'old.mp4'}));
   window.fetch=async(url,options={})=>{
    const route=new URL(url).pathname.replace('/api/studio','');requests.push({route,body:options.body});let body={};
    if(route==='/local-health')body={production_api:15};
    if(route==='/presenter-status')body={available,tested:false,message:available?'Setup ready. Test first.':'Enable realistic presenter in Colab.'};
    if(route==='/presenter-test')body={id:'f'.repeat(32)};
    if(route==='/jobs/'+'f'.repeat(32))body={id:'f'.repeat(32),kind:'presenter_test',status:'completed',progress:100,events:[],result:{video_url:'/sample.mp4',message:'Review mouth movement before generating.'}};
    if(route==='/projects'||route==='/jobs')body=[];
    return new Response(JSON.stringify(body),{headers:{'content-type':'application/json'}});
   };
   goTo('upload');el('gen-video-mode').value='avatar';el('gen-video-mode').dispatchEvent(new Event('change'));
   check(el('gen-presenter-kind').value==='realistic','Automatic talking avatar is not the default');
   await new Promise(r=>setTimeout(r,200));
   check(!el('real-presenter-options').hidden,'Automatic avatar controls missing');
   check(!el('gen-presenter-character').closest('label').hidden,'Avatar appearance choice is hidden');
   check(!el('presenter-upload')&&!el('presenter-choose'),'Upload requirement remains in the UI');
   check(el('presenter-test').disabled,'Test should be disabled before GPU setup');
   check(el('presenter-runtime-status').textContent.includes('Enable'),'Missing setup instructions');
   available=true;await checkColabStatus();await new Promise(r=>setTimeout(r,200));
   check(!el('presenter-test').disabled,'Test still requires an upload after setup');
   el('gen-video-prompt').value='Explain machine learning';el('gen-presenter-character').value='maya';
   el('presenter-test').click();for(let wait=0;wait<50&&SmartEditStudio.busy();wait++)await new Promise(r=>setTimeout(r,100));
   const test=requests.find(r=>r.route==='/presenter-test');
   check(!!test,'Test did not submit');const payload=JSON.parse(test.body);
   check(payload.presenter_kind==='realistic'&&payload.presenter_asset_id==='','An old clip leaked into automatic generation');
   check(payload.presenter_character==='maya'&&payload.prompt==='Explain machine learning','Topic/appearance lost');
   check(!requests.some(r=>r.route==='/assets'),'Automatic avatar asked for an upload');
   check(!requests.some(r=>r.route==='/generate'||r.route==='/plan'),'5-second test started full generation');
   check(!el('presenter-test').disabled,'Test button did not recover after completion');
   const modal=el('se-video-progress-modal');if(modal)modal.remove();
   el('gen-presenter-kind').value='illustrated';el('gen-presenter-kind').dispatchEvent(new Event('change'));
   check(el('real-presenter-options').hidden&&!el('gen-presenter-character').closest('label').hidden,'Returning to illustrated failed');
   el('gen-presenter-kind').value='realistic';el('gen-presenter-kind').dispatchEvent(new Event('change'));
   return {checks};
  })()`);
  for(const width of [1366,800,390]){
   win.setContentSize(width,900);
   await win.webContents.executeJavaScript(`document.getElementById('gen-presenter-options').scrollIntoView({block:'center'});`);
   await new Promise(r=>setTimeout(r,200));
   const clipped=await win.webContents.executeJavaScript(`(()=>[...document.querySelectorAll('#gen-presenter-options input,#gen-presenter-options select,#gen-presenter-options button')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&(r.left<0||r.right>innerWidth+1)}).map(e=>e.id))()`);
   if(clipped.length)throw Error('Clipped presenter controls at '+width+': '+clipped.join(','));
   fs.writeFileSync(path.join(out,'real-presenter-ui-'+width+'.png'),(await win.webContents.capturePage()).toPNG());
  }
  fs.writeFileSync(path.join(out,'presenter-ui-result.json'),JSON.stringify({passed:true,...result,widths:[1366,800,390]},null,2));app.exit(0);
 }catch(e){fs.writeFileSync(path.join(out,'presenter-ui-error.txt'),e.stack||String(e));app.exit(1)}
});
