# Avatar explainer

Choose **Video creation → Avatar explainer · Slides + voice**. Enter a topic, choose the narration language and target duration, then select a presenter and layout.

- **Side-by-side:** supporting imagery on one side, an illustrated presenter beside it. Portrait exports stack the visual above the explanation area.
- **Picture-in-picture, right / left:** the image fills the video background, with a small circular head-and-shoulders presenter over the lower corner. Titles, key points and subtitles use translucent dark backing for readability and stay clear of the avatar. **Fit full frame** preserves the entire sharp source image and fills aspect-ratio gaps with a blurred duplicate; **Fill / center crop** fills the frame by cropping its edges. Side-by-side retains the separate slide/presenter layout.
- **Alex / Maya:** two built-in illustrated characters. Indigo and teal themes change the presenter and studio palette.
- **Draft video preview:** a separate 720p MP4 with the actual presenter, narration, slide text and captions. It preserves the original project. Final generation reuses the storyboard and cached images/voice when unchanged.

The writer plans a spoken explanation, one idea per slide, short headings and key points. The image model creates supporting imagery; slide text is typeset locally, including Hindi. Review factual explanations before sharing.

In the editor, select a generated slide and use **Explainer slide** to edit its heading, key points and spoken explanation. **Video settings** changes the presenter, layout and theme. Export applies the changes. Save project retains these fields. Once a generated scene is converted to a video clip by timeline edits, its presenter is baked into that clip and is not overlaid again.

## What is animated

The illustrated mouth opens according to measured narration energy, closes during silence, and follows speed changes. Blinks and small hand gestures are added locally. Muted slides do not animate the mouth. This is speech-reactive illustration, **not** phoneme-level lip-sync, a realistic human avatar, a face swap, or a newly trained model.

PiP presenters are anchored near the bottom corner, with an edge gap of 3.5% of the shorter frame dimension. Captions wrap in the remaining width beside the avatar so long phrases cannot cross its face. The gap scales with 720p/1080p and landscape, portrait or square output.

The presenter uses FFmpeg/libass vector graphics. No additional Python package, GPU model, paid API, or Colab notebook change is required for the avatar. Topic planning and generated images still need the existing working Colab connection. Narration defaults to the OmniVoice Colab bridge and requires a running GPU notebook. Legacy Edge narration is available through explicit voice settings. See COLAB_SETUP_GUIDE.md for current voice setup and limitations. Motion presets are disabled in this mode because it does not run Wan.

Duration remains a **target**: measured narration can extend a scene. This update does not promise exact-length exports. Rendering a presenter locally avoids full-motion inference, but AI image/voice/model load times still affect total generation time.

## Verification

Backend tests exercise planning fields, real MP4 composition, Hindi text, side/PiP layouts in landscape, portrait and square, speech/silence/mute behavior, cached media reuse and materialized clips. Electron checks cover option wiring, preview routing, edit/save/reload/undo and responsive controls.

`backend/studio-data/verification/avatar-demo/avatar-explainer-demo.mp4` is a locally rendered narrated sample. It uses prepared vector diagrams and the installed Windows voice, not a live Colab generation. Reproduce with `scripts/avatar-demo-voice.ps1`, then `backend/.venv/Scripts/python.exe scripts/render_avatar_demo.py`.

The Colab tunnel was offline during this verification. New-topic cloud planning, image generation and cloud narration could not be tested live. Existing integration tests substitute only those external AI boundaries; exported MP4s are real.


## Short topic prompts and generation progress

For prompts such as “Explain artificial intelligence”, choose Avatar explainer and Auto shots. Before writing, the app interprets the topic, audience, tone, required examples and requested visual treatment, including informal Hindi, Hinglish and English prompts. The original prompt and selected controls remain authoritative. The writer receives this brief and is instructed to define the concept, explain how it works, use a concrete everyday example, and finish with a takeaway or limitation. Visual direction and measured-duration rewrites retain the same brief. Visual style changes appearance, not the factual explanation.

Online references is optional. When enabled for a factual topic in any Auto shots mode, a bounded Wikipedia lookup sends the interpreted topic query to its public API and supplies up to two introductory extracts to the writer. Purely fictional briefs can skip factual lookup. The production report stores the interpreted brief, source links, lookup time and availability. This is introductory reference support, not comprehensive research or guaranteed fact-checking. If unavailable, generation continues with an explicit notice; review factual claims before publishing. Turn it off to avoid sending the topic to Wikipedia. Finished scripts in sentence/paragraph/manual modes are not researched or replaced automatically.

Generate video submits one saved backend job for planning and rendering. Reloading the app reconnects to that job while the backend remains running; it does not create another render. Reviewed storyboards are reused. Closing the progress panel leaves a small progress button to reopen it. Connection requests time out with a visible message, and Cancel works during connection checks as well as active jobs. Model operations may need to finish before cancellation takes effect. A stopped backend or expired Colab runtime cannot keep generating; restart/reconnect and retry after checking Activity.

New videos default to **Exact target · Fit script to duration**. Auto-written narration is measured and expanded or shortened to fill the selected duration with short scene pauses before generating visuals. **Natural pace** follows the voice and can produce a different final length. Full AI motion still depends on GPU inference speed.

Reference API implementation follows the [MediaWiki TextExtracts documentation](https://www.mediawiki.org/wiki/Extension:TextExtracts) and [Search API documentation](https://www.mediawiki.org/wiki/API:Search).
