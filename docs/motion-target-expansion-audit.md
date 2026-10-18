# Display motion target expansion — 2026-10-18

## Evidence first

Read-only evidence was reused from `.robotomy/analysis/Assembly-CSharp.decompiled.cs`.
Original installed game DLL SHA-256 was rechecked:
`fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd`.
Retained decompile SHA-256:
`3f5b8d807af9b2f416a0499455014ac601f62dcc121ca07cec88d20b39f828af`.
Neither binary, assets nor decompiled copyrighted source is added to Git.

| Shipped path | Source location | Consequence |
| --- | --- | --- |
| `CreatureLayer.AddOrdealCreature` | decompile 296678 | Ordeal creatures use ordinary `CreatureUnit` and its `animTarget`; no separate per-Ordeal model adapter is needed. |
| `CreatureLayer.AddEventCreature` | 296696 onward | Event creatures also use this display component. |
| `ChildCreatureUnit : CreatureUnit` | 296173 | Derived children follow the same candidate path. |
| `ProjectileUnit.UpdateViewPosition` | 299322 | Model position is converted to final display transform; door transit can hide it at z=100000. Consume the transform and existing clip filter, never the model position. |
| `KnightOfDespiarThrowedSword : ProjectileUnit` | 165548 | A derived projectile changes a child visual transform; using only controller position misses that displacement. |
| `SlimeGirlProjectile.FixedUpdate` | 167575 | Moves `_effect`, not necessarily its controller. |
| `MagicalGirlWeaponProjectile.FixedUpdate` | 175441 | Moves explicit `_effect` visual branch. |
| `SlimeGirlWeaponProjectile.FixedUpdate` | 175961 | Moves explicit `_effect` visual branch. |
| `BinahBoss.BinahProjectile`, `GeburahProjectile` | 224106, 224566 | Explicit `animator` visual roots. Internal velocity, target, lifetime and attack fields are deliberately unused. |
| `SkeletonRenderSeparator.AddToSkeletonRenderer` | 340990 | Split mesh renderers are children of the skeleton; deduplicate to one display target. |

These are static code observations, not proof that every prefab uses a currently
supported material/mesh. In particular, this does not assert that every projectile
uses Spine, nor that all lasers, particles, attacks or boss scenes are supported.

## Implementation

`MotionTargets.cs` indexes the already-collected renderer array. Nearest supported
component ownership is memoized only for the current capture and also reused by
the occlusion broad phase and individual surface checks. There are no additional
per-family `FindObjectsOfType` scene scans. New spawning, reparenting and destruction
are reconsidered next capture; this avoids stale cross-frame ownership caches.

Candidates must belong to the component's explicit visual branch. Arbitrary unit
children such as health bars and selection markers are not admitted. All Spine
branches in that visual root are considered; the old implementation only selected
the primary `animator.GetComponent<SkeletonRenderer>()` for a creature.

Each candidate anchors to its actual skeleton transform. This follows visual child
translation, rotation and scaling, rather than a possibly stationary controller.
The vector remains the displacement of a retained visible surface sample, not a
hidden movement stat or a claim of attack-motion recognition. A changed surface,
occlusion, large discontinuity or projection failure still reacquires/withholds.

Nearest projectile ownership wins over an enclosing creature/worker, so a nested
projectile cannot automatically be ignored as part of its parent's own body during
cover checks. Multiple Spine parts of the same owner retain the existing self-cover
policy. No internal names, target type or model fields enter player JSON.

The existing camera/profile, material, actual mesh, alpha, stencil, UI cover and
offscreen checks are unchanged. Unsupported body renderers are only counted in
engineering diagnostics (`unsupported_body_renderers`). The existing 128 accepted
track limit remains; no broader capacity/performance claim is made.

## Verification and limits

- Full observer source compiled against the actual copied game-managed assemblies
  to ignored `.robotomy/build-check/RobotomyObserver-targets.dll`. This is an offline
  reference/API check, not a deployed runtime result.
- `python -m unittest discover -s tests -p test_motion_targets.py -v` passed. It
  compiles the production adapter with a minimal hierarchy fixture and executes
  14 assertions: split deduplication, multiple creature branches, derived children,
  nested derived projectile ownership, moving-child anchor, five standalone roots,
  exclusion of unrelated/UI branches, unsupported bodies, absent visual root,
  and ownership changes after reparenting.
- The fixture validates adapter selection/lifetime only. It does not simulate
  Unity rendering, visibility or game behavior.
- No game restart, input, original file/save modification or profile relaxation
  was performed for this subtask.

Runtime acceptance still requires a safe private-runtime launch, existing occlusion
probe rerun, tutorial before/after visual-vector comparison, and measured scene
cost. Real Ordeal/abnormality/projectile acceptance requires a suitable isolated
scene and a separately verified render profile; the current tutorial profile must
not be silently expanded. Unsupported SpriteRenderer/particle/laser paths need
their own final-display geometry/material audit before being exposed.

## Actual-Unity synthetic fixture

`MotionTargetsProbe.Begin(directory)` is an explicit engineering-only fixture,
triggered by the observer's marker handler. It creates its own opaque quad mesh,
texture and material and attaches render-only subclasses of the actual shipped
`CreatureUnit`, `ChildCreatureUnit` and `ProjectileUnit` types. The subclasses
override gameplay lifecycle callbacks, including destruction: the shipped
Creature/Child destruction callbacks dereference model fields even when disabled.
No game model or existing prefab is created, modified or registered.

The fixture emits `motion-targets-probe.json` and per-case PNGs for 13 checks:
three visible component-type positives; stationary vectors; a moving display child
under a stationary controller; camera-only motion; combined camera/object motion;
disabled-renderer withdrawal and reacquisition; offscreen withdrawal and
reacquisition; opaque-UI withdrawal and reacquisition. Camera offsets are applied
before the real camera renders, then restored; this avoids validating projection
against an image from before a camera mutation.

`ConsoleMotion.ProbeActive` remains enabled through teardown and the first clean
rendered frame, excluding synthetic observations from the public history. Previous
flag state is restored. Exception cleanup removes the camera callback and owned
objects. Running this fixture proves the actual Unity display path for these
synthetic types, not a real Ordeal prefab, animation, later-stage profile or player
achievement. At creation time the fixture compiled successfully; runtime result
must be read from the generated report before claiming any checks passed.

### Initial runtime fixture interpretation failure

The first actual report marked only the three negative checks true. It must not be
reported as 13 passed. Inspection of the raw snapshots and PNGs nevertheless showed
all three synthetic squares and their acquired tracks at matching image locations.
The moving-child record contained an 8px movement and +61.5px/s object velocity with
zero camera velocity; camera-only contained -49.7px/s camera velocity and zero object
velocity; the combined case contained +75.98px/s object and -75.98px/s camera with zero
screen velocity. The rejection diagnostics referred to ordinary worker atlas patches,
not these synthetic objects.

This isolates the false verdicts to the fixture's interpretation/matching path;
the first report did not include decoded fields, so a specific Unity serializer bug
is not proven. The fixture now uses `MotionProbeSnapshot` to decode the device's
fixed generated JSON schema, with explicit null-vector handling, and writes projected
expected centers plus decoded counts for independent audit. The actual decoder is
executed in an offline C# test with decimal/negative coordinates, null vectors and
empty arrays. Production visibility/candidate/vector logic was not weakened.

### Final actual-Unity result (2026-10-18 KST)

All 13 checks passed with the corrected decoder in private PID33144. The final DLL
SHA256 is `6ed15a77a95aca69b716abc4de4b65bb490db151da08c501bfca0c3757cc7383`.
Visible cases decoded three tracks; disabled/offscreen cases decoded two; opaque
UI decoded zero; reacquisition restored three. Captured PNGs were inspected for
the display-child movement and full-screen cover cases.

An intervening run began while the scene's loading overlay was still visible;
its positive cases correctly had no visible tracks and the test failed. Scene
name alone is not a sufficient readiness check. The final run followed visual
confirmation of the first tutorial dialogue. Both failed reports were retained
under `.robotomy/live/verification/history/`; `final-motion-targets.json` contains
the final raw report and source/DLL hashes. No visibility rule was bypassed.

This verifies synthetic actual-Unity display components only. Actual late-game
Ordeal/Boss prefabs, sprite-only bodies, and other scene/effect profiles remain
outside the verified coverage.
