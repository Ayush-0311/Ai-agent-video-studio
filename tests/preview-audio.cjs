const {app,BrowserWindow}=require('electron');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'backend/studio-data/verification/current-voice-review');
fs.mkdirSync(out,{recursive:true});app.setPath('userData',path.join(out,'electron-profile'));app.disableHardwareAcceleration();
const delay=ms=>new Promise(r=>setTimeout(r,ms));
app.whenReady().then(async()=>{
 let win;
 try{
  const jid=process.env.SMARTEDIT_AUDIO_JOB||'7f62602c981b4f4c9b338d0f0af41f70';
  const report=JSON.parse(fs.readFileSync(path.join(root,'backend/studio-data/renders',jid,'metadata.json'),'utf8'));
  const job=JSON.parse(fs.readFileSync(path.join(root,'backend/studio-data/jobs',jid+'.json'),'utf8'));
  const health=await fetch('http://127.0.0.1:8000/api/studio/local-health');if(!health.ok)throw new Error('Backend unavailable');
  win=new BrowserWindow({show:false,width:1400,height:900,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:false}});
  await win.loadFile(path.join(root,'index.html'));await delay(800);
  await win.webContents.executeJavaScript(`SmartEditStudio.openSavedProject(${JSON.stringify(report.project)},[${JSON.stringify(job)}]);`);
  await delay(700);await win.webContents.executeJavaScript('seekTo(1);togglePlay();',true);
  const samples=[];
  for(let i=0;i<6;i++){
   await delay(600);
   const state=await win.webContents.executeJavaScript(`(()=>{const v=document.getElementById('real-preview-video');return {src:v.src,time:v.currentTime,paused:v.paused,muted:v.muted,volume:v.volume,ready:v.readyState,error:v.error?.message,audioBytes:v.webkitAudioDecodedByteCount,videoBytes:v.webkitVideoDecodedByteCount,slider:document.querySelector('.volume-slider').value,note:document.querySelector('.editor-preview-note').textContent}})()`);
   samples.push({...state,chromiumAudible:win.webContents.isCurrentlyAudible(),pageMuted:win.webContents.isAudioMuted()});
  }
  if(!samples.some(s=>s.chromiumAudible&&s.audioBytes>0&&!s.muted&&s.volume>0))throw new Error('No decoded audible narration from restored export: '+JSON.stringify(samples));
  const mute=await win.webContents.executeJavaScript(`(()=>{const before=JSON.stringify(SmartEditStudio.collect());volChange(0);const v=document.getElementById('real-preview-video');const muted={volume:v.volume,label:document.getElementById('preview-volume-value').textContent,note:document.querySelector('.editor-preview-note').textContent};document.getElementById('preview-audio-toggle').click();return {muted,restored:v.volume,slider:document.querySelector('.volume-slider').value,exportUnchanged:before===JSON.stringify(SmartEditStudio.collect())}})()`);
  if(mute.muted.volume!==0||mute.muted.label!=='Muted'||mute.restored!==.8||mute.slider!=='80'||!mute.exportUnchanged)throw new Error('Preview mute control failed: '+JSON.stringify(mute));
  await win.webContents.executeJavaScript('seekTo(2);',true);await delay(1200);
  const restoredAudible=win.webContents.isCurrentlyAudible();
  if(!restoredAudible)throw new Error('Restored sound did not become audible');
  const changed=structuredClone(report.project);changed.scenes[0].text+=' Edited narration.';
  const stale=await win.webContents.executeJavaScript(`SmartEditStudio.openSavedProject(${JSON.stringify(changed)},[${JSON.stringify(job)}]);({url:window.lastVideoDownloadUrl,note:document.querySelector('.editor-preview-note').textContent})`);
  if(stale.url)throw new Error('Edited project incorrectly restored stale video');
  fs.writeFileSync(path.join(out,'electron-audio-result.json'),JSON.stringify({passed:true,samples,mute,restoredAudible,editedProject:stale},null,2));
  await win.webContents.executeJavaScript('SmartEditEditor.pause();');win.destroy();app.quit();
 }catch(error){fs.writeFileSync(path.join(out,'electron-audio-error.txt'),error.stack);if(win)win.destroy();app.exit(1);}
});
