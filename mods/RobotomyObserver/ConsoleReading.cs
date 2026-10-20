using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;using UnityEngine.EventSystems;

// Read rendered Text and active UI slots only. No equipment models, private
// selection flags, locked descriptions or localization tables enter observations.
public static class ConsoleReading {
 static ViewRect Item(Rect r,string text,string panel,string id,string role){return new ViewRect{text=text,panel=panel,row_id=id,role=role,x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height};}
 static string Plain(Text t){return t.supportRichText?System.Text.RegularExpressions.Regex.Replace(t.text,"<[^>]*>",""):t.text;}
 static ViewRect Add(ConsoleUI ui,Text t,string panel,string id,string role,List<ViewRect> output,Transform surface=null){
  Rect r;if(t==null || String.IsNullOrEmpty(t.text) || !(surface==null?ui.Visible(t,out r):ui.VisibleSurface(t,surface,out r)))return null;
  string plain=Plain(t);if(plain.Length>2048 || t.cachedTextGenerator.characterCountVisible<plain.Length)return null;
  if(t.supportRichText && System.Text.RegularExpressions.Regex.IsMatch(t.text,@"<(size|color)\b",System.Text.RegularExpressions.RegexOptions.IgnoreCase))return null;
  var v=Item(r,plain,panel,id,role);output.Add(v);return v;
 }
 static void Click(ConsoleUI ui,Graphic graphic,GameObject expected,string id,string role,string label,List<ViewRect> buttons,Transform surface=null){
  Rect r;var es=EventSystem.current;if(es==null || graphic==null || !ui.VisibleHitSurface(graphic,surface,out r))return;
  var data=new PointerEventData(es);data.position=r.center;var hits=new List<RaycastResult>();es.RaycastAll(data,hits);
  if(hits.Count==0)return;var target=ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject);
  if(target==null || target!=expected)return;
  var button=target.GetComponent<Button>();if(button!=null && !button.IsInteractable())return;
  var trigger=target.GetComponent<EventTrigger>();if(button==null && (trigger==null || !trigger.triggers.Exists(x=>x.eventID==EventTriggerType.PointerClick)))return;
  var v=Item(r,label,"ego",id,role);v.interactable=true;v.input_verified=true;v.target_id=target.GetInstanceID().ToString();v.hit_x=r.center.x;v.hit_y=Screen.height-r.center.y;buttons.Add(v);
 }
 static void Button(ConsoleUI ui,Button b,string id,string role,List<ViewRect> buttons,Transform surface=null){
  if(b==null || !b.isActiveAndEnabled)return;
  foreach(var t in b.GetComponentsInChildren<Text>()){Rect r;if(!ui.VisibleHitSurface(t,surface??b.transform,out r))continue;Click(ui,t,b.gameObject,id,role,Plain(t),buttons,surface??b.transform);break;}
 }
 public static void Capture(ConsoleUI ui,List<ViewRect> texts,List<ViewRect> buttons){
  var win=Inventory.InventoryUI.CurrentWindow;
  if(win!=null && win.gameObject.activeInHierarchy){
   var ctl=win.ItemController;
   foreach(var slot in win.GetComponentsInChildren<Inventory.InventorySlot>()){
    string id=slot.GetInstanceID().ToString();var name=Add(ui,slot.Name,"ego",id,"name",texts);if(name==null)continue;
    Add(ui,slot.Grade,"ego",id,"grade",texts);
    var weapon=slot as Inventory.InventoryWeaponSlot;
    if(weapon!=null){Add(ui,weapon.Type,"ego",id,"damage_type",texts);Add(ui,weapon.DamageRange,"ego",id,"damage",texts);Add(ui,weapon.AttackSpeed,"ego",id,"attack_speed",texts);Add(ui,weapon.Range,"ego",id,"range",texts);}
    var armor=slot as Inventory.InventoryArmorSlot;
    // Shipped DefenseInfo/DefenseFactor arrays use UIUtil's displayed RWBP order.
    string[] kinds={"red","white","black","pale"};
    if(armor!=null)for(int i=0;i<4;i++){if(i<armor.DefenseInfo.Length)Add(ui,armor.DefenseInfo[i],"ego",id,"resist_"+kinds[i],texts);if(i<armor.DefenseFactor.Length)Add(ui,armor.DefenseFactor[i],"ego",id,"factor_"+kinds[i],texts);}
    foreach(var owner in slot.ownerSlot){
     var n=Add(ui,owner.AgentName,"ego",id,"owner",texts,owner.transform);
     Click(ui,owner.Texture,owner.gameObject,id,"equipment_slot",n==null?"장비 슬롯":n.text,buttons,owner.transform);
    }
    Button(ui,slot.TooltipButton,id,"details",buttons);
   }
   if(win.SefiraController!=null)foreach(var agent in win.SefiraController.GetComponentsInChildren<Inventory.InventoryAgentSlot>()){
    var n=Add(ui,agent.AgentName,"ego","agents","owner",new List<ViewRect>(),agent.transform);
    if(n!=null)Click(ui,agent.Texture,agent.gameObject,"agents","select_agent",n.text,buttons,agent.transform);
   }
   var selected=win.AgentController;
   if(selected!=null && selected.gameObject.activeInHierarchy && selected.AgentSlot!=null){
    Add(ui,selected.AgentSlot.AgentName,"ego","selected","selected_name",texts,selected.AgentSlot.transform);
    Add(ui,selected.WeaponTitle,"ego","selected","weapon_name",texts);
    Add(ui,selected.WeaponGrade,"ego","selected","weapon_grade",texts);
    Add(ui,selected.TypeText,"ego","selected","weapon_damage_type",texts);
    Add(ui,selected.DamageText,"ego","selected","weapon_damage",texts);
    Add(ui,selected.ArmorTitle,"ego","selected","suit_name",texts);
    Add(ui,selected.ArmorGrade,"ego","selected","suit_grade",texts);
    string[] types={"red","white","black","pale"};
    for(int i=0;i<4;i++){
     if(i<selected.DefenseType.Length)Add(ui,selected.DefenseType[i],"ego","selected","suit_resist_"+types[i],texts);
     if(i<selected.DefenseFactor.Length)Add(ui,selected.DefenseFactor[i],"ego","selected","suit_factor_"+types[i],texts);
    }
   }
   if(ctl!=null){Button(ui,ctl.WeaponButton,"tabs","tab",buttons,win.transform);Button(ui,ctl.ArmorButton,"tabs","tab",buttons,win.transform);}
  }
  var record=CreatureInfoWindow.CurrentWindow;
  if(record==null || record.DescriptionPanel==null || !record.DescriptionPanel.gameObject.activeInHierarchy)return;
  foreach(var t in record.descList)Lines(ui,t,texts);
 }
 static void Lines(ConsoleUI ui,Text t,List<ViewRect> output){
  if(t==null || !t.isActiveAndEnabled || String.IsNullOrEmpty(t.text) || t.canvas==null || t.pixelsPerUnit<=0)return;
  // Source paragraphs use plain text. Styled text needs separate character-to-mesh mapping.
  if(t.supportRichText && System.Text.RegularExpressions.Regex.IsMatch(t.text,@"</?(b|i|size|color|material|quad)(\s|=|>)",System.Text.RegularExpressions.RegexOptions.IgnoreCase))return;
  var gen=t.cachedTextGenerator;var lines=gen.lines;var chars=gen.characters;
  string text=t.text;var cam=ConsoleUI.DisplayCamera(t.canvas);float scale=1/t.pixelsPerUnit;
  for(int n=0;n<lines.Count;n++){
   int start=lines[n].startCharIdx,end=n+1<lines.Count?lines[n+1].startCharIdx:text.Length;
   end=Math.Min(end,Math.Min(text.Length,gen.characterCountVisible));if(start<0 || start>=end || end>chars.Count)continue;
   float left=float.MaxValue,right=float.MinValue;
   for(int j=start;j<end;j++){if(Char.IsWhiteSpace(text[j]))continue;left=Mathf.Min(left,chars[j].cursorPos.x);right=Mathf.Max(right,chars[j].cursorPos.x+chars[j].charWidth);}
   if(right<=left)continue;
   float top=lines[n].topY,bottom=top-lines[n].height;
   var a=RectTransformUtility.WorldToScreenPoint(cam,t.rectTransform.TransformPoint(new Vector3(left*scale,bottom*scale,0)));
   var b=RectTransformUtility.WorldToScreenPoint(cam,t.rectTransform.TransformPoint(new Vector3(right*scale,top*scale,0)));
   var rect=Rect.MinMaxRect(Mathf.Min(a.x,b.x),Mathf.Min(a.y,b.y),Mathf.Max(a.x,b.x),Mathf.Max(a.y,b.y));
   if(!ui.VisibleTextRegion(t,rect))continue;
   string value=text.Substring(start,end-start).TrimEnd('\r','\n');if(value.Length==0 || value.Length>2048)continue;
   output.Add(Item(rect,value,"creature_record",t.GetInstanceID().ToString(),"line"));
  }
 }
}
