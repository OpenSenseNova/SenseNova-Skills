# Sound design and narration

*When to read:* Give a code-made film its sound: plan ambience, effects, music and voice; drive every sound from the animation's own event timeline; synthesize effects and an original score in code; produce narration with an available TTS engine, check it and subtitle it; mix with ducking and loudness targets; mux and verify sync. Use whenever a film needs audio (narration, voiceover, music, sound effects, sonification) and no finished soundtrack is supplied.

Sound is half the film, and it is judged mercilessly: a click two frames late, a voice buried under music, a generic piano loop or a clipped peak make a good picture feel cheap. Everything below follows three rules: plan the sound with the picture, drive it from the same timeline, and verify it in the final file.

Scripts in `scripts/`:
- `tts.py`: edge-tts narration, per line, with measured timing.
- `synth.py`: a small procedural sound kit (tones, plucks, drums, effects, mixing, WAV out).
- `audio_check.sh`: loudness, true peak, clipping, silence and length.
- `sync_check.py`: sound onsets against your event times.

Required packages are listed in `requirements.txt`.

## 1. Plan the sound

Write `SOUND.md` before making any audio. For each section of the film, list:

- **Ambience:** the room or world (wind, rain, city, underwater, studio hum). It is quiet, continuous, and changes when the place changes.
- **Effects (foley):** one sound for each meaningful visible action (lands, snaps, clicks, splashes, whooshes on fast moves), matched to the material: paper, wood, metal, glass and water all sound different. Not every particle needs a sound; important actions do.
- **Music:** tempo, instruments and energy for the section, and where it builds, drops and resolves.
- **Voice:** which lines play here, if any.

Craft rules (from strong reference films):

- Use the style's own instruments, not a generic piano and strings. Square waves suit pixel art, guqin and flute suit ink wash, a brushed swing combo suits a jazz piece, and a soft synth bed suits a clean diagram.
- Place at least one real near-silence before the key moment or turn of a longer film. The first sound after it should be one of the most important in the film.
- Use sound as a transition: bring the next scene's sound in slightly early, or let the last scene's sound run over the cut.
- Short films (10–15 s) need one clear idea in sound too: a music phrase that resolves at the end, plus a few precise accents.

## 2. One timeline

- The animation is the timing source. Export its events and useful state from the same code that draws the picture. For example, `window.EV = [{t, name}]` or an `audioEvents()` function, plus per-frame channels such as speed, angle or density. Write them to `build/events.json` and `build/motion.json` before synthesizing any sound.
- Effects are placed at the exported event times; continuous state drives continuous sound. Examples: whoosh loudness follows speed; tone pitch follows a quantity; texture density follows particle count.

```python
amount = np.clip((np.interp(audio_t, frame_t, speed) - lo) / (hi - lo), 0, 1) ** 1.5
layer = filtered_noise * amount * gain
```

- Music: write the cue map (BPM, bars, sections, hit points) from the film's structure, then put key visual events on beats. Snap an accent to a beat only when the shift stays within about 80–150 ms; otherwise keep the sound on the exact event and let the harmony support it.
- If the picture changes, re-export the events and rebuild the audio. Never maintain a second hand-typed timing list.

## 3. Narration and voiceover

**Script and budget**
- Write the script before animating the narrated parts. Budget about 130–150 words per minute in English and about 220–260 characters per minute in Mandarin, slower for technical passages, with pauses between ideas.
- Spell numbers out in the TTS text ("fifteen percent", "nineteen fifty-five"), and show them as digits on screen.
- When the brief fixes the exact lines (a voiceover reading the copy), say exactly those lines.

**TTS engine**

Default: **edge-tts** (Microsoft neural voices; needs network access). Use `scripts/tts.py`. It synthesizes one clip per line, caches by text, voice and rate, measures the real speech start and end in each clip, and exports word timings shifted onto the measured onset (edge-tts word offsets run about 40–55 ms early):

```sh
python3 "$SKILL_DIR/scripts/tts.py" build/lines.json build/vo     # writes build/vo/<id>.wav and build/vo/timing.json
```

Each line has `say` (what is spoken, numbers spelled out) and `show` (the subtitle text, e.g. "15% off"), plus optional per-line `voice` and `rate`.

Good defaults:
- English: `en-US-AndrewNeural` or `en-US-AndrewMultilingualNeural` (calm male), or `en-US-AvaNeural` / `en-US-EmmaNeural` (warm female).
- Mandarin: `zh-CN-XiaoxiaoNeural` (warm female) or `zh-CN-YunxiNeural` (male). For children's films a slightly slower rate (−5% to −10%) reads better.

Practical notes:
- Measure the speaking rate rather than assuming it: −6% has given anywhere from about 2.6 to 3.1 words/s.
- If a word gets swallowed (a final "s", a name), slow just that line (for example −14%) or rephrase it.
- A lone letter is read as a letter name: write "two n minus one" in `say` and "2n − 1" in `show`.
- The service occasionally drops a request; the script retries.

If the service is unreachable, say so in `VERIFY.md` and do not fake a voice.

**Recording and timing**
- Generate one WAV per line.
- Measure each line's real length, then build the picture timing around the voice (holds, pauses, when each visual beat lands).
- Leave about 0.2–0.4 s of air between lines.

**Checking the voice**
- Transcribe each line with `faster-whisper` and compare it with the script: `base.en` for English, a multilingual model (`small` or larger) for Mandarin, compared character by character. Regenerate lines that come back wrong. Near-homophones and unusual names ("Wassily" → "Vasily") can be recogniser errors rather than voice errors; listen before regenerating.
- Word timestamps from recognisers can be early, so place lines by the measured energy onset.

**Processing**
- Band-pass about 75 Hz–12 kHz, gentle compression, and level each line from its speech frames, not from silence.
- Keep the raw TTS files for comparison.

**Subtitles**
- One or two lines at a time, matching the spoken words.
- On screen from the start of speech until about 0.3 s after it ends, and at least 1.8 s per subtitle.
- Placed in a band that never covers the subject. Export an `.srt` file as well when it is useful.

## 4. Music in code

Make the score yourself from the cue map. Useful building blocks, all in `synth.py`:

- **Plucked strings** (guqin, lute, harp, ukulele, bass) via Karplus–Strong.
- **Tones and pads:** sine, triangle, saw and square tones with ADSR envelopes; detuned, layered saws for pads; low-passed squares for chiptune.
- **Drums:** kick (a sine with a falling pitch), snare (noise plus a tone), hi-hat (high-passed noise), brushes (soft filtered noise strokes).
- **Bells and chimes** from inharmonic partials with long decays.

Arrange by section: an intro, a build toward the main moment, the peak, and a resolution on the final frame. Repeat motifs with variation rather than looping one bar.

Keep the low end under control: avoid pad notes below about MIDI 48, give the bass some 2nd and 3rd harmonics so it is audible on small speakers, and keep 20–120 Hz around 3 dB below the rest after mixing.

For a looping film, the music's length equals the loop and every tail (reverb, decay) wraps around: render two loops and keep the second.

## 5. Effects recipes

| Sound | Recipe |
|---|---|
| Tap / click | 2–10 ms noise or sine burst through a band-pass; vary pitch ±5% per hit (seeded) |
| Thud / impact | Low sine with a fast pitch drop (120 → 50 Hz) plus a short low-passed noise burst |
| Whoosh | Band-passed noise whose centre frequency and level follow the motion's speed, with a soft attack and release |
| Pop / bubble | Short sine with a fast upward or downward pitch glide |
| Chime | 3–5 inharmonic partials (ratios such as 1, 2.76, 5.4, 8.9) with exponential decays |
| Rain / water | Filtered noise bed plus seeded droplet clicks at random times and pitches |
| Wind | Low-passed noise with a slowly modulated cutoff and level |
| Mechanical | Clicks for teeth, a rumble for rolling (level follows speed), a short scrape for sliding (noise through a moving band-pass) |
| 8-bit | Square-wave blips with pitch sweeps; explosions as noise bursts with a stepped decay |

Avoid the machine-gun effect: never repeat an identical sample in rapid succession, and vary the pitch, level and timing slightly.

## 6. Mix and master

- Keep stems separate until the end: voice, music, effects and ambience.
- **Voice first:** compress it, then set the music about 10–14 dB below the voice while the voice is speaking (sidechain ducking with a 50 ms attack and 300 ms release), letting it recover between lines.
- Effects should support the picture, not shout. Ambience stays low.
- Fade in at the start and out at the end; the audio must be exactly as long as the video.
- Master with a two-pass loudness normalization to about −16 to −14 LUFS integrated, true peak ≤ −1 dBTP:

```sh
ffmpeg -i mix.wav -af loudnorm=I=-14:TP=-1:LRA=11:print_format=json -f null -   # read measured values
ffmpeg -i mix.wav -af loudnorm=I=-14:TP=-1:LRA=11:measured_I=...:measured_TP=...:measured_LRA=...:measured_thresh=...:offset=...:linear=true -ar 48000 master.wav
ffmpeg -i video.mp4 -i master.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest final.mp4
```

## 7. Verify

- `sh "$SKILL_DIR/scripts/audio_check.sh" final.mp4 -14`: integrated loudness, true peak, clipped samples, long silences, and audio versus video length.
- `python3 "$SKILL_DIR/scripts/sync_check.py" final.mp4 build/events.json`: for each event, the nearest sound onset and the offset in milliseconds. Aim for 0 and accept ±1 frame. Events marked `"silent": true` are skipped. A sound must be a clear onset to count (`--thr`, default 0.7 of a strong onset); lower it for very soft effects, and treat "MISSING" as either a misplaced or an inaudible sound.
- Re-transcribe the final mix if it has narration, and compare it with the script.
- Listen to the opening, every key moment, every narration change and the ending with the picture. Pay attention to the ending: no cut-off tail, no abrupt stop.
- Write the measured values and the event-offset table in `VERIFY.md`.
