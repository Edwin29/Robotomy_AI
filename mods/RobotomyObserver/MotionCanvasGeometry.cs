using System;
using System.Collections.Generic;
using System.Reflection;
using Harmony;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

// Observes the final stock uGUI mesh after all IMeshModifier calls and SetMesh.
// Shipped UnityEngine.UI.dll SHA256 d6925513e19634dd3872abe83367690b87d64bee00cf2ef3e197dced056f7312.
// Graphic.DoMeshGeneration/DoLegacyMeshGeneration: retained decompile lines 399-437.
// Does not request rebuilds, replace meshes, or inspect game models.
public static class MotionCanvasGeometry
{
    sealed class Entry {
        public Graphic graphic; public Bounds local; public Scene scene; public bool empty;
        public Vector3[] vertices; public int[] triangles; public Vector2[] projected;
        public int bytes,projectedFrame=-1,projectedCamera;
        public Matrix4x4 transform,view,projection; public Rect viewport;
        public bool projectionValid;
    }
    static readonly Dictionary<int,Entry> cache=new Dictionary<int,Entry>();
    static readonly List<int> remove=new List<int>();
    static FieldInfo sharedMesh;
    static bool attempted,ready;
    static int lastPrune=-1000;
    public static int Captured,Failures;
    public static string LastReason="not_installed";
    public static int Count { get { return cache.Count; } }
    public static int CachedBytes { get; private set; }
    const int MaxEntries=4096,MaxVertices=131072,MaxIndices=393216,MaxBytes=16*1024*1024;

    static bool Stock(Graphic graphic) {
        if(graphic==null) return false;
        Type type=graphic.GetType();
        // Game SkeletonGraphic overrides Rebuild and writes CanvasRenderer directly.
        // Unknown/custom Graphics must not reuse the shared stock worker mesh.
        return type==typeof(Image) || type==typeof(RawImage) || type==typeof(Text);
    }
    public static void Install() {
        if(attempted) return;attempted=true;
        try {
            const BindingFlags flags=BindingFlags.Instance|BindingFlags.NonPublic|BindingFlags.Public;
            sharedMesh=typeof(Graphic).GetField("s_Mesh",BindingFlags.Static|BindingFlags.NonPublic);
            MethodInfo modern=typeof(Graphic).GetMethod("DoMeshGeneration",flags),legacy=typeof(Graphic).GetMethod("DoLegacyMeshGeneration",flags);
            MethodInfo dirty=typeof(Graphic).GetMethod("SetVerticesDirty",flags),disable=typeof(Graphic).GetMethod("OnDisable",flags);
            if(sharedMesh==null || modern==null || legacy==null || dirty==null || disable==null) { LastReason="ui_geometry_contract_missing";return; }
            var harmony=HarmonyInstance.Create("Robotomy.MotionCanvasGeometry.v1");
            var capture=new HarmonyMethod(typeof(MotionCanvasGeometry).GetMethod("Capture"));
            var invalidate=new HarmonyMethod(typeof(MotionCanvasGeometry).GetMethod("Invalidate"));
            harmony.Patch(modern,null,capture,null);harmony.Patch(legacy,null,capture,null);
            harmony.Patch(dirty,invalidate,null,null);harmony.Patch(disable,invalidate,null,null);
            SceneManager.sceneUnloaded+=SceneUnloaded;
            ready=true;LastReason="ready";
        } catch(Exception ex) { Failures++;LastReason="ui_geometry_install:"+ex.GetType().Name; }
    }
    public static void Invalidate(Graphic __instance) {
        if(__instance!=null) Remove(__instance.GetInstanceID());
    }
    static void Remove(int id) {
        Entry entry;if(cache.TryGetValue(id,out entry)) { CachedBytes-=entry.bytes;cache.Remove(id); }
    }
    public static void Capture(Graphic __instance) {
        if(!ready || !Stock(__instance)) return;
        int id=__instance.GetInstanceID();Remove(id);
        try {
            Mesh mesh=sharedMesh.GetValue(null) as Mesh;
            if(mesh==null || mesh.vertexCount>MaxVertices) { Failures++;return; }
            if(cache.Count>=MaxEntries) Prune(true);
            if(cache.Count>=MaxEntries) { Failures++;return; }
            var entry=new Entry {graphic=__instance,scene=__instance.gameObject.scene,empty=mesh.vertexCount==0};
            if(!entry.empty) {
                Vector3[] vertices=mesh.vertices;Vector3 min=vertices[0],max=vertices[0];
                foreach(Vector3 v in vertices) {
                    if(!Finite(v)) { Failures++;return; }
                    min=Vector3.Min(min,v);max=Vector3.Max(max,v);
                }
                entry.local=new Bounds((min+max)*.5f,max-min);
                // Query index counts before allocating indices. Unsupported topology
                // or exhausted budgets retain bounds but cannot prove a triangle miss.
                long indexCount=0;bool topology=true;
                for(int i=0;i<mesh.subMeshCount;i++) {
                    indexCount+=mesh.GetIndexCount(i);
                    if(mesh.GetTopology(i)!=MeshTopology.Triangles) topology=false;
                }
                long bytes=(long)vertices.Length*20+indexCount*4; // local+screen vertices, indices
                if(topology && indexCount<=MaxIndices && indexCount%3==0 && CachedBytes+bytes<=MaxBytes) {
                    int[] triangles=mesh.triangles;bool valid=triangles.Length==indexCount;
                    foreach(int index in triangles) if(index<0 || index>=vertices.Length) { valid=false;break; }
                    if(valid) {
                        entry.vertices=vertices;entry.triangles=triangles;entry.projected=new Vector2[vertices.Length];entry.bytes=(int)bytes;
                    } else Failures++;
                } else Failures++;
            }
            cache[id]=entry;CachedBytes+=entry.bytes;Captured++;
        } catch { Failures++; }
    }
    static bool Finite(Vector3 v) {
        return !Single.IsNaN(v.x)&&!Single.IsInfinity(v.x)&&!Single.IsNaN(v.y)&&!Single.IsInfinity(v.y)&&!Single.IsNaN(v.z)&&!Single.IsInfinity(v.z);
    }
    static void SceneUnloaded(Scene scene) {
        remove.Clear();foreach(var pair in cache) if(pair.Value.scene==scene) remove.Add(pair.Key);
        foreach(int id in remove) Remove(id);remove.Clear();
    }
    static void Prune(bool force) {
        if(!force && Time.frameCount-lastPrune<120) return;lastPrune=Time.frameCount;
        remove.Clear();foreach(var pair in cache) if(pair.Value.graphic==null || !pair.Value.graphic.isActiveAndEnabled) remove.Add(pair.Key);
        foreach(int id in remove) Remove(id);remove.Clear();
    }
    static Entry Find(CanvasRenderer renderer) {
        Graphic graphic=renderer==null?null:renderer.GetComponent<Graphic>();Entry entry;
        if(!ready || !Stock(graphic) || !graphic.isActiveAndEnabled ||
            !cache.TryGetValue(graphic.GetInstanceID(),out entry) || entry.graphic!=graphic || entry.scene!=graphic.gameObject.scene) return null;
        return entry;
    }
    public static int TriangleCount(CanvasRenderer renderer) {
        Entry entry=Find(renderer);return entry==null?-1:entry.empty?0:entry.triangles==null?-1:entry.triangles.Length/3;
    }
    static bool Project(Entry entry,Camera camera) {
        Matrix4x4 transform=entry.graphic.transform.localToWorldMatrix,view=camera.worldToCameraMatrix,projection=camera.projectionMatrix;
        if(entry.projectedFrame==Time.frameCount && entry.projectedCamera==camera.GetInstanceID() && entry.transform==transform &&
            entry.view==view && entry.projection==projection && entry.viewport==camera.pixelRect) return entry.projectionValid;
        entry.projectedFrame=Time.frameCount;entry.projectedCamera=camera.GetInstanceID();entry.transform=transform;
        entry.view=view;entry.projection=projection;entry.viewport=camera.pixelRect;entry.projectionValid=false;
        for(int i=0;i<entry.vertices.Length;i++) {
            Vector3 p=camera.WorldToScreenPoint(transform.MultiplyPoint3x4(entry.vertices[i]));
            if(!Finite(p)) return false;
            entry.projected[i]=new Vector2(p.x,p.y);
        }
        entry.projectionValid=true;return true;
    }
    static bool Separated(Vector2 axis,Vector2 a,Vector2 b,Vector2 c,Rect rect) {
        // Double intermediates retain accuracy for the game's million-pixel UI frames.
        double pa=(double)axis.x*a.x+(double)axis.y*a.y,pb=(double)axis.x*b.x+(double)axis.y*b.y,pc=(double)axis.x*c.x+(double)axis.y*c.y;
        double center=(double)axis.x*rect.center.x+(double)axis.y*rect.center.y;
        double extent=Math.Abs((double)axis.x)*rect.width*.5+Math.Abs((double)axis.y)*rect.height*.5;
        return Math.Max(pa,Math.Max(pb,pc))<center-extent || Math.Min(pa,Math.Min(pb,pc))>center+extent;
    }
    public static bool CanTouch(CanvasRenderer renderer,Camera camera,Rect patch) {
        Entry entry=Find(renderer);
        if(entry==null || camera==null || !camera.orthographic) { LastReason="ui_triangles_unknown";return true; }
        if(entry.empty) { LastReason="ui_triangles_empty";return false; }
        if(entry.triangles==null || entry.vertices==null || !Project(entry,camera)) { LastReason="ui_triangles_unavailable";return true; }
        Rect expanded=Rect.MinMaxRect(patch.xMin-.5f,patch.yMin-.5f,patch.xMax+.5f,patch.yMax+.5f);
        for(int i=0;i<entry.triangles.Length;i+=3) {
            Vector2 a=entry.projected[entry.triangles[i]],b=entry.projected[entry.triangles[i+1]],c=entry.projected[entry.triangles[i+2]];
            if(Separated(Vector2.right,a,b,c,expanded)||Separated(Vector2.up,a,b,c,expanded)) continue;
            Vector2 ab=b-a,bc=c-b,ca=a-c;
            if(Separated(new Vector2(-ab.y,ab.x),a,b,c,expanded)||Separated(new Vector2(-bc.y,bc.x),a,b,c,expanded)||
                Separated(new Vector2(-ca.y,ca.x),a,b,c,expanded)) continue;
            LastReason="ui_triangles_overlap";return true;
        }
        LastReason="ui_triangles_miss";return false;
    }
    public static bool TryBounds(CanvasRenderer renderer,Camera camera,out Rect rect,out float near,out float far) {
        rect=new Rect();near=Single.MaxValue;far=Single.MinValue;Prune(false);
        if(!ready) { LastReason="ui_geometry_not_ready";return false; }
        Graphic graphic=renderer==null?null:renderer.GetComponent<Graphic>();
        if(!Stock(graphic)) { LastReason="ui_geometry_custom_path";return false; }
        Entry entry;
        if(!graphic.isActiveAndEnabled || !cache.TryGetValue(graphic.GetInstanceID(),out entry) || entry.graphic!=graphic || entry.scene!=graphic.gameObject.scene) {
            LastReason="ui_geometry_uncaptured_or_dirty";return false;
        }
        if(entry.empty) { LastReason="ui_geometry_empty";return true; }
        Vector3 lo=entry.local.min,hi=entry.local.max;
        Vector2 min=new Vector2(Single.MaxValue,Single.MaxValue),max=new Vector2(Single.MinValue,Single.MinValue);
        for(int i=0;i<8;i++) {
            Vector3 p=camera.WorldToScreenPoint(graphic.transform.TransformPoint(new Vector3((i&1)==0?lo.x:hi.x,(i&2)==0?lo.y:hi.y,(i&4)==0?lo.z:hi.z)));
            if(!Finite(p)) { LastReason="ui_geometry_projection";return false; }
            min=Vector2.Min(min,new Vector2(p.x,p.y));max=Vector2.Max(max,new Vector2(p.x,p.y));
            near=Mathf.Min(near,p.z);far=Mathf.Max(far,p.z);
        }
        rect=Rect.MinMaxRect(min.x-2,min.y-2,max.x+2,max.y+2);
        LastReason="ui_geometry_captured";return true;
    }
}
