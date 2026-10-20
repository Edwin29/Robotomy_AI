using UnityEngine;

// UI disclosure only: never reads research, creature models, cumulative counters or backing values.
// Passing this policy is necessary, not sufficient: ConsoleUI still checks rendered geometry/effects.
public static class ConsoleDisclosure
{
    static bool Within(Transform candidate, Transform root) {
        return candidate != null && root != null && (candidate == root || candidate.IsChildOf(root));
    }
    static bool Within(Transform candidate, Component root) {
        return root != null && Within(candidate, root.transform);
    }
    static bool Within(Transform candidate, GameObject root) {
        return root != null && Within(candidate, root.transform);
    }
    static string Cover(Transform candidate, GameObject cover, string reason) {
        if (cover == null) return "missing_" + reason;
        return cover.activeInHierarchy && !Within(candidate, cover) ? reason : null;
    }
    static string Equipment(Transform candidate, CreatureInfo.EquipSlot slot) {
        if (slot == null || slot.ActiveControl == null) return "missing_equipment_slot";
        if (!Within(candidate, slot.ActiveControl)) return null;
        return Cover(candidate, slot.BlockControl, "equipment_lock");
    }
    static string CommandCounters(Transform candidate, CommandWindow.CommandWindow command) {
        // Policy excludes cumulative use/time fields even if a future layout makes them visible.
        var kit = command.kitCreatureRegion;
        if (kit == null || kit.UseCountText == null || kit.UseCountTitleText == null)
            return "missing_tool_counter_refs";
        return Within(candidate, kit.UseCountText) || Within(candidate, kit.UseCountTitleText)
            ? "tool_cumulative_counter" : null;
    }
    public static bool Allows(Transform candidate) { return RejectReason(candidate) == null; }
    public static string RejectReason(Transform candidate) {
        if (candidate == null || !candidate.gameObject.activeInHierarchy) return "inactive_display";
        string reason;
        var hud = candidate.GetComponentInParent<InGameUI.AgentUI>();
        if (hud != null) {
            // BlackHide is a sibling overlay; fillAmount continues updating under it.
            if (hud.BlackHide == null) return "missing_hud_cover";
            if (hud.BlackHide.gameObject.activeInHierarchy && !Within(candidate,hud.Name) && !Within(candidate,hud.BlackHide)) return "hud_cover";
        }
        var command = candidate.GetComponentInParent<CommandWindow.CommandWindow>();
        if (command != null) {
            reason = CommandCounters(candidate, command); if (reason != null) return reason;
        }
        // The controller and its referenced display root need not share a parent chain.
        // CurrentWindow is a UI reference only; no CurrentTarget/model state is consulted.
        var currentCommand = CommandWindow.CommandWindow.CurrentWindow;
        if (currentCommand != null && currentCommand != command && Within(candidate, currentCommand.RootControl)) {
            reason = CommandCounters(candidate, currentCommand); if (reason != null) return reason;
        }
        var agent = candidate.GetComponentInParent<CommandWindow.AgentSlot>();
        if (agent != null) {
            if (agent.HealthText == null || agent.MentalText == null || agent.HealthFill == null || agent.MentalFill == null)
                return "missing_command_vitals_refs";
            if (Within(candidate, agent.HealthFill) || Within(candidate, agent.MentalFill))
                return "command_vitals_unverified";
        }
        var kitStat = candidate.GetComponentInParent<CreatureInfo.CreatureInfoKitStatRoot>();
        if (kitStat != null) {
            reason = Cover(candidate, kitStat.Open == null ? null : kitStat.Open.gameObject, "tool_identity_lock");
            if (reason != null) return reason;
        }
        var kitRow = candidate.GetComponentInParent<CreatureInfo.CreatureInfoKitDataSlot>();
        if (kitRow != null) {
            reason = Cover(candidate, kitRow.disabled, "tool_record_lock");
            if (reason != null) return reason;
        }
        var equipment = candidate.GetComponentInParent<CreatureInfo.CreatureInfoEquipmentRoot>();
        if (equipment != null) {
            reason = Equipment(candidate, equipment.giftSlot); if (reason != null) return reason;
            reason = Equipment(candidate, equipment.weaponSlot); if (reason != null) return reason;
            reason = Equipment(candidate, equipment.armorSlot); if (reason != null) return reason;
        }
        // Preserve normal observation locks and fail closed if their required cover was detached.
        var stat = candidate.GetComponentInParent<CreatureInfo.CreatureInfoStatRoot>();
        if (stat != null) {
            reason = Cover(candidate, stat.Open == null ? null : stat.Open.gameObject, "observation_lock");
            if (reason != null) return reason;
        }
        var escape = candidate.GetComponentInParent<CreatureInfo.CreatureInfoEscapeRoot>();
        if (escape != null) {
            reason = Cover(candidate, escape.Open == null ? null : escape.Open.gameObject, "observation_lock");
            if (reason != null) return reason;
            reason = Cover(candidate, escape.BlockActiveControl, "escape_display_cover");
            if (reason != null) return reason;
        }
        var work = candidate.GetComponentInParent<CreatureInfo.CreatureInfoWorkSlot>();
        if (work != null) {
            reason = Cover(candidate, work.Open == null ? null : work.Open.gameObject, "observation_lock");
            if (reason != null) return reason;
        }
        var care = candidate.GetComponentInParent<CreatureInfo.CreatureInfoCaretakingSlot>();
        if (care != null) {
            reason = Cover(candidate, care.Open == null ? null : care.Open.gameObject, "observation_lock");
            if (reason != null) return reason;
        }
        // Covers can be siblings rather than ancestors. Only the nearest enclosing section applies.
        for (Transform parent = candidate; parent != null; parent = parent.parent) {
            if (parent.GetComponent<CreatureInfoController>() == null) continue;
            foreach (var open in parent.GetComponentsInChildren<CreatureInfo.CreatureInfoOpenArea>(true)) {
                reason = Cover(candidate, open.gameObject, "observation_lock");
                if (reason != null) return reason;
            }
            foreach (var open in parent.GetComponentsInChildren<CreatureInfo.CreatureInfoKitOpenArea>(true)) {
                reason = Cover(candidate, open.gameObject, "tool_identity_lock");
                if (reason != null) return reason;
            }
            break;
        }
        return null;
    }
}
