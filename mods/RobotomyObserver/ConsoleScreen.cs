using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;using UnityEngine.EventSystems;

// References to rendered UI only. No calls which construct results, unlock options or advance story.
public static class ConsoleScreen {
 public static bool Text(ConsoleUI ui,Text t,string panel,string row,string role,List<ViewRect> rows){
  Rect r;if(t==null || String.IsNullOrEmpty(t.text))return false;
  var aw=AgentInfoWindow.currentWindow;
  if(!(panel=="selection" && aw!=null ? ui.VisibleCommandGraphic(t,aw.transform,out r) : ui.VisibleStory(t,out r)))return false;
  var value=t.supportRichText?System.Text.RegularExpressions.Regex.Replace(t.text,"<[^>]*>",""):t.text;
  if(value.Length>2048 || t.cachedTextGenerator.characterCountVisible<value.Length)return false;
  rows.Add(new ViewRect{text=value,panel=panel,row_id=row,role=role,x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height});return true;
 }
 static void State(string value,string role,ViewRect anchor,List<ViewRect> rows){
  rows.Add(new ViewRect{text=value,panel="screen",row_id="current",role=role,x=anchor.x,y=anchor.y,width=anchor.width,height=anchor.height});
 }
 static void Root(ConsoleUI ui,GameObject root,string panel,List<ViewRect> rows,List<ViewRect> buttons){
  if(root==null || !root.activeInHierarchy)return;
  foreach(var t in root.GetComponentsInChildren<Text>())Text(ui,t,panel,t.GetInstanceID().ToString(),"display_text",rows);
  foreach(var b in root.GetComponentsInChildren<Button>()){
   if(!b.isActiveAndEnabled || !b.IsInteractable())continue;
   var t=b.GetComponentInChildren<Text>();Rect r;
   if(t!=null && ui.VisibleStory(t,out r))Action(ui,b.gameObject,t,t.text,panel,"action",buttons);
  }
  // Expansion and legacy UI use EventTrigger rather than Button.
  foreach(var trigger in root.GetComponentsInChildren<EventTrigger>()){
   bool click=false;foreach(var e in trigger.triggers)if(e.eventID==EventTriggerType.PointerClick && e.callback.GetPersistentEventCount()>0)click=true;
   if(!click)continue;
   foreach(var t in trigger.GetComponentsInChildren<Text>())if(!String.IsNullOrEmpty(t.text))Action(ui,trigger.gameObject,t,t.text,panel,"action",buttons);
  }
 }
 public static void Action(ConsoleUI ui,GameObject go,Graphic face,string label,string panel,string role,List<ViewRect> buttons){
  Rect r;var es=EventSystem.current;
  if(go==null || face==null || es==null || !go.activeInHierarchy || !ui.VisibleStory(face,out r))return;
  var d=new PointerEventData(es);d.position=r.center;var hits=new List<RaycastResult>();es.RaycastAll(d,hits);
  if(hits.Count==0 || ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject)!=go)return;
  buttons.RemoveAll(x=>x.target_id==go.GetInstanceID().ToString());
  buttons.Add(new ViewRect{text=label,panel=panel,row_id=go.GetInstanceID().ToString(),role=role,
   x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height,hit_x=r.center.x,hit_y=Screen.height-r.center.y,
   target_id=go.GetInstanceID().ToString(),input_verified=true,interactable=true});
 }
 public static void Capture(ConsoleUI ui,List<ViewRect> rows,List<ViewRect> buttons){
  var dep=DeployUI.instance;
  if(dep!=null && dep.canvas!=null && dep.canvas.isActiveAndEnabled){
   Root(ui,dep.canvas.gameObject,"preparation",rows,buttons);
   Text(ui,dep.dayCount,"preparation","summary","day",rows);Text(ui,dep.pointCount,"preparation","summary","lob",rows);
   Text(ui,dep.OrdealText,"preparation","summary","ordeal",rows);
  }
  foreach(var ex in UnityEngine.Object.FindObjectsOfType<ExpandUI>())Root(ui,ex.ActiveContorl,"expansion",rows,buttons);
  foreach(var rs in UnityEngine.Object.FindObjectsOfType<ResultScreen>()){
   if(rs.root==null || !rs.root.activeInHierarchy)continue;
   Root(ui,rs.root,"result",rows,buttons);
   var p=rs.report;if(p==null)continue;
   Text(ui,p.day,"result","summary","day",rows);Text(ui,p.gatheredEnergy,"result","summary","energy",rows);
   Text(ui,p.Rank,"result","summary","rank",rows);Text(ui,p.Reward,"result","summary","reward",rows);
   Text(ui,p.workerPromoted,"result","summary","promoted",rows);
   if(p.workerDead.Length>0)Text(ui,p.workerDead[0],"result","summary","dead",rows);
   if(p.workerAlive.Length>0)Text(ui,p.workerAlive[0],"result","summary","alive",rows);
   foreach(var b in p.buttons){
    if(b==null || b.button==null)continue;
    string action=b.index==1?"retry":b.index==2?"next_day":b.index==3 || b.index==5?"confirm":b.index==4 || b.index==6?"cancel":null;
    if(action==null)continue;
    // ReportButton is wired through ResultScreen.OnPointerClicK by EventTrigger.
    foreach(var trigger in b.button.GetComponentsInChildren<EventTrigger>()){
     bool wired=false;
     foreach(var e in trigger.triggers)if(e.eventID==EventTriggerType.PointerClick)
      for(int i=0;i<e.callback.GetPersistentEventCount();i++)if(e.callback.GetPersistentTarget(i)==rs && e.callback.GetPersistentMethodName(i)=="OnPointerClicK")wired=true;
     if(wired)foreach(var g in b.button.GetComponentsInChildren<Graphic>())Action(ui,trigger.gameObject,g,action,"result",action,buttons);
    }
   }
   var anchor=rows.FindLast(x=>x.panel=="result");
   if(anchor!=null && ((p.nextDayClicked!=null && p.nextDayClicked.activeInHierarchy)||(p.returnClicked!=null && p.returnClicked.activeInHierarchy)))State("confirmation","modal",anchor,rows);
  }
  var aw=AgentInfoWindow.currentWindow;
  if(aw!=null && aw.UIComponents!=null)Text(ui,aw.UIComponents.AgentName,"selection","panel","displayed_name",rows);
  if(aw!=null && aw.inGameModeComponent!=null)Text(ui,aw.inGameModeComponent.AgentName,"selection","panel","displayed_name",rows);
  var command=CommandWindow.CommandWindow.CurrentWindow;
  var enemy=command==null?null:command.CretureSuppress;
  if(enemy!=null){
   string[] types={"unknown","red","white","black","pale"};
   for(int i=0;i<enemy.RWBPAttackType.Length && i<types.Length;i++){
    var g=enemy.RWBPAttackType[i];if(g==null || !g.activeInHierarchy)continue;
    foreach(var image in g.GetComponentsInChildren<Image>()){
     Rect r;if(command.RootControl==null || !ui.VisibleCommandGraphic(image,command.RootControl.transform,out r))continue;
     rows.Add(new ViewRect{text=types[i],panel="enemy",row_id="selected",role="attack_"+types[i],x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height});break;
    }
   }
  }
  foreach(var choice in UnityEngine.Object.FindObjectsOfType<StorySelectionOptionUI>())
   if(choice.textUI!=null)Action(ui,choice.gameObject,choice.textUI,choice.textUI.text,"story","choice",buttons);
  var story=rows.Find(x=>x.panel=="story");
  var result=rows.Find(x=>x.panel=="result");var expansion=rows.Find(x=>x.panel=="expansion");var prep=rows.Find(x=>x.panel=="preparation");
  var operation=rows.Find(x=>x.panel=="playback" || x.panel=="energy");
  var basis=result??expansion??prep??story??operation;
  if(basis!=null)State(result!=null?"result":expansion!=null?"expansion":prep!=null?"preparation":story!=null?"story":"management","base",basis,rows);
  var research=rows.Find(x=>x.panel=="research");
  if(research!=null)State(rows.Exists(x=>x.panel=="research" && x.role=="confirmation")?"research_confirmation":"research","modal",research,rows);
 }
}
