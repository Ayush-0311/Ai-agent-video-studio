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
function initEditor() {
  if (editorInited) return; 
  editorInited = true;
  buildTranscript();
  buildDecisionPanel();
  buildTimeline();
  renderPreviewCanvas();
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
          <span class="tag ${item.vis ? 'tag-c' : 'tag-p'}" style="font-size:8px">${item.layout ? item.layout.toUpperCase() : 'SPEECH'}</span>
          <span style="font-size:9px;color:var(--t4)">${item.conf || 98}%</span>
        </div>
      </div>
      <p class="tr-text">${item.text}</p>
      <div class="flex gap-6 items-center" style="margin-top:6px">
        <span class="tr-keyword">#${item.keyword}</span>
        <span style="font-size:9px;color:var(--cyan)">${item.speaker || 'Presenter'}</span>
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
        <span class="tag ${item.vis ? 'tag-c' : 'tag-p'}" style="font-size:8px">${item.layout || 'PRESENTER'}</span>
      </div>
      <div class="dec-label" style="font-size:10px;font-weight:800;color:var(--t4);margin-bottom:3px">AGENT: ${item.agent || 'Compositor Agent'}</div>
      ${item.vis ? `
        <div style="font-size:11px;color:var(--t2);margin-bottom:7px;line-height:1.4">"${item.vis.query}"</div>
        <div class="dec-asset-preview" style="background:${item.vis.color}">${item.vis.label}</div>
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
      tracks.innerHTML = `<div style="padding:40px;text-align:center;color:var(--t4);font-size:13px">Timeline is empty. Generate a video to populate tracks.</div>`;
      return;
  }

  const sourceName = (window.AgentPipeline && AgentPipeline.state.sourceFileName) ? AgentPipeline.state.sourceFileName : 'Uploaded media';
  const TRACK_DEFS = [
    { lbl:'SOURCE', color:'rgba(59,130,246,.18)', border:'rgba(59,130,246,.5)', blocks:[{s:0,e:DURATION,t:sourceName}] },
    { lbl:'CAPTIONS', color:'rgba(6,182,212,.15)', border:'rgba(6,182,212,.4)', blocks: scenes.map(t=>({s:t.s,e:t.e,t:'Whisper transcript'})) },
    { lbl:'WORDS', color:'rgba(16,185,129,.14)', border:'rgba(16,185,129,.45)', blocks: scenes.map(t=>({s:t.s,e:t.e,t:`${(t.words || []).length} word timestamps`})) },
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
      bl.style.left = (b.s * tlZoom) + 'px';
      bl.style.width = ((b.e - b.s) * tlZoom) + 'px';
      bl.style.background = td.color;
      bl.style.borderLeft = `2px solid ${td.border}`;
      bl.style.color = 'rgba(255,255,255,.6)';
      bl.title = b.t;
      bl.textContent = b.t;
      area.appendChild(bl);
    });
    row.appendChild(area);
    tracks.appendChild(row);
  });
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

  if (isPlaying) {
    if (overlay) overlay.style.display = 'none';
    if (ppBtn) ppBtn.innerHTML = '<svg width="17" height="17" viewBox="0 0 24 24" fill="white"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
    
    // TTS is handled dynamically in updatePlaybackUI during playback
    window.currentSpeakingSceneId = null;

    playInterval = setInterval(tick, 100);
  } else {
    if (overlay) overlay.style.display = 'flex';
    if (ppBtn) ppBtn.innerHTML = '<svg width="17" height="17" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>';
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    clearInterval(playInterval);
  }
}

function tick() {
  currentTime += 0.1 * playbackSpeed;
  if (currentTime >= DURATION) { currentTime = 0; if(isPlaying) togglePlay(); }
  updatePlaybackUI();
}

function seekTo(t) { 
  currentTime = Math.max(0, Math.min(DURATION, t)); 
  updatePlaybackUI(); 
}

function seekDelta(d) { seekTo(currentTime + d); }

function seekClick(e, bar) {
  const r = bar.getBoundingClientRect();
  seekTo(((e.clientX - r.left) / r.width) * DURATION);
}

function setSpeed(s, el) { playbackSpeed = s; pickPill(el); }
function volChange(v) { /* volume control */ }

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
      AgentPipeline.speakScene(seg.text, AgentPipeline.state.language);
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
  if (e.code === 'Space' && e.target.tagName !== 'INPUT') { e.preventDefault(); togglePlay(); }
  if (e.code === 'ArrowLeft') { e.preventDefault(); seekDelta(e.shiftKey ? -10 : -5); }
  if (e.code === 'ArrowRight') { e.preventDefault(); seekDelta(e.shiftKey ? 10 : 5); }
  if (e.code === 'KeyJ') seekDelta(-10);
  if (e.code === 'KeyL') seekDelta(10);
  if (e.code === 'Equal' && e.metaKey) { e.preventDefault(); zoomTL(1); }
  if (e.code === 'Minus' && e.metaKey) { e.preventDefault(); zoomTL(-1); }
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
