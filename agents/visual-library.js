/**
 * agents/visual-library.js
 * ─────────────────────────────────────────────────────────────
 * Visual Library view logic:
 *   - initLibrary()       : lazy-initialise library on first visit
 *   - renderLib(query)    : render filtered asset grid
 *   - filterLib(el, cat)  : sidebar category filter
 *   - filterLibSearch(q)  : search-box filter
 *   - generateAIImage()   : simulate DALL·E 3 image generation
 *
 * Depends on: agent-data.js (LIB_ASSETS)
 */

let libInited  = false;
let libFilter  = 'all';

function initLibrary() {
  if (!libInited) {
    libInited = true;
    renderLib();
  }
}

function renderLib(query = '') {
  const grid = document.getElementById('lib-grid');
  grid.innerHTML = '';

  const filtered = LIB_ASSETS.filter(a => {
    const matchCat = libFilter === 'all' || a.cat === libFilter;
    const matchQ   = !query
      || a.l.toLowerCase().includes(query.toLowerCase())
      || a.t.toLowerCase().includes(query.toLowerCase());
    return matchCat && matchQ;
  });

  if (filtered.length === 0) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--t4)">No assets found. Try generating with AI.</div>';
    return;
  }

  filtered.forEach(a => {
    const card = document.createElement('div');
    card.className = 'lib-card';
    card.innerHTML = `
      <div style="width:100%;height:100%;background:${a.c};display:flex;align-items:center;justify-content:center;font-size:11px;color:rgba(255,255,255,.35);font-weight:600;text-align:center;padding:8px">${a.l}</div>
      <div class="lib-card-overlay">
        <button class="btn btn-primary btn-xs" onclick="event.stopPropagation();toast('Added to timeline!')">+ Add</button>
        <button class="btn btn-secondary btn-xs" onclick="event.stopPropagation();toast('Opening preview…')">View</button>
      </div>
      <div class="lib-card-label"><span class="tag tag-p" style="font-size:7px">${a.t}</span></div>
      <div class="lib-source-badge">${a.src}</div>`;
    grid.appendChild(card);
  });
}

function filterLib(el, cat) {
  el.closest('.sidebar').querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  el.classList.add('active');
  libFilter = cat;
  renderLib(document.getElementById('lib-search').value);
}

function filterLibSearch(q) {
  renderLib(q);
}

function generateAIImage() {
  toast('Generating with DALL·E 3…');
  setTimeout(() => { toast('AI image generated and added to library!'); }, 2400);
}
