using System;using System.Collections.Generic;using UnityEngine;
// Tracks drawn projectile renderers, not collision, damage, destinations or owners.
public static class ConsoleProjectile {
 class Track {public string id;public Renderer[] surfaces;public Renderer surface;public Vector3 world;public Vector2 pixel;public float time;public bool seen,moving;}
 static Dictionary<Component,Track> tracks=new Dictionary<Component,Track>();
 static HashSet<string> otherPrefabs=new HashSet<string>();
 static HashSet<string> types=new HashSet<string>{"ProjectileUnit","KnightOfDespiarThrowedSword","FreischutzBullet","FreischutzWeaponBullet","MagicalGirlWeaponProjectile","SlimeGirlProjectile","SlimeGirlWeaponProjectile","BinahProjectile","GeburahProjectile"};
 public static void Clear(){tracks.Clear();}
 public static void Created(string path,GameObject root){
  if(otherPrefabs.Contains(path))return;bool projectile=false;
  foreach(var component in root.GetComponentsInChildren<MonoBehaviour>(true)){
   if(component==null||!types.Contains(component.GetType().Name))continue;
   projectile=true;
   Transform surface=component.transform;var bullet=component as FreischutzWeaponBullet;if(bullet!=null&&bullet._bullet!=null)surface=bullet._bullet;
   var surfaces=new List<Renderer>();foreach(var renderer in surface.GetComponentsInChildren<Renderer>(true))if(renderer is SpriteRenderer || renderer is MeshRenderer)surfaces.Add(renderer);
   if(surfaces.Count>0&&tracks.Count<256&&!tracks.ContainsKey(component))tracks[component]=new Track{id="visual:"+ConsoleSignals.Identity(component),surfaces=surfaces.ToArray()};
  }
  if(!projectile&&otherPrefabs.Count<2048)otherPrefabs.Add(path);
 }
 public static void Sample(ConsoleUI ui){
  Camera cam=Camera.main;bool camera=ConsoleMotion.CameraGuard(cam)=="";
  foreach(var owner in new List<Component>(tracks.Keys)){
   var t=tracks[owner];if(owner==null){if(t.seen)ConsoleCombat.Projectile(t.id,"left_view",null,null);tracks.Remove(owner);continue;}
   Renderer renderer=null;foreach(var candidate in t.surfaces)if(candidate!=null&&candidate.enabled&&candidate.gameObject.activeInHierarchy){var sr=candidate as SpriteRenderer;if(sr!=null&&(sr.sprite==null||sr.color.a<=.01f))continue;renderer=candidate;break;}
   if(renderer==null){if(t.seen)ConsoleCombat.Projectile("visual:"+ConsoleSignals.Identity(owner),"left_view",null,null);t.seen=false;continue;}
   Vector3 pos=Vector3.zero;bool visible=camera&&renderer.enabled&&renderer.gameObject.activeInHierarchy&&(cam.cullingMask&(1<<renderer.gameObject.layer))!=0;
   var sprite=renderer as SpriteRenderer;if(sprite!=null&&(sprite.sprite==null||sprite.color.a<=.01f))visible=false;
   var ps=renderer.GetComponent<ParticleSystem>();if(ps!=null&&ps.particleCount==0)visible=false;
   if(renderer.sharedMaterial!=null&&renderer.sharedMaterial.HasProperty("_Color")&&renderer.sharedMaterial.GetColor("_Color").a<=.01f)visible=false;
   if(visible){pos=cam.WorldToScreenPoint(renderer.bounds.center);visible=pos.z>=cam.nearClipPlane&&pos.z<=cam.farClipPlane&&pos.x>=0&&pos.y>=0&&pos.x<Screen.width&&pos.y<Screen.height&&ui.MotionCover(new Rect(pos.x-2,pos.y-2,4,4),renderer.transform)=="";}
   string id="visual:"+ConsoleSignals.Identity(owner);
   if(!visible){if(t.seen)ConsoleCombat.Projectile(id,"left_view",null,null);t.seen=false;continue;}
   Vector2 point=new Vector2(pos.x,Screen.height-pos.y);Vector2? velocity=null;
   if(t.seen&&t.surface==renderer&&Time.realtimeSinceStartup>t.time){var previous=cam.WorldToScreenPoint(t.world);velocity=new Vector2(pos.x-previous.x,previous.y-pos.y)/(Time.realtimeSinceStartup-t.time);}
   bool moving=velocity.HasValue&&velocity.Value.magnitude>1f;
   if(!t.seen||moving||t.moving!=moving||(point-t.pixel).magnitude>1f)ConsoleCombat.Projectile(id,!t.seen?"visible":moving?"moving":"stationary",point,velocity);
   t.seen=true;t.moving=moving;t.pixel=point;t.surface=renderer;t.world=renderer.bounds.center;t.time=Time.realtimeSinceStartup;
  }
 }
}
