# Music and beat sync

*When to read:* Lock picture to music: music videos, lyric videos, karaoke highlights, audio visualizers, beat-synced motion graphics and edits. Covers reading supplied beat/lyric timing or analysing the track, building one cue map that drives both picture and checks, choosing what lands on which beat, lyric display timing, audio-reactive parameters, muxing the original audio unchanged, and measuring sync on the final file. Use whenever a film comes with a song or must move to a beat.

In a music-driven film the audience feels sync errors before they see anything else: a cut two frames late, a lyric that appears after it is sung, a visualizer that pulses to nothing. Everything here follows from one rule: a single timing source drives the picture, the audio is never altered, and sync is measured, not assumed.

## 1. Timing source

- If the user supplies timing (beats, bars, sections, lyric lines or words as JSON or LRC), use it as given. Do not re-detect and overwrite it.
- Otherwise analyse the audio once (e.g. `librosa`: `beat_track`, `onset_detect`, `rms`, `chroma`; or numpy FFT): tempo, beat times, downbeats, section boundaries, onsets, loudness envelope. Detected beats are candidates; check the grid against obvious hits by ear or by onset strength and fix the downbeat phase.
- Save everything in `cues.json`: `{bpm, beats:[...], downbeats:[...], sections:[{id,t0,t1}], lyrics:[{t0,t1,text,words:[...]}], hits:[{t,name}]}`. The renderer, the subtitles and the checks all read this file.

## 2. Cue map: decide what lands where

- Not everything on every beat. Choose levels: section changes → scene or palette changes; downbeats → cuts and major transformations; beats → secondary accents; strong onsets (snare, kick, vocal attack) → specific hits. Leave some beats empty so the hits mean something.
- Visual events land on the cue frame: the contact, the cut or the peak of a pop is at `round(cue × fps)`. Anticipation starts before the cue.
- Respect phrases: a visual idea runs for a whole phrase (usually 2 or 4 bars), and changes at phrase boundaries.

## 3. Lyrics

- Show a whole line from slightly before it is sung (3–5 frames lead) until the next line starts, unless the brief specifies otherwise. Word highlights (karaoke) follow word timings exactly.
- Readability: one or two lines at most, high contrast, a font with every needed glyph (Chinese needs a CJK font), placed where it never covers the subject.
- Lyric text is exactly the supplied text; do not retype from memory.

## 4. Audio-reactive visuals

- Compute features per video frame offline from the audio (RMS, band energies from an STFT with a hop of `sr/fps`, onset strength), smooth them (attack fast, release slow), normalise, save to JSON, and sample by frame index. Never read live audio during capture.
- Map features to a few parameters with clear meaning (bass → scale or camera shake, highs → sparkle density, onset → flash or particle burst). Clamp ranges so silence still looks designed.
- Visualizer bars must reflect the real spectrum of the track at that frame.

## 5. Mux without altering the audio

`ffmpeg -i video.mp4 -i song.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest out.mp4`

- Do not trim, stretch, re-time or normalise the supplied song unless asked. Video length must match the audio (pad the last frame or end the picture exactly at the audio end).
- If the brief says the film is silent, there is no audio stream; sync then refers to the supplied timing only.

## 6. Measure sync

- For each hit in `cues.json`, find the frame where the visual event peaks (largest frame difference, flash brightness, cut) and compare with the cue: aim for 0 frames, tolerate ±1 frame (±33 ms at 30 fps).
- For lyrics: the first frame each line is visible versus its start time.
- After muxing, extract the audio from the final file and check its duration and that its onsets still align with the cue times (no offset introduced by encoding).
- Write the table of cue vs measured frame into `VERIFY.md`.

## 7. When you write the soundtrack yourself

If there is no supplied song and the film needs music (synthesis recipes and the sound kit are in [`references/sound-design-and-narration.md`](sound-design-and-narration.md)):

- Write the cue map first (tempo, bars, sections, hit points), derived from the film's structure; then generate both the score and the picture from it, so they agree by construction.
- Synthesize in code (numpy oscillators, envelopes, filters, simple drums, noise; or Web Audio rendered offline) in a palette that suits the style: chiptune square waves for pixel art, soft plucked tones and drones for ink wash, punchy drums for a promo. Avoid a generic piano-and-strings loop.
- Effects come from the animation's event list (impacts, pops, whooshes on transitions), placed on the exact frames.
- Keep it modest and clean: a short, well-mixed piece beats an ambitious muddy one. Fade in and out, avoid clipping, keep the bass under control.

## 8. Long songs (1–3 min)

Plan by section: each section gets its own visual state (palette, camera, density), with the chorus the strongest and a variation on its return. Avoid one loop repeated for the whole song; check the contact sheet for sections that look identical. Render in chunks if needed, but from the same world-time code so chunk boundaries are invisible.
