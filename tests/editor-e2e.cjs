/* Portable real footage, backend/FFmpeg, Chromium playback and download. No AI mocks. */
const { app, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const attachDownloads = require('../desktop-downloads');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'backend/studio-data/verification');
fs.mkdirSync(output, { recursive: true });
app.setPath('userData', path.join(output, 'editor-test-profile'));
app.disableHardwareAcceleration();
let server;
const live = process.env.SMARTEDIT_TEST_LIVE === '1';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
app.whenReady().then(async () => {
    const log = fs.openSync(path.join(output, 'editor-server.log'), 'w');
    if (!live) server = spawn(path.join(root, 'backend/.venv/Scripts/python.exe'), [path.join(__dirname, 'editor_server.py')], { cwd:root, windowsHide:true, stdio:['ignore',log,log] });
    let win;
    try {
        for(let i=0;i<60;i++) {
            try { const response=await fetch(`http://127.0.0.1:${live?8000:18761}/api/studio/local-health`); if(response.ok)break; } catch {}
            if(i===59)throw new Error('Isolated backend did not start');
            await delay(500);
        }
        win = new BrowserWindow({show:false,width:1440,height:1000,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,offscreen:true,backgroundThrottling:false}});
        attachDownloads(win);
        const network=[];
        const record=value=>{network.push(value);fs.writeFileSync(path.join(output,'editor-download-network.json'),JSON.stringify(network,null,2));};
        win.webContents.session.webRequest.onBeforeSendHeaders({urls:['http://127.0.0.1:*/*/file/video*']},(details,callback)=>{record({event:'request',url:details.url,headers:details.requestHeaders});callback({requestHeaders:details.requestHeaders});});
        win.webContents.session.webRequest.onHeadersReceived({urls:['http://127.0.0.1:*/*/file/video*']},(details,callback)=>{record({event:'response',url:details.url,status:details.statusLine,headers:details.responseHeaders});callback({});});
        win.webContents.session.webRequest.onErrorOccurred({urls:['http://127.0.0.1:*/*/file/video*']},details=>record({event:'error',url:details.url,error:details.error}));

        let failNextPreview = false;
        win.webContents.session.webRequest.onBeforeRequest({urls:['http://127.0.0.1:8000/*']},(details,callback)=>{
            if (failNextPreview && details.url.endsWith('/preview')) {
                callback({redirectURL:details.url.replace(':8000/',live?':8000/':':18761/')+'/simulated-missing-route'});
            }
            else callback(live?{}:{redirectURL:details.url.replace(':8000/',':18761/')});
        });
        await win.loadFile(path.join(root,'index.html'));
        await delay(500);
        const source = process.env.SMARTEDIT_TEST_VIDEO || path.join(output,'editor-fixture.mp4');
        if (!process.env.SMARTEDIT_TEST_VIDEO && !fs.existsSync(source)) require('child_process').execFileSync(path.join(root,'backend/.venv/Scripts/python.exe'),[path.join(__dirname,'make_fixture.py'),source],{windowsHide:true});
        const encoded = fs.readFileSync(source).toString('base64');
        const result = await win.webContents.executeJavaScript(`(async()=>{
            const check=(condition,message)=>{if(!condition)throw new Error(message);};
            const wait=async(fn,message)=>{for(let i=0;i<200;i++){if(fn())return;await new Promise(r=>setTimeout(r,50));}throw new Error(message);};
            const video=document.getElementById('real-preview-video');
            if (${live}) {
                const saved=(await SmartEditStudio.api('/projects')).find(p=>p.id==='aa2da58418e3456eb9dab26cdf06b86a');
                check(saved,'Original uploaded project is missing');
                SmartEditStudio.loadProject(saved);
                await wait(()=>video.readyState>=2,'Original saved upload cannot preview on the production backend');
                check(video.videoWidth===1280,'Original upload did not decode');
            }
            const bytes=Uint8Array.from(atob(${JSON.stringify(encoded)}),c=>c.charCodeAt(0));
            SmartEditBackend.selectedFile=new File([bytes],'avatar-reference.mp4',{type:'video/mp4'});
            document.getElementById('upload-language').value='hi';
            document.getElementById('upload-transcribe').checked=false;
            await startProcessingFlow();
            check(SmartEditStudio.getProject()?.language==='hi','Import lost selected speech language');
            check(!SmartEditStudio.getProject()?.captions&&!SmartEditStudio.getProject()?.narration,'Import enabled unrequested speech generation');
            document.getElementById('se-video-progress-modal')?.remove();
            check(SmartEditStudio.getProject()?.scenes.length===1,'Upload did not create a source clip');
            check(SmartEditStudio.getProject().generation_mode==='images','Upload inherited AI generation settings');
            await wait(()=>video.readyState>=2,'Uploaded video cannot be decoded by Chromium');
            video.src='http://127.0.0.1:8000/api/studio/assets/'+'0'.repeat(32)+'/preview';video.load();
            await wait(()=>video.error&&document.getElementById('editor-retry-preview'),'Failed preview has no recovery button');
            document.getElementById('editor-retry-preview').click();
            await wait(()=>!video.error&&video.readyState>=2,'Retry did not recover preview');
            video.removeAttribute('src');video.load();SmartEditEditor.syncPreview(true);
            await wait(()=>video.readyState>=2,'Reload did not restore preview');
            const realFetch=window.fetch;let staleBlocked=false,writeAttempted=false;
            window.fetch=async(url,options={})=>{if(options.method==='POST')writeAttempted=true;return new Response(JSON.stringify({production_api:1}));};
            try{await SmartEditStudio.api('/render','POST',{});}catch(e){staleBlocked=e.message.includes('older video backend');}finally{window.fetch=realFetch;}
            check(staleBlocked&&!writeAttempted,'Old backend accepted an export with unsupported edits');
            const nl=document.getElementById('ed-nl-input');
            const originalProject=JSON.stringify(SmartEditStudio.collect());
            nl.value='Reel banao, volume 50%, thoda bright karo';await handleNLCommand('ed-nl-input');
            check(document.getElementById('edit-agent-status').dataset.state==='applied','Natural-language edit failed');
            check(SmartEditStudio.getProject().aspect_ratio==='9:16'&&AgentPipeline.state.scenes[0].volume===.5&&AgentPipeline.state.scenes[0].brightness===.04,'Compound Hinglish edits did not reach timeline');
            check(video.style.filter.includes('brightness(1.04)'),'Brightness edit not visible in preview');
            undoEdit();check(JSON.stringify(SmartEditStudio.collect())===originalProject,'One undo did not restore entire edit request');
            redoEdit();check(AgentPipeline.state.scenes[0].brightness===.04,'Redo lost natural-language edit');undoEdit();
            nl.value='Mute and replace background with a beach';await handleNLCommand('ed-nl-input');
            check(JSON.stringify(SmartEditStudio.collect())===originalProject,'Unsupported compound request partially changed video');
            // A cancelled or outdated AI response must never overwrite newer manual edits.
            let resolvePlan,requestStarted=false;
            window.fetch=(url,options={})=>String(url).endsWith('/edit')?new Promise((resolve,reject)=>{
                requestStarted=true;resolvePlan=resolve;options.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});
            }):realFetch(url,options);
            try {
                nl.value='A custom request';let pending=handleNLCommand('ed-nl-input');await wait(()=>requestStarted,'Planner did not start');
                document.getElementById('edit-agent-cancel').click();await pending;
                check(JSON.stringify(SmartEditStudio.collect())===originalProject,'Cancelled request changed timeline');
                requestStarted=false;nl.value='Another custom request';pending=handleNLCommand('ed-nl-input');await wait(()=>requestStarted,'Second planner request did not start');
                selectClip(AgentPipeline.state.scenes[0].id);await toggleClipMute();
                resolvePlan(new Response(JSON.stringify({status:'applied',project:JSON.parse(originalProject),changes:['Fake late plan'],engine:'Test planner'})));await pending;
                check(AgentPipeline.state.scenes[0].muted&&document.getElementById('edit-agent-status').textContent.includes('timeline changed'),'Late response overwrote manual edit');undoEdit();
            }finally{window.fetch=realFetch;}
            check(Math.abs(DURATION-10.005)<.1,'Source metadata rounded or overwrote timeline duration');
            check(document.querySelectorAll('#tl-tracks .tl-clip').length===1,'Video track is not selectable');
            selectClip(AgentPipeline.state.scenes[0].id);
            SmartEditEditor.setRange(1,9,1);
            seekTo(3); await splitClipAtPlayhead();
            check(AgentPipeline.state.scenes.length===2,'Split failed');
            let clips=AgentPipeline.state.scenes;
            check(clips[0].sourceStart===1&&clips[0].sourceEnd===4&&clips[1].sourceStart===4,'Trim/split changed source ranges incorrectly');
            selectClip(clips[1].id);SmartEditEditor.setRange(4,9,2,{muted:true,fit:'cover',flip:true,text:'Edited in SmartEdit'});
            await moveSelectedClip(-1);
            check(AgentPipeline.state.scenes[0].sourceStart===4,'Reorder did not move video');
            check(Math.abs(DURATION-5.5)<.001,'Edited duration is wrong');
            seekTo(.5);await wait(()=>!video.seeking&&Math.abs(video.currentTime-5)<.1,'Preview did not map timeline to trimmed/sped source');
            check(video.muted&&video.playbackRate===2,'Preview mute/speed not applied');
            check(video.style.objectFit==='cover'&&video.style.transform.includes('-1'),'Crop/mirror preview not applied');
            seekTo(3.5);await wait(()=>!video.seeking&&Math.abs(video.currentTime-2)<.1,'Preview did not switch source range after reorder');
            seekTo(2.3);await wait(()=>!video.seeking,'Seek never settled');togglePlay();
            await wait(()=>currentTime>2.7,'Playback did not cross the edited cut');SmartEditEditor.pause();
            check(video.currentTime<3,'Playback kept running removed footage at cut');
            selectClip(AgentPipeline.state.scenes[0].id);await deleteSelectedClip();
            check(AgentPipeline.state.scenes.length===1,'Delete failed');undoEdit();
            check(AgentPipeline.state.scenes.length===2&&Math.abs(DURATION-5.5)<.001,'Undo failed to restore edit');
            selectClip(AgentPipeline.state.scenes[0].id);await cutSelectedClip();await pasteClip();
            check(AgentPipeline.state.scenes.length===2,'Cut/paste lost clip');undoEdit();undoEdit();
            check(AgentPipeline.state.scenes[0].sourceStart===4,'Cut/paste undo did not restore order');
            const before=currentTime;
            const caption=document.getElementById('clip-caption');caption.focus();caption.dispatchEvent(new KeyboardEvent('keydown',{code:'ArrowLeft',bubbles:true}));caption.blur();
            check(currentTime===before,'Typing in caption triggered editor shortcut');
            await switchAspectRatio('9:16');
            nl.value='Thoda bright karo, sharpen';await handleNLCommand('ed-nl-input');
            check(AgentPipeline.state.scenes.every(s=>s.brightness===.04&&s.sharpness===.35),'Natural-language enhancements missing before export');
            const project=SmartEditStudio.getProject();project.color='noir';project.captions=true;project.brand='SmartEdit test';project.resolution='720p';SmartEditStudio.updateViews();
            selectClip(AgentPipeline.state.scenes[0].id);
            document.getElementById('fx-region').value='blur';document.getElementById('fx-x').value='0';document.getElementById('fx-end_x').value='100';
            document.getElementById('clip-source-in').closest('form').requestSubmit();
            document.getElementById('editor-transition').value='fade_black';document.getElementById('editor-ratio').closest('form').requestSubmit();
            check(SmartEditStudio.collect().scenes[0].effects.region==='blur','Real editor did not apply moving blur');
            const saved=structuredClone(SmartEditStudio.collect());await SmartEditSafety.save();
            const reopened=(await SmartEditStudio.api('/projects')).find(p=>p.id===saved.id);SmartEditStudio.loadProject(reopened);
            check(SmartEditStudio.collect().scenes[0].flip&&SmartEditStudio.collect().scenes[0].fit==='cover','Saved project lost clip settings');
            check(SmartEditStudio.collect().scenes[0].brightness===.04&&SmartEditStudio.collect().scenes[0].sharpness===.35,'Save/reopen lost enhancement settings');
            check(SmartEditStudio.collect().transition==='fade_black'&&SmartEditStudio.collect().scenes[0].effects.end_x===1,'Save/reopen lost effects');
            await wait(()=>video.readyState>=2,'Saved project did not reload preview');
            document.querySelectorAll('#real-export-resolution .pill-opt').forEach(el=>el.classList.toggle('active',el.textContent.trim()==='720p'));
            await startExport();document.getElementById('se-video-progress-modal')?.remove();
            const link=document.getElementById('editor-download');check(!link.hidden&&link.href.includes('/file/video'),'Edited download not offered');
            await wait(()=>video.readyState>=2,'Export cannot play in Chromium');
            check(Math.abs(video.duration-5.5)<.2,'Export duration differs from edited timeline');
            check(video.videoWidth===720&&video.videoHeight===1280,'Export aspect ratio/resolution was ignored');
            return {project:saved,job:SmartEditBackend.currentJobId,download:link.href,duration:video.duration,width:video.videoWidth,height:video.videoHeight,checks:40};
        })()`);
        fs.writeFileSync(path.join(output,'editor-edited-preview.png'),(await win.webContents.capturePage()).toPNG());
        const destination=path.join(output,'edited-avatar-'+result.job+'.mp4');
        const downloaded=new Promise((resolve,reject)=>{
            const timer=setTimeout(()=>reject(new Error('MP4 download timed out')),30000);
            win.webContents.session.once('will-download',(_,item)=>{item.setSavePath(destination);item.once('done',(_,state)=>{clearTimeout(timer);state==='completed'?resolve():reject(new Error('Download '+state+' '+JSON.stringify({url:item.getURL(),received:item.getReceivedBytes(),total:item.getTotalBytes(),path:item.getSavePath()})));});});
        });
        await win.webContents.executeJavaScript("document.getElementById('editor-download').click()");await downloaded;
        if(!network.some(entry=>entry.event==='response'&&entry.status.includes('200')&&Object.entries(entry.headers).some(([key,value])=>key.toLowerCase()==='cache-control'&&value.includes('no-store'))))throw new Error('Download reused a cached partial response');
        if(fs.statSync(destination).size<10000)throw new Error('Empty download');
        const stale=await win.webContents.executeJavaScript(`(async()=>{selectClip(AgentPipeline.state.scenes[0].id);await toggleClipMute();return document.getElementById('editor-download').hidden&&window.lastVideoDownloadUrl===null;})()`);
        if(!stale)throw new Error('Old download remained current after a new edit');
        await win.webContents.executeJavaScript(`new Promise((resolve,reject)=>{let n=0;const timer=setInterval(()=>{if(document.getElementById('real-preview-video').readyState>=2){clearInterval(timer);resolve();}else if(++n>200){clearInterval(timer);reject(new Error('Source preview did not return'));}},50);})`);
        failNextPreview=true;
        await win.webContents.executeJavaScript(`(async()=>{
            await SmartEditEditor.importMedia([SmartEditBackend.selectedFile]);
            const v=document.getElementById('real-preview-video');
            for(let n=0;n<200;n++){if(v.error&&document.getElementById('editor-retry-preview'))return;await new Promise(r=>setTimeout(r,50));}
            throw new Error('Blocked media request did not trigger preview failure');
        })()`);
        failNextPreview=false;
        await win.webContents.executeJavaScript(`(async()=>{
            const v=document.getElementById('real-preview-video'),url=v.src;
            const retry=document.getElementById('editor-retry-preview'),bounds=retry.getBoundingClientRect();
            if(document.elementFromPoint(bounds.x+bounds.width/2,bounds.y+bounds.height/2)!==retry)throw new Error('Retry button cannot receive mouse clicks');
            retry.click();
            for(let n=0;n<200;n++){if(!v.error&&v.readyState>=2){if(v.src!==url)throw new Error('Retry changed the selected source');undoEdit();return;}await new Promise(r=>setTimeout(r,50));}
            throw new Error('Retry did not recover the same source URL');
        })()`);
        const extras=await win.webContents.executeJavaScript(`(async()=>{
            const check=(condition,message)=>{if(!condition)throw new Error(message);};
            const sourceStart=AgentPipeline.state.scenes[0].sourceStart;
            const handle=document.querySelector('#tl-tracks .tl-clip .tl-trim-handle.left');
            handle.dispatchEvent(new PointerEvent('pointerdown',{clientX:100,bubbles:true}));
            window.dispatchEvent(new PointerEvent('pointermove',{clientX:115}));
            window.dispatchEvent(new PointerEvent('pointerup',{clientX:115}));
            check(AgentPipeline.state.scenes[0].sourceStart>sourceStart,'Drag trim did not change the source range');
            undoEdit();check(AgentPipeline.state.scenes[0].sourceStart===sourceStart,'Drag trim undo failed');
            await SmartEditEditor.importMedia([SmartEditBackend.selectedFile]);
            check(AgentPipeline.state.scenes.length===3,'Add media did not append another real clip');
            undoEdit();check(AgentPipeline.state.scenes.length===2,'Add media undo failed');
            while(AgentPipeline.state.scenes.length){selectClip(AgentPipeline.state.scenes[0].id);await deleteSelectedClip();}
            check(getComputedStyle(document.getElementById('video-edit-toolbar')).display!=='none','Empty timeline hides Add media');
            undoEdit();check(AgentPipeline.state.scenes.length===1,'Undo from empty timeline failed');
            return true;
        })()`);
        const generated=await win.webContents.executeJavaScript(`(async()=>{
            const S=SmartEditStudio,assetId=AgentPipeline.state.scenes[0].asset_id;
            const p={...S.fresh(),title:'Generated clip regression',generation_mode:'images',narration:false,captions:false,duration_mode:'content',resolution:'720p',scenes:[{id:S.uid(),text:'',visual_prompt:'',asset_id:'',media_kind:'image',start:0,end:10,speed:1,mute:false}]};
            S.loadProject(p);AgentPipeline.state.scenes[0].renderedAsset={asset_id:assetId,duration:10};selectClip(1);
            document.getElementById('custom-speed-input').value='2';await confirmSpeedChange();await toggleClipMute();currentTime=2;await splitClipAtPlayhead();
            const payload=S.collect();if(payload.scenes.some(s=>s.speed!==2||!s.mute))throw Error('Generated speed/mute lost before export');
            await startExport();const job=SmartEditBackend.currentJob;
            if(Math.abs(job.result.duration-5)>.04||job.result.audio_status!=='Silent video: narration off or clips muted')throw Error('Generated clip re-export duration/audio mismatch');
            return {duration:job.result.duration,audio_status:job.result.audio_status,job:job.id};
        })()`);
        result.generatedClip=generated;
        result.downloadedFile=destination;result.checks+=13;result.backend=live?'production :8000':'isolated :18761';
        fs.writeFileSync(path.join(output,'editor-e2e-result.json'),JSON.stringify(result,null,2));
        console.log(JSON.stringify({checks:result.checks,video:destination,duration:result.duration}));
        if(win&&!win.isDestroyed())win.destroy();server?.kill();app.exit(0);
    } catch(error) {
        fs.writeFileSync(path.join(output,'editor-e2e-error.txt'),error.stack);console.error(error);
        if(win&&!win.isDestroyed())fs.writeFileSync(path.join(output,'editor-error.png'),(await win.webContents.capturePage()).toPNG());
        server?.kill();app.exit(1);
    }
});
