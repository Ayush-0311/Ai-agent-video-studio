/**
 * backend/api/upload.js
 * Phase 2: real FastAPI upload wiring for local SmartEdit AI jobs.
 */

const SMARTEDIT_API_BASE = 'http://127.0.0.1:8000';

window.SmartEditBackend = window.SmartEditBackend || {
  apiBase: SMARTEDIT_API_BASE,
  selectedFile: null,
  currentJobId: null,
  currentJob: null,
  currentConfig: null,
  pollTimer: null
};

function setUploadUi(fileName, label, detail, pct) {
  const idle = document.getElementById('dz-idle');
  const uploading = document.getElementById('dz-uploading');
  const filename = document.getElementById('upload-filename');
  const dropZone = document.getElementById('drop-zone');
  const bar = document.getElementById('upload-bar');
  const pctLabel = document.getElementById('upload-pct-label');
  const speedLabel = document.getElementById('upload-speed');

  if (idle) idle.style.display = 'none';
  if (uploading) uploading.style.display = 'block';
  if (filename) filename.textContent = fileName || 'Selected media';
  if (dropZone) dropZone.classList.add('uploading');
  if (bar) bar.style.width = `${pct}%`;
  if (pctLabel) pctLabel.textContent = label;
  if (speedLabel) speedLabel.textContent = detail;
}

function resetUploadUi() {
  const idle = document.getElementById('dz-idle');
  const uploading = document.getElementById('dz-uploading');
  const dropZone = document.getElementById('drop-zone');
  const bar = document.getElementById('upload-bar');

  if (idle) idle.style.display = 'block';
  if (uploading) uploading.style.display = 'none';
  if (dropZone) dropZone.classList.remove('uploading', 'drag-over');
  if (bar) bar.style.width = '0%';
}

function dzDragOver(e) {
  e.preventDefault();
  const dz = document.getElementById('drop-zone');
  if (dz) dz.classList.add('drag-over');
}

function dzDragLeave() {
  const dz = document.getElementById('drop-zone');
  if (dz) dz.classList.remove('drag-over');
}

function dzDrop(e) {
  e.preventDefault();
  const dz = document.getElementById('drop-zone');
  if (dz) dz.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) simulateUpload(f);
}

function dzClick() {
  const input = document.getElementById('file-input');
  if (input) input.click();
}

function fileSelected(e) {
  const f = e.target.files[0];
  if (f) simulateUpload(f);
}

async function simulateUpload(fileOrName, config = null) {
  const file = fileOrName instanceof File ? fileOrName : window.SmartEditBackend.selectedFile;
  if (!file) {
    toast('Select a video or audio file first. Phase 2 supports upload-to-transcript only.', 'error');
    resetUploadUi();
    return;
  }

  window.SmartEditBackend.selectedFile = file;
  window.SmartEditBackend.currentConfig = config || window.SmartEditBackend.currentConfig;
  window.SmartEditBackend.currentJobId = null;
  window.SmartEditBackend.currentJob = null;

  if (window.AgentPipeline) {
    AgentPipeline.state.config = window.SmartEditBackend.currentConfig;
    AgentPipeline.state.sourceFileName = file.name;
    AgentPipeline.state.scenes = [];
    AgentPipeline.state.transcript = '';
    AgentPipeline.state.currentJobId = null;
    AgentPipeline.logAgentAction('upload', 'Upload', `Sending ${file.name} to local FastAPI backend.`, 'c');
  }

  setUploadUi(file.name, 'Uploading to local backend...', 'FastAPI endpoint: /api/v1/generate-video', 15);

  const form = new FormData();
  form.append('file', file, file.name);

  try {
    const response = await fetch(`${window.SmartEditBackend.apiBase}/api/v1/generate-video`, {
      method: 'POST',
      body: form
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || `Upload failed with HTTP ${response.status}`);
    }

    const data = await response.json();
    window.SmartEditBackend.currentJobId = data.job_id;
    if (window.AgentPipeline) {
      AgentPipeline.state.currentJobId = data.job_id;
      AgentPipeline.logAgentAction('backend', 'FastAPI Backend', `Created job ${data.job_id}.`, 'g');
    }

    setUploadUi(file.name, 'Upload complete', `Job ${data.job_id} queued for Whisper transcription.`, 100);
    goTo('processing');
  } catch (err) {
    console.error(err);
    const message = err && err.message ? err.message : String(err);
    setUploadUi(file.name, 'Upload failed', message, 0);
    toast(`Backend upload failed: ${message}`, 'error');
  }
}

async function simulatePromptUpload(promptText, config) {
  window.SmartEditBackend.selectedFile = null;
  window.SmartEditBackend.currentConfig = config || window.SmartEditBackend.currentConfig;
  window.SmartEditBackend.currentJobId = null;
  window.SmartEditBackend.currentJob = null;

  if (window.AgentPipeline) {
    AgentPipeline.state.config = window.SmartEditBackend.currentConfig;
    AgentPipeline.state.sourceFileName = 'Prompt-generated Video';
    AgentPipeline.state.scenes = [];
    AgentPipeline.state.transcript = '';
    AgentPipeline.state.currentJobId = null;
    AgentPipeline.runPipelineFromPrompt(promptText);
  }

  goTo('processing');
  
  if (window.startScriptPipeline) {
    window.startScriptPipeline(promptText, config);
  } else {
    toast('Script pipeline logic not found!', 'error');
  }
}

function startProcessingFlow() {
  const durationSelect = document.getElementById('upload-duration');
  const durationVal = durationSelect ? parseInt(durationSelect.value, 10) : 30;

  const promptInput = document.getElementById('upload-prompt-input');
  const promptText = promptInput ? promptInput.value.trim() : '';

  const config = {
    speechModel: document.querySelector('#pill-speech .active')?.textContent || 'Whisper local',
    autoSubs: document.getElementById('tog-subs')?.classList.contains('on') || false,
    aspectRatio: '16:9',
    duration: durationVal
  };

  if (promptText && !window.SmartEditBackend.selectedFile) {
    simulatePromptUpload(promptText, config);
    return;
  }

  if (!window.SmartEditBackend.selectedFile) {
    toast('Please enter a prompt or choose a media file to start.', 'error');
    return;
  }

  simulateUpload(window.SmartEditBackend.selectedFile, config);
}

document.addEventListener('DOMContentLoaded', () => {
  const dzEl = document.getElementById('drop-zone');
  if (dzEl) {
    ['dragenter', 'dragover'].forEach(ev =>
      dzEl.addEventListener(ev, e => { e.preventDefault(); dzEl.classList.add('drag-over'); })
    );
    dzEl.addEventListener('dragleave', () => dzEl.classList.remove('drag-over'));
    dzEl.addEventListener('drop', dzDrop);
  }
});
