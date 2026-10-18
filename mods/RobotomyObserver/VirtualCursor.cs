using UnityEngine;

// Cursor requests from the game belong to its virtual device. They must never
// confine, hide or replace the human's desktop cursor. No OS input is injected.
public static class VirtualCursor
{
    static CursorLockMode requestedLock;
    static bool requestedVisible = true;
    public static void set_lockState(CursorLockMode value) { requestedLock = value; }
    public static CursorLockMode get_lockState() { return requestedLock; }
    public static void set_visible(bool value) { requestedVisible = value; }
    public static bool get_visible() { return requestedVisible; }
    public static void SetCursor(Texture2D texture, Vector2 hotspot, CursorMode mode) { }
}
