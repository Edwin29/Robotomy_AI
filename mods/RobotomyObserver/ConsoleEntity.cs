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
 public static string Capture(UnityEngine.Object owner,ConsoleUI ui,Camera cam,Vector2 pixel){
  string kind=owner is AgentUnit?"employee":owner is WorkerUnit?"worker":owner is CreatureUnit?"creature":"projectile";
  string name="null";var unit=owner as CreatureUnit;Rect r;
  if(unit!=null && unit.escapeCreatureName!=null && ui.VisibleWorldLabel(unit.escapeCreatureName,out r) && unit.escapeCreatureName.cachedTextGenerator.characterCountVisible>=unit.escapeCreatureName.text.Length)
   name=RobotomyObserver.Quote(unit.escapeCreatureName.text);
  string click="null",bar="null";Vector2 point;
  Vector3 anchor;Rect anchorRect;
  if(unit!=null && Anchor(unit,ui,cam,out anchor,out anchorRect) && ConsoleEmployee.TryClick(unit,cam,pixel,out point))
   click="{\"x\":"+RobotomyObserver.Number(point.x)+",\"y\":"+RobotomyObserver.Number(Screen.height-point.y)+"}";
  // The public slider can be repurposed by creature scripts. Describe a displayed
  // gauge, not exact model HP or an inferred death/ability timer.
  if(unit!=null && unit.hpSlider!=null && unit.hpFill!=null && ui.VisibleWorldGraphic(unit.hpFill,out r)){
   var c=unit.hpFill.color;
   bar="{\"ratio\":"+RobotomyObserver.Number(unit.hpSlider.normalizedValue)+",\"color\":{\"r\":"+RobotomyObserver.Number(c.r)+",\"g\":"+RobotomyObserver.Number(c.g)+",\"b\":"+RobotomyObserver.Number(c.b)+"}}";
  }
  return "{\"kind\":"+RobotomyObserver.Quote(kind)+",\"name\":"+name+",\"click\":"+click+",\"display_bar\":"+bar+"}";
 }
}
