using System;
using System.Collections.Generic;
using UnityEngine;

// Only display objects exist in this fixture. No unlock flags, models or counters are available.
namespace UnityEngine {
    public class GameObject {
        public bool activeSelf = true;
        public Transform transform;
        public readonly List<Component> components = new List<Component>();
        public GameObject(Transform parent) { transform = new Transform(); transform.gameObject = this; transform.parent = parent;
            if (parent != null) parent.children.Add(transform); components.Add(transform); }
        public bool activeInHierarchy { get { return activeSelf && (transform.parent == null || transform.parent.gameObject.activeInHierarchy); } }
        public T Add<T>() where T:Component,new() { var c = new T(); c.gameObject = this; components.Add(c); return c; }
    }
    public class Component {
        public GameObject gameObject;
        public Transform transform { get { return gameObject.transform; } }
        public T GetComponent<T>() where T:Component { foreach(var c in gameObject.components) if(c is T) return (T)c; return null; }
        public T GetComponentInParent<T>() where T:Component { for(var t=transform;t!=null;t=t.parent) {var c=t.GetComponent<T>();if(c!=null)return c;}return null; }
        public T[] GetComponentsInChildren<T>(bool includeInactive) where T:Component {
            var result=new List<T>(); Walk(transform, result,includeInactive);return result.ToArray(); }
        static void Walk<T>(Transform t,List<T> result,bool all) where T:Component {
            if(all || t.gameObject.activeInHierarchy) foreach(var c in t.gameObject.components) if(c is T)result.Add((T)c);
            foreach(var child in t.children)Walk(child,result,all); }
    }
    public class Transform:Component {
        public Transform parent;
        public readonly List<Transform> children = new List<Transform>();
        public bool IsChildOf(Transform target) { for(var p=this;p!=null;p=p.parent)if(p==target)return true;return false; }
    }
    public class MonoBehaviour:Component {}
}
namespace UnityEngine.UI { public class Text:Component {} public class Image:Component {} }
public class CreatureInfoController:MonoBehaviour {}
namespace CreatureInfo {
    public class CreatureInfoOpenArea:MonoBehaviour {}
    public class CreatureInfoKitOpenArea:MonoBehaviour {}
    public class CreatureInfoStatRoot:CreatureInfoController { public CreatureInfoOpenArea Open; }
    public class CreatureInfoEscapeRoot:CreatureInfoController { public CreatureInfoOpenArea Open; public GameObject BlockActiveControl; }
    public class CreatureInfoWorkSlot:CreatureInfoController { public CreatureInfoOpenArea Open; }
    public class CreatureInfoCaretakingSlot:CreatureInfoController { public CreatureInfoOpenArea Open; }
    public class CreatureInfoKitStatRoot:CreatureInfoController { public CreatureInfoKitOpenArea Open; }
    public class CreatureInfoKitDataSlot:MonoBehaviour { public GameObject disabled; }
    public class EquipSlot { public GameObject ActiveControl,BlockControl; }
    public class CreatureInfoEquipmentRoot:CreatureInfoController { public EquipSlot giftSlot,weaponSlot,armorSlot; }
}
namespace InGameUI { public class AgentUI:MonoBehaviour { public UnityEngine.UI.Image BlackHide; } }
namespace CommandWindow {
    public class KitCreatureRegion { public UnityEngine.UI.Text UseCountText,UseCountTitleText; }
    public class CommandWindow:MonoBehaviour { public KitCreatureRegion kitCreatureRegion;public GameObject RootControl;public static CommandWindow CurrentWindow; }
    public class AgentSlot:MonoBehaviour { public UnityEngine.UI.Text HealthText,MentalText;public UnityEngine.UI.Image HealthFill,MentalFill; }
}
class Program {
    static int checks;
    static GameObject Go(Transform parent) {return new GameObject(parent);}
    static T Child<T>(Transform parent) where T:Component,new() {return Go(parent).Add<T>();}
    static void Check(Transform item,bool allowed,string name) {
        checks++; if(ConsoleDisclosure.Allows(item)!=allowed)throw new Exception(name+": "+ConsoleDisclosure.RejectReason(item)); }
    static CreatureInfo.EquipSlot Equip(Transform parent) {
        var root=Go(parent);return new CreatureInfo.EquipSlot {ActiveControl=root,BlockControl=Go(root.transform)}; }
    static void Main() {
        Check(null,false,"null");
        var free=Go(null);Check(free.transform,true,"ordinary display");
        var child=Go(free.transform); free.activeSelf=false; Check(child.transform,false,"closed ancestor");free.activeSelf=true;
        var kit=Child<CreatureInfo.CreatureInfoKitStatRoot>(null);
        var value=Go(kit.transform);Check(value.transform,false,"missing tool cover");
        kit.Open=Child<CreatureInfo.CreatureInfoKitOpenArea>(kit.transform);
        var threshold=Go(kit.Open.transform);Check(value.transform,false,"tool prefilled identity");
        Check(threshold.transform,true,"visible tool unlock threshold");
        kit.Open.gameObject.activeSelf=false;Check(value.transform,true,"tool unlocked");
        Check(threshold.transform,false,"hidden threshold");kit.Open.gameObject.activeSelf=true;
        Check(value.transform,false,"tool relocked");
        var row=Child<CreatureInfo.CreatureInfoKitDataSlot>(null);value=Go(row.transform);
        Check(value.transform,false,"missing row cover");row.disabled=Go(row.transform);threshold=Go(row.disabled.transform);
        Check(value.transform,false,"prefilled row");Check(threshold.transform,true,"row threshold");
        row.disabled.activeSelf=false;Check(value.transform,true,"row unlocked");
        var ego=Child<CreatureInfo.CreatureInfoEquipmentRoot>(null);
        ego.giftSlot=Equip(ego.transform);ego.weaponSlot=Equip(ego.transform);ego.armorSlot=Equip(ego.transform);
        value=Go(ego.weaponSlot.ActiveControl.transform);threshold=Go(ego.weaponSlot.BlockControl.transform);
        Check(value.transform,false,"prefilled weapon");Check(threshold.transform,true,"weapon unlock condition");
        ego.weaponSlot.BlockControl.activeSelf=false;Check(value.transform,true,"weapon unlocked independent locked gift");
        ego.weaponSlot.BlockControl=null;Check(value.transform,false,"missing EGO cover");
        var hud=Child<InGameUI.AgentUI>(null);value=Go(hud.transform);Check(value.transform,false,"missing blackhide");
        hud.BlackHide=Child<UnityEngine.UI.Image>(hud.transform);Check(value.transform,false,"HUD before research");
        hud.BlackHide.gameObject.activeSelf=false;Check(value.transform,true,"HUD displayed after research");
        hud.BlackHide.gameObject.activeSelf=true;Check(value.transform,false,"HUD hidden again");
        var normal=Child<CreatureInfo.CreatureInfoStatRoot>(null);value=Go(normal.transform);
        Check(value.transform,false,"missing normal cover");normal.Open=Child<CreatureInfo.CreatureInfoOpenArea>(normal.transform);
        threshold=Go(normal.Open.transform);Check(value.transform,false,"normal lock");Check(threshold.transform,true,"normal cost");
        normal.Open.gameObject.activeSelf=false;Check(value.transform,true,"normal unlocked");
        var section=Child<CreatureInfoController>(null);var open=Child<CreatureInfo.CreatureInfoKitOpenArea>(section.transform);
        value=Go(section.transform);Check(value.transform,false,"sibling tool cover");open.gameObject.activeSelf=false;
        Check(value.transform,true,"sibling tool unlocked");
        var cmd=Child<CommandWindow.CommandWindow>(null);value=Go(cmd.transform);Check(value.transform,false,"missing command refs");
        cmd.kitCreatureRegion=new CommandWindow.KitCreatureRegion { UseCountText=Child<UnityEngine.UI.Text>(cmd.transform),UseCountTitleText=Child<UnityEngine.UI.Text>(cmd.transform)};
        Check(cmd.kitCreatureRegion.UseCountText.transform,false,"cumulative count or time");
        Check(cmd.kitCreatureRegion.UseCountTitleText.transform,false,"cumulative title");Check(value.transform,true,"ordinary command label");
        var agent=Child<CommandWindow.AgentSlot>(null);value=Go(agent.transform);Check(value.transform,false,"missing agent refs");
        agent.HealthText=Child<UnityEngine.UI.Text>(agent.transform);agent.MentalText=Child<UnityEngine.UI.Text>(agent.transform);
        agent.HealthFill=Child<UnityEngine.UI.Image>(agent.transform);agent.MentalFill=Child<UnityEngine.UI.Image>(agent.transform);
        Check(agent.HealthText.transform,true,"HP text still requires final visibility");Check(agent.MentalText.transform,true,"SP text still requires final visibility");
        Check(agent.HealthFill.transform,false,"unverified HP fill");Check(agent.MentalFill.transform,false,"unverified SP fill");
        Check(value.transform,true,"agent unrelated label");
        var escape=Child<CreatureInfo.CreatureInfoEscapeRoot>(null);value=Go(escape.transform);
        escape.Open=Child<CreatureInfo.CreatureInfoOpenArea>(escape.transform);escape.Open.gameObject.activeSelf=false;
        Check(value.transform,false,"missing nonescape cover");escape.BlockActiveControl=Go(escape.transform);
        Check(value.transform,false,"nonescape placeholder hides prefilled resistance");
        threshold=Go(escape.BlockActiveControl.transform);Check(threshold.transform,true,"nonescape placeholder");
        escape.BlockActiveControl.activeSelf=false;Check(value.transform,true,"escape open and uncovered");
        var work=Child<CreatureInfo.CreatureInfoWorkSlot>(null);value=Go(work.transform);
        Check(value.transform,false,"missing work observation cover");work.Open=Child<CreatureInfo.CreatureInfoOpenArea>(work.transform);
        Check(value.transform,false,"work locked");
        var care=Child<CreatureInfo.CreatureInfoCaretakingSlot>(null);value=Go(care.transform);
        care.Open=Child<CreatureInfo.CreatureInfoOpenArea>(care.transform);Check(value.transform,false,"care locked");
        care.Open.gameObject.activeSelf=false;Check(value.transform,true,"care unlocked");
        var detached=Child<CommandWindow.CommandWindow>(null);detached.RootControl=Go(null);
        CommandWindow.CommandWindow.CurrentWindow=detached;
        value=Go(detached.RootControl.transform);Check(value.transform,false,"detached controller missing references");
        detached.kitCreatureRegion=new CommandWindow.KitCreatureRegion {
            UseCountText=Child<UnityEngine.UI.Text>(detached.RootControl.transform),
            UseCountTitleText=Child<UnityEngine.UI.Text>(detached.RootControl.transform)};
        Check(detached.kitCreatureRegion.UseCountText.transform,false,"detached controller cumulative count");
        Check(detached.kitCreatureRegion.UseCountTitleText.transform,false,"detached controller cumulative title");
        Check(value.transform,true,"detached controller unrelated display");
        Check(cmd.kitCreatureRegion.UseCountText.transform,false,"ancestor fallback with another current window");
        detached.kitCreatureRegion=null;Check(free.transform,true,"missing refs do not block outside current root");
        CommandWindow.CommandWindow.CurrentWindow=null;
        Console.WriteLine("PASS "+checks+" disclosure checks");
    }
}
