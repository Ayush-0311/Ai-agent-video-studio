/**
 * agents/agent-engine.js
 * ─────────────────────────────────────────────────────────────
 * AI Agent Workforce Engine for 16 Local Autonomous Agents:
 *   - renderAgentGrid(filter) : Renders Core & Bonus Agent cards
 *   - initAgents()            : Bootstraps live logs & console prompt parser
 *   - handleNLCommand()       : Natural Language Edit Agent prompt handler
 *   - initArch()              : Renders 3-Layer Local Software Architecture
 */

let agentsInited = false;
let currentAgentFilter = 'all';

function initAgents() {
  renderAgentGrid(currentAgentFilter);

  if (agentsInited) return;
  agentsInited = true;

  const logs = [
    {a: "Orchestrator Agent",        m: "Dispatching scene 2 to Layout Planner & Voice synthesis DAG.", c: "p"},
    {a: "Script Agent",              m: "Generated 6-scene structured narration with viral hooks.",     c: "p"},
    {a: "Layout Planner Agent",      m: "Assigned Split-Screen layout to Scene 2 and Dual-Avatar to Scene 4.", c: "c"},
    {a: "Image Generator Agent",     m: "Stable Diffusion XL rendered 4K visual asset in 2.1s.",          c: "c"},
    {a: "Voice Agent (Coqui XTTS)",  m: "Synthesized 44.1kHz WAV voice track with 0.98 audio clarity.",  c: "orange"},
    {a: "Lip-Sync Agent (MuseTalk)", m: "CUDA aligned mouth motion to voice frames at 60fps.",            c: "orange"},
    {a: "Caption Agent (Whisper)",   m: "Word-level timestamps generated with 0.4% WER.",                 c: "g"},
    {a: "Multi-Language Agent",      m: "Translated script to Hindi & synthesized Chatterbox TTS track.", c: "g"},
    {a: "Brand Kit Agent",           m: "Applied brand primary logo, custom hex theme & typography.",    c: "p"},
    {a: "Conversation Mode Agent",   m: "Split dialogue into Speaker A & Speaker B with camera cuts.",    c: "c"},
    {a: "Natural Language Edit Agent",m: "Parsed command: 'Make background dark cyan' -> Scene 3 updated.",c: "orange"},
    {a: "Music/Sound Agent",         m: "Selected ambient track; auto-ducked volume by -14dB during speech.",c: "g"},
    {a: "Export Optimizer Agent",    m: "Prepared YouTube 16:9, Reels 9:16 & LinkedIn 1:1 render presets.",c: "p"}
  ];

  const consoleEl = document.getElementById('agent-console');
  if (!consoleEl) return;

  setInterval(() => {
    if (window.currentView !== 'agents') return;

    const log = logs[Math.floor(Math.random() * logs.length)];
    const colorMap = {p: 'purple', c: 'cyan', orange: 'orange', g: 'green'};
    const colorVar = colorMap[log.c] || log.c;

    const el = document.createElement('div');
    el.className = 'flex gap-12';
    el.style.animation = 'fadeUp 0.3s ease';
    el.innerHTML = `
      <div class="dot dot-${log.c}" style="margin-top:6px"></div>
      <div style="font-size:13px">
        <span style="font-weight:700;color:var(--${colorVar})">${log.a}:</span> ${log.m}
      </div>`;
    consoleEl.prepend(el);

    if (consoleEl.children.length > 10) consoleEl.lastElementChild.remove();
  }, 2800);
}

function filterAgents(el, filter) {
  if (el && el.closest) {
    el.closest('.sidebar').querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
  }
  currentAgentFilter = filter;
  renderAgentGrid(filter);
}

function renderAgentGrid(filter = 'all') {
  const grid = document.getElementById('agent-grid');
  if (!grid) return;
  grid.innerHTML = '';

  const filtered = AGENTS_LIST.filter(a => {
    if (filter === 'all') return true;
    if (filter === 'core') return a.type === 'core';
    if (filter === 'bonus') return a.type === 'bonus';
    return true;
  });

  filtered.forEach(agent => {
    const card = document.createElement('div');
    card.className = 'card p-24 card-hover flex flex-col gap-16';
    card.style.padding = '22px';
    
    const tagClass = agent.type === 'core' ? 'tag-p' : 'tag-c';
    const typeLabel = agent.type === 'core' ? 'CORE PIPELINE' : 'BONUS FEATURE';

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-12">
          <div style="width:44px;height:44px;border-radius:12px;background:rgba(139,92,246,0.12);display:flex;align-items:center;justify-content:center;color:var(--purple);font-weight:800;font-size:14px">
            ${agent.id === 'orchestrator' ? '⚡' : agent.id === 'script' ? '📝' : agent.id === 'voice' ? '🎙️' : agent.id === 'lip_sync' ? '🗣️' : agent.id === 'nl_edit' ? '💬' : agent.id === 'export_optimizer' ? '📹' : '🤖'}
          </div>
          <div>
            <div class="h4" style="font-size:15px">${agent.name}</div>
            <div class="flex gap-6 items-center" style="margin-top:2px">
              <span class="tag ${tagClass}" style="font-size:8px">${typeLabel}</span>
              <span class="tag tag-y" style="font-size:8px">${agent.badge}</span>
            </div>
          </div>
        </div>
        <div class="toggle on" onclick="this.classList.toggle('on'); toast('${agent.name} state toggled')"></div>
      </div>
      <p style="font-size:12px;color:var(--t2);line-height:1.55">${agent.desc}</p>
      
      <div style="background:rgba(255,255,255,0.02);padding:10px;border-radius:8px;border:1px solid var(--bdr);font-size:11px">
        <div style="color:var(--t4);margin-bottom:3px"><strong>Tool:</strong> ${agent.tool}</div>
        <div style="color:var(--t3);margin-bottom:2px"><strong>Input:</strong> ${agent.input}</div>
        <div style="color:var(--t2)"><strong>Output:</strong> ${agent.output}</div>
      </div>

      <div class="flex items-center justify-between" style="margin-top:auto;padding-top:10px;border-top:1px solid var(--bdr)">
         <span class="mono" style="font-size:10px;color:var(--t4)">Uptime: ${agent.uptime}</span>
         <button class="btn btn-secondary btn-xs" onclick="toast('Executing ${agent.name}...')">Run Task</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

function handleNLCommand(inputElId) {
  const input = document.getElementById(inputElId);
  if (!input || !input.value.trim()) return;
  
  const cmd = input.value.trim();
  toast(`Natural Language Edit Agent parsing: "${cmd}"...`);
  
  const consoleEl = document.getElementById('agent-console');
  if (consoleEl) {
    const el = document.createElement('div');
    el.className = 'flex gap-12';
    el.style.animation = 'fadeUp 0.3s ease';
    el.innerHTML = `
      <div class="dot dot-y" style="margin-top:6px"></div>
      <div style="font-size:13px">
        <span style="font-weight:700;color:var(--yellow)">User NL Command:</span> "${cmd}" → <span style="color:var(--cyan)">Natural Language Edit Agent: Re-rendering Scene Diff...</span>
      </div>`;
    consoleEl.prepend(el);
  }
  
  input.value = '';
  setTimeout(() => {
    toast('Scene update rendered in 1.4s! (Incremental render success)', 'success');
  }, 1400);
}

/* ─── ARCHITECTURE DIAGRAM ─────────────────────────────────── */
let archInited = false;

function initArch() {
  if (archInited) return;
  archInited = true;

  const diag = document.getElementById('arch-diagram');
  if (!diag) return;
  diag.innerHTML = '';

  ARCH_NODES.forEach((node, i) => {
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;align-items:center;width:100%';

    const nodeEl = document.createElement('div');
    nodeEl.className = 'arch-node';
    nodeEl.style.animationDelay = (i * 0.07) + 's';
    nodeEl.style.width = '100%';
    nodeEl.innerHTML = `
      <div>
        <div style="font-size:15px;font-weight:700;color:var(--t1)">${node.label}</div>
        <div style="font-size:12px;color:var(--t4);margin-top:2px">${node.sub}</div>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <div style="width:8px;height:8px;border-radius:50%;background:${node.color};box-shadow:0 0 8px ${node.color}"></div>
      </div>`;

    nodeEl.onmouseenter = () => { nodeEl.style.borderColor = node.color + '80'; };
    nodeEl.onmouseleave = () => { nodeEl.style.borderColor = ''; };
    wrap.appendChild(nodeEl);

    if (i < ARCH_NODES.length - 1) {
      const conn = document.createElement('div');
      conn.className = 'arch-connector';
      conn.style.background = `linear-gradient(to bottom,${node.color}80,${ARCH_NODES[i+1].color}40)`;
      conn.style.color = node.color + '80';
      wrap.appendChild(conn);
    }

    diag.appendChild(wrap);
  });
}
