using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using GlobalBullet;

// Learn displayed geometry and direct ordinary connections between visible passages only.
// Never export raw navigation nodes, teleport destinations, or unopened areas.
public sealed class ConsoleFacilityMap {
 [Serializable] public class Landmark {public string id,kind,department;public float x,y;}
 [Serializable] public class Link {public string a,b;}
 [Serializable] public class Atlas {public int version=1;public Landmark[] landmarks=new Landmark[0];public Link[] connections=new Link[0];}
 [Serializable] class Point {public float x,y;}
 readonly Dictionary<string,Landmark> known=new Dictionary<string,Landmark>();
 readonly Dictionary<string,Link> links=new Dictionary<string,Link>();
 public string PendingSave;
 string path;float nextSave;
 public string PathName {get{return path;}}
 public void Initialize(string directory){
  path=Path.Combine(directory,"facility-map.json");
  try{
   if(new FileInfo(path).Length>1048576)return;
   var a=SharpJson.JsonDecoder.DecodeText(File.ReadAllText(path)) as IDictionary<string,object>;
   if(a==null || Convert.ToInt32(a["version"])!=1)return;
   var rows=a["landmarks"] as IList<object>;if(rows==null || rows.Count>2048)return;
   foreach(var value in rows){var r=(IDictionary<string,object>)value;string id=(string)r["id"],kind=(string)r["kind"];float x=Convert.ToSingle(r["x"]),y=Convert.ToSingle(r["y"]);if(string.IsNullOrEmpty(id) || float.IsNaN(x) || float.IsNaN(y) || float.IsInfinity(x) || float.IsInfinity(y))continue;known[id]=new Landmark{id=id,kind=kind,x=x,y=y,department=r.ContainsKey("department")?r["department"] as string:null};}
   object raw;if(a.TryGetValue("connections",out raw))foreach(var value in (IList<object>)raw){var e=(IDictionary<string,object>)value;string from=(string)e["a"],to=(string)e["b"];if(known.ContainsKey(from) && known.ContainsKey(to))links[from+"|"+to]=new Link{a=from,b=to};}
  }catch(Exception ex){Debug.LogWarning("Robotomy map restore: "+ex.Message);}

 }
 static string Q(string s){return s==null?"null":RobotomyObserver.Quote(s);}
 static string N(float n){return RobotomyObserver.Number(n);}
 static string Kind(PassageObject p){
  if(p.model!=null)switch(p.model.GetPassageType()){case PassageType.VERTICAL:return "elevator";case PassageType.HORIZONTAL:return "corridor";case PassageType.SEFIRA:return "main_room";case PassageType.DEPARTMENT:return "junction";}
  switch(p.type){case SpaceObjectType.ELEVATORLONG:case SpaceObjectType.ELEVATORSHORT:return "elevator";
   case SpaceObjectType.SEFIRAMAIN:return "main_room";case SpaceObjectType.HUBSHORT:case SpaceObjectType.HUBLONG:return "junction";
   case SpaceObjectType.HALLWAY:case SpaceObjectType.LONGHALLWAY:return "corridor";default:return "passage";}
 }
 static bool Routed(Vector2 pixel){
  var es=EventSystem.current;if(es==null)return false;var data=new PointerEventData(es);data.position=pixel;
  var hits=new List<RaycastResult>();es.RaycastAll(data,hits);if(hits.Count==0)return false;
  var h=ExecuteEvents.GetEventHandler<IPointerClickHandler>(hits[0].gameObject);var t=h==null?null:h.GetComponent<EventTrigger>();if(t==null)return false;
  foreach(var e in t.triggers)if(e.eventID==EventTriggerType.PointerClick)for(int i=0;i<e.callback.GetPersistentEventCount();i++)
   if(e.callback.GetPersistentTarget(i) is UnitMouseEventManager && e.callback.GetPersistentMethodName(i)=="OnPointerClick")return true;
  return false;
 }
 static bool OwnPoint(PassageObject p,Vector2 world){
  bool own=false;foreach(var c in Physics2D.OverlapPointAll(world)){
   var target=c.GetComponent<UnitMouseEventTarget>();if(target==null)continue;
   if(target.target==p)own=true;else if(target.target is IMouseCommandTarget)return false;
  }return own;
 }
 sealed class DisplaySpace {public string id;public Bounds bounds;}
 static readonly Dictionary<PassageObjectModel,DisplaySpace> current=new Dictionary<PassageObjectModel,DisplaySpace>();
 public static string Locate(UnityEngine.Object owner,Vector3 point){
  UnitModel unit=null;var worker=owner as WorkerUnit;var creature=owner as CreatureUnit;
  if(worker!=null)unit=worker.workerModel;else if(creature!=null)unit=creature.model;
  var node=unit==null?null:unit.GetMovableNode();var passage=node==null?null:node.currentPassage;DisplaySpace space;
  if(passage==null || !current.TryGetValue(passage,out space))return "null";
  var b=space.bounds;if(b.size.x<=.001f || b.size.y<=.001f)return "null";
  // Visible sampled body/label anchor, not hidden path position or destination.
  float u=(point.x-b.min.x)/b.size.x,v=(point.y-b.min.y)/b.size.y;
  return "{\"facility_id\":"+Q(space.id)+",\"map_position\":{\"x\":"+N(point.x)+",\"y\":"+N(point.y)+"},\"relative\":{\"u\":"+N(u)+",\"v\":"+N(v)+"},\"extent\":{\"width\":"+N(b.size.x)+",\"height\":"+N(b.size.y)+"},\"basis\":\"visible_anchor_in_display_bounds\"}";
 }
 public string Capture(ConsoleUI ui){
  current.Clear();
  var visible=new List<string>();bool dirty=false;var cam=Camera.main;var observed=new Dictionary<PassageObjectModel,string>();
  if(SceneManager.GetActiveScene().name=="Main" && ConsoleMotion.CameraGuard(cam)==""){
   foreach(var p in UnityEngine.Object.FindObjectsOfType<PassageObject>()){
    // A rendered authored frame is our evidence that this facility surface is visible.
    var frame=p.sefiraFrame;
    // Shipped Malkuth/Yesod prefabs leave sefiraFrame unset on corridors and elevators.
    // Their authored outer-frame sprites identify the actual static visual branch.
    if(frame==null)foreach(var r in p.GetComponentsInChildren<SpriteRenderer>())if(r.name=="Frame" || r.name=="PassageHub_Frame" || r.name=="ElevatorPassage_Frame"){frame=r;break;}
    if(frame==null || !frame.enabled || !frame.gameObject.activeInHierarchy || !frame.isVisible || frame.sprite==null || frame.color.a<=.05f || (cam.cullingMask&(1<<frame.gameObject.layer))==0)continue;
    Collider2D own=null;foreach(var t in p.GetComponentsInChildren<UnitMouseEventTarget>())if(t.target==p){var c=t.GetComponent<Collider2D>();if(c!=null && c.enabled){own=c;break;}}
    if(own==null && Kind(p)!="elevator")continue;
    Vector3 center=own==null?frame.bounds.center:own.bounds.center,screen=cam.WorldToScreenPoint(center);
    if(screen.z<=0 || screen.x<0 || screen.y<0 || screen.x>=Screen.width || screen.y>=Screen.height)continue;
    var region=new Rect(screen.x-1,screen.y-1,2,2);
    if(ui.MotionCover(region,p.transform)!="")continue;
    // Persist one observed anchor; do not reveal an offscreen extent of a long corridor.
    string kind=Kind(p),id=kind+":"+center.x.ToString("F2",CultureInfo.InvariantCulture)+":"+center.y.ToString("F2",CultureInfo.InvariantCulture);
    if(!known.ContainsKey(id) && known.Count<2048){known[id]=new Landmark{id=id,kind=kind,x=center.x,y=center.y,department=p.model==null || p.model.GetSefira()==null?null:LocalizeTextDataModel.instance.GetTextAppend(p.model.GetSefira().name,"Name")};dirty=true;}
    if(!known.ContainsKey(id))continue;if(p.model!=null){observed[p.model]=id;current[p.model]=new DisplaySpace{id=id,bounds=frame.bounds};}
    string click="null";
    if(own!=null && UnitMouseEventManager.instance!=null && !UnitMouseEventManager.instance.DefaultClickBlocked &&
      (GlobalBulletWindow.CurrentWindow==null || GlobalBulletWindow.CurrentWindow.CurrentSelectedBullet==GlobalBulletType.NONE)){
     // Prefer a clear point in this actual right-click region, avoiding staff/enemies on it.
     foreach(float fraction in new float[]{.5f,.25f,.75f,.1f,.9f}){
      var w=new Vector3(Mathf.Lerp(own.bounds.min.x,own.bounds.max.x,fraction),center.y,center.z);var q=cam.WorldToScreenPoint(w);
      if(q.z<=0 || q.x<0 || q.y<0 || q.x>=Screen.width || q.y>=Screen.height || !OwnPoint(p,w) || !Routed(q))continue;
      click="{\"x\":"+N(q.x)+",\"y\":"+N(Screen.height-q.y)+",\"button\":\"right\"}";break;
     }
    }
    visible.Add("{\"id\":"+Q(id)+",\"kind\":"+Q(kind)+",\"position\":{\"x\":"+N(screen.x)+",\"y\":"+N(Screen.height-screen.y)+"},\"click\":"+click+",\"status\":"+ConsoleFacilityStatus.Capture(p,cam,ui)+"}");
   }
   foreach(var room in UnityEngine.Object.FindObjectsOfType<IsolateRoom>()){
    var surface=room.RoomSpriteRenderer;if(surface==null || !surface.enabled || !surface.gameObject.activeInHierarchy || !surface.isVisible || surface.sprite==null || surface.color.a<=.05f)continue;
    string click=ConsoleRoomClick.Capture(room);if(click=="null")continue;
    var point=JsonUtility.FromJson<Point>(click);Vector3 anchor=room.transform.position;var roomPassage=room.TargetUnit==null || room.TargetUnit.model==null || room.TargetUnit.model.roomNode==null?null:room.TargetUnit.model.roomNode.GetAttachedPassage();
    string id="containment:"+anchor.x.ToString("F2",CultureInfo.InvariantCulture)+":"+anchor.y.ToString("F2",CultureInfo.InvariantCulture);
    if(!known.ContainsKey(id) && known.Count<2048){known[id]=new Landmark{id=id,kind="containment",x=anchor.x,y=anchor.y,department=roomPassage==null || roomPassage.GetSefira()==null?null:LocalizeTextDataModel.instance.GetTextAppend(roomPassage.GetSefira().name,"Name")};dirty=true;}
    if(!known.ContainsKey(id))continue;if(roomPassage!=null){observed[roomPassage]=id;current[roomPassage]=new DisplaySpace{id=id,bounds=surface.bounds};}
    visible.Add("{\"id\":"+Q(id)+",\"kind\":\"containment\",\"position\":{\"x\":"+N(point.x)+",\"y\":"+N(point.y)+"},\"click\":{\"x\":"+N(point.x)+",\"y\":"+N(point.y)+",\"button\":\"left\"}}");
   }
  }
  // The game pathfinder follows GetEdges/ConnectedNode and destination.activate;
  // MapEdge.activated is not its gate. Only ordinary edges with both visible endpoints qualify.
  foreach(var source in observed)foreach(var node in source.Key.GetNodeList()){
   if(!node.activate)continue;
   foreach(var edge in node.GetEdges()){
    var other=edge.ConnectedNode(node);if(other==null || !other.activate)continue;
    var dest=other.GetAttachedPassage();string to;
    if(dest==null || !observed.TryGetValue(dest,out to) || to==source.Value)continue;
    var p1=cam.WorldToScreenPoint(node.GetPosition());var p2=cam.WorldToScreenPoint(other.GetPosition());
    if(p1.z<=0 || p2.z<=0 || p1.x<0 || p1.y<0 || p1.x>=Screen.width || p1.y>=Screen.height || p2.x<0 || p2.y<0 || p2.x>=Screen.width || p2.y>=Screen.height)continue;
    string a=source.Value,b=to;if(String.CompareOrdinal(a,b)>0){a=to;b=source.Value;}
    string key=a+"|"+b;if(!links.ContainsKey(key)){links[key]=new Link{a=a,b=b};dirty=true;}
   }
  }
  var entries=new List<Landmark>(known.Values);entries.Sort((a,b)=>String.CompareOrdinal(a.id,b.id));
  var serialized=new List<string>();foreach(var l in entries)serialized.Add("{\"id\":"+Q(l.id)+",\"kind\":"+Q(l.kind)+",\"department\":"+Q(l.department)+",\"x\":"+N(l.x)+",\"y\":"+N(l.y)+"}");
  var edges=new List<string>();var keys=new List<string>(links.Keys);keys.Sort(StringComparer.Ordinal);foreach(var key in keys){var e=links[key];edges.Add("{\"a\":"+Q(e.a)+",\"b\":"+Q(e.b)+"}");}
  string json="{\"version\":1,\"landmarks\":["+String.Join(",",serialized.ToArray())+"],\"connections\":["+String.Join(",",edges.ToArray())+"]}";
  if(dirty || (known.Count>0 && Time.realtimeSinceStartup>=nextSave)){PendingSave=json;nextSave=Time.realtimeSinceStartup+10;}
  return "{\"known\":"+json+",\"visible\":["+String.Join(",",visible.ToArray())+"]}";
 }
}
