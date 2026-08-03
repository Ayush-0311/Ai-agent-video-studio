/**
 * backend/api/upload.js
 * ─────────────────────────────────────────────────────────────
 * Upload & Drag-Drop Event Handling connected to 16 Local AI Agents Pipeline
 */

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
  if (f) simulateUpload(f.name);
}

function dzClick() {
  const input = document.getElementById('file-input');
  if (input) input.click();
}

function fileSelected(e) {
  const f = e.target.files[0];
  if (f) simulateUpload(f.name);
}

function simulateUpload(name, config = null) {
  const idle = document.getElementById('dz-idle');
  const uploading = document.getElementById('dz-uploading');
  const filename = document.getElementById('upload-filename');
  const dropZone = document.getElementById('drop-zone');
  const bar = document.getElementById('upload-bar');
  const pctLabel = document.getElementById('upload-pct-label');
  const speedLabel = document.getElementById('upload-speed');

  if (idle) idle.style.display = 'none';
  if (uploading) uploading.style.display = 'block';
  if (filename) filename.textContent = name;
  if (dropZone) dropZone.classList.add('uploading');

  let pct = 0;
  const iv = setInterval(() => {
    pct = Math.min(100, pct + Math.random() * 8 + 4);
    if (bar) bar.style.width = pct + '%';
    if (pctLabel) pctLabel.textContent = pct < 100 ? `Uploading to Orchestrator… ${Math.floor(pct)}%` : 'Upload Complete ✓';
    const speed = (1.8 + Math.random() * 2.5).toFixed(1);
    if (speedLabel) speedLabel.textContent = pct < 100 ? `${speed} MB/s — ${Math.ceil((100 - pct) / 4)}s remaining` : 'Orchestrator Agent Initialized';

    if (pct >= 100) {
      clearInterval(iv);
      if (window.AgentPipeline) {
        if (config) {
          AgentPipeline.state.config = config;
          if (config.aspectRatio) AgentPipeline.state.aspectRatio = config.aspectRatio;
        }
        AgentPipeline.runPipelineFromPrompt(name);
      }
      setTimeout(() => goTo('processing'), 600);
    }
  }, 100);
}

function startProcessingFlow() {
  const promptInput = document.getElementById('upload-prompt-input');
  const promptVal = promptInput ? promptInput.value.trim() : '';
  
  const durationSelect = document.getElementById('upload-duration');
  const durationVal = durationSelect ? parseInt(durationSelect.value) : 30;

  // Extract AI Configuration
  const config = {
    speechModel: document.querySelector('#pill-speech .active')?.textContent || 'Whisper V3',
    llm: document.querySelector('#pill-llm .active')?.textContent || 'Llama-3 8B',
    imageSource: document.querySelector('#pill-img .active')?.textContent || 'SDXL Turbo',
    resolution: document.querySelector('#pill-res .active')?.textContent || '4K',
    subtitleStyle: document.querySelector('#pill-sub .active')?.textContent || 'Cinematic',
    transition: document.querySelector('#pill-trans .active')?.textContent || 'AI Choice',
    autoBRoll: document.getElementById('tog-broll')?.classList.contains('on') || false,
    bgMusic: document.getElementById('tog-music')?.classList.contains('on') || false,
    autoSubs: document.getElementById('tog-subs')?.classList.contains('on') || false,
    aiIntroOutro: document.getElementById('tog-intro')?.classList.contains('on') || false,
    qualityCheck: document.getElementById('tog-qa')?.classList.contains('on') || false,
    aspectRatio: '16:9', // Default
    duration: durationVal
  };

  if (config.resolution === '720p' || config.resolution === '1080p') {
      config.aspectRatio = '16:9';
  } else if (config.resolution === '4K') {
      config.aspectRatio = '16:9';
  }

  simulateUpload(promptVal || 'presenter_video.mp4', config);
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
