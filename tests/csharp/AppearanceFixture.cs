// LAB ONLY: real serialized display prefabs, no model, buffs, inventory or save mutations.
using System;using System.IO;using System.Collections;using System.Collections.Generic;using UnityEngine;using Spine.Unity;
public class AppearanceFixture:MonoBehaviour {
 GameObject display,mark;CreatureUnit unit;CreatureAnimScript art;AgentUnit employee;bool busy;
 string Dir {get{return Environment.GetEnvironmentVariable("ROBOTOMY_OBSERVATION_DIR");}}
 void Update(){if(Application.companyName!="Robotomy_LabPhysical"||busy)return;string p=Path.Combine(Dir,"appearance-fixture.request");if(!File.Exists(p))return;string cmd=File.ReadAllText(p).Trim();File.Delete(p);StartCoroutine(Run(cmd));}
 IEnumerator Run(string cmd){busy=true;string error=null;
  try{Execute(cmd);}catch(Exception e){error=e.ToString();}
  yield return new WaitForEndOfFrame();
  try{
   if(error!=null)throw new Exception(error);
   ConsoleAppearance.Begin();var ui=new ConsoleUI();
   if(art!=null&&display.activeInHierarchy){foreach(var sk in art.GetComponentsInChildren<SkeletonRenderer>())foreach(var r in sk.GetComponentsInChildren<Renderer>()){Vector3 w;Rect region;if(r.enabled&&MotionSurface.PickPresence(r,Camera.main,(rect,p)=>ui.MotionCover(rect,r.transform)=="",out w,out region)){ConsoleAppearance.Seen(unit,sk);break;}}}
   if(employee!=null){Vector3 w;Rect r;if(ConsoleEmployee.Anchor(employee,ui,Camera.main,out w,out r))ConsoleAppearance.Seen(employee,employee.spineRenderer);}
   var prior=unit==null?null:unit.animTarget;try{if(unit!=null&&art!=null){unit.animTarget=art;ConsoleAppearance.SeenNative(unit,ui);}File.WriteAllText(Path.Combine(Dir,"appearance-fixture.result.json"),ConsoleAppearance.Capture(ui));}finally{if(unit!=null)unit.animTarget=prior;}
   var lines=new List<string>();if(display!=null){lines.Add("root="+display.name+" position="+display.transform.position+" scale="+display.transform.lossyScale+" active="+display.activeInHierarchy+" art="+art);foreach(var r in display.GetComponentsInChildren<Renderer>(true)){Vector3 w;Rect rect;bool shown=MotionSurface.PickPresence(r,Camera.main,(box,p)=>true,out w,out rect);var mf=r.GetComponent<MeshFilter>();if(mf!=null&&mf.sharedMesh!=null)lines.Add("mesh vertices="+mf.sharedMesh.vertexCount+" submeshes="+mf.sharedMesh.subMeshCount);lines.Add(r.name+" active="+r.gameObject.activeInHierarchy+" enabled="+r.enabled+" bounds="+r.bounds+" screen="+Camera.main.WorldToScreenPoint(r.bounds.center)+" shown="+shown+" why="+MotionSurface.LastFailure);}}File.WriteAllLines(Path.Combine(Dir,"appearance-fixture-diagnostics.txt"),lines.ToArray());
  }catch(Exception e){File.WriteAllText(Path.Combine(Dir,"appearance-fixture.error"),e.ToString());}
  busy=false;
 }
 void Execute(string cmd){var ui=new ConsoleUI();if(employee==null)foreach(var e in UnityEngine.Object.FindObjectsOfType<AgentUnit>()){Vector3 p;Rect r;if(ConsoleEmployee.Anchor(e,ui,Camera.main,out p,out r)){employee=e;break;}}
  if(unit==null)foreach(var c in UnityEngine.Object.FindObjectsOfType<CreatureUnit>())if(c.animTarget!=null){unit=c;break;}
  if(cmd.StartsWith("load:")){
   if(display!=null)Destroy(display);string prefab=cmd.Substring(5);display=Prefab.LoadPrefab("Unit/CreatureAnimator/"+prefab);art=display.GetComponent<CreatureAnimScript>();
   foreach(var b in display.GetComponentsInChildren<MonoBehaviour>(true))if(b!=null&&!(b is SkeletonRenderer)&&!(b.GetType().Namespace??"").StartsWith("Spine"))b.enabled=false;
   var cam=Camera.main;Vector3 anchor;Rect region;float depth=ConsoleEmployee.Anchor(employee,ui,cam,out anchor,out region)?cam.WorldToScreenPoint(anchor).z:30;
   display.transform.position=cam.ScreenToWorldPoint(new Vector3(Screen.width*.65f,Screen.height*.15f,depth));display.transform.localScale=new Vector3(1,1,display.transform.localScale.z);
   foreach(var r in display.GetComponentsInChildren<Renderer>(true))r.sortingOrder=30000;
   foreach(var a in display.GetComponentsInChildren<Animator>()){a.updateMode=AnimatorUpdateMode.UnscaledTime;a.speed=0;}
  }else if(cmd.StartsWith("state:")){string state=cmd.Substring(6);foreach(var a in display.GetComponentsInChildren<Animator>())if(a.HasState(0,Animator.StringToHash(state))){a.Play(state,0,0);a.Update(0);}}
  else if(cmd.StartsWith("param:")){var pair=cmd.Substring(6).Split(':');foreach(var a in display.GetComponentsInChildren<Animator>()){foreach(var p in a.parameters)if(p.name==pair[0])a.SetInteger(pair[0],int.Parse(pair[1]));a.speed=1;a.Update(.4f);a.Update(.4f);a.speed=0;}}
  else if(cmd.StartsWith("form:")){string field=cmd.Substring(5);foreach(var f in art.GetType().GetFields()){if(f.Name!="hero"&&f.Name!="villain"&&f.Name!="Lv1Node"&&f.Name!="Lv2Node"&&f.Name!="eggNode")continue;object value=f.GetValue(art);var g=value as GameObject;var c=value as Component;if(c!=null)g=c.gameObject;if(g!=null)g.SetActive(f.Name==field);}}
  else if(cmd.StartsWith("branch:")){string name=cmd.Substring(7);foreach(var t in display.GetComponentsInChildren<Transform>(true))if(t.name==name)t.gameObject.SetActive(!t.gameObject.activeSelf);}
  else if(cmd.StartsWith("position:")){var xy=cmd.Substring(9).Split(',');var cam=Camera.main;float depth=cam.WorldToScreenPoint(display.transform.position).z;display.transform.position=cam.ScreenToWorldPoint(new Vector3(float.Parse(xy[0]),float.Parse(xy[1]),depth));}
  else if(cmd=="yes"||cmd=="no"){var a=art as YouMustHappyAnim;a.spriteYes.enabled=cmd=="yes";a.spriteNo.enabled=cmd=="no";}
  else if(cmd=="mark"){
   if(employee==null)throw new Exception("No visible employee");var prefab=Resources.Load<GameObject>("Prefabs/Unit/CreatureAnimator/OtherWorldPortraitAnim");var src=prefab.GetComponent<OtherWorldPortraitAnim>().bufRenderer;
   mark=UnityEngine.Object.Instantiate(src.gameObject);var b=mark.GetComponent<BufRenderer>();b.Render.transform.SetParent(employee.bufUI.parent,false);b.Render.transform.localPosition=Vector3.zero;b.Render.transform.localScale=Vector3.one;
  }else if(cmd=="mark_hide")mark.SetActive(false);
  else if(cmd=="mark_offscreen")mark.transform.position=new Vector3(10000,10000,0);
  else if(cmd=="offscreen")display.transform.position=new Vector3(10000,10000,0);
  else if(cmd=="hide")display.SetActive(false);
  else if(cmd=="clear"){if(display!=null)Destroy(display);if(mark!=null)Destroy(mark);art=null;}
 }
}
