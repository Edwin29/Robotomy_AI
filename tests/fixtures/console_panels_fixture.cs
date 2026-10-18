using System;
using System.Collections.Generic;
using System.Linq;
namespace UnityEngine {
    public class Object {
        public static readonly List<Object> scene = new List<Object>();
        public static T[] FindObjectsOfType<T>() where T : Object { return scene.OfType<T>().ToArray(); }
    }
    public class GameObject : Object { public readonly string name; public GameObject(string n) { name=n; } }
    public class Component : Object { public GameObject gameObject; }
    public class MonoBehaviour : Component { }
    public class RectTransform : Component {
        public readonly List<Component> children = new List<Component>();
        public T[] GetComponentsInChildren<T>(bool inactive) { return children.OfType<T>().ToArray(); }
    }
    public static class Time { public static float realtimeSinceStartup; }
}
namespace UnityEngine.UI { public class Text : UnityEngine.Component { public Text(string n) { gameObject=new UnityEngine.GameObject(n); } } }
namespace CommandWindow { public class CommandWindow { public static CommandWindow CurrentWindow; public UnityEngine.GameObject RootControl; } }
public class MissionUI { public static MissionUI instance; public UnityEngine.RectTransform listParent; }
public class MissionSlot : UnityEngine.Component { public UnityEngine.UI.Text txt; }
public class MissionPopupUI {
    public static MissionPopupUI instance;
    public UnityEngine.UI.Text missionNameText, missionDescText, missionTeamNameText, missionDiagText;
}
public class LoggingScript { public UnityEngine.RectTransform parent; }
public class SystemLogScript : UnityEngine.MonoBehaviour { public LoggingScript script; }
public class LogItemScript : UnityEngine.Component { public UnityEngine.UI.Text textTarget; }
public class ConversationUI : UnityEngine.MonoBehaviour { public UnityEngine.UI.Text InnerText; }
public class AngelaConversationUI { public static AngelaConversationUI instance; public UnityEngine.UI.Text messageText; }
public class OverlayManager { public static OverlayManager Instance; public UnityEngine.UI.Text OverlayText, _debugText; }
namespace GlobalBullet {
    public class GlobalBulletWindow { public static GlobalBulletWindow CurrentWindow; public UnityEngine.UI.Text CurrentUsableBulletCount, BulletCountMax; }
}
public class ConsolePanelsFixture {
    static int checks;
    static void Check(bool valid,string why) { if(!valid) throw new Exception(why); checks++; }
    static bool Has(IList<ConsolePanels.Entry> items,string name,string source) {
        return items.Any(x=>x.root.name==name && x.source==source);
    }
    public static void Main() {
        var panels=new ConsolePanels();
        Check(panels.Capture().Count==0,"empty scene");
        CommandWindow.CommandWindow.CurrentWindow=new CommandWindow.CommandWindow { RootControl=new UnityEngine.GameObject("command") };
        MissionUI.instance=new MissionUI { listParent=new UnityEngine.RectTransform() };
        MissionUI.instance.listParent.children.Add(new MissionSlot { txt=new UnityEngine.UI.Text("mission") });
        MissionPopupUI.instance=new MissionPopupUI { missionNameText=new UnityEngine.UI.Text("mission-name"), missionDescText=new UnityEngine.UI.Text("mission-description") };
        var logParent=new UnityEngine.RectTransform();
        logParent.children.Add(new LogItemScript { textTarget=new UnityEngine.UI.Text("log") });
        UnityEngine.Object.scene.Add(new SystemLogScript { script=new LoggingScript { parent=logParent } });
        UnityEngine.Object.scene.Add(new ConversationUI { InnerText=new UnityEngine.UI.Text("npc-one") });
        UnityEngine.Object.scene.Add(new ConversationUI { InnerText=new UnityEngine.UI.Text("npc-two") });
        AngelaConversationUI.instance=new AngelaConversationUI { messageText=new UnityEngine.UI.Text("tutorial") };
        OverlayManager.Instance=new OverlayManager { OverlayText=new UnityEngine.UI.Text("tooltip"), _debugText=new UnityEngine.UI.Text("debug-secret") };
        GlobalBullet.GlobalBulletWindow.CurrentWindow=new GlobalBullet.GlobalBulletWindow { CurrentUsableBulletCount=new UnityEngine.UI.Text("remaining"), BulletCountMax=new UnityEngine.UI.Text("maximum") };
        Check(panels.Capture().Count==0,"bounded discovery interval");
        UnityEngine.Time.realtimeSinceStartup=1.1f;
        var items=panels.Capture();
        Check(Has(items,"command","command"),"command display root");
        Check(Has(items,"mission","mission") && Has(items,"mission-description","mission"),"display mission roots");
        Check(Has(items,"log","notice"),"display log rows");
        Check(Has(items,"npc-one","notice") && Has(items,"npc-two","notice") && Has(items,"tutorial","notice"),"multiple final NPC text fields");
        Check(Has(items,"tooltip","tooltip") && !items.Any(x=>x.root.name=="debug-secret"),"debug excluded");
        Check(Has(items,"remaining","bullets") && Has(items,"maximum","bullets"),"bullet final text references");
        UnityEngine.Object.scene.Add(new SystemLogScript { script=new LoggingScript { parent=logParent } });
        UnityEngine.Time.realtimeSinceStartup=2.2f;
        Check(!Has(panels.Capture(),"log","notice"),"ambiguous log roots withheld");
        UnityEngine.Object.scene.Clear(); MissionUI.instance=null; MissionPopupUI.instance=null;
        CommandWindow.CommandWindow.CurrentWindow=null; AngelaConversationUI.instance=null;
        OverlayManager.Instance=null; GlobalBullet.GlobalBulletWindow.CurrentWindow=null;
        UnityEngine.Time.realtimeSinceStartup=3.3f;
        Check(panels.Capture().Count==0,"scene references removed");
        Console.WriteLine("PASS "+checks+" panel routing checks");
    }
}
