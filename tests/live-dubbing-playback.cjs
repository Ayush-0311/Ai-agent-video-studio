const {app,BrowserWindow}=require('electron');
const fs=require('fs'),path=require('path');
const folder=path.resolve(__dirname,'../backend/studio-data/verification/dubbing-live-2026-10-18/fixed');
const base=process.env.SMARTEDIT_LIVE_TEST_BASE||'http://127.0.0.1:8012';
app.disableHardwareAcceleration();
app.setPath('userData',path.join(folder,'playback-profile'));
app.whenReady().then(async()=>{
 const win=new BrowserWindow({show:false,webPreferences:{offscreen:true,sandbox:true}});
 try{
  const job=JSON.parse(fs.readFileSync(path.join(folder,'ui-job.json')));
  const ui=JSON.parse(fs.readFileSync(path.join(folder,'ui-result.json')));
  if(!ui.passed||ui.job!==job.id||job.status!=='completed')throw Error('The latest UI run is not complete');
  const url=base+job.result.video_url;
  const range=await fetch(url,{headers:{Range:'bytes=0-127'}});
  if(range.status!==206||(await range.arrayBuffer()).byteLength!==128)throw Error('Range seeking unavailable');
  await win.loadURL(base+'/docs');
  const playback=await win.webContents.executeJavaScript(`(async()=>{
   const v=document.createElement('video');v.muted=true;v.src=${JSON.stringify(url)};document.body.append(v);
   await new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Video load timed out')),20000);v.onloadedmetadata=()=>{clearTimeout(t);resolve()};v.onerror=()=>reject(Error('Video decode error'));});
   await v.play();await new Promise(r=>setTimeout(r,1500));const first=v.currentTime;
   if(first<.5)throw Error('Playback did not advance');
   v.currentTime=24;await new Promise(r=>setTimeout(r,1500));const seek=v.currentTime;v.pause();
   if(seek<24.5)throw Error('Seek playback did not advance');
   return {first,seek,duration:v.duration,width:v.videoWidth,height:v.videoHeight};
  })()`);
  fs.writeFileSync(path.join(folder,'playback-result.json'),JSON.stringify({passed:true,job:job.id,range:206,...playback},null,2));app.exit(0);
 }catch(e){fs.writeFileSync(path.join(folder,'playback-error.txt'),e.stack);app.exit(1);}
});
