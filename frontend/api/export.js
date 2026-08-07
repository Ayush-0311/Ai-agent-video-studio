/**
 * backend/api/export.js
 * ─────────────────────────────────────────────────────────────
 * SmartEdit AI — Export Optimizer Agent UI
 * Wired to real /api/v1/export-video backend endpoint.
 */

var selectedPreset = '16:9';
var selectedResolution = '1080p';
var selectedCodec = 'h264';

function setExportPreset(ratio, el) {
  selectedPreset = ratio;
  if (el && el.closest) {
    el.closest('.pill-group').querySelectorAll('.pill-opt').forEach(function(o) { o.classList.remove('active'); });
    el.classList.add('active');
  }
  var label = ratio === '16:9' ? 'YouTube / Standard' : ratio === '9:16' ? 'Reels / Shorts / TikTok' : 'Instagram / LinkedIn';
  if (typeof toast === 'function') toast('Export Optimizer: Preset → ' + label);
}

function openModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.add('open');
}

function closeModal(id) {
  var el = document.getElementById(id);
  if (el) el.classList.remove('open');
  var wrap = document.getElementById('export-progress-wrap');
  var bar  = document.getElementById('export-bar');
  var btn  = document.getElementById('export-btn');
  var pct  = document.getElementById('export-pct-text');
  var stat = document.getElementById('export-status-text');
  if (wrap) wrap.style.display = 'none';
  if (bar)  bar.style.width = '0%';
  if (pct)  pct.textContent = '0%';
  if (stat) stat.textContent = 'Initializing encoder…';
  if (btn)  { btn.disabled = false; btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Export ' + selectedPreset + ' MP4'; }
}

async function startExport() {
  var btn     = document.getElementById('export-btn');
  var wrap    = document.getElementById('export-progress-wrap');
  var bar     = document.getElementById('export-bar');
  var pctText = document.getElementById('export-pct-text');
  var statText = document.getElementById('export-status-text');

  if (btn) btn.disabled = true;
  if (wrap) wrap.style.display = 'block';

  var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';

  // Determine selected resolution from pill
  var resPills = document.querySelectorAll('#export-modal .pill-group:nth-child(2) .pill-opt.active');
  var resolution = resPills.length ? resPills[0].textContent.trim() : '1080p';

  var includeSubtitles = document.querySelector('#export-modal .toggle.on') !== null;

  var payload = {
    aspect_ratio: selectedPreset,
    resolution: resolution,
    fps: 30,
    codec: 'h264',
    include_subtitles: includeSubtitles,
    job_id: (window.SmartEditBackend && window.SmartEditBackend.currentJobId) || ''
  };

  // Animate progress while calling backend
  var pct = 0;
  var iv = setInterval(function() {
    pct = Math.min(85, pct + Math.random() * 6 + 2);
    if (bar) bar.style.width = pct + '%';
    if (pctText) pctText.textContent = Math.floor(pct) + '%';
  }, 150);

  var statusTexts = [
    'Export Optimizer Agent: Initializing ' + selectedPreset + ' reframing presets…',
    'Generating FFmpeg export command for ' + resolution + '…',
    'Applying Brand Kit watermarks & color grading…',
    'Configuring audio mix (speech + background music)…',
    'Building subtitle filter for Whisper captions…',
    'Validating output codec and container format…'
  ];
  var si = 0;
  var stIv = setInterval(function() {
    if (statText && si < statusTexts.length) statText.textContent = statusTexts[si++];
  }, 600);

  try {
    var resp = await fetch(apiBase + '/api/v1/export-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    clearInterval(iv);
    clearInterval(stIv);

    if (!resp.ok) throw new Error('HTTP ' + resp.status + ': ' + (await resp.text()));
    var data = await resp.json();

    // Finish progress
    if (bar) bar.style.width = '100%';
    if (pctText) pctText.textContent = '100%';

    if (statText) {
      if (data.ffmpeg_available) {
        statText.textContent = 'Export Optimizer Agent: Command ready! Run FFmpeg to render.';
      } else {
        statText.textContent = 'Export Optimizer Agent: FFmpeg command generated (FFmpeg not installed — install to execute).';
      }
    }

    // Show result
    setTimeout(function() {
      closeModal('export-modal');
      showExportResult(data);
    }, 800);

  } catch (err) {
    clearInterval(iv);
    clearInterval(stIv);
    var message = err && err.message ? err.message : String(err);
    if (statText) statText.textContent = 'Export Agent error: ' + message;
    if (bar) bar.style.width = '100%';
    if (bar) bar.style.background = 'var(--red)';
    if (typeof toast === 'function') toast('Export failed: ' + message, 'error');
    if (btn) { btn.disabled = false; btn.textContent = 'Retry Export'; }
  }
}

function showExportResult(data) {
  var existing = document.getElementById('export-result-overlay');
  if (existing) existing.remove();

  var overlay = document.createElement('div');
  overlay.id = 'export-result-overlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.75);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(6px)';

  var ffmpegBlock = data.ffmpeg_command
    ? '<div style="margin-top:16px"><div style="font-size:10px;font-weight:700;color:var(--t4);text-transform:uppercase;margin-bottom:6px">FFmpeg Command</div>' +
      '<pre style="background:rgba(0,0,0,.5);padding:14px;border-radius:10px;font-size:11px;overflow-x:auto;white-space:pre-wrap;word-break:break-all;color:var(--cyan);border:1px solid rgba(6,182,212,.2)">' + data.ffmpeg_command + '</pre>' +
      '<button onclick="navigator.clipboard && navigator.clipboard.writeText(\'' + data.ffmpeg_command.replace(/'/g, "\\'") + '\').then(function(){if(typeof toast===\'function\')toast(\'FFmpeg command copied!\');})" style="margin-top:8px;background:rgba(6,182,212,.1);border:1px solid rgba(6,182,212,.3);border-radius:8px;padding:6px 16px;color:var(--cyan);cursor:pointer;font-size:12px;font-weight:700">📋 Copy Command</button>' +
      '</div>'
    : '';

  var ffmpegNote = !data.ffmpeg_available
    ? '<div style="margin-top:12px;padding:10px 14px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);border-radius:8px;font-size:12px;color:var(--yellow)">⚠️ FFmpeg not detected on PATH. <a href="https://ffmpeg.org/download.html" target="_blank" style="color:var(--cyan);text-decoration:underline">Install FFmpeg</a> then run the command above.</div>'
    : '<div style="margin-top:12px;padding:10px 14px;background:rgba(16,185,129,.08);border:1px solid rgba(16,185,129,.2);border-radius:8px;font-size:12px;color:var(--green)">✓ FFmpeg is available. Run the command above to create your video.</div>';

  overlay.innerHTML =
    '<div style="background:var(--bg1);border:1px solid var(--bdr);border-radius:20px;padding:28px;max-width:600px;width:90%;max-height:85vh;overflow-y:auto">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">' +
        '<div>' +
          '<div style="font-size:18px;font-weight:800">📹 Export Ready</div>' +
          '<div style="font-size:10px;color:var(--cyan);font-weight:700;margin-top:2px">EXPORT OPTIMIZER AGENT</div>' +
        '</div>' +
        '<button onclick="document.getElementById(\'export-result-overlay\').remove()" style="background:rgba(255,255,255,.06);border:none;border-radius:8px;padding:6px 12px;color:#fff;cursor:pointer">✕</button>' +
      '</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">' +
        '<div style="padding:12px;background:rgba(255,255,255,.03);border:1px solid var(--bdr);border-radius:10px"><div style="font-size:9px;color:var(--t4);font-weight:700;text-transform:uppercase;margin-bottom:4px">Platform</div><div style="font-size:14px;font-weight:700">' + (data.platform || '—') + '</div></div>' +
        '<div style="padding:12px;background:rgba(255,255,255,.03);border:1px solid var(--bdr);border-radius:10px"><div style="font-size:9px;color:var(--t4);font-weight:700;text-transform:uppercase;margin-bottom:4px">Resolution</div><div style="font-size:14px;font-weight:700">' + (data.resolution || '—') + '</div></div>' +
        '<div style="padding:12px;background:rgba(255,255,255,.03);border:1px solid var(--bdr);border-radius:10px"><div style="font-size:9px;color:var(--t4);font-weight:700;text-transform:uppercase;margin-bottom:4px">Output File</div><div style="font-size:12px;color:var(--cyan)">' + (data.output_filename || '—') + '</div></div>' +
        '<div style="padding:12px;background:rgba(255,255,255,.03);border:1px solid var(--bdr);border-radius:10px"><div style="font-size:9px;color:var(--t4);font-weight:700;text-transform:uppercase;margin-bottom:4px">Estimated Size</div><div style="font-size:14px;font-weight:700">' + (data.estimated_file_size || '—') + '</div></div>' +
      '</div>' +
      ffmpegBlock +
      ffmpegNote +
    '</div>';

  document.body.appendChild(overlay);
  overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
  if (typeof toast === 'function') toast('Export command ready for ' + (data.platform || selectedPreset) + '!');
}
