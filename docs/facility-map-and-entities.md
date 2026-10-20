# Facility map and visible entity adapters

Status: deployed to production private runtime on 2026-10-19; existing player MCP connections must reconnect for the expanded catalog.

## Player contract

`facility_map.known` is remembered geometry, outside the expiring frame buffer. It contains:

- stable `id`, fixed `map_position` (x right, y up), space kind and department label;
- direct `connections` with neighbor IDs, labels, relative direction and delta;
- `layout_top_to_bottom`, with each horizontal band ordered left to right;
- `relative_to_lobby` when the department's central room has been observed.

Bands are geometric rows, not invented official floor numbers. Nearby spaces are not implicitly connected. Connections are remembered ordinary structural links, not live promises that a staff member can traverse them during every special event. No hidden teleport routes, future departments, enemy destinations or A* cost tables are exported.

`facility_map.visible` is the current camera's usable set. `click` is current client-pixel input; never use `map_position` as screen pixels. An absent landmark is not presently actionable. Remembering it does not unlock or reveal it. Historical geometry remains after a camera move or restarting the game; current input always resolves anew.

Player tools (new catalog requires MCP reconnect):

- `read_facility_map()` reads persistent remembered layout without waiting for a frame.
- `click_facility(facility_id, rationale='')` resolves a fresh visible point and uses existing virtual input. Containment rooms use left-click. Corridors/central rooms use right-click; select staff first. Elevator shafts have no native click collider and are read-only landmarks: choose a connected landing/corridor as destination.

Neither tool chooses routes, selects staff, changes the camera or runs a policy. They are device conveniences. Input receipt is not proof of movement. Internal capture for fixed-ID input is not recorded as an observation offered to the player; the action result is recorded separately.

## Shipped structure

Evidence: `.robotomy/analysis/Assembly-CSharp.decompiled.cs`:

- `PassageObject` 187722: visible wrapper, actual UnitMouseEventTarget and collider.
- `PassageObjectModel` 204622: authored PassageType and node list.
- `SefiraObject.InitAreaActivate` 300498: unlock gates activate the passage GameObject.
- `MapNode.GetEdges`, `GetAttachedPassage`, `MapEdge.ConnectedNode`; GraphAstar 99660 follows destination `activate`, not MapEdge.activated.
- `IsolateRoom.TargetUnit.model.roomNode`: room-to-passage structural attachment only; no creature hidden stats read.
- `ElevatorPassageModel` 195157: moving lift platform is separate from fixed shaft and landing graph.
- Actual Lab Malkuth/Yesod prefab probe: many corridors/central rooms leave `sefiraFrame` null. Their authored `Frame`, `PassageHub_Frame`, `ElevatorPassage_Frame` sprite branches provide visibility. Elevators have no UnitMouseEventTarget collider.

Only visible active display anchors enter the map. A new ordinary connection is learned only when both spaces and connection endpoints are in view. Static geometry is learned independently of the transient data buffer. Writes use the existing background publisher, coalesce, and retry periodically without blocking game input. Serialized data is restored using shipped SharpJson; Unity JsonUtility did not restore the nested atlas reliably in this build.

Department names use the same localization lookup as the game's deployment UI, only for admitted visible spaces. Locked areas are not enumerated. Camera effects use the existing display guard. Room input uses its actual EventTrigger; no dependency on tiny label legibility for an otherwise visible clickable room.

## Entity channel

`visible_entities` provides nonemployee body track IDs, visible names if shown, screen position/bounds, screen/object/camera velocity. CreatureUnit covers ordinary creatures, OrdealCreatureModel and SefiraBossCreatureModel display inheritance. No hidden model names, vitals, targets or attack timers are returned. Unsupported non-Spine display branches remain a coverage limit; all bosses have not been runtime verified.

Small creature display presence uses known rendered mesh/texture alpha samples rather than requiring an entire conservative anisotropic footprint to be opaque. This is practical display detection, not a pixel-perfect general occlusion renderer. UI masks, camera effects, active render state and stencil checks remain. Static facility artwork is not treated as an arbitrary opaque blocker in this fallback. Boss-specific effects still need representative validation.

## Deployment

Candidate DLL, host and MCP catalog: `.robotomy/patches/facility-entities-20261019/`.
Do not deploy `Lab.dll`, `LabObserver.cs` or `LabFacilityProbe.cs`: these contain engineering-only probes/spawn triggers. Production candidate is `RobotomyObserver.dll`.

The production host now includes `facility` in its generation modules and exposes both map tools. Existing clients must reconnect once for the expanded catalog. The private production game was normally closed from DAY 8 preparation and relaunched through the integrity-checked launcher.

## Verification 2026-10-19

- Lab DAY6: 24 observed spaces and 24 direct connections, including Malkuth/Yesod central rooms, corridors, elevator shafts and containment attachments.
- Re-launch at title: 24 spaces / 24 links restored; zero currently visible/actionable spaces.
- Same fixed containment ID after camera pan resolved to new pixels; clicking opened the expected Welchs command window. Offscreen containment rejected before any input.
- ESC menu: zero visible facility entries and zero creature tracks; remembered map retained 24 entries.
- Lab-only explicitly spawned real MachineDawnOrdeal bodies: 22 samples / 66 creature vector samples; camera movement and nonzero object movement both observed. Screen = object + camera decomposition error 0 at exported precision. This is a representative runtime check, not proof of all creature/boss art or exact pixel occlusion.
- Small-body presence fallback still uses a representative textured mesh point; do not interpret its 2x2 bounds as the entire creature outline or a guaranteed suppression click point.
- Python map decode benchmark, 200 repetitions: median 0.14 ms, maximum 0.385 ms. Excludes game capture/model latency.
- Full unittest suite: 220 passed; MCP stdio smoke passed. Candidate generation listed both new tools and read an empty map correctly (35 tools including two host controls).
- Production PID 32852 and DLL SHA256 0bc824be8dd5c16ed4d68bf110cb29b2d17354b1ddc8699303b9d1ba72842c22 unchanged. Original-game integrity checks at lab launch passed.
- Actual selected-staff arrival at a fixed-ID destination was not established in this run. Native right-click input was delivered; existing game selection/order rules still apply.


## Production application 2026-10-19 21:10 KST

- Production DLL SHA256: `e2155c9c167bc92868121cead52d349d1972f60546f9779d5bdd1cbab56347c6`. No Lab probe/spawn assembly deployed.
- Backup: `.robotomy/backups/production-facility-20261019T210825/` (isolated save, previous DLL, manifest, host/catalog and guides).
- Previous process normally closed from DAY 8 preparation; official launcher started PID 17440. Left at title, live, without starting the next management day.
- Original save/integrity verification passed. All isolated `.dat` and `.dat.backup` hashes unchanged across close/deploy/relaunch.
- Live producer publishes facility-map contract. At title, remembered and visible landmarks are empty; no laboratory discoveries were imported.
- Fresh ReloadHost lists 35 tools including read_facility_map/click_facility; persistent-map read succeeds. Existing player chat connection has not been reconnected by this operation.
- Updated config/player/AGENTS.md and external Robotomy_Player/AGENTS.md with fixed IDs, graph relationships, coordinate conventions and visible-entity use.
- Tests: 220 unittest cases; standard MCP smoke 44 tools; reload smoke 35 tools with change/error/recovery checks.
- Runtime motion/map behavior remains backed by the lab verification above; production gameplay was not advanced to repeat those tests.
- Machine-readable report: `.robotomy/verification/facility-production-deployment.json`.
