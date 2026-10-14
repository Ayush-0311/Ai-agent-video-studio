# Local video effects

These effects run in the local FFmpeg renderer; they do not require Colab. Save existing work and reopen the app through its launcher to use backend API 6 and the new controls.

## Transitions

In the editor's **Video settings**, choose **Between clips → Fade through black** or **Fade through white**. Set the fade duration per side (0.1–1 second) and apply video settings. Short clips clamp each fade to half their duration. Clip lengths, captions and chapter times remain unchanged. The first clip has no incoming fade and the final clip has no outgoing fade. Clip audio fades at the same boundaries; background music continues through the transition.

The timeline previews the visual dip. Export renders the final visual and audio fades. These are dip transitions, not overlapping cross-dissolves. The edit assistant also accepts `Fade through black`, `Fade white`, and `Remove transitions` locally.

## Replace a plain colored screen

Select a clip, open **Background & moving effects**, enable **Remove screen color**, and set its screen color (green, blue or another solid color). Choose a replacement color or upload a background image. Adjust color tolerance and edge softness, then **Apply clip changes** and Export.

Export produces the actual composite and opens it for playback/download. The live source preview does not perform chroma key; its note explicitly says to export for the replaced background. Image backgrounds fill the output frame with a center crop. Color grading is applied after compositing.

This works with a plain colored screen and adequate separation from the subject. It cannot automatically separate a person from an arbitrary room or reconstruct hidden scenery. Similar colors on clothing can also be removed; inspect the result and reduce tolerance where necessary.

## Moving blur or image overlay

Choose **Moving region → Blur area** or upload an image for **Image overlay**. Set width/height and start/end horizontal/vertical percentages. Position values use the available frame space: 0% means left/top, 100% right/bottom, and 50% center. Use the same start and end positions for a stationary region.

The region moves in a straight line across the clip's output duration. Preview shows its placement; browser blur is approximate. Export performs the actual crop/blur/composite or image overlay. Image overlays fill the selected rectangle with a center crop. Save/reopen and undo/redo preserve effect settings. Trimming/splitting preserves the corresponding portion of the motion path; changing speed changes how quickly the path is traversed.

This is a manually specified motion path, not automatic object/face tracking, face swapping or generative object removal. Check every frame if using it to obscure private content. A still image overlay does not create a photorealistic face replacement.

## Remaining AI features

Photorealistic talking avatars/lip-sync, arbitrary background segmentation/reconstruction, face swapping and automatic object tracking remain unimplemented. No disabled model-backed feature is represented as successfully rendered. MuseTalk was researched as a possible lip-sync backend, but its separate Python/CUDA/model dependencies have not been installed or GPU-tested here. The existing Colab generator is unchanged.

References: [FFmpeg filters](https://ffmpeg.org/ffmpeg-filters.html) and [official MuseTalk setup](https://github.com/TMElyralab/MuseTalk#installation).

## Validation

Real FFmpeg tests inspect output pixels for keyed backgrounds, foreground preservation, image backgrounds, moving overlays, blur and both fade colors. They verify duration, validate asset types/parameters, and reject arbitrary filter expressions. Editor tests cover effect form values, save/load, undo and motion-path preservation through cuts. The real-video test exports/downloads the supplied avatar reference with a moving blur and a fade through black.
