using System;using System.Collections.Generic;using System.Security.Cryptography;using System.Text;
using UnityEngine;using UnityEngine.UI;using Spine.Unity;

// Presentation only. Never reads model state, buf type, work counts or future timers.
public static class ConsoleAppearance {
 public static double Milliseconds;
 static readonly Dictionary<string,string> hashes=new Dictionary<string,string>();
 static readonly Dictionary<UnityEngine.Object,List<SkeletonRenderer>> visible=new Dictionary<UnityEngine.Object,List<SkeletonRenderer>>();
 static string Q(string s){return RobotomyObserver.Quote(s);}
 static string Hash(string s){string v;if(hashes.TryGetValue(s,out v))return v;using(var h=SHA256.Create())v=BitConverter.ToString(h.ComputeHash(Encoding.UTF8.GetBytes("appearance-v1|"+s))).Replace("-","").ToLowerInvariant().Substring(0,20);if(hashes.Count>4096)hashes.Clear();hashes[s]=v;return v;}
 static string Asset(UnityEngine.Object o){return o==null?"":o.name.Replace("(Clone)","").Trim();}
 static string ColorKey(Color c){return ((int)Math.Round(c.r*10))+","+((int)Math.Round(c.g*10))+","+((int)Math.Round(c.b*10));}
 static string SpriteKey(Sprite s){return s==null?"":Asset(s.texture)+"/"+Asset(s)+"/"+(int)s.rect.x+","+(int)s.rect.y+","+(int)s.rect.width+","+(int)s.rect.height;}
 static string Item(string kind,string key,string label){return "{\"ref\":"+Q(kind+":"+Hash(key))+",\"kind\":"+Q(kind)+",\"label\":"+Q(label)+"}";}
 public static void Begin(){visible.Clear();}
 public static void Seen(UnityEngine.Object owner,SkeletonRenderer skeleton){if(owner==null||skeleton==null)return;List<SkeletonRenderer> list;if(!visible.TryGetValue(owner,out list)){list=new List<SkeletonRenderer>();visible[owner]=list;}if(!list.Contains(skeleton))list.Add(skeleton);}
 public static void SeenNative(CreatureUnit unit,ConsoleUI ui){
  if(unit==null)return;
  var old=unit.animTarget as OldLadyAnim;
  if(old!=null&&Display(old.gameObject,ui)){if(!visible.ContainsKey(unit))visible[unit]=new List<SkeletonRenderer>();return;}
  var n=unit.animTarget as NothingAnim;if(n==null)return;foreach(var a in new[]{n.Lv1Node,n.Lv2Node,n.eggNode})if(a!=null&&Display(a.gameObject,ui)){if(!visible.ContainsKey(unit))visible[unit]=new List<SkeletonRenderer>();return;}
 }
 static bool Shown(Renderer r,ConsoleUI ui){
  var cam=Camera.main;if(r==null||!r.enabled||!r.gameObject.activeInHierarchy||cam==null||(cam.cullingMask&(1<<r.gameObject.layer))==0)return false;
  var sprite=r as SpriteRenderer;if(sprite!=null&&(sprite.sprite==null||sprite.color.a<.1f))return false;
  var mat=r.sharedMaterial;if(mat!=null&&mat.HasProperty("_Color")&&mat.GetColor("_Color").a<.1f)return false;
  if(r is MeshRenderer){Vector3 world;Rect region;return MotionSurface.PickPresence(r,cam,(rect,p)=>ui.MotionCover(rect,r.transform)==""&&MotionStencil.CanDraw(r,rect),out world,out region);}
  // An enabled particle/line renderer can contain no visible pixels. Those need
  // a dedicated display sampler; do not turn their GameObject flags into marks.
  if(sprite==null)return false;
  Vector3 p0=cam.WorldToScreenPoint(r.bounds.center);return p0.z>cam.nearClipPlane&&p0.z<cam.farClipPlane&&p0.x>=2&&p0.y>=2&&p0.x<Screen.width-2&&p0.y<Screen.height-2&&ui.MotionCover(new Rect(p0.x-2,p0.y-2,4,4),r.transform)=="";
 }
 static bool Display(GameObject g,ConsoleUI ui){if(g==null||!g.activeInHierarchy)return false;foreach(var r in g.GetComponentsInChildren<Renderer>())if(Shown(r,ui))return true;return false;}
 static ParticleSystem.Particle[] dustParticles=new ParticleSystem.Particle[64];
 static bool VisibleDust(GameObject effect,ConsoleUI ui){
  if(effect==null||!effect.activeInHierarchy)return false;var cam=Camera.main;if(cam==null)return false;
  foreach(var ps in effect.GetComponentsInChildren<ParticleSystem>()){
   var render=ps.GetComponent<ParticleSystemRenderer>();if(render==null||!render.enabled||(cam.cullingMask&(1<<ps.gameObject.layer))==0||ps.particleCount==0)continue;
   if(dustParticles.Length<ps.particleCount)dustParticles=new ParticleSystem.Particle[ps.particleCount];
   int count=ps.GetParticles(dustParticles);var main=ps.main;
   for(int i=0;i<count;i++){
    var particle=dustParticles[i];if(particle.GetCurrentColor(ps).a<26||particle.GetCurrentSize(ps)<=.001f)continue;
    Vector3 world=particle.position;
    if(main.simulationSpace==ParticleSystemSimulationSpace.Local)world=ps.transform.TransformPoint(world);
    else if(main.simulationSpace==ParticleSystemSimulationSpace.Custom){if(main.customSimulationSpace==null)continue;world=main.customSimulationSpace.TransformPoint(world);}
    Vector3 p=cam.WorldToScreenPoint(world);if(p.z<=cam.nearClipPlane||p.z>=cam.farClipPlane||p.x<2||p.y<2||p.x>=Screen.width-2||p.y>=Screen.height-2)continue;
    var rect=new Rect(p.x-2,p.y-2,4,4);if(ui.MotionCover(rect,render.transform)==""&&MotionStencil.CanDraw(render,rect))return true;
   }
  }
  return false;
 }
 static void AddParts(CreatureAnimScript root,List<string> form,ConsoleUI ui){
  // Audited display branches, not arbitrary private model/reflection fields.
  string[] fields=null;string type=root.GetType().Name;
  switch(type){
   case "MagicalGirlAnim":fields=new[]{"hero","villain"};break;
   case "NothingAnim":fields=new[]{"Lv1Node","Lv2Node","eggNode"};break;
   case "BakuAnim":fields=new[]{"sheep","chicken"};break;
   case "FireBirdAnim":fields=new[]{"burnt","burning"};break;
   case "PpodaeAnim":fields=new[]{"NormalPpodae","FrenzyPpodae"};break;
   case "FengYunAnim":fields=new[]{"monkAnim","ghoulAnim"};break;
   case "YoungPrinceAnim":fields=new[]{"Normal","Transformed"};break;
   case "BigBadWolfAnim":fields=new[]{"_normalWolf","_badassWolf","_moonObject"};break;
   case "BloodBathAnim":fields=new[]{"hand1","hand2","hand3"};break;
   case "DangoCreatureAnim":fields=new[]{"Shadow_lv2","Shadow_lv3"};break;
  }
  if(fields!=null)foreach(string field in fields){var f=root.GetType().GetField(field,System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic);if(f==null)continue;object value=f.GetValue(root);var array=value as GameObject[];
   if(array!=null){for(int i=0;i<array.Length;i++)if(Display(array[i],ui))form.Add(field+":"+i);continue;}
   var g=value as GameObject;var c=value as Component;if(c!=null)g=c.gameObject;if(Display(g,ui))form.Add(field);
  }
  var al=root as AlriuneAnim;if(al!=null&&al.petals!=null)for(int i=0;i<al.petals.Length;i++)if(Shown(al.petals[i],ui))form.Add("petal:"+i+":"+(int)(Mathf.Clamp01(al.petals[i].color.a)*3));
  var bird=root as SmallBirdAnim;if(bird!=null&&bird.coloredTarget!=null)foreach(var s in bird.coloredTarget)if(Shown(s,ui))form.Add("tint:"+ColorKey(s.color));
  var plague=root as WhiteNightSpace.PlagueDoctorAnim;if(plague!=null&&plague.SkeletonAnim!=null)foreach(var part in plague.SkeletonAnim.activateParts)foreach(var g in part.list)if(Display(g,ui))form.Add("part-object:"+Asset(g));
 }
 static string Motion(SkeletonRenderer sk,List<string> form,string ownerType){
  var a=sk.GetComponent<Animator>();string key=null;
  if(a!=null&&a.isActiveAndEnabled&&a.isInitialized){
   var state=a.GetCurrentAnimatorStateInfo(0);var clips=a.GetCurrentAnimatorClipInfo(0);float best=0;string clip=null;
   foreach(var c in clips)if(c.clip!=null&&c.weight>best){best=c.weight;clip=Asset(c.clip);}
   if(clip!=null)key=Asset(sk.skeletonDataAsset)+"/"+Asset(a.runtimeAnimatorController)+"/"+state.shortNameHash+"/"+clip;
   string phase=ConsoleAppearanceForms.Form(ownerType,state.shortNameHash);if(phase!=null)form.Add(a.IsInTransition(0)?"transition":phase);
  }else{var sa=sk as SkeletonAnimation;if(sa!=null&&sa.state!=null){var tr=sa.state.GetCurrent(0);if(tr!=null&&tr.Animation!=null)key=Asset(sk.skeletonDataAsset)+"/"+tr.Animation.Name;}}
  return key;
 }
 public static string Capture(ConsoleUI ui){
  var timer=System.Diagnostics.Stopwatch.StartNew();Milliseconds=0;
  if(ConsoleMotion.CameraGuard(Camera.main)!="")return "[]";
  var rows=new List<string>();
  foreach(var pair in visible){
   var worker=pair.Key as AgentUnit;var creature=pair.Key as CreatureUnit;
   if(worker==null&&creature==null)continue;
   var forms=new List<string>();var motions=new HashSet<string>();var marks=new HashSet<string>();
   if(creature!=null&&creature.animTarget!=null){
    var root=creature.animTarget;string type=root.GetType().Name;
    foreach(var sk in pair.Value){if(!Display(sk.gameObject,ui))continue;forms.Add("body:"+Asset(sk.skeletonDataAsset));var m=Motion(sk,forms,type);if(m!=null)motions.Add(Item("motion",m,"동작"));
     // This rig explicitly changes attachment colors/parts; do not publish its internal level.
     if(root is WhiteNightSpace.PlagueDoctorAnim&&sk.skeleton!=null)foreach(var slot in sk.skeleton.Slots){
      var ra=slot.Attachment as Spine.RegionAttachment;var ma=slot.Attachment as Spine.MeshAttachment;
      // Accept only parts whose actual displayed bone projects inside this view.
      var pt=Camera.main.WorldToScreenPoint(sk.transform.TransformPoint(new Vector3(slot.Bone.WorldX,slot.Bone.WorldY,0)));
      if(pt.z<=0||pt.x<0||pt.y<0||pt.x>=Screen.width||pt.y>=Screen.height||ui.MotionCover(new Rect(pt.x-2,pt.y-2,4,4),sk.transform)!="")continue;
      if(slot.A<.1f)continue;if(ra!=null&&ra.A>=.1f)forms.Add("part:"+slot.Data.Name+":"+ColorKey(new Color(ra.R,ra.G,ra.B)));
      if(ma!=null&&ma.A>=.1f)forms.Add("part:"+slot.Data.Name+":"+ColorKey(new Color(ma.R,ma.G,ma.B)));
     }
    }
    AddParts(root,forms,ui);
    var old=root as OldLadyAnim;if(old!=null){
     // Authored Puppet2D body; the fog is 3 live particle groups,
     // not three gameplay stacks. Report one visible mark, never the counter.
     var a=old.animator;if(a!=null){forms.Add("body:"+Asset(a.runtimeAnimatorController));if(a.isInitialized){var clips=a.GetCurrentAnimatorClipInfo(0);float weight=0;string clip=null;foreach(var c in clips)if(c.clip!=null&&c.weight>weight){weight=c.weight;clip=Asset(c.clip);}if(clip!=null)motions.Add(Item("motion",Asset(a.runtimeAnimatorController)+"/"+a.GetCurrentAnimatorStateInfo(0).shortNameHash+"/"+clip,"동작"));}}
     if(old.stackEffect!=null)foreach(var effect in old.stackEffect)if(VisibleDust(effect,ui)){marks.Add(Item("mark","visible:black-fog:oldlady","검은 안개"));break;}
    }
    var puppet=root as NothingAnim;if(puppet!=null)foreach(var a in new[]{puppet.Lv1Node,puppet.Lv2Node,puppet.eggNode})if(a!=null&&Display(a.gameObject,ui)){
     forms.Add("body:"+Asset(a.runtimeAnimatorController));if(a.isInitialized){var clips=a.GetCurrentAnimatorClipInfo(0);float weight=0;string clip=null;foreach(var c in clips)if(c.clip!=null&&c.weight>weight){weight=c.weight;clip=Asset(c.clip);}if(clip!=null)motions.Add(Item("motion",Asset(a.runtimeAnimatorController)+"/"+a.GetCurrentAnimatorStateInfo(0).shortNameHash+"/"+clip,"동작"));}
    }
    var yn=root as YouMustHappyAnim;if(yn!=null){if(Shown(yn.spriteYes,ui))marks.Add(Item("mark","text:YES","YES"));if(Shown(yn.spriteNo,ui))marks.Add(Item("mark","text:NO","NO"));}
    Rect resultRect;var result=creature.room==null?null:creature.room.CurrentResultIcon;
    if(result!=null&&result.sprite!=null&&ui.VisibleWorldGraphic(result,out resultRect))marks.Add(Item("mark",SpriteKey(result.sprite),"표식"));
   }
   if(worker!=null&&worker.bufUI!=null&&worker.bufUI.parent!=null)foreach(var b in worker.bufUI.parent.GetComponentsInChildren<BufRenderer>()){
    Rect rect;var im=b.Render;if(im!=null&&im.sprite!=null&&ui.VisibleWorldGraphic(im,out rect))marks.Add(Item("mark",SpriteKey(im.sprite)+":"+ColorKey(im.color),"표식"));
   }
   forms.Sort(StringComparer.Ordinal);string body=forms.Count==0?"null":Item("form",String.Join("|",forms.ToArray()),"상태");
   string room="null",position="null";
   if(creature!=null&&creature.animTarget!=null){var p=creature.animTarget.transform.position;var q=Camera.main.WorldToScreenPoint(p);position="{\"x\":"+RobotomyObserver.Number(q.x)+",\"y\":"+RobotomyObserver.Number(Screen.height-q.y)+"}";
    if(creature.room!=null&&creature.room.RoomSpriteRenderer!=null){var bounds=creature.room.RoomSpriteRenderer.bounds;if(bounds.Contains(new Vector3(p.x,p.y,bounds.center.z)))room=Q(creature.room.GetInstanceID().ToString());}
   }
   rows.Add("{\"subject\":"+Q("unit:"+ConsoleSignals.Identity(pair.Key))+",\"position\":"+position+",\"room_id\":"+room+",\"form\":"+body+",\"motions\":["+String.Join(",",new List<string>(motions).ToArray())+"],\"marks\":["+String.Join(",",new List<string>(marks).ToArray())+"]}");
   if(rows.Count>=128)break;
  }
  string output="["+String.Join(",",rows.ToArray())+"]";Milliseconds=timer.Elapsed.TotalMilliseconds;return output;
 }
}
