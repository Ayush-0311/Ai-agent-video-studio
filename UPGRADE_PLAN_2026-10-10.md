# Motion, narration and caption upgrade plan — 10 October 2026

This is an inspected implementation plan, not a claim that these upgrades are installed. The current turn inspected code and measured existing exports; it did not change the production rendering pipeline.

## Confirmed timing findings

- backend/studio.py caption_files divides text into seven-word chunks and spreads them in proportion to word count across the entire scene. It does not consume speech timestamps.
- The renderer pads short audio to the scene duration with apad. Its caption timeline records the whole encoded scene, including this padding.
- In the saved 20-second image story, detected speech in scene 1 ends around 7.435 seconds. The caption `from erosion.` starts at 8.750 seconds. It appears over a second after the scene has become silent.
- The same file is silent from approximately 7.435 to 10.163 seconds across the scene change: a 2.73-second gap. Scene 2's final caption similarly starts at 18.750 seconds, after detected speech ends around 18.370 seconds.
- Audio and video stream start timestamps are both zero in the inspected image and motion exports. Detected initial silence is about 0.16–0.18 seconds. This does not show a multi-second container audio offset; padded gaps and inaccurate captions are the larger confirmed issues in these samples.
- These are FFmpeg silence-threshold observations (-40 dB, minimum 80 ms), not a word-level transcription or listening verdict. Evidence: backend/studio-data/verification/live-quality-2026-10-10/audio-timing-inspection.json.

## Priority 1: synchronize captions with actual speech

Keep the current neural voice initially. Its installed edge-tts package supports WordBoundary and SentenceBoundary events, but narration.synthesize currently saves audio only. Request word boundaries explicitly, save a JSON timing sidecar alongside the speech cache, preserve script punctuation, and group captions by sentence/readability instead of arbitrary seven-word intervals.

Convert timestamps using the same clip speed, narration tempo and trimmed leading offset as the audio. Add scene offsets only after duration quantization. Silence padding must not stretch caption timing. A source clip trim must clip/rebase captions too. Regenerate or align legacy narration that has no timing sidecar; label any estimated fallback clearly.

For uploaded speech or providers without timestamps, evaluate forced alignment against the actual narration. WhisperX provides a word-alignment stage; its alignment model must support the language. Hindi and English require separate validation: https://github.com/m-bain/whisperX.

Acceptance targets, not current results: manually checked English and Hindi samples with caption onset usually within 150 ms of the spoken phrase; monotonic, nonoverlapping cues; no final phrase first appearing after speech has ended; correct timing after trim, split, reorder and speed changes. Include a longer multi-scene export to detect accumulated drift.

## Priority 2: narration-driven scene timing

Generate and measure speech before assigning final shot lengths (speech preflight already exists). Measure leading/trailing quiet sections and distinguish excessive silence from natural punctuation pauses. Preserve a small intentional lead-in/tail rather than stripping all silence. Rebase the word timestamps whenever audio is trimmed.

Provide an explicit choice between exact target duration and natural narration duration. For an exact target, improve script length or allocate scene budgets around actual speech, with intentional visual breathing room; avoid several seconds of accidental silence at every scene boundary. Keep the existing bound on voice acceleration.

Use one prepared narration timeline for the final soundtrack, captions and lip-sync. Consider PCM intermediates and a single final AAC encode; measure encoder delay and joins instead of applying a guessed universal delay correction. Do not move all audio by an arbitrary fixed offset.

## Priority 3: natural voice delivery

Current direct Edge TTS generation works in English/Hindi. The fastest useful improvements are speech-oriented scripts, punctuation, pronunciation handling for names/numbers/abbreviations, consistent language and voice choice, and the timing fixes above. Natural delivery currently means a small rate/pitch adjustment; it is not an expressive acting model.

Keep voice previews and saved per-project voice settings. Compare the same English/Hindi scripts across candidate voices/providers before adopting a new engine. Evaluate pronunciation, pauses, warmth, noise and consistency by listening. Higher audio bitrate or normalization alone cannot make a synthetic voice human-like. Avoid adding a large GPU TTS model to the already busy T4 before showing a real quality advantage.

## Priority 4: motion quality and real motion cadence

The live 12-step Wan draft completed but failed visual review: dark/banded first shot and overly bright, soft second shot. The cause is not isolated. Perform a controlled short reference test at the model's reference settings, then vary steps, resolution, precision/quantization and decoding settings independently where supported. Do not claim that changing only the step count fixes the issue.

Evaluate a genuinely distilled low-step motion model as a separate candidate. LTX-Video 2B distilled is a candidate documented by its official repository: https://github.com/Lightricks/LTX-Video. It is not installed or benchmarked here, and advertised speed is not a prediction for this T4. Also evaluate image-to-video conditioning from an approved high-quality still for better composition control; this is an experiment, not a guarantee against artifacts.

Avoid routinely stretching a roughly three-second source to six seconds. This halves its motion speed, and exporting at 30 fps does not restore missing motion detail. Prefer native-length shots, split long narration across more shots, or generate a longer source where supported. Test interpolation only as optional finishing for already-good footage; it cannot repair malformed content or poor texture. Upscaling is also a finishing step, not native high-resolution generation.

Keep GPU inference serialized and reuse model/prompt caches, which are already partly implemented. Record downloads, loading, inference, decoding and local export separately. Select stronger hardware or a hosted provider only after comparing the same short benchmark, memory needs, cost and visual quality. Free T4 cannot be promised fast, polished output for every mode and prompt.

Acceptance: render and inspect several prompts covering water/foliage, a person, and camera motion; compare multiple timestamps and playback, including banding, flicker, anatomy, prompt match and source resolution. Passing MP4 validation alone does not pass this review.

## Priority 5: realistic avatar and final quality checks

Enable the existing MuseTalk integration in Colab and run the five-second test before a full render. It remains disabled and untested in the connected setup; automatic desktop control failed. Feed lip-sync the same prepared, time-adjusted narration used in the final export. Review mouth synchronization; the illustrated avatar uses speech-energy animation, not phoneme lip-sync.

Retain technical export validation, and add explicit timing/quality reports: audio onset/end, unexplained silence gaps, caption alignment coverage, A/V duration, decode failures, blank/clipped frames, and source versus export resolution. Automated image metrics should flag review candidates, not claim perfect semantic or human quality.

## Recommended implementation order

1. Save speech boundaries and implement caption alignment.
2. Remove accidental padded gaps and share one narration timeline across all outputs.
3. Validate English/Hindi voice delivery and longer exports.
4. Benchmark a corrected reference motion path and a distilled candidate.
5. Validate realistic lip-sync and then select hardware based on measurements.

Caption and narration timing work can be developed and tested locally; it does not require replacing the Colab GPU. This is the first upgrade to make.
