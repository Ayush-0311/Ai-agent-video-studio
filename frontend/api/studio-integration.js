/** Production backend adapter. Keeps the original SmartEdit views and editor. */
(function () {
    'use strict';
    const base = 'http://127.0.0.1:8000';
    const $ = id => document.getElementById(id);
    const uid = () => crypto.randomUUID().replaceAll('-', '');
    const sliceEffects = (fx = {}, start = 0, end = 1) => {
        const point=(a,b,t)=>a+(b-a)*Math.max(0,Math.min(1,t));
        return {...fx,x:point(fx.x??.5,fx.end_x??.5,start),end_x:point(fx.x??.5,fx.end_x??.5,end),y:point(fx.y??.5,fx.end_y??.5,start),end_y:point(fx.y??.5,fx.end_y??.5,end)};
    };
    let project = null, activeJob = null, running = false, settingsCache = null, connectionHealth = null;
    let taskController = null, latestProgress = [0, 'Checking connection…'], taskStarted = 0;
    const node = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined)
        n.textContent = text; if (cls)
        n.className = cls; return n; };
    const protect = fn => async (...args) => { try {
        return await fn(...args);
    }
    catch (e) {
        AgentPipeline._updateVideoProgress(0, e.message, true);
        toast(e.message, 'error');
        return false;
    } };
    const updateProgress = AgentPipeline._updateVideoProgress.bind(AgentPipeline);
    AgentPipeline._updateVideoProgress = (...args) => {
        latestProgress = args; updateProgress(...args);
        const status = $('studio-generation-status');
        if (status) { status.hidden = false; status.textContent = args[1]; }
    };
    function showProgress() {
        AgentPipeline._showVideoProgressModal('SmartEdit production pipeline'); updateProgress(...latestProgress);
        const box = $('se-vp-steps')?.parentElement;
        if (!box) return;
        const elapsed = node('p', '', 'editor-help'); elapsed.id = 'studio-job-elapsed'; box.append(elapsed);
        const cancel = node('button', 'Cancel current job', 'btn btn-secondary btn-sm'); cancel.id = 'studio-cancel-job';
        cancel.disabled = !running && !activeJob;
        cancel.onclick = protect(async () => {
            if (activeJob) {
                await api('/jobs/' + activeJob + '/cancel', 'POST'); cancel.disabled = true;
                toast('Cancellation requested; the current model/encoding operation may finish first.');
            } else if (running) taskController?.abort();
        });
        box.append(cancel);
    }
    const statusButton = node('button', '', 'btn btn-secondary btn-sm');
    statusButton.id = 'studio-generation-status'; statusButton.hidden = true;
    statusButton.setAttribute('aria-label', 'Open video production progress');
    statusButton.style.cssText = 'position:fixed;bottom:12px;left:12px;max-width:min(560px,80vw);white-space:normal;z-index:99998;text-align:left;';
    statusButton.onclick = () => { showProgress(); if (!running && !activeJob) statusButton.hidden = true; }; document.body.append(statusButton);
    async function api(path, method = 'GET', body, options = {}) {
        // Do not let a stale server silently discard newer editing properties.
        if (method !== 'GET' && (['/dub', '/plan', '/render', '/generate', '/assets', '/edit', '/agent-run', '/voice-preview', '/voice-settings', '/presenter-test'].includes(path) || method === 'PUT' && path.startsWith('/projects/'))) {
            const health = await api('/local-health', 'GET', undefined, options);
            if (!(health.production_api >= (path === '/dub' ? 16 : ['/generate', '/render', '/plan', '/presenter-test'].includes(path) ? 17 : path.startsWith('/projects/') ? 17 : ['/voice-preview', '/voice-settings'].includes(path) ? 10 : path === '/agent-run' ? 5 : 3)))
                throw new Error('An older video backend is running. Keep this window open to preserve edits, finish active jobs, then run the SmartEdit launcher and retry.');
        }
        const controller = new AbortController(), signal = options.signal || taskController?.signal;
        const abort = () => controller.abort(); signal?.addEventListener('abort', abort, {once:true});
        if (signal?.aborted) abort();
        let timedOut = false;
        const timer = setTimeout(() => { timedOut = true; controller.abort(); }, options.timeout ?? (path === '/health' ? 90000 : path === '/assets' ? 300000 : path === '/voice-preview' ? 1230000 : 30000));
        try {
        const response = await fetch(base + '/api/studio' + path, { signal: controller.signal, method, headers: body instanceof FormData ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body) });
        const data = await response.json();
        if (!response.ok) {
            const error = new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
            error.status = response.status;
            throw error;
        }
        return data;
        } catch (error) {
            if (timedOut) throw new Error('The backend did not respond in time. ' + (activeJob ? 'Your job is still saved; reload to reconnect to its progress.' : 'Check the backend and connection. Check Activity before submitting again.'));
            if (signal?.aborted) throw new Error('Request cancelled. Check Activity if a job was already submitted.');
            throw error;
        } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort); }
    }
    let presenterReady = false;
    const isRealPresenter = () => $('gen-video-mode')?.value === 'avatar' && $('gen-presenter-kind')?.value === 'realistic';
    function updatePresenterUI() {
        const real = $('gen-presenter-kind')?.value === 'realistic';
        $('real-presenter-options').hidden = !real;
        $('gen-presenter-character').closest('label').hidden = false;
        $('presenter-description').textContent = real
            ? 'Your topic → script → AI-created face → talking avatar with voice and matching slides. No upload needed. Mouth movement follows speech; head and body stay still. Choose the voice separately in Voice settings & preview. GPU generation can take minutes.'
            : 'Illustrated mouth animation follows narration, with blinks and gestures. Slides use AI images and editable text. Choose the voice separately in Voice settings & preview. No realistic human lip-sync.';
        $('presenter-test').disabled = running || !presenterReady;
    }
    async function checkPresenter() {
        $('presenter-runtime-status').textContent = 'Checking presenter setup…';
        presenterReady = false; updatePresenterUI();
        try {
            const result = await api('/presenter-status');
            presenterReady = result.available === true;
            $('presenter-runtime-status').textContent = result.message;
        } catch (e) { $('presenter-runtime-status').textContent = 'Cannot check presenter setup. Relaunch the updated backend and reconnect Colab.'; }
        $('presenter-runtime-status').dataset.ready = String(presenterReady);
        updatePresenterUI();
        return presenterReady;
    }
    $('gen-presenter-kind')?.addEventListener('change', () => {
        updatePresenterUI();
        if (isRealPresenter()) checkPresenter();
    });
    $('presenter-check')?.addEventListener('click', checkPresenter);
    async function requirePresenter() {
        if (!isRealPresenter()) return;
        if (!$('gen-narration').checked) throw new Error('Turn on Add narration for realistic lip-sync.');
        if (!await checkPresenter()) throw new Error($('presenter-runtime-status').textContent);
    }
    $('presenter-test')?.addEventListener('click',protect(() => task(async () => {
        await requirePresenter();
        const p = fresh();
        const job = await watch(await api('/presenter-test','POST',p));
        AgentPipeline._updateVideoProgress(100,job.result.message,false,base+job.result.video_url);
    })));
    updatePresenterUI();
    let musicChosen=false, referenceChosen=false;
    $('gen-auto-music')?.addEventListener('change',()=>{musicChosen=true;});
    $('gen-character-reference')?.addEventListener('change',()=>{referenceChosen=true;});
    function timedScriptInfo(text) {
        const clock = value => value.includes(':') ? Number(value.split(':')[0])*60+Number(value.split(':')[1]) : Number(value);
        const headers = [...text.matchAll(/^\s*(?:\*\*)?\[?\s*((?:\d{1,2}:)?\d{1,3}(?:\.\d+)?)\s*(?:sec(?:onds?)?|s)?\s*(?:[-–—]|to)\s*((?:\d{1,2}:)?\d{1,3}(?:\.\d+)?)\s*(?:sec(?:onds?)?|s)?\s*\]?\s*(?:\*\*)?\s*:\s*(?:\*\*)?/gim)];
        return headers.length ? {duration:clock(headers.at(-1)[2])} : null;
    }
    function fresh() {
        const presenter = $('gen-video-mode')?.value === 'avatar' ? '' : {realistic: ', realistic human presenter', cartoon: ', expressive 3D animated character'}[$('gen-avatar-style')?.value] || '';
        const result = { id: uid(), title: 'New video', prompt: $('gen-video-prompt')?.value || '',
            language: $('gen-video-lang')?.value || 'en', duration: Number($('gen-video-duration')?.value || 10),
            aspect_ratio: $('gen-video-ratio')?.value || '16:9', duration_mode: 'target',
            narration_timing: $('gen-narration-timing')?.value || 'exact',
            generation_mode: $('gen-video-mode')?.value || 'motion', narration: $('gen-narration')?.checked ?? true,
            motion_preset: $('gen-motion-preset')?.value || 'balanced',
            presenter_kind: $('gen-presenter-kind')?.value || 'illustrated',
            presenter_asset_id: '', // New videos always generate an avatar; old saved clips remain renderable.
            presenter_layout: $('gen-presenter-layout')?.value || 'side',
            presenter_character: $('gen-presenter-character')?.value || 'alex',
            presenter_theme: $('gen-presenter-theme')?.value || 'indigo',
            scene_mode: $('edit-ai-scene-type')?.value || 'auto',
            style: ($('gen-video-style')?.value || 'cinematic photography, natural lighting') + presenter,
            resolution: '1080p', captions: $('gen-captions')?.checked ?? true, brand: $('studio-brand')?.value || '',
            research: $('gen-research')?.checked ?? true,
            auto_music: $('gen-auto-music')?.value || 'off',
            character_reference: $('gen-character-reference')?.checked ?? false,
            music_id: '', music_volume: .12, denoise: !!$('studio-denoise')?.checked,
            color: $('studio-color')?.value || 'natural', scenes: [] };
        const timed=timedScriptInfo(result.prompt);
        if (timed && ['auto','ready'].includes(result.scene_mode)) {
            result.scene_mode='ready'; result.narration_timing='exact';
            if (Number.isInteger(timed.duration) && timed.duration>=10 && timed.duration<=180) result.duration=timed.duration;
            if (/[\u0900-\u097f]/.test(result.prompt)) result.language='hi';
            if (/\b9:16\b/.test(result.prompt)) result.aspect_ratio='9:16';
            if (/generate all images|all images automatically/i.test(result.prompt)) result.generation_mode='images';
            if (!musicChosen && /background music/i.test(result.prompt) && !/no background music/i.test(result.prompt)) result.auto_music='cinematic';
            if (!referenceChosen && /consistent character|same character/i.test(result.prompt)) result.character_reference=true;
        }
        return result;
    }
    $('gen-video-prompt')?.addEventListener('input',()=>{
        const p=fresh();
        if(p.scene_mode!=='ready')return;
        $('gen-video-duration').max=['motion','hybrid'].includes(p.generation_mode)?'60':'180';
        $('gen-video-duration').value=String(p.duration);
        $('gen-dur-val').textContent=p.duration+'s · from script';
        $('gen-narration-timing').value='exact';
        $('gen-video-lang').value=p.language;
        $('gen-video-ratio').value=p.aspect_ratio;
        if($('gen-video-mode').value!==p.generation_mode){
            $('gen-video-mode').value=p.generation_mode;
            $('gen-video-mode').dispatchEvent(new Event('change'));
        }
        if(!musicChosen)$('gen-auto-music').value=p.auto_music;
        if(!referenceChosen)$('gen-character-reference').checked=p.character_reference;
        $('scene-type-help').textContent='Timed script detected. Timestamps, voiceover and screen text will be preserved.';
    });
    $('gen-video-mode')?.addEventListener('change', () => {
        const mode = $('gen-video-mode').value, motion = ['motion','hybrid'].includes(mode), avatar = mode === 'avatar';
        $('gen-presenter-options').hidden = !avatar;
        $('gen-motion-preset').closest('.generation-speed').hidden = avatar;
        $('gen-avatar-style').disabled = avatar;
        $('gen-avatar-style').closest('label').hidden = avatar;
        $('avatar-lipsync-row').hidden = avatar || $('gen-avatar-style').value === 'none';
        if (avatar) $('gen-narration').checked = true;
        updatePresenterUI();
        if (isRealPresenter()) checkPresenter();
        updateVoiceStatus();
        $('gen-draft-description').textContent = avatar ? '720p draft video · Presenter + slides + narration.' : '720p draft video · Images + selected voice/subtitles.';
        $('gen-preview-btn').textContent = 'Draft video preview';
        $('gen-preview-btn').title = avatar ? 'Creates a 720p draft MP4 with slides, your selected presenter and narration/subtitles.' : 'Creates a 720p draft MP4 from images with pan/zoom and your selected narration/subtitles. No AI motion is generated.';
        $('gen-motion-preset').disabled = !motion;
        const duration = $('gen-video-duration');
        duration.max = motion ? '60' : '180';
        duration.value = Math.min(Number(duration.value), Number(duration.max));
        $('gen-dur-val').textContent = duration.value + 's';
        const t4SlowWan = /T4/i.test(connectionHealth?.gpu || '') && connectionHealth?.video_profile?.engine === 'wan2.1';
        $('gen-mode-help').textContent = avatar ? 'Topic → full explanation → narrated slides and presenter. Exact target fits the auto-written script to your selected duration.' : mode === 'hybrid' ? (t4SlowWan ? 'One motion opening, then animated images and narration. On the connected T4, one balanced 5-second motion shot measured about 46 minutes; Fast draft is shorter.' : 'One motion opening, then animated images and narration. Draft video preview tests the storyboard without motion generation.') : motion
            ? (t4SlowWan ? 'Every scene generates new motion. The connected T4 uses FP32 Wan; one balanced 5-second shot measured about 46 minutes, so a multi-shot video can take hours. Use Fast draft or Hybrid for a shorter job.' : 'Every scene generates new motion. Fast draft is a low-detail composition test and may show visible artifacts. Balanced and High detail take longer. 1080p export cannot restore missing source detail.')
            : 'Animated images with pan/zoom and narration; no generated character motion. This is the fastest creation mode.';
    });
    function updateVoiceStatus() {
        const status = $('gen-voice-status');
        if (status) status.textContent = $('gen-narration').checked ? 'Add narration' : 'Voice off · silent generation';
    }
    $('gen-narration')?.addEventListener('change', updateVoiceStatus);
    updateVoiceStatus();
    $('edit-ai-scene-type')?.addEventListener('change', () => {
        $('scene-type-help').textContent = {
            auto: 'Plans a topic, or detects a timestamped ready script automatically.',
            ready: 'Paste 0–5 sec: Visual: … Voiceover: “…” Text: “…”. Exact timestamps and dialogue are preserved.',
            sentences: 'One scene per sentence. Hindi danda (।) and line breaks are supported.',
            paragraphs: 'One scene per paragraph. Separate paragraphs with a blank line.',
            manual: 'Start each scene with [Scene 1], [Scene 2], etc.'
        }[$('edit-ai-scene-type').value];
    });
    function updateViews(reason = 'edit') { if (reason === 'edit' && project) project.duration_mode = 'content'; let cursor = 0; for (const scene of AgentPipeline.state.scenes) {
        const duration = Math.max(.1, scene.e - scene.s);
        scene.s = cursor;
        scene.e = cursor + duration;
        cursor = scene.e;
    } DURATION = Math.max(1, cursor); const total = document.querySelector('.playback-controls span.mono:last-of-type'); if (total)
        total.textContent = fmt(DURATION); if ($('ed-project-sub'))
        $('ed-project-sub').textContent = AgentPipeline.state.scenes.length + ' CLIPS · EDITABLE TIMELINE'; currentTime = Math.min(currentTime, DURATION); buildTranscript(); buildDecisionPanel(); buildTimeline(); updateEditorToolbar(); updatePlaybackUI(); window.dispatchEvent(new CustomEvent('studio:changed', {detail:{reason}})); }
    function loadProject(p, reason = 'load') { project = p; window.lastVideoDownloadUrl = null; SmartEditBackend.lastVideoDownloadUrl = null; selectedPreset = p.aspect_ratio; currentAspectRatio = p.aspect_ratio; if ($('ed-project-title'))
        $('ed-project-title').textContent = p.title; const oldVideo = $('real-preview-video'); if (oldVideo) {
        oldVideo.pause();
        oldVideo.removeAttribute('src');
        oldVideo.style.display = 'none';
        oldVideo.load();
    } let cursor = 0; AgentPipeline.state.scenes = p.scenes.map((s, i) => { const duration = (s.end - s.start) / s.speed; const scene = { id: i + 1, studio_id: s.id, keyword: 'Scene_' + (i + 1), s: cursor, e: cursor + duration, text: s.text, caption_source_text: s.caption_source_text || '', caption_words: structuredClone(s.caption_words || []), slide_title: s.slide_title || '', slide_points: [...(s.slide_points || [])], overlay_text: s.overlay_text || '', fade_out: !!s.fade_out, speaker: s.media_kind === 'video' ? 'Source audio' : 'AI voice', layout: s.layout || 'full-presenter', agent: 'Studio pipeline', vis: { query: s.visual_prompt, label: 'Scene ' + (i + 1), color: 'rgba(139,92,246,.2)' }, asset_id: s.asset_id, media_kind: s.media_kind, sourceStart: s.start, sourceEnd: s.end, speed: s.speed, muted: s.mute, volume: s.volume ?? 1, fit: s.fit || 'contain', flip: !!s.flip, brightness: s.brightness ?? 0, contrast: s.contrast ?? 1, saturation: s.saturation ?? 1, sharpness: s.sharpness ?? 0, effects: structuredClone(s.effects || {}), renderedAsset: s.rendered_asset ? structuredClone(s.rendered_asset) : undefined }; if (scene.renderedAsset && !scene.renderedAsset.content_key) scene.renderedAsset.content_key = previewKey(scene, p); cursor += duration; return scene; }); AgentPipeline.state.language = p.language; AgentPipeline.state.aspectRatio = p.aspect_ratio; AgentPipeline.state.prompt = p.prompt; AgentPipeline.state.historyStack = []; AgentPipeline.state.redoStack = []; window.selectedClipId = null; window.editorInited = false; currentTime = 0; goTo('editor'); updateViews(reason); if (reason === 'load') window.SmartEditSafety?.markSaved(); }
    function collect() { project = project || fresh(); project.language = AgentPipeline.state.language || project.language; project.aspect_ratio = AgentPipeline.state.aspectRatio || project.aspect_ratio; project.scenes = AgentPipeline.state.scenes.map(s => ({ id: s.studio_id || (s.studio_id = uid()), text: s.text || '', caption_source_text: s.caption_source_text || '', caption_words: structuredClone(s.caption_words || []), slide_title: s.slide_title || '', slide_points: [...(s.slide_points || [])], overlay_text: s.overlay_text || '', fade_out: !!s.fade_out, visual_prompt: s.vis?.sdPrompt || s.vis?.query || s.visual_prompt || '', asset_id: s.asset_id || '', media_kind: s.media_kind || 'image', layout: s.layout || 'full-presenter', start: s.asset_id ? Number(s.sourceStart || 0) : 0, end: s.asset_id ? Number(s.sourceEnd || s.e - s.s) : Math.max(.1, (s.e - s.s) * (s.speed || 1)), speed: s.speed || 1, mute: !!s.muted, volume: s.volume ?? 1, fit: s.fit || 'contain', flip: !!s.flip, brightness: s.brightness ?? 0, contrast: s.contrast ?? 1, saturation: s.saturation ?? 1, sharpness: s.sharpness ?? 0, effects: structuredClone(s.effects || {}), rendered_asset: !s.asset_id && validPreview(s) ? structuredClone(s.renderedAsset) : null })); return project; }
    function finish(job, showCompletion = true) { const result = job.result; if (result.project) { loadProject(structuredClone(result.project)); plannedKey = briefKey(result.project); plannedProjectId = result.project.id; } result.timeline.forEach((timing, index) => { const scene = AgentPipeline.state.scenes[index]; if (scene) {
        scene.s = timing.start;
        scene.e = timing.end;
        scene.renderedAsset = result.scene_assets?.[index];
        if (scene.renderedAsset) scene.renderedAsset.content_key = previewKey(scene, project);
    } }); DURATION = result.duration; const url = base + result.video_url; window.lastVideoDownloadUrl = url; Object.assign(SmartEditBackend, { lastVideoDownloadUrl: url, currentJobId: job.id, currentJob: job }); loadRealVideo(url); updateViews('export'); window.SmartEditSafety?.markSaved(); if (!showCompletion) return; AgentPipeline._updateVideoProgress(100, 'MP4 verified. ' + (result.audio_status || 'Video and audio streams checked') + '. Download is ready.', false, url + '?download=1'); const links = $('se-vp-download'); if (links) {
        for (const [name, key] of [['Subtitles', 'subtitles_url'], ['Production report', 'metadata_url']]) {
            const a = node('a', name, 'btn btn-secondary btn-sm');
            a.href = base + result[key];
            a.target = '_blank';
            a.rel = 'noopener';
            a.style.margin = '12px 6px 0';
            links.append(a);
        }
    } toast('Final video ready — preview or download.'); refreshProjects().catch(() => { }); }
    async function watch(job) { activeJob = job.id; localStorage.setItem('smartedit.original.activeJob', job.id); let lastEvent = 0; while (true) {
        let current;
        try { current = await api('/jobs/' + job.id); }
        catch (error) {
            if (error.status === 404 || error.status === 410) {
                activeJob = null;
                localStorage.removeItem('smartedit.original.activeJob');
                throw new Error('The previous job is no longer available. Its tracking was cleared; open your saved project or start a new job.');
            }
            throw error; // Retain tracking on a connection failure: the job may still be running.
        }
        for (const event of current.events.slice(lastEvent)) {
            AgentPipeline._updateVideoProgress(current.progress, event.agent + ': ' + event.message, false);
            AgentPipeline.logAgentAction('studio', event.agent, event.message, event.status === 'completed' ? 'g' : 'p');
        }
        lastEvent = current.events.length;
        if ($('export-bar'))
            $('export-bar').style.width = current.progress + '%';
        if ($('export-pct-text'))
            $('export-pct-text').textContent = current.progress + '%';
        if ($('export-status-text'))
            $('export-status-text').textContent = current.events.at(-1)?.message || current.status;
        if (!['running', 'queued'].includes(current.status)) {
            activeJob = null;
            localStorage.removeItem('smartedit.original.activeJob');
            if (current.status !== 'completed')
                throw new Error(current.error || 'Job cancelled.');
            return current;
        }
        await new Promise(resolve => setTimeout(resolve, 1800));
    } }
    async function task(fn) { if (running)
        throw new Error('A production job is already running.'); if (activeJob)
        throw new Error('Previous job is still tracked. Reload the app to reconnect to its progress before starting another.'); running = true; const ids = ['gen-video-btn', 'gen-preview-btn', 'export-btn', 'edit-ai-btn']; ids.forEach(id => { if ($(id))
        $(id).disabled = true; }); taskController = new AbortController(); taskStarted = Date.now();
        latestProgress = [0, 'Checking connection and preparing your request…']; showProgress();
        AgentPipeline._updateVideoProgress(...latestProgress);
        const clock = setInterval(() => { const seconds = Math.floor((Date.now()-taskStarted)/1000);
            if ($('studio-job-elapsed')) $('studio-job-elapsed').textContent = `Elapsed ${Math.floor(seconds/60)}m ${seconds%60}s · You can close this panel and reopen progress below.`;
        }, 1000);
        try {
        const result = await fn();
        if (latestProgress[0] < 100 && !latestProgress[2]) AgentPipeline._updateVideoProgress(100, 'Task completed.');
        return result;
    }
    finally {
        running = false;
        updatePresenterUI();
        clearInterval(clock); taskController = null;
        if ($('studio-cancel-job')) $('studio-cancel-job').disabled = !activeJob;
        ids.forEach(id => { if ($(id))
            $(id).disabled = false; });
    } }
    async function requirePlannerReady() {
        const health = await api('/health');
        const connectionError = Object.values(health.services || {}).find(s => ['auth_required', 'tunnel_offline', 'network_error', 'timeout', 'invalid_response', 'http_error'].includes(s.status));
        if (connectionError) throw new Error(connectionError.message);
        if (!health.ollama) throw new Error('The planning model is not connected. Use Connect & Test before generating.');
        if (health.planner_ready === false) throw new Error(health.planner_error || 'Colab planner inference is not ready. Use Connect & Test to check or recover it.');
        return health;
    }
    async function planOnly(p = fresh()) { if (!p.prompt.trim())
        throw new Error('Write a video idea or script first.'); await requirePlannerReady(); const job = await watch(await api('/plan', 'POST', p)); loadProject(job.result);
        plannedKey = briefKey(p); plannedProjectId = project.id; return job.result; }
    window.triggerFullVideoGeneration = protect(() => task(async () => {
        const desired = fresh();
        const reuseEdits = briefKey(desired) === plannedKey && project?.id === plannedProjectId;
        if (!reuseEdits && window.SmartEditSafety && !await window.SmartEditSafety.confirmReplacement()) return;
        await requirePresenter();
        if ($('gen-lipsync')?.checked) throw new Error('Lip-sync is not integrated. Turn it off to continue.');
        if (!desired.prompt.trim()) throw new Error('Write a video idea or script first.');
        const health = await api('/health');
        const connectionError = Object.values(health.services || {}).find(s => ['auth_required', 'tunnel_offline', 'network_error', 'timeout', 'invalid_response', 'http_error'].includes(s.status));
        if (connectionError) throw new Error(connectionError.message);
        const motion = ['motion','hybrid'].includes(desired.generation_mode);
        if (motion && !health.video_available)
            throw new Error('Run the updated SmartEdit Colab notebook on a T4 GPU and reconnect. This bridge does not support AI motion yet.');
        if (!health.ollama) throw new Error('The planning model is not connected. Use Connect & Test before generating.');
        if (health.planner_ready === false) throw new Error(health.planner_error || 'Colab planner inference is not ready. Use Connect & Test to check or recover it.');
        if (!health.ffmpeg) throw new Error('Video encoder is unavailable. Relaunch SmartEdit to check the backend setup.');
        if (desired.generation_mode !== 'motion' && !health.image)
            throw new Error('The image model is not ready. Finish Colab setup and reconnect with Connect & Test.');
        if (desired.narration && !health.voice) throw new Error('The voice service is not ready. Connect & Test before generating narration.');
        if (motion && !health.motion_presets?.includes(desired.motion_preset))
            throw new Error('Update the Colab notebook once to use speed presets. You can use Draft video preview or Image story with the current connection.');
        const reuse = briefKey(desired) === plannedKey && project?.id === plannedProjectId && project?.scenes?.length;
        const payload = reuse ? {...collect(), duration_mode:'target', narration_timing:desired.narration_timing, duration:desired.duration, motion_preset:desired.motion_preset, presenter_layout:desired.presenter_layout,
            presenter_character:desired.presenter_character, presenter_theme:desired.presenter_theme,
            presenter_kind:desired.presenter_kind,presenter_asset_id:desired.presenter_asset_id,
            auto_music:desired.auto_music,character_reference:desired.character_reference} : desired;
        AgentPipeline._updateVideoProgress(0, reuse ? 'Submitting reviewed storyboard for rendering…' : 'Starting explanation planning and video production…');
        const job = await watch(await api('/generate', 'POST', payload)); finish(job);
    }));
    let plannedKey = '', plannedProjectId = '';
    // Render detail changes do not change the story or invalidate manual scene edits.
    function briefKey(p) { return JSON.stringify([p.prompt,p.duration,p.language,p.style,p.aspect_ratio,p.generation_mode,p.scene_mode,p.narration,p.captions,p.research ?? true]); }
    async function prepareStoryboard() {
        const desired = fresh();
        if ((briefKey(desired) !== plannedKey || project?.id !== plannedProjectId) && window.SmartEditSafety && !await window.SmartEditSafety.confirmReplacement()) return false;
        if (briefKey(desired) !== plannedKey || project?.id !== plannedProjectId || !project?.scenes?.length) await planOnly(desired);
        project.motion_preset = desired.motion_preset;
        project.narration_timing = desired.narration_timing;
        project.auto_music = desired.auto_music;
        project.character_reference = desired.character_reference;
        project.presenter_layout = desired.presenter_layout;
        project.presenter_character = desired.presenter_character;
        project.presenter_theme = desired.presenter_theme;
        project.presenter_kind = desired.presenter_kind;
        project.presenter_asset_id = desired.presenter_asset_id;
        return true;
    }
    window.previewGeneration = protect(() => task(async () => {
        await requirePresenter();
        const health = await api('/health');
        if (!health.ollama || health.planner_ready === false || !health.image || !health.ffmpeg) throw new Error(health.planner_error || health.errors?.[0] || 'Connect the planner and image bridge to make a draft video preview.');
        if ($('gen-narration')?.checked && !health.voice) throw new Error('Connect the voice service before creating a narrated preview.');
        if (!await prepareStoryboard()) return;
        const draft = structuredClone(collect());
        const avatar = draft.generation_mode === 'avatar';
        draft.id = uid(); draft.duration_mode = 'target'; draft.title += avatar ? ' — Avatar draft video preview' : ' — Draft video preview'; draft.generation_mode = avatar ? 'avatar' : 'images'; draft.resolution = '720p';
        const job = await watch(await api('/render','POST',draft));
        // Keep any measured-duration script repair for the final render and its voice cache.
        for (const revised of job.result.project?.scenes || []) {
            const original = project.scenes.find(s => s.id === revised.id);
            const editable = AgentPipeline.state.scenes.find(s => s.studio_id === revised.id);
            if (original) { original.text = revised.text; original.visual_prompt = revised.visual_prompt;
                original.slide_title = revised.slide_title || ''; original.slide_points = [...(revised.slide_points || [])]; }
            if (editable) { editable.text = revised.text; editable.vis = {...editable.vis, query:revised.visual_prompt, sdPrompt:revised.visual_prompt};
                editable.slide_title = revised.slide_title || ''; editable.slide_points = [...(revised.slide_points || [])]; }
        }
        if (job.result.project?.production_notes) project.production_notes = structuredClone(job.result.project.production_notes);
        updateViews('preview');
        AgentPipeline._updateVideoProgress(100, avatar ? '720p draft video ready — slides with your selected presenter and narration/subtitles. Generate video reuses the storyboard and cached images/voice.' : '720p draft video ready — images with pan/zoom and your selected narration/subtitles. No AI motion was generated. Generate video uses your selected mode and storyboard.', false, base + job.result.video_url);
    }));
    window.generateScriptWithAI = protect(() => task(async () => { if (window.SmartEditSafety && !await window.SmartEditSafety.confirmReplacement()) return false; await planOnly(); AgentPipeline._updateVideoProgress(100, 'Storyboard ready in the editor. Review it, then click Export.'); return true; }));
    window.startExport = protect(() => task(async () => { const p = collect(); if (!p.scenes.length)
        throw new Error('Create scenes or upload a video first.'); p.aspect_ratio = window.selectedPreset || p.aspect_ratio; p.resolution = $('real-export-resolution')?.querySelector('.active')?.textContent.trim() || '720p'; p.captions = !!document.querySelector('#export-modal .toggle.on'); $('export-progress-wrap').style.display = 'block'; const job = await watch(await api('/render', 'POST', p)); finish(job); closeModal('export-modal'); }));
    AgentPipeline.reRenderVideo = protect(() => task(async () => { const job = await watch(await api('/render', 'POST', collect())); finish(job); }));
    AgentPipeline.reRenderVideoAfterEdit = () => updateViews();
    AgentPipeline.runFullAgentChain = window.triggerFullVideoGeneration;
    window.generateFullVideo = (prompt, duration) => { if ($('gen-video-prompt'))
        $('gen-video-prompt').value = prompt; if ($('gen-video-duration'))
        $('gen-video-duration').value = duration || 10; return window.triggerFullVideoGeneration(); };
    AgentPipeline.runFullAgentChain = (prompt, duration) => window.generateFullVideo(prompt || $('gen-video-prompt')?.value || '', duration);
    window.simulatePromptUpload = (prompt, config = {}) => { if ($('gen-video-lang') && config.language)
        $('gen-video-lang').value = config.language; if ($('gen-video-ratio') && config.aspectRatio)
        $('gen-video-ratio').value = config.aspectRatio; return window.generateFullVideo(prompt, config.duration || 10); };
    window.startScriptPipeline = window.simulatePromptUpload;
    async function upload(file) { validateMediaFile(file); const form = new FormData(); form.append('file', file); return api('/assets', 'POST', form); }
    function updateDubOptions() {
        const enabled = $('upload-translate').checked;
        $('upload-target-wrap').hidden = $('upload-dub-help').hidden = !enabled;
        $('upload-action-label').textContent = enabled ? 'Translate & dub video' : 'Import video';
        const source = $('upload-language').selectedOptions[0].textContent;
        const target = $('upload-target-language').selectedOptions[0].textContent;
        const outputLanguage = enabled ? target : source;
        $('upload-caption-label').textContent = '3. Add ' + outputLanguage + ' captions';
        $('upload-caption-help').textContent = enabled ? 'Captions use the translated script.' : 'Captions follow the original speech language.';
        $('upload-local-help').hidden = enabled;
        $('upload-output-summary').textContent = enabled && source === target
            ? 'Choose a new voice language different from the original.'
            : 'Output: ' + (enabled ? source + ' → ' + target + ' voice' : 'Original ' + source + ' audio')
              + ($('upload-transcribe').checked ? ' + ' + outputLanguage + ' captions' : ' · No new captions');
    }
    for (const id of ['upload-translate','upload-language','upload-target-language','upload-transcribe']) $(id).addEventListener('change', updateDubOptions);
    updateDubOptions();
    async function importVideo(transcribe, dub = false) {
        const target = $('upload-target-language').value;
        if (dub && target === $('upload-language').value) throw new Error('Choose a target language different from the source speech language.');
        const file = SmartEditBackend.selectedFile; if (!file)
        throw new Error('Select your video first.'); if (window.SmartEditSafety && !await window.SmartEditSafety.confirmReplacement()) return; const media = await upload(file); if (media.kind !== 'video')
        throw new Error('Select a video file.'); const p = fresh(); p.language = $('upload-language')?.value || p.language; p.generation_mode = 'images'; p.duration_mode = 'content'; p.narration = false; p.captions = false; p.title = media.name; p.scenes = [{ id: uid(), asset_id: media.id, media_kind: 'video', start: 0, end: media.duration, text: '', visual_prompt: '', speed: 1, mute: false }]; loadProject(p, 'import'); await window.SmartEditSafety.save(); loadRealVideo(base + '/api/studio/assets/' + media.id); if (dub) {
        const job = await watch(await api('/dub', 'POST', {project:p, scene_id:p.scenes[0].id, target_language:target, captions:!!transcribe}));
        finish(job); return;
    } if (transcribe) {
        const job = await watch(await api('/transcribe', 'POST', { project: p, scene_id: p.scenes[0].id, remove_silence: false }));
        loadProject(job.result);
    } AgentPipeline._updateVideoProgress(100, 'Video loaded. Edit the timeline and click Export to apply edits.'); }
    window.openInEditorDirectly = protect(event => { event?.stopPropagation(); return task(() => importVideo(false)); });
    window.startProcessingFlow = protect(() => task(() => importVideo($('upload-transcribe')?.checked ?? false, $('upload-translate')?.checked ?? false)));
    window.simulateUpload = protect((file, config) => { if (file instanceof File)
        SmartEditBackend.selectedFile = file; return task(() => importVideo(true)); });
    window.addAudioTrack = () => { const picker = node('input'); picker.type = 'file'; picker.accept = 'audio/*'; picker.onchange = protect(async () => { if (!picker.files[0])
        return; const media = await upload(picker.files[0]); if (media.kind !== 'audio')
        throw new Error('Select an audio-only track.'); project = project || fresh(); project.music_id = media.id; toast('Music attached: ' + media.name + '. It will be mixed and ducked in the next export.'); }); picker.click(); };
    // Timeline operations preserve separate source time and output time.
    function previewKey(scene, p = project) {
        return JSON.stringify([scene.text || '', scene.vis?.sdPrompt || scene.vis?.query || '', scene.slide_title || '', scene.slide_points || [],scene.overlay_text || '',!!scene.fade_out,
            p?.style, p?.language, p?.generation_mode, p?.presenter_kind, p?.presenter_asset_id,
            p?.presenter_character, p?.presenter_theme, p?.presenter_layout, p?.narration, p?.motion_preset]);
    }
    function validPreview(scene) {
        if (!scene.renderedAsset) return false;
        if (scene.renderedAsset.content_key && scene.renderedAsset.content_key !== previewKey(scene)) {
            delete scene.renderedAsset;
            return false;
        }
        return true;
    }
    function materialize(scene) { if (!scene.asset_id && validPreview(scene)) {
        scene.asset_id = scene.renderedAsset.asset_id;
        scene.media_kind = 'video';
        scene.sourceStart = 0;
        scene.sourceEnd = scene.renderedAsset.duration;
        scene.speed = scene.renderedAsset.duration / Math.max(.1, scene.e - scene.s);
        // Preserve the output duration and the user's current mute choice.
    } }
    function history() { if (running)
        throw new Error('Wait for the current render before editing.'); AgentPipeline.pushHistoryState(); }
    window.selectClip = id => { window.selectedClipId = id; AgentPipeline.state.currentSceneIndex = Math.max(0, AgentPipeline.state.scenes.findIndex(s => s.id === id)); buildTracks(); updateEditorToolbar(); };
    window.splitClip = protect(() => { const index = AgentPipeline.state.scenes.findIndex(s => currentTime > s.s && currentTime < s.e); if (index < 0)
        throw new Error('Move the playhead inside a clip.'); history(); const original = AgentPipeline.state.scenes[index]; materialize(original); const fraction = (currentTime - original.s) / (original.e - original.s); const words = (original.text || '').split(/\s+/); const split = Math.round(words.length * fraction); const left = structuredClone(original), right = structuredClone(original); left.e = currentTime; right.s = currentTime; right.id = uid(); right.studio_id = uid(); left.text = words.slice(0, split).join(' '); right.text = words.slice(split).join(' '); left.words = []; right.words = []; if (original.asset_id) {
        const sourceCut = original.sourceStart + (original.sourceEnd - original.sourceStart) * fraction;
        left.sourceEnd = sourceCut;
        right.sourceStart = sourceCut;
    } left.effects=sliceEffects(original.effects,0,fraction);right.effects=sliceEffects(original.effects,fraction,1);AgentPipeline.state.scenes.splice(index, 1, left, right); window.selectedClipId = right.id; updateViews(); });
    // The existing toolbar calls splitAtPlayhead in some project versions.
    window.splitAtPlayhead = window.splitClip;
    window.splitClipAtPlayhead = window.splitClip;
    function trim(left) { const scene = getSelectedScene(); if (!scene || currentTime <= scene.s || currentTime >= scene.e)
        throw new Error('Put the playhead inside the selected clip.'); history(); materialize(scene); const fraction = (currentTime - scene.s) / (scene.e - scene.s); if (scene.asset_id) {
        const cut = scene.sourceStart + (scene.sourceEnd - scene.sourceStart) * fraction;
        if (left)
            scene.sourceStart = cut;
        else
            scene.sourceEnd = cut;
    } scene.effects=sliceEffects(scene.effects,left?fraction:0,left?1:fraction);if (left)
        scene.s = currentTime;
    else
        scene.e = currentTime; updateViews(); }
    window.trimClipLeft = protect(() => trim(true));
    window.trimClipRight = protect(() => trim(false));
    window.deleteSelectedClip = protect(() => { const scene = getSelectedScene(); if (!scene)
        throw new Error('Select a clip first.'); history(); AgentPipeline.state.scenes = AgentPipeline.state.scenes.filter(s => s.id !== scene.id); window.selectedClipId = null; updateViews(); });
    window.cutSelectedClip = window.deleteSelectedClip;
    window.duplicateSelectedClip = protect(() => { const scene = getSelectedScene(); if (!scene)
        throw new Error('Select a clip first.'); history(); const copy = structuredClone(scene); copy.id = uid(); copy.studio_id = uid(); AgentPipeline.state.scenes.splice(AgentPipeline.state.scenes.indexOf(scene) + 1, 0, copy); window.selectedClipId = copy.id; updateViews(); });
    window.confirmSpeedChange = protect(() => { const scene = getSelectedScene(); if (!scene)
        return; const speed = Number($('custom-speed-input')?.value || 1); if (!Number.isFinite(speed) || speed < .5 || speed > 2)
        throw new Error('Choose a speed between 0.5× and 2×.'); history(); const previous = !scene.asset_id && validPreview(scene) ? scene.renderedAsset.duration / (scene.e-scene.s) : scene.speed || 1; scene.e = scene.s + (scene.e - scene.s) * previous / speed; scene.speed = speed; closeSpeedDialog(); updateViews(); });
    const originalUndo = AgentPipeline.undo.bind(AgentPipeline), originalRedo = AgentPipeline.redo.bind(AgentPipeline);
    // Legacy undo called reRenderVideo implicitly. Keep undo local; Export commits media changes.
    AgentPipeline.undo = function () { const rerender = this.reRenderVideo; this.reRenderVideo = () => { }; try {
        originalUndo();
    }
    finally {
        this.reRenderVideo = rerender;
    } updateViews(); };
    AgentPipeline.redo = function () { const rerender = this.reRenderVideo; this.reRenderVideo = () => { }; try {
        originalRedo();
    }
    finally {
        this.reRenderVideo = rerender;
    } updateViews(); };
    window.setEditTool = (tool, button) => { document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active')); button?.classList.add('active'); toast('Select a clip, then use its trim, split or speed controls.'); };
    window.filterAgentsBySearch = value => { document.querySelectorAll('#agent-grid > *').forEach(card => card.style.display = card.textContent.toLowerCase().includes(String(value).toLowerCase()) ? '' : 'none'); };
    window.pollAgentStatus = async () => { try {
        const rows = await api('/agents');
        const dot = $('agent-backend-dot');
        if (dot) { dot.className = 'dot dot-g'; dot.style.background = ''; dot.title = 'Local backend reachable; model connections are checked when used.'; }
        for (const item of rows) {
            const badge = $('agent-status-' + item.id);
            if (badge) {
                badge.textContent = item.capability;
                badge.title = item.note;
            }
        }
    }
    catch {
        const dot = $('agent-backend-dot');
        if (dot) { dot.title = 'Backend offline'; dot.className = 'dot'; dot.style.background = '#EF4444'; }
        document.querySelectorAll('[id^="agent-status-"]').forEach(b => b.textContent = 'Backend offline');
    } };
    window.smartEditAsk = (label, value = '') => new Promise(resolve => { const overlay = node('div', undefined, 'modal-overlay open'); const box = node('div', undefined, 'modal-box'); const input = node('input'); input.value = value; input.style.cssText = 'width:100%;padding:12px;margin:20px 0;background:var(--bg3);color:var(--t1);border:1px solid var(--bdr);border-radius:8px'; const ok = node('button', 'Apply', 'btn btn-primary'); const cancel = node('button', 'Cancel', 'btn btn-secondary'); const done = v => { overlay.remove(); resolve(v); }; ok.onclick = () => done(input.value); cancel.onclick = () => done(null); input.onkeydown = e => { if (e.key === 'Enter')
        done(input.value); if (e.key === 'Escape')
        done(null); }; box.append(node('h3', label), input, ok, cancel); overlay.append(box); document.body.append(overlay); input.focus(); });
    window.triggerAgent = protect(async (id, button) => {
        if (running || activeJob) throw new Error('Wait for the current job before running another agent.');
        if (['caption', 'scene_detection', 'jump_cut'].includes(id))
        return task(async () => { const p = collect(); const selected = getSelectedScene(); const scene = p.scenes.find(s => s.id === selected?.studio_id) || p.scenes.find(s => s.media_kind === 'video'); if (!scene)
            throw new Error('Upload and select source footage with audio first.'); const job = await watch(await api('/transcribe', 'POST', { project: p, scene_id: scene.id, remove_silence: id === 'jump_cut' })); loadProject(job.result); AgentPipeline._updateVideoProgress(100, 'Speech scenes ready. Export applies the edits.'); }); if (id === 'image_generator')
        return task(async () => { const p = collect(); const selected = getSelectedScene(); const scene = p.scenes.find(s => s.id === selected?.studio_id) || p.scenes[0]; if (!scene)
            throw new Error('Create a storyboard first.'); const job = await watch(await api('/visual', 'POST', { project: p, scene_id: scene.id })); loadProject(job.result); const generated = job.result.scenes.find(s => s.id === scene.id); const image = node('img'); image.src = base + '/api/studio/assets/' + generated.asset_id; image.style.cssText = 'max-width:100%;max-height:350px;object-fit:contain'; $('se-vp-steps')?.append(image); AgentPipeline._updateVideoProgress(100, 'SDXL image created and attached to this scene.'); }); if (id === 'noise_reduction') {
        project = project || fresh();
        history();
        project.denoise = true;
        updateViews();
        toast('Audio denoising enabled for the next export.');
        return;
    } if (id === 'brand_kit' || id === 'color_grading') {
        goTo('editor');
        toast('Use Video settings in the right panel to apply watermark or color, then Export.');
        return;
    } if (id === 'music_sound') {
        window.addAudioTrack();
        return;
    } if (['export_optimizer', 'compositor'].includes(id))
        return window.startExport(); if (id === 'orchestrator')
        return window.triggerFullVideoGeneration(); if (id === 'script')
        return window.generateScriptWithAI(); if (id === 'lip_sync') {
        goTo('upload');
        $('gen-video-mode').value = 'avatar';
        $('gen-presenter-kind').value = 'realistic';
        $('gen-video-mode').dispatchEvent(new Event('change'));
        $('gen-presenter-options').scrollIntoView({block:'center'});
        toast('Enter your topic, choose a presenter, and check Colab setup. Your avatar is created automatically.');
        return;
    } if (id === 'nl_edit') { goTo('editor'); $('ed-nl-input').focus(); toast('Type your edit request below the video, then Apply edits.'); return; }
    if (id === 'voice') return task(async () => {
        const p = collect(), selected = getSelectedScene();
        const text = (p.scenes.find(s => s.id === selected?.studio_id) || p.scenes[0])?.text;
        if (!text?.trim()) throw new Error('Add scene narration first.');
        const result = await api('/voice-preview','POST',{text:text.slice(0,500),language:p.language});
        safeResult('Voice sample — first 500 characters; export synthesizes enabled narration', {language:p.language});
        const audio = node('audio'); audio.controls = true; audio.src = base + result.url;
        document.querySelector('.modal-overlay:last-child .modal-box')?.append(audio);
    });
    const specialists = ['layout_planner','script_optimizer','multi_language','viral_hook','seo_metadata','thumbnail_gen','broll_suggestion','emotion_analysis','slide_generator','conversation_mode','viral_clip','avatar_generator','chapter_marker'];
    if (specialists.includes(id)) {
        let language = 'hi';
        if (id === 'multi_language') {
            language = await window.smartEditAsk('Translate captions/narration to en, hi, es, fr or de. Source audio stays unchanged.', 'hi');
            if (language === null) return;
            language = language.trim();
            if (!['en','hi','es','fr','de'].includes(language)) throw new Error('Choose en, hi, es, fr or de.');
        }
        return task(async () => {
            const p = collect(); if (!p.scenes.length) throw new Error('Create or upload scenes first.');
            const job = await watch(await api('/agent-run','POST',{project:p,agent:id,language}));
            loadProject(job.result);
            safeResult(id.replaceAll('_',' ') + ' — review result', job.result.production_notes.specialists[id]);
        });
    }
    throw new Error('Unknown agent action.'); });
    function safeResult(title, data) { const overlay = node('div', undefined, 'modal-overlay open'); const box = node('div', undefined, 'modal-box'); const close = node('button', 'Close', 'btn btn-secondary'); close.onclick = () => overlay.remove(); const pre = node('pre', JSON.stringify(data, null, 2)); pre.style.cssText = 'white-space:pre-wrap;overflow:auto;max-height:60vh;font-size:12px;'; box.append(node('h3', title), pre, close); overlay.append(box); document.body.append(overlay); }
    window.showAgentResultModal = safeResult;
    function settingsInput(group, label, id, password = false) { const row = node('div', undefined, 'setting-row'); row.style.flexWrap = 'wrap'; const caption = node('label', label, 'setting-label'); caption.htmlFor = id; const input = node('input'); input.id = id; input.type = password ? 'password' : 'text'; input.style.cssText = 'width:100%;padding:11px;border:1px solid var(--bdr);background:var(--bg3);color:var(--t1);border-radius:8px'; row.append(caption, input); group.append(row); return input; }
    function installSettings() { const groups = document.querySelectorAll('#view-settings .setting-group'); if (groups.length < 3)
        return; groups[1].replaceChildren(node('div', '🧠 Colab / Ollama connection', 'setting-group-header')); settingsInput(groups[1], 'Ollama URL', 'studio-ollama'); settingsInput(groups[1], 'Installed model (default: qwen3.5:9b)', 'studio-model'); settingsInput(groups[1], 'Bridge access token', 'studio-token', true); groups[2].replaceChildren(node('div', '🖼 SDXL image generation', 'setting-group-header')); settingsInput(groups[2], 'Image bridge URL (same URL from the new Colab setup)', 'studio-image'); const help = node('p', 'Run colab/SmartEdit_Colab.py in a Colab GPU notebook. Paste its URL and access token here. Images use SDXL; scripts use Ollama.', 'setting-desc'); help.style.padding = '14px'; groups[2].append(help); const test = node('button', 'Save & check connections', 'btn btn-primary'); test.onclick = protect(saveAndCheck); groups[2].append(test); groups[0].replaceChildren(node('div', '🎙 Speech recognition', 'setting-group-header'), node('p', 'Whisper base (multilingual). The first transcription downloads its model. Language follows your project selection. Speaker diarization is not enabled.', 'setting-desc')); groups[0].style.padding = '20px'; for (let i = 3; i < groups.length; i++) {
        groups[i].replaceChildren(node('div', '🎬 Rendering', 'setting-group-header'), node('p', 'Real MP4/H.264 export, 30 fps, 720p or 1080p. Set aspect ratio and subtitles in the Export dialog. Noise, color and watermark options below are applied to the actual video.', 'setting-desc'));
        groups[i].style.padding = '20px';
    } const finish = groups[3] || groups[2]; settingsInput(finish, 'Watermark text (optional)', 'studio-brand'); const select = node('select'); select.id = 'studio-color'; select.className = 'btn btn-secondary'; for (const value of ['natural', 'warm', 'vibrant', 'noir']) {
        const option = node('option', value);
        option.value = value;
        select.append(option);
    } finish.append(select); const noise = node('label', ' Reduce uploaded audio noise '); const check = node('input'); check.type = 'checkbox'; check.id = 'studio-denoise'; noise.prepend(check); finish.append(noise); }
    function decodeConnection(raw) {
        const url = new URL(raw.trim());
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password)
            throw new Error('Use a valid Colab HTTPS connection link.');
        const fragment = new URLSearchParams(url.hash.slice(1));
        const encoded = fragment.get('smartedit');
        let info = {};
        if (url.hash) {
            try {
                if (!encoded) throw new Error();
                const normalized = encoded.replaceAll('-', '+').replaceAll('_', '/');
                info = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')));
            } catch { throw new Error('Connection link is incomplete. Copy the full ONE-PASTE link from Colab.'); }
            if (!info || typeof info.token !== 'string' || !info.token || /[^\x21-\x7e]/.test(info.token) || info.token.length > 512 || typeof info.model !== 'string' || !info.model.trim())
                throw new Error('Invalid SmartEdit connection data. Copy a fresh link from Colab.');
        }
        return {url: url.origin, token: info.token, model: info.model};
    }
    function connectionValues() {
        const parsed = decodeConnection($('studio-ollama').value);
        let token = parsed.token || $('studio-token').value.trim();
        let model = parsed.model || $('studio-model').value.trim();
        let image = parsed.token ? parsed.url : $('studio-image').value.trim();
        if (/^https?:\/\//i.test(token)) {
            const link = decodeConnection(token);
            if (!link.token) throw new Error('A base URL is not an access token. Copy the complete ONE-PASTE link from Colab.');
            if (link.url !== parsed.url || (image && decodeConnection(image).url !== link.url))
                throw new Error('Connection link belongs to a different server. Paste it into the Colab URL box.');
            token = link.token; model = link.model; image = link.url;
        }
        if (token.length > 512 || /[^\x21-\x7e]/.test(token)) throw new Error('Use only the bridge token, or paste the complete ONE-PASTE link.');
        return {ollama_url: parsed.url, model, image_url: image, bridge_token: token,
            voice_gender: $('studio-voice-gender').value, speech_rate: Number($('studio-speech-rate').value),
            voice_engine: $('studio-voice-engine').value, voice_profile: $('studio-voice-profile').value,
            voice_delivery: $('studio-voice-delivery').value, voice_normalize: $('studio-voice-normalize').value === 'true',
            image_quality: $('studio-image-quality').value};
    }
    async function readSettings() {
        const pendingLink = $('colab-url-input')?.value;
        settingsCache = await api('/settings');
        $('studio-ollama').value = settingsCache.ollama_url;
        $('studio-model').value = settingsCache.model;
        $('studio-image').value = settingsCache.image_url;
        $('studio-token').value = settingsCache.bridge_token;
        $('studio-voice-gender').value = settingsCache.voice_gender || 'male';
        $('studio-speech-rate').value = settingsCache.speech_rate ?? -5;
        $('studio-voice-engine').value = settingsCache.voice_engine || 'bridge';
        $('studio-voice-profile').value = settingsCache.voice_profile || 'auto';
        $('studio-voice-delivery').value = settingsCache.voice_delivery || 'natural';
        $('studio-voice-normalize').value = String(settingsCache.voice_normalize ?? true);
        $('studio-voice-engine').dispatchEvent(new Event('change'));
        $('studio-image-quality').value = settingsCache.image_quality || 'high';
        if ($('colab-url-input') && $('colab-url-input').value === pendingLink) $('colab-url-input').value = settingsCache.ollama_url;
    }
    async function saveConnections() {
        const value = connectionValues();
        await api('/settings', 'PUT', value);
        settingsCache = value;
        $('studio-ollama').value = value.ollama_url;
        $('studio-model').value = value.model;
        $('studio-image').value = value.image_url;
        $('studio-token').value = value.bridge_token;
        return value;
    }
    let connectionRevision = 0, checkingConnection = false;
    function showConnectionHealth(health, model) {
        connectionHealth = health;
        health.ollama ? setColabOnline(model, health.models) : setColabOffline();
        const auth = Object.values(health.services || {}).some(s => s.status === 'auth_required');
        const ready = health.ollama && health.planner_ready !== false && health.image && health.voice && health.ffmpeg;
        if (auth || (health.ollama && !ready)) {
            $('colab-status-text').textContent = auth ? 'TOKEN REQUIRED' : 'PARTLY READY';
            $('colab-status-text').style.color = '#F59E0B';
            $('colab-status-dot').style.background = '#F59E0B';
            $('colab-status-dot').title = auth ? 'Server reached; access token rejected' : 'Some services need attention';
        }
        const authError = Object.values(health.services || {}).find(s => s.status === 'auth_required')?.message;
        showColabMsg(ready ? (health.voice_provider === 'direct_neural' ? 'Connected: planning and images ready. Direct neural voice available; use Hear voice sample.' + (health.video_tested ? ' Motion encoded; review visual quality.' : '') : health.video_tested ? 'Connected: planning, images and voice ready. Motion encoded in this session; review visual quality.' : health.video_available ? 'Connected: AI motion available; motion inference has not been tested yet.' : 'Connected: image stories and voice ready. Motion is unavailable on this bridge.') : authError || (health.planner_ready === false && health.planner_error) || health.errors?.[0] || 'A service is not ready. Open the connection report.', ready ? 'green' : 'orange');
    }
    async function saveAndCheck(applyPreferences = true) {
        if (checkingConnection) return;
        checkingConnection = true; connectionRevision++;
        const button = $('colab-connect-btn'); button.disabled = true;
        showColabMsg('Checking connection…', '');
        try {
        const value = await saveConnections();
        if ($('colab-url-input')) $('colab-url-input').value = value.ollama_url;
        if (applyPreferences !== false) {
        project = project || fresh();
        project.brand = $('studio-brand').value;
        project.color = $('studio-color').value;
        project.denoise = $('studio-denoise').checked;
        }
        const health = await api('/health');
        showConnectionHealth(health, value.model);
        if (isRealPresenter()) await checkPresenter();
        safeResult('Connection check', {language_model: health.planner_ready === false ? (health.planner_error || 'Inference unavailable') : health.ollama ? 'Ready' : 'Unavailable',
            motion: health.video_tested ? 'Video encoded in this Colab session; visual quality requires review' : health.video_available ? 'Available; inference not yet tested' : !health.bridge_connected ? 'Not checked — connect the bridge first' : 'Unavailable on this Colab bridge',
            images: health.image ? 'Startup test passed' : 'Unavailable',
            voice: health.voice ? (health.voice_provider === 'direct_neural' ? 'Direct neural runtime available; Hear voice sample tests the online service' : 'Startup test passed') : 'Unavailable',
            ffmpeg: health.ffmpeg, installed_models: health.models, services: health.services, errors: health.errors});
        return health;
        } catch (error) {
            showColabMsg(error.message, 'red'); throw error;
        } finally { checkingConnection = false; button.disabled = false; }
    }
    window.saveSettings = protect(saveAndCheck);
    window.connectColab = protect(async () => {
        if (checkingConnection) return;
        const parsed = decodeConnection($('colab-url-input').value);
        if (!parsed.token && $('studio-ollama').value.replace(/\/$/, '') !== parsed.url) $('studio-token').value = '';
        $('studio-ollama').value = parsed.url;
        $('studio-image').value = parsed.url;
        if (parsed.token) $('studio-token').value = parsed.token;
        if (parsed.model) $('studio-model').value = parsed.model;
        if (!$('studio-token').value) {
            goTo('settings');
            toast('Paste the complete ONE-PASTE connection link, or enter the bridge token here.', 'error');
            return;
        }
        await saveAndCheck(false);
    });
    window.checkColabStatus = async () => {
        if (checkingConnection) return;
        const revision = ++connectionRevision;
        try {
        const saved = await api('/settings');
        const health = await api('/health');
        if (revision === connectionRevision) {
            showConnectionHealth(health, saved.model);
            if (isRealPresenter()) await checkPresenter();
        }
    }
    catch {
        if (revision === connectionRevision) {
            setColabOffline();
            showColabMsg('Local backend is unavailable. Relaunch SmartEdit, then Connect & Test.', 'red');
        }
    } };
    function studioCounts(projects, jobs) {
        return [projects.length, jobs.filter(j => ['render','generate'].includes(j.kind) && j.status === 'completed').length,
            jobs.filter(j => ['running', 'queued'].includes(j.status)).length, jobs.filter(j => j.status === 'failed').length];
    }
    function dashboardCounts(projects, jobs) {
        const labels = ['Saved projects', 'Completed exports', 'Active jobs', 'Failed jobs'];
        ['dash-total-videos', 'dash-proc-time', 'dash-images', 'dash-confidence'].forEach((id, i) => {
            const value = $(id); if (!value) return;
            value.textContent = studioCounts(projects, jobs)[i];
            value.parentElement.querySelector('.stat-label').textContent = labels[i];
            value.parentElement.querySelector('.stat-sub').textContent = 'Local saved records';
        });
    }
    window.initAnalytics = async () => {
        const host = document.querySelector('#view-analytics .scroll-area');
        host.replaceChildren(node('h2', 'Production activity', 'h3'), node('p', 'Loading saved projects and job records…', 'setting-desc'));
        try {
            const [projects, jobs] = await Promise.all([api('/projects'), api('/jobs')]);
            const refresh = node('button', 'Refresh', 'btn btn-secondary'); refresh.onclick = window.initAnalytics;
            const cards = node('div'); cards.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:24px 0';
            studioCounts(projects, jobs).forEach((value, i) => {
                const card = node('div', undefined, 'stat-card');
                card.append(node('div', ['Saved projects', 'Completed exports', 'Active jobs', 'Failed jobs'][i], 'stat-label'), node('div', value, 'stat-kpi'));
                cards.append(card);
            });
            host.replaceChildren(node('h2', 'Production activity', 'h3'), node('p', 'Counts use local saved records. Repeat exports count separately. Model accuracy and visual quality have not been benchmarked.', 'setting-desc'), refresh, cards);
            if (!jobs.length) host.append(node('p', 'No production jobs yet. Import a video and export your first edit.'));
            for (const job of jobs.slice(0, 30)) {
                const row = node('div', undefined, 'stat-card'); row.style.marginBottom = '12px';
                const title = projects.find(p => p.id === job.project_id)?.title || 'Saved job';
                row.append(node('strong', title), node('p', `${job.kind} · ${job.status} · ${Math.round(Number(job.progress) || 0)}%`, 'setting-desc'));
                if (job.error) row.append(node('p', job.error, 'setting-desc'));
                if (['render','generate','presenter_test'].includes(job.kind) && job.status === 'completed' && job.result?.video_url) {
                    const link = node('a', job.kind === 'presenter_test' ? 'Download presenter test' : 'Download MP4', 'btn btn-secondary btn-sm');
                    link.href = base + job.result.video_url + '?download=1'; row.append(link);
                }
                host.append(row);
            }
        } catch (error) {
            const retry = node('button', 'Retry', 'btn btn-secondary'); retry.onclick = window.initAnalytics;
            host.replaceChildren(node('h2', 'Production activity', 'h3'), node('p', 'Activity unavailable: ' + error.message), retry);
        }
    };
    function renderSignature(p) {
        function canonical(value) {
            if (Array.isArray(value)) return value.map(canonical);
            if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).filter(k => k !== 'rendered_asset' && k !== 'content_key').sort().map(k => [k, canonical(value[k])]));
            return value;
        }
        const {title, production_notes, ...content} = p;
        return JSON.stringify(canonical(content));
    }
    async function openSavedProject(p, jobs = []) {
        if (running || activeJob) return toast('Wait for the current job.', 'error');
        if (window.SmartEditSafety && !await window.SmartEditSafety.confirmReplacement()) return false;
        if (p.id === project?.id && window.SmartEditSafety && !window.SmartEditSafety.isDirty()) p = structuredClone(collect());
        const matching = jobs.find(j => j.project_id === p.id && ['render','generate'].includes(j.kind) &&
            j.status === 'completed' && j.result?.video_url && j.result?.project &&
            renderSignature(j.result.project) === renderSignature(p));
        if (matching) finish({...matching,result:{...matching.result,project:structuredClone(p)}}, false);
        else loadProject(structuredClone(p));
    }
    async function refreshProjects() { const [projects, jobs, storage] = await Promise.all([api('/projects'), api('/jobs'), api('/storage-health').catch(() => ({warnings:[]}))]); dashboardCounts(projects, jobs); const host = document.querySelector('#view-dashboard .scroll-area') || $('view-dashboard'); let section = $('studio-saved-projects'); if (!section) {
        section = node('details');
        section.open = true;
        section.id = 'studio-saved-projects';
        section.style.cssText = 'padding:16px;margin:16px;border:1px solid var(--bdr);border-radius:12px';
        host.append(section);
    } section.replaceChildren(node('summary', 'Saved projects & completed videos (' + projects.length + ')'));
        if (storage.warnings?.length) { const warning = node('p', storage.warnings.length + ' saved record(s) could not be read. Original files are retained in backend/studio-data. Other projects remain available.', 'editor-help'); warning.setAttribute('role','status'); section.prepend(warning); } for (const p of projects) {
        const row = node('div', undefined, 'setting-row');
        const open = node('button', p.title, 'btn btn-secondary btn-sm');
        open.onclick = () => openSavedProject(p, jobs);
        row.append(open);
        const job = jobs.find(j => j.project_id === p.id && ['render','generate'].includes(j.kind) && j.status === 'completed' && j.result?.video_url);
        if (job) {
            const current = job.result?.project && renderSignature(job.result.project) === renderSignature(p);
            const link = node('a', current ? 'Download MP4' : 'Download previous export', 'btn btn-primary btn-sm');
            if (!current) row.append(node('span', 'Saved changes need a new export.', 'editor-help'));
            link.href = base + job.result.video_url + '?download=1';
            link.target = '_blank';
            link.rel = 'noopener';
            row.append(link);
        }
        section.append(row);
    } }
    // Small actions added to the existing editor; the original layout stays intact.
    const toolbar = $('view-editor')?.querySelector('.topbar') || $('view-editor')?.querySelector('.editor-toolbar');
    if (toolbar) {
        const save = node('button', 'Save project', 'btn btn-secondary btn-sm');
        save.onclick = protect(() => window.SmartEditSafety.save());
        toolbar.append(save);
    }
    window.refreshStudioProjects = () => refreshProjects().catch(() => { });
    window.updateDashboardStats = window.refreshStudioProjects;
    installSettings();
    const voiceGroup = document.querySelector('#view-settings .setting-group');
    function choice(label, id, options) {
        const row = node('div', undefined, 'setting-row');
        const caption = node('label', label, 'setting-label'); caption.htmlFor = id;
        const select = node('select'); select.id = id; select.className = 'btn btn-secondary';
        for (const [value, text] of options) { const option = node('option', text); option.value = value; select.append(option); }
        row.append(caption, select); voiceGroup.append(row);
    }
    choice('Voice engine', 'studio-voice-engine', [['bridge','OmniVoice / Colab'],['neural','Legacy Edge / Internet']]);
    choice('Narrator voice', 'studio-voice-profile', [['auto','Auto · Match narration language'],['hi-madhur','Madhur · Hindi · Male'],['hi-swara','Swara · Hindi · Female'],['en-prabhat','Prabhat · Indian English · Male'],['en-neerja','Neerja · Indian English · Female'],['en-christopher','Christopher · US English · Male'],['en-jenny','Jenny · US English · Female']]);
    choice('Auto voice gender', 'studio-voice-gender', [['male','Male'],['female','Female']]);
    choice('Delivery', 'studio-voice-delivery', [['natural','Natural · Original pitch'],['calm','Calm · Slightly slower'],['energetic','Energetic · Slightly brighter']]);
    choice('Voice loudness', 'studio-voice-normalize', [['true','Balanced loudness · On'],['false','Original audio level']]);
    const voiceHelp=node('p','Neural narration creates the voice and speech timings. MuseTalk uses that same audio to animate talking presenters; it does not create voices. Delivery adjusts pace and pitch. A voice for another language uses Auto. Internet is required.','editor-help');voiceGroup.append(voiceHelp);
    $('studio-voice-engine').addEventListener('change', () => {
        const bridgeVoice = $('studio-voice-engine').value === 'bridge';
        for (const id of ['studio-voice-profile','studio-voice-delivery','studio-voice-normalize']) $(id).disabled = bridgeVoice;
        voiceHelp.textContent = bridgeVoice
            ? 'OmniVoice runs on your connected Colab GPU. Choose male/female and pace below. Named Edge voices do not apply. Captions use estimated timing. Model weights are for non-commercial use. MuseTalk animates the resulting audio.'
            : 'Legacy Edge voice uses Internet on this PC and supplies word timings. Named voices, delivery and loudness controls apply to this engine.';
    });
    const rate = settingsInput(voiceGroup, 'Voice pace (-20% to +20%; default -5%)', 'studio-speech-rate');
    rate.type = 'number'; rate.min = '-20'; rate.max = '20'; rate.value = '-5';
    choice('Image detail', 'studio-image-quality', [['high','High · SDXL ~1 MP · 40 steps'],['balanced','Balanced · 28 steps']]);
    choice('Sample language', 'studio-voice-language', [['hi','Hindi'],['en','English'],['es','Spanish'],['fr','French'],['de','German']]);
    async function saveVoicePreferences() {
        const value={voice_engine:$('studio-voice-engine').value,voice_profile:$('studio-voice-profile').value,
            voice_gender:$('studio-voice-gender').value,voice_delivery:$('studio-voice-delivery').value,
            voice_normalize:$('studio-voice-normalize').value==='true',speech_rate:Number($('studio-speech-rate').value)};
        if(!Number.isInteger(value.speech_rate)||value.speech_rate < -20||value.speech_rate > 20)throw new Error('Voice pace must be a whole number from -20 to 20.');
        await api('/voice-settings','PUT',value);
        if(settingsCache)Object.assign(settingsCache,value);
    }
    const saveVoice=node('button','Save voice settings','btn btn-primary');saveVoice.id='studio-save-voice';
    saveVoice.onclick=protect(async()=>{saveVoice.disabled=true;try{await saveVoicePreferences();toast('Voice settings saved. New narration exports will use these preferences.');}finally{saveVoice.disabled=false;}});
    voiceGroup.append(saveVoice);
    $('studio-voice-profile').addEventListener('change',()=>{const language=$('studio-voice-profile').value.split('-')[0];if(['hi','en'].includes(language))$('studio-voice-language').value=language;});
    const previewVoice = node('button', 'Hear voice sample', 'btn btn-secondary');previewVoice.id='studio-hear-voice';
    previewVoice.onclick = protect(async () => {
        previewVoice.disabled = true;
        saveVoice.disabled = true;
        try {
            await saveVoicePreferences();
            const language = $('studio-voice-language').value;
            const samples = {hi:'नमस्ते! आइए, इस विषय को आसान भाषा में समझते हैं। पहले मुख्य बात जानेंगे, फिर एक छोटा सा उदाहरण देखेंगे।',en:'Let’s explore this idea together. First, we will understand the main point, then look at a simple example.',es:'Esta es una muestra de la narración de tu vídeo.',fr:'Voici un exemple de la narration de votre vidéo.',de:'Hier ist eine Vorschau der Stimme für dein Video.'};
            const response = await api('/voice-preview', 'POST', {language, text:samples[language]});
            const audio = node('audio'); audio.controls = true; audio.src = base + response.url;
            $('studio-voice-sample')?.remove(); audio.id = 'studio-voice-sample'; voiceGroup.append(audio);
            $('studio-voice-result')?.remove();const info=node('p',(response.voice?.voice||'Voice sample')+(response.voice?.profile_matched===false?' · Auto voice used for this sample language':''),'editor-help');info.id='studio-voice-result';voiceGroup.append(info);
            try { await audio.play(); } catch { toast('Voice sample ready. Press Play to listen.'); }
        } finally { previewVoice.disabled = false; saveVoice.disabled = false; }
    });
    voiceGroup.append(previewVoice);
    readSettings().catch(() => { });
    refreshProjects().catch(() => { });
    const resumed = localStorage.getItem('smartedit.original.activeJob');
    if (resumed)
        protect(() => task(async () => { const job = await watch({ id: resumed }); const projects = await api('/projects'); const p = projects.find(p => p.id === job.project_id); if (p)
            loadProject(p); if (['render','generate','dub'].includes(job.kind))
            finish(job);
        else if (job.kind === 'presenter_test')
            AgentPipeline._updateVideoProgress(100,job.result.message,false,base+job.result.video_url);
        else
            loadProject(job.result); }))();
    window.generateAIImage = () => window.triggerAgent('image_generator');
    const editToolbar = $('video-edit-toolbar');
    if (editToolbar) {
        const edit = node('button', 'Edit scene', 'btn btn-secondary btn-sm');
        edit.onclick = protect(async () => {
            const scene = getSelectedScene();
            if (!scene) throw new Error('Select a timeline clip first.');
            const text = await window.smartEditAsk(scene.media_kind === 'video' ? 'Caption text (source audio stays unchanged)' : 'Scene narration', scene.text || '');
            if (text === null) return;
            let visual = scene.vis?.query || '';
            if (scene.media_kind !== 'video') {
                visual = await window.smartEditAsk('Image direction in English', visual);
                if (visual === null) return;
            }
            history();
            scene.text = text;
            if (scene.media_kind !== 'video') {
                if (visual !== scene.vis?.query) scene.asset_id = '';
                scene.vis = { ...scene.vis, query: visual, sdPrompt: visual };
                delete scene.renderedAsset;
            }
            updateViews();
            toast('Scene updated. Export renders the revised narration and visuals.');
        });
        editToolbar.append(edit);
    }
    // Exposed for deterministic adapter tests, without granting renderer Node access.
    window.SmartEditStudio = {  sliceEffects, validPreview, collect, loadProject, openSavedProject, api, getProject: () => project, setProject: p => project = p, decodeConnection, updateViews, history, materialize, upload, task, watch, finish, protect, uid, fresh, hasActiveJob: () => !!activeJob, busy: () => running || !!activeJob };
})();
