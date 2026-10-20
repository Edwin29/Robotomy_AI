using System;
using System.Collections.Generic;
using UnityEngine;

// Read presentation branches only, after the facility camera/unlock gate.
public static class ConsoleFacilityStatus {
 static bool Visible(SpriteRenderer r,Camera cam,ConsoleUI ui,bool blinking=false){
  if(r==null || !r.enabled || !r.gameObject.activeInHierarchy || r.sprite==null || !r.isVisible || (!blinking && r.color.a<=.05f) || (cam.cullingMask&(1<<r.gameObject.layer))==0)return false;
  var q=cam.WorldToScreenPoint(r.bounds.center);
  return q.z>0 && q.x>=0 && q.y>=0 && q.x<Screen.width && q.y<Screen.height && ui.MotionCover(new Rect(q.x-1,q.y-1,2,2),r.transform)=="";
 }
 static string VisualId(SpriteRenderer r){
  // Stable opaque identity of the displayed art, not a creature/model identifier.
  string s=r.sprite.texture.name+":"+r.sprite.rect.ToString();uint h=2166136261;
  foreach(char c in s){h^=c;h*=16777619;}return "surface-"+h.ToString("x8");
 }
 static string Appearance(SpriteRenderer r){
  string[] paths={"Sprites/CreatureSprite/1.76Mhz/Noise2","Sprites/CreatureSprite/FireBird/PassageFilter","Sprites/CreatureSprite/Shark/Filter","Sprites/CreatureSprite/Yggdrasil/filter_hall"};
  string[] codes={"static_noise","flames_embers","rainbow_waves","green_mist_particles"};
  for(int i=0;i<paths.Length;i++)if(r.sprite.texture==Resources.Load<Texture2D>(paths[i]))return codes[i];
  return "unclassified";
 }
 public static string Capture(PassageObject p,Camera cam,ConsoleUI ui){
  string warning="null";var way=p as PassageWayObject;
  if(way!=null && way.EscapeFrame!=null){var e=way.EscapeFrame;
   if(!e.gameObject.activeInHierarchy)warning="\"off\"";
   else if(Visible(e,cam,ui,true))warning="\"red\"";
  }
  var effects=new List<string>();var seen=new HashSet<string>();
  foreach(var f in p.GetComponentsInChildren<SefiraFilterMgr>()){
   // A nested passage owns its own effects.
   if(f.GetComponentInParent<PassageObject>()!=p)continue;
   foreach(var r in f.GetComponentsInChildren<SpriteRenderer>())if(Visible(r,cam,ui)){
    string id=VisualId(r);if(seen.Add(id))effects.Add("{\"visual_id\":"+RobotomyObserver.Quote(id)+",\"appearance\":"+RobotomyObserver.Quote(Appearance(r))+"}");
   }
  }
  return "{\"warning_light\":"+warning+",\"surface_effects\":["+string.Join(",",effects.ToArray())+"]}";
 }
}
