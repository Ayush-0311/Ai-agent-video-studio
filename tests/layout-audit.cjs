const {app,BrowserWindow} = require('electron');
const fs=require('fs'),path=require('path');
const out=path.resolve(__dirname,'../backend/studio-data/verification');
app.disableHardwareAcceleration();
app.setPath('userData',path.join(out,'layout-audit-profile'));
app.whenReady().then(async()=>{
 const win=new BrowserWindow({show:false,width:1253,height:850,webPreferences:{sandbox:true,contextIsolation:true,offscreen:true,backgroundThrottling:false}});
 const records=[];
 try{
  await win.loadFile(path.resolve(__dirname,'../index.html'));
  await win.webContents.executeJavaScript(`window.fetch=async url=>new Response(JSON.stringify(/\\/(projects|jobs)$/.test(new URL(url).pathname)?[]:{}));void 0;`);
  for(const [width,height] of [[1253,850],[1024,650],[800,600]]){
   win.setContentSize(width,height);
   for(const view of ['upload','settings','agents','library','dashboard','editor']){
    await win.webContents.executeJavaScript(`goTo(${JSON.stringify(view)});`);
    await new Promise(r=>setTimeout(r,350));
    const details=await win.webContents.executeJavaScript(`(()=>{
     const view=document.querySelector('.view.active');
     const clipped=[...view.querySelectorAll('button,input,select,textarea,[onclick]')].filter(e=>{
      const r=e.getBoundingClientRect();return r.width&&r.height&&r.top<innerHeight&&r.bottom>0&&(r.right>innerWidth+2||r.left<-2);
     }).map(e=>({id:e.id||e.tagName,right:Math.round(e.getBoundingClientRect().right),left:Math.round(e.getBoundingClientRect().left)}));
     const nestedClipped=[...view.querySelectorAll('button,input,select,textarea,[onclick]')].filter(e=>{
      const r=e.getBoundingClientRect();if(!r.width||!r.height||r.bottom<0||r.top>innerHeight)return false;
      for(let p=e.parentElement;p&&p!==view;p=p.parentElement){
       const c=getComputedStyle(p),b=p.getBoundingClientRect();
       if(['auto','scroll'].includes(c.overflowX))return false;
       if(['hidden','clip'].includes(c.overflowX)&&(r.right>b.right+2||r.left<b.left-2))return true;
      }return false;
     }).map(e=>e.id||e.tagName);
     const selects=[...view.querySelectorAll('select')].filter(e=>e.getBoundingClientRect().width&&e.options.length).map(e=>({id:e.id,color:getComputedStyle(e.options[0]).color,background:getComputedStyle(e.options[0]).backgroundColor,scheme:getComputedStyle(e).colorScheme}));
     return {clipped,nestedClipped,selects};
    })()`);
    records.push({width,height,view,...details});
    if(view==='editor')fs.writeFileSync(path.join(out,'editor-layout-'+width+'.png'),(await win.webContents.capturePage()).toPNG());
    if(view==='upload'){
     await win.webContents.executeJavaScript(`document.getElementById('upload-language').scrollIntoView({block:'center'});`);
     await new Promise(r=>setTimeout(r,100));
     fs.writeFileSync(path.join(out,'import-layout-'+width+'.png'),(await win.webContents.capturePage()).toPNG());
    }
   }
  }
  fs.writeFileSync(path.join(out,'layout-audit.json'),JSON.stringify(records,null,2));
  if(records.some(r=>r.clipped.length||r.nestedClipped.length))throw new Error('A control is clipped; see layout-audit.json');
  if(records.some(r=>r.selects.some(s=>s.scheme!=='dark'||s.background==='rgba(0, 0, 0, 0)')))throw new Error('Dropdown options lack a readable dark theme');
  const guideScreens=[];
  for(const [width,height] of [[1024,768],[390,844]]){
   win.setContentSize(width,height);await win.webContents.executeJavaScript('openCreationGuide()');await new Promise(r=>setTimeout(r,400));
   const guide=await win.webContents.executeJavaScript(`(()=>{const root=document.getElementById('creation-guide');const clipped=[...root.querySelectorAll('button,summary,h2,h3,p,li,dd')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&(r.left<0||r.right>innerWidth+1)}).map(e=>e.textContent.slice(0,50));const page=document.querySelector('#view-landing>.scroll-area');return {clipped,focused:document.activeElement.id,overflow:page.scrollWidth>page.clientWidth+1};})()`);
   if(guide.overflow||guide.clipped.length||guide.focused!=='creation-guide-title')throw Error('Starting guide clipped or unfocused: '+JSON.stringify(guide));
   fs.writeFileSync(path.join(out,'creation-guide-'+width+'.png'),(await win.webContents.capturePage()).toPNG());
   await win.webContents.executeJavaScript("document.querySelectorAll('.guide-settings details').forEach(e=>e.open=true);document.querySelector('.guide-settings').scrollIntoView({block:'start'})");await new Promise(r=>setTimeout(r,100));
   const settings=await win.webContents.executeJavaScript(`(()=>{const root=document.querySelector('.guide-settings');return [...root.querySelectorAll('dd,summary')].every(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1})})()`);
   if(!settings)throw Error('Expanded starting guide settings clipped');
   fs.writeFileSync(path.join(out,'creation-guide-settings-'+width+'.png'),(await win.webContents.capturePage()).toPNG());
   await win.webContents.executeJavaScript("document.querySelectorAll('.guide-settings details').forEach(e=>e.open=false)");guideScreens.push({width,height,passed:true});
  }
  win.setContentSize(800,500);
  const modal=await win.webContents.executeJavaScript(`(()=>{
   AgentPipeline._showVideoProgressModal('Layout check');
   const box=document.querySelector('#se-video-progress-modal>div');
   const extra=document.createElement('p');extra.textContent='Long progress details. '.repeat(300);box.append(extra);
   const r=box.getBoundingClientRect();
   return {top:r.top,bottom:r.bottom,height:innerHeight,scrollable:box.scrollHeight>box.clientHeight,overflow:getComputedStyle(box).overflowY};
  })()`);
  if(modal.top<0||modal.bottom>modal.height||!modal.scrollable||modal.overflow!=='auto')throw new Error('Tall production dialog cannot be reached');
  fs.writeFileSync(path.join(out,'layout-audit-result.json'),JSON.stringify({passed:true,screens:records.length,dropdowns:records.reduce((n,r)=>n+r.selects.length,0),shortWindowModal:modal,guideScreens},null,2));
  app.exit(0);
 }catch(e){fs.writeFileSync(path.join(out,'layout-audit-error.txt'),e.stack);app.exit(1);}
});
