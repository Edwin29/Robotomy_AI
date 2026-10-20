using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;

// IsolateRoom's final display widgets only. No CreatureModel, private work
// counts, cumulative tool use or work-command state is read here.
public static class ConsoleRoomStatus {
 static string Q(string s){return RobotomyObserver.Quote(s);}
 static string N(float n){return RobotomyObserver.Number(n);}
 static bool Number(ConsoleUI ui,Text t,out int value,out Rect r){
  value=0;r=new Rect();return t!=null && ui.VisibleWorldLabel(t,out r) &&
   t.cachedTextGenerator.characterCountVisible>=t.text.Length && Int32.TryParse(t.text,out value) && value>=0;
 }
 static int? Bars(ConsoleUI ui,Text anchor,RectTransform grid,List<GameObject> bars){
  Rect area;if(grid==null || bars==null || !grid.gameObject.activeInHierarchy ||
   !ConsoleUI.ScreenRect(grid,anchor.canvas,out area) || !ui.VisibleWorldRegion(anchor,area))return null;
  int count=0;
  foreach(var bar in bars){
   if(bar==null)return null;if(!bar.activeInHierarchy)continue;
   var graphic=bar.GetComponent<Image>();Rect r;
   if(graphic==null || !ui.VisibleWorldGraphic(graphic,out r))return null;
   count++;
  }
  return count;
 }
 public static string Capture(ConsoleUI ui){
  var rows=new List<string>();
  foreach(var room in UnityEngine.Object.FindObjectsOfType<IsolateRoom>()){
   Rect location=new Rect(),r;int number;string counter="null",work="null",stored="null",penalty="null";
   if(Number(ui,room.CumlativeCubeCount,out number,out r)){stored=number.ToString();location=r;}
   var p=room.probReductionText;
   if(p!=null && !String.IsNullOrEmpty(p.text) && ui.VisibleWorldLabel(p,out r) && p.cachedTextGenerator.characterCountVisible>=p.text.Length){penalty=Q(p.text);location=r;}
   if(Number(ui,room.CounterText,out number,out r)){
    counter="{\"display\":\"number\",\"value\":"+number+"}";location=r;
   } else if(room.CounterInnerImage!=null && ui.VisibleWorldGraphic(room.CounterInnerImage,out r)){
    var sprite=room.CounterInnerImage.sprite;
    string state=sprite!=null && sprite==room.CounterImage_Unknown?"unknown":sprite!=null && sprite==room.CounterImage_None?"not_applicable":null;
    if(state!=null){counter="{\"display\":"+Q(state)+",\"value\":null}";location=r;}
   }
   var progress=room.ProgressBar;
   if(progress!=null && progress.ActiveContorl!=null && progress.ActiveContorl.activeInHierarchy &&
      Number(ui,room.CurrentWorkCubeText,out number,out r)){
    int? pe=Bars(ui,room.CurrentWorkCubeText,progress.SuccessParent,progress.SuccessObject);
    int? ne=Bars(ui,room.CurrentWorkCubeText,progress.FailParent,progress.FailObject);
    if(pe.HasValue && ne.HasValue){
     work="{\"pe_boxes\":"+pe.Value+",\"ne_boxes\":"+ne.Value+",\"generated_total\":"+(pe.Value+ne.Value)+"}";location=r;
    }
   }
   if(counter=="null" && work=="null" && stored=="null" && penalty=="null")continue;
   string name="null";var label=room.CreatureName;
   if(label!=null && ui.VisibleWorldLabel(label,out r) && label.cachedTextGenerator.characterCountVisible>=label.text.Length)name=Q(label.text);
   rows.Add("{\"room_id\":"+Q(room.GetInstanceID().ToString())+",\"room_label\":"+name+",\"x\":"+N(location.center.x)+",\"y\":"+N(Screen.height-location.center.y)+",\"click\":"+ConsoleRoomClick.Capture(room)+",\"qliphoth_counter\":"+counter+",\"work_boxes\":"+work+",\"stored_pe_boxes\":"+stored+",\"work_penalty_text\":"+penalty+"}");
  }
  return "["+String.Join(",",rows.ToArray())+"]";
 }
 static string Text(ConsoleUI ui,Text t){Rect r;return t!=null && !String.IsNullOrEmpty(t.text) && ui.Visible(t,out r) && t.cachedTextGenerator.characterCountVisible>=t.text.Length?Q(t.text):"null";}
 static void Equipment(ConsoleUI ui,CreatureInfo.EquipSlot slot,Text count,string kind,List<string> costs){
  if(slot==null)return;string text=Text(ui,count);Rect r;
  if(text=="null" || !ui.Visible(count,out r))return;
  // MakeCount alternates owned/max with a localized cost label on hover.
  // Keep its actual wording rather than reading the separate integer Cost.
  costs.Add("{\"kind\":"+Q(kind)+",\"label\":"+Text(ui,slot.ItemName)+",\"display_text\":"+text+",\"x\":"+N(r.center.x)+",\"y\":"+N(Screen.height-r.center.y)+"}");
 }
 public static string Management(ConsoleUI ui){
  var win=CreatureInfoWindow.CurrentWindow;
  if(win==null || !win.gameObject.activeInHierarchy)return "null";
  var costs=new List<string>();
  foreach(var open in win.GetComponentsInChildren<CreatureInfo.CreatureInfoOpenArea>()){
   string cost=Text(ui,open.CostText);Rect r;if(cost=="null" || !ui.Visible(open.CostText,out r))continue;
   string shownLabel=Text(ui,open.AreaText);
   string prerequisite=shownLabel!="null" && open.AreaText.text==LocalizeTextDataModel.instance.GetText("CreatureInfo_PrevNeed")?"required":"not_indicated";
   // The two-line AreaText can be clipped by this game's scroll mask.
   // Its separately rendered tooltip remains readable; associate it with the hovered display area.
   var overlay=OverlayManager.Instance;Rect hoverArea;
   if(prerequisite!="required" && overlay!=null && Text(ui,overlay.OverlayText)!="null" &&
      overlay.OverlayText.text==LocalizeTextDataModel.instance.GetText("Tooltip_CreatureInfo@NeedPreviousManagement") &&
      ConsoleUI.ScreenRect(open.GetComponent<RectTransform>(),open.CostText.canvas,out hoverArea) &&
      hoverArea.Contains(RobotomyVirtualInput.VirtualState.get_mousePosition()))prerequisite="required";
   costs.Add("{\"prerequisite\":"+Q(prerequisite)+",\"kind\":\"unlock\",\"label\":"+shownLabel+",\"display_text\":"+cost+",\"x\":"+N(r.center.x)+",\"y\":"+N(Screen.height-r.center.y)+"}");
  }
  var eq=win.equipmentRoot;
  if(eq!=null){if(eq.weaponSlot!=null)Equipment(ui,eq.weaponSlot,eq.weaponSlot.MakeCount,"weapon_cost_or_stock",costs);if(eq.armorSlot!=null)Equipment(ui,eq.armorSlot,eq.armorSlot.MakeCount,"suit_cost_or_stock",costs);}
  string stored="null";var balance=win.CurrentCumlativeCube_Cost;Rect balanceRect;
  // Runtime prefab: Count/Cube/Textures/CurrentCube. Its artwork is the same widget.
  if(balance!=null){Transform surface=balance.transform;while(surface!=null && surface.name!="CurrentCube" && surface!=win.transform)surface=surface.parent;
   if(surface!=null && surface.name=="CurrentCube" && ui.VisibleSurface(balance,surface,out balanceRect) && balance.cachedTextGenerator.characterCountVisible>=balance.text.Length)stored=Q(balance.text);}

  var details=new List<string>();var stat=win.statRoot;
  if(stat!=null){
   Detail(ui,details,"identity",new string[]{"name","code","risk","max_pe_boxes"},new Text[]{stat.Name,stat.CodeNo,stat.RiskLevel,stat.MaximumCubeGenerate});
   Detail(ui,details,"work_damage",new string[]{"type","range"},new Text[]{stat.WorkDamageType,stat.WorkDamageRange});
   if(stat.damageList!=null)foreach(var slot in stat.damageList)if(slot!=null)Detail(ui,details,"work_damage",new string[]{"type","range"},new Text[]{slot.Type,slot.DamageRange});
   if(stat.slots!=null)foreach(var slot in stat.slots)if(slot!=null)Detail(ui,details,"work_result_pe_range",new string[]{"label","range"},new Text[]{slot.Label,slot.RangeText},true);
  }
  if(win.workRoot!=null && win.workRoot.workSlots!=null)foreach(var slot in win.workRoot.workSlots){
   if(slot==null || slot.levelSuccessPercentage==null)continue;
   string name=Text(ui,slot.WorkName);if(name=="null")continue;
   string[] ranks={"I","II","III","IV","V"};
   // Shipped SetWorkSuccess binds index i to employee level i+1.
   var levels=new List<string>();
   for(int i=0;i<slot.levelSuccessPercentage.Length && i<ranks.Length;i++){
    string value=Text(ui,slot.levelSuccessPercentage[i]);if(value!="null")levels.Add(Q(ranks[i])+":"+value);
   }
   if(levels.Count>0)details.Add("{\"kind\":\"work_preference\",\"work\":"+name+","+String.Join(",",levels.ToArray())+"}");
  }
  if(eq!=null){
   var w=eq.weaponSlot;if(w!=null)Detail(ui,details,"ego_weapon",new string[]{"name","grade","damage_type","damage_range","attack_speed","attack_range"},new Text[]{w.ItemName,w.ItemGrade,w.TypeText,w.DamageRange,w.AttackSpeed,w.AttackRange});
   var a=eq.armorSlot;if(a!=null){Detail(ui,details,"ego_suit",new string[]{"name","grade"},new Text[]{a.ItemName,a.GradeText});
    for(int i=0;i<a.TypeText.Length && i<a.RWBP_Defense.Length;i++)Detail(ui,details,"ego_suit_resistance",new string[]{"type_and_factor","resistance"},new Text[]{a.TypeText[i],a.RWBP_Defense[i]});}
  }
  if(win.caretakingRoot!=null)foreach(var slot in win.caretakingRoot.GetComponentsInChildren<CreatureInfo.CreatureInfoCaretakingSlot>())
   Detail(ui,details,"management_tip",new string[]{"label","text"},new Text[]{slot.Title,slot.CaretakingSection});
  if(stored=="null" && costs.Count==0 && details.Count==0)return "null";
  return "{\"stored_pe_text\":"+stored+",\"costs\":["+String.Join(",",costs.ToArray())+"],\"details\":["+String.Join(",",details.ToArray())+"]}";
 }
 static void Detail(ConsoleUI ui,List<string> rows,string kind,string[] keys,Text[] fields,bool feelingPalette=false){
  var parts=new List<string>();for(int i=0;i<keys.Length;i++){Rect rect;var t=fields[i];string s=feelingPalette?(t!=null && ui.VisibleFeelingLabel(t,out rect) && t.cachedTextGenerator.characterCountVisible>=t.text.Length?Q(t.text):"null"):Text(ui,t);if(s!="null")parts.Add(Q(keys[i])+":"+s);}
  if(parts.Count>0){string row="{\"kind\":"+Q(kind)+","+String.Join(",",parts.ToArray())+"}";if(!rows.Contains(row))rows.Add(row);}
 }
}
