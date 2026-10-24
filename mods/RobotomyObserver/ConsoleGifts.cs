using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;
// Gift state comes from the displayed slot and lock sprite, never the inventory model.
public static class ConsoleGifts {
 static void Value(Rect r,string text,string id,string role,List<ViewRect> output){output.Add(new ViewRect{text=text,panel="gift",row_id=id,role=role,x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height});}
 static void Control(ConsoleUI ui,Button b,string id,string role,string label,List<ViewRect> texts,List<ViewRect> buttons,Transform surface){
  Rect r;if(b==null || b.image==null || !ui.VisibleSurface(b.image,surface,out r))return;
  Value(r,b.IsInteractable()?"true":"false",id,role+"_available",texts);
  ConsoleReading.Click(ui,b.image,b.gameObject,id,role,label,buttons,surface,"gift");
 }
 public static void Capture(ConsoleUI ui,List<ViewRect> texts,List<ViewRect> buttons){
  var w=AgentInfoWindow.currentWindow;if(w==null || !w.gameObject.activeInHierarchy)return;
  var name=ConsoleReading.Add(ui,w.UIComponents.AgentName,"gift","window","employee",texts,w.transform);
  if(name==null)name=ConsoleReading.Add(ui,w.inGameModeComponent.AgentName,"gift","window","employee",texts,w.transform);
  if(name==null)return;
  foreach(var b in w.GiftAreaActiveButton)Control(ui,b,"window","open","E.G.O GIFT 목록",texts,buttons,w.transform);
  var g=w.giftWindow;if(g==null || !g.gameObject.activeInHierarchy)return;
  foreach(var slot in g.slots){
   if(slot==null || !slot.gameObject.activeInHierarchy)continue;
   string id=name.text+":"+slot.GetInstanceID().ToString();var n=ConsoleReading.Add(ui,slot.GiftName,"gift",id,"name",texts,slot.transform);if(n==null)continue;
   ConsoleReading.Add(ui,slot.RegionName,"gift",id,"region",texts,slot.transform);
   ConsoleReading.Add(ui,slot.GiftDescription,"gift",id,"description",texts,slot.transform);
   Rect rect;var b=slot.LockButton;
   if(b!=null && b.image!=null && ui.VisibleSurface(b.image,slot.transform,out rect)){
    var sprite=b.image.overrideSprite;string state=sprite==slot.Lock_Close?"true":sprite==slot.Lock_Open?"false":"unknown";
    Value(rect,state,id,"locked",texts);
   }
   Control(ui,b,id,"lock","기프트 잠금 전환: "+n.text,texts,buttons,slot.transform);
  }
 }
}
