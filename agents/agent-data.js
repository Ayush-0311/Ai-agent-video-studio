/**
 * agents/agent-data.js
 * ─────────────────────────────────────────────────────────────
 * 100% Local AI Agentic Video Generator - Data Architecture
 * 
 * 16 Autonomous Agents (10 Core Pipeline + 6 Bonus Feature Agents):
 *   1. Orchestrator Agent (CrewAI/LangGraph + Ollama)
 *   2. Script Agent (Ollama Llama3/Mistral)
 *   3. Layout Planner Agent (Ollama prompt-based layout reasoning)
 *   4. Slide Generator Agent (Ollama JSON structure)
 *   5. Image Generator Agent (Stable Diffusion local)
 *   6. Avatar Generator Agent (Stable Diffusion local)
 *   7. Voice Agent (Coqui XTTS-v2 / Chatterbox TTS)
 *   8. Lip-Sync Agent (MuseTalk / Wav2Lip)
 *   9. Caption Agent (Whisper local)
 *  10. Compositor Agent (FFmpeg / Remotion)
 *  11. Multi-Language Agent (Ollama Translation + Chatterbox TTS)
 *  12. Brand Kit Agent (Logo, Color Palette, Custom Typography)
 *  13. Conversation Mode Agent (Dual Dialogue + Dual MuseTalk Lip-Sync)
 *  14. Natural Language Edit Agent (Intent Parsing & Incremental Render)
 *  15. Music/Sound Agent (Royalty-free Local Audio + FFmpeg Auto-Ducking)
 *  16. Export Optimizer Agent (YouTube 16:9, Reels 9:16, LinkedIn 1:1 Presets)
 */

const AGENTS_LIST = [
  // SECTION A: CORE PIPELINE AGENTS (10)
  {
    id: "orchestrator",
    name: "Orchestrator Agent",
    type: "core",
    badge: "CREWAI / LANGGRAPH",
    desc: "Sare agents ko sequence me chalana, task delegation, error recovery & state sync.",
    input: "User Request / Video Prompt",
    output: "Execution Graph & Task DAG",
    tool: "LangGraph + Ollama Llama-3 (Local)",
    status: "active",
    uptime: "99.9%"
  },
  {
    id: "script",
    name: "Script Agent",
    type: "core",
    badge: "OLLAMA LLAMA-3",
    desc: "Topic/prompt se scene-wise script structure, tone control aur verbal hooks banana.",
    input: "Prompt + Target Tone + Duration",
    output: "Scene-by-scene script JSON",
    tool: "Ollama (Llama-3 / Mistral 7B)",
    status: "active",
    uptime: "100%"
  },
  {
    id: "layout_planner",
    name: "Layout Planner Agent",
    type: "core",
    badge: "SEMANTIC REASONING",
    desc: "Har scene ke visual impact ke hisaab se layout choose karna (Full/Split/PiP/Slide/Dual).",
    input: "Script Text & Sentiment",
    output: "Scene Layout Metadata Tag",
    tool: "Ollama Visual Reasoning Engine",
    status: "active",
    uptime: "99.8%"
  },
  {
    id: "slide_generator",
    name: "Slide Generator Agent",
    type: "core",
    badge: "JSON TEMPLATE ENGINE",
    desc: "Slide mode wale scenes ke liye catchy title, bullet points aur graphic prompts banana.",
    input: "Script Scene Segment",
    output: "Slide Content Data (JSON)",
    tool: "Ollama + Local Canvas Engine",
    status: "active",
    uptime: "99.7%"
  },
  {
    id: "image_generator",
    name: "Image Generator Agent",
    type: "core",
    badge: "STABLE DIFFUSION XL",
    desc: "Slides, split-screen aur B-roll ke liye high-res contextual AI images generate karna.",
    input: "Image Prompt & Art Style",
    output: "PNG / JPG 4K Visual Assets",
    tool: "Stable Diffusion XL (Local GPU)",
    status: "active",
    uptime: "98.9%"
  },
  {
    id: "avatar_generator",
    name: "Avatar Generator Agent",
    type: "core",
    badge: "SD-AVATAR PIPELINE",
    desc: "Custom photorealistic AI avatars/presenters generate karna bina external API key ke.",
    input: "Avatar Style / Demographic Preference",
    output: "High-Res Avatar Model Frame",
    tool: "Stable Diffusion Portrait Model",
    status: "active",
    uptime: "99.2%"
  },
  {
    id: "voice",
    name: "Voice Agent",
    type: "core",
    badge: "COQUI XTTS-V2",
    desc: "Script ko crystal-clear human-like voice synthesis me convert karna & voice cloning.",
    input: "Script Text + Voice Sample",
    output: "High Quality WAV Audio Stream",
    tool: "Coqui XTTS-v2 / Chatterbox TTS",
    status: "active",
    uptime: "99.6%"
  },
  {
    id: "lip_sync",
    name: "Lip-Sync Agent",
    type: "core",
    badge: "MUSETALK / WAV2LIP",
    desc: "AI Avatar ke mouth movements ko synthesized voice audio ke sath frame-perfect sync karna.",
    input: "Avatar Image + Voice WAV",
    output: "Talking Avatar Video Segment",
    tool: "MuseTalk / Wav2Lip (CUDA Local)",
    status: "active",
    uptime: "97.8%"
  },
  {
    id: "caption",
    name: "Caption Agent",
    type: "core",
    badge: "OPENAI WHISPER LOCAL",
    desc: "Word-level timestamped subtitle generation, auto-punctuate aur animated overlay burning.",
    input: "Audio Stream WAV",
    output: "SRT / VTT / Animated Subtitle Data",
    tool: "Whisper Medium/Large (Local)",
    status: "active",
    uptime: "99.9%"
  },
  {
    id: "compositor",
    name: "Compositor Agent",
    type: "core",
    badge: "FFMPEG + REMOTION",
    desc: "Avatar, slides, B-roll, captions aur background music ko single 60fps timeline me assemble karna.",
    input: "All Media Assets + Layout Specs",
    output: "Unified Master Video Render",
    tool: "FFmpeg CUDA + Remotion (Local)",
    status: "active",
    uptime: "99.5%"
  },

  // SECTION B: BONUS FEATURE AGENTS (6)
  {
    id: "multi_language",
    name: "Multi-Language Agent",
    type: "bonus",
    badge: "23+ LANGUAGES",
    desc: "Script ko Hindi, Spanish, French etc. me translate karna aur matching TTS native voice dubbing.",
    input: "Target Language Code",
    output: "Translated Script & Native Dub WAV",
    tool: "Ollama Translation + Chatterbox TTS",
    status: "active",
    uptime: "99.4%"
  },
  {
    id: "brand_kit",
    name: "Brand Kit Agent",
    type: "bonus",
    badge: "AUTO-BRANDING",
    desc: "User ka custom logo, color hex codes, font family aur watermark har scene me enforce karna.",
    input: "Brand Assets & Guidelines JSON",
    output: "Branded Overlay Layers",
    tool: "Template Branding Engine",
    status: "active",
    uptime: "100%"
  },
  {
    id: "conversation_mode",
    name: "Conversation Mode Agent",
    type: "bonus",
    badge: "DUAL AVATAR SYNC",
    desc: "Single script ko podcast/interview style me 2 characters ke dialogue me split karke dual lip-sync karna.",
    input: "Multi-speaker Script",
    output: "Dual-talking Avatar Split Screen",
    tool: "Ollama Splitter + Dual MuseTalk",
    status: "active",
    uptime: "98.2%"
  },
  {
    id: "nl_edit",
    name: "Natural Language Edit Agent",
    type: "bonus",
    badge: "NL COMMAND PARSER",
    desc: "User ke plain prompt ('Avatar background blue karo') se target scene recall karke instant re-render karna.",
    input: "Natural Language Edit Prompt",
    output: "Targeted Scene Diff Update",
    tool: "Ollama Intent Parser + Compositor Recall",
    status: "active",
    uptime: "99.1%"
  },
  {
    id: "music_sound",
    name: "Music / Sound Agent",
    type: "bonus",
    badge: "AUTO DUCKING",
    desc: "Content sentiment ke hisaab se background music pick karna & speech aate hi automatic volume ducking.",
    input: "Scene Sentiment & Audio Track",
    output: "Balanced Stereo Mix Track",
    tool: "Local Royalty-free Library + FFmpeg",
    status: "active",
    uptime: "99.7%"
  },
  {
    id: "export_optimizer",
    name: "Export Optimizer Agent",
    type: "bonus",
    badge: "MULTI-PLATFORM RATIO",
    desc: "YouTube (16:9), Instagram Reels/Shorts (9:16), LinkedIn (1:1) ke liye auto-crop, reframing & render optimization.",
    input: "Master Render + Target Preset",
    output: "Platform Optimized MP4 / WebM",
    tool: "FFmpeg Hardware Encoder Presets",
    status: "active",
    uptime: "100%"
  }
];

const TRANSCRIPT = [];

const PIPELINE_STEPS = [
  {label: "1. Orchestrator Initialization", detail: "LangGraph pipeline execution DAG created (Ollama Llama-3)"},
  {label: "2. Script Agent Narration",      detail: "Scene-wise dialogue, emotional tone & verbal hooks crafted"},
  {label: "3. Layout Planner Structuring",   detail: "Determining Full Presenter / Split / PiP / Slide per scene"},
  {label: "4. Slide Generator Formatting",  detail: "Structuring JSON bullet points, titles & visual prompts"},
  {label: "5. Image Generator Synthesis",   detail: "Stable Diffusion XL rendering 4K background & slide assets"},
  {label: "6. Avatar Generator Setup",       detail: "Local SD Portrait model rendering photorealistic presenter"},
  {label: "7. Voice Agent Audio Synthesis", detail: "Coqui XTTS-v2 generating 44.1kHz WAV voice stream"},
  {label: "8. Lip-Sync Agent Alignment",     detail: "MuseTalk CUDA aligning mouth motion to audio frames"},
  {label: "9. Caption Agent Subtitles",     detail: "Whisper Medium generating word-level animated subtitles"},
  {label: "10. Multi-Language Dubbing",     detail: "Chatterbox translating & dubbing target language tracks"},
  {label: "11. Brand Kit Layering",         detail: "Applying logo, brand colors, font themes & watermark"},
  {label: "12. Conversation Mode Check",    detail: "Dual-speaker layout composition for podcast scenes"},
  {label: "13. Music & Sound Mixing",       detail: "Local audio selection + FFmpeg speech-activated ducking"},
  {label: "14. Compositor Assembly",        detail: "FFmpeg CUDA compositing 4K 60fps multi-track timeline"},
  {label: "15. NL Edit Verification",       detail: "Checking scene diff cache for fast incremental re-renders"},
  {label: "16. Export Optimizer Render",    detail: "Encoding YouTube 16:9, Reels 9:16 & LinkedIn 1:1 renders"}
];

const ARCH_NODES = [
  {label: "Frontend Layer (React + Remotion)",   sub: "Live Preview Player, Multi-Track Timeline, NL Edit Console", color: "#8B5CF6"},
  {label: "FastAPI + Celery Task Queue",         sub: "Async REST APIs, Redis Background Worker Dispatcher",         color: "#3B82F6"},
  {label: "CrewAI / LangGraph Orchestrator",     sub: "Multi-Agent DAG execution engine & state manager",           color: "#06B6D4"},
  {label: "Ollama Local LLM Engine",            sub: "Llama-3 8B / Mistral 7B (Zero API Key, 100% Offline)",        color: "#10B981"},
  {label: "Stable Diffusion XL (Local GPU)",     sub: "Background, Slide & Custom Photorealistic Avatar Generation", color: "#F59E0B"},
  {label: "Coqui XTTS-v2 & Whisper Speech",     sub: "Natural Voice Synthesis, Voice Cloning & Word Timestamps",   color: "#EF4444"},
  {label: "MuseTalk / Wav2Lip CUDA Sync",        sub: "Frame-accurate real-time Talking Avatar Lip-Sync",           color: "#8B5CF6"},
  {label: "FFmpeg Hardware Accelerated Render", sub: "Multi-ratio H.265 export (16:9, 9:16, 1:1) @ 4K 60fps",       color: "#06B6D4"}
];

const LIB_ASSETS = [
  {l: "Futuristic Studio Avatar", c: "rgba(139,92,246,.2)", t: "#AVATAR",  src: "Stable Diffusion", cat: "ai"},
  {l: "Neural Network Nodes",    c: "rgba(6,182,212,.2)",  t: "#NEURAL",  src: "Stable Diffusion", cat: "ai"},
  {l: "Podcast Dual Studio",     c: "rgba(59,130,246,.2)", t: "#PODCAST", src: "Local Template",   cat: "illustration"},
  {l: "AI Analytics Chart",      c: "rgba(16,185,129,.2)", t: "#CHART",   src: "Slide Generator",  cat: "diagram"},
  {l: "Abstract Geometry",       c: "rgba(245,158,11,.2)", t: "#SLIDE",   src: "Stable Diffusion", cat: "ai"},
  {l: "Presenter Dark Stage",    c: "rgba(139,92,246,.25)",t: "#STAGE",   src: "Stable Diffusion", cat: "photo"},
  {l: "Tech Infographic Slide",  c: "rgba(6,182,212,.25)", t: "#TECH",    src: "Slide Generator",  cat: "diagram"},
  {l: "Cyberpunk City B-Roll",   c: "rgba(239,68,68,.2)",  t: "#BROLL",   src: "Local Asset Lib",  cat: "video"},
  {l: "Space Concept Slide",     c: "rgba(59,130,246,.25)",t: "#SLIDE",   src: "Stable Diffusion", cat: "ai"},
  {l: "Growth Metrics Bar",      c: "rgba(16,185,129,.25)",t: "#CHART",   src: "Slide Generator",  cat: "chart"},
  {l: "Conversation Dual Split", c: "rgba(245,158,11,.25)",t: "#DUAL",    src: "Conversation Mode",cat: "photo"},
  {l: "Minimal Dark UI",         c: "rgba(139,92,246,.3)", t: "#MINIMAL", src: "Brand Kit Agent",  cat: "ai"}
];
