
function escapeSceneHTML(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character])); }
/**
 * frontend/app.js
 * ─────────────────────────────────────────────────────────────
 * Core Frontend Application Controller connected to 16 Local AI Agents:
 *   - Inter-Agent State Sync (AgentPipeline integration)
 *   - Video Player Canvas, Layout Engine (Full, Split, PiP, Slides, Dual Conversation)
 *   - Real Speech Synthesis Voice Agent & Lip-Sync Animation
 *   - Natural Language Edit Agent Execution
 *   - Platform Aspect Ratio Reframing
 */

var currentView = 'landing';
var isPlaying = false;
var currentTime = 0;
var playbackSpeed = 1;
var playInterval = null;
var tlZoom = 30; // px per second
var DURATION = 30;

/* ─── NAVIGATION ─────────────────────────────────────────── */
function goTo(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const el = document.getElementById('view-' + view);
  if (el) { 
    el.classList.add('active'); 
    window.currentView = view;
    currentView = view;
  }
  
  if (view === 'editor') initEditor();
  if (view === 'agents') initAgents();
  if (view === 'processing') startPipeline();
  if (view === 'library') initLibrary();
  if (view === 'architecture') initArch();
  if (view === 'analytics') initAnalytics();
  if (view === 'dashboard') window.refreshStudioProjects?.();
}

/* ─── ASPECT RATIO SWITCHER (merged) ─────────────────────── */
var currentAspectRatio = '16:9';
function switchAspectRatio(ratio, el) {
  currentAspectRatio = ratio;

  // Push undo history
  if (window.AgentPipeline) {
    window.AgentPipeline.pushHistoryState();
    window.AgentPipeline.state.aspectRatio = ratio;
  }

  // Update preview screen size
  var screen = document.getElementById('preview-screen');
  if (screen) {
    var arMap = { '16:9': '16/9', '9:16': '9/16', '1:1': '1/1' };
    var maxWMap = { '16:9': '860px', '9:16': '320px', '1:1': '520px' };
    var resolvedAr = arMap[ratio] || '16/9';
    screen.style.aspectRatio = resolvedAr;
    screen.style.setProperty('--ar', resolvedAr);
    screen.style.maxWidth = maxWMap[ratio] || '860px';
  }

  // Update real video element aspect ratio
  var realVideo = document.getElementById('real-preview-video');
  if (realVideo) {
    realVideo.style.aspectRatio = ratio.replace(':', '/');
  }

  // Highlight active ratio button
  var allBtns = ['ar-btn-16-9','ar-btn-9-16','ar-btn-1-1'];
  allBtns.forEach(function(id) {
    var btn = document.getElementById(id);
    if (btn) { btn.style.background = 'transparent'; btn.style.color = 'var(--t4)'; btn.classList.remove('active'); }
  });
  if (el) { el.style.background = 'var(--purple)'; el.style.color = '#fff'; el.classList.add('active'); }

  // Sync with export preset
  if (typeof selectedPreset !== 'undefined') { window.selectedPreset = ratio; }

  var labelMap = { '16:9': 'YouTube 16:9', '9:16': 'Reels / Shorts 9:16', '1:1': 'Square 1:1' };
  toast('Aspect Ratio: ' + (labelMap[ratio] || ratio));

  // Re-render video with new aspect ratio
  if (window.AgentPipeline) window.AgentPipeline.reRenderVideoAfterEdit();
}

function scrollToSection(id) {
  const el = document.getElementById(id);
  if (el) el.scrollIntoView({behavior:'smooth'});
}

function sideNav(el, view) {
  document.querySelectorAll('#sidebar-dash .nav-item').forEach(n => n.classList.remove('active'));
  el.classList.add('active');
}

function subTab(el, evt) {
  if(evt) evt.stopPropagation();
  el.closest('.sub-tabs').querySelectorAll('.sub-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
}

function pickPill(el) {
  el.closest('.pill-group').querySelectorAll('.pill-opt').forEach(o => o.classList.remove('active'));
  el.classList.add('active');
}

/* ─── TOAST NOTIFICATION ──────────────────────────────────── */
var toastTimer = null;
function toast(msg, type='success') {
  const t = document.getElementById('toast');
  if (!t) return;
  document.getElementById('toast-msg').textContent = msg;
  t.classList.add('visible');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('visible'), 3200);
}

/* ─── EDITOR CORE ENGINE ─────────────────────────────────── */
var editorInited = false;
window.editorInited = false; // allow upload.js to reset this
function initEditor() {
  // Allow re-init if editorInited was reset externally (e.g. new file loaded)
  if (window.editorInited) return;
  window.editorInited = true;
  editorInited = true;
  buildTranscript();
  buildDecisionPanel();
  buildTimeline();
  renderPreviewCanvas();

  // If there's a local video file already selected, load it immediately
  const blobURL = window.SmartEditBackend && window.SmartEditBackend.localObjectURL;
  if (blobURL && !window.SmartEditStudio?.getProject()) {
    requestAnimationFrame(() => {
      window.loadRealVideo(blobURL);
      const file = window.SmartEditBackend.selectedFile;
      if (file) {
        const titleEl = document.getElementById('ed-project-title');
        if (titleEl) {
          titleEl.textContent = file.name;
        }
      }
    });
  }
}

function buildTranscript() {
  const panel = document.getElementById('transcript-list');
  if (!panel) return;
  panel.innerHTML = '';

  const scenes = (window.AgentPipeline && AgentPipeline.state.scenes) ? AgentPipeline.state.scenes : (typeof TRANSCRIPT !== 'undefined' ? TRANSCRIPT : []);

  if (scenes.length === 0) {
    panel.innerHTML = `<div style="padding:40px 20px;text-align:center;color:var(--t4);font-size:12px">No transcript yet. Upload a real video or audio file to run Whisper.</div>`;
    return;
  }

  scenes.forEach((item, i) => {
    const el = document.createElement('div');
    el.className = 'tr-item' + (i === 0 ? ' active' : '');
    el.id = 'tr-' + item.id;
    el.onclick = () => seekTo(item.s);
    el.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
        <span class="tr-time">${fmt(item.s)} – ${fmt(item.e)}</span>
        <div style="display:flex;gap:4px;align-items:center">
          <span class="tag ${item.vis ? 'tag-c' : 'tag-p'}" style="font-size:8px">${escapeSceneHTML(item.layout ? item.layout.toUpperCase() : 'SPEECH')}</span>
          <span style="font-size:9px;color:var(--t4)">${typeof item.conf === 'number' ? Math.round(item.conf) + '%' : '—'}</span>
        </div>
      </div>
      <p class="tr-text">${escapeSceneHTML(item.text)}</p>
      <div class="flex gap-6 items-center" style="margin-top:6px">
        <span class="tr-keyword">#${escapeSceneHTML(item.keyword)}</span>
        <span style="font-size:9px;color:var(--cyan)">${escapeSceneHTML(item.speaker || 'Presenter')}</span>
      </div>
    `;
    panel.appendChild(el);
  });
}

function buildDecisionPanel() {
  const panel = document.getElementById('decision-list');
  if (!panel) return;
  panel.innerHTML = '';

  const scenes = (window.AgentPipeline && AgentPipeline.state.scenes) ? AgentPipeline.state.scenes : (typeof TRANSCRIPT !== 'undefined' ? TRANSCRIPT : []);

  if (scenes.length === 0) {
    panel.innerHTML = `<div style="padding:40px 20px;text-align:center;color:var(--t4);font-size:12px">No Whisper transcript segments loaded yet.</div>`;
    return;
  }

  scenes.forEach((item) => {
    const el = document.createElement('div');
    el.className = 'dec-card' + (item.vis ? '' : '');
    el.id = 'dec-' + item.id;
    el.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span class="mono" style="font-size:9px;color:var(--t4)">${fmt(item.s)} — ${fmt(item.e)}</span>
        <span class="tag ${item.vis ? 'tag-c' : 'tag-p'}" style="font-size:8px">${escapeSceneHTML(item.layout || 'PRESENTER')}</span>
      </div>
      <div class="dec-label" style="font-size:10px;font-weight:800;color:var(--t4);margin-bottom:3px">AGENT: ${escapeSceneHTML(item.agent || 'Compositor Agent')}</div>
      ${item.vis ? `
        <div style="font-size:11px;color:var(--t2);margin-bottom:7px;line-height:1.4">"${escapeSceneHTML(item.vis.query)}"</div>
        <div class="dec-asset-preview" style="background:${escapeSceneHTML(item.vis.color)}">${escapeSceneHTML(item.vis.label)}</div>
      ` : `<div style="font-size:11px;color:var(--t4)">Real Whisper segment from uploaded media.</div>`}
    `;
    panel.appendChild(el);
  });
}

function buildTimeline() {
  buildRuler();
  buildTracks();
}

function buildRuler() {
  const ruler = document.getElementById('tl-ruler');
  if (!ruler) return;
  ruler.innerHTML = `<div style="width:72px;min-width:72px;border-right:1px solid var(--bdr)"></div>`;
  const totalW = DURATION * tlZoom;
  ruler.style.minWidth = (72 + totalW) + 'px';
  for (let s = 0; s <= DURATION; s += 5) {
    const lbl = document.createElement('div');
    lbl.className = 'tl-ruler-label';
    lbl.style.left = (72 + s * tlZoom) + 'px';
    lbl.textContent = fmt(s);
    ruler.appendChild(lbl);
  }
  const zoomLbl = document.getElementById('zoom-label');
  if (zoomLbl) zoomLbl.textContent = tlZoom + 'px/s';
  const content = document.getElementById('tl-content');
  if (content) content.style.minWidth = (72 + totalW + 40) + 'px';
}

function buildTracks() {
  const tracks = document.getElementById('tl-tracks');
  if (!tracks) return;
  tracks.innerHTML = '';

  const scenes = (window.AgentPipeline && AgentPipeline.state.scenes) ? AgentPipeline.state.scenes : (typeof TRANSCRIPT !== 'undefined' ? TRANSCRIPT : []);

  if (scenes.length === 0) {
    tracks.innerHTML = `<div style="padding:40px;text-align:center;color:var(--t4);font-size:13px">Timeline is empty. Generate a video or upload a file to populate tracks.</div>`;
    return;
  }

  const sourceName = (window.AgentPipeline && AgentPipeline.state.sourceFileName) ? AgentPipeline.state.sourceFileName : 'Uploaded media';
  const TRACK_DEFS = [
    { lbl:'SOURCE',   color:'rgba(59,130,246,.18)', border:'rgba(59,130,246,.5)',  blocks:[{s:0,e:DURATION,t:sourceName}],                                                          interactive:false },
    { lbl:'CAPTIONS', color:'rgba(6,182,212,.15)',  border:'rgba(6,182,212,.4)',   blocks:scenes.map(t=>({s:t.s,e:t.e,t:'Whisper transcript',id:t.id,muted:t.muted})),             interactive:true  },
    { lbl:'WORDS',    color:'rgba(16,185,129,.14)', border:'rgba(16,185,129,.45)', blocks:scenes.map(t=>({s:t.s,e:t.e,t:`${(t.words||[]).length} word timestamps`})),               interactive:false },
  ];

  TRACK_DEFS.forEach(td => {
    const row = document.createElement('div');
    row.className = 'tl-track-row';
    row.innerHTML = `<div class="tl-track-label">${td.lbl}</div>`;
    const area = document.createElement('div');
    area.className = 'tl-track-area';
    area.style.minWidth = (DURATION * tlZoom) + 'px';
    td.blocks.forEach(b => {
      const bl = document.createElement('div');
      bl.className = 'tl-block';
      bl.style.left       = (b.s * tlZoom) + 'px';
      bl.style.width      = Math.max(4, (b.e - b.s) * tlZoom) + 'px';
      bl.style.background = b.muted ? 'rgba(239,68,68,.22)' : td.color;
      bl.style.borderLeft = `2px solid ${td.border}`;
      bl.style.color      = 'rgba(255,255,255,.65)';
      bl.style.transition = 'box-shadow .15s, border-color .15s, background .15s';
      bl.style.cursor     = td.interactive ? 'pointer' : 'default';
      bl.style.userSelect = 'none';
      bl.title            = b.t;
      bl.textContent      = b.muted ? '🔇 ' + b.t : b.t;

      if (td.interactive && b.id != null) {
        bl.dataset.sceneId = b.id;
        bl.addEventListener('click', function(e) {
          e.stopPropagation();
          selectClip(b.id);
        });
        if (window.selectedClipId === b.id) {
          bl.style.boxShadow   = '0 0 0 2px #8B5CF6, 0 0 18px rgba(139,92,246,.55)';
          bl.style.borderColor = '#8B5CF6';
          bl.style.background  = b.muted ? 'rgba(239,68,68,.38)' : 'rgba(139,92,246,.38)';
          bl.style.zIndex      = '5';
        }
      }
      area.appendChild(bl);
    });
    area.addEventListener('click', e => { if (e.target === area) selectClip(null); });
    row.appendChild(area);
    tracks.appendChild(row);
  });
}

/* ─── CLIP SELECTION ─────────────────────────────────────── */
window.selectedClipId = null;

function selectClip(id) {
  window.selectedClipId = id;
  buildTracks(); // re-render to show highlight
}

function getSelectedScene() {
  if (window.selectedClipId == null) return null;
  const scenes = (window.AgentPipeline && AgentPipeline.state.scenes) ? AgentPipeline.state.scenes : [];
  return scenes.find(s => s.id === window.selectedClipId) || null;
}

/* ─── CLIP INFO BAR ──────────────────────────────────────── */
function updateEditorToolbar() {
  const scenes = (window.AgentPipeline && AgentPipeline.state.scenes) ? AgentPipeline.state.scenes : [];
  const countEl = document.getElementById('clip-info-count');
  if (countEl) countEl.textContent = scenes.length;
  const sel    = getSelectedScene();
  const timeEl = document.getElementById('clip-info-time');
  const durEl  = document.getElementById('clip-info-dur');
  if (timeEl) timeEl.textContent = sel ? `${fmt(sel.s)} → ${fmt(sel.e)}` : '—';
  if (durEl)  durEl.textContent  = sel ? fmt(sel.e - sel.s) : '—';
  const toolbar = document.getElementById('video-edit-toolbar');
  if (toolbar) toolbar.style.display = scenes.length > 0 ? 'flex' : 'none';
  const muteBtn = document.getElementById('tool-mute');
  if (muteBtn) { muteBtn.style.color = (sel && sel.muted) ? '#f87171' : ''; muteBtn.title = (sel && sel.muted) ? 'Unmute clip' : 'Mute clip'; }
}

/* ─── SPLIT AT PLAYHEAD ──────────────────────────────────── */
function splitClipAtPlayhead() {
  const scenes = (window.AgentPipeline && AgentPipeline.state.scenes) ? AgentPipeline.state.scenes : [];
  const t = currentTime;
  const idx = scenes.findIndex(s => t > s.s && t < s.e);
  if (idx === -1) { toast('Move the playhead inside a clip to split it.', 'error'); return; }
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  const orig  = scenes[idx];
  const left  = Object.assign({}, orig, { e: t, id: orig.id });
  const right = Object.assign({}, orig, { s: t, id: Date.now() });
  scenes.splice(idx, 1, left, right);
  window.selectedClipId = right.id;
  buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
  toast(`✂ Split at ${fmt(t)}.`);
}

/* ─── CUT ────────────────────────────────────────────────── */
var _clipBoard = null;
function cutSelectedClip() {
  const sel = getSelectedScene();
  if (!sel) { toast('Select a clip first.', 'error'); return; }
  _clipBoard = Object.assign({}, sel);
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  const scenes = AgentPipeline.state.scenes;
  const idx = scenes.findIndex(s => s.id === sel.id);
  if (idx !== -1) scenes.splice(idx, 1);
  window.selectedClipId = null;
  buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
  toast('✂ Clip cut to clipboard.');
}

/* ─── TRIM IN / TRIM OUT ─────────────────────────────────── */
function trimClipLeft() {
  const sel = getSelectedScene();
  if (!sel) { toast('Select a clip first.', 'error'); return; }
  if (currentTime <= sel.s || currentTime >= sel.e) { toast('Playhead must be inside the selected clip.', 'error'); return; }
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  sel.s = parseFloat(currentTime.toFixed(3));
  buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
  toast(`◀ Trimmed in to ${fmt(sel.s)}.`);
}
function trimClipRight() {
  const sel = getSelectedScene();
  if (!sel) { toast('Select a clip first.', 'error'); return; }
  if (currentTime <= sel.s || currentTime >= sel.e) { toast('Playhead must be inside the selected clip.', 'error'); return; }
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  sel.e = parseFloat(currentTime.toFixed(3));
  buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
  toast(`▶ Trimmed out to ${fmt(sel.e)}.`);
}

/* ─── DUPLICATE ──────────────────────────────────────────── */
function duplicateSelectedClip() {
  const sel = getSelectedScene();
  if (!sel) { toast('Select a clip to duplicate.', 'error'); return; }
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  const scenes = AgentPipeline.state.scenes;
  const idx  = scenes.findIndex(s => s.id === sel.id);
  const dur  = sel.e - sel.s;
  const clone = Object.assign({}, sel, { id: Date.now(), s: sel.e, e: sel.e + dur });
  scenes.splice(idx + 1, 0, clone);
  window.selectedClipId = clone.id;
  buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
  toast('⧉ Clip duplicated.');
}

/* ─── DELETE ─────────────────────────────────────────────── */
function deleteSelectedClip() {
  const sel = getSelectedScene();
  if (!sel) { toast('Select a clip to delete.', 'error'); return; }
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  const scenes = AgentPipeline.state.scenes;
  const idx = scenes.findIndex(s => s.id === sel.id);
  if (idx !== -1) scenes.splice(idx, 1);
  window.selectedClipId = null;
  buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
  toast('🗑 Clip deleted.');
}

/* ─── MUTE ───────────────────────────────────────────────── */
function toggleClipMute() {
  const sel = getSelectedScene();
  if (!sel) { toast('Select a clip to mute/unmute.', 'error'); return; }
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  sel.muted = !sel.muted;
  buildTimeline(); updateEditorToolbar();
  toast(sel.muted ? '🔇 Clip muted.' : '🔊 Clip unmuted.');
}

/* ─── ADD AUDIO TRACK ────────────────────────────────────── */
function addAudioTrack() {
  const input = document.createElement('input');
  input.type = 'file'; input.accept = 'audio/*';
  input.onchange = function(e) {
    const file = e.target.files[0]; if (!file) return;
    const url = URL.createObjectURL(file);
    if (!window._audioTracks) window._audioTracks = [];
    const audio = new Audio(url); audio.volume = 0.4;
    window._audioTracks.push(audio);
    const tracksEl = document.getElementById('tl-tracks');
    if (tracksEl) {
      const row = document.createElement('div'); row.className = 'tl-track-row';
      row.innerHTML = `<div class="tl-track-label">🎵 MUSIC</div>`;
      const area = document.createElement('div'); area.className = 'tl-track-area';
      area.style.minWidth = (DURATION * tlZoom) + 'px';
      const bl = document.createElement('div'); bl.className = 'tl-block';
      bl.style.cssText = `left:0;width:${DURATION * tlZoom}px;background:rgba(16,185,129,.2);border-left:2px solid rgba(16,185,129,.6);color:rgba(255,255,255,.65);cursor:pointer`;
      bl.textContent = `🎵 ${file.name}`;
      bl.onclick = () => { audio.paused ? audio.play() : audio.pause(); toast(audio.paused ? '⏸ Audio paused' : '▶ Audio playing'); };
      area.appendChild(bl); row.appendChild(area); tracksEl.appendChild(row);
    }
    toast(`🎵 Added: ${file.name}`);
  };
  input.click();
}

/* ─── SPEED DIALOG ───────────────────────────────────────── */
var _pendingSpeed = 1;
function openSpeedDialog() {
  const sel = getSelectedScene();
  if (!sel) { toast('Select a clip to adjust speed.', 'error'); return; }
  _pendingSpeed = window.SmartEditEditor?.info(sel)?.speed || sel.speed || 1;
  const dlg = document.getElementById('speed-dialog'); if (!dlg) return;
  dlg.style.display = 'flex';
  const inp = document.getElementById('custom-speed-input'); if (inp) inp.value = _pendingSpeed;
  document.querySelectorAll('.speed-preset-btn').forEach(btn => btn.classList.toggle('active-speed', parseFloat(btn.textContent) === _pendingSpeed));
}
function applyClipSpeed(speed, btn) {
  _pendingSpeed = speed;
  if (btn) { document.querySelectorAll('.speed-preset-btn').forEach(b => b.classList.remove('active-speed')); btn.classList.add('active-speed'); }
  const inp = document.getElementById('custom-speed-input'); if (inp) inp.value = speed;
}
function confirmSpeedChange() {
  const sel = getSelectedScene(); if (!sel) { closeSpeedDialog(); return; }
  if (window.AgentPipeline) window.AgentPipeline.pushHistoryState();
  const origDur = sel.e - sel.s;
  sel.speed = _pendingSpeed;
  sel.e = parseFloat((sel.s + origDur / _pendingSpeed).toFixed(3));
  closeSpeedDialog();
  buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
  toast(`⚡ Speed set to ${_pendingSpeed}×.`);
}
function closeSpeedDialog() {
  const dlg = document.getElementById('speed-dialog'); if (dlg) dlg.style.display = 'none';
}

/* ─── UNDO / REDO ────────────────────────────────────────── */
function undoEdit() {
  if (window.AgentPipeline && window.AgentPipeline.undo) {
    window.AgentPipeline.undo(); window.selectedClipId = null;
    buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
    toast('↩ Undo applied.');
  }
}
function redoEdit() {
  if (window.AgentPipeline && window.AgentPipeline.redo) {
    window.AgentPipeline.redo(); window.selectedClipId = null;
    buildTimeline(); buildTranscript(); buildDecisionPanel(); updateEditorToolbar();
    toast('↪ Redo applied.');
  }
}

function zoomTL(dir, fit = false) {
  if (fit) tlZoom = 30;
  else tlZoom = Math.max(8, Math.min(80, tlZoom + dir * 10));
  buildTimeline();
  updatePlayhead();
}

/* ─── PLAYBACK & CANVAS COMPOSITOR ────────────────────────── */
function togglePlay() {
  isPlaying = !isPlaying;
  const overlay = document.getElementById('play-overlay');
  const ppBtn = document.getElementById('play-pause-btn');
  const realVideo = document.getElementById('real-preview-video');
  const hasRealVideo = realVideo && realVideo.style.display === 'block' && realVideo.src;

  if (isPlaying) {
    if (overlay) { overlay.style.opacity = '0'; overlay.style.pointerEvents = 'none'; }
    if (ppBtn) ppBtn.innerHTML = '<svg width="17" height="17" viewBox="0 0 24 24" fill="white"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
    window.currentSpeakingSceneId = null;
    if (hasRealVideo) { realVideo.play(); }
    playInterval = setInterval(tick, 100);
  } else {
    if (overlay) {
      overlay.style.pointerEvents = 'auto';
      overlay.style.opacity = hasRealVideo ? '0' : '1';
    }
    if (ppBtn) ppBtn.innerHTML = '<svg width="17" height="17" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>';
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    if (hasRealVideo) { realVideo.pause(); }
    clearInterval(playInterval);
  }
}

function tick() {
  const realVideo = document.getElementById('real-preview-video');
  if (realVideo && realVideo.style.display === 'block') {
    currentTime = realVideo.currentTime;
    if (realVideo.ended || currentTime >= DURATION) {
       currentTime = 0;
       realVideo.currentTime = 0;
       if (isPlaying) togglePlay();
    }
  } else {
    currentTime += 0.1 * playbackSpeed;
    if (currentTime >= DURATION) { currentTime = 0; if(isPlaying) togglePlay(); }
  }
  updatePlaybackUI();
}

function seekTo(t) { 
  currentTime = Math.max(0, Math.min(DURATION, t)); 
  const realVideo = document.getElementById('real-preview-video');
  if (realVideo && realVideo.style.display === 'block') {
    realVideo.currentTime = currentTime;
  }
  updatePlaybackUI(); 
}

function seekDelta(d) { seekTo(currentTime + d); }

function seekClick(e, bar) {
  const r = bar.getBoundingClientRect();
  seekTo(((e.clientX - r.left) / r.width) * DURATION);
}

function setSpeed(s, el) { 
  playbackSpeed = s; 
  pickPill(el); 
  const realVideo = document.getElementById('real-preview-video');
  if (realVideo) realVideo.playbackRate = s;
}
function volChange(v) { 
  const realVideo = document.getElementById('real-preview-video');
  if (realVideo) realVideo.volume = v / 100;
}

function updatePlaybackUI() {
  const pct = (currentTime / DURATION) * 100;
  const fill = document.getElementById('progress-fill');
  const thumb = document.getElementById('progress-thumb');
  if (fill) fill.style.width = pct + '%';
  if (thumb) thumb.style.left = pct + '%';

  const curTimeEl = document.getElementById('cur-time');
  const edTimeCode = document.getElementById('ed-timecode');
  const tlTimeCode = document.getElementById('tl-timecode');
  if (curTimeEl) curTimeEl.textContent = fmt(currentTime);
  if (edTimeCode) edTimeCode.textContent = fmtFull(currentTime);
  if (tlTimeCode) tlTimeCode.textContent = fmtFull(currentTime);

  updatePlayhead();

  const scenes = (window.AgentPipeline && AgentPipeline.state.scenes) ? AgentPipeline.state.scenes : TRANSCRIPT;
  const seg = scenes.find(s => currentTime >= s.s && currentTime < s.e);

  if (isPlaying && seg && seg.id !== window.currentSpeakingSceneId) {
    window.currentSpeakingSceneId = seg.id;
    if (window.AgentPipeline && AgentPipeline.speakScene) {
      const rv = document.getElementById('real-preview-video');
      const hasRV = rv && rv.style.display === 'block' && rv.src;
      if (!hasRV) {
        AgentPipeline.speakScene(seg.text, AgentPipeline.state.language);
      }
    }
  } else if (!seg) {
    window.currentSpeakingSceneId = null;
  }


  // Subtitle Overlay (Caption Agent)
  const subEl = document.getElementById('subtitle-display');
  if (subEl) { 
    if (seg) { subEl.textContent = seg.text; subEl.style.opacity = '1'; } 
    else { subEl.style.opacity = '0'; } 
  }

  // Preview Screen Composition Engine (Layout Planner + Compositor)
  renderPreviewCanvas(seg);

  // Highlight active transcript & decision card
  document.querySelectorAll('.tr-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.dec-card').forEach(el => el.classList.remove('active-dec'));
  if (seg) {
    const trEl = document.getElementById('tr-' + seg.id);
    const decEl = document.getElementById('dec-' + seg.id);
    if (trEl) trEl.classList.add('active');
    if (decEl) decEl.classList.add('active-dec');
  }
}

window.loadRealVideo = function(url) {
  const realVideo = document.getElementById('real-preview-video');
  const fallbackBg = document.getElementById('preview-bg-fallback');
  const playOverlay = document.getElementById('play-overlay');
  if (realVideo) {
    realVideo.src = url;
    realVideo.style.display = 'block';
    if (fallbackBg) fallbackBg.style.display = 'none';
    // Hide the big play overlay — video thumbnail/first-frame is shown instead
    // Show it again when user explicitly clicks
    if (playOverlay) playOverlay.style.opacity = '0';
    
    // Hide artificial PiP & Subtitles since video is final
    const pip = document.getElementById('pip-box');
    const subBar = document.querySelector('.subtitle-bar');
    if (pip) pip.style.display = 'none';
    if (subBar) subBar.style.display = 'none';

    // Restore play overlay on hover so user can still click play
    realVideo.addEventListener('mouseenter', () => {
      if (playOverlay && !isPlaying) playOverlay.style.opacity = '1';
    }, { once: false });
    realVideo.addEventListener('mouseleave', () => {
      if (playOverlay && !isPlaying) playOverlay.style.opacity = '0';
    }, { once: false });
    
    realVideo.onloadedmetadata = () => {
       if (realVideo.duration && !isNaN(realVideo.duration)) {
           DURATION = Math.ceil(realVideo.duration);
           buildTimeline();
           // Update duration display in controls
           const durEl = document.querySelector('.playback-controls span.mono:last-of-type');
           if (durEl) durEl.textContent = fmt(DURATION);
       }
    };

    // Auto-load first frame so preview shows video thumbnail
    realVideo.load();
  }
};

function renderPreviewCanvas(seg) {
  const pip = document.getElementById('pip-box');
  const pipC = document.getElementById('pip-content');
  if (!pip) return;

  const currentLayout = seg ? (seg.layout || 'full-presenter') : 'full-presenter';

  if (currentLayout === 'split-screen' || currentLayout === 'pip-overlay') {
    pip.style.transform = 'scale(1)';
    pip.style.opacity = '1';
    if (pipC && seg && seg.vis) {
      pipC.style.background = seg.vis.color;
      pipC.textContent = `${seg.vis.label} (${currentLayout.toUpperCase()})`;
    }
  } 
  else if (currentLayout === 'dual-conversation') {
    pip.style.transform = 'scale(1)';
    pip.style.opacity = '1';
    if (pipC) {
      pipC.style.background = "rgba(16,185,129,.3)";
      pipC.textContent = "🎙️ Speaker B (Dual Podcast Split)";
    }
  }
  else if (currentLayout === 'slide-deck') {
    pip.style.transform = 'scale(1)';
    pip.style.opacity = '1';
    if (pipC) {
      pipC.style.background = "rgba(245,158,11,.3)";
      pipC.textContent = "📊 AI Slide Deck Template";
    }
  }
  else {
    pip.style.transform = 'scale(0.85)';
    pip.style.opacity = '0';
  }
}

function updatePlayhead() {
  const ph = document.getElementById('tl-playhead');
  if (ph) ph.style.left = (72 + currentTime * tlZoom) + 'px';
}

/* ─── NATURAL LANGUAGE EDIT HANDLER ───────────────────────── */
function handleNLCommand(inputElId) {
  const input = document.getElementById(inputElId);
  if (!input || !input.value.trim()) return;

  const cmd = input.value.trim();
  if (window.AgentPipeline) {
    AgentPipeline.executeNLCommand(cmd);
  }
  input.value = '';
}

/* ─── ANALYTICS ─────────────────────────────────────────── */
var analyticsInited = false;
function initAnalytics() {
  if (analyticsInited) return; 
  analyticsInited = true;
  const heights = [72, 88, 65, 95, 100, 82, 91];
  const chart = document.getElementById('weekly-chart');
  if (!chart) return;
  chart.innerHTML = '';
  heights.forEach(h => {
    const bar = document.createElement('div');
    bar.className = 'chart-bar flex-1';
    bar.style.height = '0%';
    chart.appendChild(bar);
    setTimeout(() => bar.style.height = h + '%', 100);
  });
}

/* ─── SETTINGS HANDLERS ──────────────────────────────────── */
function toggleSetting(el, key) {
  el.classList.toggle('on');
  toast(`${key} ${el.classList.contains('on') ? 'enabled' : 'disabled'}`);
}

function saveSettings() {
  toast('Settings saved successfully!');
}

/* Unified switchAspectRatio — merged from two previous definitions */
/* The first definition at line 40 is kept as a no-op redirect; this is the real one */

function shareVideo() {
  const url = window.lastVideoDownloadUrl;
  if (!url) {
    toast('No video to share yet!', 'error');
    return;
  }
  // Construct absolute local path if running on localhost
  let localPath = url;
  if (url.startsWith('/')) {
    const apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
    localPath = apiBase + url;
  }
  navigator.clipboard.writeText(localPath).then(() => {
    toast('Video path copied to clipboard!');
  }).catch(() => {
    toast('Failed to copy link', 'error');
  });
}

/* ─── HELPERS ─────────────────────────────────────────────── */
function fmt(s) {
  s = Math.floor(s);
  return `${Math.floor(s/60)}:${(s%60).toString().padStart(2,'0')}`;
}

function fmtFull(s) {
  s = Math.floor(s);
  return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor((s%3600)/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
}

/* ─── EVENT LISTENERS ─────────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (currentView !== 'editor') return;
  const inInput = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';

  // Playback & navigation
  if (e.code === 'Space' && !inInput)  { e.preventDefault(); togglePlay(); }
  if (e.code === 'ArrowLeft')           { e.preventDefault(); seekDelta(e.shiftKey ? -10 : -5); }
  if (e.code === 'ArrowRight')          { e.preventDefault(); seekDelta(e.shiftKey ? 10 : 5); }
  if (e.code === 'KeyJ')                seekDelta(-10);
  if (e.code === 'KeyL')                seekDelta(10);
  if (e.code === 'Equal' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); zoomTL(1); }
  if (e.code === 'Minus'  && (e.metaKey || e.ctrlKey)) { e.preventDefault(); zoomTL(-1); }

  if (inInput) return; // don't fire editing shortcuts while typing

  // Editing shortcuts (mirrors timeline toolbar labels)
  if (e.code === 'KeyS')                              { e.preventDefault(); splitClipAtPlayhead(); }
  if (e.code === 'KeyX')                              { e.preventDefault(); cutSelectedClip(); }
  if (e.code === 'BracketLeft')                       { e.preventDefault(); trimClipLeft(); }
  if (e.code === 'BracketRight')                      { e.preventDefault(); trimClipRight(); }
  if (e.code === 'Delete' || e.code === 'Backspace')  { e.preventDefault(); deleteSelectedClip(); }
  if (e.code === 'Escape')                            { selectClip(null); }
  if (e.code === 'KeyZ' && (e.ctrlKey || e.metaKey) && !e.shiftKey) { e.preventDefault(); undoEdit(); }
  if ((e.code === 'KeyY' && (e.ctrlKey || e.metaKey)) ||
      (e.code === 'KeyZ' && (e.ctrlKey || e.metaKey) && e.shiftKey)) { e.preventDefault(); redoEdit(); }
});

document.addEventListener('click', e => {
  const tlBody = document.getElementById('tl-body');
  if (tlBody && tlBody.contains(e.target) && currentView === 'editor') {
    const content = document.getElementById('tl-content');
    if (content) {
      const rect = content.getBoundingClientRect();
      const x = e.clientX - rect.left - 72;
      if (x >= 0) seekTo(x / tlZoom);
    }
  }
});

window.addEventListener('load', () => {
  setTimeout(() => document.querySelector('.hero')?.scrollIntoView({behavior:'instant'}), 0);
});

/* ─── SCRIPT TO VIDEO LOGIC ───────────────────────────────── */
async function generateScriptWithAI(auto = false) {
  var promptEl = document.getElementById('gen-video-prompt');
  var prompt = promptEl.value;
  if (!prompt || prompt.length < 5) {
    if (typeof toast === 'function') toast('Please write a short prompt or idea first!');
    return false;
  }
  
  var btn = document.getElementById('edit-ai-btn');
  var originalBtnText = btn ? btn.innerHTML : '✨ Edit with AI';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<div style="width:14px;height:14px;border:2px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:spin 1s linear infinite;display:inline-block;vertical-align:middle;margin-right:6px"></div> Generating...';
    btn.style.opacity = '0.7';
    btn.style.cursor = 'not-allowed';
  }
  
  if (typeof toast === 'function') toast('Generating script with AI... (Takes ~10s)');
  
  var durInput = document.getElementById('gen-video-duration');
  var dur = durInput ? parseInt(durInput.value) : 60;
  
  var langSel = document.getElementById('gen-video-lang');
  var lang = langSel ? langSel.value : 'en';

  var ratioSel = document.getElementById('gen-video-ratio');
  var ratio = ratioSel ? ratioSel.value : '16:9';

  var sceneTypeSel = document.getElementById('edit-ai-scene-type');
  var sceneType = sceneTypeSel ? sceneTypeSel.value : 'sentences';
  
  var qualityInstructions = "\\n\\nREQUIREMENTS:\\n- Ensure the script is highly professional, engaging, and delivers high-quality content.\\n- Chunk the script by " + sceneType + ".";
  var extendedPrompt = prompt + qualityInstructions;

  if (window.AgentPipeline) {
    try {
      var res = await window.AgentPipeline.callAgent('script', 'Script Agent', '/api/v1/generate-script', { 
        prompt: extendedPrompt, 
        duration_seconds: dur, 
        language: lang, 
        aspect_ratio: ratio 
      });
      if (res && res.result && res.result.scenes) {
        let scriptText = '';
        res.result.scenes.forEach((scene, index) => {
          scriptText += `[Scene ${index + 1}]\n`;
          if (scene.visual_prompt) {
            scriptText += `[Visual: ${scene.visual_prompt}]\n`;
          }
          scriptText += `${scene.text}\n\n`;
        });
        promptEl.value = scriptText.trim();
        if (!auto && typeof toast === 'function') toast('Script generated successfully! Review and edit before generating.');
        
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalBtnText;
          btn.style.opacity = '1';
          btn.style.cursor = 'pointer';
        }
        return true;
      }
    } catch (e) { 
      console.error(e);
      if (typeof toast === 'function') toast('Error generating script from AI.', 'error');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalBtnText;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
      }
      return false;
    }
  }
  
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = originalBtnText;
    btn.style.opacity = '1';
    btn.style.cursor = 'pointer';
  }
  return false;
}

async function triggerFullVideoGeneration() {
  var promptEl = document.getElementById('gen-video-prompt');
  var prompt = promptEl.value;
  
  // Detect if it's a short idea/prompt instead of a full script
  var isShortPrompt = prompt.split(' ').length < 25 && !prompt.includes('[Scene');
  if (isShortPrompt) {
    if (typeof toast === 'function') toast('Short idea detected. Auto-generating full script...');
    var success = await generateScriptWithAI(true);
    if (!success) return; // Stop if script generation failed
    prompt = promptEl.value; // Get the newly generated full script
  }

  var durInput = document.getElementById('gen-video-duration');
  var dur = durInput ? parseInt(durInput.value) : 60;
  
  if (window.AgentPipeline) {
    var langSel = document.getElementById('gen-video-lang');
    if (langSel) window.AgentPipeline.state.language = langSel.value || 'en';
    
    var ratioSel = document.getElementById('gen-video-ratio');
    if (ratioSel) {
      window.AgentPipeline.state.aspectRatio = ratioSel.value || '16:9';
      // Sync UI preview element size
      switchAspectRatio(window.AgentPipeline.state.aspectRatio);
    }

    var avatarSel = document.getElementById('gen-avatar-style');
    if (avatarSel) window.AgentPipeline.state.avatarStyle = avatarSel.value || 'none';

    var lipsyncChk = document.getElementById('gen-lipsync');
    window.AgentPipeline.state.enableLipsync = !!(lipsyncChk && lipsyncChk.checked);
    
    if (typeof goTo === 'function') {
      goTo('editor');
    } else if (typeof switchView === 'function') {
      switchView('editor');
    }
    // Start the full pipeline
    window.AgentPipeline.runFullAgentChain(prompt, dur);
  } else {
    alert("Agent pipeline not initialized.");
  }
}

function openCreationPath(kind) {
  goTo('upload');
  requestAnimationFrame(() => {
    const target = document.getElementById(kind === 'import' ? 'drop-zone' : 'gen-video-prompt');
    target?.scrollIntoView({block:'center',behavior:'smooth'});
    if (kind === 'ai') target?.focus({preventScroll:true});
  });
}

// Guide choices configure the form; generation always remains an explicit action.
function openCreationGuide() {
  goTo('landing');
  requestAnimationFrame(() => {
    document.getElementById('creation-guide').scrollIntoView({block:'start'});
    document.getElementById('creation-guide-title').focus({preventScroll:true});
  });
}
function chooseCreationMode(mode, presenterKind) {
  if (!['images','hybrid','motion','avatar'].includes(mode)) return;
  if (mode === 'avatar' && ['illustrated','realistic'].includes(presenterKind)) {
    document.getElementById('gen-presenter-kind').value = presenterKind;
  }
  const select = document.getElementById('gen-video-mode');
  select.value = mode;
  select.dispatchEvent(new Event('change'));
  openCreationPath('ai');
}
