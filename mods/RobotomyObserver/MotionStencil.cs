using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

// Shipped render-profile analysis, not a general Unity stencil emulator.
// Sources: .robotomy/analysis/custom-stencil-states.json,
// stencil-writer-vertex-hashes.json, custom-sprite-mask.dxbc.txt.
// Both retained game assemblies contain no _Stencil access; the only SetPropertyBlock
// calls copy Spine blocks. In this approved profile, native Sprite blocks do not
// override stencil state. Old Unity cannot distinguish absent vs explicit-zero MPB
// floats: arbitrary third-party injected stencil overrides are outside this profile.
public static class MotionStencil
{
    sealed class State {
        public int reference, read=255, write=255, compare=8, operation;
        public bool canvasWriter;
        public CanvasRenderer canvasRenderer;
        public Renderer renderer;
        public int queue, layer, order;
        public bool withinClip;
        public Rect bounds;
        public Vector2[] vertices;
        public ushort[] triangles;
    }
    static readonly List<State> writers=new List<State>();
    static readonly Dictionary<Renderer,List<State>> targets=new Dictionary<Renderer,List<State>>();
    static readonly MaterialPropertyBlock block=new MaterialPropertyBlock();
    static Camera preparedCamera;
    static int preparedFrame=-1;
    static string blocked="not_prepared";
    static string depthReason="not_prepared";
    public static string LastReason="not_prepared";
    public static int WriterCount { get { return writers.Count; } }
    public static string LastMaskSummary="";
    public static string LastDepthShaders="";
    static bool dumpPending;
    static float dumpCheck=-10;
    static string dumpDirectory;
    static readonly List<string> canvasDump=new List<string>();

    static bool Integer(float value,int maximum,out int result) {
        result=0;
        if(Single.IsNaN(value)||Single.IsInfinity(value)||value<0||value>maximum||value!=Mathf.Round(value)) return false;
        result=(int)value; return true;
    }
    static bool Read(Material material,string name,int maximum,out int value) {
        value=0; return material.HasProperty(name) && Integer(material.GetFloat(name),maximum,out value);
    }
    static bool ParticleShader(string name) {
        // resources.assets 4971..4976: every pass has immutable Stencil Keep,
        // Compare Always and ZWriteOff (particle-shaders.json audit).
        switch(name) {
        case "Particles/Additive": case "Particles/~Additive-Multiply":
        case "Particles/Additive (Soft)": case "Particles/Alpha Blended":
        case "Particles/Multiply": case "Particles/Alpha Blended Premultiply":return true;
        default:return false;
        }
    }
    static bool StateFor(Renderer renderer,Material material,out State state) {
        state=null;
        if(material==null || material.shader==null) return false;
        string name=material.shader.name;
        if(material.shader!=Shader.Find(name)) return false;
        if(ParticleShader(name)){state=new State();return true;}
        switch(name) {
        case "Sprites/Default": case "Spine/Skeleton": case "Custom/SpriteOverlayBlend":
        // Main resources.assets 4971/4979: all stencil operations Keep, ZWriteOff.
        case "Unlit/Transparent":
            state=new State(); return true; // Audited passes never write/test stencil.
        case "Custom/SpriteDefaultStencilTest": case "Custom/SpriteMulStencilTest":
            state=new State { compare=3,reference=0,read=1 }; return true;
        case "Custom/SpriteDoorStencilTest":
            state=new State { compare=3,reference=11 }; return true;
        case "Custom/SpriteDefaultStencilWriter":
            state=new State { compare=8,reference=1,operation=2 }; return true;
        case "Custom/SpriteDoorStencilWriter":
            state=new State { compare=8,reference=11,operation=2 }; return true;
        case "Custom/SpriteDefaultCustomMask":
            int reference,read,compare,operation;
            if(!Read(material,"_Stencil",255,out reference) || !Read(material,"_StencilReadMask",255,out read) ||
                !Read(material,"_StencilComp",8,out compare) || !Read(material,"_StencilOp",7,out operation)) return false;
            block.Clear(); renderer.GetPropertyBlock(block);
            // Nonzero overrides are detectable and outside the audited material-only path.
            foreach(string property in new string[] {"_Stencil","_StencilReadMask","_StencilComp","_StencilOp","_StencilWriteMask"})
                if(block.GetFloat(property)!=0) return false;
            state=new State { reference=reference,read=read,compare=compare,operation=operation }; return true;
        default: return false;
        }
    }
    static bool Project(Camera camera,Bounds bounds,out Rect rectangle) {
        rectangle=new Rect();
        Vector3 lo=bounds.min,hi=bounds.max;
        Vector2 min=new Vector2(Single.MaxValue,Single.MaxValue),max=new Vector2(Single.MinValue,Single.MinValue);
        float near=Single.MaxValue,far=Single.MinValue;
        for(int i=0;i<8;i++) {
            Vector3 p=camera.WorldToScreenPoint(new Vector3((i&1)==0?lo.x:hi.x,(i&2)==0?lo.y:hi.y,(i&4)==0?lo.z:hi.z));
            if(Single.IsNaN(p.x)||Single.IsInfinity(p.x)||Single.IsNaN(p.y)||Single.IsInfinity(p.y)) return false;
            min=Vector2.Min(min,new Vector2(p.x,p.y));max=Vector2.Max(max,new Vector2(p.x,p.y));
            near=Mathf.Min(near,p.z);far=Mathf.Max(far,p.z);
        }
        if(far<camera.nearClipPlane || near>camera.farClipPlane) { rectangle=new Rect(); return true; }
        // Contains PixelSnap displacement and conservative raster edge uncertainty.
        rectangle=Rect.MinMaxRect(min.x-1,min.y-1,max.x+1,max.y+1); return true;
    }
    static bool Geometry(SpriteRenderer sprite,Material material,Camera camera,State state) {
        // The shipped custom writer vertex programs do not consume _Flip.
        if(sprite.flipX || sprite.flipY || sprite.maskInteraction!=SpriteMaskInteraction.None) return false;
        Vector2[] vertices=sprite.sprite.vertices;
        ushort[] triangles=sprite.sprite.triangles;
        if(vertices.Length>65536 || triangles.Length>262144 || triangles.Length%3!=0) return false;
        state.vertices=new Vector2[vertices.Length];state.triangles=triangles;
        for(int i=0;i<vertices.Length;i++) {
            Vector2 v=vertices[i];if(sprite.flipX)v.x=-v.x;if(sprite.flipY)v.y=-v.y;
            Vector3 p=camera.WorldToScreenPoint(sprite.transform.TransformPoint(new Vector3(v.x,v.y,0)));
            if(p.z<=camera.nearClipPlane+.001f || p.z>=camera.farClipPlane-.001f) state.withinClip=false;
            if(Single.IsNaN(p.x)||Single.IsInfinity(p.x)||Single.IsNaN(p.y)||Single.IsInfinity(p.y)) return false;
            if(material.IsKeywordEnabled("PIXELSNAP_ON")) {
                p.x=(float)Math.Round(p.x-Screen.width*.5f,MidpointRounding.ToEven)+Screen.width*.5f;
                p.y=(float)Math.Round(p.y-Screen.height*.5f,MidpointRounding.ToEven)+Screen.height*.5f;
            }
            state.vertices[i]=new Vector2(p.x,p.y);
        }
        foreach(ushort index in triangles) if(index>=vertices.Length) return false;
        return true;
    }
    static bool Separated(Vector2 axis,Vector2 a,Vector2 b,Vector2 c,Rect rect) {
        float pa=Vector2.Dot(axis,a),pb=Vector2.Dot(axis,b),pc=Vector2.Dot(axis,c);
        float min=Mathf.Min(pa,Mathf.Min(pb,pc)),max=Mathf.Max(pa,Mathf.Max(pb,pc));
        float center=Vector2.Dot(axis,rect.center);
        float extent=Mathf.Abs(axis.x)*rect.width*.5f+Mathf.Abs(axis.y)*rect.height*.5f;
        return max<center-extent || min>center+extent;
    }
    static bool Touches(State writer,Rect patch) {
        if(!writer.bounds.Overlaps(patch)) return false;
        if(writer.canvasWriter) return MotionCanvasGeometry.CanTouch(writer.canvasRenderer,preparedCamera,patch);
        // Exact sprite mesh triangles remove large bounding-box holes. Alpha is NOT
        // consulted: these audited shaders write stencil even for transparent texels.
        Rect expanded=Rect.MinMaxRect(patch.xMin-.5f,patch.yMin-.5f,patch.xMax+.5f,patch.yMax+.5f);
        for(int i=0;i<writer.triangles.Length;i+=3) {
            Vector2 a=writer.vertices[writer.triangles[i]],b=writer.vertices[writer.triangles[i+1]],c=writer.vertices[writer.triangles[i+2]];
            if(Separated(Vector2.right,a,b,c,expanded)||Separated(Vector2.up,a,b,c,expanded)) continue;
            Vector2 ab=b-a,bc=c-b,ca=a-c;
            if(Separated(new Vector2(-ab.y,ab.x),a,b,c,expanded)||Separated(new Vector2(-bc.y,bc.x),a,b,c,expanded)||
                Separated(new Vector2(-ca.y,ca.x),a,b,c,expanded)) continue;
            return true;
        }
        return false;
    }
    static float Cross(Vector2 a,Vector2 b) { return a.x*b.y-a.y*b.x; }
    static bool Covers(State writer,Rect patch) {
        if(!writer.withinClip || writer.renderer.GetComponentInParent<LODGroup>()!=null) return false;
        if(writer.renderer.shadowCastingMode==UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly ||
            preparedCamera.layerCullDistances[writer.renderer.gameObject.layer]!=0) return false;
        // One actual nondegenerate triangle must contain the entire expanded patch.
        // This proves coverage without assuming a bounding rectangle fills mesh holes.
        Rect inner=Rect.MinMaxRect(patch.xMin-1,patch.yMin-1,patch.xMax+1,patch.yMax+1);
        Vector2[] corners={new Vector2(inner.xMin,inner.yMin),new Vector2(inner.xMax,inner.yMin),
            new Vector2(inner.xMax,inner.yMax),new Vector2(inner.xMin,inner.yMax)};
        for(int i=0;i<writer.triangles.Length;i+=3) {
            Vector2 a=writer.vertices[writer.triangles[i]],b=writer.vertices[writer.triangles[i+1]],c=writer.vertices[writer.triangles[i+2]];
            float area=Cross(b-a,c-a);if(Mathf.Abs(area)<.01f) continue;
            float sign=area>0?1:-1;bool covered=true;
            foreach(Vector2 p in corners) if(Cross(b-a,p-a)*sign<=.01f || Cross(c-b,p-b)*sign<=.01f || Cross(a-c,p-c)*sign<=.01f) { covered=false;break; }
            if(covered) return true;
        }
        return false;
    }
    static bool Before(State a,State b) {
        // Require a strict sorting-priority relation and a nonconflicting transparent
        // queue. Equal priorities deliberately do not use unverified batch distances.
        return a.queue>=2501 && b.queue>=2501 && a.queue<=b.queue &&
            (a.layer<b.layer || (a.layer==b.layer&&a.order<b.order));
    }
    static bool BeforeAll(State writer,List<State> tests) {
        foreach(State test in tests) if(!Before(writer,test)) return false;
        return tests.Count>0;
    }
    static bool CanvasUsesCamera(CanvasRenderer renderer,Camera camera) {
        if(renderer==null || !renderer.gameObject.activeInHierarchy || renderer.cull || renderer.absoluteDepth<0 ||
            (camera.cullingMask&(1<<renderer.gameObject.layer))==0) return false;
        Canvas canvas=renderer.GetComponentInParent<Canvas>();
        if(canvas==null || !canvas.isActiveAndEnabled) return false;
        Canvas root=canvas.rootCanvas;
        return root!=null && root.isActiveAndEnabled && root.renderMode!=RenderMode.ScreenSpaceOverlay &&
            (root.renderMode!=RenderMode.ScreenSpaceCamera || root.worldCamera==camera);
    }
    static Rect CanvasBounds(CanvasRenderer renderer,Camera camera) {
        Rect rect;float near,far;
        if(MotionCanvasGeometry.TryBounds(renderer,camera,out rect,out near,out far)) return rect;
        // A missing, dirty, or custom generation path is not a zero-size mesh.
        return new Rect(-2,-2,Screen.width+4,Screen.height+4);
    }
    static string Q(string value) { return RobotomyObserver.Quote(value); }
    static void DumpCanvasWriter(CanvasRenderer renderer,Material material,Camera camera,State state,bool pop) {
        if(!dumpPending || canvasDump.Count>=256) return;
        Graphic graphic=renderer.GetComponent<Graphic>();
        Canvas canvas=renderer.GetComponentInParent<Canvas>(),root=canvas==null?null:canvas.rootCanvas,sorting=canvas;
        while(sorting!=null && sorting!=root && !sorting.overrideSorting) {
            Transform parent=sorting.transform.parent;sorting=parent==null?root:parent.GetComponentInParent<Canvas>();
        }
        var modifiers=new List<string>();
        foreach(Component component in renderer.GetComponents<Component>()) if(component is IMeshModifier) {
            Behaviour behaviour=component as Behaviour;
            modifiers.Add(Q(component.GetType().FullName+":"+(behaviour==null||behaviour.isActiveAndEnabled)));
        }
        Rect bounds;float near,far;bool captured=MotionCanvasGeometry.TryBounds(renderer,camera,out bounds,out near,out far);
        string geometry=MotionCanvasGeometry.LastReason;
        canvasDump.Add("{\"name\":"+Q(renderer.name)+",\"graphic\":"+Q(graphic==null?"null":graphic.GetType().FullName)+
            ",\"pop\":"+(pop?"true":"false")+",\"modifiers\":["+String.Join(",",modifiers.ToArray())+"],\"bounds\":"+Q(state.bounds.ToString())+
            ",\"geometry\":"+Q(geometry)+",\"captured\":"+(captured?"true":"false")+",\"near_far\":"+Q(near+","+far)+
            ",\"triangles\":"+MotionCanvasGeometry.TriangleCount(renderer)+
            ",\"screen_center_touch\":"+(MotionCanvasGeometry.CanTouch(renderer,camera,new Rect(Screen.width*.5f-1,Screen.height*.5f-1,2,2))?"true":"false")+
            ",\"clip\":"+Q(camera.nearClipPlane+","+camera.farClipPlane)+",\"sorting_canvas\":"+Q(sorting==null?"null":sorting.name)+
            ",\"root\":"+Q(root==null?"null":root.name)+",\"mode\":"+Q(root==null?"null":root.renderMode.ToString())+
            ",\"sort\":"+Q(sorting==null?"null":sorting.sortingLayerID+","+sorting.sortingOrder)+
            ",\"shader\":"+Q(material.shader.name)+",\"queue\":"+material.renderQueue+
            ",\"reference\":"+state.reference+",\"read_mask\":"+state.read+",\"write_mask\":"+state.write+
            ",\"compare\":"+state.compare+",\"operation\":"+state.operation+"}");
    }
    static bool AddCanvasWriter(CanvasRenderer renderer,Material material,Camera camera,bool pop) {
        int reference,read,write,compare,operation;
        if(!Read(material,"_Stencil",255,out reference) || !Read(material,"_StencilReadMask",255,out read) ||
            !Read(material,"_StencilWriteMask",255,out write) || !Read(material,"_StencilComp",8,out compare) ||
            !Read(material,"_StencilOp",7,out operation)) return false;
        if(operation==0 || write==0) return true;
        // UI/Default has immutable Fail Keep / ZFail Keep / ZWriteOff. Its optional
        // alpha clipping can only suppress writes: retaining the old value in the
        // closure and permitting a write across this bound safely includes both.
        var state=new State { canvasWriter=true,canvasRenderer=renderer,reference=reference,read=read,write=write,
            compare=compare,operation=operation,bounds=CanvasBounds(renderer,camera) };
        writers.Add(state);DumpCanvasWriter(renderer,material,camera,state,pop);
        return true;
    }
    static void CheckDepth(Camera camera) {
        depthReason="";
        // All accepted world shader color passes have immutable ZWriteOff (see
        // stencil-depth-states.json); Spine's SHADOWCASTER pass is not this target.
        // An unknown skybox/Canvas shader might write depth, so it disables resets.
        if(camera.clearFlags==CameraClearFlags.Skybox && RenderSettings.skybox!=null) depthReason="skybox_depth_unknown";
        var shaders=new List<string>();
        foreach(CanvasRenderer renderer in UnityEngine.Object.FindObjectsOfType<CanvasRenderer>()) {
            if(!CanvasUsesCamera(renderer,camera)) continue;
            for(int i=0;i<renderer.materialCount+renderer.popMaterialCount;i++) {
                Material material=i<renderer.materialCount?renderer.GetMaterial(i):renderer.GetPopMaterial(i-renderer.materialCount);
                string name=material==null||material.shader==null?"null":material.shader.name;
                if(shaders.Count<32 && !shaders.Contains(name)) shaders.Add(name);
                bool known=material!=null && material.shader!=null && material.shader==Shader.Find(name);
                if(known && ParticleShader(name))continue;
                if(known) switch(name) {
                // These exact shipped shader main passes have both immutable
                // ZWriteOff and Stencil Keep. Canvas usage cannot change those
                // compiled states. Stencil tests may fail, which still writes nothing.
                case "Sprites/Default": case "Spine/Skeleton": case "Custom/SpriteOverlayBlend":
                case "Unlit/Transparent":
                case "Custom/SpriteDefaultStencilTest": case "Custom/SpriteMulStencilTest": case "Custom/SpriteDoorStencilTest":
                    continue;
                case "UI/Default":
                    if(AddCanvasWriter(renderer,material,camera,i>=renderer.materialCount)) continue;
                    break;
                }
                string reason="canvas_shader_untracked:"+renderer.name+":"+name;
                if(depthReason=="") depthReason=reason;
                // An unknown Canvas shader can write stencil as well as depth.
                // Disabling only reset barriers would incorrectly start at {0}.
                if(blocked=="") blocked="stencil_"+reason;
            }
        }
        shaders.Sort();LastDepthShaders=String.Join(",",shaders.ToArray());
        if(dumpPending) try {
            System.IO.File.WriteAllText(System.IO.Path.Combine(dumpDirectory,"motion-canvas-writers.json"),
                "{\"scene\":"+Q(SceneManager.GetActiveScene().name)+",\"frame\":"+Time.frameCount+
                ",\"geometry_cached\":"+MotionCanvasGeometry.Count+",\"geometry_captures\":"+MotionCanvasGeometry.Captured+
                ",\"geometry_bytes\":"+MotionCanvasGeometry.CachedBytes+
                ",\"geometry_failures\":"+MotionCanvasGeometry.Failures+",\"writers\":["+String.Join(",",canvasDump.ToArray())+"]}");
            System.IO.File.Delete(System.IO.Path.Combine(dumpDirectory,"motion-canvas-dump.request"));dumpPending=false;
        } catch { }
    }
    public static void Prepare(Camera camera,Renderer[] renderers) {
        writers.Clear(); targets.Clear();
        preparedCamera=camera;preparedFrame=Time.frameCount;blocked="";depthReason="not_checked";LastReason="";LastMaskSummary="";LastDepthShaders="";
        canvasDump.Clear();
        if(Time.realtimeSinceStartup-dumpCheck>1) {
            dumpCheck=Time.realtimeSinceStartup;dumpDirectory=Environment.GetEnvironmentVariable("ROBOTOMY_OBSERVATION_DIR");
            dumpPending=!String.IsNullOrEmpty(dumpDirectory) && System.IO.File.Exists(System.IO.Path.Combine(dumpDirectory,"motion-canvas-dump.request"));
        }
        // Validate the actual camera, materials and stencil writers below.
        // Main uses the same shipped shader assets as the tutorial; the scene
        // name is not evidence that a foreground background-mask is opaque.
        if(camera==null || !camera.isActiveAndEnabled || !camera.orthographic || camera.targetTexture!=null ||
            camera.pixelRect!=new Rect(0,0,Screen.width,Screen.height) || camera.actualRenderingPath!=RenderingPath.Forward) {
            blocked="stencil_camera_unverified";return;
        }
        if(camera.clearFlags!=CameraClearFlags.Color && camera.clearFlags!=CameraClearFlags.Skybox && camera.clearFlags!=CameraClearFlags.Depth) {
            blocked="stencil_initial_value_unknown";return;
        }
        if(camera.commandBufferCount!=0) { blocked="stencil_command_buffers";return; }
        try {
            // Native SortingGroup batches can override individual renderer sorting.
            foreach(UnityEngine.Rendering.SortingGroup group in UnityEngine.Object.FindObjectsOfType<UnityEngine.Rendering.SortingGroup>())
                if(group.isActiveAndEnabled) { blocked="stencil_sorting_group_unverified";return; }
            foreach(Renderer renderer in renderers) {
                if(renderer==null || !renderer.enabled || !renderer.gameObject.activeInHierarchy ||
                    (camera.cullingMask&(1<<renderer.gameObject.layer))==0) continue;
                // Spine separators keep enabled, empty mesh renderers for absent
                // attachment slots. They submit no triangles and cannot write stencil.
                var mesh=renderer.GetComponent<MeshFilter>();
                if(renderer is MeshRenderer && (mesh==null || mesh.sharedMesh==null || mesh.sharedMesh.vertexCount==0)) continue;
                var spriteBody=renderer as SpriteRenderer;
                if(spriteBody!=null && spriteBody.sprite==null)continue;
                var particles=renderer is ParticleSystemRenderer?renderer.GetComponent<ParticleSystem>():null;
                if(particles!=null && particles.particleCount==0)continue;
                var states=new List<State>();
                Material[] materials=renderer.sharedMaterials;
                for(int slot=0;slot<materials.Length;slot++) {
                    // Shipped Aura particle prefabs retain a null trail-material
                    // slot while TrailModule is disabled. That slot is not drawn.
                    if(particles!=null && slot==1 && !particles.trails.enabled)continue;
                    Material material=materials[slot];
                    State state;
                    if(!StateFor(renderer,material,out state)) {
                        // Unknown shader vertices may leave CPU bounds, so an unknown
                        // writer cannot safely be excluded just by a rectangle test.
                        blocked="stencil_unknown_shader:"+renderer.name+":"+(material==null||material.shader==null?"null":material.shader.name);return;
                    }
                    state.renderer=renderer;state.queue=material.renderQueue;
                    state.layer=SortingLayer.GetLayerValueFromID(renderer.sortingLayerID);state.order=renderer.sortingOrder;
                    states.Add(state);
                    if(state.operation==0) continue;
                    SpriteRenderer sprite=renderer as SpriteRenderer;
                    if(sprite==null || sprite.sprite==null || sprite.drawMode!=SpriteDrawMode.Simple) {
                        blocked="stencil_writer_geometry_unverified";return;
                    }
                    block.Clear(); renderer.GetPropertyBlock(block);
                    foreach(string matrix in new string[] {"unity_ObjectToWorld","unity_MatrixVP","glstate_matrix_mvp"})
                        if(block.GetMatrix(matrix)!=Matrix4x4.identity) { blocked="stencil_writer_matrix_override";return; }
                    if(block.GetVector("_ScreenParams")!=Vector4.zero) { blocked="stencil_writer_screen_override";return; }
                    // Audited writer binaries contain ONLY plain/PIXELSNAP vertex
                    // variants and identical no-discard fragment programs. Serialized
                    // flags such as ETC1_EXTERNAL_ALPHA or _EMISSION have no program
                    // or binding here; flags cannot add shader code. Geometry handles
                    // the sole compiled keyword PIXELSNAP_ON.
                    // Verified DXBC for all three writer profiles uses ordinary
                    // transform+projection (+PixelSnap), so renderer bounds suffice.
                    if(!Project(camera,renderer.bounds,out state.bounds)) { blocked="stencil_writer_bounds";return; }
                    state.withinClip=true;
                    if(!Geometry(sprite,material,camera,state)) { blocked="stencil_writer_mesh";return; }
                    // Alpha0 does NOT imply no stencil write; do not filter by color.
                    if(state.bounds.width>0&&state.bounds.height>0) writers.Add(state);
                }
                if(states.Count==0) { blocked="stencil_missing_material";return; }
                targets[renderer]=states;
            }
            CheckDepth(camera);
            int canvasWrites=0;
            foreach(State writer in writers) if(writer.canvasWriter) canvasWrites++;
            LastMaskSummary="modeled_canvas_writes="+canvasWrites;
        } catch { blocked="stencil_prepare_exception"; }
    }
    static bool Pass(State state,int value) {
        int reference=state.reference&state.read,current=value&state.read;
        switch(state.compare) {
        case 1:return false;
        case 2:return reference<current;
        case 3:return reference==current;
        case 4:return reference<=current;
        case 5:return reference>current;
        case 6:return reference!=current;
        case 7:return reference>=current;
        default:return true; // Always or disabled: permit conservatively.
        }
    }
    static int UnmaskedWrite(State state,int value) {
        switch(state.operation) {
        case 1:return 0;
        case 2:return state.reference;
        case 3:return Math.Min(255,value+1);
        case 4:return Math.Max(0,value-1);
        case 5:return value^255;
        case 6:return (value+1)&255;
        case 7:return (value-1)&255;
        default:return value;
        }
    }
    static int Write(State state,int value) {
        return (value&(255^state.write)) | (UnmaskedWrite(state,value)&state.write);
    }
    public static bool CanDraw(Renderer target,Rect patch) {
        LastReason=blocked;
        if(blocked!="" || preparedCamera==null || preparedFrame!=Time.frameCount) { if(LastReason=="")LastReason="stencil_stale";return true; }
        List<State> tests;
        if(!targets.TryGetValue(target,out tests)) { LastReason="stencil_target_unknown";return true; }
        State barrier=null;
        if(depthReason=="") foreach(State writer in writers) {
            if(writer.canvasWriter || writer.write!=255 || writer.compare!=8 || writer.operation!=2 || !BeforeAll(writer,tests) || !Covers(writer,patch)) continue;
            if(barrier==null || Before(barrier,writer)) barrier=writer;
        }
        bool[] reachable=new bool[256];reachable[barrier==null?0:barrier.reference]=true;
        bool changed=true;int rounds=0,count=1;
        // Ignore ordering, alpha discard, depth failures and exact triangle edges.
        // This overapproximates every value any writer could produce at the patch.
        // Crucially Equal4/Replace4 cannot conjure4 from0 without another writer.
        while(changed && rounds++<256) {
            changed=false;
            foreach(State writer in writers) {
                // A definite Always/Replace covering every patch sample discards all
                // earlier stencil values. Ambiguous order remains in the closure.
                if(barrier!=null && (writer==barrier || Before(writer,barrier))) continue;
                if(!Touches(writer,patch)) continue;
                for(int value=0;value<256;value++) if(reachable[value]&&Pass(writer,value)) {
                    int next=Write(writer,value);
                    if(!reachable[next]) { reachable[next]=true;count++;changed=true; }
                }
            }
        }
        foreach(State test in tests) for(int value=0;value<256;value++)
            if(reachable[value]&&Pass(test,value)) { LastReason="stencil_possible:values="+count+",reset="+(barrier==null?"none":barrier.reference.ToString())+",depth="+depthReason;return true; }
        LastReason="stencil_unreachable:values="+count+",writers="+writers.Count+",reset="+(barrier==null?"none":barrier.reference.ToString());
        return false;
    }
}
