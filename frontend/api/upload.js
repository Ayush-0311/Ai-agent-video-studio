/**
 * backend/api/upload.js
 * Phase 2: real FastAPI upload wiring for local SmartEdit AI jobs.
 * + Direct local video preview (no backend required).
 */

const SMARTEDIT_API_BASE = 'http://127.0.0.1:8000';

window.SmartEditBackend = window.SmartEditBackend || {
  apiBase: SMARTEDIT_API_BASE,
  selectedFile: null,
  localObjectURL: null,   // blob:// URL for instant local preview
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
  if (f) handleFileChosen(f);
}

function dzClick() {
  // Only open file picker if no file is selected yet (idle state)
  const readyDiv = document.getElementById('dz-file-ready');
  if (readyDiv && readyDiv.style.display !== 'none' && readyDiv.innerHTML.trim() !== '') return;
  const input = document.getElementById('file-input');
  if (input) input.click();
}

function fileSelected(e) {
  const f = e.target.files[0];
  if (f) handleFileChosen(f);
}

/**
 * handleFileChosen — stores the file and shows the "file ready" UI.
 * Does NOT trigger backend upload yet; user picks a path via buttons.
 */
function validateMediaFile(file, videoOnly = false) {
  const extension = '.' + file.name.split('.').pop().toLowerCase();
  const allowed = videoOnly ? ['.mp4','.mov','.mkv','.webm'] : ['.png','.jpg','.jpeg','.webp','.mp4','.mov','.mkv','.webm','.mp3','.wav','.m4a','.ogg'];
  if (!allowed.includes(extension)) throw new Error(videoOnly ? 'Choose MP4, MOV, MKV or WebM video.' : 'Unsupported file format. Choose a supported image, video or audio file.');
  if (file.size > 500 * 1024 * 1024) throw new Error('Maximum upload size is 500 MiB. Choose a smaller file.');
  if (!file.size) throw new Error('This file is empty. Choose another file.');
}

function handleFileChosen(file) {
  try { validateMediaFile(file, true); } catch (error) { toast(error.message, 'error'); return false; }
  // Revoke previous object URL to free memory
  if (window.SmartEditBackend.localObjectURL) {
    URL.revokeObjectURL(window.SmartEditBackend.localObjectURL);
  }

  window.SmartEditBackend.selectedFile = file;
  window.SmartEditBackend.localObjectURL = URL.createObjectURL(file);

  // Show "file selected" state inside drop zone
  showFileReadyUI(file);
}

/**
 * showFileReadyUI — replaces drop zone content with file name + two action buttons.
 */
function showFileReadyUI(file) {
  const idle      = document.getElementById('dz-idle');
  const uploading = document.getElementById('dz-uploading');
  let   readyDiv  = document.getElementById('dz-file-ready');

  if (idle)      idle.style.display      = 'none';
  if (uploading) uploading.style.display = 'none';

  if (!readyDiv) {
    readyDiv = document.createElement('div');
    readyDiv.id = 'dz-file-ready';
    const dz = document.getElementById('drop-zone');
    if (dz) dz.appendChild(readyDiv);
  }

  const sizeMB = (file.size / 1024 / 1024).toFixed(1);
  const escapeLabel = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  readyDiv.style.display = 'block';
  readyDiv.innerHTML = `
    <div style="font-size:42px;margin-bottom:12px">🎬</div>
    <div style="font-weight:700;font-size:16px;margin-bottom:6px;color:#fff;word-break:break-all">${escapeLabel(file.name)}</div>
    <div style="font-size:12px;color:var(--t4);margin-bottom:22px">${sizeMB} MB · ${escapeLabel(file.type || 'video')}</div>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
      <button
        id="btn-open-editor"
        onclick="openInEditorDirectly(event)"
        style="padding:12px 26px;background:linear-gradient(135deg,#8B5CF6,#06B6D4);color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;display:flex;align-items:center;gap:8px;transition:transform .15s,box-shadow .15s;box-shadow:0 4px 20px rgba(139,92,246,.4)"
        onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 8px 28px rgba(139,92,246,.6)'"
        onmouseout="this.style.transform='';this.style.boxShadow='0 4px 20px rgba(139,92,246,.4)'">
        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
        Open in Editor
      </button>
      <button
        onclick="startProcessingFlow()"
        style="padding:12px 26px;background:rgba(255,255,255,.06);color:var(--t2);border:1px solid var(--bdr2);border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;transition:background .15s"
        onmouseover="this.style.background='rgba(255,255,255,.12)'"
        onmouseout="this.style.background='rgba(255,255,255,.06)'">
        Import with selected options
      </button>
      <button
        onclick="resetFileSelection()"
        style="padding:12px 18px;background:transparent;color:var(--t4);border:1px solid var(--bdr);border-radius:12px;font-size:13px;cursor:pointer;transition:color .15s"
        onmouseover="this.style.color='#fff'"
        onmouseout="this.style.color='var(--t4)'">
        ✕ Change File
      </button>
    </div>
  `;
}

/**
 * openInEditorDirectly — loads the selected video straight into the editor
 * preview using the local blob URL (no backend required).
 */
function openInEditorDirectly(e) {
  if (e) e.stopPropagation();

  const file = window.SmartEditBackend.selectedFile;
  const blobURL = window.SmartEditBackend.localObjectURL;

  if (!file || !blobURL) {
    toast('No video file selected!', 'error');
    return;
  }

  // Reset editor state so it re-initializes with new video
  if (typeof editorInited !== 'undefined') window.editorInited = false;
  if (typeof window.editorInited !== 'undefined') window.editorInited = false;

  // Navigate to editor view
  goTo('editor');

  // After editor DOM is shown, load the local video
  requestAnimationFrame(() => {
    if (typeof window.loadRealVideo === 'function') {
      window.loadRealVideo(blobURL);
    } else {
      // Fallback: set directly
      const vid = document.getElementById('real-preview-video');
      const fallback = document.getElementById('preview-bg-fallback');
      if (vid) {
        vid.src = blobURL;
        vid.style.display = 'block';
        if (fallback) fallback.style.display = 'none';
      }
    }

    // Update editor project title with filename
    const titleEl = document.getElementById('ed-project-title');
    if (titleEl) {
      titleEl.innerHTML = `${file.name} <span class="tag tag-g" style="font-size:8px">READY</span>`;
    }

    toast(`✅ ${file.name} loaded in editor!`, 'success');
  });
}

/**
 * resetFileSelection — clears the current file and shows the idle drop zone.
 */
function resetFileSelection() {
  if (window.SmartEditBackend.localObjectURL) {
    URL.revokeObjectURL(window.SmartEditBackend.localObjectURL);
    window.SmartEditBackend.localObjectURL = null;
  }
  window.SmartEditBackend.selectedFile = null;

  const idle     = document.getElementById('dz-idle');
  const readyDiv = document.getElementById('dz-file-ready');
  const fileInput = document.getElementById('file-input');

  if (idle)     idle.style.display     = 'block';
  if (readyDiv) readyDiv.style.display = 'none';
  if (fileInput) fileInput.value = '';
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
  let promptText = promptInput ? promptInput.value.trim() : '';

  // Read shared generator settings (language, avatar, aspect ratio)
  const langEl = document.getElementById('gen-video-lang');
  const ratioEl = document.getElementById('gen-video-ratio');
  const avatarEl = document.getElementById('gen-avatar-style');
  const lipsyncEl = document.getElementById('gen-lipsync');

  const config = {
    speechModel: document.querySelector('#pill-speech .active')?.textContent || 'Whisper local',
    visualTheme: document.querySelector('#pill-theme .active')?.textContent || '',
    bgMusic: document.querySelector('#pill-music .active')?.textContent || '',
    directorAgent: document.querySelector('#pill-agent .active')?.textContent || '',
    autoSubs: document.getElementById('tog-subs')?.classList.contains('on') || false,
    sfx: document.getElementById('tog-sfx')?.classList.contains('on') || false,
    aspectRatio: ratioEl ? ratioEl.value : '16:9',
    duration: durationVal,
    language: langEl ? langEl.value : 'en',
    avatarStyle: avatarEl ? avatarEl.value : 'none',
    enableLipsync: !!(lipsyncEl && lipsyncEl.checked),
  };

  if (promptText) {
    let enhancedPrompt = promptText;
    if (config.visualTheme) enhancedPrompt += `\n[STYLE]: Use a ${config.visualTheme} visual style.`;
    if (config.bgMusic) enhancedPrompt += `\n[AUDIO]: Add ${config.bgMusic} background music.`;
    if (config.sfx) enhancedPrompt += `\n[SFX]: Include dynamic AI sound effects.`;
    if (config.directorAgent) enhancedPrompt += `\n[DIRECTOR]: Handled by ${config.directorAgent} Agent.`;
    promptText = enhancedPrompt;
  }

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
