/* Editable source timeline. The same ranges and settings are sent to the MP4 renderer. */
(function () {
    'use strict';
    const S = window.SmartEditStudio, $ = id => document.getElementById(id);
    const base = 'http://127.0.0.1:8000/api/studio';
    const scenes = () => AgentPipeline.state.scenes;
    const clone = value => structuredClone(value);
    const make = (tag, text, cls) => { const el = document.createElement(tag); if (text != null) el.textContent = text; if (cls) el.className = cls; return el; };
    const guarded = fn => async (...args) => { try { return await fn(...args); } catch (error) { toast(error.message, 'error'); return false; } };
    let exportURL = '', clipboard = null, undo = [], redo = [], monitorVolume = .8, lastMonitorVolume = .8;
    let playbackScene = null, pendingSeek = null, loadedKey = '', animation = 0, imageTick = 0;
    document.querySelectorAll('#speed-pills .pill-opt').forEach(button => button.title = 'Preview speed only; use Clip properties to change the export');
    const metadata = new Map(), music = new Audio(); music.loop = true;
    const originalVideo = $('real-preview-video');
    const video = originalVideo.cloneNode(false); originalVideo.replaceWith(video);
    const previewImage = make('img'); previewImage.id = 'timeline-preview-image'; $('preview-screen').append(previewImage);
    const empty = make('button', 'Import a video to start editing.', 'editor-empty'); empty.type='button'; empty.onclick=()=>openCreationPath('import'); $('preview-screen').append(empty);
    const retryPreview = make('button', 'Retry preview', 'btn btn-primary btn-sm'); retryPreview.id = 'editor-retry-preview';
    retryPreview.onclick = () => syncPreview(true);
    const previewNote = make('div', 'Timeline preview', 'editor-preview-note'); $('preview-screen').append(previewNote);
    const brand = make('div', '', 'editor-brand'); $('preview-screen').append(brand);
    const screenText = make('div'); screenText.id='editor-screen-text';
    screenText.style.cssText='position:absolute;top:12%;left:7%;width:86%;text-align:center;white-space:pre-wrap;overflow-wrap:anywhere;font-weight:800;font-size:clamp(14px,2vw,30px);color:white;text-shadow:0 2px 4px black;pointer-events:none;z-index:2';
    $('preview-screen').append(screenText);
    const regionPreview = make('div'); regionPreview.id = 'editor-region-preview';
    const regionImage = make('img'); regionImage.style.cssText = 'width:100%;height:100%;object-fit:cover'; regionPreview.append(regionImage);
    regionPreview.style.cssText = 'position:absolute;pointer-events:none;z-index:2;overflow:hidden'; $('preview-screen').append(regionPreview);
    const fadePreview = make('div'); fadePreview.id = 'editor-fade-preview';
    fadePreview.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:3'; $('preview-screen').append(fadePreview);
    const svgNS='http://www.w3.org/2000/svg', sharpenSVG=document.createElementNS(svgNS,'svg');
    sharpenSVG.setAttribute('width','0');sharpenSVG.setAttribute('height','0');sharpenSVG.style.position='absolute';
    const sharpenFilter=document.createElementNS(svgNS,'filter'),kernel=document.createElementNS(svgNS,'feConvolveMatrix');
    sharpenFilter.id='editor-sharpen';kernel.setAttribute('order','3');kernel.setAttribute('preserveAlpha','true');
    sharpenFilter.append(kernel);sharpenSVG.append(sharpenFilter);document.body.append(sharpenSVG);
    const download = make('a', 'Download edited MP4', 'btn btn-primary btn-sm'); download.id = 'editor-download'; download.hidden = true;
    download.target = '_blank'; download.rel = 'noopener'; download.setAttribute('download', 'edited-video.mp4');
    $('view-editor').querySelector('.topbar').append(download);

    function snapshot() { return {project: clone(S.collect()), scenes: clone(scenes()), time: currentTime, selected: window.selectedClipId}; }
    AgentPipeline.pushHistoryState = () => {
        if (S.busy()) throw new Error('Wait for the current export or import to finish.');
        pause(); undo.push(snapshot()); if (undo.length > 80) undo.shift(); redo = [];
    };
    function restore(stack, opposite) {
        if (S.busy()) return toast('Wait for the current job to finish.', 'error');
        if (!stack.length) return;
        pause(); opposite.push(snapshot()); const saved = stack.pop();
        S.setProject(saved.project); AgentPipeline.state.scenes = saved.scenes;
        AgentPipeline.state.aspectRatio = saved.project.aspect_ratio;
        selectedPreset = currentAspectRatio = saved.project.aspect_ratio;
        currentTime = saved.time; window.selectedClipId = saved.selected;
        S.updateViews();
    }
    AgentPipeline.undo = () => restore(undo, redo);
    AgentPipeline.redo = () => restore(redo, undo);
    window.undoEdit = AgentPipeline.undo; window.redoEdit = AgentPipeline.redo;

    function invalidateExport() {
        exportURL = ''; download.hidden = true; download.removeAttribute('href');
        window.lastVideoDownloadUrl = null; SmartEditBackend.lastVideoDownloadUrl = null;
        $('se-vp-download')?.setAttribute('style', 'display:none');
    }
    function info(scene) {
        if (!scene) return null;
        if (scene.asset_id) return {key: scene.asset_id, kind: scene.media_kind,
            url: base + '/assets/' + scene.asset_id + (scene.media_kind === 'video' ? '/preview' : ''),
            start: scene.sourceStart || 0, end: scene.sourceEnd, speed: scene.speed || 1};
        if (S.validPreview(scene)) return {key: scene.renderedAsset.asset_id, kind: 'video',
            url: base + '/assets/' + scene.renderedAsset.asset_id + '/preview', start: 0,
            end: scene.renderedAsset.duration, speed: scene.renderedAsset.duration / (scene.e - scene.s)};
        return null;
    }
    function sceneAt(time) { return scenes().find(s => time >= s.s && time < s.e) || (time >= DURATION ? scenes().at(-1) : null); }
    function stylePreview(scene) {
        const p = S.getProject(); if (!p) return;
        const screen = $('preview-screen'); screen.style.setProperty('--ar', p.aspect_ratio.replace(':', '/'));
        screen.style.aspectRatio = p.aspect_ratio.replace(':', '/'); screen.style.maxWidth = p.aspect_ratio === '9:16' ? '360px' : p.aspect_ratio === '1:1' ? '650px' : '100%';
        for (const el of [video, previewImage]) {
            el.style.objectFit = scene?.fit || 'contain'; el.style.transform = scene?.flip && !exportURL ? 'scaleX(-1)' : '';
            const amount=scene?.sharpness || 0;
            kernel.setAttribute('kernelMatrix',Array.from({length:9},(_,i)=>i===4?1+amount:-amount/8).join(' '));
            el.style.filter = exportURL ? '' : [
                {natural:'', warm:'sepia(.12) saturate(1.05)', vibrant:'saturate(1.15) contrast(1.03)', noir:'grayscale(1)'}[p.color || 'natural'],
                `brightness(${1+(scene?.brightness||0)}) contrast(${scene?.contrast??1}) saturate(${scene?.saturation??1})`,
                amount?'url(#editor-sharpen)':''
            ].join(' ');
        }
        video.muted = !exportURL && !!scene?.muted;
        video.volume = monitorVolume * (exportURL ? 1 : scene?.volume ?? 1);
        updateAudioControls();
        const sub = $('subtitle-display');
        const storyboard = !!scene && !exportURL && !info(scene);
        screen.classList.toggle('is-storyboard', storyboard);
        sub.tabIndex = storyboard ? 0 : -1;
        sub.setAttribute('aria-label', storyboard ? 'Scene script preview' : 'Captions');
        const seconds = Math.max(0, Math.round(DURATION || 0));
        $('preview-total-duration').textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
        document.querySelector('.subtitle-bar').style.display = !exportURL && p.captions ? (storyboard ? 'flex' : 'block') : 'none';
        let caption = scene?.text || '';
        const key = text => (text || '').normalize('NFC').trim().replace(/\s+/g, ' ');
        if (scene?.caption_words?.length && key(scene.caption_source_text) === key(caption)) {
            const start = scene.sourceStart || 0, end = scene.sourceEnd;
            const words = scene.caption_words.filter(w => w.end > start && w.start < end)
                .map(w => ({...w, start: Math.max(start,w.start), end: Math.min(end,w.end)}));
            const time = start + Math.max(0,currentTime-scene.s)*(scene.speed || 1);
            const groups = []; let group = [];
            for (const word of words) {
                if (group.length && (/[.!?।]["”’]*$/.test(group.at(-1).text) || group.length >= 7 || (word.start-group.at(-1).end)/(scene.speed || 1) > .45 ||
                    (word.end-group[0].start)/(scene.speed || 1) > 3)) { groups.push(group); group = []; }
                group.push(word);
            }
            if (group.length) groups.push(group);
            caption = (groups.find(g => time >= g[0].start && time < g.at(-1).end) || []).map(w => w.text).join(' ');
        }
        sub.textContent = p.captions ? caption : '';
        brand.textContent = exportURL ? '' : p.brand || '';
        screenText.textContent = exportURL ? '' : scene?.overlay_text || '';
        previewNote.textContent = exportURL ? 'Exported MP4 · ready to download' : 'Timeline preview · Export to download';
        const fx = scene?.effects || {}, progress = scene ? Math.max(0, Math.min(1,(currentTime-scene.s)/(scene.e-scene.s))) : 0;
        regionPreview.hidden = !!exportURL || !scene || !fx.region || fx.region === 'none';
        if (!regionPreview.hidden) {
            const w=fx.width??.25,h=fx.height??.25;
            Object.assign(regionPreview.style,{width:w*100+'%',height:h*100+'%',
                left:((fx.x??.5)+((fx.end_x??.5)-(fx.x??.5))*progress)*(1-w)*100+'%',
                top:((fx.y??.5)+((fx.end_y??.5)-(fx.y??.5))*progress)*(1-h)*100+'%',
                backdropFilter:fx.region==='blur'?'blur(8px)':'none'});
            regionImage.hidden=fx.region!=='image';
            if (fx.region==='image'&&fx.overlay_id) regionImage.src=base+'/assets/'+fx.overlay_id;
        }
        let fade=0;
        if (!exportURL&&scene&&p.transition&&p.transition!=='cut') {
            const d=Math.min(p.transition_duration??.3,(scene.e-scene.s)/2),index=scenes().indexOf(scene);
            if(index>0)fade=Math.max(fade,1-(currentTime-scene.s)/d);
            if(index<scenes().length-1)fade=Math.max(fade,1-(scene.e-currentTime)/d);
        }
        const explicitFade=!exportURL&&scene?.fade_out;
        if(explicitFade)fade=Math.max(fade,1-(scene.e-currentTime)/Math.min(.65,(scene.e-scene.s)/2));
        fadePreview.hidden=fade<=0;fadePreview.style.opacity=Math.max(0,Math.min(1,fade));
        fadePreview.style.background=!explicitFade&&p.transition==='fade_white'?'white':'black';
        if (!exportURL&&fx.key_enabled) previewNote.textContent='Chroma key enabled · Export to preview the replaced background';
        if (monitorVolume === 0) previewNote.textContent += ' · Preview muted — click the speaker to hear audio';
        else if (video.muted || video.volume === 0) previewNote.textContent += ' · Selected clip is muted';
        else if (storyboard) previewNote.textContent = 'Storyboard · Script preview only · Export to create video' + (p.narration ? ' and voice' : '');
    }
    function setPlayingUI() {
        $('play-pause-btn').textContent = isPlaying ? '❚❚' : '▶';
        $('play-overlay').style.display = 'none'; $('pip-box').style.display = 'none';
    }
    function pause() {
        isPlaying = false; video.pause(); music.pause(); cancelAnimationFrame(animation); clearInterval(playInterval);
        window.speechSynthesis?.cancel(); setPlayingUI();
    }
    function startVideo() {
        if (isPlaying && video.readyState >= 2 && pendingSeek === null) video.play().catch(error => {
            if (error.name !== 'AbortError') { pause(); toast('Preview could not play. Try seeking again or export this clip.', 'error'); }
        });
    }
    function applySeek() {
        if (pendingSeek !== null && video.readyState >= 1) {
            const target = Math.max(0, Math.min(pendingSeek, Math.max(0, video.duration - .001)));
            pendingSeek = null; video.currentTime = target;
            startVideo();
        }
    }
    function syncMusic(force) {
        const p = S.getProject();
        if (!p?.music_id || exportURL || !isPlaying) { music.pause(); return; }
        const url = base + '/assets/' + p.music_id;
        if (music.src !== url) music.src = url;
        music.volume = monitorVolume * p.music_volume; music.playbackRate = playbackSpeed;
        if (Number.isFinite(music.duration) && music.duration > 0 && (force || music.paused)) music.currentTime = currentTime % music.duration;
        music.play().catch(() => {});
    }
    function syncPreview(force = false) {
        const scene = sceneAt(currentTime), source = exportURL ? {key:exportURL, kind:'video', url:exportURL, start:0, speed:1} : info(scene);
        playbackScene = scene; stylePreview(scene); setPlayingUI();
        empty.hidden = !!source || !!(scene?.text && S.getProject()?.captions); empty.textContent = scenes().length ? 'Generate or export this scene to create its preview.' : 'Import a video to start editing.';
        previewImage.style.display = source?.kind === 'image' ? 'block' : 'none';
        video.style.display = source?.kind === 'video' ? 'block' : 'none';
        $('preview-bg-fallback').style.display = 'none';
        if (!source) { video.pause(); syncMusic(force); return; }
        if (source.kind === 'image') { video.pause(); previewImage.src = source.url; loadedKey = source.key; syncMusic(force); return; }
        video.playbackRate = Math.min(4, Math.max(.25, source.speed * playbackSpeed));
        const target = exportURL ? currentTime : source.start + (currentTime - scene.s) * source.speed;
        if (loadedKey !== source.key || !video.src || video.src !== source.url || (force && video.error)) {
            video.pause(); loadedKey = source.key; pendingSeek = target;
            video.src = source.url; video.load();
        } else if (force || Math.abs(video.currentTime - target) > .15) {
            pendingSeek = target; applySeek();
        } else startVideo();
        syncMusic(force);
    }
    video.addEventListener('loadedmetadata', applySeek);
    video.addEventListener('canplay', startVideo);
    video.addEventListener('seeked', startVideo);
    video.addEventListener('error', async () => {
        if (!video.getAttribute('src')) return;
        const failedURL = video.src;
        pause(); empty.hidden = false;
        empty.replaceChildren(make('p', 'Could not load this preview. Your timeline edits are preserved.'), retryPreview);
        let message;
        try {
            const health = await S.api('/local-health');
            if (health.production_api < 2 || !health.production_api)
                message = 'An older video backend is running. Save your project and relaunch SmartEdit to update it.';
        } catch { message = 'The video backend is offline. Relaunch SmartEdit, then reopen your saved project.'; }
        if (message && video.src === failedURL && video.error) empty.firstChild.textContent = message;
    });
    music.addEventListener('loadedmetadata', () => syncMusic(true));
    function nextScene() {
        const next = scenes()[scenes().indexOf(playbackScene) + 1];
        if (!next) { currentTime = DURATION; pause(); updatePlaybackUI(); return; }
        currentTime = next.s; syncPreview(true); updatePlaybackUI();
    }
    function frame(now) {
        if (!isPlaying) return;
        if (exportURL) {
            if (!video.seeking && pendingSeek === null) currentTime = Math.min(DURATION, video.currentTime);
            if (video.ended) { currentTime = DURATION; pause(); }
        } else {
            const source = info(playbackScene);
            if (source?.kind === 'video' && !video.seeking && pendingSeek === null && video.readyState >= 2) {
                if (video.ended || video.currentTime >= source.end - .015) nextScene();
                else currentTime = Math.max(playbackScene.s, Math.min(playbackScene.e, playbackScene.s + (video.currentTime - source.start) / source.speed));
            } else if (source?.kind === 'image' || !source) {
                currentTime += Math.min(.1, (now - imageTick) / 1000) * playbackSpeed;
                if (playbackScene && currentTime >= playbackScene.e) nextScene();
            }
        }
        imageTick = now; updatePlaybackUI(); if (isPlaying) animation = requestAnimationFrame(frame);
    }
    window.togglePlay = () => {
        if (isPlaying) return pause(); if (!scenes().length) return;
        if (currentTime >= DURATION - .02) currentTime = 0;
        isPlaying = true; imageTick = performance.now(); syncPreview(true); animation = requestAnimationFrame(frame);
    };
    window.seekTo = time => { currentTime = Math.max(0, Math.min(DURATION, Number(time) || 0)); syncPreview(true); updatePlaybackUI(); };
    window.setSpeed = (speed, el) => { playbackSpeed = speed; if (el) pickPill(el); syncPreview(true); };
    function updateAudioControls() {
        const slider = document.querySelector('.volume-slider');
        if (slider) slider.value = String(Math.round(monitorVolume * 100));
        const label = $('preview-volume-value');
        if (label) label.textContent = monitorVolume === 0 ? 'Muted' : Math.round(monitorVolume * 100) + '%';
        const button = $('preview-audio-toggle');
        if (button) {
            button.setAttribute('aria-pressed', String(monitorVolume === 0));
            button.title = monitorVolume === 0 ? 'Restore preview sound (does not change export)' : 'Mute preview only (does not change export)';
            button.setAttribute('aria-label', button.title);
            button.textContent = monitorVolume === 0 ? '🔇' : '🔊';
        }
    }
    window.volChange = value => {
        const volume = Number(value); if (!Number.isFinite(volume)) return;
        monitorVolume = Math.max(0, Math.min(1, volume / 100));
        if (monitorVolume > 0) lastMonitorVolume = monitorVolume;
        stylePreview(sceneAt(currentTime)); syncMusic(false);
    };
    window.togglePreviewMute = () => volChange(monitorVolume === 0 ? lastMonitorVolume * 100 : 0);
    updateAudioControls();
    window.loadRealVideo = url => { pause(); if (/\/jobs\/[a-f0-9]+\/file\/video/.test(url)) exportURL = url; syncPreview(true); };
    window.initEditor = () => { window.editorInited = true; buildTranscript(); buildDecisionPanel(); buildTimeline(); };
    AgentPipeline.speakScene = () => {}; // The source audio is the only voice in source preview.
    const oldPlaybackUI = window.updatePlaybackUI;
    window.updatePlaybackUI = () => { oldPlaybackUI(); stylePreview(sceneAt(currentTime)); };
    const oldGoTo = window.goTo;
    window.goTo = view => { if (view !== 'editor') pause(); oldGoTo(view); if (view === 'editor') syncPreview(true); };

    window.selectClip = id => {
        window.selectedClipId = id; AgentPipeline.state.currentSceneIndex = Math.max(0, scenes().findIndex(s => s.id === id));
        const scene = getSelectedScene(); if (scene && (currentTime < scene.s || currentTime >= scene.e)) seekTo(scene.s);
        buildTracks(); updateEditorToolbar(); buildDecisionPanel();
    };
    function sourceLimit(scene) { if (!scene.asset_id && S.validPreview(scene)) return scene.renderedAsset.duration; return scene.media_kind === 'image' && scene.asset_id ? 300 : metadata.get(scene.asset_id)?.duration || scene.sourceDuration || scene.sourceEnd || (scene.e - scene.s) * (scene.speed || 1); }
    function setRange(start, end, speed, values = {}) {
        const scene = getSelectedScene(); if (!scene) throw new Error('Select a clip first.');
        if (![start, end, speed].every(Number.isFinite) || start < 0 || end - start < .1 || end > sourceLimit(scene) + .01 || speed < .5 || speed > 2)
            throw new Error('Use a valid source range (at least 0.1s) and speed from 0.5× to 2×.');
        for(const [key,low,high] of [['brightness',-.15,.15],['contrast',.5,1.5],['saturation',0,2],['sharpness',0,1]])
            if(key in values&&(!Number.isFinite(values[key])||values[key]<low||values[key]>high))throw new Error(`${key} must be between ${low} and ${high}.`);
        S.history(); S.materialize(scene);
        const oldStart=scene.sourceStart||0,oldEnd=scene.sourceEnd||(scene.e-scene.s)*(scene.speed||1);
        if(!values.effects||['x','y','end_x','end_y'].every(key=>(values.effects[key]??.5)===(scene.effects?.[key]??.5)))
            values.effects=S.sliceEffects(values.effects||scene.effects,(start-oldStart)/(oldEnd-oldStart),(end-oldStart)/(oldEnd-oldStart));
        scene.sourceStart = start; scene.sourceEnd = end; scene.speed = speed; scene.e = scene.s + (end - start) / speed;
        Object.assign(scene, values); currentTime = scene.s; S.updateViews();
    }
    window.toggleClipMute = guarded(() => { const s = getSelectedScene(); if (!s) throw new Error('Select a clip first.'); S.history(); s.muted = !s.muted; S.updateViews(); });
    window.cutSelectedClip = guarded(() => { const s = getSelectedScene(); if (!s) throw new Error('Select a clip first.'); clipboard = clone(s); return deleteSelectedClip(); });
    window.pasteClip = guarded(() => {
        if (!clipboard) throw new Error('Cut or copy a clip first.'); S.history();
        const copy = clone(clipboard); copy.id = S.uid(); copy.studio_id = S.uid();
        const index = scenes().findIndex(s => s.id === window.selectedClipId); scenes().splice(index < 0 ? scenes().length : index + 1, 0, copy);
        window.selectedClipId = copy.id; S.updateViews();
    });
    function moveClip(id, beforeId) {
        const from = scenes().findIndex(s => s.id === id), to = scenes().findIndex(s => s.id === beforeId);
        if (from < 0 || to < 0 || from === to) return;
        S.history(); const [item] = scenes().splice(from, 1); scenes().splice(to, 0, item); S.updateViews(); seekTo(item.s);
    }
    window.moveSelectedClip = guarded(direction => { const i = scenes().findIndex(s => s.id === window.selectedClipId); if (i >= 0 && scenes()[i + direction]) moveClip(scenes()[i].id, scenes()[i + direction].id); });
    function trimDrag(event, scene, left, block) {
        event.stopPropagation(); event.preventDefault(); if (S.busy()) return;
        // Keep the existing DOM block alive while dragging; selectClip rebuilds the track.
        window.selectedClipId = scene.id; pause(); const source = info(scene), initial = event.clientX, start = source?.start ?? scene.sourceStart ?? 0, end = source?.end ?? scene.sourceEnd ?? (scene.e-scene.s)*scene.speed, speed = source?.speed || scene.speed || 1;
        let a = start, b = end;
        const move = e => { const delta = (e.clientX - initial) / tlZoom * speed;
            a = left ? Math.max(0, Math.min(end - .1, start + delta)) : start;
            b = left ? end : Math.min(sourceLimit(scene), Math.max(start + .1, end + delta));
            block.style.width = Math.max(5, (b - a) / speed * tlZoom) + 'px'; };
        const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); if (a !== start || b !== end) guarded(setRange)(a, b, speed); };
        window.addEventListener('pointermove', move); window.addEventListener('pointerup', up, {once:true});
    }
    window.buildTracks = () => {
        const tracks = $('tl-tracks'); tracks.replaceChildren();
        const row = label => { const r = make('div', null, 'tl-track-row'); r.append(make('div', label, 'tl-track-label')); const area = make('div', null, 'tl-track-area'); area.style.minWidth = Math.max(200, DURATION * tlZoom) + 'px'; r.append(area); tracks.append(r); return area; };
        const area = row('VIDEO');
        if (!scenes().length) area.append(make('span', 'Add media to start your timeline', 'editor-timeline-empty'));
        for (const [index, s] of scenes().entries()) {
            const block = make('div', null, 'tl-clip' + (s.id === window.selectedClipId ? ' selected' : '') + (s.muted ? ' muted' : ''));
            block.dataset.sceneId = s.id; block.style.left = s.s * tlZoom + 'px'; block.style.width = Math.max(5, (s.e - s.s) * tlZoom) + 'px';
            block.style.background = 'linear-gradient(135deg,#263d69,#48346c)';
            const name = metadata.get(s.asset_id)?.name || 'Clip ' + (index + 1);
            block.append(make('span', (s.muted ? '🔇 ' : '') + name, 'tl-clip-label'), make('span', (s.speed || 1) + '×', 'tl-clip-speed'));
            block.title = `${name} · ${s.s.toFixed(2)}–${s.e.toFixed(2)}s. Drag to reorder; drag edges to trim.`;
            block.onclick = e => { e.stopPropagation(); selectClip(s.id); seekTo(s.s + Math.max(0, Math.min(s.e - s.s - .001, (e.clientX - block.getBoundingClientRect().left) / tlZoom))); };
            block.draggable = true; block.ondragstart = e => e.dataTransfer.setData('text/plain', String(s.id));
            block.ondragover = e => e.preventDefault(); block.ondrop = e => { e.preventDefault(); e.stopPropagation(); const from = scenes().find(x => String(x.id) === e.dataTransfer.getData('text/plain')); if (from) guarded(moveClip)(from.id, s.id); };
            for (const left of [true, false]) { const handle = make('div', '⋮', 'tl-trim-handle ' + (left ? 'left' : 'right')); handle.draggable = false; handle.onpointerdown = e => trimDrag(e, s, left, block); handle.onclick = e => e.stopPropagation(); block.append(handle); }
            area.append(block);
        }
        const captions = row('CAPTIONS');
        for (const s of scenes().filter(s => s.text)) { const b = make('div', s.text, 'tl-block'); b.style.cssText = `left:${s.s*tlZoom}px;width:${(s.e-s.s)*tlZoom}px;background:#153b45`; b.onclick = e => { e.stopPropagation(); selectClip(s.id); }; captions.append(b); }
        const p = S.getProject(); if (p?.music_id) { const audio = row('MUSIC'); const b = make('div', '♫ Background music · ' + Math.round(p.music_volume * 100) + '%', 'tl-audio-clip'); b.style.width = DURATION * tlZoom + 'px'; audio.append(b); }
    };
    window.zoomTL = (direction, fit) => { tlZoom = fit ? Math.max(4, Math.min(200, ($('tl-body').clientWidth - 110) / Math.max(DURATION, 1))) : Math.max(4, Math.min(200, tlZoom + direction * 10)); buildTimeline(); updatePlayhead(); };

    function field(form, label, id, type, value, options) {
        const row = make('label', null, 'editor-field'); row.append(make('span', label));
        const input = make(type === 'select' ? 'select' : type === 'textarea' ? 'textarea' : 'input'); input.id = id;
        if (type === 'select') for (const [v, text] of options) { const option = make('option', text); option.value = v; input.append(option); }
        else if (type !== 'textarea') input.type = type;
        if (type === 'checkbox') input.checked = !!value; else input.value = value;
        if (type === 'number') input.step = '.01'; row.append(input); form.append(row); return input;
    }
    window.buildDecisionPanel = () => {
        const host = $('decision-list'); host.replaceChildren();
        const s = getSelectedScene(), p = S.getProject();
        if (!p) return;
        const form = make('form'); form.append(make('h3', s ? 'Clip properties' : 'Select a video clip'));
        if (s) {
            const source = info(s);
            field(form, 'Source in (seconds)', 'clip-source-in', 'number', source?.start ?? s.sourceStart ?? 0).min = '0';
            field(form, 'Source out (seconds)', 'clip-source-out', 'number', source?.end ?? s.sourceEnd ?? (s.e-s.s)*(s.speed||1)).max = sourceLimit(s);
            const speed = field(form, 'Clip speed', 'clip-speed', 'number', source?.speed || s.speed || 1); speed.min = '.5'; speed.max = '2';
            const volume = field(form, 'Clip volume (0–100%)', 'clip-volume', 'number', Math.round((s.volume ?? 1)*100)); volume.min='0'; volume.max='100';
            field(form, 'Frame fit', 'clip-fit', 'select', s.fit || 'contain', [['contain','Fit full frame'],['cover','Fill / center crop']]);
            field(form, 'Mirror horizontally', 'clip-flip', 'checkbox', s.flip);
            field(form, 'Mute source audio', 'clip-muted', 'checkbox', s.muted);
            field(form, 'Caption text', 'clip-caption', 'textarea', s.text || '');
            field(form, 'Screen text (separate from speech)', 'clip-screen-text', 'textarea', s.overlay_text || '').maxLength=300;
            field(form, 'Fade this scene to black', 'clip-fade-out', 'checkbox', s.fade_out);
            for(const [key,label,value,min,max] of [['brightness','Brightness',s.brightness??0,-.15,.15],['contrast','Contrast',s.contrast??1,.5,1.5],['saturation','Saturation',s.saturation??1,0,2],['sharpness','Sharpen',s.sharpness??0,0,1]]) {
                const control=field(form,label,'clip-'+key,'number',value);control.min=min;control.max=max;
            }
            const fx=s.effects||{},effects=make('details');effects.append(make('summary','Background & moving effects'));form.append(effects);
            field(effects,'Remove screen color (export)','fx-key-enabled','checkbox',fx.key_enabled);
            field(effects,'Screen color to remove','fx-key-color','color',fx.key_color||'#00ff00');
            const similarity=field(effects,'Color tolerance (0.01–0.5)','fx-similarity','number',fx.key_similarity??.15);similarity.min='.01';similarity.max='.5';
            const blend=field(effects,'Edge softness (0–0.3)','fx-blend','number',fx.key_blend??.05);blend.min='0';blend.max='.3';
            field(effects,'Replacement background color','fx-background-color','color',fx.background_color||'#182438');
            const chooseImage=(label,key)=>{
                const button=make('button',label,'btn btn-secondary btn-sm');button.type='button';
                button.onclick=()=>{const picker=make('input');picker.type='file';picker.accept='image/*';picker.onchange=guarded(async()=>{
                    if(!picker.files[0])return;if(S.busy())throw new Error('Wait for the current job.');
                    const media=await S.upload(picker.files[0]);if(media.kind!=='image')throw new Error('Choose an image.');
                    if(S.busy()||!scenes().includes(s))throw new Error('Selection changed; choose the image again.');
                    S.history();s.effects={...s.effects,[key]:media.id};
                    if(key==='overlay_id')s.effects.region='image';else s.effects.key_enabled=true;
                    S.updateViews();toast('Image attached to this clip.');
                });picker.click();};effects.append(button);
            };
            chooseImage(fx.background_id?'Replace background image':'Choose background image','background_id');
            if(fx.background_id){const remove=make('button','Use solid background','btn btn-secondary btn-sm');remove.type='button';remove.onclick=guarded(()=>{S.history();s.effects.background_id='';S.updateViews();});effects.append(remove);}
            field(effects,'Moving region','fx-region','select',fx.region||'none',[['none','Off'],['blur','Blur area'],['image','Image overlay']]);
            chooseImage(fx.overlay_id?'Replace overlay image':'Choose overlay image','overlay_id');
            for(const [key,label,def] of [['width','Region width %',.25],['height','Region height %',.25],['x','Start horizontal %',.5],['y','Start vertical %',.5],['end_x','End horizontal %',.5],['end_y','End vertical %',.5]]){
                const control=field(effects,label,'fx-'+key,'number',(fx[key]??def)*100);control.min=['width','height'].includes(key)?'5':'0';control.max='100';
            }
            effects.append(make('p','Manual linear motion across this clip: 0% is left/top, 100% is right/bottom. Preview blur is approximate. Chroma key needs a plain colored screen; it does not remove arbitrary backgrounds.','editor-help'));
            const apply = make('button', 'Apply clip changes', 'btn btn-primary btn-sm'); apply.type = 'submit'; form.append(apply);
            form.onsubmit = guarded(e => { e.preventDefault(); const volume = Number($('clip-volume').value); if (!Number.isFinite(volume) || volume < 0 || volume > 100) throw new Error('Volume must be between 0 and 100%.');
                const effects={...s.effects,key_enabled:$('fx-key-enabled').checked,key_color:$('fx-key-color').value,background_color:$('fx-background-color').value,key_similarity:Number($('fx-similarity').value),key_blend:Number($('fx-blend').value),region:$('fx-region').value};
                if(!Number.isFinite(effects.key_similarity)||effects.key_similarity<.01||effects.key_similarity>.5)throw new Error('Color tolerance must be 0.01–0.5.');
                if(!Number.isFinite(effects.key_blend)||effects.key_blend<0||effects.key_blend>.3)throw new Error('Edge softness must be 0–0.3.');
                for(const key of ['width','height','x','y','end_x','end_y']){effects[key]=Number($('fx-'+key).value)/100;const min=['width','height'].includes(key) ? 0.05 : 0;if(!Number.isFinite(effects[key])||effects[key]<min||effects[key]>1)throw new Error('Use valid region percentages.');}
                if(effects.region==='image'&&!effects.overlay_id)throw new Error('Choose an overlay image first.');
                setRange(Number($('clip-source-in').value), Number($('clip-source-out').value), Number($('clip-speed').value), {effects,volume:volume/100, fit:$('clip-fit').value, flip:$('clip-flip').checked, muted:$('clip-muted').checked, text:$('clip-caption').value,
                    overlay_text:$('clip-screen-text').value,fade_out:$('clip-fade-out').checked,
                    brightness:Number($('clip-brightness').value),contrast:Number($('clip-contrast').value),saturation:Number($('clip-saturation').value),sharpness:Number($('clip-sharpness').value)}); });
        }
        host.append(form);
        if (p.generation_mode === 'avatar' && s && s.media_kind !== 'video') {
            const slides=make('form');slides.append(make('h3','Explainer slide'));
            field(slides,'Slide heading','slide-title','text',s.slide_title||'').maxLength=100;
            field(slides,'Key points (one per line, up to 3)','slide-points','textarea',(s.slide_points||[]).join('\n'));
            field(slides,'Spoken explanation','slide-narration','textarea',s.text||'');
            const saveSlide=make('button','Apply slide & narration','btn btn-primary btn-sm');saveSlide.type='submit';slides.append(saveSlide);
            slides.onsubmit=guarded(e=>{e.preventDefault();const points=$('slide-points').value.split('\n').map(v=>v.trim()).filter(Boolean);
                if(points.length>3||points.some(v=>v.length>180))throw new Error('Use up to 3 points, each at most 180 characters.');
                const changes={slide_title:$('slide-title').value,slide_points:points,text:$('slide-narration').value};
                if(changes.text.length>5000)throw new Error('Narration must be under 5000 characters.');
                S.history();Object.assign(s,changes);delete s.renderedAsset;S.updateViews();toast('Slide updated. Export regenerates narration and presenter; cached images are reused.');});
            host.append(slides);
        }
        const output = make('form'); output.append(make('h3', 'Video settings'));
        if(p.generation_mode==='avatar') {
            field(output,'Presenter layout','editor-presenter-layout','select',p.presenter_layout||'side',[['side','Side-by-side'],['pip-right','Picture-in-picture · Right'],['pip-left','Picture-in-picture · Left']]);
            field(output,'Illustrated presenter','editor-presenter-character','select',p.presenter_character||'alex',[['alex','Alex'],['maya','Maya']]);
            field(output,'Presenter theme','editor-presenter-theme','select',p.presenter_theme||'indigo',[['indigo','Indigo'],['teal','Teal']]);
            output.append(make('p','Export applies presenter changes to generated slides. Video clips already contain their rendered presenter.','editor-help'));
        }
        field(output, 'Aspect ratio', 'editor-ratio', 'select', p.aspect_ratio, [['16:9','Landscape · 16:9'],['9:16','Portrait · 9:16'],['1:1','Square · 1:1']]);
        field(output, 'Color look', 'editor-color', 'select', p.color || 'natural', [['natural','Original'],['warm','Warm'],['vibrant','Vibrant'],['noir','Black & white']]);
        field(output,'Between clips','editor-transition','select',p.transition||'cut',[['cut','Cut'],['fade_black','Fade through black'],['fade_white','Fade through white']]);
        const td=field(output,'Fade duration per side (0.1–1s)','editor-transition-duration','number',p.transition_duration??.3);td.min='.1';td.max='1';
        field(output, 'Show captions', 'editor-captions', 'checkbox', p.captions);
        field(output, 'Watermark / title', 'editor-brand', 'text', p.brand || '').maxLength=60;
        field(output, 'Reduce source noise (export)', 'editor-denoise', 'checkbox', p.denoise);
        field(output, 'Automatic instrumental (export)', 'editor-auto-music', 'select', p.auto_music || 'off', [['off','Off'],['cinematic','Cinematic'],['uplifting','Uplifting'],['calm','Calm']]);
        const mv = field(output, 'Background music (0–50%)', 'editor-music-volume', 'number', Math.round(p.music_volume * 100)); mv.min='0'; mv.max='50';
        const apply = make('button', 'Apply video settings', 'btn btn-primary btn-sm'); apply.type='submit'; output.append(apply);
        output.onsubmit = guarded(e => { e.preventDefault(); const mv=Number($('editor-music-volume').value); if (!Number.isFinite(mv)||mv<0||mv>50) throw new Error('Music volume must be between 0 and 50%.');
            const transitionDuration=Number($('editor-transition-duration').value);if(!Number.isFinite(transitionDuration)||transitionDuration<.1||transitionDuration>1)throw new Error('Fade duration must be 0.1–1 seconds.');
            const changes={transition:$('editor-transition').value,transition_duration:transitionDuration,aspect_ratio:$('editor-ratio').value,color:$('editor-color').value,captions:$('editor-captions').checked,brand:$('editor-brand').value,denoise:$('editor-denoise').checked,music_volume:mv/100,auto_music:$('editor-auto-music').value};
            if(p.generation_mode==='avatar')Object.assign(changes,{presenter_layout:$('editor-presenter-layout').value,presenter_character:$('editor-presenter-character').value,presenter_theme:$('editor-presenter-theme').value});
            S.history(); Object.assign(p, changes); AgentPipeline.state.aspectRatio = selectedPreset = currentAspectRatio = p.aspect_ratio; S.updateViews(); });
        if (p.music_id) { const remove=make('button','Remove music','btn btn-secondary btn-sm'); remove.type='button'; remove.onclick=guarded(()=>{S.history();p.music_id='';music.pause();S.updateViews();}); output.append(remove); }
        output.append(make('p', 'Color and screen-text preview are approximate. Export applies final typography, audio cleanup, automatic instrumental and music ducking. Uploaded music takes priority.', 'editor-help')); host.append(output);
    };
    $('view-editor').querySelector('.panel-right .panel-label').textContent = 'CLIP & VIDEO SETTINGS';
    $('de-tabs').style.display = 'none';
    let editController=null;
    const editStatus=$('edit-agent-status');
    function reportEdit(message,state='ready',changes=[]) {
        editStatus.dataset.state=state;editStatus.replaceChildren(make('div',message));
        if(changes.length){const list=make('ul');for(const text of changes)list.append(make('li',text));editStatus.append(list);}
    }
    for(const [label,command] of [['Natural polish','Make the video natural and clean'],['Make a reel','Portrait, volume 50%, brighten'],['Trim footage','Keep 2 to 8 seconds'],['Caption text','Add caption "Welcome"']]) {
        const button=make('button',label);button.onclick=()=>{$('ed-nl-input').value=command;$('ed-nl-input').focus();};$('edit-agent-examples').append(button);
    }
    const connectAI=make('button','Connect AI');connectAI.onclick=()=>goTo('settings');$('edit-agent-examples').append(connectAI);
    $('edit-agent-cancel').onclick=()=>editController?.abort();
    window.handleNLCommand = async id => {
        if(editController)return;
        const input=$(id),command=input.value.trim();if(!command)return;
        if(S.busy()){reportEdit('Wait for the current export or import to finish.','error');return;}
        const shortcuts={undo:undoEdit,redo:redoEdit,'trim in':trimClipLeft,'trim out':trimClipRight};
        if(shortcuts[command.toLowerCase()]) {await guarded(shortcuts[command.toLowerCase()])();input.value='';return;}
        const controller=new AbortController();editController=controller;
        $('edit-agent-apply').disabled=true;$('edit-agent-apply').textContent='Understanding…';$('edit-agent-cancel').hidden=false;
        const timer=setTimeout(()=>controller.abort(),100000);
        try {
            pause();
            const before=JSON.stringify(S.collect()),requestProject=JSON.parse(before);
            requestProject.scenes.forEach((clip,i)=>{const rendered=S.validPreview(scenes()[i])&&scenes()[i].renderedAsset;if(!clip.asset_id&&rendered){clip.asset_id=rendered.asset_id;clip.media_kind='video';clip.start=0;clip.end=rendered.duration;clip.speed=rendered.duration/(scenes()[i].e-scenes()[i].s);}});
            reportEdit('Understanding your request and validating supported edits…');
            const selectedId=getSelectedScene()?.studio_id||'';
            const result=await S.api('/edit','POST',{project:requestProject,command,scope:$('edit-agent-scope').value,selected_id:selectedId,playhead:currentTime},{signal:controller.signal});
            if(controller.signal.aborted)throw new DOMException('Cancelled','AbortError');
            if(result.status!=='applied'){reportEdit(result.message,'error');return;}
            if(S.busy()||JSON.stringify(S.collect())!==before)throw new Error('The timeline changed while the assistant was thinking. Please apply your request again to the updated video.');
            const time=currentTime;S.history();S.loadProject(result.project,'agent');
            const selected=scenes().find(s=>s.studio_id===selectedId);if(selected)selectClip(selected.id);
            seekTo(Math.min(time,DURATION));input.value='';
            reportEdit(`${result.engine} · Edits applied. Review the preview, then Export. Ctrl+Z undoes this request.`,'applied',result.changes);
            toast('Edits applied to the video timeline.');
        } catch(error) {
            reportEdit(error.name==='AbortError'?'Edit cancelled or timed out. No changes were applied.':error.message,'error');
        } finally {
            clearTimeout(timer);editController=null;$('edit-agent-apply').disabled=false;$('edit-agent-apply').textContent='Apply edits';$('edit-agent-cancel').hidden=true;
        }
    };
    async function importMedia(files) {
        if (!files.length) return;
        if (scenes().length + files.length > 30) throw new Error('A project supports up to 30 clips.');
        const received=[];
        for (const file of files) { const media=await S.upload(file); if (!['video','image'].includes(media.kind)) throw new Error('Add video or image files here. Use + Audio for music.'); received.push(media); }
        // Commit all successfully validated uploads together, so one undo restores the timeline.
        S.history();
        for (const media of received) { metadata.set(media.id, media); scenes().push({id:S.uid(),studio_id:S.uid(),asset_id:media.id,media_kind:media.kind,sourceStart:0,sourceEnd:media.kind==='video'?media.duration:5,s:0,e:media.kind==='video'?media.duration:5,speed:1,volume:1,fit:'contain',flip:false,muted:false,text:'',vis:{query:'',label:media.name},layout:'full-presenter'}); }
        window.selectedClipId=scenes().at(-1).id; S.updateViews(); seekTo(scenes().at(-1).s);
    }
    const toolbar=$('video-edit-toolbar');
    function tool(text, action, id) { const button=make('button',text,'edit-tool-btn'); if(id)button.id=id;button.onclick=guarded(action);toolbar.append(button);return button; }
    tool('+ Media',()=>{const input=make('input');input.type='file';input.accept='video/*,image/*';input.multiple=true;input.onchange=guarded(()=>importMedia([...input.files]));input.click();},'editor-add-media');
    tool('← Move',()=>moveSelectedClip(-1),'editor-move-left'); tool('Move →',()=>moveSelectedClip(1),'editor-move-right'); tool('Paste',()=>pasteClip(),'editor-paste');
    window.addAudioTrack = () => {const input=make('input');input.type='file';input.accept='audio/*';input.onchange=guarded(async()=>{if(!input.files[0])return;const media=await S.upload(input.files[0]);if(media.kind!=='audio')throw new Error('Choose an audio file.');S.history();S.getProject().music_id=media.id;S.updateViews();});input.click();};
    const ratioChange = guarded(ratio => { if (!S.getProject() || !['16:9','9:16','1:1'].includes(ratio)) return; S.history(); S.getProject().aspect_ratio=ratio; AgentPipeline.state.aspectRatio=selectedPreset=currentAspectRatio=ratio; S.updateViews(); });
    window.switchAspectRatio = ratioChange; window.setExportPreset=ratioChange;
    function syncExportOptions() {
        const p=S.getProject();if(!p)return;
        document.querySelectorAll('#export-modal .pill-opt').forEach(el=>{
            if(/\((16:9|9:16|1:1)\)/.test(el.textContent)) el.classList.toggle('active',el.textContent.includes(p.aspect_ratio));
        });
        document.querySelector('#export-modal .toggle').classList.toggle('on',!!p.captions);
        for(const ratio of ['16:9','9:16','1:1']) {const el=$('ar-btn-'+ratio.replace(':','-'));if(el){el.classList.toggle('active',ratio===p.aspect_ratio);el.style.background=ratio===p.aspect_ratio?'var(--purple)':'transparent';}}
    }
    const oldOpenModal=window.openModal;
    window.openModal=id=>{if(id==='export-modal'){syncExportOptions();$('export-progress-wrap').style.display='none';}oldOpenModal(id);};
    const oldExport=window.startExport;
    window.startExport=()=>{if(!S.busy()){pause();invalidateExport();syncPreview(true);}return oldExport();};
    window.addEventListener('studio:changed', event => {
        pause();
        const reason=event.detail.reason;
        if(editStatus.dataset.state==='applied'&&!['agent','export'].includes(reason))reportEdit('Timeline updated. The preview shows your current edits.');
        if(reason==='load'||reason==='import'){undo=[];redo=[];clipboard=null;window.selectedClipId=scenes()[0]?.id??null;loadedKey='';invalidateExport();}
        else if(reason==='export'){exportURL=window.lastVideoDownloadUrl||'';download.href=exportURL+'?download=1';download.hidden=!exportURL;}
        else invalidateExport();
        if(!scenes().some(s=>s.id===window.selectedClipId))window.selectedClipId=scenes()[0]?.id??null;
        syncExportOptions();buildTracks();buildDecisionPanel();updateEditorToolbar();toolbar.style.display='flex';syncPreview(true);
        $('ed-project-sub').textContent=`${scenes().length} CLIPS · ${DURATION.toFixed(2)}s · ${reason==='export'?'EXPORTED':'EDITABLE TIMELINE'}`;
        for(const s of scenes()) if(s.asset_id&&!metadata.has(s.asset_id)) {
            metadata.set(s.asset_id, null);
            S.api('/assets/'+s.asset_id+'/metadata').then(meta=>{metadata.set(s.asset_id,meta);s.sourceDuration=meta.duration;if(!document.activeElement?.closest('#decision-list'))buildDecisionPanel();buildTracks();}).catch(()=>metadata.delete(s.asset_id));
        }
    });
    // Capture prevents the legacy keyboard listener from cutting while typing or turning Ctrl+S into Split.
    document.addEventListener('keydown',e=>{
        if(currentView!=='editor')return;
        if(e.target.closest?.('input,textarea,select,[contenteditable="true"]')){e.stopImmediatePropagation();return;}
        if(document.querySelector('.modal-overlay.open'))return;
        e.stopImmediatePropagation(); const mod=e.ctrlKey||e.metaKey;
        if(mod&&e.code==='KeyS'){e.preventDefault();guarded(async()=>{await window.SmartEditSafety.save();})();return;}
        if(mod&&e.code==='KeyC'){e.preventDefault();if(getSelectedScene())clipboard=clone(getSelectedScene());return;}
        if(mod&&e.code==='KeyV'){e.preventDefault();pasteClip();return;}
        if(mod&&e.code==='KeyZ'){e.preventDefault();e.shiftKey?redoEdit():undoEdit();return;}
        if(mod&&e.code==='KeyY'){e.preventDefault();redoEdit();return;}
        const actions={Space:togglePlay,KeyS:splitClipAtPlayhead,KeyX:cutSelectedClip,Delete:deleteSelectedClip,Backspace:deleteSelectedClip,BracketLeft:trimClipLeft,BracketRight:trimClipRight,ArrowLeft:()=>seekDelta(e.shiftKey?-5:-1/30),ArrowRight:()=>seekDelta(e.shiftKey?5:1/30),KeyJ:()=>seekDelta(-5),KeyL:()=>seekDelta(5),KeyM:toggleClipMute,Escape:()=>selectClip(null)};
        if(actions[e.code]){e.preventDefault();actions[e.code]();}
    },true);
    window.SmartEditEditor={info,sceneAt,setRange,moveClip,importMedia,pause,syncPreview,snapshot,metadata};
})();
