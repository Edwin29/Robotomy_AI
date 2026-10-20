using UnityEngine;
using UnityEngine.UI;

// Display identity only: no creature IDs, hidden names, AI targets or combat timers.
public static class ConsoleEntity {
 public static bool Anchor(CreatureUnit unit,ConsoleUI ui,Camera cam,out Vector3 world,out Rect rect){
  world=Vector3.zero;rect=new Rect();var t=unit==null?null:unit.escapeCreatureName;
  if(t==null || string.IsNullOrEmpty(t.text) || !ui.VisibleWorldLabel(t,out rect))return false;
  float depth=cam.WorldToScreenPoint(t.transform.position).z;if(depth<=0)return false;
  world=cam.ScreenToWorldPoint(new Vector3(rect.center.x,rect.center.y,depth));return true;
 }
 public static string Capture(UnityEngine.Object owner,ConsoleUI ui){
  string kind=owner is AgentUnit?"employee":owner is WorkerUnit?"worker":owner is CreatureUnit?"creature":"projectile";
  string name="null";var unit=owner as CreatureUnit;Rect r;
  if(unit!=null && unit.escapeCreatureName!=null && ui.VisibleWorldLabel(unit.escapeCreatureName,out r) && unit.escapeCreatureName.cachedTextGenerator.characterCountVisible>=unit.escapeCreatureName.text.Length)
   name=RobotomyObserver.Quote(unit.escapeCreatureName.text);
  return "{\"kind\":"+RobotomyObserver.Quote(kind)+",\"name\":"+name+"}";
 }
}
