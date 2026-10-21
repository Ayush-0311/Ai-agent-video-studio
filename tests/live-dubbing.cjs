/* Live UI import -> translation -> Hindi dubbing; no mocked AI or HTTP responses. */
const {app,BrowserWindow}=require('electron');
const fs=require('fs'),path=require('path');
const sourceFolder=path.resolve(__dirname,'../backend/studio-data/verification/dubbing-live-2026-10-18');
const out=process.env.SMARTEDIT_LIVE_TEST_BASE?path.join(sourceFolder,'fixed'):sourceFolder;
fs.mkdirSync(out,{recursive:true});
// Electron can outlive the launching terminal. Persist logs without writing to
// its closed stdout/stderr pipe (which otherwise opens repeated EPIPE dialogs).
const log=(value)=>fs.appendFileSync(path.join(out,'ui-progress.log'),String(value)+'\n');
console.log=log;console.error=log;
log('Starting live dubbing test '+new Date().toISOString());
fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({passed:false,status:'running'}));
const base=process.env.SMARTEDIT_LIVE_TEST_BASE||'http://127.0.0.1:8000';
app.disableHardwareAcceleration();
app.setPath('userData',path.join(out,'electron-profile'));
app.whenReady().then(async()=>{
 const win=new BrowserWindow({show:false,width:1400,height:960,webPreferences:{sandbox:true,contextIsolation:true,offscreen:true,backgroundThrottling:false}});
 let timer;
 try{
  if(base!=='http://127.0.0.1:8000')win.webContents.session.webRequest.onBeforeRequest({urls:['http://127.0.0.1:8000/*']},(details,callback)=>callback({redirectURL:details.url.replace('http://127.0.0.1:8000',base)}));
  await win.loadFile(path.resolve(__dirname,'../index.html'));
  await new Promise(r=>setTimeout(r,1500));
  const encoded=fs.readFileSync(path.join(sourceFolder,'english-source-30s.mp4')).toString('base64');
  await win.webContents.executeJavaScript(`(()=>{
    const original=window.fetch;
    window.fetch=async(...args)=>{const r=await original(...args);if(String(args[0]).endsWith('/dub')&&r.ok)window.__liveDubJob=(await r.clone().json()).id;return r;};
    goTo('upload');
    const transfer=new DataTransfer();transfer.items.add(new File([Uint8Array.from(atob(${JSON.stringify(encoded)}),c=>c.charCodeAt(0))],'English river lesson - 30 seconds.mp4',{type:'video/mp4'}));
    const input=document.getElementById('file-input');input.files=transfer.files;input.dispatchEvent(new Event('change'));
    document.getElementById('upload-language').value='en';
    document.getElementById('upload-target-language').value='hi';
    document.getElementById('upload-translate').checked=true;
    document.getElementById('upload-transcribe').checked=true;
    document.getElementById('upload-translate').dispatchEvent(new Event('change'));
    return true;
  })()`);
  fs.writeFileSync(path.join(out,'import-options.png'),(await win.webContents.capturePage()).toPNG());
  const started=Date.now();let last='',seen=0,job;
  const flow=win.webContents.executeJavaScript('startProcessingFlow()');
  timer=setInterval(async()=>{
   try{
    const id=await win.webContents.executeJavaScript('window.__liveDubJob||null');
    if(!id)return;
    job=await(await fetch(base+'/api/studio/jobs/'+id)).json();
    fs.writeFileSync(path.join(out,'ui-job.json'),JSON.stringify(job,null,2));
    for(const event of (job.events||[]).slice(seen))console.log(JSON.stringify({elapsed:(Date.now()-started)/1000,...event}));
    seen=(job.events||[]).length;
   }catch(e){if(e.message!==last)console.log(e.message);last=e.message;}
  },3000);
  await flow;
  clearInterval(timer);
  const id=await win.webContents.executeJavaScript('window.__liveDubJob||null');
  if(!id)throw Error('UI did not submit dubbing; inspect the error screenshot.');
  job=await(await fetch(base+'/api/studio/jobs/'+id)).json();
  fs.writeFileSync(path.join(out,'ui-job.json'),JSON.stringify(job,null,2));
  if(job.status!=='completed')throw Error(job.error||job.status);
  const state=await win.webContents.executeJavaScript(`({language:SmartEditStudio.collect().language,captions:SmartEditStudio.collect().captions,scenes:SmartEditStudio.collect().scenes.length})`);
  if(state.language!=='hi'||!state.captions)throw Error('UI did not load the Hindi captioned result.');
  for(const [key,name]of[['video_url','hindi-dub-ui.mp4'],['subtitles_url','hindi-dub-ui.srt'],['metadata_url','hindi-dub-ui-metadata.json']]){
   const r=await fetch(base+job.result[key]);if(!r.ok)throw Error('Download failed');fs.writeFileSync(path.join(out,name),Buffer.from(await r.arrayBuffer()));
  }
  fs.writeFileSync(path.join(out,'editor-result.png'),(await win.webContents.capturePage()).toPNG());
  const result={passed:true,seconds:(Date.now()-started)/1000,job:id,duration:job.result.duration,...state};
  fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));app.exit(0);
 }catch(e){clearInterval(timer);fs.writeFileSync(path.join(out,'ui-result.json'),JSON.stringify({passed:false,status:'failed',error:e.message,finished:new Date().toISOString()},null,2));fs.writeFileSync(path.join(out,'ui-error.txt'),e.stack);fs.writeFileSync(path.join(out,'ui-error.png'),(await win.webContents.capturePage()).toPNG());console.error(e.stack);app.exit(1);}
});
