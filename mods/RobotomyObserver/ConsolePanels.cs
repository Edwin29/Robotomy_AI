using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

// Candidate roots only. ConsoleUI must still apply disclosure, final geometry,
// clipping, occlusion, text completeness and camera-effect checks every frame.
// No model values, event callbacks, story logs or stored tooltip strings are read.
public sealed class ConsolePanels
{
    public sealed class Entry
    {
        public readonly GameObject root;
        public readonly string source;
        public Entry(GameObject root, string source) { this.root = root; this.source = source; }
    }

    readonly List<Entry> entries = new List<Entry>();
    readonly HashSet<GameObject> roots = new HashSet<GameObject>();
    float refreshed = -10;

    void Add(GameObject root, string source)
    {
        if (root != null && roots.Add(root)) entries.Add(new Entry(root, source));
    }

    void Add(Text text, string source)
    {
        if (text != null) Add(text.gameObject, source);
    }

    public IList<Entry> Capture()
    {
        if (Time.realtimeSinceStartup - refreshed < 1f) return entries;
        refreshed = Time.realtimeSinceStartup;
        entries.Clear(); roots.Clear();

        // Exact public display references; never invoke methods that build or
        // advance the game's UI. Inactive roots are harmless candidates only.
        var command = CommandWindow.CommandWindow.CurrentWindow;
        if (command != null) Add(command.RootControl, "command");

        var mission = MissionUI.instance;
        if (mission != null && mission.listParent != null)
            foreach (var slot in mission.listParent.GetComponentsInChildren<MissionSlot>(true))
                Add(slot.txt, "mission");
        var popup = MissionPopupUI.instance;
        if (popup != null) {
            Add(popup.missionNameText, "mission");
            Add(popup.missionDescText, "mission");
            Add(popup.missionTeamNameText, "mission");
            Add(popup.missionDiagText, "mission");
        }

        // This is the visible system log, not Unity's console or SystemLoggerUI.
        // Only the actual LoggingScript display parent may supply log rows.
        // Multiple active SystemLogScript controllers are unverified: withhold.
        var logs = Object.FindObjectsOfType<SystemLogScript>();
        if (logs.Length == 1 && logs[0].script != null && logs[0].script.parent != null)
            foreach (var row in logs[0].script.parent.GetComponentsInChildren<LogItemScript>(true))
                Add(row.textTarget, "notice");

        // Several simultaneous communications are legitimate. Do not derive
        // speaker names from component types, enums, portraits or asset names.
        foreach (var conversation in Object.FindObjectsOfType<ConversationUI>())
            Add(conversation.InnerText, "notice");
        var angela = AngelaConversationUI.instance;
        if (angela != null) Add(angela.messageText, "notice");

        var tooltip = OverlayManager.Instance;
        if (tooltip != null) Add(tooltip.OverlayText, "tooltip"); // excludes _debugText and prev

        var bullets = GlobalBullet.GlobalBulletWindow.CurrentWindow;
        if (bullets != null) {
            Add(bullets.CurrentUsableBulletCount, "bullets");
            Add(bullets.BulletCountMax, "bullets");
        }
        return entries;
    }
}
