using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;

// Semantic labels for final display fields. Never read CurrentTarget/CurrentSkill.
public static class CommandWindowReading {
 public static void Tag(Text text, ViewRect item) {
  var w=CommandWindow.CommandWindow.CurrentWindow;if(w==null)return;
  var a=w.WorkAllocate;
  if(a!=null){
   string role=text==a.Name?"name":text==a.CodeNo?"code":text==a.RiskLevel?"risk":text==a.MaximumCubeGenerate?"max_pe_boxes":text==a.WorkDamageType?"damage_type":text==a.WorkDamageRange?"damage_range":null;
   if(role!=null){item.row_id="summary";item.role=role;return;}
   for(int i=0;i<a.slots.Count;i++){
    var s=a.slots[i];if(s!=null && (text==s.Label || text==s.RangeText)){
     // SetData(index): 0 bad, 1 normal, 2 good. Values remain rendered text (including Unknown).
     item.row_id="result_"+(i==0?"bad":i==1?"normal":i==2?"good":i.ToString());
     item.role=text==s.RangeText?"pe_range":"result_label";return;
    }
   }
  }
  if(string.IsNullOrEmpty(item.row_id))item.row_id="window";
  if(string.IsNullOrEmpty(item.role))item.role="display_text";
 }
 public static void Capture(ConsoleUI ui,List<ViewRect> buttons){
  var w=CommandWindow.CommandWindow.CurrentWindow;var es=EventSystem.current;
  if(w==null || w.RootControl==null || !w.RootControl.activeInHierarchy || w.WorkButton==null || es==null)return;
  foreach(var b in w.WorkButton){
   if(b==null || !b.isActiveAndEnabled)continue;
   // Game swaps the actual displayed icon for special actions; do not infer from array index.
   var iconTransform=b.transform.Find("Icon");var icon=iconTransform==null?null:iconTransform.GetComponent<Image>();Rect r;
   if(icon==null || !ui.VisibleCommandGraphic(icon,w.RootControl.transform,out r))continue;
   string label=icon.sprite==w.Work_R?"본능":icon.sprite==w.Work_W?"통찰":icon.sprite==w.Work_B?"애착":icon.sprite==w.Work_P?"억압":icon.sprite==w.Work_S?"특수 작업":null;
   var nameTransform=b.transform.Find("WorkName");var displayedName=nameTransform==null?null:nameTransform.GetComponent<Text>();Rect nameRect;
   if(displayedName!=null && ui.VisibleCommandGraphic(displayedName,w.RootControl.transform,out nameRect) && !string.IsNullOrEmpty(displayedName.text) && displayedName.cachedTextGenerator.characterCountVisible>=displayedName.text.Length)label=displayedName.text;
   if(label==null)continue;
   bool clickable=b.IsInteractable();var data=new PointerEventData(es);data.position=r.center;var hits=new List<RaycastResult>();es.RaycastAll(data,hits);
   clickable=clickable && hits.Count>0 && ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject)==b.gameObject;
   buttons.Add(new ViewRect{panel="command",row_id="work_"+b.GetInstanceID(),role="work_type",text=label,
    x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height,interactable=clickable,input_verified=clickable,
    target_id=clickable?b.GetInstanceID().ToString():"",hit_x=r.center.x,hit_y=Screen.height-r.center.y});
  }
 }
}
