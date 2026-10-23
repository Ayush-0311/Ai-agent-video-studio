# Timed scripts → videos

Paste a script into **Your video idea** with **Auto shots / detect script** selected, or select **Ready script · Exact timestamps**. For example:

```text
Generate all images automatically.
0–5 sec: Visual: A young man studying at night.
Voiceover: “मेहनत करते रहो।”
Text: “KEEP GOING”
5–10 sec: Visual: The same man at sunrise, fade to black.
Voiceover: “हर कदम मायने रखता है।”
Text: “ONE STEP AT A TIME”
Use consistent character appearance, background music, Hindi male voiceover, vertical 9:16.
```

The complete supplied 60-second example is in [tests/fixtures/motivational-ready-script.txt](tests/fixtures/motivational-ready-script.txt).

## What the workflow preserves

- Continuous timestamps starting at zero; the last timestamp sets duration. Supported total: 10–180 whole seconds for images/avatar, up to 60 seconds for motion/hybrid. This is not limited to 40 or 60 seconds.
- Spoken dialogue, separate screen text, scene order and timings. Screen text does not become narration.
- The visual director improves English image prompts and shared character descriptions. It receives the supplied scene directions and treats cinematic/motivational metaphors as intentional.
- A `fade to black` visual direction adds a fade. Screen text appears at the top, speech subtitles below. Both are included in the final MP4.
- Hindi dialogue, explicit `9:16`, `male voiceover` / `female voiceover`, and `Generate all images automatically` are recognized. Voice gender still depends on support in the selected voice provider.

Use quotes around **Voiceover** and **Text**, especially in the final scene followed by global instructions. Use one set of fields per scene. Both seconds (`55–60 sec:`) and clock notation (`0:55–1:00:`) work. Gaps, overlaps and invalid clocks are rejected with a scene-specific message.

The supplied dialogue is measured before generating scene visuals. Up to 10% tempo adjustment is allowed. If dialogue still exceeds its locked slot, the app identifies that scene and asks for shorter dialogue or revised timestamps. It does not silently cut words or rewrite a finished script. Brief dialogue in a long explicit slot leaves quiet time; for a newly written, duration-filling explanation, enter a topic using **Auto shots** instead.

## Images, character reference and motion

- **Image story:** generated images with pan/zoom. A long montage direction is directed into a single composition per timed scene. Split it into smaller timed scenes when you want several different images.
- **Hybrid:** first scene is AI motion, later scenes are images.
- **Full AI motion:** each generated shot is motion. Per-shot maximum is 6 seconds for Fast draft and 10 seconds for the other presets. Split longer supplied scenes; they are not silently stretched.
- **Main character reference:** one reusable portrait conditions matching image scenes. SDXL uses IP-Adapter; FLUX.2 Klein uses its image input. Landscapes without that character remain unconditioned. Motion shots use written appearance descriptions. This improves consistency but does not guarantee identical faces.

For the new reference input, upload the updated **colab/SmartEdit_Colab.ipynb**, stop the old setup cell, run the new one and reconnect the desktop app. Adapter/image-encoder weights download on first use. A connected GPU runtime is required for AI image/motion generation; no paid provider API key is used. The existing tunnel may still require its free authentication token.

## Instrumental and editing

**Script, music & character options** includes cinematic, uplifting and calm local instrumentals. These are original procedural compositions, not a downloaded recording or a generative music model. They require no API key. Narration ducks the music and the ending fades it out. Uploaded music takes priority.

The editor lets you change screen text, per-scene fade, music preset and volume. The timeline shows approximate screen-text placement; automatic music and final typography are applied during MP4 export. Open the exported preview to judge the complete mix.

## Verification scope

Local checks exercise parsing, dialogue preservation, UI options, image-reference request routing/cache, actual FFmpeg assembly, frame count, screen-text pixels, fade and non-silent music. External language/image/voice providers are mocked in deterministic integration tests. These checks do not establish live GPU image quality, character identity or Hindi speech quality; review a connected preview before a long render.

For development, install `tests/requirements.txt` into the backend environment for the isolated Colab PNG decoding tests.
