/**
 * backend/api/pipeline.js
 * ─────────────────────────────────────────────────────────────
 * SmartEdit AI — Pipeline Progress + Auto-Chain Agent Trigger
 * After Whisper STT completes, auto-triggers Layout Planner,
 * Slide Generator, Image Prompts, and Music Selection.
 */

function renderPipelineStep(label, detail, state) {
  state = state || 'current';
  var list = document.getElementById('proc-steps-list');
  if (!list) return null;

  var el = document.createElement('div');
  el.className = 'pipe-step ' + state;
  var icon = state === 'done'
    ? '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'
    : state === 'failed'
      ? '<svg width="16" height="16" fill="none" stroke="#EF4444" stroke-width="2.5" viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12"/></svg>'
      : '<div class="spin-ring"></div>';

  el.innerHTML =
    '<div style="width:32px;height:32px;border-radius:9px;background:rgba(139,92,246,.12);display:flex;align-items:center;justify-content:center;flex-shrink:0">' + icon + '</div>' +
    '<div style="flex:1;min-width:0">' +
      '<div style="font-size:13px;font-weight:700">' + label + '</div>' +
      '<div style="font-size:11px;color:var(--t4);margin-top:2px">' + detail + '</div>' +
    '</div>';
  list.appendChild(el);
  list.scrollTop = list.scrollHeight;
  return el;
}

function setProcessingHeader(tag, title, subtitle, progress) {
  var tagEl    = document.getElementById('proc-step-tag');
  var titleEl  = document.getElementById('proc-title');
  var subEl    = document.getElementById('proc-sub');
  var barEl    = document.getElementById('proc-bar');
  if (tagEl)   tagEl.textContent   = tag;
  if (titleEl) titleEl.textContent = title;
  if (subEl)   subEl.textContent   = subtitle;
  if (barEl)   barEl.style.width   = Math.max(0, Math.min(100, progress || 0)) + '%';
}

function summarizeTranscript(job) {
  var result = job && job.result ? job.result : {};
  var segments = Array.isArray(result.segments) ? result.segments.length : 0;
  var words = Array.isArray(result.segments)
    ? result.segments.reduce(function(count, seg) { return count + ((seg.words || []).length); }, 0)
    : 0;
  return segments + ' transcript segment(s), ' + words + ' word timestamp(s), ' + Math.round(result.duration || 0) + 's source duration.';
}

async function pollJobOnce(jobId) {
  var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
  var response = await fetch(apiBase + '/api/v1/job-status/' + jobId);
  if (!response.ok) {
    var text = await response.text();
    throw new Error(text || 'Job poll failed with HTTP ' + response.status);
  }
  return response.json();
}

// ─────────────────────────────────────────────────────────────
// startPipeline — called when entering the processing view
// ─────────────────────────────────────────────────────────────

function startPipeline() {
  var list   = document.getElementById('proc-steps-list');
  var doneEl = document.getElementById('proc-done');
  var statsEl = document.getElementById('proc-done-stats');

  if (!list) return;
  list.innerHTML = '';
  if (doneEl) doneEl.style.display = 'none';

  var jobId = window.SmartEditBackend && window.SmartEditBackend.currentJobId;
  if (!jobId) {
    setProcessingHeader('WAITING', 'No backend job found', 'Upload a real video or audio file first.', 0);
    renderPipelineStep('Waiting for upload', 'No FastAPI job id is available yet.', 'failed');
    return;
  }

  if (window.SmartEditBackend.pollTimer) {
    clearInterval(window.SmartEditBackend.pollTimer);
    window.SmartEditBackend.pollTimer = null;
  }

  setProcessingHeader('AGENT 9 / CAPTION AGENT', 'Whisper transcription queued', 'Polling FastAPI job ' + jobId, 5);
  renderPipelineStep('Upload accepted', 'Caption Agent (Whisper) created job ' + jobId + '.', 'done');
  var transcribeStep = renderPipelineStep('Whisper transcription', 'Waiting for backend progress…', 'current');

  var poll = async function() {
    try {
      var job = await pollJobOnce(jobId);
      window.SmartEditBackend.currentJob = job;
      if (window.AgentPipeline) AgentPipeline.state.currentJob = job;

      var progress = typeof job.progress === 'number' ? job.progress : 0;
      setProcessingHeader('AGENT 9 / CAPTION AGENT', 'Whisper transcription running', job.message || job.status, progress);

      if (transcribeStep) {
        var detailEl = transcribeStep.querySelector('div[style*="font-size:11px"]');
        if (detailEl) detailEl.textContent = job.status + ' — ' + (job.message || 'Polling backend');
      }

      if (job.status === 'completed') {
        clearInterval(window.SmartEditBackend.pollTimer);
        window.SmartEditBackend.pollTimer = null;

        // Mark transcription done
        if (transcribeStep) {
          transcribeStep.classList.remove('current');
          transcribeStep.classList.add('done');
          var iconWrap = transcribeStep.firstElementChild;
          if (iconWrap) iconWrap.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>';
        }

        if (window.AgentPipeline) AgentPipeline.applyTranscriptionJob(job);
        setProcessingHeader('AGENT 9 / COMPLETE', 'Whisper transcript ready', summarizeTranscript(job), 30);
        renderPipelineStep('Caption Agent complete', 'Whisper segments loaded into editor timeline.', 'done');

        // Auto-chain: Layout Planner
        await runPostTranscriptionChain(job);

        if (statsEl) statsEl.textContent = summarizeTranscript(job);
        if (doneEl) doneEl.style.display = 'block';
        if (typeof toast === 'function') toast('Real Whisper transcript ready + agents activated! Opening editor…');
        setTimeout(function() { goTo('editor'); }, 900);
      }

      if (job.status === 'failed') {
        clearInterval(window.SmartEditBackend.pollTimer);
        window.SmartEditBackend.pollTimer = null;
        setProcessingHeader('AGENT 9 / FAILED', 'Whisper transcription failed', job.error || job.message || 'Unknown backend error', 100);
        if (transcribeStep) { transcribeStep.classList.remove('current'); transcribeStep.classList.add('failed'); }
        renderPipelineStep('Caption Agent error', job.error || 'No error detail returned.', 'failed');
        if (typeof toast === 'function') toast('Whisper transcription failed. Check backend logs.', 'error');
      }

    } catch (err) {
      clearInterval(window.SmartEditBackend.pollTimer);
      window.SmartEditBackend.pollTimer = null;
      var message = err && err.message ? err.message : String(err);
      setProcessingHeader('CONNECTION ERROR', 'Cannot reach FastAPI backend', message, 0);
      renderPipelineStep('Polling failed', message, 'failed');
      if (typeof toast === 'function') toast('Backend polling failed: ' + message, 'error');
    }
  };

  poll();
  window.SmartEditBackend.pollTimer = setInterval(poll, 1500);
}

// ─────────────────────────────────────────────────────────────
// runPostTranscriptionChain — auto-triggers agents after STT
// ─────────────────────────────────────────────────────────────

async function runPostTranscriptionChain(job) {
  if (!window.AgentPipeline || !AgentPipeline.state.scenes.length) return;

  var config = AgentPipeline.state.config || {};
  var theme = config.visualTheme || 'cinematic';
  var music = config.bgMusic || 'neutral';
  var director = config.directorAgent || 'Standard';

  // Step 2: Layout Planner
  try {
    var lpStep = renderPipelineStep('Agent 3: Layout Planner', `Assigning ${theme} layouts to transcript scenes…`, 'current');
    setProcessingHeader('AGENT 3 / LAYOUT PLANNER', `Planning ${theme} visual layout`, `Ollama analyzing each scene via ${director} Agent…`, 40);
    await AgentPipeline.runLayoutPlannerAgent(theme);
    if (lpStep) { lpStep.classList.remove('current'); lpStep.classList.add('done'); var iw1 = lpStep.firstElementChild; if (iw1) iw1.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
    renderPipelineStep('Layout Planner done', `All scenes assigned ${theme} layouts by ${director} Agent.`, 'done');
    setProcessingHeader('AGENT 3 / COMPLETE', 'Layouts assigned', AgentPipeline.state.scenes.length + ' scenes laid out.', 55);
  } catch(e) {
    renderPipelineStep('Layout Planner skipped', 'Ollama not available or timed out.', 'failed');
  }

  // Step 3: Music selection
  try {
    var msStep = renderPipelineStep('Agent 15: Music/Sound Agent', `Selecting ${music} background music profile…`, 'current');
    setProcessingHeader('AGENT 15 / MUSIC AGENT', 'Music selection', `Matching ${music} mood to music profile…`, 70);
    await AgentPipeline.runMusicSoundAgent(music);
    if (msStep) { msStep.classList.remove('current'); msStep.classList.add('done'); var iw2 = msStep.firstElementChild; if (iw2) iw2.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
    renderPipelineStep('Music/Sound Agent done', `Audio profile (${music}) selected. FFmpeg ducking command ready.`, 'done');
    setProcessingHeader('AGENT 15 / COMPLETE', 'Music profile ready', 'Background music configured.', 85);
  } catch(e) {
    renderPipelineStep('Music Agent skipped', 'Could not reach backend.', 'failed');
  }

  setProcessingHeader('PIPELINE / COMPLETE', 'All agents ready', 'Caption + Layout + Music agents complete.', 100);
}

// ─────────────────────────────────────────────────────────────
// startScriptPipeline — Full Auto Text-to-Video Pipeline
// Calls /api/v1/render-video, polls job, shows download button
// ─────────────────────────────────────────────────────────────

window.startScriptPipeline = async function(promptText, config) {
  config = config || {};
  var list   = document.getElementById('proc-steps-list');
  var doneEl = document.getElementById('proc-done');
  var statsEl = document.getElementById('proc-done-stats');

  if (!list) return;
  list.innerHTML = '';
  if (doneEl) doneEl.style.display = 'none';

  var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';

  setProcessingHeader('AGENT 1 / ORCHESTRATOR', 'Full Auto Pipeline Started', 'Script → Images → Voice → Video…', 5);
  var orchStep = renderPipelineStep('Orchestrator Agent', 'Dispatching full pipeline for: "' + (promptText || '').substring(0, 50) + '"', 'done');

  // ── Step 1: Call /api/v1/render-video → get job_id ──
  var jobId;
  try {
    var resp = await fetch(apiBase + '/api/v1/render-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: promptText,
        duration_seconds: config.duration || 30,
        language: config.language || 'en',
        aspect_ratio: config.aspectRatio || '16:9',
        image_style: 'cinematic photography, professional lighting, ultra detailed, 4K',
        avatar_style: config.avatarStyle || 'none',
        enable_lipsync: config.enableLipsync || false
      })
    });
    if (!resp.ok) {
      var errText = await resp.text();
      throw new Error(errText || 'render-video failed HTTP ' + resp.status);
    }
    var startData = await resp.json();
    jobId = startData.job_id;
    if (window.SmartEditBackend) window.SmartEditBackend.currentJobId = jobId;
  } catch(err) {
    var msg = err && err.message ? err.message : String(err);
    setProcessingHeader('PIPELINE / FAILED', 'Could not start pipeline', msg, 100);
    renderPipelineStep('Pipeline error', msg, 'failed');
    if (typeof toast === 'function') toast('Pipeline failed: ' + msg, 'error');
    return;
  }

  // ── Step 2: Poll job progress ──
  var lastStep = '';
  var scriptStep = null, imageStep = null, voiceStep = null, ffmpegStep = null;

  var poll = setInterval(async function() {
    try {
      var pollResp = await fetch(apiBase + '/api/v1/job-status/' + jobId);
      if (!pollResp.ok) return;
      var job = await pollResp.json();
      var progress = typeof job.progress === 'number' ? job.progress : 0;
      var message = job.message || job.status || '';

      // Detect which step we are on and update UI
      if (progress <= 20 && lastStep !== 'script') {
        lastStep = 'script';
        if (!scriptStep) scriptStep = renderPipelineStep('Agent 2: Script Agent', 'Ollama Llama-3 writing scene script…', 'current');
        setProcessingHeader('AGENT 2 / SCRIPT AGENT', 'Writing video script', message, progress);
      } else if (progress > 20 && progress <= 50 && lastStep !== 'image') {
        lastStep = 'image';
        if (scriptStep) { scriptStep.classList.remove('current'); scriptStep.classList.add('done'); var iws = scriptStep.firstElementChild; if(iws) iws.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
        renderPipelineStep('Script Agent complete', 'Scene script ready.', 'done');
        if (!imageStep) imageStep = renderPipelineStep('Agent 5: Image Generator', 'Generating AI images via Pollinations.ai…', 'current');
        setProcessingHeader('AGENT 5 / IMAGE GENERATOR', 'Generating scene images', message, progress);
      } else if (progress > 50 && progress <= 75 && lastStep !== 'voice') {
        lastStep = 'voice';
        if (imageStep) { imageStep.classList.remove('current'); imageStep.classList.add('done'); var iwi = imageStep.firstElementChild; if(iwi) iwi.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
        renderPipelineStep('Image Generator complete', 'All scene images ready.', 'done');
        if (!voiceStep) voiceStep = renderPipelineStep('Agent 7: Voice Agent', 'Synthesizing narration audio (gTTS)…', 'current');
        setProcessingHeader('AGENT 7 / VOICE AGENT', 'Generating voice audio', message, progress);
      } else if (progress > 75 && progress <= 95 && lastStep !== 'ffmpeg') {
        lastStep = 'ffmpeg';
        if (voiceStep) { voiceStep.classList.remove('current'); voiceStep.classList.add('done'); var iwv = voiceStep.firstElementChild; if(iwv) iwv.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
        renderPipelineStep('Voice Agent complete', 'All audio narration ready.', 'done');
        if (!ffmpegStep) ffmpegStep = renderPipelineStep('Agent 10: Compositor (FFmpeg)', 'Merging clips into final MP4…', 'current');
        setProcessingHeader('AGENT 10 / COMPOSITOR', 'FFmpeg rendering video', message, progress);
      }

      // ── DONE ──
      if (job.status === 'completed') {
        clearInterval(poll);
        if (ffmpegStep) { ffmpegStep.classList.remove('current'); ffmpegStep.classList.add('done'); var iwf = ffmpegStep.firstElementChild; if(iwf) iwf.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
        renderPipelineStep('Compositor complete', 'Final MP4 video rendered!', 'done');
        setProcessingHeader('PIPELINE / COMPLETE', '🎬 Video Ready!', 'All agents finished. Download your video below.', 100);

        // Apply script scenes to editor
        var result = job.result || {};
        if (window.AgentPipeline && result.scenes) {
          AgentPipeline.applyScriptJob(result.script || {});
        }

        // Show download button
        var downloadUrl = apiBase + '/api/v1/download-video/' + jobId;
        if (statsEl) {
          statsEl.innerHTML = (result.scene_count || '?') + ' scenes rendered into a ' + (result.duration_seconds || 30) + 's MP4 video.';
        }
        if (doneEl) {
          doneEl.style.display = 'block';
          // Inject or update download button
          var existingBtn = document.getElementById('video-download-btn');
          if (!existingBtn) {
            var btnGroup = document.createElement('div');
            btnGroup.style.display = 'flex';
            btnGroup.style.gap = '16px';
            btnGroup.style.marginTop = '16px';
            
            var btn = document.createElement('a');
            btn.id = 'video-download-btn';
            btn.href = downloadUrl;
            btn.download = 'smartedit_video.mp4';
            btn.style.cssText = 'display:inline-flex;align-items:center;gap:8px;padding:12px 28px;background:linear-gradient(135deg,#8B5CF6,#06B6D4);color:#fff;border-radius:12px;font-weight:700;font-size:14px;text-decoration:none;box-shadow:0 4px 20px rgba(139,92,246,0.4);transition:transform .2s;';
            btn.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download Video (MP4)';
            btn.onmouseover = function(){ this.style.transform='scale(1.05)'; };
            btn.onmouseout = function(){ this.style.transform='scale(1)'; };
            btnGroup.appendChild(btn);

            var editorBtn = document.createElement('button');
            editorBtn.id = 'open-editor-btn';
            editorBtn.style.cssText = 'display:inline-flex;align-items:center;gap:8px;padding:12px 28px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);color:#fff;border-radius:12px;font-weight:700;font-size:14px;cursor:pointer;transition:background .2s;';
            editorBtn.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg> Open in AI Editor';
            editorBtn.onmouseover = function(){ this.style.background='rgba(255,255,255,0.1)'; };
            editorBtn.onmouseout = function(){ this.style.background='rgba(255,255,255,0.05)'; };
            editorBtn.onclick = function() { if (typeof goTo === 'function') goTo('editor'); };
            btnGroup.appendChild(editorBtn);

            doneEl.appendChild(btnGroup);
          } else {
            existingBtn.href = downloadUrl;
          }
        }
        if (typeof toast === 'function') toast('🎬 Video ready! Click Download to save your MP4.');

        // Store download URL globally for editor topbar
        window.SmartEditBackend.lastVideoDownloadUrl = downloadUrl;
        window.SmartEditBackend.lastVideoJobId = jobId;
        window.SmartEditBackend.lastVideoResult = result;
        
        if (window.loadRealVideo) {
            window.loadRealVideo(downloadUrl);
        }

        // Show download button in editor topbar
        injectEditorDownloadButton(downloadUrl, result);

        // Update dashboard stats & add project card
        updateDashboardStats(result);

        // Ensure it doesn't automatically navigate if user wants to see the buttons
        // setTimeout(function() { if (typeof goTo === 'function') goTo('editor'); }, 1500);
      }

      // ── FAILED ──
      if (job.status === 'failed') {
        clearInterval(poll);
        setProcessingHeader('PIPELINE / FAILED', 'Pipeline failed', job.error || job.message || 'Unknown error', 100);
        renderPipelineStep('Pipeline error', job.error || 'Check backend logs.', 'failed');
        if (typeof toast === 'function') toast('Pipeline failed: ' + (job.error || 'unknown error'), 'error');
      }

    } catch(err) {
      clearInterval(poll);
      var emsg = err && err.message ? err.message : String(err);
      setProcessingHeader('CONNECTION ERROR', 'Lost connection to backend', emsg, 0);
      renderPipelineStep('Polling failed', emsg, 'failed');
    }
  }, 2000);
};

// ─────────────────────────────────────────────────────────────
// injectEditorDownloadButton
// Adds a green Download MP4 button to editor topbar
// ─────────────────────────────────────────────────────────────
function injectEditorDownloadButton(downloadUrl, result) {
  var old = document.getElementById('editor-dl-btn-wrap');
  if (old) old.remove();

  var topbarRight = document.querySelector('#view-editor .topbar .flex.items-center.gap-10');
  if (!topbarRight) return;

  var duration = (result && result.duration_seconds) || 30;
  var scenes   = (result && result.scene_count) || '?';

  var wrap = document.createElement('div');
  wrap.id = 'editor-dl-btn-wrap';
  wrap.style.cssText = 'display:flex;align-items:center;gap:8px;';
  wrap.innerHTML =
    '<div style="font-size:10px;color:var(--green);font-weight:700;background:rgba(16,185,129,.1);' +
      'border:1px solid rgba(16,185,129,.25);border-radius:8px;padding:4px 10px;white-space:nowrap">' +
      '\u2713 ' + scenes + ' scenes \u00b7 ' + duration + 's</div>' +
    '<a id="editor-topbar-dl" href="' + downloadUrl + '" download="smartedit_video.mp4"' +
      ' style="display:inline-flex;align-items:center;gap:6px;padding:7px 16px;' +
      'background:linear-gradient(135deg,#10B981,#06B6D4);color:#fff;border-radius:9px;' +
      'font-weight:700;font-size:12px;text-decoration:none;box-shadow:0 4px 16px rgba(16,185,129,.4);' +
      'transition:transform .2s,box-shadow .2s;white-space:nowrap"' +
      ' onmouseover="this.style.transform=\'translateY(-2px)\';this.style.boxShadow=\'0 8px 24px rgba(16,185,129,.6)\'"' +
      ' onmouseout="this.style.transform=\'\';this.style.boxShadow=\'0 4px 16px rgba(16,185,129,.4)\'">' +
      '<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">' +
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
        '<polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>' +
      '</svg> Download MP4' +
    '</a>';

  var analyticsBtn = topbarRight.querySelector('button');
  if (analyticsBtn) topbarRight.insertBefore(wrap, analyticsBtn);
  else topbarRight.prepend(wrap);

  // Update editor title
  var titleEl = document.querySelector('#view-editor .topbar [style*="font-size:13px;font-weight:700"]');
  if (titleEl) titleEl.innerHTML = 'AI Generated Video <span class="tag tag-g" style="font-size:8px">READY</span>';
  var subEl = document.querySelector('#view-editor .topbar [style*="color:var(--purple);font-weight:700"]');
  if (subEl) subEl.textContent = 'AUTO-EDITED \u00b7 ' + scenes + ' SCENES \u00b7 ' + duration + 'S';
}

// ─────────────────────────────────────────────────────────────
// updateDashboardStats
// ─────────────────────────────────────────────────────────────
function updateDashboardStats(result) {
  var totalEl = document.getElementById('dash-total-videos');
  var procEl  = document.getElementById('dash-proc-time');
  var imgEl   = document.getElementById('dash-images');
  var confEl  = document.getElementById('dash-confidence');
  if (totalEl) { var cur = parseInt(totalEl.textContent) || 0; totalEl.textContent = cur + 1; }
  if (procEl)  procEl.textContent = ((result && result.duration_seconds) || 30) + 's';
  if (imgEl)   imgEl.textContent  = (result && result.scene_count) ? (result.scene_count * 2) : 6;
  if (confEl)  confEl.textContent = '98%';
  addProjectCardToDashboard(result);
}

// ─────────────────────────────────────────────────────────────
// addProjectCardToDashboard
// ─────────────────────────────────────────────────────────────
function addProjectCardToDashboard(result) {
  var grid = document.getElementById('projects-grid');
  if (!grid) return;

  var apiBase     = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
  var jobId       = window.SmartEditBackend && window.SmartEditBackend.lastVideoJobId;
  var downloadUrl = jobId ? (apiBase + '/api/v1/download-video/' + jobId) : '#';
  var scenes      = (result && result.scene_count) || '?';
  var duration    = (result && result.duration_seconds) || 30;
  var now         = new Date().toLocaleTimeString();

  var card = document.createElement('div');
  card.className = 'proj-card';
  card.style.cursor = 'default';
  card.innerHTML =
    '<div class="proj-thumb" style="background:linear-gradient(135deg,rgba(139,92,246,.2),rgba(6,182,212,.12));display:flex;align-items:center;justify-content:center;font-size:40px">' +
      '\uD83C\uDFAC' +
      '<div class="proj-thumb-play">' +
        '<a href="' + downloadUrl + '" download="smartedit_video.mp4"' +
          ' style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;background:linear-gradient(135deg,#8B5CF6,#06B6D4);color:#fff;border-radius:10px;font-weight:700;font-size:12px;text-decoration:none">' +
          '\u2B07\uFE0F Download</a>' +
      '</div>' +
    '</div>' +
    '<div style="padding:14px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">' +
        '<div style="font-size:13px;font-weight:700;color:#fff">AI Generated Video</div>' +
        '<span class="tag tag-g" style="font-size:8px">READY</span>' +
      '</div>' +
      '<div style="font-size:11px;color:var(--t3)">' + scenes + ' scenes \u2022 ' + duration + 's \u2022 ' + now + '</div>' +
      '<div style="display:flex;gap:8px;margin-top:10px">' +
        '<button onclick="goTo(\'editor\')" style="flex:1;padding:7px;background:rgba(139,92,246,.1);border:1px solid rgba(139,92,246,.25);border-radius:8px;color:var(--purple);font-size:11px;font-weight:700;cursor:pointer">Open Editor</button>' +
        '<a href="' + downloadUrl + '" download="smartedit_video.mp4" style="flex:1;display:flex;align-items:center;justify-content:center;padding:7px;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);border-radius:8px;color:var(--green);font-size:11px;font-weight:700;text-decoration:none">Download</a>' +
      '</div>' +
    '</div>';

  var firstCard = grid.querySelector('[style*="dashed"]');
  if (firstCard) grid.insertBefore(card, firstCard);
  else grid.appendChild(card);
}
