using UnityEngine;using UnityEngine.UI;

// Room HUD is an authored display above the facility renderers. Its own frames
// are not independent obstructions. ConsoleUI checks activity, clipping, camera
// bounds and external UI layers; this gate rejects unsupported camera effects.
public static class ConsoleWorldLabels {
 public static bool Clear(Graphic label,Rect patch){
  if(label.canvas.renderMode!=RenderMode.WorldSpace)return true;
  Camera cam=ConsoleUI.DisplayCamera(label.canvas);
  return cam!=null && cam==Camera.main && ConsoleMotion.CameraGuard(cam)=="";
 }
}
