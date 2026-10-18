using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;
using Packet=MotionProbeSnapshot.Packet;
using Sample=MotionProbeSnapshot.Sample;
using Vector=MotionProbeSnapshot.Vector;

// Render-only inheritance fixtures: never register models, run gameplay callbacks,
// load a prefab, issue input or touch progression. Base lifecycle is unsafe with
// null models (notably CreatureUnit/ChildCreatureUnit.OnDestroy), so override it.
public sealed class MotionFixtureCreature : CreatureUnit {
    public override void Awake() {} public override void Start() {}
    public override void Update() {} public override void FixedUpdate() {}
    public override void LateUpdate() {} public override void OnDestroy() {}
}
public sealed class MotionFixtureChild : ChildCreatureUnit {
    public override void Awake() {} public override void Start() {}
    public override void Update() {} public override void FixedUpdate() {}
    public override void LateUpdate() {} public override void OnDestroy() {}
}
public sealed class MotionFixtureProjectile : ProjectileUnit {
    public override void FixedUpdate() {} public override void LateUpdate() {}
    public override void OnDestroy() {}
}
public sealed class MotionFixtureSkeleton : Spine.Unity.SkeletonRenderer {
    public override void Awake() {} public override void LateUpdate() {}
}

public sealed class MotionTargetsProbe : MonoBehaviour {
    sealed class Body { public GameObject root,visual; public MeshRenderer renderer; public string token; }
    string output;
    Camera cam;
    Vector3 cameraOrigin,cameraOffset;
    bool oldProbe,cleaned;
    GameObject fixture,cover;
    Mesh mesh;
    Material material;
    Texture2D texture;
    Body[] bodies;
    readonly ConsoleMotion motion=new ConsoleMotion();
    readonly List<string> results=new List<string>();
    string snapshot="{}";
    int decodedCount;
    float unitsPerPixel;

    public void Begin(string directory) {
        output=directory;oldProbe=ConsoleMotion.ProbeActive;ConsoleMotion.ProbeActive=true;
        StartCoroutine(GuardedRun());
    }
    IEnumerator GuardedRun() {
        IEnumerator run=Run();
        while(true) {
            bool next=false;Exception failure=null;
            try { next=run.MoveNext(); } catch(Exception error) { failure=error; }
            if(failure!=null) { Finish(failure.ToString());yield break; }
            if(!next) yield break;
            yield return run.Current;
        }
    }
    void PositionCamera(Camera camera) { if(camera==cam) camera.transform.position=cameraOrigin+cameraOffset; }
    void Assets() {
        texture=new Texture2D(8,8,TextureFormat.RGBA32,false);
        var colors=new Color32[64];for(int i=0;i<colors.Length;i++) colors[i]=new Color32(255,255,255,255);
        texture.SetPixels32(colors);texture.Apply();texture.filterMode=FilterMode.Point;
        material=new Material(Shader.Find("Spine/Skeleton"));material.mainTexture=texture;
        mesh=new Mesh();
        mesh.vertices=new Vector3[] {new Vector3(-.5f,-.5f),new Vector3(-.5f,.5f),new Vector3(.5f,.5f),new Vector3(.5f,-.5f)};
        mesh.uv=new Vector2[] {new Vector2(0,0),new Vector2(0,1),new Vector2(1,1),new Vector2(1,0)};
        mesh.colors32=new Color32[] {colors[0],colors[0],colors[0],colors[0]};
        mesh.triangles=new int[] {0,1,2,0,2,3};mesh.RecalculateBounds();
    }
    Body Create(int type,float x) {
        var result=new Body();
        result.root=new GameObject("MotionSyntheticController"+type);result.root.transform.SetParent(fixture.transform,false);
        result.root.transform.position=cam.ViewportToWorldPoint(new Vector3(x,.52f,10));
        result.visual=new GameObject("MotionSyntheticDisplay"+type,typeof(MeshFilter),typeof(MeshRenderer));
        result.visual.transform.SetParent(result.root.transform,false);
        result.visual.transform.localScale=Vector3.one*(40*unitsPerPixel);
        result.visual.AddComponent<MotionFixtureSkeleton>().enabled=false;
        result.visual.GetComponent<MeshFilter>().sharedMesh=mesh;
        result.renderer=result.visual.GetComponent<MeshRenderer>();result.renderer.sharedMaterial=material;
        result.renderer.sortingOrder=32760;result.renderer.shadowCastingMode=UnityEngine.Rendering.ShadowCastingMode.Off;
        result.renderer.receiveShadows=false;
        if(type<2) {
            CreatureUnit unit=type==0?(CreatureUnit)result.root.AddComponent<MotionFixtureCreature>():result.root.AddComponent<MotionFixtureChild>();
            unit.enabled=false;unit.animTarget=result.visual.AddComponent<CreatureAnimScript>();unit.animTarget.enabled=false;
        } else {
            var unit=result.root.AddComponent<MotionFixtureProjectile>();unit.enabled=false;unit.animTarget=result.visual;
        }
        return result;
    }
    Packet Read() {
        var ui=new ConsoleUI();ui.Capture(new List<ViewRect>(),new List<ViewRect>(),new List<string>());
        motion.Capture(ui,true);snapshot=motion.Snapshot;
        Packet packet=MotionProbeSnapshot.Decode(snapshot);decodedCount=packet.tracks.Length;return packet;
    }
    Sample Find(Packet packet,Body body) {
        Vector3 p=cam.WorldToScreenPoint(body.visual.transform.position);
        if(packet.tracks==null) return null;
        foreach(var track in packet.tracks)
            if(track.position!=null && Mathf.Abs(track.position.x-p.x)<20 && Mathf.Abs(track.position.y-(Screen.height-p.y))<20) return track;
        return null;
    }
    static bool Zero(Vector value) { return value!=null && Mathf.Abs(value.x)<.05f && Mathf.Abs(value.y)<.05f; }
    static bool HasToken(Packet packet,string token) {
        if(packet.tracks!=null) foreach(var track in packet.tracks) if(track.track_id==token) return true;
        return false;
    }
    void Check(string name,bool passed) {
        string file="motion-targets-probe-"+name+".png";
        var image=new Texture2D(Screen.width,Screen.height,TextureFormat.RGB24,false);
        try {
            image.ReadPixels(new Rect(0,0,Screen.width,Screen.height),0,0,false);image.Apply(false);
            File.WriteAllBytes(Path.Combine(output,file),image.EncodeToPNG());
        } finally { Destroy(image); }
        var expected=new List<string>();
        foreach(var body in bodies) {
            Vector3 pixel=cam.WorldToScreenPoint(body.visual.transform.position);
            expected.Add("{\"x\":"+pixel.x.ToString("R",System.Globalization.CultureInfo.InvariantCulture)+
                ",\"y\":"+(Screen.height-pixel.y).ToString("R",System.Globalization.CultureInfo.InvariantCulture)+"}");
        }
        results.Add("{\"case\":"+RobotomyObserver.Quote(name)+",\"passed\":"+(passed?"true":"false")+
            ",\"decoded_count\":"+decodedCount+",\"expected_centers\":["+String.Join(",",expected.ToArray())+"]"+
            ",\"frame\":"+RobotomyObserver.Quote(file)+",\"snapshot\":"+snapshot+",\"diagnostics\":"+motion.Diagnostics()+"}");
    }
    IEnumerator Run() {
        cam=Camera.main;
        if(cam==null) { Finish("camera_missing");yield break; }
        cameraOrigin=cam.transform.position;unitsPerPixel=cam.orthographicSize*2/Screen.height;
        fixture=new GameObject("RobotomySyntheticMotionTargets");Assets();
        bodies=new Body[] {Create(0,.35f),Create(1,.50f),Create(2,.65f)};
        Camera.onPreCull+=PositionCamera;
        yield return new WaitForEndOfFrame();
        Packet packet=Read();
        string[] kinds={"creature","child_creature","projectile"};
        for(int i=0;i<3;i++) {
            Sample sample=Find(packet,bodies[i]);bodies[i].token=sample==null?"":sample.track_id;
            Check(kinds[i]+"_visible",sample!=null && sample.state=="acquiring");
        }
        // Three PNG saves above can exceed the 300ms track horizon. Warm the state
        // afresh, then sample on a short real-time interval without screenshots.
        yield return new WaitForEndOfFrame();Read();
        yield return new WaitForSecondsRealtime(.06f);yield return new WaitForEndOfFrame();
        packet=Read();bool stable=true;
        foreach(var body in bodies) {
            Sample sample=Find(packet,body);
            stable&=sample!=null && sample.state=="tracking" && Zero(sample.object_velocity) && Zero(sample.camera_velocity);
            if(sample!=null) body.token=sample.track_id;
        }
        Check("stationary",stable);
        Vector3 controller=bodies[2].root.transform.position;
        bodies[2].visual.transform.position+=cam.transform.right*(8*unitsPerPixel);
        yield return new WaitForSecondsRealtime(.04f);yield return new WaitForEndOfFrame();
        packet=Read();Sample moving=Find(packet,bodies[2]);
        Check("display_child_moves",moving!=null && moving.track_id==bodies[2].token && moving.object_velocity!=null &&
            moving.object_velocity.x>1 && Zero(moving.camera_velocity) && bodies[2].root.transform.position==controller);
        cameraOffset=cam.transform.right*(8*unitsPerPixel);
        yield return new WaitForSecondsRealtime(.04f);yield return new WaitForEndOfFrame();
        packet=Read();bool cameraOnly=true;
        foreach(var body in bodies) {
            Sample sample=Find(packet,body);
            cameraOnly&=sample!=null && Zero(sample.object_velocity) && sample.camera_velocity!=null && sample.camera_velocity.x<-1;
        }
        Check("camera_moves_objects_stationary",cameraOnly);
        cameraOffset=cam.transform.right*(16*unitsPerPixel);
        bodies[2].visual.transform.position+=cam.transform.right*(8*unitsPerPixel);
        yield return new WaitForSecondsRealtime(.04f);yield return new WaitForEndOfFrame();
        packet=Read();moving=Find(packet,bodies[2]);
        Check("camera_and_object_separated",moving!=null && moving.object_velocity!=null && moving.camera_velocity!=null &&
            moving.object_velocity.x>1 && moving.camera_velocity.x<-1 && Zero(moving.screen_velocity));
        bodies[1].renderer.enabled=false;
        yield return new WaitForEndOfFrame();packet=Read();
        Check("hidden_child_withdrawn",!HasToken(packet,bodies[1].token) && Find(packet,bodies[1])==null);
        bodies[1].renderer.enabled=true;
        yield return new WaitForEndOfFrame();packet=Read();Sample returned=Find(packet,bodies[1]);
        Check("hidden_child_reacquired",returned!=null && returned.track_id!=bodies[1].token && returned.state=="acquiring" && returned.object_velocity==null);
        Vector3 creaturePosition=bodies[0].visual.transform.position;
        bodies[0].visual.transform.position=cam.ViewportToWorldPoint(new Vector3(2,.52f,10));
        yield return new WaitForEndOfFrame();packet=Read();
        Check("offscreen_creature_withdrawn",!HasToken(packet,bodies[0].token) && Find(packet,bodies[0])==null);
        bodies[0].visual.transform.position=creaturePosition;
        yield return new WaitForEndOfFrame();packet=Read();returned=Find(packet,bodies[0]);
        Check("offscreen_creature_reacquired",returned!=null && returned.track_id!=bodies[0].token && returned.state=="acquiring" && returned.object_velocity==null);
        cover=new GameObject("MotionTargetsOpaqueCover",typeof(RectTransform),typeof(Canvas));
        var canvas=cover.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=32767;
        var panel=new GameObject("Opaque",typeof(RectTransform),typeof(CanvasRenderer),typeof(Image));panel.transform.SetParent(cover.transform,false);
        var rect=panel.GetComponent<RectTransform>();rect.anchorMin=Vector2.zero;rect.anchorMax=Vector2.one;rect.offsetMin=rect.offsetMax=Vector2.zero;
        panel.GetComponent<Image>().color=Color.black;
        yield return new WaitForEndOfFrame();packet=Read();
        Check("opaque_ui_withdraws_all_types",Find(packet,bodies[0])==null && Find(packet,bodies[1])==null && Find(packet,bodies[2])==null);
        cover.SetActive(false);
        yield return new WaitForEndOfFrame();packet=Read();bool restored=true;
        foreach(var body in bodies) { returned=Find(packet,body);restored&=returned!=null && returned.state=="acquiring" && returned.object_velocity==null; }
        Check("cover_removed_reacquires",restored);
        Finish("");
    }
    void Finish(string error) {
        try {
            File.WriteAllText(Path.Combine(output,"motion-targets-probe.json"),"{\"basis\":\"synthetic_display_components_in_actual_unity\",\"error\":"+
                RobotomyObserver.Quote(error)+",\"cases\":["+String.Join(",",results.ToArray())+"]}");
        } finally { Cleanup();StartCoroutine(FinishAfterCleanFrame()); }
    }
    IEnumerator FinishAfterCleanFrame() {
        // The last backbuffer still contains the fixture after deactivation. Keep
        // public history suppressed until a clean frame has actually rendered.
        yield return new WaitForEndOfFrame();
        ConsoleMotion.ProbeActive=oldProbe;Destroy(this);
    }
    void Cleanup() {
        if(cleaned) return;cleaned=true;
        Camera.onPreCull-=PositionCamera;
        if(cam!=null) cam.transform.position=cameraOrigin;
        if(fixture!=null) { fixture.SetActive(false);Destroy(fixture); }
        if(cover!=null) { cover.SetActive(false);Destroy(cover); }
        if(mesh!=null) Destroy(mesh);if(material!=null) Destroy(material);if(texture!=null) Destroy(texture);
    }
    void OnDestroy() { Cleanup();ConsoleMotion.ProbeActive=oldProbe; }
}
