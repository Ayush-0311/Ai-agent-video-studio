/* Run with the existing Electron executable. Tests the original UI, not a mock DOM. */
const { app, BrowserWindow } = require('electron');
const path = require('path');
const fs = require('fs');
const output = path.join(__dirname, '../backend/studio-data/verification');
fs.mkdirSync(output, { recursive: true });
app.disableHardwareAcceleration();
app.whenReady().then(async () => {
    const win = new BrowserWindow({ show: false, width: 1400, height: 960, webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true, offscreen: true, backgroundThrottling: false } });
    try {
        await win.loadFile(path.join(__dirname, '../index.html'));
        await new Promise(r => setTimeout(r, 1200));
        const result = await win.webContents.executeJavaScript(`(async()=>{
      let checks=0;const check=(condition,message)=>{checks++;if(!condition)throw new Error(message);};
      document.getElementById('gen-presenter-kind').value='illustrated';
      check(document.getElementById('gen-video-mode').value==='hybrid','Hybrid default missing');
      check(document.getElementById('gen-video-duration').value==='20','20 second default missing');
      const mode=document.getElementById('gen-video-mode'),duration=document.getElementById('gen-video-duration');
      mode.value='images';mode.dispatchEvent(new Event('change'));
      check(duration.max==='180','Image mode duration lost');
      duration.value='120';mode.value='motion';mode.dispatchEvent(new Event('change'));
      check(duration.max==='60'&&duration.value==='60','Motion budget not applied');
      duration.value='10';
      check(document.getElementById('gen-lipsync').disabled,'Unavailable lip-sync is enabled');
      check(document.querySelectorAll('#view-agents').length===1,'Duplicate agent view');
      check(document.querySelectorAll('#agent-grid').length===1,'Duplicate agent grid');
      check(document.querySelector('#view-editor .topbar'),'Original editor not present');
      check(getComputedStyle(document.getElementById('edit-agent-cancel')).display==='none','Idle edit assistant shows Cancel');
      const p={id:'a'.repeat(32),title:'Editor verification',prompt:'Test',language:'en',duration:15,aspect_ratio:'16:9',style:'cinematic',resolution:'720p',captions:true,brand:'',music_id:'',music_volume:.12,denoise:false,color:'natural',scenes:[{id:'b'.repeat(32),text:'One two three four',visual_prompt:'A test scene',asset_id:'c'.repeat(32),media_kind:'video',start:1,end:5,speed:1,mute:false},{id:'d'.repeat(32),text:'A second scene',visual_prompt:'Another test scene',asset_id:'c'.repeat(32),media_kind:'video',start:5,end:8,speed:1,mute:false}]};
      const timed=structuredClone(p); timed.scenes=timed.scenes.slice(0,1);
      Object.assign(timed.scenes[0],{start:0,end:8,text:'Hello world',caption_source_text:'Hello world',caption_words:[{text:'Hello',start:2,end:2.5},{text:'world',start:5,end:5.5}]});
      SmartEditStudio.loadProject(timed);
      check(document.getElementById('preview-total-duration').textContent==='0:08','Preview duration is not the actual timeline length');
      for(const [time,text] of [[1,''],[2.2,'Hello'],[3,''],[5.2,'world'],[7,'']]){
        currentTime=time;updatePlaybackUI();
        check(document.getElementById('subtitle-display').textContent===text,'Source caption timing wrong at '+time);
      }
      check(SmartEditStudio.collect().scenes[0].caption_words.length===2,'Saving drops source speech timestamps');
      Object.assign(AgentPipeline.state.scenes[0],{text:'Ready. Next sentence.',caption_source_text:'Ready. Next sentence.',caption_words:[{text:'Ready.',start:2,end:3},{text:'Next',start:3.15,end:3.5},{text:'sentence.',start:3.5,end:4}]});
      currentTime=2.5;updatePlaybackUI();
      check(document.getElementById('subtitle-display').textContent==='Ready.','Next sentence shown before speech');
      currentTime=3.3;updatePlaybackUI();
      check(document.getElementById('subtitle-display').textContent==='Next sentence.','Sentence change delayed');
      AgentPipeline.state.scenes[0].text='Manually edited';currentTime=3;updatePlaybackUI();
      check(document.getElementById('subtitle-display').textContent==='Manually edited','Stale speech text overrides edited caption');
      const storyboard=structuredClone(p);storyboard.scenes=[{...p.scenes[0],asset_id:'',start:0,end:20,text:'Imagine teaching a child to recognize apples. '.repeat(30)}];
      SmartEditStudio.loadProject(storyboard);goTo('editor');
      check(document.getElementById('preview-screen').classList.contains('is-storyboard'),'Missing storyboard script layout');
      check(getComputedStyle(document.getElementById('subtitle-display')).overflowY==='auto','Long storyboard text cannot scroll');
      check(document.querySelector('.editor-empty').hidden,'Empty placeholder overlaps storyboard script');
      check(document.getElementById('preview-total-duration').textContent==='0:20','Storyboard duration incorrect');
      SmartEditStudio.loadProject(p);
      check(!document.getElementById('preview-screen').classList.contains('is-storyboard'),'Storyboard layout leaked into source footage');
      selectClip(2);check(AgentPipeline.state.currentSceneIndex===1,'Selected agent target is incorrect');
      selectClip(1);currentTime=2;await splitClipAtPlayhead();
      check(AgentPipeline.state.scenes.length===3,'Split did not add a scene');
      let output=SmartEditStudio.collect();
      check(output.scenes[0].end===3&&output.scenes[1].start===3,'Split lost source time');
      check(output.scenes[0].text==='One two'&&output.scenes[1].text==='three four','Split duplicated transcript');
      selectClip(1);document.getElementById('custom-speed-input').value='2';await confirmSpeedChange();
      check(AgentPipeline.state.scenes[0].e-AgentPipeline.state.scenes[0].s===1,'Speed 2 duration incorrect');
      document.getElementById('custom-speed-input').value='1';await confirmSpeedChange();
      check(AgentPipeline.state.scenes[0].e-AgentPipeline.state.scenes[0].s===2,'Repeated speed compounded');
      await deleteSelectedClip();check(AgentPipeline.state.scenes[0].s===0,'Delete left a timeline gap');
      AgentPipeline.undo();check(AgentPipeline.state.scenes.length===3,'Undo failed');
      selectClip(1);toggleClipMute();check(SmartEditStudio.collect().scenes[0].mute,'Mute missing from export');
      goTo('agents');check(document.querySelectorAll('#agent-grid > *').length===28,'Missing agent cards');
      goTo('settings');check(document.getElementById('studio-image'),'Missing image connection');
      check(document.getElementById('studio-voice-gender'),'Missing narrator settings');
      check(document.getElementById('studio-image-quality').value==='high','High detail default missing');
      const connection=SmartEditStudio.decodeConnection('https://example.test/#smartedit='+btoa(JSON.stringify({token:'test-only',model:'qwen3.5:9b'})));
      check(connection.url==='https://example.test'&&connection.token==='test-only'&&connection.model==='qwen3.5:9b','One-paste connection parsing failed');
      const motionProject={...p,generation_mode:'motion',narration:false,style:'3D animation',scenes:[{...p.scenes[0],asset_id:'',media_kind:'image',start:0,end:5,text:''}]};
      SmartEditStudio.loadProject(motionProject);
      const motionPayload=SmartEditStudio.collect();
      check(motionPayload.generation_mode==='motion'&&motionPayload.narration===false&&motionPayload.style==='3D animation','Motion project settings lost in editor');
      SmartEditStudio.loadProject(p);
      let invalid=false;try{SmartEditStudio.decodeConnection('javascript:alert(1)');}catch{invalid=true;}check(invalid,'Unsafe connection URL accepted');
      // Exercise the real Generate button handler with isolated HTTP fixtures.
      // No external model or live project writes occur in this check.
      const originalFetch=window.fetch,calls=[];
      // Wrong-field paste and stale-session authentication must be recoverable.
      {
        const input=id=>document.getElementById(id);
        const fullLink='https://bridge.test/#smartedit='+btoa(JSON.stringify({token:'current-test-token',model:'test-model'}));
        let saved,puts=0;
        let health={ollama:false,image:false,voice:false,ffmpeg:true,models:[],bridge_connected:false,services:{language_model:{status:'auth_required',http_status:401,message:'Access token rejected. Paste the current ONE-PASTE CONNECTION LINK.'}},errors:['Access token rejected. Paste the current ONE-PASTE CONNECTION LINK.']};
        window.fetch=async(url,options={})=>{
          const route=new URL(url).pathname.replace('/api/studio','');
          if(route==='/settings'&&options.method==='PUT'){saved=JSON.parse(options.body);puts++;return new Response('{}');}
          if(route==='/settings')return new Response(JSON.stringify(saved));
          if(route==='/health')return new Response(JSON.stringify(health));
          throw new Error('Unexpected connection request '+route);
        };
        const closeReports=()=>document.querySelectorAll('.modal-overlay.open').forEach(el=>{if(el.textContent.includes('Connection check'))el.remove();});
        try{
          input('studio-ollama').value='https://bridge.test';input('studio-image').value='https://bridge.test';
          input('studio-token').value=fullLink;
          await saveSettings();
          check(saved?.bridge_token==='current-test-token'&&saved.model==='test-model','Full link was sent verbatim as bearer token');
          check(input('colab-status-text').textContent==='TOKEN REQUIRED','Authentication failure falsely labelled offline');
          check(input('colab-connect-msg').textContent.includes('ONE-PASTE'),'Authentication recovery instruction missing');
          check(!AgentPipeline.state.ollamaOnline,'Failed authentication left agents online');
          const originalToast=window.toast;let failureMessage='';
          try{
            window.toast=message=>{failureMessage=message;};input('gen-video-prompt').value='A robot walks through a city';
            await triggerFullVideoGeneration();
            check(failureMessage.includes('Access token rejected')&&!failureMessage.includes('T4 GPU'),'Generation hid the authentication failure behind a GPU error');
          }finally{window.toast=originalToast;}
          const report=[...document.querySelectorAll('.modal-overlay.open')].find(el=>el.textContent.includes('Connection check'));
          check(report?.textContent.includes('Not checked')&&!report.textContent.includes('T4 GPU'),'Auth failure incorrectly recommends a different GPU');closeReports();
          input('colab-url-input').value=fullLink;
          await checkColabStatus();
          check(input('colab-url-input').value===fullLink,'Status refresh overwrote the newly pasted link');
          health={ollama:true,image:true,voice:true,ffmpeg:true,models:['test-model'],bridge_connected:true,video_available:true,video_tested:true,errors:[]};
          await connectColab();
          check(input('colab-status-text').textContent==='ONLINE'&&AgentPipeline.state.ollamaOnline,'Valid connection did not restore online state');
          check(input('colab-connect-msg').textContent.includes('Motion encoded')&&input('colab-connect-msg').textContent.includes('review visual quality'),'Encoded motion must still require a visual quality review');
          check(input('colab-url-input').value==='https://bridge.test','Saved connection still exposes private link');closeReports();
          input('studio-token').value=fullLink.replace('bridge.test','other.test');const before=puts;
          await saveSettings();check(puts===before,'Mismatched-host token was sent to server');
          input('colab-url-input').value='https://new.test';
          await connectColab();check(puts===before&&!input('studio-token').value,'Base URL change reused another server token');
          input('colab-url-input').value=fullLink;await connectColab();closeReports();
          const beforeProject=JSON.stringify(SmartEditStudio.collect());
          input('studio-brand').value='Unapplied setting';input('colab-url-input').value=fullLink;
          await connectColab();check(JSON.stringify(SmartEditStudio.collect())===beforeProject,'Connection check changed video edits');closeReports();
          check(!input('colab-connect-btn').disabled,'Connection button remained disabled');
        }finally{window.fetch=originalFetch;closeReports();}
      }
      // Named voice settings must reach the same preview/render configuration.
      {
        const el=id=>document.getElementById(id);let preferences,previewBody;
        const originalPlay=HTMLMediaElement.prototype.play;
        HTMLMediaElement.prototype.play=async()=>{};
        window.fetch=async(url,options={})=>{
          const route=new URL(url).pathname.replace('/api/studio','');
          if(route==='/local-health')return new Response(JSON.stringify({production_api:17}));
          if(route==='/voice-settings'&&options.method==='PUT'){preferences=JSON.parse(options.body);return new Response('{}');}
          if(route==='/voice-preview'){previewBody=JSON.parse(options.body);return new Response(JSON.stringify({url:'/api/studio/assets/voice-fixture',voice:{voice:'hi-IN-SwaraNeural',profile_matched:true}}));}
          throw new Error('Unexpected voice preview route '+route);
        };
        try{
          el('studio-voice-engine').value='neural';el('studio-voice-engine').dispatchEvent(new Event('change'));
          el('studio-voice-profile').value='hi-swara';el('studio-voice-profile').dispatchEvent(new Event('change'));
          el('studio-voice-delivery').value='calm';el('studio-voice-normalize').value='true';
          check(el('studio-voice-language').value==='hi','Named Hindi voice did not select Hindi sample');
          await el('studio-save-voice').onclick();
          check(preferences.voice_profile==='hi-swara'&&!('ollama_url' in preferences),'Voice save depends on or changes Colab settings');
          await el('studio-hear-voice').onclick();
          check(preferences.voice_profile==='hi-swara'&&preferences.voice_engine==='neural'&&preferences.voice_delivery==='calm'&&preferences.voice_normalize,'Voice settings were lost before preview');
          check(previewBody.language==='hi'&&previewBody.text.includes('नमस्ते'),'Wrong sample language sent');
          check(el('studio-voice-sample').src.endsWith('/voice-fixture')&&el('studio-voice-result').textContent.includes('Swara'),'Playable named sample missing');
          check(!el('studio-hear-voice').disabled,'Voice preview button stayed disabled');
          check(el('studio-voice-engine').tagName==='SELECT'&&el('studio-voice-engine').value==='neural','Voice engine preference was not preserved');
          el('studio-voice-engine').value='bridge';el('studio-voice-engine').dispatchEvent(new Event('change'));
          check(el('studio-voice-profile').disabled&&el('studio-voice-delivery').disabled,'Edge-only settings remain active for OmniVoice');
          await el('studio-save-voice').onclick();
          check(preferences.voice_engine==='bridge','OmniVoice bridge selection was not saved');
          el('studio-voice-engine').value='neural';el('studio-voice-engine').dispatchEvent(new Event('change'));
          check(!el('studio-voice-profile').disabled&&!el('studio-voice-delivery').disabled,'Named voice controls are disabled');
          check(SmartEditStudio.fresh().narration_timing==='exact','New videos should fit narration to the selected duration');
          {
            const names=['gen-video-prompt','gen-video-duration','gen-video-mode','gen-video-lang','gen-video-ratio','edit-ai-scene-type','gen-narration-timing','gen-auto-music'];
            const saved=Object.fromEntries(names.map(id=>[id,el(id).value]));
            const reference=el('gen-character-reference').checked;
            el('edit-ai-scene-type').value='auto';
            el('gen-video-prompt').value='Generate all images automatically.\\n**0–20 sec:** Visual: A man at night. Voiceover: “चलते रहो।” Text: “KEEP GOING”\\n**20–60 sec:** Visual: The same man at sunrise. Voiceover: “हार मत मानो।” Text: “BELIEVE”\\nUse background music, consistent character appearance, vertical 9:16.';
            el('gen-video-prompt').value=el('gen-video-prompt').value.replaceAll('\\\\n','\\n');
            el('gen-video-prompt').dispatchEvent(new Event('input'));
            const timed=SmartEditStudio.fresh();
            check(timed.scene_mode==='ready'&&timed.duration===60,'Timed script did not set its duration');
            check(timed.aspect_ratio==='9:16'&&timed.language==='hi'&&timed.generation_mode==='images','Timed script instructions were lost');
            check(timed.auto_music==='cinematic'&&timed.character_reference,'Requested music/reference defaults missing');
            el('gen-auto-music').value='off';el('gen-auto-music').dispatchEvent(new Event('change'));
            el('gen-character-reference').checked=false;el('gen-character-reference').dispatchEvent(new Event('change'));
            check(SmartEditStudio.fresh().auto_music==='off'&&!SmartEditStudio.fresh().character_reference,'Explicit choices were overwritten by script hints');
            for(const id of names)el(id).value=saved[id];
            el('gen-character-reference').checked=reference;
            el('gen-video-mode').dispatchEvent(new Event('change'));
            el('edit-ai-scene-type').dispatchEvent(new Event('change'));
          }
          el('studio-voice-engine').value='neural';el('studio-voice-engine').dispatchEvent(new Event('change'));
          el('studio-voice-profile').value='auto';el('studio-voice-delivery').value='natural';
        }finally{window.fetch=originalFetch;HTMLMediaElement.prototype.play=originalPlay;}
      }
      const storyId='e'.repeat(32),renderId='f'.repeat(32);
      let planned,rendered,repairNextPreview=false;
      window.fetch=async(url,options={})=>{
        const route=new URL(url).pathname.replace('/api/studio','');
        calls.push(route);
        let body={};
        if(route==='/health')body={video_available:true,motion_presets:['preview','balanced','quality'],ollama:true,image:true,voice:true,ffmpeg:true};
        else if(route==='/local-health')body={production_api:17};
        else if(route==='/plan'){
          planned=JSON.parse(options.body);
          body={id:storyId};
        }else if(route==='/jobs/'+storyId)body={id:storyId,status:'completed',progress:100,events:[],result:{...planned,title:'Robot city',scenes:[{id:'1'.repeat(32),text:'',visual_prompt:'A silver robot walks, tracking shot',asset_id:'',media_kind:'image',start:0,end:5,speed:1,mute:false}]}};
        else if(route==='/generate'){
          const payload=JSON.parse(options.body);
          if(!payload.scenes.length){planned=payload;rendered={...payload,title:'Robot city',scenes:[{id:'1'.repeat(32),text:'',visual_prompt:'A silver robot walks, tracking shot',asset_id:'',media_kind:'image',start:0,end:5,speed:1,mute:false}]};}
          else rendered=payload;
          body={id:renderId};
        }else if(route==='/render'){
          rendered=JSON.parse(options.body);
          if(repairNextPreview){
            rendered.scenes[0].text='Sea turtles return to their nesting beach.';
            rendered.scenes[0].visual_prompt='A sea turtle emerging onto its nesting beach, no text.';
            rendered.scenes[0].slide_title='Nesting beach';
            rendered.scenes[0].slide_points=['Turtles return to shore'];
            rendered.production_notes={visual_alignment:{status:'reviewed',fingerprint:'fixture-reviewed'}};
            repairNextPreview=false;
          }
          body={id:renderId};
        }
        else if(route==='/jobs/'+renderId)body={id:renderId,status:'completed',progress:100,events:[],result:{project:rendered,duration:5,timeline:[{start:0,end:5}],scene_assets:[],video_url:'/api/studio/jobs/'+renderId+'/file/video',subtitles_url:'/api/studio/jobs/'+renderId+'/file/subtitles',metadata_url:'/api/studio/jobs/'+renderId+'/file/metadata'}};
        else if(route==='/projects'||route==='/jobs')body=[];
        else throw new Error('Unexpected request during UI test: '+route);
        return new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}});
      };
      try{
        document.getElementById('gen-video-prompt').value='AI';
        document.getElementById('gen-narration').checked=false;
        document.getElementById('gen-captions').checked=false;
        document.getElementById('gen-video-style').selectedIndex=1;
        await triggerFullVideoGeneration();
        check(planned?.generation_mode==='motion'&&planned.duration===10,'Generate did not plan short motion');
        check(planned.prompt==='AI','Short topic was rejected or changed');
        check(rendered?.generation_mode==='motion'&&rendered.narration===false&&rendered.captions===false,'Generate lost motion/voice/caption options');
        check(rendered.duration_mode==='target','New generation did not enforce selected duration');
        document.getElementById('gen-narration').dispatchEvent(new Event('change'));
        check(document.getElementById('gen-voice-status').textContent.includes('Voice off'),'Silent generation is not clearly indicated');
        check(rendered.style.includes('3D animation'),'Style was not sent to director/render');
        check(window.lastVideoDownloadUrl?.includes(renderId),'Completed motion result not exposed');
        check(!document.getElementById('gen-video-btn').disabled,'Generate remained disabled');
        const fields=id=>document.getElementById(id);
        for(let i=0;i<5;i++){
          fields('gen-video-mode').value=i%2?'images':'motion';fields('gen-video-mode').dispatchEvent(new Event('change'));
          fields('gen-video-duration').value='15';
          fields('gen-video-style').selectedIndex=i;
          fields('gen-video-lang').value=['en','hi','es','fr','de'][i];
          fields('gen-video-ratio').value=['16:9','9:16','1:1'][i%3];
          fields('gen-avatar-style').value=['none','realistic','cartoon'][i%3];
          fields('edit-ai-scene-type').value=['auto','sentences','paragraphs','manual','auto'][i];
          fields('edit-ai-scene-type').dispatchEvent(new Event('change'));
          fields('gen-narration').checked=i%2===0;fields('gen-captions').checked=i!==2;
          await triggerFullVideoGeneration();
          for(const payload of [planned,rendered]){
            check(payload.language===fields('gen-video-lang').value,'Language lost');
            check(payload.aspect_ratio===fields('gen-video-ratio').value,'Format lost');
            check(payload.scene_mode===fields('edit-ai-scene-type').value,'Scene split mode lost');
            check(payload.duration===15&&payload.generation_mode===fields('gen-video-mode').value,'Duration/mode lost');
            check(payload.style.startsWith(fields('gen-video-style').value),'Visual style lost');
            check(payload.narration===fields('gen-narration').checked&&payload.captions===fields('gen-captions').checked,'Independent caption/voice options lost');
            if(i%3===1)check(payload.style.includes('realistic human presenter'),'Presenter preference lost');
            if(i%3===2)check(payload.style.includes('3D animated character'),'Avatar preference lost');
          }
        }
        fields('gen-video-prompt').value='Sun';
        calls.length=0;await generateScriptWithAI();
        check(calls.includes('/plan')&&!calls.includes('/render'),'Plan scenes should open storyboard without rendering');
        check(planned.prompt==='Sun','Short topic did not reach the planner');
        AgentPipeline.state.scenes[0].text='My reviewed narration';
        calls.length=0;await triggerFullVideoGeneration();
        check(!calls.includes('/plan')&&rendered.scenes[0].text==='My reviewed narration','Generate replanned or discarded reviewed Plan scenes edits');
        check(rendered.duration_mode==='target','Reviewed storyboard lost selected duration on Generate');
        calls.length=0;fields('gen-video-mode').value='hybrid';fields('gen-video-duration').value='20';fields('gen-motion-preset').value='preview';
        fields('gen-video-prompt').value='An ocean research story with a moving opening shot';
        repairNextPreview=true;
        await previewGeneration();
        check(rendered.generation_mode==='images'&&rendered.resolution==='720p','Image preview invoked heavy motion generation');
        check(SmartEditStudio.collect().generation_mode==='hybrid'&&SmartEditStudio.collect().motion_preset==='preview','Preview overwrote selected final settings');
        const draftId=rendered.id;await triggerFullVideoGeneration();
        check(rendered.generation_mode==='hybrid'&&rendered.motion_preset==='preview','Final hybrid/preset selection was lost');
        check(rendered.scenes[0].visual_prompt==='A sea turtle emerging onto its nesting beach, no text.'&&rendered.scenes[0].text==='Sea turtles return to their nesting beach.','Preview narration/image repair was lost in final generation');
        check(rendered.production_notes.visual_alignment.fingerprint==='fixture-reviewed','Final generation lost the preview relevance review');
        check(rendered.id!==draftId&&calls.filter(c=>c==='/plan').length===1,'Preview was saved over the final project or unnecessarily replanned');
        fields('gen-motion-preset').value='balanced';
        AgentPipeline.state.scenes[0].vis.query='Reviewed opening composition';
        calls.length=0;await triggerFullVideoGeneration();
        check(!calls.includes('/plan')&&rendered.motion_preset==='balanced'&&rendered.scenes[0].visual_prompt==='Reviewed opening composition','Changing render detail replanned the story, lost edits or kept old preset');
        fields('gen-video-prompt').value='A completely new mountain expedition story';
        calls.length=0;await triggerFullVideoGeneration();
        check(calls.includes('/generate')&&!calls.includes('/plan')&&rendered.prompt===fields('gen-video-prompt').value,'A changed brief did not use durable generation');
        fields('gen-video-mode').value='avatar';fields('gen-video-mode').dispatchEvent(new Event('change'));
        fields('gen-presenter-layout').value='pip-left';fields('gen-presenter-character').value='maya';fields('gen-presenter-theme').value='teal';
        check(!fields('gen-presenter-options').hidden&&fields('gen-motion-preset').disabled&&fields('gen-narration').checked,'Avatar controls or narration default missing');
        check(fields('gen-video-duration').max==='180'&&fields('avatar-lipsync-row').hidden,'Avatar kept motion duration limit or misleading lip-sync warning');
        const normalFetch=window.fetch;
        window.fetch=async(url,options)=>new URL(url).pathname.endsWith('/health')?new Response(JSON.stringify({ollama:true,image:true,voice:true,ffmpeg:true,video_available:false})):normalFetch(url,options);
        repairNextPreview=true;
        calls.length=0;await previewGeneration();
        check(rendered.generation_mode==='avatar'&&rendered.presenter_layout==='pip-left'&&rendered.presenter_character==='maya'&&rendered.presenter_theme==='teal','Explainer preview lost presenter options');
        check(rendered.resolution==='720p','Explainer preview resolution incorrect');
        await triggerFullVideoGeneration();
        check(rendered.generation_mode==='avatar'&&calls.filter(c=>c==='/plan').length===1,'Avatar requires Wan or replans after preview');
        check(rendered.scenes[0].slide_title==='Nesting beach'&&rendered.scenes[0].slide_points[0]==='Turtles return to shore','Preview slide repair was lost before final generation');
        selectClip(1);fields('slide-title').value='Solar power';fields('slide-points').value='Sunlight becomes electricity';fields('slide-narration').value='Here is how solar panels work.';
        fields('slide-title').closest('form').requestSubmit();
        let savedSlide=SmartEditStudio.collect();
        check(savedSlide.scenes[0].slide_title==='Solar power'&&savedSlide.scenes[0].slide_points[0]==='Sunlight becomes electricity','Slide editor did not persist heading and bullets');
        SmartEditStudio.loadProject(structuredClone(savedSlide));selectClip(1);
        check(fields('slide-title').value==='Solar power'&&fields('slide-narration').value==='Here is how solar panels work.','Explainer fields lost on reload');
        fields('editor-presenter-layout').value='side';fields('editor-presenter-layout').closest('form').requestSubmit();
        check(SmartEditStudio.collect().presenter_layout==='side','Editor presenter layout not applied');
        undoEdit();check(SmartEditStudio.collect().presenter_layout==='pip-left','Presenter setting undo failed');
        window.fetch=normalFetch;
        fields('gen-video-mode').value='motion';fields('gen-video-duration').value='10';fields('edit-ai-scene-type').value='auto';
        fields('gen-video-mode').dispatchEvent(new Event('change'));
        fields('edit-ai-scene-type').dispatchEvent(new Event('change'));
        await new Promise(resolve=>setTimeout(resolve,0));
        calls.length=0;
        window.fetch=async(url)=>{calls.push(new URL(url).pathname);return new Response(JSON.stringify({video_available:false}),{headers:{'Content-Type':'application/json'}});};
        await triggerFullVideoGeneration();
        check(calls.length===1&&calls[0].endsWith('/health'),'Old bridge should stop before planning/rendering');
      }finally{window.fetch=originalFetch;}
      // An unresponsive connection must time out or cancel, with usable progress after closing the modal.
      try{
        window.fetch=async(url,options)=>new Promise((resolve,reject)=>{
          options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true});
        });
        let timedOut=false;
        try{await SmartEditStudio.api('/health','GET',undefined,{timeout:25});}catch(e){timedOut=e.message.includes('did not respond in time');}
        check(timedOut,'Connection request can spin forever');
        const pending=triggerFullVideoGeneration();
        await new Promise(r=>setTimeout(r,10));
        document.getElementById('se-video-progress-modal').remove();
        document.getElementById('studio-generation-status').click();
        check(!!document.getElementById('studio-cancel-job'),'Closed production modal cannot reopen with cancellation');
        await document.getElementById('studio-cancel-job').onclick();
        await pending;
        check(!SmartEditStudio.busy()&&!document.getElementById('gen-video-btn').disabled,'Cancelling preflight leaves Generate locked');
        check(document.getElementById('studio-generation-status').textContent.includes('cancelled'),'Cancellation result is hidden');
      }finally{window.fetch=originalFetch;}
      // Failed job recovery must not leave future work permanently locked.
      try{
        const missingId='9'.repeat(32);
        window.fetch=async()=>new Response(JSON.stringify({detail:'Job not found'}),{status:404});
        let missing=false;try{await SmartEditStudio.watch({id:missingId});}catch(e){missing=e.message.includes('tracking was cleared');}
        check(missing&&!SmartEditStudio.busy()&&!localStorage.getItem('smartedit.original.activeJob'),'Missing job left the editor locked');
        window.fetch=async()=>{throw new TypeError('Network unavailable');};
        try{await SmartEditStudio.watch({id:missingId});}catch{}
        check(SmartEditStudio.busy()&&localStorage.getItem('smartedit.original.activeJob')===missingId,'Network failure discarded recoverable job');
        window.fetch=async()=>new Response(JSON.stringify({detail:'Gone'}),{status:410});
        try{await SmartEditStudio.watch({id:missingId});}catch{}
        check(!SmartEditStudio.busy(),'Gone job left the editor locked');
        const unsafeName='<img src=x onerror=alert(1)>.mp4';
        handleFileChosen(new File(['test'],unsafeName,{type:'video/mp4'}));
        const ready=document.getElementById('dz-file-ready');
        check(ready.textContent.includes(unsafeName)&&!ready.querySelector('img'),'File name was interpreted as HTML');
        let transcribed,uploadedProject;
        window.fetch=async(url,options={})=>{
          const route=new URL(url).pathname.replace('/api/studio','');let body={};
          if(route==='/local-health')body={production_api:17};
          else if(route==='/assets')body={id:'8'.repeat(32),name:'test.mp4',kind:'video',duration:10};
          else if(route.startsWith('/projects/'))uploadedProject=JSON.parse(options.body);
          else if(route==='/transcribe'){transcribed=JSON.parse(options.body);body={id:missingId};}
          else if(route==='/jobs/'+missingId)body={status:'completed',progress:100,events:[],result:{...uploadedProject,captions:true}};
          else throw new Error('Unexpected import request '+route);
          return new Response(JSON.stringify(body));
        };
        document.getElementById('upload-language').value='hi';
        document.getElementById('upload-transcribe').checked=true;
        await startProcessingFlow();
        check(transcribed?.project.language==='hi'&&transcribed.remove_silence===false,'Transcription options did not reach backend');
        check(SmartEditStudio.getProject()?.captions===true,'Transcription result not loaded');
        transcribed=null;await openInEditorDirectly();
        check(transcribed===null&&!SmartEditStudio.getProject().captions,'Direct editor import unexpectedly transcribed');
        let dubbed;
        const toggle=document.getElementById('upload-translate');toggle.checked=true;toggle.dispatchEvent(new Event('change'));
        check(!document.getElementById('upload-target-wrap').hidden,'Dubbing language control hidden');
        check(document.getElementById('upload-action-label').textContent==='Translate & dub video','Dubbing action label missing');
        document.getElementById('upload-language').value='en';
        document.getElementById('upload-target-language').value='hi';
        window.fetch=async(url,options={})=>{
          const route=new URL(url).pathname.replace('/api/studio','');let body={};
          if(route==='/local-health')body={production_api:17};
          else if(route==='/assets')body={id:'8'.repeat(32),name:'English.mp4',kind:'video',duration:10};
          else if(route.startsWith('/projects/'))uploadedProject=JSON.parse(options.body);
          else if(route==='/projects')body=[];
          else if(route==='/dub'){dubbed=JSON.parse(options.body);body={id:missingId};}
          else if(route==='/jobs/'+missingId)body={id:missingId,kind:'dub',status:'completed',progress:100,events:[],result:{project:{...uploadedProject,language:'hi',captions:true},timeline:[],duration:10,video_url:'/api/studio/jobs/'+missingId+'/file/video'}};
          return new Response(JSON.stringify(body));
        };
        await startProcessingFlow();
        check(dubbed?.project.language==='en'&&dubbed.target_language==='hi'&&dubbed.captions,'Dubbing options did not reach backend');
        check(SmartEditStudio.getProject().language==='hi'&&window.lastVideoDownloadUrl,'Dubbed export not loaded');
        toggle.checked=false;toggle.dispatchEvent(new Event('change'));
        check(document.getElementById('upload-target-wrap').hidden,'Dubbing controls remain active on ordinary import');

      }finally{window.fetch=originalFetch;}
      try{
        const records=[{kind:'render',status:'completed',progress:100,project_id:p.id,result:{video_url:'/api/studio/jobs/test/file/video'}},{kind:'storyboard',status:'failed',progress:0,error:'Planner unavailable'},{kind:'render',status:'running',progress:40}];
        window.fetch=async(url)=>new Response(JSON.stringify(new URL(url).pathname.endsWith('/projects')?[p]:records));
        await initAnalytics();
        const activity=document.querySelector('#view-analytics .scroll-area');
        check([...activity.querySelectorAll('.stat-kpi')].map(e=>e.textContent).join(',')==='1,1,1,1','Analytics counts do not match saved records');
        check(activity.textContent.includes('Planner unavailable')&&activity.querySelector('a')?.href.includes('/jobs/test/file/video'),'Analytics lost job error or completed download');
        await refreshStudioProjects();
        check(document.getElementById('dash-total-videos').textContent==='1'&&document.getElementById('dash-confidence').textContent==='1','Dashboard counts not refreshed');
        window.fetch=async()=>{throw new Error('Backend offline');};
        await initAnalytics();
        check(activity.textContent.includes('Activity unavailable')&&activity.querySelector('button').textContent==='Retry'&&!activity.querySelector('.stat-kpi'),'Analytics displays fabricated success while offline');
      }finally{window.fetch=originalFetch;}
      // Every agent card must dispatch to the production adapter, never legacy simulated handlers.
      const savedHandlers={ask:window.smartEditAsk,generate:window.triggerFullVideoGeneration,plan:window.generateScriptWithAI,export:window.startExport,audio:window.addAudioTrack};
      try{
        const hit=[],agentJob='7'.repeat(32);let requestProject,agentRequest;
        window.smartEditAsk=async()=> 'hi';
        window.fetch=async(url,options={})=>{
          const route=new URL(url).pathname.replace('/api/studio','');let body={};
          if(route==='/local-health')body={production_api:17};
          else if(route==='/agents')body=[];
          else if(route==='/agent-run'){
            agentRequest=JSON.parse(options.body);requestProject=structuredClone(agentRequest.project);
            requestProject.production_notes={specialists:{[agentRequest.agent]:{summary:'Scoped review'}}};body={id:agentJob};hit.push(agentRequest.agent);
          }else if(route==='/transcribe'||route==='/visual'){
            requestProject=JSON.parse(options.body).project;body={id:agentJob};hit.push(route);
          }else if(route==='/voice-preview'){hit.push('voice');body={url:'/api/studio/assets/sample'};}
          else if(route==='/jobs/'+agentJob)body={status:'completed',progress:100,events:[],result:requestProject};
          else if(route==='/projects'||route==='/jobs')body=[];
          else throw new Error('Agent used unexpected route '+route);
          return new Response(JSON.stringify(body));
        };
        const specialistIds=['layout_planner','script_optimizer','multi_language','viral_hook','seo_metadata','thumbnail_gen','broll_suggestion','emotion_analysis','slide_generator','conversation_mode','viral_clip','avatar_generator','chapter_marker'];
        for(const id of specialistIds){
          SmartEditStudio.loadProject(structuredClone(p));await triggerAgent(id);
          check(agentRequest.agent===id&&hit.includes(id),'Specialist not independently dispatched: '+id);
          check(SmartEditStudio.getProject().scenes[0].text===p.scenes[0].text,'Review unexpectedly rewrote scene text');
          if(id==='multi_language')check(agentRequest.language==='hi','Translation target missing');
          document.querySelectorAll('.modal-overlay.open').forEach(e=>e.remove());
        }
        for(const id of ['caption','scene_detection','jump_cut','image_generator','voice']){
          SmartEditStudio.loadProject(structuredClone(p));selectClip(1);const before=hit.length;
          await triggerAgent(id);check(hit.length===before+1,'Media agent not dispatched: '+id);
          document.querySelectorAll('.modal-overlay.open').forEach(e=>e.remove());
        }
        window.triggerFullVideoGeneration=async()=>hit.push('orchestrator');window.generateScriptWithAI=async()=>hit.push('script');
        window.startExport=async()=>hit.push('export');window.addAudioTrack=()=>hit.push('music');
        for(const id of ['orchestrator','script','compositor','export_optimizer','music_sound']){const before=hit.length;await triggerAgent(id);check(hit.length===before+1,'Workflow agent disconnected: '+id);}
        for(const id of ['brand_kit','color_grading','nl_edit']){goTo('upload');await triggerAgent(id);check(currentView==='editor','Editor tool did not open: '+id);}
        SmartEditStudio.loadProject(structuredClone(p));await triggerAgent('noise_reduction');
        check(SmartEditStudio.collect().denoise===true,'Denoising not enabled');
        undoEdit();check(!SmartEditStudio.collect().denoise,'Denoising cannot be undone');
        renderAgentGrid('all');check(!document.getElementById('run-btn-lip_sync').disabled,'Presenter setup tool is inaccessible');
        await triggerAgent('lip_sync');check(document.getElementById('gen-video-mode').value==='avatar'&&document.getElementById('gen-presenter-kind').value==='realistic','Lip-sync tool did not open presenter setup');
          document.getElementById('gen-presenter-kind').value='illustrated';document.getElementById('gen-video-mode').value='hybrid';document.getElementById('gen-video-mode').dispatchEvent(new Event('change'));
        check(!document.getElementById('agent-grid').textContent.includes('Uptime:'),'Fabricated agent uptime remains');
      }finally{
        window.fetch=originalFetch;window.smartEditAsk=savedHandlers.ask;window.triggerFullVideoGeneration=savedHandlers.generate;
        window.generateScriptWithAI=savedHandlers.plan;window.startExport=savedHandlers.export;window.addAudioTrack=savedHandlers.audio;
      }
      SmartEditStudio.loadProject({...structuredClone(p),transition:'cut',scenes:[{...p.scenes[0],start:0,end:4,speed:1,effects:{}}]});selectClip(1);
      document.getElementById('fx-region').value='blur';document.getElementById('fx-x').value='0';document.getElementById('fx-end_x').value='100';
      document.getElementById('clip-source-in').closest('form').requestSubmit();
      check(SmartEditStudio.collect().scenes[0].effects.region==='blur','Effect controls did not reach project');
      document.getElementById('editor-transition').value='fade_black';document.getElementById('editor-transition-duration').value='.4';
      document.getElementById('editor-ratio').closest('form').requestSubmit();
      check(SmartEditStudio.collect().transition==='fade_black'&&SmartEditStudio.collect().transition_duration===.4,'Transition setting missing');
      undoEdit();check((SmartEditStudio.collect().transition||'cut')==='cut','Transition undo failed');redoEdit();
      const withEffects=structuredClone(SmartEditStudio.collect());SmartEditStudio.loadProject(withEffects);selectClip(1);
      check(SmartEditStudio.collect().scenes[0].effects.end_x===1,'Effect lost on reload');
      currentTime=2;await splitClipAtPlayhead();
      check(SmartEditStudio.collect().scenes[0].effects.end_x===.5&&SmartEditStudio.collect().scenes[1].effects.x===.5,'Split restarted effect motion');
      SmartEditEditor.setRange(3,4,1);
      check(SmartEditStudio.collect().scenes[1].effects.x===.75,'Trim restarted effect motion');
      document.getElementById('se-video-progress-modal')?.remove();
      goTo('editor');
      return {checks,activeView:currentView,scenes:AgentPipeline.state.scenes.length,originalEditor:true};
    })()`);
        await new Promise(r => setTimeout(r, 600));
        const visible = await win.webContents.executeJavaScript("({editor:getComputedStyle(document.getElementById('view-editor')).display,landing:getComputedStyle(document.getElementById('view-landing')).display})");
        if (visible.editor === 'none' || visible.landing !== 'none')
            throw new Error('Navigation visibility failed: ' + JSON.stringify(visible));
        const image = await win.webContents.capturePage();
        fs.writeFileSync(path.join(output, 'original-editor.png'), image.toPNG());
        await win.webContents.executeJavaScript("goTo('upload');document.getElementById('gen-video-mode').scrollIntoView({block:'center'});");
        await new Promise(r => setTimeout(r, 300));
        fs.writeFileSync(path.join(output, 'motion-controls.png'), (await win.webContents.capturePage()).toPNG());
        await win.webContents.executeJavaScript("document.querySelectorAll('.toast').forEach(e=>e.remove());document.getElementById('gen-video-duration').dispatchEvent(new Event('input'));");
        const layouts = [];
        for (const [width, height] of [[1366,768], [1024,768], [800,700], [390,844]]) {
            win.setContentSize(width, height);
            await new Promise(r => setTimeout(r, 180));
            const layout = await win.webContents.executeJavaScript(`(()=>{try{
                const panel=document.getElementById('generation-panel');
                panel.scrollIntoView({block:'start'});
                const page=document.querySelector('#view-upload .generation-page');
                const ids=['gen-video-prompt','gen-video-mode','gen-video-style','gen-video-ratio','gen-video-lang','gen-avatar-style','gen-video-duration','gen-video-btn'];
                for(const id of ids){
                    const e=document.getElementById(id),r=e.getBoundingClientRect();
                    if(r.width<30||r.height<20||r.left<0||r.right>innerWidth+1)throw new Error('Clipped generation control: '+id+' at '+innerWidth);
                }
                if(page.scrollWidth>page.clientWidth+1)throw new Error('Horizontal page overflow at '+innerWidth);
                const button=document.getElementById('gen-video-btn').getBoundingClientRect();
                if(innerWidth>=1024 && (button.bottom>innerHeight||button.top<0))throw new Error('Generate button outside laptop viewport');
                const character=document.getElementById('gen-avatar-style');
                character.value='cartoon';character.dispatchEvent(new Event('change'));
                if(document.getElementById('avatar-lipsync-row').hidden)throw new Error('Character note did not open');
                character.value='none';character.dispatchEvent(new Event('change'));
                if(!document.getElementById('avatar-lipsync-row').hidden)throw new Error('Character note did not close');
                return {width:innerWidth,height:innerHeight,panelHeight:Math.round(panel.getBoundingClientRect().height),horizontalOverflow:false};
            }catch(e){return {error:e.message,overflow:[...document.querySelectorAll('#view-upload *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>e.id||e.className).slice(0,12)};}})()`);
            layouts.push(layout);
            await new Promise(r => setTimeout(r, 150));
            fs.writeFileSync(path.join(output, `generation-${width}.png`), (await win.webContents.capturePage()).toPNG());
            if(layout.error)throw new Error(JSON.stringify(layout));
            if(width>=1024){
                const bottom=await win.webContents.executeJavaScript("document.querySelector('#view-upload .generation-page').scrollTop=0;document.getElementById('gen-video-btn').getBoundingClientRect().bottom;");
                await new Promise(r=>setTimeout(r,100));
                fs.writeFileSync(path.join(output, `generation-overview-${width}.png`), (await win.webContents.capturePage()).toPNG());
                if(bottom>height)throw new Error(`Generate button requires scrolling at ${width}: ${bottom}`);
            }
        }
        result.generationLayouts = layouts;
        result.avatarLayouts=[];
        for(const [width,height] of [[1366,768],[1024,768],[800,700],[390,844]]){
            win.setContentSize(width,height);
            const details=await win.webContents.executeJavaScript(`(()=>{
                const mode=document.getElementById('gen-video-mode');mode.value='avatar';mode.dispatchEvent(new Event('change'));
                const panel=document.getElementById('generation-panel');panel.scrollIntoView({block:'start'});
                for(const id of ['gen-presenter-layout','gen-presenter-character','gen-presenter-theme','gen-preview-btn','gen-video-btn']){
                    const r=document.getElementById(id).getBoundingClientRect();
                    if(r.width<30||r.left<0||r.right>innerWidth+1)throw new Error('Avatar control clipped: '+id);
                }
                const page=document.querySelector('#view-upload .generation-page');
                if(page.scrollWidth>page.clientWidth+1)throw new Error('Avatar horizontal overflow');
                return {width:innerWidth,height:innerHeight,horizontalOverflow:false};
            })()`);
            await new Promise(r=>setTimeout(r,180));
            fs.writeFileSync(path.join(output,`avatar-controls-${width}.png`),(await win.webContents.capturePage()).toPNG());
            result.avatarLayouts.push(details);
        }
        win.setContentSize(1366,900);
        await win.webContents.executeJavaScript(`openCreationPath('import');handleFileChosen(new File(['test'],'English lesson.mp4',{type:'video/mp4'}));document.getElementById('upload-translate').checked=true;document.getElementById('upload-translate').dispatchEvent(new Event('change'));document.getElementById('upload-options-title').scrollIntoView({block:'center'});document.querySelectorAll('.toast').forEach(e=>e.remove());`);
        await new Promise(r=>setTimeout(r,180));
        fs.writeFileSync(path.join(output,'import-dubbing-controls.png'),(await win.webContents.capturePage()).toPNG());
        fs.writeFileSync(path.join(output, 'ui-result.json'), JSON.stringify(result, null, 2));
        console.log(JSON.stringify(result));
        app.exit(0);
    }
    catch (error) {
        fs.writeFileSync(path.join(output, 'ui-error.txt'), error.stack);
        console.error(error);
        app.exit(1);
    }
});
