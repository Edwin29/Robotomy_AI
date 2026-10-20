# Visible facility status

`facility_map.visible[].status` adds transient presentation state to the existing fixed facility ID. The persistent atlas and `read_facility_map` contain geometry only.

- `warning_light`: `red` when the authored EscapeFrame warning branch is active and visible, `off` when that branch is inactive, null when absent or not observable. Off does not mean no enemies.
- `surface_effects`: visible SefiraFilterMgr sprite layers, each with an opaque art identity and the label 통로 표면 효과. No internal creature names, damage, occupancy targets, or hidden threat list. This describes the effect, not its inferred cause.
- Existing camera/unlock and UI gate applies. No status for offscreen landmarks. Normal diff replaces the facility map section when state changes.

## Shipped-code evidence

Assembly-CSharp.decompiled.cs: PassageWayObject.Update (188088+) activates EscapeFrame when entered CreatureModel is ESCAPE and its script IsSensoredInPassage returns true; it inversely toggles LightObjects. Several scripts override the sensor predicate. We read the resulting display branch, not this hidden membership list.
PassageObject.SetPassageFilter (187987+) creates a SefiraFilterMgr under the passage shader parent. SefiraFilterMgr.Init/SetAlpha (238447+) controls the actual SpriteRenderer layers. Display adapters read those renderers.
Representative callers: 1.76MHz noise (139974), FireBird surface (127942), Shark surface (151844), Yggdrasil surface (159986), Rabbit protocol (188003). These names remain engineering evidence only. There is no single common occupied flag established by this audit. Other special effects using different display paths remain outside current coverage.
ElevatorPassageObject (195442+) moves the platform only; it does not define a universal warning field. Its containing passage may or may not have the authored warning branch. Missing branch is null, never a fabricated safe state.

## Verification

Lab runtime comparison passed: baseline off; two red-warning corridors matched screenshots after lab-only MachineDawnOrdeal spawn; one actual Noise2 surface matched a visible noise patch after lab-only renderer injection. ESC menu removed all current facility entries. Persistent atlas contained no warning/status data. 222 unit tests and 44-tool MCP smoke passed. Test fixtures cover state disappearance offscreen, no persistence, field whitelist and diff. Lab-only effect injection is a renderer test, not natural abnormality progression.


Production applied 2026-10-19: official private launcher confirmed live PID 8168; original integrity check passed, all six isolated save .dat/.dat.backup hashes unchanged. Player guide updated in repository and external player workspace. No new tool schema; facility decoder is in the hot-reload module set. Existing connections established before the prior map-tool addition still need that earlier catalog reconnect. Engineering lab was normally closed.
