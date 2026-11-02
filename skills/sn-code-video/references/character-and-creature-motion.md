# Character and creature motion

*When to read:* Make people, animals and story characters actually perform in code: jointed 2D or 3D rigs, walk/run/trot/gallop cycles with planted feet, jumps and catches, anticipation-action-settle phases, props held and handed over, group stagger, expressions, and cuts that continue motion. Use for any film where a figure walks, runs, jumps, reaches, reacts or tells a story (mannequins, dogs, kids' picture-book characters, MV characters).

Viewers forgive simple shapes but not dead motion. The weak pattern is always the same: a still image of a figure slid across the screen with a little bob, poses that switch instantly at a time threshold, and story actions that exist only in the plan. A figure made of a few primitives that moves with real phases reads as alive.

## 1. Rig, not pictures

- Build every acting figure as a joint hierarchy: pelvis → spine → chest → neck → head; shoulders → elbows → wrists; hips → knees → ankles (animals: front and hind legs with upper, lower and paw segments; neck, head, tail chain). Parts are primitives (capsules, spheres, rounded boxes in 3D; filled paths in 2D) parented to joints.
- Pose = a set of joint angles. Animate by blending poses with easing, never by swapping pose sets with `if (t > x)`.
- Proportions decide recognition: check the silhouette at final size (a dog needs a snout, ears, a tail and a deep chest; a child character a big head and short limbs).
- Bend joints only in their natural direction and range (knees backwards never; elbows within ~0–150°).

## 2. One performance in world time

Write each character's state as a function of global time: position, facing, pose, held props. Cameras and cuts look at that one world. A cut never resets a character's position or the progress of an action.

## 3. Phases of every action

Anticipation (a small move away from the goal) → action → contact on the key moment → overshoot and settle → a hold that stays alive (breathing, blink, small sway) → eased release. A jump crouches before take-off and absorbs on landing; a catch reaches before the object arrives; a surprise takes a short beat before the reaction.

## 4. Locomotion

- **Planted feet:** while a foot bears weight, its world position is fixed. Drive the gait phase from distance travelled, not from time: `phase = distance / strideLength`. If speed changes, the cycle slows with it, and feet never slide.
- **Walk:** always one foot on the ground; opposite arm and leg swing together; pelvis rises at mid-stance and dips at contact.
- **Run / sprint:** flight phase between steps; knee drive forward; arms bent ~90° and swinging opposite; torso leaning slightly forward.
- **Hurdle or jump:** lead leg extends forward, trail leg tucks out sideways, torso leans forward; land on the lead leg and continue into the next stride.
- **Quadruped trot:** diagonal leg pairs move together (left-front with right-hind).
- **Quadruped gallop:** hind legs push off close together, front legs reach, a suspension phase; the spine flexes and extends; ears and tail lag behind.
- **Small 2D characters (picture books):** a simple bounce walk is fine only if feet land; add squash on landing and stretch on take-off.

Use simple IK for legs (two-bone, analytic) so feet reach the ground on slopes and steps, and for hands that grip props.

## 5. Props and contacts

- A held object is parented to the hand (or jaw) from the moment of contact and stays there; it is never drawn independently near the hand.
- Hand-overs interpolate from one hand to the other at a contact frame. Thrown objects follow a ballistic arc; caught objects attach exactly at the catch point.
- Things leave the frame by moving, not by vanishing.

## 6. Faces and acting (2D or stylized)

- A few elements carry emotion: eye shape, brow angle, mouth curve, head tilt. Check brow direction at final size: worried and angry differ only in which end of the brow is raised.
- Emotions change through the story; transitions between expressions take 4–8 frames.
- Secondary motion: blink every 2–5 s at seeded times, breathing in holds, hair, ears and cloth lag slightly behind the body.

## 7. Groups

Characters react 4–8 frames after the cause; members of a group start the same action 3–6 frames apart, with small variation in speed and pose. Crowds: vary height, colour and walking speed; steer around each other; no two overlapping.

## 8. Checks

- **Action strips:** for every key action, frames 0.1 s apart from anticipation to settle. Look for sliding feet, popping poses, limbs passing through the body or props, and objects jumping between hands.
- **Foot-slide test:** track a planted foot's world position over its stance frames; it should not move more than a few millimetres (or 1–2 px in 2D).
- **Motion audit:** no stretch of more than ~1.5 s where the main character is completely still, except a deliberate hold with breathing.
- **Silhouette test:** a frame converted to a flat dark silhouette still reads as the intended creature or action.
