using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;using UnityEngine.EventSystems;

// Resolve the authored IsolateRoom.OnClick event, not a HUD label position.
public static class ConsoleRoomClick {
 public static string Capture(IsolateRoom room,string method="OnClick"){
  var es=EventSystem.current;if(es==null)return "null";
  foreach(var trigger in room.GetComponentsInChildren<EventTrigger>()){
   bool roomClick=false;
   foreach(var entry in trigger.triggers){
    if(entry.eventID!=EventTriggerType.PointerClick)continue;
    for(int i=0;i<entry.callback.GetPersistentEventCount();i++)
     if(entry.callback.GetPersistentTarget(i)==room && entry.callback.GetPersistentMethodName(i)==method)roomClick=true;
   }
   if(!roomClick || !trigger.isActiveAndEnabled)continue;
   var rect=trigger.GetComponent<RectTransform>();var canvas=trigger.GetComponentInParent<Canvas>();Rect area;
   if(rect==null || canvas==null || !ConsoleUI.ScreenRect(rect,canvas,out area))continue;
   // Centre first, then inset points when another UI control occupies the centre.
   float[] offsets={.5f,.25f,.75f};
   foreach(float y in offsets)foreach(float x in offsets){
    var p=new Vector2(area.xMin+area.width*x,area.yMin+area.height*y);
    if(p.x<0 || p.y<0 || p.x>=Screen.width || p.y>=Screen.height)continue;
    var data=new PointerEventData(es);data.position=p;var hits=new List<RaycastResult>();es.RaycastAll(data,hits);
    if(hits.Count==0 || ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject)!=trigger.gameObject)continue;
    return "{\"x\":"+RobotomyObserver.Number(p.x)+",\"y\":"+RobotomyObserver.Number(Screen.height-p.y)+",\"target_id\":"+RobotomyObserver.Quote(trigger.GetInstanceID().ToString())+",\"input_verified\":true}";
   }
  }
  return "null";
 }
}
