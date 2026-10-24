using System;using System.Collections.Generic;using UnityEngine;using UnityEngine.SceneManagement;using UnityEngine.UI;using Harmony;
// Public announcement events. No targets, hidden timers or model conditions are exported.
public static class ConsoleSignals {
 public static int Epoch;
 public static void StageStart(){Epoch++;recent.Clear();ids.Clear();escapeRows.Clear();narrations.Clear();}
 static Dictionary<IsolateRoom,string> narrations=new Dictionary<IsolateRoom,string>();
 static List<string> recent=new List<string>();static long serial;static string scene="";
 static Dictionary<UnityEngine.Object,string> ids=new Dictionary<UnityEngine.Object,string>();
 static Dictionary<ConversationUI,bool> escapeRows=new Dictionary<ConversationUI,bool>();static bool handlingEscape;
 static void SceneCheck(){string next=SceneManager.GetActiveScene().name;if(next!=scene){scene=next;recent.Clear();ids.Clear();escapeRows.Clear();narrations.Clear();}}
 public static string Identity(UnityEngine.Object owner){SceneCheck();string id;if(owner==null)return "";if(!ids.TryGetValue(owner,out id)){id=Guid.NewGuid().ToString("N");ids[owner]=id;}return id;}
 public static void Install(){var h=HarmonyInstance.Create("Robotomy.VisibleSignals.v2");
  h.Patch(typeof(CreatureOverloadManager).GetMethod("OnStageStart"),null,new HarmonyMethod(typeof(ConsoleSignals).GetMethod("StageStart")),null);
  h.Patch(typeof(GameStatusUI.EnergyController).GetMethod("SetOverLoadUI"),null,new HarmonyMethod(typeof(ConsoleSignals).GetMethod("OverloadShown")),null);
  h.Patch(typeof(SefiraConversationController).GetMethod("OnNotice"),new HarmonyMethod(typeof(ConsoleSignals).GetMethod("BeforeNotice")),new HarmonyMethod(typeof(ConsoleSignals).GetMethod("AfterNotice")),null);
  h.Patch(typeof(ConversationUI).GetMethod("InitUI"),null,new HarmonyMethod(typeof(ConsoleSignals).GetMethod("ConversationShown")),null);
 }
 public static void OverloadShown(GameStatusUI.EnergyController __instance){
  SceneCheck();
  // SetOverLoadUI itself suppresses the announcement in E4. Do not emit from
  // an old active UI left behind by that no-op call.
  if(SefiraBossManager.Instance.IsKetherBoss(KetherBossType.E4))return;
  if(__instance==null || __instance.OverloadUIController==null ||
     !__instance.OverloadUIController.gameObject.activeInHierarchy ||
     __instance.OverloadUIText==null || String.IsNullOrEmpty(__instance.OverloadUIText.text))return;
  // One event per announcement invocation, even at the capped level.
  // Ordinary overlays (including the day-complete banner) do not cancel it.
  Emit("meltdown_cycle",__instance.OverloadUIText.text);
 }
 public static void BeforeNotice(string notice,out bool __state){SceneCheck();__state=handlingEscape;handlingEscape=notice==NoticeName.OnEscape;}
 public static void AfterNotice(bool __state){handlingEscape=__state;}
 public static void ConversationShown(ConversationUI __instance){if(handlingEscape)escapeRows[__instance]=false;}
 static void Emit(string kind,string text){serial++;recent.Add("{\"id\":"+serial+",\"kind\":"+RobotomyObserver.Quote(kind)+",\"at\":"+RobotomyObserver.Quote(DateTime.UtcNow.ToString("o"))+",\"text\":"+RobotomyObserver.Quote(text)+"}");if(recent.Count>128)recent.RemoveAt(0);}
 public static void NarrationObserved(IsolateRoom room,string text,string label){
  SceneCheck();
  if(String.IsNullOrEmpty(text)){narrations.Remove(room);return;}
  string prior;if(narrations.TryGetValue(room,out prior) && prior==text)return;
  narrations[room]=text;serial++;
  recent.Add("{\"id\":"+serial+",\"kind\":\"room_narration\",\"at\":"+RobotomyObserver.Quote(DateTime.UtcNow.ToString("o"))+
   ",\"room_id\":"+RobotomyObserver.Quote(room.GetInstanceID().ToString())+",\"room_label\":"+(label==null?"null":RobotomyObserver.Quote(label))+",\"text\":"+RobotomyObserver.Quote(text)+"}");
  if(recent.Count>128)recent.RemoveAt(0);
 }
 public static string Capture(ConsoleUI ui){
  SceneCheck();
  Rect r;
  foreach(var row in new List<ConversationUI>(escapeRows.Keys)){
   if(row==null){escapeRows.Remove(row);continue;}
   if(!escapeRows[row] && ui.Visible(row.InnerText,out r) && row.InnerText.cachedTextGenerator.characterCountVisible>=row.InnerText.text.Length){Emit("escape_confirmed",row.InnerText.text);escapeRows[row]=true;}
  }
  return "["+String.Join(",",recent.ToArray())+"]";
 }
}
