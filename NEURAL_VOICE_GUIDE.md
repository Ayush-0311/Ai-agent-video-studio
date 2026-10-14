# Natural narration

Use **Voice settings & preview** on the creation screen, or open Settings.

**Save voice settings** saves narration preferences independently of Colab URLs/tokens and without testing those connections. **Hear voice sample** also saves only narration preferences before synthesis. Queued/running renders prevent changes so one export cannot mix different voice configurations.

**Direct neural** is the default engine. It sends narration to the online Edge TTS service from this PC; it uses no Colab GPU. It needs Internet access. The previous Colab voice route remains available as **Colab voice · Basic gender / pace**.

Available named profiles:

| Language | Voices |
|---|---|
| Hindi | Madhur (male), Swara (female) |
| Indian English | Prabhat (male), Neerja (female) |
| US English | Christopher (male), Jenny (female) |

Auto follows narration language and the Auto voice gender. English Auto uses an Indian-English voice. When a named profile belongs to a different language, the actual narration uses that language's Auto voice; the sample player identifies this change. Spanish, French and German keep their existing automatic voice pairs.

**Natural / Calm / Energetic** apply modest rate and pitch changes. They do not provide emotional acting, voice cloning or a newly trained voice model. Pace remains bounded from -20% to +20%. Optional loudness balancing applies a 65 Hz high-pass filter and FFmpeg loudness normalization targeting -16 LUFS / -1.5 dB true peak, then saves a validated 48 kHz MP3. It is level processing, not a guarantee of studio-quality speech or pronunciation.

Choose a sample language and press **Hear voice sample**. The sample uses the same saved engine, voice, delivery, pace and loudness settings as subsequent scene narration. Changing those settings invalidates the voice cache, while image and motion caches remain reusable. Already-exported videos are unchanged; export generated scenes again to apply the new narration. Video clips with baked-in source audio retain that source audio.

The voice engine reports an error if online synthesis fails; it does not silently replace the selected neural voice with gTTS. Health indicates that the local runtime is available, not that the online provider has passed a fresh synthesis test. Existing Colab code does not need updating for Direct neural.

Implementation references: [edge-tts voice, rate and pitch support](https://github.com/rany2/edge-tts), [Microsoft voice-language reference](https://learn.microsoft.com/azure/cognitive-services/speech-service/language-support?tabs=tts). Azure's full voice catalogue is not a guarantee that every voice is available through Edge; only the bounded profiles above are exposed here.

Live verification produced decoded MP3 samples for **hi-IN-SwaraNeural** and **en-IN-NeerjaNeural** in `backend/studio-data/verification/neural-voices`. Automated tests cover voice resolution, pacing bounds, cache separation, real audio normalization, atomic writes, failures and UI preview routing. Perceived naturalness and pronunciation should be judged by listening to the samples.

The October 4 integration audit also passed voice-only settings save, real Hindi synthesis through the preview endpoint, preview download, an avatar MP4 render, Hindi subtitles and final MP4 download. The isolated test used an uploaded diagram, so it does not verify cloud image/planning services. Reproduce with `scripts/audit_voice_export.py`; reports and videos are under `backend/studio-data/verification/voice-export-audit`.
