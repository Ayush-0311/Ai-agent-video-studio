/**
 * agents/agent-pipeline-core.js
 * ─────────────────────────────────────────────────────────────
 * SmartEdit AI — Full 16-Agent Pipeline Core
 * All agent methods call real FastAPI backend endpoints.
 */

var AgentPipeline = {

  // ── Shared State ──────────────────────────────────────────
  state: {
    prompt: '',
    language: 'en',
    aspectRatio: '16:9',
    layoutMode: 'transcript',
    brandKit: { logo: 'SmartEdit AI', color: '#8B5CF6', secondaryColor: '#06B6D4', font: 'Inter' },
    audioDucking: false,
    bgMusicVolume: 0,
    scenes: [],
    transcript: '',
    wordCount: 0,
    sourceFileName: '',
    currentJobId: null,
    currentJob: null,
    currentSceneIndex: 0,
    activeAgentsLog: [],
    translatedScenes: [],
    musicProfile: null,
    brandApplied: false,
    lastNLCommand: '',
    historyStack: [],
    redoStack: [],
    avatarStyle: 'none',
    enableLipsync: false,
  },

  // ── Core Logging ──────────────────────────────────────────

  logAgentAction: function(agentId, agentName, actionMessage, type) {
    type = type || 'p';
    var logEntry = {
      timestamp: new Date().toLocaleTimeString(),
      agentId: agentId,
      agentName: agentName,
      message: actionMessage,
      colorType: type
    };
    this.state.activeAgentsLog.unshift(logEntry);

    var consoleEl = document.getElementById('agent-console');
    if (consoleEl) {
      var colorMap = { p: 'purple', c: 'cyan', orange: 'orange', g: 'green', y: 'yellow', r: 'red' };
      var colorVar = colorMap[type] || 'purple';
      var el = document.createElement('div');
      el.className = 'flex gap-12';
      el.style.animation = 'fadeUp 0.3s ease';
      el.innerHTML = '<div class="dot dot-' + type + '" style="margin-top:6px"></div>' +
        '<div style="font-size:13px"><span style="font-weight:700;color:var(--' + colorVar + ')">' + agentName + ':</span> ' + actionMessage + '</div>';
      consoleEl.prepend(el);
      if (consoleEl.children.length > 14) consoleEl.lastElementChild.remove();
    }
  },

  // ── Universal API caller ──────────────────────────────────

  callAgent: async function(agentId, agentName, endpoint, payload) {
    var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
    this.logAgentAction(agentId, agentName, 'Calling ' + endpoint + '…', 'c');
    try {
      var response = await fetch(apiBase + endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        var errText = await response.text();
        throw new Error('HTTP ' + response.status + ': ' + errText);
      }
      var data = await response.json();
      this.logAgentAction(agentId, agentName, 'Completed successfully ✓', 'g');
      return data;
    } catch (err) {
      var msg = err && err.message ? err.message : String(err);
      this.logAgentAction(agentId, agentName, 'Error: ' + msg, 'r');
      if (typeof toast === 'function') toast(agentName + ' error: ' + msg, 'error');
      throw err;
    }
  },

  // ── Agent 1: Orchestrator ─────────────────────────────────

  runOrchestratorAgent: async function(userPrompt, config) {
    config = config || {};
    if (userPrompt) this.state.prompt = userPrompt;
    this.logAgentAction('orchestrator', 'Orchestrator Agent', 'Initiating full 16-agent pipeline for: "' + (userPrompt || '').substring(0, 40) + '…"', 'c');

    var payload = {
      prompt: userPrompt || this.state.prompt,
      duration_seconds: config.duration || 30,
      language: this.state.language,
      aspect_ratio: this.state.aspectRatio
    };

    try {
      var result = await this.callAgent('orchestrator', 'Orchestrator Agent', '/api/v1/orchestrate', payload);
      // Apply script results
      if (result.script) this.applyScriptJob(result.script);
      // Apply layout results
      if (result.scenes && result.scenes.length) this.state.scenes = result.scenes;
      // Apply music
      if (result.music) this.state.musicProfile = result.music;
      // Log pipeline
      if (result.pipeline_log) {
        result.pipeline_log.forEach(function(step) {
          var type = step.status === 'completed' ? 'g' : (step.status === 'failed' ? 'r' : 'c');
          AgentPipeline.logAgentAction(step.agent.toLowerCase().replace(/ /g,'_'), step.agent, step.detail || step.status, type);
        });
      }
      if (typeof toast === 'function') toast('Orchestrator: Pipeline complete — ' + this.state.scenes.length + ' scenes ready!');
      return result;
    } catch(err) {
      this.logAgentAction('orchestrator', 'Orchestrator Agent', 'Pipeline failed — check backend is running', 'r');
      throw err;
    }
  },

  runPipelineFromPrompt: function(userPrompt) {
    if (userPrompt) this.state.prompt = userPrompt;
    this.logAgentAction('orchestrator', 'Orchestrator Agent', 'Dispatching prompt: "' + (userPrompt||'').substring(0,40) + '…"', 'c');
  },

  // ── History Management (Undo/Redo) ────────────────────────
  
  pushHistoryState: function() {
    this.state.historyStack.push(JSON.parse(JSON.stringify(this.state.scenes)));
    this.state.redoStack = []; // clear redo stack on new edit
  },

  undo: function() {
    if (this.state.historyStack.length > 0) {
      this.state.redoStack.push(JSON.parse(JSON.stringify(this.state.scenes)));
      this.state.scenes = this.state.historyStack.pop();
      if (typeof window.toast === 'function') toast('Undo successful!');
      if (window.buildTimeline) window.buildTimeline();
      this.reRenderVideoAfterEdit();
    } else {
      if (typeof window.toast === 'function') toast('Nothing to undo.', 'error');
    }
  },

  redo: function() {
    if (this.state.redoStack.length > 0) {
      this.state.historyStack.push(JSON.parse(JSON.stringify(this.state.scenes)));
      this.state.scenes = this.state.redoStack.pop();
      if (typeof window.toast === 'function') toast('Redo successful!');
      if (window.buildTimeline) window.buildTimeline();
      this.reRenderVideoAfterEdit();
    } else {
      if (typeof window.toast === 'function') toast('Nothing to redo.', 'error');
    }
  },

  // ── Video Re-Rendering ────────────────────────────────────

  reRenderVideoAfterEdit: async function() {
    var scenes = this.state.scenes;
    if (!scenes || scenes.length === 0) return;
    
    // Show loading overlay
    var overlay = document.getElementById('render-loading-overlay');
    if (overlay) overlay.style.display = 'flex';
    if (typeof window.toast === 'function') toast('Re-rendering video with edits...');
    
    var payload = {
      scenes: scenes,
      duration_seconds: window.DURATION || 30,
      language: this.state.language || 'en',
      aspect_ratio: this.state.aspectRatio || '16:9',
      image_style: "cinematic photography, professional lighting, ultra detailed, 4K"
    };

    try {
      var result = await this.callAgent('compositor', 'Re-Render Agent', '/api/v1/re-render-video', payload);
      // Wait for it to finish by polling (reuse pipeline.js logic if possible or do simple polling here)
      var jobId = result.job_id;
      var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
      
      var pollIv = setInterval(async function() {
        try {
          var resp = await fetch(apiBase + '/api/v1/job-status/' + jobId);
          var job = await resp.json();
          if (job.status === 'completed') {
            clearInterval(pollIv);
            if (overlay) overlay.style.display = 'none';
            if (window.loadRealVideo && job.result && job.result.video_path) {
              window.loadRealVideo(apiBase + job.result.download_url);
            }
          } else if (job.status === 'failed') {
            clearInterval(pollIv);
            if (overlay) overlay.style.display = 'none';
            if (typeof window.toast === 'function') toast('Re-rendering failed: ' + job.error, 'error');
          }
        } catch(e) {
          // ignore transient poll errors
        }
      }, 2000);
      
    } catch(err) {
      if (overlay) overlay.style.display = 'none';
    }
  },

  // ── Natural Language Edit Agent (see executeNLCommand below in Agent 14 section) ──

  // ── Agent 2: Script Agent ─────────────────────────────────

  runScriptAgent: async function(promptText, config) {
    config = config || {};
    var scenes = this.state.scenes;
    if (scenes && scenes.length > 0) {
      this.logAgentAction('script', 'Script Agent', 'Re-running with ' + scenes.length + ' existing scenes — overwriting with new prompt', 'y');
    }
    var payload = {
      prompt: promptText || this.state.prompt,
      duration_seconds: config.duration || 30,
      language: config.language || this.state.language,
      aspect_ratio: config.aspectRatio || this.state.aspectRatio
    };
    var result = await this.callAgent('script', 'Script Agent', '/api/v1/generate-script', payload);
    if (result && result.result) this.applyScriptJob(result.result);
    return result;
  },

  applyScriptJob: function(result) {
    if (!result || !result.scenes) return;
    this.state.currentJob = { result: result };
    this.state.prompt = result.prompt || this.state.prompt;
    this.state.language = result.language || 'en';
    this.state.transcript = result.transcript || '';
    this.state.scenes = result.scenes.map(function(scene, index) {
      return {
        id: scene.id || index + 1,
        s: Number(scene.start) || 0,
        e: Number(scene.end) || 5,
        speaker: 'AI Avatar',
        text: scene.text || '',
        keyword: 'Scene_' + (scene.id || index + 1),
        topic: 'Script',
        layout: scene.layout || 'full-presenter',
        agent: 'Script Agent',
        notes: scene.notes || '',
        vis: {
          query: scene.visual_prompt || '',
          label: (scene.visual_prompt || '').substring(0, 20) + (scene.visual_prompt && scene.visual_prompt.length > 20 ? '…' : ''),
          color: 'rgba(245,158,11,.2)'
        }
      };
    });
    if (typeof window.DURATION !== 'undefined') {
      window.DURATION = Math.max(1, Math.ceil(Number(result.duration_seconds) || 30));
    }
    this.logAgentAction('script', 'Script Agent', 'Loaded ' + this.state.scenes.length + ' scenes into timeline.', 'p');
    if (window.buildTranscript) window.buildTranscript();
    if (window.buildDecisionPanel) window.buildDecisionPanel();
    if (window.buildTimeline) window.buildTimeline();
    if (window.updatePlaybackUI) window.updatePlaybackUI();
  },

  // ── Agent 3: Layout Planner ───────────────────────────────

  runLayoutPlannerAgent: async function(style) {
    style = style || 'cinematic';
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('Layout Planner: Generate a script first!', 'error');
      return;
    }
    var payload = { scenes: this.state.scenes.map(function(s) { return { id: s.id, text: s.text, layout: s.layout }; }), style: style };
    var result = await this.callAgent('layout_planner', 'Layout Planner Agent', '/api/v1/layout-plan', payload);
    if (result && result.scenes) {
      var self = this;
      result.scenes.forEach(function(updated) {
        var scene = self.state.scenes.find(function(s) { return s.id === updated.id; });
        if (scene) {
          scene.layout = updated.layout;
          scene.layout_reason = updated.layout_reason;
        }
      });
      this.logAgentAction('layout_planner', 'Layout Planner Agent', 'Applied layouts to ' + result.scenes.length + ' scenes.', 'p');
      if (window.buildTimeline) window.buildTimeline();
      if (window.buildTranscript) window.buildTranscript();
    }
    return result;
  },

  // ── Agent 4: Slide Generator ──────────────────────────────

  runSlideGeneratorAgent: async function(sceneIndex) {
    sceneIndex = sceneIndex !== undefined ? sceneIndex : this.state.currentSceneIndex;
    var scene = this.state.scenes[sceneIndex];
    if (!scene) {
      if (typeof toast === 'function') toast('Slide Generator: No scene selected!', 'error');
      return;
    }
    var payload = { scene_text: scene.text, scene_id: scene.id, visual_prompt: (scene.vis && scene.vis.query) || '' };
    var result = await this.callAgent('slide_generator', 'Slide Generator Agent', '/api/v1/generate-slides', payload);
    if (result && result.slide) {
      scene.slide = result.slide;
      scene.layout = 'slide-deck';
      this.logAgentAction('slide_generator', 'Slide Generator Agent', 'Slide ready: "' + result.slide.title + '"', 'c');
      if (window.buildTranscript) window.buildTranscript();
      if (typeof toast === 'function') toast('Slide generated: ' + result.slide.title);
    }
    return result;
  },

  // ── Agent 5: Image Generator ──────────────────────────────

  runImageGeneratorAgent: async function(sceneIndex) {
    sceneIndex = sceneIndex !== undefined ? sceneIndex : this.state.currentSceneIndex;
    var scene = this.state.scenes[sceneIndex];
    if (!scene) {
      if (typeof toast === 'function') toast('Image Generator: No scene selected!', 'error');
      return;
    }
    var payload = { text: scene.text, style: 'cinematic photorealistic 4K', aspect_ratio: this.state.aspectRatio };
    var result = await this.callAgent('image_generator', 'Image Generator Agent', '/api/v1/generate-image-prompt', payload);
    if (result && result.result) {
      scene.imagePrompt = result.result;
      if (scene.vis) {
        scene.vis.sdPrompt = result.result.positive_prompt;
        scene.vis.color = 'rgba(139,92,246,.25)';
      }
      this.logAgentAction('image_generator', 'Image Generator Agent', 'SD prompt: "' + (result.result.positive_prompt || '').substring(0, 50) + '…"', 'c');
      if (typeof toast === 'function') toast('Image prompt ready! Copy to Stable Diffusion or DALL-E 3.');
    }
    return result;
  },

  // ── Agent 6: Avatar Generator ─────────────────────────────

  runAvatarGeneratorAgent: async function(style, gender, background) {
    var payload = {
      style: style || 'professional presenter, studio lighting',
      gender: gender || 'neutral',
      background: background || 'dark studio gradient'
    };
    var result = await this.callAgent('avatar_generator', 'Avatar Generator Agent', '/api/v1/generate-avatar-prompt', payload);
    if (result && result.result) {
      this.logAgentAction('avatar_generator', 'Avatar Generator Agent', 'Portrait prompt: "' + (result.result.portrait_prompt || '').substring(0, 50) + '…"', 'orange');
      if (typeof toast === 'function') toast('Avatar prompt generated! Ready for Stable Diffusion Portrait model.');
    }
    return result;
  },

  // ── Agent 7: Voice Agent ──────────────────────────────────

  runVoiceAgent: async function(text, lang) {
    text = text || (this.state.scenes[this.state.currentSceneIndex] && this.state.scenes[this.state.currentSceneIndex].text) || this.state.transcript;
    lang = lang || this.state.language || 'en';
    if (!text) {
      if (typeof toast === 'function') toast('Voice Agent: No text to synthesize!', 'error');
      return;
    }
    this.logAgentAction('voice', 'Voice Agent', 'Synthesizing: "' + text.substring(0, 40) + '…"', 'orange');

    // Try backend gTTS first
    try {
      var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';
      var response = await fetch(apiBase + '/api/v1/synthesize-voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, language: lang, slow: false })
      });
      if (response.ok) {
        var data = await response.json();
        if (data.audio_base64) {
          var audio = new Audio('data:audio/mp3;base64,' + data.audio_base64);
          audio.play();
          this.logAgentAction('voice', 'Voice Agent', 'gTTS synthesis complete — playing audio.', 'g');
          return data;
        }
      }
    } catch (e) {
      this.logAgentAction('voice', 'Voice Agent', 'Backend gTTS unavailable — falling back to Web Speech API.', 'y');
    }

    // Fallback: Web Speech Synthesis API
    this.speakScene(text, lang);
  },

  speakScene: function(text, lang) {
    if (!text) return;
    this.logAgentAction('voice', 'Voice Agent', 'Web Speech API: synthesizing "' + text.substring(0, 30) + '…"', 'orange');
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      var utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = (lang || 'en') + (lang === 'en' ? '-US' : '');
      utterance.rate = 1.0;
      window.speechSynthesis.speak(utterance);
    }
  },

  // ── Agent 8: Lip-Sync Agent ───────────────────────────────

  runLipSyncAgent: async function(sceneIndex) {
    sceneIndex = sceneIndex !== undefined ? sceneIndex : this.state.currentSceneIndex;
    var scene = this.state.scenes[sceneIndex];
    if (!scene) {
      if (typeof toast === 'function') toast('Lip-Sync Agent: No scene selected!', 'error');
      return;
    }
    var duration = (scene.e - scene.s) || 5;
    var payload = { text: scene.text, duration: duration, fps: 30 };
    var result = await this.callAgent('lip_sync', 'Lip-Sync Agent', '/api/v1/lip-sync-info', payload);
    if (result) {
      scene.lipSync = result;
      this.logAgentAction('lip_sync', 'Lip-Sync Agent', result.word_count + ' words → ' + result.frame_count + ' animation frames at ' + result.fps + 'fps.', 'g');
      if (typeof toast === 'function') toast('Lip-sync frames computed: ' + result.frame_count + ' frames');
    }
    return result;
  },

  // ── Agent 9: Caption Agent ────────────────────────────────

  applyTranscriptionJob: function(job) {
    if (!job || !job.result) return;
    var result = job.result;
    var segments = Array.isArray(result.segments) ? result.segments : [];
    var transcript = result.transcript || '';
    this.state.currentJob = job;
    this.state.currentJobId = job.job_id;
    this.state.language = result.language || 'en';
    this.state.transcript = transcript;
    this.state.rawSegments = segments;
    this.state.wordCount = segments.reduce(function(count, seg) { return count + ((seg.words || []).length); }, 0);
    this.state.scenes = segments.map(function(segment, index) {
      return {
        id: segment.id || index,
        s: Number(segment.start) || 0,
        e: Number(segment.end) || Number(segment.start) || 0,
        speaker: 'Source Audio',
        text: segment.text || '',
        keyword: 'Whisper_' + (index + 1),
        topic: 'Speech-to-Text',
        layout: 'full-presenter',
        agent: 'Caption Agent (Whisper)',
        words: segment.words || [],
        conf: AgentPipeline.averageWordConfidence(segment.words)
      };
    });
    if (typeof window.DURATION !== 'undefined') {
      window.DURATION = Math.max(1, Math.ceil(Number(result.duration) || 1));
    }
    this.logAgentAction('caption', 'Caption Agent (Whisper)', 'Loaded ' + segments.length + ' segment(s), ' + this.state.wordCount + ' word timestamps.', 'g');
    if (window.buildTranscript) window.buildTranscript();
    if (window.buildDecisionPanel) window.buildDecisionPanel();
    if (window.buildTimeline) window.buildTimeline();
    if (window.updatePlaybackUI) window.updatePlaybackUI();
  },

  averageWordConfidence: function(words) {
    if (!Array.isArray(words) || words.length === 0) return 100;
    var probs = words.map(function(w) { return typeof w.probability === 'number' ? w.probability : null; }).filter(function(v) { return v !== null; });
    if (!probs.length) return 100;
    var avg = probs.reduce(function(s, v) { return s + v; }, 0) / probs.length;
    return Math.round(avg * 100);
  },

  // ── Agent 10: Compositor Agent ────────────────────────────

  runCompositorAgent: async function() {
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('Compositor Agent: Generate content first!', 'error');
      return;
    }
    var payload = {
      job_id: this.state.currentJobId || '',
      scenes: this.state.scenes.map(function(s) { return { id: s.id, start: s.s, end: s.e, layout: s.layout }; }),
      include_captions: true,
      include_music: true
    };
    var result = await this.callAgent('compositor', 'Compositor Agent', '/api/v1/composite-video', payload);
    if (result) {
      if (result.status === 'unavailable') {
        this.logAgentAction('compositor', 'Compositor Agent', 'FFmpeg not found — install FFmpeg to enable video compositing.', 'y');
        if (typeof toast === 'function') toast('Compositor: Install FFmpeg for video compositing.', 'error');
      } else {
        this.logAgentAction('compositor', 'Compositor Agent', 'FFmpeg command ready — ' + result.scenes_count + ' scenes.', 'g');
        if (typeof toast === 'function') toast('Compositor: FFmpeg command generated!');
      }
    }
    return result;
  },

  // ── Agent 11: Multi-Language Agent ───────────────────────

  runMultiLanguageAgent: async function(targetLang) {
    targetLang = targetLang || 'hi';
    if (!this.state.transcript && !this.state.scenes.length) {
      if (typeof toast === 'function') toast('Multi-Language Agent: No content to translate!', 'error');
      return;
    }
    var payload = {
      text: this.state.transcript,
      source_language: this.state.language || 'en',
      target_language: targetLang,
      scenes: this.state.scenes.map(function(s) { return { id: s.id, text: s.text }; })
    };
    var result = await this.callAgent('multi_language', 'Multi-Language Agent', '/api/v1/translate-script', payload);
    if (result && result.translated_scenes) {
      this.state.translatedScenes = result.translated_scenes;
      this.logAgentAction('multi_language', 'Multi-Language Agent', 'Translated ' + result.scenes_translated + ' scenes → ' + targetLang, 'g');
      if (typeof toast === 'function') toast('Translation complete! ' + result.scenes_translated + ' scenes translated to ' + targetLang);
    }
    return result;
  },

  // ── Agent 12: Brand Kit Agent ─────────────────────────────

  runBrandKitAgent: async function(kit) {
    kit = kit || this.state.brandKit;
    var payload = {
      logo_text: kit.logo || 'SmartEdit AI',
      primary_color: kit.color || '#8B5CF6',
      secondary_color: kit.secondaryColor || '#06B6D4',
      font: kit.font || 'Inter',
      watermark: true,
      scenes: this.state.scenes.map(function(s) { return { id: s.id, layout: s.layout }; })
    };
    var result = await this.callAgent('brand_kit', 'Brand Kit Agent', '/api/v1/apply-brand-kit', payload);
    if (result) {
      this.state.brandApplied = true;
      // Apply CSS rules if returned
      if (result.css_rules) {
        var style = document.getElementById('brand-kit-styles') || document.createElement('style');
        style.id = 'brand-kit-styles';
        style.textContent = result.css_rules;
        document.head.appendChild(style);
      }
      // Update CSS vars for instant preview
      document.documentElement.style.setProperty('--brand-primary', kit.color || '#8B5CF6');
      document.documentElement.style.setProperty('--brand-secondary', kit.secondaryColor || '#06B6D4');
      this.logAgentAction('brand_kit', 'Brand Kit Agent', 'Brand applied: ' + kit.logo + ' | ' + kit.color, 'g');
      if (typeof toast === 'function') toast('Brand Kit applied! ' + result.scenes_branded + ' scenes branded.');
    }
    return result;
  },

  // ── Agent 13: Conversation Mode Agent ────────────────────

  runConversationModeAgent: async function(speakerA, speakerB) {
    speakerA = speakerA || 'Host';
    speakerB = speakerB || 'Guest';
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('Conversation Mode: Generate a script first!', 'error');
      return;
    }
    var payload = {
      scenes: this.state.scenes.map(function(s) { return { id: s.id, text: s.text }; }).slice(0, 6),
      speaker_a_name: speakerA,
      speaker_b_name: speakerB
    };
    var result = await this.callAgent('conversation_mode', 'Conversation Mode Agent', '/api/v1/conversation-split', payload);
    if (result && result.dialogue) {
      result.dialogue.forEach(function(d) {
        var scene = AgentPipeline.state.scenes.find(function(s) { return s.id === d.scene_id; });
        if (scene) {
          scene.layout = 'dual-conversation';
          scene.speaker = d.speaker;
        }
      });
      this.logAgentAction('conversation_mode', 'Conversation Mode Agent', 'Split into ' + result.exchange_count + ' dialogue exchanges: ' + speakerA + ' ↔ ' + speakerB, 'c');
      if (window.buildTranscript) window.buildTranscript();
      if (typeof toast === 'function') toast('Conversation Mode: ' + result.exchange_count + ' exchanges between ' + speakerA + ' & ' + speakerB);
    }
    return result;
  },

  // ── Agent 14: NL Edit Agent ───────────────────────────────

  executeNLCommand: async function(commandStr) {
    if (!commandStr || !commandStr.trim()) return;
    this.pushHistoryState();
    this.state.lastNLCommand = commandStr;
    var payload = {
      command: commandStr,
      scenes: this.state.scenes.map(function(s) { return { id: s.id, text: s.text, layout: s.layout }; }),
      current_scene_id: this.state.scenes[this.state.currentSceneIndex] ? this.state.scenes[this.state.currentSceneIndex].id : 0
    };
    var result = await this.callAgent('nl_edit', 'Natural Language Edit Agent', '/api/v1/nl-edit', payload);
    if (result) {
      this.logAgentAction('nl_edit', 'Natural Language Edit Agent', 'Action: ' + result.action + ' | ' + result.explanation, 'y');
      // Apply changes
      var changes = result.changes || {};
      var targetIds = result.target_all ? this.state.scenes.map(function(s) { return s.id; }) : (result.target_scene_ids || []);
      targetIds.forEach(function(id) {
        var scene = AgentPipeline.state.scenes.find(function(s) { return s.id === id; });
        if (!scene) return;
        if (changes.layout) scene.layout = changes.layout;
        if (changes.color && scene.vis) scene.vis.color = changes.color;
        if (changes.text) { scene.text = changes.text; }
      });
      if (window.buildTranscript) window.buildTranscript();
      if (window.buildTimeline) window.buildTimeline();
      if (typeof toast === 'function') toast('NL Edit: ' + result.explanation);
      this.reRenderVideoAfterEdit();
    }
    return result;
  },

  runNLEditAgent: function(inputElId) {
    var input = document.getElementById(inputElId || 'nl-cmd-input');
    if (!input || !input.value.trim()) return;
    var cmd = input.value.trim();
    input.value = '';
    this.executeNLCommand(cmd);
  },

  // ── Agent 15: Music / Sound Agent ────────────────────────

  runMusicSoundAgent: async function(mood) {
    mood = mood || 'neutral';
    var duration = typeof window.DURATION !== 'undefined' ? window.DURATION : 30;
    var payload = { mood: mood, duration_seconds: duration, duck_on_speech: true };
    var result = await this.callAgent('music_sound', 'Music/Sound Agent', '/api/v1/select-music', payload);
    if (result) {
      this.state.musicProfile = result;
      this.logAgentAction('music_sound', 'Music/Sound Agent', 'Profile: ' + result.mood + ' | BPM: ' + (result.music_profile && result.music_profile.bpm) + ' | Sources: ' + (result.recommended_sources || []).length, 'g');
      if (typeof toast === 'function') toast('Music profile selected: ' + result.mood + ' (' + (result.music_profile && result.music_profile.genre) + ')');
    }
    return result;
  },

  // ── Agent 16: Export Optimizer Agent ─────────────────────

  runExportOptimizerAgent: async function(aspectRatio, resolution, codec) {
    aspectRatio = aspectRatio || '16:9';
    resolution = resolution || '1080p';
    codec = codec || 'h264';
    var payload = {
      aspect_ratio: aspectRatio,
      resolution: resolution,
      fps: 30,
      codec: codec,
      include_subtitles: true,
      job_id: this.state.currentJobId || ''
    };
    var result = await this.callAgent('export_optimizer', 'Export Optimizer Agent', '/api/v1/export-video', payload);
    if (result) {
      this.logAgentAction('export_optimizer', 'Export Optimizer Agent', 'FFmpeg command ready for ' + result.platform + ' — ' + result.resolution, 'p');
      if (typeof toast === 'function') toast('Export ready: ' + result.platform + ' ' + result.resolution);
    }
    return result;
  },

  // ══════════════════════════════════════════════════════════════════════════
  // VIDEO INTELLIGENCE AGENTS — Agents 17-28
  // ══════════════════════════════════════════════════════════════════════════

  // Agent 17: Scene Detection
  runSceneDetectionAgent: async function(segments, threshold) {
    var segs = segments || this.state.rawSegments || [];
    if (!segs.length) {
      this.logAgentAction('scene_detection', 'Scene Detection Agent', 'No segments available — upload a file first', 'r');
      if (typeof toast === 'function') toast('Upload a video first to detect scenes!', 'error');
      return null;
    }
    var payload = { transcript_segments: segs, threshold: threshold || 0.4, min_scene_duration: 3.0 };
    var result = await this.callAgent('scene_detection', 'Scene Detection Agent', '/api/v1/detect-scenes', payload);
    if (result) {
      this.logAgentAction('scene_detection', 'Scene Detection Agent', result.detected_scenes + ' semantic scenes detected from ' + result.input_segments + ' segments.', 'g');
      if (result.scenes && result.scenes.length) {
        // Merge into existing scenes
        this.state.scenes = result.scenes.map(function(s, i) {
          return { id: s.id || i+1, text: s.text, start: s.start, end: s.end, duration: s.duration, layout: s.suggested_layout };
        });
      }
      if (typeof toast === 'function') toast('Scene Detection: ' + result.detected_scenes + ' scenes found!');
    }
    return result;
  },

  // Agent 18: Jump Cut Editor
  runJumpCutAgent: async function(minSilence, padding) {
    var segs = this.state.rawSegments || [];
    if (!segs.length) {
      this.logAgentAction('jump_cut', 'Jump Cut Editor Agent', 'No segments available — upload a file first', 'r');
      if (typeof toast === 'function') toast('Upload a video first!', 'error');
      return null;
    }
    var payload = { segments: segs, silence_threshold_db: -40, min_silence_duration: minSilence || 0.3, padding_seconds: padding || 0.05 };
    var result = await this.callAgent('jump_cut', 'Jump Cut Editor Agent', '/api/v1/jump-cut', payload);
    if (result) {
      this.logAgentAction('jump_cut', 'Jump Cut Editor Agent',
        result.silences_removed + ' silences removed. Saved ' + result.time_saved_seconds + 's. New duration: ' + result.new_duration + 's.', 'g');
      if (typeof toast === 'function') toast('Jump Cut: removed ' + result.silences_removed + ' silences, saved ' + result.time_saved_seconds + 's!');
    }
    return result;
  },

  // Agent 19: Viral Hook Analyzer
  runViralHookAgent: async function(platform) {
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('Generate a script or upload a video first!', 'error');
      return null;
    }
    var payload = { scenes: this.state.scenes.slice(0, 3), platform: platform || 'youtube', hook_duration_seconds: 3.0 };
    var result = await this.callAgent('viral_hook', 'Viral Hook Analyzer Agent', '/api/v1/analyze-hook', payload);
    if (result) {
      this.logAgentAction('viral_hook', 'Viral Hook Analyzer Agent',
        'Hook score: ' + result.hook_score + '/10 (' + result.hook_grade + ') | Improved hook: "' + (result.improved_hook || '').substring(0, 60) + '"', 'g');
      if (typeof toast === 'function') toast('Viral Hook scored: ' + result.hook_score + '/10 — ' + result.hook_grade);
    }
    return result;
  },

  // Agent 20: SEO Metadata
  runSEOMetadataAgent: async function(platform, topic) {
    var transcript = this.state.transcript || this.state.scenes.map(function(s) { return s.text; }).join(' ');
    if (!transcript || transcript.length < 10) {
      if (typeof toast === 'function') toast('No transcript available — upload a video or generate a script first!', 'error');
      return null;
    }
    var payload = { transcript: transcript, topic: topic || this.state.prompt || '', platform: platform || 'youtube', language: this.state.language || 'en', target_audience: 'general' };
    var result = await this.callAgent('seo_metadata', 'SEO Metadata Agent', '/api/v1/generate-seo', payload);
    if (result) {
      this.state.seoData = result;
      this.logAgentAction('seo_metadata', 'SEO Metadata Agent',
        'Title: "' + result.title + '" | Tags: ' + (result.tags || []).length + ' | Hashtags: ' + (result.hashtags || []).length, 'g');
      if (typeof toast === 'function') toast('SEO Metadata ready for ' + result.platform + '!');
    }
    return result;
  },

  // Agent 21: Chapter Marker
  runChapterMarkerAgent: async function(minDuration) {
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('No scenes available!', 'error');
      return null;
    }
    var payload = { scenes: this.state.scenes, min_chapter_duration: minDuration || 30.0 };
    var result = await this.callAgent('chapter_marker', 'Chapter Marker Agent', '/api/v1/generate-chapters', payload);
    if (result) {
      this.state.chapters = result.chapters;
      this.logAgentAction('chapter_marker', 'Chapter Marker Agent',
        result.chapter_count + ' chapters generated. Timestamps: ' + result.chapters.map(function(c) { return c.timestamp; }).join(', '), 'g');
      if (typeof toast === 'function') toast(result.chapter_count + ' YouTube chapters generated!');
    }
    return result;
  },

  // Agent 22: Thumbnail Generator
  runThumbnailGenAgent: async function(style, colorTheme) {
    var title = (this.state.seoData && this.state.seoData.title) || this.state.prompt || 'Untitled Video';
    var hook = this.state.scenes[0] && this.state.scenes[0].text ? this.state.scenes[0].text.substring(0, 80) : '';
    var payload = { title: title, hook: hook, style: style || 'bold-text-overlay', platform: 'youtube', color_theme: colorTheme || 'dark-purple' };
    var result = await this.callAgent('thumbnail_gen', 'Thumbnail Generator Agent', '/api/v1/generate-thumbnail', payload);
    if (result) {
      this.state.thumbnailData = result;
      this.logAgentAction('thumbnail_gen', 'Thumbnail Generator Agent', 'Prompt: "' + (result.image_prompt || '').substring(0, 80) + '"', 'g');
      if (typeof toast === 'function') toast('Thumbnail design ready — copy prompt to SD/DALL-E!');
    }
    return result;
  },

  // Agent 23: Color Grading
  runColorGradingAgent: async function(mood, intensity) {
    var payload = { scenes: this.state.scenes, mood: mood || 'cinematic', intensity: intensity || 0.7 };
    var result = await this.callAgent('color_grading', 'Color Grading Agent', '/api/v1/color-grade', payload);
    if (result) {
      // Apply CSS filter to preview
      var previewEl = document.getElementById('preview-video') || document.getElementById('live-preview');
      if (previewEl) previewEl.style.cssText += result.css_filter;
      this.logAgentAction('color_grading', 'Color Grading Agent',
        'Grade: ' + result.mood + ' | ' + result.note + ' | CSS filter applied.', 'g');
      if (typeof toast === 'function') toast('Color grade applied: ' + result.mood + ' (' + Math.round(intensity * 100) + '% intensity)');
    }
    return result;
  },

  // Agent 24: Noise Reduction
  runNoiseReductionAgent: async function(profile, strength) {
    var payload = { noise_profile: profile || 'auto', strength: strength || 0.5, job_id: this.state.currentJobId || '' };
    var result = await this.callAgent('noise_reduction', 'Noise Reduction Agent', '/api/v1/reduce-noise', payload);
    if (result) {
      this.logAgentAction('noise_reduction', 'Noise Reduction Agent',
        result.profile_desc + ' | Filter: ' + result.audio_filter.substring(0, 60) + '…', 'g');
      if (typeof toast === 'function') toast('Noise Reduction: ' + result.profile_desc);
    }
    return result;
  },

  // Agent 25: B-Roll Suggestion
  runBRollSuggestionAgent: async function(style) {
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('Generate a script or upload a video first!', 'error');
      return null;
    }
    var payload = { scenes: this.state.scenes, style: style || 'cinematic' };
    var result = await this.callAgent('broll_suggestion', 'B-Roll Suggestion Agent', '/api/v1/suggest-broll', payload);
    if (result) {
      this.logAgentAction('broll_suggestion', 'B-Roll Suggestion Agent',
        result.suggestion_count + ' B-roll ideas across ' + result.scene_count + ' scenes. Style: ' + result.style, 'g');
      if (typeof toast === 'function') toast(result.suggestion_count + ' B-roll suggestions ready!');
    }
    return result;
  },

  // Agent 26: Script Optimizer
  runScriptOptimizerAgent: async function(goal, tone) {
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('Generate a script first!', 'error');
      return null;
    }
    var payload = { scenes: this.state.scenes, goal: goal || 'engagement', tone: tone || 'professional' };
    var result = await this.callAgent('script_optimizer', 'Script Optimizer Agent', '/api/v1/optimize-script', payload);
    if (result) {
      // Apply optimized text back to scenes
      if (result.updated_scenes && result.updated_scenes.length) {
        this.state.scenes = this.state.scenes.map(function(s) {
          var updated = result.updated_scenes.find(function(u) { return u.id === s.id; });
          if (updated) {
            s.text_original = updated.text_original;
            s.text = updated.text;
            s.optimization_changes = updated.optimization_changes;
          }
          return s;
        });
      }
      this.logAgentAction('script_optimizer', 'Script Optimizer Agent',
        result.scenes_optimized + ' scenes rewritten for ' + result.goal + '. Grade: ' + result.readability_grade + '. Est. improvement: ' + result.estimated_watch_time_improvement, 'g');
      if (typeof toast === 'function') toast('Script optimized for ' + result.goal + '! Watch time +' + result.estimated_watch_time_improvement);
    }
    return result;
  },

  // Agent 27: Emotion Analysis
  runEmotionAnalysisAgent: async function() {
    if (!this.state.scenes.length && !this.state.transcript) {
      if (typeof toast === 'function') toast('Generate a script or upload a video first!', 'error');
      return null;
    }
    var payload = { scenes: this.state.scenes, transcript: this.state.transcript || '' };
    var result = await this.callAgent('emotion_analysis', 'Emotion Analysis Agent', '/api/v1/analyze-emotion', payload);
    if (result) {
      // Enrich scenes with emotion data
      if (result.enriched_scenes && result.enriched_scenes.length) {
        this.state.scenes = this.state.scenes.map(function(s) {
          var enriched = result.enriched_scenes.find(function(e) { return e.id === s.id; });
          if (enriched) {
            s.emotion = enriched.emotion;
            s.energy = enriched.energy;
            s.pacing = enriched.pacing;
            s.color_grade_suggestion = enriched.color_grade_suggestion;
            s.music_mood = enriched.music_mood;
          }
          return s;
        });
      }
      this.logAgentAction('emotion_analysis', 'Emotion Analysis Agent',
        'Arc: ' + result.overall_arc + ' | Engagement: ' + result.engagement_prediction + ' | ' + result.emotions_detected + ' scenes analyzed.', 'g');
      if (typeof toast === 'function') toast('Emotion analysis: ' + result.engagement_prediction + ' engagement predicted.');
    }
    return result;
  },

  // Agent 28: Viral Clip Finder
  runViralClipAgent: async function(platform, maxDuration) {
    if (!this.state.scenes.length) {
      if (typeof toast === 'function') toast('Generate a script or upload a video first!', 'error');
      return null;
    }
    var payload = { scenes: this.state.scenes, platform: platform || 'reels', clip_duration_max: maxDuration || 60.0 };
    var result = await this.callAgent('viral_clip', 'Viral Clip Finder Agent', '/api/v1/find-viral-clip', payload);
    if (result) {
      this.logAgentAction('viral_clip', 'Viral Clip Finder Agent',
        result.clips_found + ' clips found for ' + result.platform + '. Best virality: ' + (result.viral_clips[0] && result.viral_clips[0].virality_score), 'g');
      if (typeof toast === 'function') toast(result.clips_found + ' viral clips found for ' + result.platform + '!');
    }
    return result;
  },

  // ── FULL 28-AGENT CHAIN ─────────────────────────────────────
  // Sequentially runs every agent then starts the full render pipeline.
  // Call: AgentPipeline.runFullAgentChain('Your prompt here', 60)

  runFullAgentChain: async function(userPrompt, durationSeconds) {
    var self = this;
    var prompt = userPrompt || this.state.prompt || '';
    var duration = durationSeconds || 60;

    if (!prompt || prompt.trim().length < 5) {
      if (typeof toast === 'function') toast('Please write a prompt first!', 'error');
      return;
    }

    // ── UI: show progress modal ──────────────────────────────
    self._showVideoProgressModal(prompt);
    self._updateVideoProgress(0, '🤖 Video production is starting…');

    try {
      // ── PHASE 1: Script Agent ────────────────────────────
      self._updateVideoProgress(4, '📝 Script Agent: Generating script using Qwen3…');
      self.logAgentAction('script', 'Script Agent', 'Writing script using Qwen3:8b: "' + prompt.substring(0, 40) + '…"', 'c');
      var scriptResult;
      try {
        scriptResult = await self.callAgent('script', 'Script Agent', '/api/v1/generate-script', {
          prompt: prompt, duration_seconds: duration, language: self.state.language || 'en', aspect_ratio: self.state.aspectRatio || '16:9'
        });
        if (scriptResult && scriptResult.result) self.applyScriptJob(scriptResult.result);
      } catch(e) { self.logAgentAction('script', 'Script Agent', 'Error — continuing: ' + e.message, 'y'); }

      // ── PHASE 2: Layout Planner ──────────────────────────
      self._updateVideoProgress(10, '🎨 Layout Planner: Assigning scene layouts…');
      if (self.state.scenes.length) {
        try {
          await self.runLayoutPlannerAgent('cinematic');
        } catch(e) { self.logAgentAction('layout_planner', 'Layout Planner', 'Skipped: ' + e.message, 'y'); }
      }

      // ── PHASE 3: Image Generator (prompts) ──────────────
      self._updateVideoProgress(15, '🖼️ Image Generator: Generating visual prompts for each scene…');
      for (var i = 0; i < Math.min(self.state.scenes.length, 4); i++) {
        try { await self.runImageGeneratorAgent(i); } catch(e) {}
      }

      // ── PHASE 4: Avatar Generator ────────────────────────
      self._updateVideoProgress(20, '🧑 Avatar Generator: AI presenter prompt ready…');
      try { await self.runAvatarGeneratorAgent(); } catch(e) {}

      // ── PHASE 5: SEO Metadata ────────────────────────────
      self._updateVideoProgress(24, '🔍 SEO Metadata Agent: Title, tags, description…');
      try { await self.runSEOMetadataAgent('youtube'); } catch(e) {}

      // ── PHASE 6: Viral Hook Analyzer ─────────────────────
      self._updateVideoProgress(28, '🎯 Viral Hook Agent: Scoring the opening hook…');
      try { await self.runViralHookAgent('youtube'); } catch(e) {}

      // ── PHASE 7: Emotion Analysis ────────────────────────
      self._updateVideoProgress(32, '💡 Emotion Agent: Detecting scene-wise emotions…');
      try { await self.runEmotionAnalysisAgent(); } catch(e) {}

      // ── PHASE 8: Script Optimizer ────────────────────────
      self._updateVideoProgress(36, '✍️ Script Optimizer: Rewriting for better engagement…');
      try { await self.runScriptOptimizerAgent('engagement', 'professional'); } catch(e) {}

      // ── PHASE 9: Music / Sound ───────────────────────────
      self._updateVideoProgress(40, '🎵 Music Agent: Mood-matched background music select…');
      try { await self.runMusicSoundAgent('energetic'); } catch(e) {}

      // ── PHASE 10: Color Grading ──────────────────────────
      self._updateVideoProgress(44, '🎬 Color Grading: Applying Cinematic LUT…');
      try { await self.runColorGradingAgent('cinematic', 0.7); } catch(e) {}

      // ── PHASE 11: B-Roll Suggestions ─────────────────────
      self._updateVideoProgress(47, '📹 B-Roll Agent: Contextual footage suggestions…');
      try { await self.runBRollSuggestionAgent('cinematic'); } catch(e) {}

      // ── PHASE 12: Chapter Markers ────────────────────────
      self._updateVideoProgress(50, '📌 Chapter Marker: YouTube timestamps generate…');
      try { await self.runChapterMarkerAgent(20); } catch(e) {}

      // ── PHASE 13: Thumbnail Generator ───────────────────
      self._updateVideoProgress(53, '🖼️ Thumbnail Agent: Viral thumbnail prompt ready…');
      try { await self.runThumbnailGenAgent('bold-text-overlay', 'dark-purple'); } catch(e) {}

      // ── PHASE 14: Brand Kit ──────────────────────────────
      self._updateVideoProgress(56, '🏷️ Brand Kit: Applying logo + watermark…');
      try { await self.runBrandKitAgent(); } catch(e) {}

      // ── PHASE 15: Noise Reduction (command ready) ────────
      self._updateVideoProgress(59, '🔇 Noise Reduction: FFmpeg audio cleanup command…');
      try { await self.runNoiseReductionAgent('auto', 0.5); } catch(e) {}

      // ── PHASE 16: Export Optimizer command ──────────────
      self._updateVideoProgress(62, '📦 Export Optimizer: Platform-optimized encode preset…');
      try { await self.runExportOptimizerAgent('16:9', '1080p', 'h264'); } catch(e) {}

      // ── PHASE 17: START ACTUAL VIDEO RENDER PIPELINE ────
      self._updateVideoProgress(65, '🎥 Compositor: Starting cinema-grade render pipeline…');
      self.logAgentAction('compositor', 'Compositor Agent', 'Sending ' + self.state.scenes.length + ' scenes to FFmpeg pipeline → Flux images → gTTS audio → 1080p MP4', 'c');

      var apiBase = (window.SmartEditBackend && window.SmartEditBackend.apiBase) || 'http://127.0.0.1:8000';

      // Normalize scenes: map frontend format (s/e, vis.query) → backend format
      var normalizedScenes = self.state.scenes.map(function(sc) {
        return {
          id:            sc.id,
          start:         sc.s  !== undefined ? sc.s  : (sc.start  || 0),
          end:           sc.e  !== undefined ? sc.e  : (sc.end    || 8),
          text:          sc.text || '',
          visual_prompt: sc.vis && sc.vis.query ? sc.vis.query : (sc.visual_prompt || sc.text || ''),
          layout:        sc.layout || 'full-presenter',
          notes:         sc.notes  || ''
        };
      });

      var renderResp = await fetch(apiBase + '/api/v1/re-render-video', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenes:           normalizedScenes,
          duration_seconds: duration,
          language:         self.state.language || 'en',
          aspect_ratio:     self.state.aspectRatio || '16:9',
          image_style:      'cinematic photorealistic, professional lighting, ultra detailed, film grain, 8K',
          avatar_style:     self.state.avatarStyle || 'none',
          enable_lipsync:   self.state.enableLipsync || false
        })
      });

      if (!renderResp.ok) {
        var errText = await renderResp.text();
        throw new Error('Render API error: ' + errText);
      }

      var renderJob = await renderResp.json();
      var jobId = renderJob.job_id;
      self.state.currentJobId = jobId;
      self.logAgentAction('compositor', 'Compositor Agent', 'Job ' + jobId + ' queued — polling status…', 'g');

      // ── PHASE 18: Poll until done ────────────────────────
      await self._pollRenderJob(jobId, apiBase);

    } catch(err) {
      self.logAgentAction('pipeline', 'Full Pipeline', 'Pipeline failed: ' + (err && err.message ? err.message : String(err)), 'r');
      self._updateVideoProgress(0, '❌ Error: ' + (err && err.message ? err.message : 'Unknown error'), true);
      if (typeof toast === 'function') toast('Pipeline error: ' + (err && err.message ? err.message : 'Unknown'), 'error');
    }
  },

  // ── Polling helper ──────────────────────────────────────────
  _pollRenderJob: async function(jobId, apiBase) {
    var self = this;
    var maxWait = 600000; // 10 minutes max
    var startTime = Date.now();
    var pollInterval = 3000; // poll every 3s

    return new Promise(function(resolve, reject) {
      var timer = setInterval(async function() {
        if (Date.now() - startTime > maxWait) {
          clearInterval(timer);
          reject(new Error('Video render timeout (10 min). FFmpeg or Colab is slow.'));
          return;
        }
        try {
          var statusResp = await fetch(apiBase + '/api/v1/job-status/' + jobId);
          if (!statusResp.ok) return;
          var job = await statusResp.json();
          var pct = 65 + Math.round((job.progress || 0) * 0.35); // 65% → 100%
          var msg = job.message || 'Processing…';
          self._updateVideoProgress(pct, '⚙️ ' + msg);
          self.logAgentAction('compositor', 'Compositor Agent', msg + ' (' + (job.progress || 0) + '%)', 'c');

          if (job.status === 'completed') {
            clearInterval(timer);
            var downloadUrl = (job.result && job.result.download_url) ? job.result.download_url : null;
            var sceneCount = (job.result && job.result.scene_count) ? job.result.scene_count : '?';
            self._updateVideoProgress(100, '✅ Video ready! ' + sceneCount + ' scenes render hua!', false, apiBase + (downloadUrl || ''));
            self.logAgentAction('compositor', 'Compositor Agent', '🎉 Final MP4 ready! Download: ' + downloadUrl, 'g');
            if (typeof toast === 'function') toast('🎉 Video ready! ' + sceneCount + ' scenes rendered!');
            resolve(job);
          } else if (job.status === 'failed') {
            clearInterval(timer);
            reject(new Error(job.error || job.message || 'Render failed'));
          }
        } catch(e) { /* network hiccup — keep polling */ }
      }, pollInterval);
    });
  },

  // ── Progress Modal helpers ──────────────────────────────────
  _showVideoProgressModal: function(prompt) {
    var existing = document.getElementById('se-video-progress-modal');
    if (existing) existing.remove();

    var modal = document.createElement('div');
    modal.id = 'se-video-progress-modal';
    modal.style.cssText = [
      'position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;',
      'background:rgba(0,0,0,0.82);backdrop-filter:blur(12px);'
    ].join('');

    modal.innerHTML = [
      '<div style="background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);border:1px solid rgba(139,92,246,0.4);',
      'border-radius:20px;padding:40px;max-width:560px;width:90%;box-shadow:0 0 60px rgba(139,92,246,0.3);position:relative;">',

      '<div style="position:absolute;top:14px;right:16px;cursor:pointer;font-size:20px;color:rgba(255,255,255,0.5);" ',
      'onclick="document.getElementById(\'se-video-progress-modal\').remove()">✕</div>',

      '<div style="text-align:center;margin-bottom:24px;">',
      '<div style="font-size:36px;margin-bottom:8px;">🎬</div>',
      '<h2 style="margin:0;color:#fff;font-size:20px;font-weight:700;">Video production</h2>',
      '<p style="color:rgba(255,255,255,0.5);font-size:13px;margin:6px 0 0;">',
      '"' + (prompt || '').substring(0, 60) + (prompt && prompt.length > 60 ? '…' : '') + '"</p>',
      '</div>',

      '<div style="background:rgba(0,0,0,0.3);border-radius:10px;height:12px;overflow:hidden;margin-bottom:12px;">',
      '<div id="se-vp-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#8B5CF6,#06B6D4);',
      'transition:width 0.6s ease;border-radius:10px;box-shadow:0 0 12px #8B5CF6;"></div>',
      '</div>',

      '<div style="display:flex;justify-content:space-between;margin-bottom:20px;">',
      '<span id="se-vp-msg" style="color:#A78BFA;font-size:13px;font-weight:600;">Starting…</span>',
      '<span id="se-vp-pct" style="color:#06B6D4;font-size:13px;font-weight:700;">0%</span>',
      '</div>',

      '<div id="se-vp-steps" style="display:flex;flex-direction:column;gap:6px;max-height:180px;overflow-y:auto;',
      'background:rgba(0,0,0,0.2);border-radius:10px;padding:12px;">',
      '<div style="color:rgba(255,255,255,0.35);font-size:11px;text-align:center;">Agent logs will appear here…</div>',
      '</div>',

      '<div id="se-vp-download" style="display:none;margin-top:20px;text-align:center;">',
      '<div style="display:flex;gap:12px;justify-content:center;align-items:center;">',
      '<a id="se-vp-dl-link" href="#" target="_blank" style="',
      'display:inline-block;padding:12px 32px;background:linear-gradient(135deg,#8B5CF6,#06B6D4);',
      'color:#fff;border-radius:10px;font-weight:700;text-decoration:none;font-size:15px;',
      'box-shadow:0 4px 20px rgba(139,92,246,0.5);transition:transform 0.2s;" ',
      'onmouseover="this.style.transform=\'scale(1.05)\'" onmouseout="this.style.transform=\'\'">',
      '⬇️ Download Video</a>',
      '<button id="se-vp-proj-btn" onclick="openVideoInProjector()" style="',
      'display:inline-block;padding:12px 32px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);',
      'color:#fff;border-radius:10px;font-weight:700;cursor:pointer;font-size:15px;transition:background 0.2s;" ',
      'onmouseover="this.style.background=\'rgba(255,255,255,0.2)\'" onmouseout="this.style.background=\'rgba(255,255,255,0.1)\'">',
      '📽️ AI Video Projector</button>',
      '</div>',
      '</div>',

      '</div>'
    ].join('');

    document.body.appendChild(modal);
  },

  _updateVideoProgress: function(pct, msg, isError, downloadUrl) {
    var bar = document.getElementById('se-vp-bar');
    var msgEl = document.getElementById('se-vp-msg');
    var pctEl = document.getElementById('se-vp-pct');
    var stepsEl = document.getElementById('se-vp-steps');
    var dlDiv = document.getElementById('se-vp-download');
    var dlLink = document.getElementById('se-vp-dl-link');

    if (bar) {
      bar.style.width = pct + '%';
      if (isError) bar.style.background = 'linear-gradient(90deg,#EF4444,#F97316)';
    }
    if (msgEl) {
      msgEl.textContent = msg || '';
      msgEl.style.color = isError ? '#EF4444' : '#A78BFA';
    }
    if (pctEl) pctEl.textContent = pct + '%';
    if (stepsEl) {
      var entry = document.createElement('div');
      entry.style.cssText = 'font-size:11px;color:rgba(255,255,255,0.65);padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.05);';
      entry.textContent = '[' + new Date().toLocaleTimeString() + '] ' + (msg || '');
      stepsEl.prepend(entry);
    }
    if (downloadUrl && dlDiv && dlLink) {
      dlLink.href = downloadUrl;
      dlDiv.style.display = 'block';
    }
  }
};

// Make runNLEditAgent accessible globally for HTML onclick
window.handleNLCommand = function(inputElId) {
  AgentPipeline.runNLEditAgent(inputElId);
};

// Global trigger — call from anywhere: generateFullVideo('My prompt', 60)
window.generateFullVideo = function(prompt, duration) {
  if (window.AgentPipeline) {
    window.AgentPipeline.runFullAgentChain(prompt, duration || 60);
  }
};

window.openVideoInProjector = function() {
  var dlLink = document.getElementById('se-vp-dl-link');
  if (dlLink && dlLink.href) {
    var modal = document.getElementById('se-video-progress-modal');
    if (modal) modal.remove();
    if (typeof goTo === 'function') goTo('editor');
    if (typeof loadRealVideo === 'function') loadRealVideo(dlLink.href);
  }
};
