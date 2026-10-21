# SmartEdit production agents

Agents coordinate model/tool calls; Ollama runs the language model they use. Role prompts and validators are not model training. No fine-tuning or new model weights were created by this update.

Both **Plan scenes** and **Generate video** now execute the production writing/direction workflow in `backend/studio.py` and `backend/production_agents.py`. Legacy browser prompts are not the authority for this pipeline.

| Stage | Actual work | Implementation |
|---|---|---|
| Orchestrator | Applies mode, language, duration and scene-splitting settings; runs stages sequentially | Backend workflow |
| Video brief | Interprets subject, audience, tone, requested examples, exclusions and visual approach | Validated Ollama call; one repair before falling back to the original prompt |
| Topic references | Looks up factual topics when Online references is enabled; retries a broader topic only for empty results | Wikipedia introductory extracts, up to two queries and two sources; ambiguous index pages excluded |
| Script writer | Drafts connected narration/caption text and scene-specific visual ideas for the brief and selected duration | Ollama call with settings and available references; three total structural attempts |
| Shot director | Refines camera framing, action, setting, composition and light | Separate Ollama model call |
| Continuity check | Resolves shared character descriptions and adds them only to matching shots | Validated character keys and deterministic prompt assembly |
| Storyboard QA | Checks IDs/count, rejects missing/duplicate references, preserves narration/order/timing | Code validation; one director repair attempt on invalid JSON/schema |
| Narration–visual review | Compares each spoken idea/example to its image prompt, repairs mismatches once and rechecks | Language-model prompt review; does not inspect generated pixels |
| Visual generation | Creates moving shots or still images as selected | Connected Wan or image model through Colab |
| Narration/captions | Synthesizes speech when enabled; creates subtitle files and overlays separately | Speech service and timed captions |
| Measured duration fitting | Expands short automatic scripts or shortens long ones before generating visuals; preserves intent and updates supporting imagery | Up to three measured rewrites; exact frame allocation, short pauses and motion-shot limits |
| Compositor/export | Fits the frame, applies edits, mixes audio and encodes MP4 | Local FFmpeg, followed by FFprobe validation |

The director cannot change narration, timings, scene IDs or their order. A failed director check does not overwrite the saved project or silently skip the stage. Cancellation is checked between model calls. Healthy automatic narrated planning normally uses four language-model calls: brief analyst, writer, director and narration–visual reviewer. Finished scripts skip the analyst. A reviewer can repair mismatched prompts and check them once more; invalid director output also permits one repair. Measured-duration fitting may require up to three narration revisions. Additional calls increase latency on free Colab and run sequentially.

The analyst, writer, director, visual reviewer, narration revisions and optional specialists share selected settings. These include language, duration, framing, style, narration/caption switches, motion preset and presenter options. Hybrid explicitly means one moving opening shot followed by image scenes. Optimizer and translation requests carry the intended audience, source references, output language and per-scene timing. Repaired avatar headings and points from previews are retained for final generation.

Short nonempty topics such as “AI”, “Sun” or “जल” are accepted. Specific audience and example requests improve guidance, but are not required. The original prompt and selected controls remain authoritative over inferred defaults.

Research is introductory context, not comprehensive web fact-checking. Empty searches can retry the main topic; connection errors and provider errors do not trigger repeated calls. The report records attempted queries and unavailable-source reasons. Lookup uses the official [MediaWiki Search API](https://www.mediawiki.org/wiki/API:Search) and [Pageprops API](https://www.mediawiki.org/wiki/API:Pageprops).

Progress events name the stages actually executed. `production_notes.agent_workflow` records structural checks, character descriptions and retry count; it is included in the saved project and downloaded production report. It does not contain a fabricated visual quality score.

The Agents page distinguishes integrated stages, editorial advice, prompt helpers and unavailable capabilities. **Review & polish** is optional. Lip-sync, talking-avatar identity and arbitrary object/background replacement are not implemented merely by adding an agent name.

## Individual agent actions (October 2026 audit)

All 28 card actions are checked against the production adapter. Legacy browser task handlers are no longer used by these cards. Model-service availability remains separate from the local backend capability label. Cards no longer claim fabricated uptime, professional credits or benchmark scores.

Nine specialists now have separate, scoped model instructions: opening/hook, SEO, thumbnail design, supporting shots, tone/pacing, slide design, dialogue, excerpt selection and presenter appearance. Each produces a structured brief saved under `production_notes.specialists`; briefs leave narration and attached media unchanged. These are recommendations, not rendered thumbnails/slides, two-speaker audio or automatically cut clips. Unknown scene references and malformed responses receive one repair attempt, then fail without saving.

**Refine direction** runs the actual shot director on the current storyboard, preserving existing media and text. **Improve narration** validates every scene ID, edits generated narration and preserves source-video captions. **Translate text** supports en/hi/es/fr/de and changes captions/generated narration, not uploaded source audio. Translation preserves asset IDs, source ranges, speed and clip settings. **Timeline chapters** uses current clip durations and speeds without a language-model call.

**Voice sample** now uses the production neural voice service rather than the legacy browser voice flow. It previews up to 500 characters of selected narration. **Edit assistant** opens the validated timeline editor. Watermark and color actions open the actual editor settings; audio attachment and export use the production workflows. Enabling denoising supports undo.

The Lip-Sync card opens the realistic Avatar workflow; the separate presenter-description specialist only supplies a brief. The automatic generation pipeline uses relevant stages sequentially; optional specialist briefs do not all run on every Generate click. This avoids unrelated edits and unnecessary GPU work.

Verification includes every card's dispatch through the real Electron UI with external-service fixtures, plus backend schema, cancellation, bounded-repair, translation preservation and read-only report tests. This does not claim live GPU generation has passed while Colab is offline.

Continuity prompts improve consistency instructions; they do not guarantee identical characters across generated shots. Structural QA and playable MP4 checks cannot prove photorealism, factual accuracy, good pacing or visual coherence. Review the actual output. Real quality evaluation and fine-tuning require an evaluation set/training dataset and a live GPU runtime.

Validation: backend tests exercise the two real workflow stages with external-model fixtures, bad IDs, missing character references, a bounded repair, cancellation and project preservation. Rendering tests use real FFmpeg. UI checks cover settings reaching the planning/render requests and responsive layouts. These are not live Colab inference or model-quality benchmarks.

## Narration and image relevance (7 October 2026)

The reviewer receives each narration, supporting image prompt, slide text, neighboring narration and selected style. It must quote exact narration words and explain the depicted example. Hindi narration is reviewed against English image prompts without keyword-only matching. Unresolved mismatches fail before new visuals. Repairs preserve narration, timings and scene IDs.

`production_notes.visual_alignment` stores the reasons, repaired IDs and a fingerprint. Unchanged scripts reuse their review. Voice shortening, text edits, visual-prompt changes or style changes invalidate it; final rendering rechecks before requesting images/motion. Changed prompts use new image-cache keys. Explicit scene image regeneration also uses this check and retains the previous media on failure. Preview repairs reach the final-generation project. User-selected media are preserved and are not claimed to have passed automatic image-content inspection.

This is semantic review of prompts by the language model, not computer-vision verification of the generated frames. The image model can still draw an inaccurate object; inspect the preview. No agents were fine-tuned and no benchmark of professional visual quality is implied.


Realistic presenter update: the Lip-Sync tool now opens Avatar explainer → Realistic. It uses optional MuseTalk on the same authenticated Colab bridge after Ollama writes the script and voice duration is fitted. Enter a topic and choose Alex or Maya; the image model creates a face automatically, then MuseTalk animates its mouth. No upload is required. Run the five-second test to check live inference. The Avatar Generator specialist supplies a character brief; the production pipeline creates the portrait. This does not generate full-body gestures. See REALISTIC_PRESENTER_GUIDE.md for setup and limits.
## Ready-script workflow

Timestamped scripts now use a deterministic parser before visual direction. Their dialogue,
screen text and scene slots remain separate and are preserved; automatic research/writing
continues for short topic prompts. See [READY_SCRIPT_GUIDE.md](READY_SCRIPT_GUIDE.md)
for format, duration limits, instrumental music and image-reference setup.
