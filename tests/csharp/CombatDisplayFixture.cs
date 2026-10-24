// LAB ONLY. Creates real display prefabs without changing HP, inventory or save data.
using System;using System.IO;using UnityEngine;
public class CombatDisplayFixture:MonoBehaviour {
 BarrierEffect barrier;
 void Update(){string dir=Environment.GetEnvironmentVariable("ROBOTOMY_OBSERVATION_DIR");
  if(Application.companyName!="Robotomy_LabPhysical")return;
  string path=Path.Combine(dir,"combat-fixture.request");if(!File.Exists(path))return;string cmd=File.ReadAllText(path).Trim();File.Delete(path);
  try{
   AgentUnit unit=null;var ui=new ConsoleUI();foreach(var u in UnityEngine.Object.FindObjectsOfType<AgentUnit>()){Vector3 p;Rect r;if(ConsoleEmployee.Anchor(u,ui,Camera.main,out p,out r)){unit=u;break;}}
   if(unit==null)throw new Exception("No visible employee");
   if(cmd=="damage")for(int i=0;i<12;i++)DamageEffect.Invoker(unit.model.GetMovableNode(),RwbpType.R,i+1,DefenseInfo.Type.NONE,unit.model);
   if(cmd=="hidden"){
    var a=DamageEffect.Invoker(new Vector3(10000,10000,0),RwbpType.R,999,DefenseInfo.Type.NONE,unit.model);
    var b=DamageEffect.Invoker(unit.model.GetMovableNode(),RwbpType.R,888,DefenseInfo.Type.NONE,unit.model);b.gameObject.SetActive(false);
   }
   if(cmd=="barrier"){barrier=BarrierEffect.MakeBarrier(unit.model);barrier.SetRwbpType(RwbpType.W);}
   if(cmd=="crack")barrier.OnCrack();
   if(cmd=="break")barrier.OnBreak();
   if(cmd=="fade")barrier.OnDisappear();
   if(cmd=="items")foreach(var t in new[]{GlobalBullet.GlobalBulletType.RECOVER_HP,GlobalBullet.GlobalBulletType.RECOVER_MENTAL,GlobalBullet.GlobalBulletType.RESIST_R,GlobalBullet.GlobalBulletType.SLOW})GlobalBullet.GlobalBulletEffect.GenEffect(t,unit.transform.position);
   if(cmd=="projectile"){
    var g=Prefab.LoadPrefab("Effect/Invoke/DamageInfo/FreischutzWeaponBullet");g.transform.position=unit.model.GetCurrentViewPosition();g.transform.localScale=Vector3.one*.5f;
    var b=g.GetComponent<FreischutzWeaponBullet>();b.dir=-1;b._bulletSpeed=3;b.target=g.transform.position-Vector3.right*20;b.Active();UnityEngine.Object.Destroy(g,3);
   }
   var lines=new System.Collections.Generic.List<string>();
   lines.Add("subject=unit:"+ConsoleSignals.Identity(unit));
   foreach(var u in UnityEngine.Object.FindObjectsOfType<AgentUnit>())lines.Add(u.model.GetUnitName()+" renderer="+(u.spineRenderer==null?"null":u.spineRenderer.GetType().FullName));
   if(cmd=="inspect")foreach(var e in UnityEngine.Object.FindObjectsOfType<GlobalBullet.GlobalBulletEffect>()){
    lines.Add("effect="+e.name+" active="+e.gameObject.activeInHierarchy+" main="+(e.particle==null?"null":e.particle.name));
    foreach(var ps in e.GetComponentsInChildren<ParticleSystem>(true))lines.Add(ps.name+" active="+ps.gameObject.activeInHierarchy+" count="+ps.particleCount);
    foreach(var rr in e.GetComponentsInChildren<Renderer>(true))lines.Add(rr.name+" renderer="+rr.GetType().Name+" enabled="+rr.enabled);
   }
   File.WriteAllLines(Path.Combine(dir,"combat-fixture.result"),lines.ToArray());
  }catch(Exception e){File.WriteAllText(Path.Combine(dir,"combat-fixture.result"),e.ToString());}
 }
}
