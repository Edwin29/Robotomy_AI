using System;using System.Collections.Generic;using System.Reflection;using UnityEngine;using UnityEngine.UI;using Harmony;

// Render observations, never TakeDamage/attack AI/buff timers. Main thread only.
public static class ConsoleCombat {
 class Pending { public DamageEffect effect; public Component owner; }
 static Dictionary<DamageEffect,Pending> pending=new Dictionary<DamageEffect,Pending>();
 static List<string> events=new List<string>(),journal=new List<string>();
 static Dictionary<BarrierEffect,string> barriers=new Dictionary<BarrierEffect,string>();
 static Dictionary<BarrierEffect,WorkerUnit> barrierOwners=new Dictionary<BarrierEffect,WorkerUnit>();
 static Dictionary<string,string> motions=new Dictionary<string,string>();
 static Dictionary<GameObject,string> particles=new Dictionary<GameObject,string>();
 static string lastAmmo;
 static long serial;static int epoch=-1;static string scene="";
 static string Q(string s){return s==null?"null":RobotomyObserver.Quote(s);}
 static string N(float v){return RobotomyObserver.Number(v);}
 public static void Install(){var h=HarmonyInstance.Create("Robotomy.VisibleCombat.v1");
  foreach(var m in typeof(DamageEffect).GetMethods(BindingFlags.Public|BindingFlags.Static))
   if(m.Name=="Invoker"){
    string hook="DamageCreated";foreach(var p in m.GetParameters())if(p.Name=="mov")hook="DamageMov";
    foreach(var p in m.GetParameters())if(p.Name=="target")hook="DamageTarget";
    h.Patch(m,null,new HarmonyMethod(typeof(ConsoleCombat).GetMethod(hook)),null);
   }
  h.Patch(typeof(BarrierEffect).GetMethod("OnBreak"),new HarmonyMethod(typeof(ConsoleCombat).GetMethod("BarrierBreak")),null,null);
  h.Patch(typeof(BarrierEffect).GetMethod("MakeBarrier"),null,new HarmonyMethod(typeof(ConsoleCombat).GetMethod("BarrierCreated")),null);
  h.Patch(typeof(BarrierEffect).GetMethod("OnDisappear"),new HarmonyMethod(typeof(ConsoleCombat).GetMethod("BarrierFade")),null,null);
  h.Patch(typeof(Prefab).GetMethod("LoadPrefab"),null,new HarmonyMethod(typeof(ConsoleCombat).GetMethod("PrefabShown")),null);
 }
 static void Check(){string next=UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
  if(next!=scene||epoch!=ConsoleSignals.Epoch){scene=next;epoch=ConsoleSignals.Epoch;pending.Clear();barriers.Clear();barrierOwners.Clear();motions.Clear();motionTokens.Clear();particles.Clear();lastAmmo=null;events.Clear();ConsoleProjectile.Clear();}
 }
 public static void PrefabShown(string name,GameObject __result){
  Check();if(__result==null)return;string label=name=="Effect/Bullet/Health_Proto"?"체력 회복 탄환 효과":name=="Effect/Bullet/Mental_Prototype"?"정신력 회복 탄환 효과":name=="Effect/Bullet/Shield_Proto"?"보호 탄환 효과":name=="Effect/Bullet/SlowBullet"?"둔화 탄환 효과":name=="Effect/Bullet/ExecutionEffect"?"처형 탄환 효과":null;
  ConsoleProjectile.Created(name,__result);
  if(label!=null&&particles.Count<128)particles[__result]=label;
 }
 static Component Unit(UnitModel u){var w=u as WorkerModel;if(w!=null)return w.GetWorkerUnit();var c=u as CreatureModel;return c==null?null:c.Unit;}
 public static void DamageCreated(DamageEffect __result){RegisterDamage(__result,null);}
 public static void DamageMov(DamageEffect __result,MovableObjectNode mov){RegisterDamage(__result,mov==null?null:Unit(mov.GetUnit()));}
 public static void DamageTarget(DamageEffect __result,UnitModel target){RegisterDamage(__result,Unit(target));}
 static void RegisterDamage(DamageEffect __result,Component owner){
  Check();if(__result==null)return;
  Pending p;if(pending.TryGetValue(__result,out p)){if(owner!=null)p.owner=owner;return;}
  if(pending.Count<512)pending[__result]=new Pending{effect=__result,owner=owner};
 }
 static string Ref(Component owner,ConsoleUI ui){
  if(owner==null)return null;Rect r;Vector3 p;Camera c=Camera.main;
  bool visible=ConsoleEmployee.Anchor(owner as AgentUnit,ui,c,out p,out r)||ConsoleEntity.Anchor(owner as CreatureUnit,ui,c,out p,out r);
  return visible?"unit:"+ConsoleSignals.Identity(owner):null;
 }
 static void Emit(string kind,string fields){
  string e="{\"id\":"+(++serial)+",\"kind\":"+Q(kind)+",\"scene\":"+Q(scene)+",\"epoch\":"+epoch+",\"at\":"+Q(DateTime.UtcNow.ToString("o"))+",\"game_time\":"+N(Time.time)+",\"real_time\":"+N(Time.realtimeSinceStartup)+",\"frame\":"+Time.frameCount+fields+"}";
  events.Add(e);journal.Add(e);if(events.Count>512)events.RemoveAt(0);if(journal.Count>2048)journal.RemoveAt(0);
 }
 static string Point(Vector3 p){return ",\"position\":{\"x\":"+N(p.x)+",\"y\":"+N(Screen.height-p.y)+"}";}
 public static void PollFrame(ConsoleUI ui){
  Check();foreach(var d in new List<DamageEffect>(pending.Keys))if(d==null)pending.Remove(d);
  if(pending.Count==0&&particles.Count==0)return;
  if(ConsoleMotion.CameraGuard(Camera.main)!="")return;
  foreach(var g in new List<GameObject>(particles.Keys)){
   if(g==null){particles.Remove(g);continue;}
   foreach(var ps in g.GetComponentsInChildren<ParticleSystem>()){
    var renderer=ps.GetComponent<Renderer>();
    if(renderer==null||!renderer.enabled||!ps.gameObject.activeInHierarchy||ps.particleCount==0)continue;
    Vector3 pos=Camera.main.WorldToScreenPoint(ps.transform.position);if(pos.z<=0||pos.x<0||pos.y<0||pos.x>=Screen.width||pos.y>=Screen.height)continue;
    if(ui.MotionCover(new Rect(pos.x-2,pos.y-2,4,4),ps.transform)!="")continue;
    Emit("item_effect",",\"text\":"+Q(particles[g])+Point(pos));particles.Remove(g);break;
   }
  }
  foreach(var pair in new List<Pending>(pending.Values)){
   var d=pair.effect;if(d==null){pending.Remove(d);continue;}
   Rect r=new Rect(),countRect=new Rect(),iconRect=new Rect(),defenseRect=new Rect();bool count=d.DamageCount!=null&&ui.VisibleWorldLabel(d.DamageCount,out countRect);
   bool icon=d.Icon!=null&&ui.VisibleWorldGraphic(d.Icon,out iconRect);
   bool defense=d.DefenseTypeText!=null&&ui.VisibleWorldGraphic(d.DefenseTypeText,out defenseRect);
   if(!count&&!icon&&!defense)continue;
   string type=null;if(icon)for(int i=1;i<d.DamageIcon.Length&&i<=4;i++)if(d.Icon.sprite==d.DamageIcon[i])type=new[]{"","RED","WHITE","BLACK","PALE"}[i];
   string resist=null;if(defense)for(int i=0;i<d.DamageTextImage.Length&&i<5;i++)if(d.DefenseTypeText.sprite==d.DamageTextImage[i])resist=new[]{"취약","약점","면역","내성","견딤"}[i];
   string context=null;if(d.DamageContext!=null&&ui.VisibleWorldLabel(d.DamageContext,out r))context=d.DamageContext.text;
   Rect shown=count?countRect:icon?iconRect:defenseRect;Vector3 p=shown.center;
   Emit("damage_display",",\"subject\":"+Q(Ref(pair.owner,ui))+",\"type\":"+Q(type)+",\"display\":"+Q(count?d.DamageCount.text:null)+",\"defense\":"+Q(resist)+",\"text\":"+Q(context)+Point(p));
   pending.Remove(d);
  }
 }
 static bool Visible(BarrierEffect b){var c=Camera.main;var r=b==null?null:b.barrierRenderer;
  if(r==null||!r.enabled||!r.gameObject.activeInHierarchy||r.sprite==null||r.color.a<=.01f||ConsoleMotion.CameraGuard(c)!="")return false;
  var p=c.WorldToScreenPoint(r.bounds.center);return p.z>0&&p.x>=0&&p.x<Screen.width&&p.y>=0&&p.y<Screen.height;
 }
 public static void BarrierCreated(WorkerModel target,BarrierEffect __result){Check();if(__result!=null&&target!=null)barrierOwners[__result]=target.GetWorkerUnit();}
 static void BarrierEvent(BarrierEffect b,string state){if(!Visible(b))return;
  var ui=new ConsoleUI();WorkerUnit owner;if(!barrierOwners.TryGetValue(b,out owner))owner=b.GetComponentInParent<WorkerUnit>();string target=Ref(owner,ui);if(target==null)return;
  string type=null;foreach(RwbpType t in new[]{RwbpType.R,RwbpType.W,RwbpType.B,RwbpType.P}){Color c=UIColorManager.instance.GetRWBPTypeColor(t);Color a=b.barrierRenderer.color;if(Mathf.Abs(a.r-c.r)+Mathf.Abs(a.g-c.g)+Mathf.Abs(a.b-c.b)<.03f)type=t==RwbpType.R?"RED":t==RwbpType.W?"WHITE":t==RwbpType.B?"BLACK":"PALE";}
  Emit("barrier_display",",\"subject\":"+Q(target)+",\"type\":"+Q(type)+",\"state\":"+Q(state)+Point(Camera.main.WorldToScreenPoint(b.barrierRenderer.bounds.center)));
  barriers[b]=state;
 }
 public static void BarrierBreak(BarrierEffect __instance){Check();BarrierEvent(__instance,"break_effect");}
 public static void BarrierFade(BarrierEffect __instance){Check();BarrierEvent(__instance,"fade_started");}
 public static void Sample(ConsoleUI ui){Check();
  ConsoleProjectile.Sample(ui);
  var bullets=GlobalBullet.GlobalBulletWindow.CurrentWindow;Rect rect;
  if(bullets!=null&&bullets.CurrentUsableBulletCount!=null&&ui.Visible(bullets.CurrentUsableBulletCount,out rect)){
   string value=bullets.CurrentUsableBulletCount.text;
   if(value!=lastAmmo){Emit("ammo_display",",\"display\":"+Q(value)+",\"previous\":"+Q(lastAmmo));lastAmmo=value;}
  }else lastAmmo=null;
  foreach(var b in new List<BarrierEffect>(barrierOwners.Keys)){
   if(!Visible(b)){barriers.Remove(b);continue;}string prior;barriers.TryGetValue(b,out prior);if(prior=="break_effect"||prior=="fade_started")continue;
   string state=b.barrierRenderer.sprite==b.barrier_cracked?"cracked":"visible";if(prior!=state)BarrierEvent(b,state);
  }
  foreach(var b in new List<BarrierEffect>(barriers.Keys))if(b==null)barriers.Remove(b);
  foreach(var b in new List<BarrierEffect>(barrierOwners.Keys))if(b==null)barrierOwners.Remove(b);
 }
 public static void Motion(UnityEngine.Object owner,Spine.Unity.SkeletonRenderer skeleton,Vector2 pixel){
  // Called only after the existing visible-body check. Opaque presentation token, no animation names.
  string display=null;var anim=skeleton as Spine.Unity.SkeletonAnimation;
  if(anim!=null&&anim.state!=null){var track=anim.state.GetCurrent(0);if(track!=null&&track.Animation!=null)display=track.Animation.Name;}
  if(display==null){var controller=skeleton.GetComponent<Animator>();if(controller!=null&&controller.isActiveAndEnabled){
   var clips=controller.GetCurrentAnimatorClipInfo(0);if(clips.Length>0&&clips[0].clip!=null&&clips[0].weight>.01f)display="clip:"+clips[0].clip.GetInstanceID();
  }}
  if(display==null)return;
  string id="unit:"+ConsoleSignals.Identity(owner),key=ConsoleSignals.Identity(skeleton.skeletonDataAsset)+":"+display,old;
  if(motions.TryGetValue(id,out old)&&old==key)return;motions[id]=key;
  string token; if(!motionTokens.TryGetValue(key,out token)){token="motion:"+(motionTokens.Count+1);motionTokens[key]=token;}
  Emit("motion_changed",",\"subject\":"+Q(id)+",\"motion\":"+Q(token)+Point(new Vector3(pixel.x,Screen.height-pixel.y,0)));
 }
 static Dictionary<string,string> motionTokens=new Dictionary<string,string>();
 public static void Projectile(string id,string state,Vector2? point,Vector2? velocity){
  string fields=",\"subject\":"+Q(id)+",\"state\":"+Q(state);
  if(point.HasValue)fields+=",\"position\":{\"x\":"+N(point.Value.x)+",\"y\":"+N(point.Value.y)+"}";
  if(velocity.HasValue)fields+=",\"object_velocity\":{\"x\":"+N(velocity.Value.x)+",\"y\":"+N(velocity.Value.y)+"}";
  Emit("projectile_display",fields);
 }
 public static string Snapshot(){return "{\"latest_id\":"+serial+",\"events\":["+String.Join(",",events.ToArray())+"]}";}
 public static string Drain(){string s=journal.Count==0?"":String.Join("\n",journal.ToArray())+"\n";journal.Clear();return s;}
}
