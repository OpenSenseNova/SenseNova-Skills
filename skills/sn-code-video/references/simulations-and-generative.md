# Simulations and generative motion

*When to read:* Rule- and physics-driven visuals: rigid bodies, pendulums and projectiles, particles and fireworks, flocking (boids), crowds, cellular automata, fluids and flow fields, shader effects (aurora, noise fields), and generative patterns. Covers baking simulations deterministically, choosing integrators, keeping particle identity, checking invariants (rules, energy, counts), and rendering many elements fast. Use when motion should come from rules or physics rather than keyframes.

The appeal of a simulation is that it is true to its rules. The two ways it goes wrong in a video: it is not deterministic (each frame or each render differs), or it quietly breaks its own rules (energy grows, cells update wrongly, objects overlap, particles respawn and flicker).

## 1. Bake, then sample

- Run the simulation once, before rendering, with a fixed time step `dt` (and substeps) and a fixed seed. Store the state you need per step (positions, angles, alive cells).
- Render frame `i` from the stored state at `t = i / fps`: pick the two nearest steps and interpolate positions (slerp rotations). The render function never advances the simulation.
- For long or large sims, store to a typed array or a binary file and load it before `READY`.
- Time scale (slow motion) is a uniform factor applied when sampling, never a change of `dt` mid-run.
- Before the full bake, run 100–1,000 steps on a small grid and assert that the state actually changes and the invariants hold (see the main `SKILL.md`, long jobs). Measure how fast the pattern grows or moves per step, then choose steps per frame from that measurement.

## 2. Integrators

| System | Use |
|---|---|
| Projectile, simple gravity | Closed form (`x = v0 t`, `y = v0 t − g t²/2`); no integration needed |
| Double pendulum, orbits, chaotic systems | RK4 with small `dt` (e.g. 1/2000 s) and several substeps per frame; check energy drift |
| Springs, cloth, particles with drag | Semi-implicit (symplectic) Euler or Verlet with fixed `dt` |
| Rigid bodies, stacks, dominoes | A physics engine (cannon-es, rapier) at fixed step, or a scripted kinematic model when the motion is simple and must be exact |
| Boids, crowds | Fixed-step steering (separation, alignment, cohesion, goal, obstacle avoidance) with neighbour search on a grid |
| Cellular automata | Exact discrete update per generation; display generations at a chosen rate |

## 3. Invariants: decide them, then check them

Write the invariants in `SPEC.md` and test them in code after baking:

- **Rules:** e.g. Game of Life B3/S23: recompute a few generations independently and compare; known patterns behave as known (a Gosper glider gun has period 30 and emits one glider per period).
- **Conservation:** total energy within ~1% for frictionless systems; object and atom counts constant; mass of fluid constant.
- **Geometry:** rigid rods keep their length; no interpenetration beyond a small tolerance; resting objects have zero velocity (no jitter).
- **Sensitivity (chaos):** if the brief wants divergence from tiny differences, the trajectories must start visually identical and separate only through the dynamics.

Print the measured values; put them in `VERIFY.md`.

## 3b. Reference data (verified, use instead of recalling)

**Gosper glider gun** (Game of Life B3/S23), RLE, 36 cells, bounding box 36 × 9. Verified: population is 36 + 5k at generation 30k, so it emits one glider every 30 generations, and the gliders travel down-right.

```
x = 36, y = 9, rule = B3/S23
24bo$22bobo$12b2o6b2o12b2o$11bo3bo4b2o12b2o$2o8bo5bo3b2o$2o8bo3bob2o4bobo$10bo5bo7bo$11bo3bo$12b2o!
```

RLE decoding: a number repeats the next symbol; `b` is dead, `o` is alive, `$` ends a row, `!` ends the pattern. Glider: `bo$2bo$3o!` (moves one cell diagonally every 4 generations). Test any pattern you use in your own simulator before building the film on it.

**Gray–Scott reaction–diffusion** (Karl Sims' setup): `A' = A + (Da·∇²A − A·B² + f·(1−A))·dt`, `B' = B + (Db·∇²B + A·B² − (k+f)·B)·dt`, with Da = 1.0, Db = 0.5, dt = 1 and a 3 × 3 Laplacian (centre −1, edge neighbours 0.2, corners 0.05). Starting points: f = 0.055, k = 0.062 (coral-like growth), f = 0.0367, k = 0.0649 (mitosis, splitting spots). Other regimes depend on the Laplacian, the scaling and the seeding, so map them with one small batch scan (for example an 8 × 8 grid of (f, k) on 256² cells) rather than recalling values. Dense seeding merges every domain into one labyrinth within seconds; to show distinct regimes, seed sparsely and give patterns room to grow. Growth is slow (fronts move a small fraction of a cell per step), so measure it before planning the steps per frame.

## 4. Particles

- Each particle has a stable id and seeded properties (birth time, lifetime, colour, size). Its position is a function of `t − birth` (closed form or baked). Do not spawn particles from frame-dependent randomness.
- Motion fields: curl noise (divergence-free) for ink, smoke and fluid-like drift; gravity + drag for sparks; attraction to target points for particles forming a shape (assign each particle a target point by a fixed mapping so gathering is traceable).
- Fading: alpha by age; trails by drawing the last few positions (computed from `t`), not by leaving the previous frame on the canvas.
- Many particles: Canvas 2D handles ~10–50k small rects; beyond that use WebGL points / `InstancedMesh` or GPU computation in a shader.

## 5. Shaders and fields

- A fragment shader driven only by a `uTime` uniform (and resolution) is naturally deterministic; pass `t`, not a clock.
- fbm noise, domain warping and ray-marched layers make clouds, aurora curtains, water and fire. Add tiny dithering to gradients to avoid banding in 8-bit output.
- For loops, make noise periodic: sample 4D noise on a circle (`cos(2πt/T), sin(2πt/T)`) or blend two offsets.

## 6. Simulations that must loop

A free-running simulation never returns exactly to its first state, so design the loop in:

- **Scheduled agents:** give vehicles, pedestrians and trains routes and departure times that repeat with the loop period (an agent leaving the frame at the end is replaced by the same agent entering at the start of its next cycle). Compute each agent's position as a function of `t mod period` plus its offset, with rules (stopping at lights, keeping gaps) resolved inside that periodic schedule.
- **Global state cycles:** time of day, weather and lighting are periodic functions of `t`, and per-object switches (windows on and off) use seeded times within one period.
- **Particles:** a particle whose life ends is reborn with the same parameters one period later; its age is `(t − birth) mod period`.
- **Fields:** use periodic noise (sampled on a circle in an extra dimension).
- Verify by comparing the state at `t = period` with `t = 0`; they must match exactly.

## 7. Making rules look good

- Choose the moment: start the camera on the interesting structure (the gun, the flock's edge), and widen to show the emergent pattern.
- Colour encodes state (age, speed, newly born, recently dead) to make the rule visible.
- Keep the background quiet; a simulation is usually busy enough.

## 8. Checks

Invariant report printed and within tolerance; frame strips at 0.1 s around the fastest events (no pops, no respawn flicker); determinism test: render the same frame twice in different orders and compare pixels (they must be identical).
