using System;
using System.IO;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using System.Globalization;
using UnityEngine;
using UnityEngine.SceneManagement;
using Harmony;

// Game-local input. Targeted employee clicks reuse the normal pointer-click handler; no goal/state writes.
[DefaultExecutionOrder(-32000)]
public class RobotomyVirtualInput : MonoBehaviour
{
    static string directory;
    static int patched;
    static int cursorCalls;
    static Vector3 pointer = new Vector3(640, 360, 0);
    public static Rect PointerOverlayRect { get { return new Rect(pointer.x-8,pointer.y-8,98,30); } }
    static Vector2 wheel;
    static KeyCode heldKey = KeyCode.None, downKey = KeyCode.None, upKey = KeyCode.None;
    static bool pauseOnlyKey;
    static int heldButton = -1, downButton = -1, upButton = -1;
    string[] active;
    int phase;
    float started;
    static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
    static readonly Dictionary<short, OpCode> Opcodes = MakeOpcodes();
    static readonly Dictionary<string, MethodInfo> Replacements = MakeReplacements();
    static double Epoch { get { return (DateTime.UtcNow - new DateTime(1970,1,1)).TotalSeconds; } }

    static Dictionary<short, OpCode> MakeOpcodes() {
        var d = new Dictionary<short, OpCode>();
        foreach (FieldInfo f in typeof(OpCodes).GetFields()) if (f.FieldType == typeof(OpCode)) {
            OpCode op = (OpCode)f.GetValue(null); d[op.Value] = op;
        }
        return d;
    }
    static string Signature(MethodInfo m) {
        string s = m.Name;
        foreach (ParameterInfo p in m.GetParameters()) s += ":" + p.ParameterType.FullName;
        return s;
    }
    static Dictionary<string, MethodInfo> MakeReplacements() {
        var d = new Dictionary<string, MethodInfo>();
        foreach (MethodInfo m in typeof(VirtualState).GetMethods(BindingFlags.Public | BindingFlags.Static)) d[Signature(m)] = m;
        return d;
    }
    static bool HasInput(MethodBase method) {
        MethodBody body = method.GetMethodBody(); if (body == null) return false;
        byte[] il = body.GetILAsByteArray();
        for (int i=0; i<il.Length;) {
            short b = il[i++]; if (b == 254) b = (short)(0xfe00 | il[i++]);
            OpCode op = Opcodes[b];
            if (op == OpCodes.Call || op == OpCodes.Callvirt) {
                MethodBase target = method.Module.ResolveMethod(BitConverter.ToInt32(il,i));
                if (target.DeclaringType == typeof(Cursor)) return true;
                if (target.DeclaringType == typeof(Input)) {
                    MethodInfo info = target as MethodInfo;
                    if (info == null || !Replacements.ContainsKey(Signature(info)))
                        throw new InvalidOperationException("Unsupported input: " + target);
                    return true;
                }
            }
            switch (op.OperandType) {
                case OperandType.InlineNone: break;
                case OperandType.ShortInlineBrTarget: case OperandType.ShortInlineI: case OperandType.ShortInlineVar: i+=1; break;
                case OperandType.InlineVar: i+=2; break;
                case OperandType.InlineI8: case OperandType.InlineR: i+=8; break;
                case OperandType.InlineSwitch: i+=4+4*BitConverter.ToInt32(il,i); break;
                default: i+=4; break;
            }
        }
        return false;
    }
    public static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> instructions) {
        foreach (CodeInstruction code in instructions) {
            MethodInfo m = code.operand as MethodInfo;
            if (m != null && m.DeclaringType == typeof(Cursor)) {
                Type[] parameters = Array.ConvertAll(m.GetParameters(), p => p.ParameterType);
                MethodInfo replacement = typeof(VirtualCursor).GetMethod(m.Name, parameters);
                if (replacement == null) throw new InvalidOperationException("Unsupported cursor operation " + m);
                code.opcode = OpCodes.Call; code.operand = replacement; cursorCalls++;
            }
            if (m != null && m.DeclaringType == typeof(Input)) {
                MethodInfo replacement;
                if (!Replacements.TryGetValue(Signature(m),out replacement)) throw new InvalidOperationException("Unsupported input " + m);
                code.opcode = OpCodes.Call; code.operand = replacement;
            }
            yield return code;
        }
    }
    public static bool IgnoreFocus(ref bool __result) { __result = false; return false; }
    public static void Install(string output) {
        directory = Path.Combine(output,"control"); Directory.CreateDirectory(directory);
        Directory.CreateDirectory(Path.Combine(directory,"virtual-acks"));
        var harmony = HarmonyInstance.Create("Robotomy.VirtualInput.v1");
        var transpiler = new HarmonyMethod(typeof(RobotomyVirtualInput).GetMethod("Rewrite"));
        foreach (Assembly assembly in AppDomain.CurrentDomain.GetAssemblies()) {
            string name = assembly.GetName().Name;
            if (name != "Assembly-CSharp" && name != "UnityEngine.UI") continue;
            foreach (Type type in assembly.GetTypes()) {
                var methods = new List<MethodBase>();
                methods.AddRange(type.GetMethods(BindingFlags.Instance|BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.DeclaredOnly));
                methods.AddRange(type.GetConstructors(BindingFlags.Instance|BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic));
                foreach (MethodBase method in methods) {
                    if (method.ContainsGenericParameters || method.IsAbstract) continue;
                    if (HasInput(method)) { harmony.Patch(method,null,null,transpiler); patched++; }
                }
            }
        }
        MethodInfo focus = typeof(UnityEngine.EventSystems.StandaloneInputModule).GetMethod("ShouldIgnoreEventsOnNoFocus",BindingFlags.Instance|BindingFlags.NonPublic);
        if (focus == null || patched == 0) throw new InvalidOperationException("Virtual input patch coverage missing");
        harmony.Patch(focus,new HarmonyMethod(typeof(RobotomyVirtualInput).GetMethod("IgnoreFocus")),null,null);
        Cursor.lockState = CursorLockMode.None;
        Cursor.visible = true;
        Cursor.SetCursor(null, Vector2.zero, CursorMode.Auto);
        Debug.Log("Robotomy virtual input installed: " + patched + " managed methods");
    }
    static void Write(string path,string contents) {
        string tmp=path+".tmp"; File.WriteAllText(tmp,contents);
        if(File.Exists(path)) File.Replace(tmp,path,null); else File.Move(tmp,path);
    }
    static float Num(string s) { return Single.Parse(s,Inv); }
    static bool PredatesBarrier(string created) {
        string path=Path.Combine(directory,"not-before.json");
        if(!File.Exists(path)) return false;
        var match=System.Text.RegularExpressions.Regex.Match(File.ReadAllText(path),"\"epoch\"\\s*:\\s*([0-9.Ee+-]+)");
        return !match.Success || Double.Parse(created,Inv)<Double.Parse(match.Groups[1].Value,Inv);
    }
    void Release() { pauseOnlyKey=false; upKey=heldKey; upButton=heldButton; heldKey=KeyCode.None; heldButton=-1; }
    void Ack(string status,string reason) {
        if(active == null) return;
        Write(Path.Combine(directory,"virtual-acks/"+active[0]+".json"),
            "{\"id\":\""+active[0]+"\",\"status\":\""+status+"\",\"reason\":\""+reason+"\",\"released\":true,\"process_id\":"+
            System.Diagnostics.Process.GetCurrentProcess().Id+",\"at_epoch\":"+Epoch.ToString("R",Inv)+"}");
        active=null; phase=0;
    }
    bool Accept(string[] c) {
        if((c.Length!=16 && c.Length!=17) || c[0].Length!=32) return false;
        if(c.Length==16 && c[12]!="v1")return false;
        if(c.Length==17){
            if(c[12]!="v2" || c[6]!="click" || c[16].Length!=32)return false;
            foreach(char ch in c[16])if(!Uri.IsHexDigit(ch)||Char.IsUpper(ch))return false;
        }
        foreach(char ch in c[0]) if(!Uri.IsHexDigit(ch) || Char.IsUpper(ch)) return false;
        if(c[1]!=System.Diagnostics.Process.GetCurrentProcess().Id.ToString() || c[2]!=SceneManager.GetActiveScene().name ||
           c[3]!=Screen.width.ToString() || c[4]!=Screen.height.ToString()) return false;
        double expires=Double.Parse(c[5],Inv), created=Double.Parse(c[15],Inv);
        if(Double.IsNaN(expires)||Double.IsNaN(created)||expires<Epoch || expires>Epoch+30 || created>Epoch+5 || created<Epoch-30 || PredatesBarrier(c[15])) return false;
        float duration=Num(c[13]); if(Single.IsNaN(duration)||duration<20||duration>3000) return false;
        if(c[6]!="key") for(int i=8;i<=11;i++) {
            float v=Num(c[i]); if(Single.IsNaN(v)||v<0||v>=(i%2==0?Screen.width:Screen.height)) return false;
        }
        if(c[6]=="key" && !new List<string>{"space","pause_only","Escape","Return","1","2","3","w","a","s","d","f","g"}.Contains(c[7])) return false;
        if(!new List<string>{"key","click","right_click","drag","right_drag","move","scroll"}.Contains(c[6])) return false;
        float scroll=Num(c[14]); if(Single.IsNaN(scroll)||Math.Abs(scroll)>600) return false;
        return !File.Exists(Path.Combine(directory,"virtual-acks/"+c[0]+".json"));
    }
    static KeyCode Key(string s) {
        if(s=="space"||s=="pause_only") return KeyCode.Space;
        if(s.Length==1 && s[0]>='1' && s[0]<='3') return KeyCode.Alpha0+(s[0]-'0');
        return (KeyCode)Enum.Parse(typeof(KeyCode),s,true);
    }
    void Update() {
        downKey=upKey=KeyCode.None; downButton=upButton=-1; wheel=Vector2.zero;
        try {
            if(Input.GetKeyDown(KeyCode.F8)) File.WriteAllText(Path.Combine(directory,"PAUSED"),"Physical F8 emergency stop");
            if(File.Exists(Path.Combine(directory,"PAUSED"))) {
                Release(); Ack("unknown","Operator paused input");
                string pending=Path.Combine(directory,"virtual-command.txt");
                if(File.Exists(pending)) File.Delete(pending);
            }
            else if(active!=null) {
                if(phase<3 && (active[2]!=SceneManager.GetActiveScene().name || active[3]!=Screen.width.ToString() || active[4]!=Screen.height.ToString())) { Release(); Ack("unknown","Scene or resolution changed during gesture"); }
                else if(PredatesBarrier(active[15]) || Epoch>Double.Parse(active[5],Inv) || Time.realtimeSinceStartup-started>4) { Release(); Ack("unknown","Input deadline or control barrier exceeded"); }
                else if(phase==1) {
                    if(active.Length==17){
                        Vector2 target;
                        if(!ConsoleMotion.TryEmployeeClick(active[16],out target)){Ack("rejected","Unit no longer visible or unambiguously clickable");return;}
                        pointer=new Vector3(target.x,target.y,0);
                        var data=new UnityEngine.EventSystems.PointerEventData(UnityEngine.EventSystems.EventSystem.current);
                        data.position=target;data.button=UnityEngine.EventSystems.PointerEventData.InputButton.Left;
                        UnitMouseEventManager.instance.OnPointerClick(data);
                        Ack("input_sent","Current visible unit click dispatched");return;
                    }
                    started=Time.realtimeSinceStartup; phase=2;
                    string kind=active[6];
                    if(kind=="key") { pauseOnlyKey=active[7]=="pause_only"; downKey=heldKey=Key(active[7]); }
                    else if(kind=="click"||kind=="drag") downButton=heldButton=0;
                    else if(kind=="right_click"||kind=="right_drag") downButton=heldButton=1;
                    else if(kind=="scroll") wheel=new Vector2(0,-Num(active[14])/120f);
                }
                else if(phase==2) {
                    float ratio=Mathf.Clamp01((Time.realtimeSinceStartup-started)/(Num(active[13])/1000f));
                    if(active[6]=="drag"||active[6]=="right_drag") pointer=new Vector3(Mathf.Lerp(Num(active[8]),Num(active[10]),ratio),Screen.height-Mathf.Lerp(Num(active[9]),Num(active[11]),ratio),0);
                    if(ratio>=1) { Release(); phase=3; }
                }
                else { Ack("input_sent","Virtual gesture completed"); }
            }
            else {
                string path=Path.Combine(directory,"virtual-command.txt");
                if(File.Exists(path)) {
                    string[] c=File.ReadAllText(path).Split('\n'); File.Delete(path);
                    if(Accept(c)) { active=c; phase=1; started=Time.realtimeSinceStartup;
                        if(c[6]!="key") pointer=new Vector3(Num(c[8]),Screen.height-Num(c[9]),0);
                    } else Debug.LogWarning("Robotomy rejected virtual command");
                }
            }
            if(Time.frameCount%30==0) Write(Path.Combine(directory,"virtual-status.json"),
                "{\"backend\":\"virtual_unity\",\"process_id\":"+System.Diagnostics.Process.GetCurrentProcess().Id+
                ",\"patched_methods\":"+patched+",\"at_epoch\":"+Epoch.ToString("R",Inv)+
                ",\"cursor_calls_replaced\":"+cursorCalls+",\"physical_cursor_lock\":\""+Cursor.lockState+"\""+
                ",\"pointer\":["+pointer.x.ToString("R",Inv)+","+(Screen.height-pointer.y).ToString("R",Inv)+"],\"held_key\":\""+heldKey+"\",\"held_button\":"+heldButton+"}");
        } catch(Exception ex) { Release(); Ack("unknown","Virtual executor error"); Debug.LogError("Robotomy virtual input: "+ex); }
    }
    void OnGUI() {
        GUI.depth=-10000; Color old=GUI.color; GUI.color=Color.cyan;
        float x=pointer.x,y=Screen.height-pointer.y;
        GUI.DrawTexture(new Rect(x-8,y-1,17,3),Texture2D.whiteTexture);
        GUI.DrawTexture(new Rect(x-1,y-8,3,17),Texture2D.whiteTexture);
        GUI.Label(new Rect(x+10,y-22,80,25),"AI"); GUI.color=old;
    }
    void OnDestroy() { Release(); Ack("unknown","Virtual executor stopped"); }
    public static class VirtualState {
        public static Vector3 get_mousePosition(){return pointer;}
        public static Vector2 get_mouseScrollDelta(){return wheel;}
        public static bool GetMouseButton(int b){return heldButton==b;}
        public static bool GetMouseButtonDown(int b){return downButton==b;}
        public static bool GetMouseButtonUp(int b){return upButton==b;}
        static bool AllowedKey(KeyCode k){return !pauseOnlyKey||k!=KeyCode.Space||(GameManager.currentGameManager!=null&&GameManager.currentGameManager.state==GameState.PLAYING);}
        public static bool GetKey(KeyCode k){return k!=KeyCode.None&&heldKey==k&&AllowedKey(k);}
        public static bool GetKeyDown(KeyCode k){return k!=KeyCode.None&&downKey==k&&AllowedKey(k);}
        public static bool GetKeyUp(KeyCode k){return k!=KeyCode.None&&upKey==k;}
        public static bool get_anyKey(){return heldKey!=KeyCode.None||heldButton>=0;}
        public static bool get_anyKeyDown(){return downKey!=KeyCode.None||downButton>=0;}
        public static bool get_mousePresent(){return true;}
        public static bool get_touchSupported(){return false;}
        public static int get_touchCount(){return 0;}
        public static Touch GetTouch(int index){return default(Touch);}
        public static string get_compositionString(){return "";}
        public static IMECompositionMode get_imeCompositionMode(){return IMECompositionMode.Off;}
        public static void set_imeCompositionMode(IMECompositionMode mode){}
        public static Vector2 get_compositionCursorPos(){return Vector2.zero;}
        public static void set_compositionCursorPos(Vector2 value){}
        public static float GetAxis(string name){return name=="Mouse ScrollWheel"?wheel.y*.1f:GetAxisRaw(name);}
        public static float GetAxisRaw(string name){return name=="Horizontal"?(heldKey==KeyCode.D?1:heldKey==KeyCode.A?-1:0):name=="Vertical"?(heldKey==KeyCode.W?1:heldKey==KeyCode.S?-1:0):0;}
        public static bool GetButtonDown(string name){return name=="Submit"?(GetKeyDown(KeyCode.Return)||GetKeyDown(KeyCode.Space)):name=="Cancel"&&downKey==KeyCode.Escape;}
    }
}
