/* Reload a real renderer mid-generation; backend responses are fixtures. */
const {app, BrowserWindow} = require('electron');
const fs = require('fs');
const path = require('path');
const output = path.resolve(__dirname, '../backend/studio-data/verification');
app.setPath('userData', path.join(output, 'generation-recovery-profile'));
app.disableHardwareAcceleration();
app.whenReady().then(async () => {
  const deadline = setTimeout(() => {fs.writeFileSync(path.join(output,'generation-recovery-error.txt'),'Recovery check exceeded 20 seconds');app.exit(1);},20000);
  const win = new BrowserWindow({show:false, webPreferences:{sandbox:true, contextIsolation:true, nodeIntegration:false, offscreen:true, backgroundThrottling:false}});
  try {
    await win.webContents.session.clearStorageData();
    const fixture = `
      const jobId='7'.repeat(32);
      const reloadCount=Number(localStorage.getItem('fixture-reloads')||0)+1;
      localStorage.setItem('fixture-reloads',reloadCount);
      if(reloadCount===1)localStorage.setItem('smartedit.original.activeJob',jobId);
      const project={id:'6'.repeat(32),title:'AI explained',prompt:'Explain artificial intelligence',language:'hi',duration:30,
        aspect_ratio:'16:9',resolution:'1080p',generation_mode:'avatar',presenter_layout:'pip-right',presenter_character:'maya',presenter_theme:'teal',
        style:'cinematic',narration:true,captions:true,scene_mode:'auto',research:true,
        scenes:[{id:'5'.repeat(32),text:'कृत्रिम बुद्धिमत्ता उदाहरणों से सीखती है।',visual_prompt:'A computer classifies fruit',start:0,end:5,speed:1,media_kind:'image',asset_id:''}]};
      window.fetch=async (url,options={})=>{
        const route=new URL(url).pathname.replace('/api/studio','');
        let data={};
        if(route==='/jobs/'+jobId)data={id:jobId,project_id:project.id,kind:'generate',status:reloadCount>1?'completed':'running',progress:reloadCount>1?100:10,
          events:[{agent:'Script writer',status:'running',message:'Writing explanation and example'}],
          result:reloadCount>1?{project,duration:5,timeline:[{start:0,end:5}],video_url:'/fixture-recovered.mp4'}:undefined};
        else if(route==='/projects')data=[project];
        else if(route==='/jobs')data=[];
        else if(options.method==='POST')throw new Error('Reload must not create a second job');
        return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
      };
    `;
    const root=path.resolve(__dirname,'..');
    const base=require('url').pathToFileURL(root+path.sep).href;
    const html=fs.readFileSync(path.join(root,'index.html'),'utf8').replace('<head>','<head><base href="'+base+'"><script>'+fixture+'</script>');
    const fixturePath=path.join(output,'generation-recovery-fixture.html');
    fs.writeFileSync(fixturePath,html);
    await win.loadFile(fixturePath);
    await new Promise(r=>setTimeout(r,600));
    if(!await win.webContents.executeJavaScript('SmartEditStudio.busy()'))throw new Error('Initial job not tracked');
    const loaded = new Promise(resolve=>win.webContents.once('did-finish-load',resolve));
    win.reload(); await loaded;
    await new Promise(r=>setTimeout(r,900));
    const result = await win.webContents.executeJavaScript(`({busy:SmartEditStudio.busy(),tracked:localStorage.getItem('smartedit.original.activeJob'),
      project:SmartEditStudio.getProject()?.id,narration:AgentPipeline.state.scenes[0]?.text,url:window.lastVideoDownloadUrl})`);
    if(result.busy||result.tracked||result.project!=='6'.repeat(32)||!result.narration.includes('कृत्रिम')||!result.url?.endsWith('/fixture-recovered.mp4'))throw new Error(JSON.stringify(result));
    fs.writeFileSync(path.join(output,'generation-recovery-result.json'),JSON.stringify({passed:true,...result},null,2));
    clearTimeout(deadline);
    await win.webContents.executeJavaScript('localStorage.clear()');
    app.exit(0);
  } catch(error) {
    fs.writeFileSync(path.join(output,'generation-recovery-error.txt'),String(error.stack));app.exit(1);
  }
});
