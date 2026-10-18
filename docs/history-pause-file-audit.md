# Count-bounded history pause gate: shipped-file audit

Date: 2026-10-18 (KST). Engineering evidence only. This audit reads the installed
game and existing observer sources; it does not change the game, input, or saves.
Scratch-style automation remains deferred.

## Source identity

- Installed `LobotomyCorp_Data/Managed/Assembly-CSharp.dll` SHA-256:
  `fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd`.
- Retained `.robotomy/analysis/Assembly-CSharp.decompiled.cs` SHA-256:
  `3f5b8d807af9b2f416a0499455014ac601f62dcc121ca07cec88d20b39f828af`.
- Both hashes rechecked during this audit. Line references below refer to that
  retained decompilation; proprietary code stays outside Git.

## Exact game behavior

| Evidence | Consequence |
| --- | --- |
| `GameState` at 179636 has `PLAYING`, `STOP`, `PAUSE`; `GameManager.Awake` at 179692 starts in `STOP`. | Lack of an explicit pause is not proof that management is running. |
| `GameManager.FixedUpdate` at 180116 calls the creature, ordeal, officer, agent, and other simulation managers only inside `state == GameState.PLAYING` (180119–180132). | This state is the narrow internal criterion for management-history accumulation. |
| `UpdateGameSpeed` at 179978 assigns normal speeds while playing and `Time.timeScale = 0f` when paused (180003–180005). | A positive time scale is a second guard against actual simulation freeze. |
| `Pause()` and `Resume()` at 180044–180053 change the state and update speed. | Ordinary pause/resume is directly represented by the state. |
| `TutorialPause()` at 180089 changes only the state; `TutorialResume()` at 180094 changes it back. | Testing only `Time.timeScale` would miss a valid state-only freeze path. |
| Tutorial `Pause`/`Resume` at 251984–251997 use `PlaySpeedSettingUI.OnPause/OnResume(PAUSECALL.TUTORIAL)`. | The ordinary tutorial controller reaches the same game-state gate. |
| `PlaySpeedSettingUI.OnPause` at 277034–277052 disables the visible pause filter for tutorial and roulette, then calls `GameManager.Pause(caller)`. | A visible pause overlay is not a reliable gate. |
| `PlaySpeedSettingUI.Update` at 276838 returns immediately in tutorial mode; other modes check restrictions before handling Space (276858–276881). | Blind Space injection cannot be assumed to test tutorial pause. Preserve actual game restrictions. |
| `ClearAction` at 180187 sets time scale to zero and calls `EndGame`; `EndGame` at 180102 sets `STOP`. | Ended management must not push stationary frames into gameplay history. |

## Recommended minimal gate

Evaluate once, on the Unity main thread, for each collected sample:

```csharp
var manager = GameManager.currentGameManager;
bool accumulate = manager != null
    && manager.state == GameState.PLAYING
    && Time.timeScale > 0f;
```

Unknown/absent manager, `STOP`, `PAUSE`, or a zero time scale freeze history.
This is a storage gate, not a command: it never calls `Pause`, `Resume`,
`SetPlaySpeed`, or a boss-specific method. No timer/expiry scheduler is needed.
The ring evicts the oldest item only when a new eligible item exceeds its count
capacity. Timestamps remain useful for alignment and motion, not deletion.

Always collect/publish the latest observation and latest frame independently of
this gate. Camera/menu changes remain observable while paused. A scene boundary
must start a distinct history context or clear the old ring, so old scene data
cannot be mistaken for current data. Preserve explicit historical timestamps,
session identifiers, and sequence numbers.

If publication is asynchronous, copy `accumulate` into the immutable capture
work item. A worker must not inspect Unity objects or decide using a later game
state. Already captured pre-pause items may finish publication after the pause;
the count should settle once those bounded pending jobs drain. Do not create new
paused captures for the history queue. Latest-state publication remains active.

## Privacy and operator pause

Do not export `PAUSECALL`, its priority, blocked caller lists, boss flags,
`BossEvent`, or the reason that time controls are unavailable. None is needed to
apply this gate. Player-facing history may state whether accumulation is active
as a device status, but must not attach hidden game causes. Structured records
and their associated images still use the existing display-only filtering.

The operator `control/PAUSED` marker is separate: `VirtualInput.Update` at
`mods/RobotomyObserver/VirtualInput.cs:163` releases virtual input when it exists.
It does not pause the simulation. Never use it as the history gate, and never
remove it to make a storage test pass.

Read-only runtime check during this audit: private copied game PID 32912 at
`.robotomy/runtime/LobotomyCorp/LobotomyCorp.exe`, scene `Tutorial_1`, input marker
present with `operator stop`. Existing observation schema does not report the
actual game-state gate, so this alone does not prove the simulation is paused.
No input was sent and no runtime state was modified.

## Acceptance and testing boundary

1. Pure gate cases: missing manager; each enum state; playing with zero/positive
   time scale; paused with positive time scale (the state-only tutorial case).
2. Pure ring tests: count cap, oldest-first eviction, no mutation while frozen,
   resume append, timestamp preservation, and distinct scene/session identity.
3. With an actual paused game, show latest sequence/frame changes while the
   history count and oldest/newest retained capture identifiers remain stable.
   Allow the bounded publication queue to drain before asserting stability.
4. A real pause/resume transition must use the game's legitimate input paths and
   verify the displayed result. It is separate from a synthetic gate test and
   requires the parent/operator's existing live-input authorization boundary.
5. Existing `MotionProbe` changes only render fixtures. It cannot prove actual
   game pause behavior. Do not add direct `GameManager` mutation to that fixture
   or label a synthetic state sequence as gameplay validation.

This audit establishes the gate from shipped-file logic. Runtime verification
of the new history producer still has to be reported separately.
