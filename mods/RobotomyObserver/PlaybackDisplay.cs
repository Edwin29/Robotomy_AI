using UnityEngine;
using UnityEngine.UI;

// Shipped Main PlaySpeedButtonAnimCTRL binding, audited in level2 and runtime.
// The Button targetGraphic is a transparent input plane; Icon/InnerFill are
// animated display children. Names here are asset bindings, not employee IDs,
// screen coordinates or inferred gameplay state.
public sealed class PlaybackDisplay {
    public readonly Button button;
    public readonly Image icon, fill;
    PlaybackDisplay(Button b,Image i,Image f){button=b;icon=i;fill=f;}
    public static PlaybackDisplay Resolve(Button button) {
        if(button==null || button.transition!=Selectable.Transition.Animation)return null;
        var i=button.transform.Find("Icon");var f=button.transform.Find("InnerFill");
        var icon=i==null?null:i.GetComponent<Image>();var fill=f==null?null:f.GetComponent<Image>();
        return icon==null||fill==null?null:new PlaybackDisplay(button,icon,fill);
    }
    public bool Selected { get {
        // Disabled animation is also the hover palette. The public control's
        // interactable flag disambiguates selected from merely hovered.
        if(button.interactable || !fill.isActiveAndEnabled || fill.canvasRenderer.cull)return false;
        Color i=icon.color*icon.canvasRenderer.GetColor(), f=fill.color*fill.canvasRenderer.GetColor();
        return i.a>.99f && i.r<.03f && i.g<.03f && i.b<.03f &&
            f.a>.99f && Mathf.Abs(f.r-1)<.03f && Mathf.Abs(f.g-.5803922f)<.03f && Mathf.Abs(f.b-.254902f)<.03f;
    }}
    public static bool IsPlayback(PlaySpeedSettingUI ui,Button b) {
        return ui!=null && (b==ui.PauseButton||b==ui.NormalSpeed||b==ui.OneHalfSpeed||b==ui.TwiceSpeed);
    }
    public static string Label(PlaySpeedSettingUI ui,Button b) {
        return b==ui.PauseButton?"paused":b==ui.NormalSpeed?"1x":b==ui.OneHalfSpeed?"1.5x":"2x";
    }
}
