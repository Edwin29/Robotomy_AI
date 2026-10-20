# Entity-to-facility display location

The existing screen position and screen/object/camera velocities remain unchanged. `facility_location` joins a currently visible motion track to a currently visible facility ID, with its label/department/kind, `map_position` in fixed world xy, continuous `relative.u/v` and facility display `extent.width/height`.

u=0 is left, u=1 right; v=0 bottom, v=1 top. These are continuous coordinates, not three bins. The reference rectangle is the authored visible facility frame (containment room sprite for rooms), not the pathfinding walk line. Sampled body/label anchors can extend beyond it; values are not clamped or claimed as precise feet positions. Existing click coordinates are the input channel; never pass u/v or map_position to pixel input.

Game structure: WorkerUnit.workerModel and CreatureUnit.model inherit UnitModel.GetMovableNode; currentPassage identifies the current space. Only its match against this capture's visible facility registry is used; no destination/path/hidden roster data. Unknown/unseen space yields null. Projectiles without this owner association remain null. The display registry rebuilds before motion each capture and never persists dynamic entity locations. The sampled rendered anchor is used for coordinates, not the hidden model position.

Art evidence: read-only ResourceManager mapping to shipped Texture2D/Sprite resources; exported inspection images under .robotomy/verification/surface-art. The inspected textures show black/white static, flames with embers, rainbow waves, and green mist with luminous particles. Source creature names, damage, cause and mechanics are not player labels. Unknown art remains unclassified. These four labels describe textures, not full boss effect coverage.

## Verification

224 unit tests and MCP 44-tool smoke passed. Lab DAY6 real displayed employee and spawned ordeal body were associated with observed central room/corridor. Lab injected Noise2 texture was labeled 흑백 노이즈. With game paused, camera pan shifted screen x by about -92.94 pixels while four retained tracks kept the same facility ID; maximum relative-u drift 0.000000267. ESC menu removed all current facilities/tracks. Evidence: Robotomy_Lab/.robotomy/verification/location-runtime.json, location-camera.json and PNG. Natural boss progression and every effect animation were not tested.
