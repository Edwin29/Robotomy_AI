using GlobalBullet;
using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;using UnityEngine.EventSystems;

// State decoding is explicitly authorized only after visible-surface/name gating.
// Death roster is the user-authorized off-camera exception; no positions or vitals.
public static class ConsoleEmployee {
 static string Q(string s){return RobotomyObserver.Quote(s);}
 static string Label(ConsoleUI ui,Text t){Rect r;return t!=null && ui.VisibleWorldLabel(t,out r) && t.cachedTextGenerator.characterCountVisible>=t.text.Length?Q(t.text):"null";}
 public static bool Anchor(AgentUnit unit,ConsoleUI ui,Camera cam,out Vector3 world,out Rect rect){
  world=Vector3.zero;rect=new Rect();if(unit==null || cam==null)return false;
  Text label=unit.ui==null?null:unit.ui.Name;
  if(label==null || !ui.VisibleWorldLabel(label,out rect)){
   label=unit.agentUI==null?null:unit.agentUI.Name;
   if(label==null || !ui.VisibleWorldLabel(label,out rect)){
    // AutoUIHider disables Name at zoom >= its authored threshold. The
    // independently rendered title remains visible in the shipped Day 11 HUD.
    label=unit.ui==null?null:unit.ui.title;
    if(label==null || !ui.VisibleWorldLabel(label,out rect))return false;
   }
  }
  var p=rect.center;float depth=cam.WorldToScreenPoint(label.transform.position).z;if(depth<=0)return false;
  world=cam.ScreenToWorldPoint(new Vector3(p.x,p.y,depth));return true;
 }
 public static string Capture(AgentUnit unit,ConsoleUI ui,Camera cam,Vector2 pixel){
  if(unit==null)return "null";
  string name=unit.ui==null?"null":Label(ui,unit.ui.Name);
  var hud=unit.agentUI;if(name=="null" && hud!=null)name=Label(ui,hud.Name);
  // Identity of an already visible employee is allowed at distant zoom, too.
  // This is not a claim that the disabled name text is readable on screen.
  // Restrict this fallback to the actual zoom hider, never an inactive HUD.
  var nameLabel=unit.ui==null?null:unit.ui.Name;
  var hider=nameLabel==null?null:nameLabel.GetComponent<Optimization.AutoUIHider>();
  Rect titleRect;
  if(name=="null" && nameLabel!=null && nameLabel.gameObject.activeInHierarchy && !nameLabel.enabled &&
     hider!=null && hider.isActiveAndEnabled && hider.targetGraphic==nameLabel &&
     unit.ui.title!=null && ui.VisibleWorldLabel(unit.ui.title,out titleRect))name=Q(nameLabel.text);
  string status=Status(unit.model);
  // UI selection membership, not hover/pinned AgentInfoWindow or a state-dependent tint.
  // Capture is reached only for a currently visible employee.
  bool selected=false;var mouse=UnitMouseEventManager.instance;
  if(mouse!=null)foreach(var target in mouse.seletedtargets)if(target!=null && target.target==unit)selected=true;
  return "{\"selected\":"+(selected?"true":"false")+",\"name\":"+name+",\"status\":"+Q(status)+",\"hp_bar\":"+Bar(hud,hud==null?null:hud.HpFill,ui)+",\"sp_bar\":"+Bar(hud,hud==null?null:hud.MentalFill,ui)+",\"click\":"+(status=="dead"?"null":Click(unit,cam,pixel))+"}";
 }
 static string Bar(InGameUI.AgentUI hud,Image fill,ConsoleUI ui){
  Rect rect;
  if(hud==null || hud.ActiveControl==null || !hud.ActiveControl.activeInHierarchy || hud.BlackHide==null || hud.BlackHide.gameObject.activeInHierarchy ||
     fill==null || fill.type!=Image.Type.Filled || fill.fillMethod!=Image.FillMethod.Horizontal || !ui.VisibleWorldGraphic(fill,out rect))return "null";
  int total=Math.Max(1,(int)Math.Round(rect.width));
  int filled=(int)Math.Round(Mathf.Clamp01(fill.fillAmount)*total);
  return "{\"ratio\":"+RobotomyObserver.Number((float)filled/total)+",\"filled_pixels\":"+filled+",\"total_pixels\":"+total+"}";
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
 public static bool TryClick(Component unit,Camera cam,Vector2 pixel,out Vector2 point){
  point=Vector2.zero;
  var es=EventSystem.current;if(es==null)return false;
  // OnPointerClick dispatches to bullets before ordinary selection.
  if(UnitMouseEventManager.instance==null || UnitMouseEventManager.instance.DefaultClickBlocked ||
     (GlobalBulletWindow.CurrentWindow!=null && GlobalBulletWindow.CurrentWindow.CurrentSelectedBullet!=GlobalBulletType.NONE))return false;
  var points=new List<Vector2>();points.Add(new Vector2(pixel.x,Screen.height-pixel.y));
  foreach(var target in unit.GetComponentsInChildren<UnitMouseEventTarget>()){
   if(!System.Object.ReferenceEquals(target.target,unit))continue;var collider=target.GetComponent<Collider2D>();
   if(collider!=null && collider.enabled){
    var p=cam.WorldToScreenPoint(collider.bounds.center);if(p.z>0)points.Add(p);
    // Try separate visible parts of the actual hit collider when units overlap.
    foreach(float dx in new float[]{-.35f,.35f})foreach(float dy in new float[]{-.35f,.35f}){
     var q=cam.WorldToScreenPoint(collider.bounds.center+new Vector3(collider.bounds.size.x*dx,collider.bounds.size.y*dy,0));
     if(q.z>0)points.Add(q);
    }
   }
  }
  foreach(var p in points){
   if(p.x<0 || p.y<0 || p.x>=Screen.width || p.y>=Screen.height)continue;
   bool own=false,other=false;
   foreach(var col in Physics2D.OverlapPointAll(cam.ScreenToWorldPoint(p))){var t=col.GetComponent<UnitMouseEventTarget>();if(t==null)continue;if(System.Object.ReferenceEquals(t.target,unit))own=true;else if(t.target is IMouseOnSelectListener)other=true;}
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
