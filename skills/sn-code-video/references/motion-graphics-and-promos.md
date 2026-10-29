# Motion graphics and promos

*When to read:* Design-led motion graphics: kinetic typography, title sequences, logo reveals, product and app promos, social ads (16:9 and 9:16), UI demos built from supplied screenshots, and ads built from supplied product photos. Covers the design system, motion phases and springs, exact copy and reading time, safe areas, and using supplied logos, screenshots and photos faithfully. Use with the main SKILL.md for any promo, ad, brand or typography-driven film.

A promo is judged in seconds: does the first second grab, is every line of copy readable, does it feel designed rather than templated, and is the brand exactly right. Brand mistakes (a stretched logo, a wrong price, a mistyped code) fail the whole film, however good the motion is.

## 1. Design system first

Before animating, fix and write down:

- **Palette:** 2–4 colours plus neutrals, from the brief or the brand guide; nothing else.
- **Type:** one display face and one text face at most, from the supplied fonts or those installed. Sizes on a scale (e.g. 160 / 96 / 56 / 32 px at 1080p).
- **Grid and safe area:** 5% margins at 16:9. For 9:16 social video keep copy and logo out of the top ~220 px and bottom ~320 px, where app UI overlaps.
- **One motif** that carries transitions (a ripple, a wedge, a torn paper edge, a route line). Transitions grow from the motif instead of generic fades and wipes.

## 2. Motion grammar

- Every key action has phases: a short anticipation or wind-up → a decisive move → a landing (contact) → a small overshoot that settles → a readable hold. Vary durations; nothing moves at one constant speed.
- Springs as pure functions of time (no simulation state):

```js
// damped spring from 0 to 1 starting at t0; zeta < 1 overshoots
function spring(t, t0, freq = 2.2, zeta = 0.55) {
  const x = Math.max(0, t - t0), w = 2 * Math.PI * freq, wd = w * Math.sqrt(1 - zeta * zeta);
  return 1 - Math.exp(-zeta * w * x) * (Math.cos(wd * x) + (zeta * w / wd) * Math.sin(wd * x));
}
```

- Stagger groups by 2–5 frames instead of moving in unison. Keep one main event per moment; supporting elements stay quiet while it happens.
- Rhythm: something new roughly every 1–2 s in a fast promo, but every line of copy still gets its reading hold. Make it fast with fewer words, not with shorter holds.
- End on a composed final frame (logo, offer, call to action) held long enough to read twice.

## 3. Copy

- On-screen text is exactly the brief's copy: same words, case, punctuation, numbers and codes. No invented claims, prices, specs, awards or slogans.
- Reading time after a line has finished animating in: about `letters / 15 + 1.5` s. Large type for headlines; never shrink text below ~28 px at 1080p to make it fit.
- Kinetic type: when letters are material (stretching, cutting, morphing), the word must still reach a complete, readable state and hold there.
- Measure text with the real font before placing it; check kerning, line breaks and that nothing touches the safe-area edge.

## 4. Supplied assets

- **Logo:** use the file as given (SVG or PNG). Scale uniformly, never recolour, stretch, crop, rebuild or add effects that change it. Keep clear space around it.
- **Screenshots / UI:** the UI shown must match the screenshots (layout, colours, icons, copy). To animate a part (a checkbox filling, a ring sweeping, a number counting), rebuild only that element in code and match it to the pixel, then cross-check by overlaying the rebuilt frame on the screenshot at 50% opacity. Any changed values must follow the brief (e.g. 3/5 → 4/5) and stay consistent everywhere they appear.
- **Video clips** (showreels, product demos, "made with" walls): extract each clip window to an image sequence and draw it by `t`; never play `<video>` during capture. Recipe and checks in the main `SKILL.md`, section 11 (video assets).
- **Device mockups:** draw the phone or laptop frame in code (rounded body, screen inset, notch or island), put the UI inside a clip path; keep the UI sharp: scale screenshots down, not up.
- **Product photos:** keep them photographic; do not redraw or restyle the product. For a white or plain background, cut out with a soft key on the background colour, refine the edge (erode 1 px, feather 1–2 px) and check against a dark background for halos. Do not enlarge photos much beyond native size; design the layout around their real resolution.
- **Applying artwork to a product photo** (a label on a blank bottle): map the artwork into the blank region, bend it with the surface (for a cylinder, horizontal compression toward the edges ≈ `sin` mapping), multiply it with the photo's luminance so it picks up the lighting, and keep it strictly inside the label boundary. Check at 100% zoom.

## 5. Typical structures (10–15 s)

- **Product hero:** reveal (light sweep or silhouette) → one or two feature beats with exact copy → end card.
- **Social promo (9:16):** hook in the first second (big headline or bold shape) → products or offer beats on accents → code or call to action → logo hold.
- **App demo:** motif opening → one real interaction on the device (touch indicator, visible response) → result → end card.
- **Kinetic type / title:** a few distinctive transformations of the letterforms → full readable title → hold.

Sound: follow the brief (music bed, effects on key hits, sometimes a voiceover reading the exact copy) and build it with [`references/sound-design-and-narration.md`](sound-design-and-narration.md). A voiceover says only the brief's lines. Every on-screen line must still work with the sound off.

## 6. Checks

- Every string on screen against `SPEC.md`, character by character (prices, codes, dates).
- Logo: aspect ratio unchanged (measure its bounding box), colours unchanged.
- Safe area: no copy or logo outside it on any frame (check the contact sheet with the safe area drawn on).
- Readability: each line's on-screen hold ≥ its reading time.
- UI fidelity: overlay test; updated values consistent.
- Photos: no halos, no visible upscaling blur, applied artwork inside its region.
