# Three.js scenes and cameras

*When to read:* Build 3D shots in Three.js from code alone: procedural modelling of buildings, interiors, vehicles, products and props; designed camera paths (orbit, dolly, crane, FPV, chase, fly-under) that never clip; simple procedural and product-studio looks; deterministic seek(t) with baked simulation; headless WebGL rendering. Use for architectural fly-throughs, game-like scenes, 3D product shots, exploded views and any Three.js video.

A 3D shot is judged on three things before materials: whether the objects are recognizable by silhouette, whether the camera path matches the brief (direction, extent, start and end framing), and whether nothing pops, slides or clips. Build in that order.

## 1. Scene skeleton

```js
import * as THREE from './three.module.js';
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setSize(W, H);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping;
const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(35, W / H, 0.1, 5000);
window.seek = (t) => { updateWorld(t); updateCamera(t); renderer.render(scene, camera); };
window.READY = true;
```

- Use real-world units (1 unit = 1 m) so the brief's dimensions translate directly and light, fog and camera speeds behave.
- `updateWorld(t)` sets every transform from `t`. No `clock.getDelta()`, no mixers advanced by delta: use `mixer.setTime(t)` if you use AnimationMixer.
- Set `camera.near` as large as the scene allows (0.05–0.5) to avoid z-fighting; set `far` to just beyond the visible scene.

## 2. Procedural modelling

Build recognizable silhouettes from primitives; detail where the camera goes close.

| Need | Tool |
|---|---|
| Bottles, vases, towers, wheels, lamps | `LatheGeometry` from a 2D profile |
| Car bodies, frames, mouldings, letters | `ExtrudeGeometry` from a `Shape` (with bevel), or lofted rings |
| Pipes, cables, frame tubes, rails, roads | `TubeGeometry` along a `CatmullRomCurve3` |
| Terrain, cliffs, rock undersides | `PlaneGeometry` displaced by seeded noise (fbm), recompute normals |
| Many repeated parts (keys, windows, people, dominoes, trees) | `InstancedMesh`, one matrix per instance |
| Rounded boxes (devices, furniture) | `RoundedBoxGeometry` from addons, or extruded rounded rectangles |

- Group parts in a hierarchy that matches how they move (car → body, wheels; arm → waist → shoulder → elbow → wrist). Pivot each group at its joint.
- Give a scene a readable scale cue: a door, a railing, a person-sized figure, a car.
- Text in 3D (labels, product names): prefer HTML/canvas overlays composited in the same frame, or `TextGeometry` with a bundled font; check glyphs at final size.

## 3. Camera paths

Write the camera as data, then sample it by `t`:

```js
const path = new THREE.CatmullRomCurve3([p0, p1, p2, p3], false, 'centripetal');
const look = new THREE.CatmullRomCurve3([l0, l1, l2, l3], false, 'centripetal');
function updateCamera(t) {
  const u = ease(clamp((t - T0) / (T1 - T0), 0, 1));       // ease-in-out progress
  camera.position.copy(path.getPointAt(u));                 // getPointAt = arc-length, even speed
  camera.lookAt(look.getPointAt(u));
}
```

- Match the brief's grammar exactly: orbit direction (counterclockwise seen from above means angle increasing with `t` in the x–z plane), extent (~90°), height change (crane up), dolly in or out, start and end framings. A static shot or the wrong direction is a failure even if it looks good.
- Speed: ease in and out; the middle of a move is the fastest. Avoid sudden acceleration or a stop-start. FPV moves can bank slightly (roll ≤ 10°) and level out; architectural moves keep the horizon level.
- Chase and tracking cameras: compute the subject's position at `t`, then place the camera relative to it with a smoothed (lagged) offset, e.g. sample the subject path a few tenths of a second earlier for the look target. Never parent the camera rigidly to a bouncing object.
- **No clipping.** Before the final render, sample the camera every 1/30 s and raycast from the previous position to the current one and in a small sphere around it; any hit with solid geometry closer than the near plane plus a margin is a bug. Fix the path, not the near plane.
- Holds: end most shots with a short hold on the final framing.

## 4. Looks

**Simple procedural models (blockout detail, often a structural proxy for a video model):** recognizable shapes at blockout detail; `MeshStandardMaterial` with plain, believable colours per material group (ground, structures, vehicles, characters), sensible roughness and metalness; simple procedural patterns only where they aid reading (lane lines, window grids); no photographic textures, text or logos. One directional key light with soft shadows (shadow map 2048+, tight shadow camera bounds), plus a `HemisphereLight` fill; a simple sky gradient; optional subtle fog for depth. Geometry, depth and motion carry the shot; colour keeps objects separable.

**Product studio:** dark or seamless light backdrop, a large soft key, rim lights for silhouette, a moving highlight sweep (animate a light or an emissive card across the product), a glossy floor with a soft reflection (`MeshPhysicalMaterial` with clearcoat or a mirrored copy under a translucent floor). Materials: brushed metal (low roughness + anisotropy or a faint stripe normal), matte plastic (roughness 0.6–0.8), glass (`transmission`), fabric (high roughness, darker).

**Night / special lighting:** if the brief overrides the neutral setup (torchlight, golden hour), keep geometry readable with a low fill light; flicker uses seeded noise of `t`.

## 5. Motion that reads as physical

- Wheels: angle = distance travelled / radius; front wheels steer into curves; slight body roll outward in turns.
- Objects moving along a path face along the tangent (`curve.getTangentAt(u)`), with eased speed changes.
- Rigid-body physics (dominoes, collapsing towers, falling objects): precompute with a fixed step (cannon-es, rapier, or your own solver) and seed, store transforms per step, interpolate by `t`. Check: no interpenetration, nothing floats, everything at rest truly stops, object count unchanged.
- Exploded views: each part moves along a consistent axis by a staggered amount, with spacing so nothing intersects; reassembly returns to the exact original transforms (store and reuse them). Callout leader lines are recomputed every frame by projecting the part's anchor point to screen.
- Characters and animals: see [`references/character-and-creature-motion.md`](character-and-creature-motion.md).

## 6. Headless rendering

- Headless Chromium often renders WebGL in software (SwiftShader): heavy shadows, many lights and high instance counts get slow. Measure ms/frame on a few frames, then cut cost where the camera cannot see it (smaller shadow maps for distant lights, fewer segments on far objects).
- Keep `preserveDrawingBuffer: true` for screenshots and render once per `seek`. Wait for all procedural textures (canvas textures) to be created before `READY`.
- Antialiasing: MSAA from `antialias: true` may be unavailable in software GL. If edges stair-step, render at 2× size and downscale in ffmpeg (`-vf scale=1920:1080:flags=lanczos`).

## 7. Checks

Contact sheet plus stills at the brief's named moments, then: start and end framing as described; camera direction and extent; subject size in frame; no clipping (raycast log); no popping or teleporting objects (frame strips at 0.1 s around fast motion); shadows and contact present (no floating objects); constant horizon unless a roll was asked for.
