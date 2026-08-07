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

  // Step 2: Layout Planner
  try {
    var lpStep = renderPipelineStep('Agent 3: Layout Planner', 'Assigning layouts to transcript scenes…', 'current');
    setProcessingHeader('AGENT 3 / LAYOUT PLANNER', 'Planning visual layout', 'Ollama analyzing each scene…', 40);
    await AgentPipeline.runLayoutPlannerAgent('cinematic');
    if (lpStep) { lpStep.classList.remove('current'); lpStep.classList.add('done'); var iw1 = lpStep.firstElementChild; if (iw1) iw1.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
    renderPipelineStep('Layout Planner done', 'All scenes assigned Full/Split/PiP/Slide/Dual layouts.', 'done');
    setProcessingHeader('AGENT 3 / COMPLETE', 'Layouts assigned', AgentPipeline.state.scenes.length + ' scenes laid out.', 55);
  } catch(e) {
    renderPipelineStep('Layout Planner skipped', 'Ollama not available or timed out.', 'failed');
  }

  // Step 3: Music selection
  try {
    var msStep = renderPipelineStep('Agent 15: Music/Sound Agent', 'Selecting background music profile…', 'current');
    setProcessingHeader('AGENT 15 / MUSIC AGENT', 'Music selection', 'Matching content mood to music profile…', 70);
    await AgentPipeline.runMusicSoundAgent('neutral');
    if (msStep) { msStep.classList.remove('current'); msStep.classList.add('done'); var iw2 = msStep.firstElementChild; if (iw2) iw2.innerHTML = '<svg width="16" height="16" fill="none" stroke="#10B981" stroke-width="2.5" viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg>'; }
    renderPipelineStep('Music/Sound Agent done', 'Audio profile selected. FFmpeg ducking command ready.', 'done');
    setProcessingHeader('AGENT 15 / COMPLETE', 'Music profile ready', 'Background music configured.', 85);
  } catch(e) {
    renderPipelineStep('Music Agent skipped', 'Could not reach backend.', 'failed');
  }

  setProcessingHeader('PIPELINE / COMPLETE', 'All agents ready', 'Caption + Layout + Music agents complete.', 100);
}

// ─────────────────────────────────────────────────────────────
// startScriptPipeline — triggered by text-to-video prompt flow
// ─────────────────────────────────────────────────────────────

window.startScriptPipeline = async function(promptText, config) {
  config = config || {};
  var list   = document.getElementById('proc-steps-list');
  var doneEl = document.getElementById('proc-done');
  var statsEl = document.getElementById('proc-done-stats');

  if (!list) return;
  list.innerHTML = '';
  if (doneEl) doneEl.style.display = 'none';

  setProcessingHeader('AGENT 1 / ORCHESTRATOR', 'Orchestrator Agent activated', 'Running full pipeline for prompt…', 5);
  var orchStep = renderPipelineStep('Orchestrator Agent', 'Dispatching pipeline for: "' + (promptText || '').substring(0, 50) + '"', 'current');

  try {
    // Agent 2: Script
    setProcessingHeader('AGENT 2 / SCRIPT AGENT', 'Script Agent running', 'Ollama Llama-3 writing scene-by-scene script…', 20);
    var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
    var resp = await fetch(apiBase + '/api/v1/generate-script', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: promptText,
        duration_seconds: config.duration || 30,
        language: 'en',
        aspect_ratio: config.aspectRatio || '16:9'
      })
    });
    if (!resp.ok) throw new Error(await resp.text() || 'Script generation failed HTTP ' + resp.status);
    var data = await resp.json();

    if (orchStep) { orchStep.classList.remove('current'); orchStep.classList.add('done'); }
    renderPipelineStep('Script Agent complete', data.result && data.result.scenes ? data.result.scenes.length + ' scenes generated.' : 'Script ready.', 'done');
    setProcessingHeader('AGENT 2 / COMPLETE', 'Script generation complete', 'Formatting scenes…', 50);

    if (window.AgentPipeline && data.result) {
      AgentPipeline.applyScriptJob(data.result);
    }

    // Agent 3: Layout Planner
    try {
      var lpStep2 = renderPipelineStep('Layout Planner Agent', 'Assigning visual layouts per scene…', 'current');
      setProcessingHeader('AGENT 3 / LAYOUT PLANNER', 'Layout planning', 'Analyzing scene sentiment for layout…', 65);
      await AgentPipeline.runLayoutPlannerAgent('cinematic');
      if (lpStep2) { lpStep2.classList.remove('current'); lpStep2.classList.add('done'); }
      renderPipelineStep('Layout Planner complete', 'Layouts assigned to all scenes.', 'done');
    } catch(e) {
      renderPipelineStep('Layout Planner skipped', 'Ollama timeout — default layouts used.', 'failed');
    }

    // Agent 15: Music
    try {
      var msStep2 = renderPipelineStep('Music/Sound Agent', 'Selecting music profile for content…', 'current');
      setProcessingHeader('AGENT 15 / MUSIC', 'Music selection', 'Matching mood to audio profile…', 80);
      await AgentPipeline.runMusicSoundAgent('upbeat');
      if (msStep2) { msStep2.classList.remove('current'); msStep2.classList.add('done'); }
      renderPipelineStep('Music/Sound Agent complete', 'Background music profile ready.', 'done');
    } catch(e) {
      renderPipelineStep('Music Agent skipped', 'Could not reach backend.', 'failed');
    }

    var sceneCount = data.result && data.result.scenes ? data.result.scenes.length : 0;
    setProcessingHeader('PIPELINE / COMPLETE', 'All agents complete', sceneCount + ' scenes ready in timeline.', 100);
    if (statsEl) statsEl.textContent = 'Script Agent generated ' + sceneCount + ' scenes from your prompt.';
    if (doneEl) doneEl.style.display = 'block';
    if (typeof toast === 'function') toast('Text-to-Video pipeline complete — ' + sceneCount + ' scenes ready!');
    setTimeout(function() { goTo('editor'); }, 900);

  } catch (err) {
    var message = err && err.message ? err.message : String(err);
    setProcessingHeader('PIPELINE / FAILED', 'Script pipeline failed', message, 100);
    if (orchStep) { orchStep.classList.remove('current'); orchStep.classList.add('failed'); }
    renderPipelineStep('Pipeline error', message, 'failed');
    if (typeof toast === 'function') toast('Pipeline failed: ' + message, 'error');
  }
};
