using GlobalBullet;
using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;using UnityEngine.EventSystems;

// State decoding is explicitly authorized only after visible-surface/name gating.
// Death roster is the user-authorized off-camera exception; no positions or vitals.
public static class ConsoleEmployee {
 static string Q(string s){return RobotomyObserver.Quote(s);}
 static string Label(ConsoleUI ui,Text t){Rect r;return t!=null && ui.VisibleWorldLabel(t,out r) && t.cachedTextGenerator.characterCountVisible>=t.text.Length?Q(t.text):"null";}
 public static bool Anchor(AgentUnit unit,ConsoleUI ui,Camera cam,out Vector3 world,out Rect rect){
  world=Vector3.zero;rect=new Rect();if(unit==null || unit.ui==null || unit.ui.Name==null || !ui.VisibleWorldLabel(unit.ui.Name,out rect))return false;
  var p=rect.center;float depth=cam.WorldToScreenPoint(unit.ui.Name.transform.position).z;if(depth<=0)return false;
  world=cam.ScreenToWorldPoint(new Vector3(p.x,p.y,depth));return true;
 }
 public static string Capture(AgentUnit unit,ConsoleUI ui,Camera cam,Vector2 pixel){
  if(unit==null)return "null";
  string name=unit.ui==null?"null":Label(ui,unit.ui.Name);
  var hud=unit.agentUI;if(name=="null" && hud!=null)name=Label(ui,hud.Name);
  string status=Status(unit.model);
  // Shipped AgentUI.SetSelectState paints the visible HUD texture orange.
  var texture=hud==null?null:hud.Texture;Rect selectedRect;
  bool selected=texture!=null && ui.VisibleWorldLabel(hud.Name,out selectedRect) && texture.enabled && texture.gameObject.activeInHierarchy &&
   Mathf.Abs(texture.color.r-1f)<.005f && Mathf.Abs(texture.color.g-.5803922f)<.005f && Mathf.Abs(texture.color.b-13f/51f)<.005f && texture.color.a>.05f;
  return "{\"selected\":"+(selected?"true":"false")+",\"name\":"+name+",\"status\":"+Q(status)+",\"click\":"+(status=="dead"?"null":Click(unit,cam,pixel))+"}";
 }
 public static string Status(AgentModel model){
  if(model==null)return "unknown";
  if(model.IsDead())return "dead";
  if(model.IsPanic())return "panic";
  if(model.IsCrazy())return "uncontrollable";
  if(model.IsSuppressing())return "suppressing";
  if(model.GetState()==AgentAIState.MANAGE)return model.currentSkill==null?"moving":"working";
  if(model.GetMovableNode()!=null && model.GetMovableNode().IsMoving())return "moving";
  return model.GetState()==AgentAIState.IDLE?"idle":"unknown";
 }
 public static string DeadRoster(){
  var rows=new List<string>();var manager=AgentManager.instance;
  if(manager==null || UnityEngine.SceneManagement.SceneManager.GetActiveScene().name!="Main")return "[]";
  foreach(var model in manager.GetAgentList())if(model!=null && model.IsDead())
   rows.Add("{\"employee_id\":"+Q(model.instanceId.ToString())+",\"name\":"+Q(model.GetUnitName())+",\"status\":\"dead\"}");
  return "["+String.Join(",",rows.ToArray())+"]";
 }

 static string Click(AgentUnit unit,Camera cam,Vector2 pixel){
  Vector2 point;if(!TryClick(unit,cam,pixel,out point))return "null";
  return "{\"x\":"+RobotomyObserver.Number(point.x)+",\"y\":"+RobotomyObserver.Number(Screen.height-point.y)+"}";
 }
 public static bool TryClick(AgentUnit unit,Camera cam,Vector2 pixel,out Vector2 point){
  point=Vector2.zero;
  var es=EventSystem.current;if(es==null)return false;
  // OnPointerClick dispatches to bullets before ordinary selection.
  if(UnitMouseEventManager.instance==null || UnitMouseEventManager.instance.DefaultClickBlocked ||
     (GlobalBulletWindow.CurrentWindow!=null && GlobalBulletWindow.CurrentWindow.CurrentSelectedBullet!=GlobalBulletType.NONE))return false;
  var points=new List<Vector2>();points.Add(new Vector2(pixel.x,Screen.height-pixel.y));
  foreach(var target in unit.GetComponentsInChildren<UnitMouseEventTarget>()){
   if(target.target!=unit)continue;var collider=target.GetComponent<Collider2D>();
   if(collider!=null && collider.enabled){var p=cam.WorldToScreenPoint(collider.bounds.center);if(p.z>0)points.Add(p);}
  }
  foreach(var p in points){
   if(p.x<0 || p.y<0 || p.x>=Screen.width || p.y>=Screen.height)continue;
   bool own=false,other=false;
   foreach(var col in Physics2D.OverlapPointAll(cam.ScreenToWorldPoint(p))){var t=col.GetComponent<UnitMouseEventTarget>();if(t==null)continue;if(t.target==unit)own=true;else if(t.target is IMouseOnSelectListener)other=true;}
   if(!own || other)continue;
   var data=new PointerEventData(es);data.position=p;var hits=new List<RaycastResult>();es.RaycastAll(data,hits);if(hits.Count==0)continue;
   var handler=ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject);var trigger=handler==null?null:handler.GetComponent<EventTrigger>();if(trigger==null)continue;
   bool routed=false;foreach(var entry in trigger.triggers)if(entry.eventID==EventTriggerType.PointerClick)
    for(int i=0;i<entry.callback.GetPersistentEventCount();i++)if(entry.callback.GetPersistentTarget(i) is UnitMouseEventManager && entry.callback.GetPersistentMethodName(i)=="OnPointerClick")routed=true;
   if(routed){point=p;return true;}
  }
  return false;
 }
}
