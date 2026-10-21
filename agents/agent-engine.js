/**
 * agents/agent-engine.js
 * ─────────────────────────────────────────────────────────────
 * SmartEdit AI — Agent Engine UI
 * Renders agent cards with real "Run Task" buttons wired to backend.
 */

var agentsInited = false;
var currentAgentFilter = 'all';

// ─────────────────────────────────────────────────────────────
// initAgents — bootstraps the agent view with live console
// ─────────────────────────────────────────────────────────────

function initAgents() {
  renderAgentGrid(currentAgentFilter);
  if (agentsInited) return;
  agentsInited = true;
  startAgentStatusPoller();
}

// ─────────────────────────────────────────────────────────────
// Live status poller — pings /api/v1/agents-status every 8s
// ─────────────────────────────────────────────────────────────

var agentStatusInterval = null;

function startAgentStatusPoller() {
  if (agentStatusInterval) clearInterval(agentStatusInterval);
  pollAgentStatus();
  agentStatusInterval = setInterval(pollAgentStatus, 8000);
}

async function pollAgentStatus() {
  var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
  try {
    var res = await fetch(apiBase + '/api/v1/agents-status');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var data = await res.json();

    // Update status badges on agent cards
    if (data.implemented_agents) {
      data.implemented_agents.forEach(function(agent) {
        var badge = document.getElementById('agent-status-' + agent.agent_id);
        if (badge) {
          badge.textContent = agent.status === 'active' ? 'ONLINE' : agent.status.toUpperCase().replace(/_/g, ' ');
          badge.style.background = agent.status === 'active' ? 'rgba(16,185,129,.15)' : 'rgba(245,158,11,.15)';
          badge.style.color = agent.status === 'active' ? 'var(--green)' : 'var(--yellow)';
        }
      });
    }

    // Update status dot
    var statusDot = document.getElementById('agent-backend-dot');
    if (statusDot) {
      statusDot.className = 'dot dot-g';
      statusDot.title = 'Backend: Online — ' + (data.total_agents || 16) + ' agents loaded';
    }

    // Log runtime info to console once
    if (window.AgentPipeline && data.runtime) {
      var rt = data.runtime;
      AgentPipeline.logAgentAction('backend', 'Backend Status', 'Online ✓ | Ollama: ' + rt.ollama_model + ' | FFmpeg: ' + (rt.ffmpeg_available ? 'yes' : 'not found') + ' | Voice: ' + (rt.voice_engine || 'unconfigured') + (rt.voice_configured ? ' (configured)' : ' (needs setup)'), 'g');
    }
  } catch (e) {
    var statusDot2 = document.getElementById('agent-backend-dot');
    if (statusDot2) { statusDot2.className = 'dot'; statusDot2.style.background = '#EF4444'; }
    if (window.AgentPipeline) AgentPipeline.logAgentAction('backend', 'Backend Status', 'Offline — start the backend with "Launch SmartEdit.bat"', 'r');
  }
}

// ─────────────────────────────────────────────────────────────
// filterAgents
// ─────────────────────────────────────────────────────────────

function filterAgents(el, filter) {
  if (el && el.closest) {
    el.closest('.sidebar').querySelectorAll('.nav-item').forEach(function(n) { n.classList.remove('active'); });
    el.classList.add('active');
  }
  currentAgentFilter = filter;
  renderAgentGrid(filter);
}


// ─────────────────────────────────────────────────────────────
// renderAgentGrid — draws all agent cards
// ─────────────────────────────────────────────────────────────

var AGENT_ICONS = {
  orchestrator: '⚡', script: '📝', layout_planner: '🗂️',
  slide_generator: '📊', image_generator: '🖼️', avatar_generator: '🧑‍💻',
  voice: '🎙️', lip_sync: '🗣️', caption: '🔤', compositor: '🎬',
  multi_language: '🌍', brand_kit: '🎨', conversation_mode: '💬',
  nl_edit: '✏️', music_sound: '🎵', export_optimizer: '📹',
  // Video Intelligence Agents
  scene_detection: '🔍', jump_cut: '✂️', viral_hook: '🪝',
  seo_metadata: '🔎', chapter_marker: '📍', thumbnail_gen: '🖼',
  color_grading: '🎨', noise_reduction: '🔇', broll_suggestion: '🎞️',
  script_optimizer: '🚀', emotion_analysis: '💡', viral_clip: '📱'
};

var AGENT_TYPE_COLORS = {
  core:  { tag: 'tag-p', label: 'CORE PIPELINE' },
  bonus: { tag: 'tag-c', label: 'BONUS FEATURE' },
  video: { tag: 'tag-g', label: 'VIDEO INTEL' }
};

function renderAgentGrid(filter) {
  filter = filter || 'all';
  var grid = document.getElementById('agent-grid');
  if (!grid) return;
  grid.innerHTML = '';

  var filtered = AGENTS_LIST.filter(function(a) {
    if (filter === 'all') return true;
    if (filter === 'core') return a.type === 'core';
    if (filter === 'bonus') return a.type === 'bonus';
    if (filter === 'video') return a.type === 'video';
    return true;
  });

  filtered.forEach(function(agent, index) {
    var card = document.createElement('div');
    card.className = 'card p-24 card-hover flex flex-col gap-16';
    card.style.cssText = 'padding:22px;animation:fadeUp ' + (0.05 + index * 0.04) + 's ease both;position:relative;';

    var typeInfo = AGENT_TYPE_COLORS[agent.type] || { tag: 'tag-c', label: 'FEATURE' };
    var tagClass = typeInfo.tag;
    var typeLabel = typeInfo.label;
    var icon = AGENT_ICONS[agent.id] || '🤖';

    // Build the Run button action
    var runBtnId = 'run-btn-' + agent.id;
    var statusBadgeId = 'agent-status-' + agent.id;

    card.innerHTML =
      '<div class="flex items-center justify-between">' +
        '<div class="flex items-center gap-12">' +
          '<div style="width:44px;height:44px;border-radius:12px;background:rgba(139,92,246,0.12);display:flex;align-items:center;justify-content:center;font-size:22px">' + icon + '</div>' +
          '<div>' +
            '<div class="h4" style="font-size:15px">' + agent.name + '</div>' +
            '<div class="flex gap-6 items-center" style="margin-top:3px">' +
              '<span class="tag ' + tagClass + '" style="font-size:8px">' + typeLabel + '</span>' +
              '<span class="tag tag-y" style="font-size:8px">' + agent.badge + '</span>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '<div id="' + statusBadgeId + '" style="font-size:9px;font-weight:800;padding:3px 8px;border-radius:5px;background:rgba(139,92,246,.15);color:var(--t2)">Checking</div>' +
      '</div>' +
      '<p style="font-size:12px;color:var(--t2);line-height:1.55;flex:1">' + agent.desc + '</p>' +
      '<div style="background:rgba(255,255,255,0.02);padding:10px;border-radius:8px;border:1px solid var(--bdr);font-size:11px">' +
        '<div style="color:var(--t4);margin-bottom:3px"><strong>Tool:</strong> ' + agent.tool + '</div>' +
        '<div style="color:var(--t3);margin-bottom:2px"><strong>Input:</strong> ' + agent.input + '</div>' +
        '<div style="color:var(--t2);margin-bottom:2px"><strong>Output:</strong> ' + agent.output + '</div>' +
        '<div style="color:var(--cyan);font-family:monospace;font-size:10px;margin-top:3px">' + (agent.method || 'POST') + ' ' + (agent.endpoint || '') + '</div>' +
      '</div>' +
      '<div class="flex items-center justify-between" style="padding-top:10px;border-top:1px solid var(--bdr)">' +
        '<span class="mono" style="font-size:10px;color:var(--t4)">On demand</span>' +
        '<button id="' + runBtnId + '" class="btn btn-secondary btn-xs" '+(agent.status==='unavailable'?'disabled ':'')+'onclick="triggerAgent(\'' + agent.id + '\', this)" style="min-width:80px">' + agent.badge + '</button>' +
      '</div>';

    grid.appendChild(card);
  });
  pollAgentStatus();
}

// ─────────────────────────────────────────────────────────────
// triggerAgent — called by each agent card's Run Task button
// ─────────────────────────────────────────────────────────────

async function triggerAgent(agentId, btn) {
  if (!window.AgentPipeline) {
    toast('AgentPipeline not loaded', 'error');
    return;
  }

  // Visual feedback
  var originalText = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Running…'; }

  try {
    var result;
    switch (agentId) {
      case 'orchestrator':
        var prompt = window.AgentPipeline.state.prompt || await window.smartEditAsk('Enter video prompt for Orchestrator:', 'Create a 30-second video about AI technology');
        if (!prompt) break;
        result = await AgentPipeline.runOrchestratorAgent(prompt, { duration: 30 });
        break;

      case 'script':
        var sp = window.AgentPipeline.state.prompt || await window.smartEditAsk('Enter script prompt:', 'Explain the power of artificial intelligence in 30 seconds');
        if (!sp) break;
        result = await AgentPipeline.runScriptAgent(sp, { duration: 30 });
        break;

      case 'layout_planner':
        if (!AgentPipeline.state.scenes.length) { toast('Generate a script first!', 'error'); break; }
        result = await AgentPipeline.runLayoutPlannerAgent('cinematic');
        break;

      case 'slide_generator':
        if (!AgentPipeline.state.scenes.length) { toast('Generate a script first!', 'error'); break; }
        result = await AgentPipeline.runSlideGeneratorAgent(AgentPipeline.state.currentSceneIndex);
        break;

      case 'image_generator':
        if (!AgentPipeline.state.scenes.length) { toast('Generate a script first!', 'error'); break; }
        result = await AgentPipeline.runImageGeneratorAgent(AgentPipeline.state.currentSceneIndex);
        showAgentResultModal('Image Generator Agent', result && result.result);
        break;

      case 'avatar_generator':
        result = await AgentPipeline.runAvatarGeneratorAgent('professional presenter, dark studio', 'neutral', 'dark studio gradient');
        showAgentResultModal('Avatar Generator Agent', result && result.result);
        break;

      case 'voice':
        var vText = (AgentPipeline.state.scenes[AgentPipeline.state.currentSceneIndex] && AgentPipeline.state.scenes[AgentPipeline.state.currentSceneIndex].text) || AgentPipeline.state.transcript;
        if (!vText) { toast('No text to speak — generate a script first!', 'error'); break; }
        result = await AgentPipeline.runVoiceAgent(vText, AgentPipeline.state.language || 'en');
        break;

      case 'lip_sync':
        if (!AgentPipeline.state.scenes.length) { toast('Generate a script first!', 'error'); break; }
        result = await AgentPipeline.runLipSyncAgent(AgentPipeline.state.currentSceneIndex);
        showAgentResultModal('Lip-Sync Agent', result ? { frames: result.frame_count, words: result.word_count, fps: result.fps } : null);
        break;

      case 'caption':
        toast('Caption Agent: Upload an audio/video file via the Upload view!');
        goTo('upload');
        break;

      case 'compositor':
        result = await AgentPipeline.runCompositorAgent();
        if (result && result.ffmpeg_command) showAgentResultModal('Compositor Agent', { command: result.ffmpeg_command, ffmpeg_available: result.ffmpeg_available });
        break;

      case 'multi_language':
        var lang = await window.smartEditAsk('Target language code (hi=Hindi, es=Spanish, fr=French, de=German, zh-CN=Chinese):', 'hi');
        if (!lang) break;
        result = await AgentPipeline.runMultiLanguageAgent(lang.trim());
        if (result) showAgentResultModal('Multi-Language Agent', { scenes_translated: result.scenes_translated, target: result.target_language, sample: result.translated_text && result.translated_text.substring(0, 120) });
        break;

      case 'brand_kit':
        var brandColor = await window.smartEditAsk('Brand primary color (hex):', '#8B5CF6');
        var brandLogo = await window.smartEditAsk('Brand logo text:', 'SmartEdit AI');
        result = await AgentPipeline.runBrandKitAgent({ logo: brandLogo || 'SmartEdit AI', color: brandColor || '#8B5CF6', secondaryColor: '#06B6D4', font: 'Inter' });
        break;

      case 'conversation_mode':
        var spA = await window.smartEditAsk('Speaker A name:', 'Host');
        var spB = await window.smartEditAsk('Speaker B name:', 'Guest');
        result = await AgentPipeline.runConversationModeAgent(spA || 'Host', spB || 'Guest');
        break;

      case 'nl_edit':
        var cmd = await window.smartEditAsk('Enter natural language edit command:', 'Make scene 1 use split-screen layout');
        if (!cmd) break;
        result = await AgentPipeline.executeNLCommand(cmd);
        if (result) showAgentResultModal('NL Edit Agent', { action: result.action, explanation: result.explanation, targets: result.target_scene_ids });
        break;

      case 'music_sound':
        var mood = await window.smartEditAsk('Select mood (energetic, calm, dramatic, upbeat, neutral):', 'neutral');
        result = await AgentPipeline.runMusicSoundAgent(mood || 'neutral');
        if (result) showAgentResultModal('Music/Sound Agent', { mood: result.mood, genre: result.music_profile && result.music_profile.genre, bpm: result.music_profile && result.music_profile.bpm, sources: result.recommended_sources });
        break;

      case 'export_optimizer':
        var ratio = await window.smartEditAsk('Aspect ratio (16:9, 9:16, 1:1):', '16:9');
        var res2 = await window.smartEditAsk('Resolution (720p, 1080p, 4K):', '1080p');
        result = await AgentPipeline.runExportOptimizerAgent(ratio || '16:9', res2 || '1080p', 'h264');
        if (result) showAgentResultModal('Export Optimizer Agent', { platform: result.platform, filename: result.output_filename, command: result.ffmpeg_command, size: result.estimated_file_size });
        break;

      // ── Video Intelligence Agents (17-28) ──────────────────────────────────

      case 'scene_detection':
        result = await AgentPipeline.runSceneDetectionAgent(AgentPipeline.state.rawSegments || [], 0.4);
        if (result) showAgentResultModal('Scene Detection Agent', { detected_scenes: result.detected_scenes, input_segments: result.input_segments, note: result.note });
        break;

      case 'jump_cut':
        var minSil = await window.smartEditAsk('Min silence duration to remove (seconds):', '0.3');
        result = await AgentPipeline.runJumpCutAgent(parseFloat(minSil) || 0.3);
        if (result) showAgentResultModal('Jump Cut Editor Agent', { silences_removed: result.silences_removed, time_saved_seconds: result.time_saved_seconds, new_duration: result.new_duration, command: result.ffmpeg_command });
        break;

      case 'viral_hook':
        var hvPlatform = await window.smartEditAsk('Platform (youtube, reels, tiktok, linkedin):', 'youtube');
        result = await AgentPipeline.runViralHookAgent(hvPlatform || 'youtube');
        if (result) showAgentResultModal('Viral Hook Analyzer Agent', { hook_score: result.hook_score + '/10', hook_grade: result.hook_grade, improved_hook: result.improved_hook, retention_tip: result.retention_tip, weaknesses: (result.weaknesses || []).join(', ') });
        break;

      case 'seo_metadata':
        var seoPlatform = await window.smartEditAsk('Platform (youtube, linkedin, instagram, tiktok):', 'youtube');
        var seoTopic = await window.smartEditAsk('Video topic (optional):', AgentPipeline.state.prompt || '');
        result = await AgentPipeline.runSEOMetadataAgent(seoPlatform || 'youtube', seoTopic || '');
        if (result) showAgentResultModal('SEO Metadata Agent', { title: result.title, tags: (result.tags || []).join(', '), hashtags: (result.hashtags || []).join(' '), thumbnail_text: result.thumbnail_text, first_comment: result.first_comment });
        break;

      case 'chapter_marker':
        var minChDur = await window.smartEditAsk('Min chapter duration (seconds):', '30');
        result = await AgentPipeline.runChapterMarkerAgent(parseFloat(minChDur) || 30);
        if (result) showAgentResultModal('Chapter Marker Agent', { chapter_count: result.chapter_count, youtube_chapters: result.youtube_description_format });
        break;

      case 'thumbnail_gen':
        var thumbStyle = await window.smartEditAsk('Style (bold-text-overlay, minimal, face-close-up, split-before-after):', 'bold-text-overlay');
        var thumbColor = await window.smartEditAsk('Color theme (dark-purple, electric-blue, fire-orange, green-neon, red-drama):', 'dark-purple');
        result = await AgentPipeline.runThumbnailGenAgent(thumbStyle || 'bold-text-overlay', thumbColor || 'dark-purple');
        if (result) showAgentResultModal('Thumbnail Generator Agent', { image_prompt: result.image_prompt, design_tip: result.design_tip, face_expression: result.face_expression, a_b_variant_prompt: result.a_b_variant_prompt, avoid: result.avoid });
        break;

      case 'color_grading':
        var cgMood = await window.smartEditAsk('Mood (cinematic, warm, cool, vibrant, noir, vintage, natural):', 'cinematic');
        var cgInt = await window.smartEditAsk('Intensity (0.0-1.0):', '0.7');
        result = await AgentPipeline.runColorGradingAgent(cgMood || 'cinematic', parseFloat(cgInt) || 0.7);
        if (result) showAgentResultModal('Color Grading Agent', { mood: result.mood, note: result.note, css_filter: result.css_filter, command: result.ffmpeg_command });
        break;

      case 'noise_reduction':
        var nrProfile = await window.smartEditAsk('Noise profile (auto, room, outdoor, studio, street):', 'auto');
        var nrStr = await window.smartEditAsk('Strength (0.0-1.0):', '0.5');
        result = await AgentPipeline.runNoiseReductionAgent(nrProfile || 'auto', parseFloat(nrStr) || 0.5);
        if (result) showAgentResultModal('Noise Reduction Agent', { profile: result.noise_profile, desc: result.profile_desc, command: result.ffmpeg_command, loudnorm: result.settings && result.settings.loudnorm });
        break;

      case 'broll_suggestion':
        var bStyle = await window.smartEditAsk('B-Roll style (cinematic, documentary, stock, animated):', 'cinematic');
        result = await AgentPipeline.runBRollSuggestionAgent(bStyle || 'cinematic');
        if (result) showAgentResultModal('B-Roll Suggestion Agent', { suggestions: result.suggestion_count + ' ideas for ' + result.scene_count + ' scenes', tip: result.tip, sources: Object.keys(result.free_sources || {}).join(', ') });
        break;

      case 'script_optimizer':
        var soGoal = await window.smartEditAsk('Optimization goal (engagement, clarity, seo, retention, conversion):', 'engagement');
        var soTone = await window.smartEditAsk('Tone (professional, casual, energetic, educational, storytelling):', 'professional');
        result = await AgentPipeline.runScriptOptimizerAgent(soGoal || 'engagement', soTone || 'professional');
        if (result) showAgentResultModal('Script Optimizer Agent', { goal: result.goal, scenes_optimized: result.scenes_optimized, readability_grade: result.readability_grade, watch_time_improvement: result.estimated_watch_time_improvement, tips: (result.overall_tips || []).join(' | ') });
        break;

      case 'emotion_analysis':
        result = await AgentPipeline.runEmotionAnalysisAgent();
        if (result) showAgentResultModal('Emotion Analysis Agent', { overall_arc: result.overall_arc, engagement_prediction: result.engagement_prediction, scenes_analyzed: result.emotions_detected, pacing_issues: (result.pacing_issues || []).join(', ') || 'None', best_thumbnail_scene: result.best_scene_for_thumbnail });
        break;

      case 'viral_clip':
        var vcPlatform = await window.smartEditAsk('Platform (reels, tiktok, shorts, linkedin):', 'reels');
        var vcMaxDur = await window.smartEditAsk('Max clip duration (seconds):', '60');
        result = await AgentPipeline.runViralClipAgent(vcPlatform || 'reels', parseFloat(vcMaxDur) || 60);
        if (result && result.viral_clips && result.viral_clips.length) {
          var best = result.viral_clips[0];
          showAgentResultModal('Viral Clip Finder Agent', { clips_found: result.clips_found, best_virality_score: best.virality_score, suggested_title: best.suggested_title, caption: best.suggested_caption, command: best.ffmpeg_command, editing_tips: (result.editing_suggestions || []).join(' | ') });
        }
        break;

      default:
        toast('Agent "' + agentId + '" not wired yet', 'error');
    }
  } catch (err) {
    console.error('triggerAgent error:', err);
  }

  if (btn) { btn.disabled = false; btn.textContent = originalText; }
}

// ─────────────────────────────────────────────────────────────
// showAgentResultModal — shows result in a toast-style overlay
// ─────────────────────────────────────────────────────────────

function showAgentResultModal(agentName, data) {
  if (!data) return;

  // Remove existing
  var existing = document.getElementById('agent-result-overlay');
  if (existing) existing.remove();

  var overlay = document.createElement('div');
  overlay.id = 'agent-result-overlay';
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px)';

  var rows = Object.entries(data).map(function(kv) {
    var key = kv[0];
    var val = kv[1];
    var valStr = typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val);
    var isCode = key === 'command' || key === 'positive_prompt' || key === 'portrait_prompt';
    var displayVal = isCode
      ? '<pre style="background:rgba(0,0,0,.4);padding:10px;border-radius:8px;font-size:10px;overflow-x:auto;max-width:100%;white-space:pre-wrap;word-break:break-all;color:var(--cyan)">' + valStr + '</pre>'
      : '<div style="color:var(--t2);font-size:12px">' + valStr + '</div>';
    return '<div style="margin-bottom:12px"><div style="font-size:10px;font-weight:700;color:var(--t4);text-transform:uppercase;margin-bottom:4px">' + key.replace(/_/g, ' ') + '</div>' + displayVal + '</div>';
  }).join('');

  overlay.innerHTML =
    '<div style="background:var(--bg1);border:1px solid var(--bdr);border-radius:20px;padding:28px;max-width:560px;width:90%;max-height:80vh;overflow-y:auto;position:relative">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">' +
        '<div>' +
          '<div style="font-size:17px;font-weight:800">' + agentName + ' Result</div>' +
          '<div style="font-size:10px;color:var(--cyan);font-weight:700;margin-top:2px">AGENT OUTPUT</div>' +
        '</div>' +
        '<button onclick="document.getElementById(\'agent-result-overlay\').remove()" style="background:rgba(255,255,255,.06);border:none;border-radius:8px;padding:6px 12px;color:#fff;cursor:pointer;font-size:14px">✕ Close</button>' +
      '</div>' +
      rows +
    '</div>';

  document.body.appendChild(overlay);
  overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
}



// ─────────────────────────────────────────────────────────────
// Architecture diagram
// ─────────────────────────────────────────────────────────────

var archInited = false;

function initArch() {
  if (archInited) return;
  archInited = true;
  var diag = document.getElementById('arch-diagram');
  if (!diag) return;
  diag.innerHTML = '';

  ARCH_NODES.forEach(function(node, i) {
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;align-items:center;width:100%';

    var nodeEl = document.createElement('div');
    nodeEl.className = 'arch-node';
    nodeEl.style.animationDelay = (i * 0.07) + 's';
    nodeEl.style.width = '100%';
    nodeEl.innerHTML =
      '<div>' +
        '<div style="font-size:15px;font-weight:700;color:var(--t1)">' + node.label + '</div>' +
        '<div style="font-size:12px;color:var(--t4);margin-top:2px">' + node.sub + '</div>' +
      '</div>' +
      '<div style="display:flex;align-items:center;gap:8px">' +
        '<div style="width:8px;height:8px;border-radius:50%;background:' + node.color + ';box-shadow:0 0 8px ' + node.color + '"></div>' +
      '</div>';

    nodeEl.onmouseenter = function() { nodeEl.style.borderColor = node.color + '80'; };
    nodeEl.onmouseleave = function() { nodeEl.style.borderColor = ''; };
    wrap.appendChild(nodeEl);

    if (i < ARCH_NODES.length - 1) {
      var conn = document.createElement('div');
      conn.className = 'arch-connector';
      conn.style.background = 'linear-gradient(to bottom,' + node.color + '80,' + ARCH_NODES[i + 1].color + '40)';
      wrap.appendChild(conn);
    }
    diag.appendChild(wrap);
  });
}
