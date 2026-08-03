# 🎬 MASTER ARCHITECTURE & REPORT: AI Agentic Video Generator (100% Local, No API Key)

> **Project Name:** SmartEdit AI — Automated Video Production Studio  
> **Execution Mode:** 100% Offline / Local Execution (Zero API Costs, Privacy Safe)  
> **Core Engine:** CrewAI / LangGraph + Ollama Llama-3 (8B) + Local GPU Inference Models  

---

## 📌 Executive Summary

SmartEdit AI is an autonomous, multi-agent video production studio designed to convert natural language prompts or raw video inputs into fully-rendered 4K cinematic videos in under 60 seconds without reliance on external cloud APIs.

The system features **16 Specialized Autonomous AI Agents** organized into **10 Core Pipeline Agents** and **6 Bonus Feature Agents**.

---

## 🤖 SECTION A: Core Pipeline Agents (10)

| # | Agent Name | Primary Responsibility | Input Data | Output Data | Tooling & Model Stack |
|---|---|---|---|---|---|
| **1** | **Orchestrator Agent** | Task DAG delegation, state management, and error recovery across all 16 agents | User Request / Video Prompt | Agent Execution Sequence (DAG) | CrewAI / LangGraph + Ollama Llama-3 (Local) |
| **2** | **Script Agent** | Generates scene-by-scene script with verbal hooks, emotional arc & tone | Prompt + Target Tone + Duration | Scene-wise Script JSON | Ollama (Llama-3 8B / Mistral 7B) |
| **3** | **Layout Planner Agent** | Decides scene layout (Full Presenter / Split-Screen / PiP / Slide / Dual) | Script Text & Sentiment | Layout Metadata Tags | Ollama Visual Reasoning Engine |
| **4** | **Slide Generator Agent** | Generates bullet points, titles, and graphic prompts for slide scenes | Script Portion | Slide Content JSON | Ollama + Canvas Engine |
| **5** | **Image Generator Agent** | Renders 4K background art, slide graphics & B-roll visual assets | Image Prompts | High-Res PNG/JPG Images | Stable Diffusion XL (Local GPU) |
| **6** | **Avatar Generator Agent** | Synthesizes photorealistic custom AI presenter models | Demographic & Style Preference | Avatar Portrait Models | Stable Diffusion Portrait Checkpoints |
| **7** | **Voice Agent** | Performs natural voice synthesis and zero-shot voice cloning | Script + Voice Sample | 44.1kHz Audio WAV Stream | Coqui XTTS-v2 / Chatterbox TTS |
| **8** | **Lip-Sync Agent** | Synchronizes AI avatar mouth motion with synthesized audio frames | Avatar Model + Voice WAV | Talking Avatar Video | MuseTalk / Wav2Lip (CUDA Local) |
| **9** | **Caption Agent** | Generates word-level timestamped subtitles & animated text overlays | Audio Stream | SRT / VTT / Animated Overlay | OpenAI Whisper Medium/Large (Local) |
| **10** | **Compositor Agent** | Merges avatar, slides, B-roll, captions & audio tracks into a 60fps video | All Media Assets + Layout Specs | Master 4K Video Stream | FFmpeg CUDA + Remotion Player |

---

## 🌟 SECTION B: Bonus Feature Agents (6)

| # | Agent Name | Primary Responsibility | Tooling & Model Stack |
|---|---|---|---|
| **11** | **Multi-Language Agent** | Translates script into 23+ languages & synthesizes native voice dubbing | Ollama Translation + Chatterbox TTS |
| **12** | **Brand Kit Agent** | Automatically overlays company logo, hex color palettes, fonts & watermark | Simple Canvas & Template Engine |
| **13** | **Conversation Mode Agent** | Splits script into dual-speaker dialogue for podcast/interview split-screen | Ollama Dialogue Splitter + Dual MuseTalk |
| **14** | **Natural Language Edit Agent** | Parses plain text user edits ("Make background dark blue") & re-renders target scene diff | Ollama Intent Parser + Compositor Recall |
| **15** | **Music/Sound Agent** | Selects mood-matching background audio & applies speech-activated volume ducking | Local Royalty-Free Audio + FFmpeg Ducking |
| **16** | **Export Optimizer Agent** | Auto-crops & reframes for YouTube (16:9), Instagram Reels/Shorts (9:16) & LinkedIn (1:1) | FFmpeg Hardware Encoder Presets |

---

## ⚡ SECTION C: Complete End-to-End Data Flow

```
STEP 1: User Input
   ├── Prompt Entry OR Video Upload
   └── Parameters: Language, Tone, Target Platform (YouTube 16:9 / Reels 9:16 / LinkedIn 1:1)

STEP 2: Orchestrator Agent Initialization
   └── LangGraph builds multi-agent execution graph (DAG) via Ollama

STEP 3: Content Creation Phase
   Script Agent ──► Layout Planner Agent ──► Slide Generator Agent ──► Image Generator Agent (SD XL)

STEP 4: Audio-Visual Synthesis Phase
   Avatar Generator Agent ──► Voice Agent (Coqui XTTS) ──► Lip-Sync Agent (MuseTalk CUDA)

STEP 5: Production Enhancement Phase
   Multi-Language Agent ──► Music/Sound Agent (Ducking) ──► Caption Agent (Whisper Subtitles)

STEP 6: Timeline Assembly Phase
   Compositor Agent ──► Assembles multi-track 60fps video
   Brand Kit Agent  ──► Overlays branding logo, hex theme & font guidelines

STEP 7: Interactive Editor Screen & NL Edit Loop
   ├── User previews live Remotion timeline
   └── Natural Language Edit Agent receives user command ("Change background to blue")
       └── Performs fast incremental re-render of target scene ONLY (Cached pipeline)

STEP 8: Platform Export
   Export Optimizer Agent ──► Encodes 4K 60fps renders tailored for YouTube, Reels & LinkedIn
```

---

## 🏛️ SECTION D: 3-Layer Software Architecture

```
+-----------------------------------------------------------------------+
|                       1. FRONTEND LAYER (UI)                          |
|   React.js + Remotion Player (Live Timeline & Multi-Track Preview)     |
|   Natural Language Edit Console + Aspect Ratio Presets (16:9, 9:16, 1:1)  |
+-----------------------------------------------------------------------+
                                   │ REST API / WebSockets
                                   ▼
+-----------------------------------------------------------------------+
|                    2. BACKEND LAYER (ORCHESTRATION)                   |
|   Python FastAPI (REST Gateway)                                       |
|   Celery + Redis Task Queue (Async Background Execution)              |
|   CrewAI / LangGraph Orchestrator (Multi-Agent State Graph)           |
+-----------------------------------------------------------------------+
                                   │ Local Calls
                                   ▼
+-----------------------------------------------------------------------+
|                     3. AI / ML LAYER (LOCAL GPU)                      |
|   LLM Engine    : Ollama (Llama-3 8B / Mistral 7B)                     |
|   Image Engine  : Stable Diffusion XL (Local CUDA)                    |
|   Voice Engine  : Coqui XTTS-v2 / Chatterbox TTS                      |
|   Lip-Sync      : MuseTalk / Wav2Lip CUDA                             |
|   Subtitles     : OpenAI Whisper (Local Model)                        |
|   Compositor    : FFmpeg CUDA Accelerated                               |
+-----------------------------------------------------------------------+
```

---

## 🗓️ SECTION E: Implementation Roadmap

| Phase | Core Objective | Duration | Key Deliverable |
|---|---|---|---|
| **Phase 1** | Local LLM & Scripting Agent Setup | 1-2 Weeks | Ollama integration & scene JSON script parser |
| **Phase 2** | Voice Agent Synthesis & Audio Ducking | 1-2 Weeks | Coqui XTTS-v2 WAV generation & FFmpeg ducking |
| **Phase 3** | Avatar & Lip-Sync Pipeline | 3-4 Weeks | SD Avatar generation + MuseTalk CUDA lip-sync |
| **Phase 4** | Caption & Compositor Engine | 1-2 Weeks | Whisper SRT alignment & FFmpeg timeline render |
| **Phase 5** | Layout Planner & Visual Generation | 2 Weeks | Layout tags (Full/Split/PiP) & SD XL image synthesis |
| **Phase 6** | LangGraph Orchestrator Integration | 2 Weeks | Complete multi-agent pipeline DAG execution |
| **Phase 7** | React + Remotion Editor Frontend | 2-3 Weeks | Interactive preview, timeline & NL edit bar |
| **Phase 8** | Bonus Agents Integration | 2-3 Weeks | Multi-language, Brand Kit, Conversation Mode & Export Presets |
| **Phase 9** | Testing & Optimization | 1-2 Weeks | Incremental scene re-render caching & bug fixes |

*Total Estimated Development Timeline: 4 - 5 Months (Team of 2-3 Developers)*

---

## 💻 SECTION F: Hardware Requirements

- **Minimum Specification (Basic Testing):**
  - GPU: NVIDIA RTX 3060 / 3070 (8GB VRAM)
  - RAM: 16GB System Memory
  - Storage: 50GB SSD space (for SD XL, Whisper & LLM weights)
- **Recommended Specification (Production Ready):**
  - GPU: NVIDIA RTX 4070 / 4080 / 4090 (12GB - 24GB VRAM)
  - RAM: 32GB System Memory
  - Storage: 100GB NVMe M.2 SSD

---

## 🎤 SECTION G: Key Talking Points for Presentation / Defense

1. **True Agentic Architecture:** "System is powered by 16 autonomous AI agents working in a structured DAG directed by LangGraph."
2. **100% Offline & Cost-Free:** "Zero dependency on OpenAI or cloud APIs. Runs entirely on local Ollama, Stable Diffusion & MuseTalk models."
3. **Autonomous Layout Reasoning:** "The Layout Planner Agent uses semantic reasoning to automatically select optimal scene layouts (Full, Split, PiP, Slides, Conversation)."
4. **Natural Language Editing:** "Users can edit specific scenes using plain Hindi/English prompts without re-rendering the entire video."
5. **Multi-Format Export Optimization:** "Instant multi-platform renders for YouTube (16:9), Instagram Reels (9:16), and LinkedIn (1:1)."
