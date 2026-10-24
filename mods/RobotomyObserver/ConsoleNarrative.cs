using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.UI;using UnityEngine.EventSystems;

// Only current rendered UI strings and verified gesture geometry. Never story scripts/research models.
public static class ConsoleNarrative {
 public static string FrameKey(ViewRect[] texts){
  var key=new System.Text.StringBuilder();
  foreach(var t in texts)if(t.panel=="story")key.Append(t.row_id).Append(':').Append(t.role).Append(':').Append(t.text).Append('\n');
  // Sprite swaps capture portraits/CG/background changes without reading scripts.
  foreach(var g in UnityEngine.Object.FindObjectsOfType<Image>())
   // DialogueDisplay.Init parents its blinking NextGuide under the text.
   // Its blink is not a new story scene; text itself is already in the key.
   if(g.isActiveAndEnabled && g.GetComponentInParent<DialogueDisplay>()==null &&
      g.canvasRenderer.GetAlpha()*g.color.a>.05f && g.sprite!=null)
    key.Append(g.GetInstanceID()).Append(':').Append(g.sprite.GetInstanceID()).Append(';');
  return key.ToString();
 }
 static void Add(ConsoleUI ui,Text t,string panel,string id,string role,List<ViewRect> rows,Transform surface=null){
  Rect r;if(t==null || String.IsNullOrEmpty(t.text))return;
  if(!(panel=="research"?ui.VisibleResearch(t,surface,out r):ui.VisibleStory(t,out r)))return;
  string text=t.supportRichText?System.Text.RegularExpressions.Regex.Replace(t.text,"<[^>]*>",""):t.text;
  if(text.Length>2048 || t.cachedTextGenerator.characterCountVisible<text.Length)return;
  rows.Add(new ViewRect{text=text,panel=panel,row_id=id,role=role,x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height});
 }
 static void Point(ConsoleUI ui,Graphic g,Transform surface,GameObject expected,bool drag,string id,List<ViewRect> rows){
  Rect r;var es=EventSystem.current;
  // Authored transparent hit areas have no visible alpha. Verify their actual
  // EventSystem receiver instead; don't mistake transparency for disabled input.
  if(g==null || expected==null || es==null || !g.gameObject.activeInHierarchy ||
     !ConsoleUI.ScreenRect(g.rectTransform,g.canvas,out r) ||
     !new Rect(0,0,Screen.width,Screen.height).Contains(r.center))return;
  var p=new PointerEventData(es);p.position=r.center;var hits=new List<RaycastResult>();es.RaycastAll(p,hits);
  if(hits.Count==0)return;
  var handler=drag?ExecuteEvents.GetEventHandler<IDragHandler>(hits[0].gameObject):ExecuteEvents.GetEventHandler<IDropHandler>(hits[0].gameObject);
  if(handler!=expected) {
   var exchange=handler==null?null:handler.GetComponent<DragExchanger>();
   var over=handler==null?null:handler.GetComponent<DragOverDrop>();
   if(drag || !((exchange!=null && exchange.dropScript!=null && exchange.dropScript.gameObject==expected) ||
       (over!=null && over.dropScript!=null && over.dropScript.gameObject==expected)))return;
  }
  rows.Add(new ViewRect{text="",panel="research",row_id=id,role=drag?"drag_start":"drop_target",x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height});
 }
 public static void Capture(ConsoleUI ui,List<ViewRect> rows){
  foreach(var d in UnityEngine.Object.FindObjectsOfType<StoryDialogueUI>()){
   string id=d.GetInstanceID().ToString();
   Add(ui,d.dialogueNameUI,"story",id,"speaker",rows);
   if(d.dialogueDisplay!=null)Add(ui,d.dialogueDisplay.GetComponent<Text>(),"story",id,"dialogue",rows);
   Add(ui,d.diaglogueText,"story",id,"letter",rows);Add(ui,d.exDiagText,"story",id,"extra",rows);
   if(d.narDiagDisplay!=null)Add(ui,d.narDiagDisplay.GetComponent<Text>(),"story",id,"narration",rows);
   var shown=rows.FindLast(x=>x.panel=="story" && x.row_id==id && (x.role=="dialogue" || x.role=="letter" || x.role=="narration"));
   if(shown!=null)rows.Add(new ViewRect{text=d.dialogueNowProcessing?"revealing":"ready",panel="story",row_id=id,role="display_state",x=shown.x,y=shown.y,width=shown.width,height=shown.height});
  }
  foreach(var choice in UnityEngine.Object.FindObjectsOfType<StorySelectionOptionUI>())
   Add(ui,choice.textUI,"story",choice.GetInstanceID().ToString(),"choice",rows);
  var deploy=DeployUI.instance;var win=deploy==null?null:deploy.researchWindow;
  if(win==null || win.ui==null || win.rootObject==null || !win.rootObject.activeInHierarchy)return;
  if(win.IsDragging)return;
  Add(ui,win.ui.AreaName,"research","window","department",rows,win.ui.AreaName==null?null:win.ui.AreaName.transform.parent);
  Add(ui,win.ui.AreaDesc,"research","window","title",rows,win.ui.AreaDesc==null?null:win.ui.AreaDesc.transform.parent);
  Add(ui,win.ui.HelpDescription,"research","window","help",rows,win.HelpArea);
  Add(ui,win.Conversation,"research","window","confirmation",rows,win.rootObject.transform);
  foreach(var button in win.ButtonArea.GetComponentsInChildren<Button>()) {
   if(!button.IsInteractable() || !button.isActiveAndEnabled)continue;
   var label=button.GetComponentInChildren<Text>();if(label==null)continue;
   string id=button.GetInstanceID().ToString();
   Add(ui,label,"research",id,"action",rows,win.rootObject.transform);
   Rect r;var es=EventSystem.current;
   if(es==null || !ConsoleUI.ScreenRect(label.rectTransform,label.canvas,out r) ||
      !new Rect(0,0,Screen.width,Screen.height).Contains(r.center))continue;
   var data=new PointerEventData(es);data.position=r.center;var hits=new List<RaycastResult>();es.RaycastAll(data,hits);
   if(hits.Count>0 && ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject)==button.gameObject)
    rows.Add(new ViewRect{text="",panel="research",row_id=id,role="click",x=r.x,y=Screen.height-r.yMax,width=r.width,height=r.height});
  }
  foreach(var p in win.rootObject.GetComponentsInChildren<ResearchPanel>()){
   if(win.ButtonArea.gameObject.activeInHierarchy && p!=win.selectedPanel)continue;
   string id=p.GetInstanceID().ToString();
   Add(ui,p.ResearchName,"research",id,"name",rows,win.rootObject.transform);
   Add(ui,p.ResearchShortDesc,"research",id,"effect",rows,win.rootObject.transform);
   Add(ui,p.ResearchLongDesc,"research",id,"description",rows,win.rootObject.transform);
   if(p.dragScript!=null)Point(ui,p.dragScript.Image,p.transform,p.dragScript.gameObject,true,id,rows);
  }
  if(win.dropHandler!=null)Point(ui,win.dropArea,win.LowerArea,win.dropHandler.gameObject,false,"window",rows);
 }
}
