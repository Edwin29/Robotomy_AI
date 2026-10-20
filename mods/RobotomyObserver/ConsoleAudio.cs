using System;
using System.Collections.Generic;
using System.Reflection;
using System.Reflection.Emit;
using UnityEngine;
using Harmony;

// Observes actual managed playback calls, preserving arguments and original behavior.
// This is a playback-state approximation, not recognition of the final mixed waveform.
public static class ConsoleAudio
{
    static readonly Dictionary<short,OpCode> ops=new Dictionary<short,OpCode>();
    static readonly Dictionary<string,MethodInfo> replacements=new Dictionary<string,MethodInfo>();
    static readonly Dictionary<AudioClip,string> clips=new Dictionary<AudioClip,string>();
    sealed class Source { public AudioSource source; public string id; public bool paused, playing; }
    static readonly Dictionary<int,Source> sources=new Dictionary<int,Source>();
    static readonly List<string> recent=new List<string>(), pending=new List<string>();
    static long sequence;
    public static long EventSequence { get { return sequence; } }
    public static int Patched, Failures, Dropped;
    static float lastScan=-10;
    static string Signature(MethodInfo m,bool wrapper) {
        string key=m.Name; ParameterInfo[] args=m.GetParameters();
        for(int i=wrapper?1:0;i<args.Length;i++) key+=":"+args[i].ParameterType.FullName;
        return key;
    }
    public static IEnumerable<CodeInstruction> Rewrite(IEnumerable<CodeInstruction> code) {
        foreach(var c in code) {
            var m=c.operand as MethodInfo; MethodInfo replacement;
            if(m!=null && m.DeclaringType==typeof(AudioSource) && replacements.TryGetValue(Signature(m,false),out replacement)) {
                c.opcode=OpCodes.Call; c.operand=replacement;
            }
            yield return c;
        }
    }
    static bool HasCall(MethodBase m) {
        var body=m.GetMethodBody(); if(body==null) return false; byte[] il=body.GetILAsByteArray();
        for(int i=0;i<il.Length;) {
            short b=il[i++]; if(b==254) b=(short)(0xfe00|il[i++]); OpCode op=ops[b];
            if(op==OpCodes.Call || op==OpCodes.Callvirt) {
                var target=m.Module.ResolveMethod(BitConverter.ToInt32(il,i)) as MethodInfo;
                if(target!=null && target.DeclaringType==typeof(AudioSource) && replacements.ContainsKey(Signature(target,false))) return true;
            }
            switch(op.OperandType) {
                case OperandType.InlineNone:break;
                case OperandType.ShortInlineBrTarget:case OperandType.ShortInlineI:case OperandType.ShortInlineVar:i++;break;
                case OperandType.InlineVar:i+=2;break;
                case OperandType.InlineI8:case OperandType.InlineR:i+=8;break;
                case OperandType.InlineSwitch:i+=4+4*BitConverter.ToInt32(il,i);break;
                default:i+=4;break;
            }
        }
        return false;
    }
    public static void Install() {
        ConsoleSoundCatalog.Initialize(Application.dataPath);
        foreach(var f in typeof(OpCodes).GetFields()) if(f.FieldType==typeof(OpCode)) { var op=(OpCode)f.GetValue(null); ops[op.Value]=op; }
        foreach(var method in typeof(Calls).GetMethods(BindingFlags.Public|BindingFlags.Static)) replacements[Signature(method,true)]=method;
        var harmony=HarmonyInstance.Create("Robotomy.ConsoleAudio.v1");
        var transpiler=new HarmonyMethod(typeof(ConsoleAudio).GetMethod("Rewrite"));
        foreach(var assembly in AppDomain.CurrentDomain.GetAssemblies()) if(assembly.GetName().Name=="Assembly-CSharp")
            foreach(var type in assembly.GetTypes()) {
                var methods=new List<MethodBase>();
                methods.AddRange(type.GetMethods(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static|BindingFlags.DeclaredOnly));
                methods.AddRange(type.GetConstructors(BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Instance|BindingFlags.Static));
                foreach(var method in methods) {
                    if(method.IsAbstract || method.ContainsGenericParameters) continue;
                    try { if(HasCall(method)) { harmony.Patch(method,null,null,transpiler); Patched++; } }
                    catch(Exception ex) { Failures++; Debug.LogWarning("Robotomy audio patch unavailable: "+method.Name+" "+ex.GetType().Name); }
                }
            }
        Debug.Log("Robotomy audio installed: "+Patched+" methods, "+Failures+" failures");
    }
    static Source Track(AudioSource source) {
        int id=source.GetInstanceID(); Source record;
        if(!sources.TryGetValue(id,out record) || record.source!=source) {
            record=new Source{source=source,id=Guid.NewGuid().ToString("N")}; sources[id]=record;
        }
        return record;
    }
    static void Emit(Source source,string kind,AudioClip clip) {
        string token="";
        if(clip!=null && !clips.TryGetValue(clip,out token)) {
            if(clips.Count>=2048) { Dropped++; return; }
            token=Guid.NewGuid().ToString("N"); clips[clip]=token;
        }
        var match=ConsoleSoundCatalog.Match(clip);
        string semantic=match==null?"":",\"sound_id\":"+RobotomyObserver.Quote(match.id)+
            ",\"label\":"+RobotomyObserver.Quote(match.label)+",\"category\":"+RobotomyObserver.Quote(match.category);
        string value="{\"event_id\":"+(++sequence)+",\"at_utc\":"+RobotomyObserver.Quote(DateTime.UtcNow.ToString("o"))+
            ",\"kind\":"+RobotomyObserver.Quote(kind)+",\"source_token\":"+RobotomyObserver.Quote(source.id)+
            ",\"sound_token\":"+RobotomyObserver.Quote(token)+semantic+"}";
        recent.Add(value); pending.Add(value);
        if(recent.Count>128) recent.RemoveAt(0);
        if(pending.Count>512) { pending.RemoveAt(0); Dropped++; }
    }
    static bool Audible(AudioSource source) {
        return source!=null && source.isActiveAndEnabled && source.isPlaying && !source.mute && source.volume>.001f &&
            AudioListener.volume>.001f && (!AudioListener.pause || source.ignoreListenerPause);
    }
    static void Started(AudioSource source,AudioClip clip,float scale) {
        try {
            if(clip==null || !Audible(source) || scale<=.001f) return;
            var record=Track(source); record.playing=true; record.paused=false; Emit(record,"start",clip);
        } catch { Failures++; } // Observation must never change the game's playback behavior.
    }
    static void Changed(AudioSource source,string kind) {
        try {
            Source record; if(source==null || !sources.TryGetValue(source.GetInstanceID(),out record)) return;
            if(kind=="resume" && !Audible(source)) return;
            record.paused=kind=="pause"; record.playing=kind!="stop";
            Emit(record,kind,null);
        } catch { Failures++; }
    }
    public static void Reconcile() {
        var dead=new List<int>();
        foreach(var pair in sources) {
            var record=pair.Value;
            if(record.source==null) { if(record.playing) Emit(record,"source_destroyed",null); dead.Add(pair.Key); }
            else if(record.playing && !record.paused && !record.source.isPlaying) {
                Emit(record,"source_idle",null); record.playing=false;
            }
        }
        foreach(int id in dead) sources.Remove(id);
        // Initial/PlayOnAwake playback is a sampled ongoing observation, not a manufactured start event.
        if(Time.realtimeSinceStartup-lastScan>=1) {
            lastScan=Time.realtimeSinceStartup;
            foreach(var source in UnityEngine.Object.FindObjectsOfType<AudioSource>()) if(Audible(source) && source.clip!=null) {
                var record=Track(source);
                if(!record.playing && !record.paused) { record.playing=true; Emit(record,"ongoing_detected",source.clip); }
            }
        }
    }
    public static string Snapshot() { return "["+String.Join(",",recent.ToArray())+"]"; }
    public static string Drain() { string data=pending.Count==0?"":String.Join("\n",pending.ToArray())+"\n"; pending.Clear(); return data; }
    public static class Calls {
        public static void Play(AudioSource source) { source.Play(); Started(source,source.clip,1); }
        public static void Play(AudioSource source,UInt64 delay) { source.Play(delay); if(delay==0) Started(source,source.clip,1); }
        public static void PlayOneShot(AudioSource source,AudioClip clip) { source.PlayOneShot(clip); Started(source,clip,1); }
        public static void PlayOneShot(AudioSource source,AudioClip clip,float volume) { source.PlayOneShot(clip,volume); Started(source,clip,volume); }
        public static void Stop(AudioSource source) { source.Stop(); Changed(source,"stop"); }
        public static void Pause(AudioSource source) { source.Pause(); Changed(source,"pause"); }
        public static void UnPause(AudioSource source) { source.UnPause(); Changed(source,"resume"); }
    }
}
