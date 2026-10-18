using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using UnityEngine.SceneManagement;

// Device-side display geometry only. Never reads models, paths, destinations or movement stats.
// Unknown render compositions withhold observations. Tokens survive only continuous visibility.
public sealed class ConsoleMotion
{
    sealed class Track {
        public string token = Guid.NewGuid().ToString("N");
        public Vector3 world, local;
        public Vector2 pixel;
        public float time;
    }
    sealed class Cover {
        public Renderer renderer;
        public Rect rect;
        public float near, far;
        public UnityEngine.Object owner;
    }
    readonly Dictionary<Transform, Track> previous = new Dictionary<Transform, Track>();
    readonly Dictionary<string,int> rejected = new Dictionary<string,int>();
    readonly List<string> details = new List<string>();
    string scene = "", blocked = "";
    int width, height, cameraId, candidates, accepted;
    int unsupportedRenderers;
    MotionTargets targets;
    public string Snapshot = "{}";
    public double Milliseconds;
    public static bool ProbeActive;
    static string profilePath, approvedProfile="", currentProfile="";
    static float profileRead=-10;
    public static void Initialize(string directory) { profilePath=System.IO.Path.Combine(directory,"motion-approved-profile.txt"); }

    static string Q(string s) { return RobotomyObserver.Quote(s); }
    static string N(float v) { return Math.Round(v,2).ToString(CultureInfo.InvariantCulture); }
    static string V(Vector2 v) { return "{\"x\":"+N(v.x)+",\"y\":"+N(v.y)+"}"; }
    static Vector2 Pixel(Camera cam, Vector3 world) {
        Vector3 p=cam.WorldToScreenPoint(world); return new Vector2(p.x,Screen.height-p.y);
    }
    bool Reject(string reason, Renderer r) {
        if(!rejected.ContainsKey(reason)) rejected[reason]=0; rejected[reason]++;
        if(details.Count<24) details.Add(Q((r==null?"":r.name)+":"+reason));
        return false;
    }
    static bool Active(Renderer r) {
        if(r==null || !r.enabled || !r.gameObject.activeInHierarchy) return false;
        var sprite=r as SpriteRenderer;
        if(sprite!=null && (sprite.sprite==null || sprite.color.a<=.001f)) return false;
        var m=r.sharedMaterial;
        if(m!=null && m.HasProperty("_Color") && m.GetColor("_Color").a<=.001f) return false;
        return true;
    }
    static bool ProjectBounds(Camera cam, Bounds b, out Rect rect, out float near, out float far) {
        Vector2 lo=new Vector2(float.MaxValue,float.MaxValue), hi=new Vector2(float.MinValue,float.MinValue);
        near=float.MaxValue; far=float.MinValue;
        Vector3 min=b.min, max=b.max;
        for(int i=0;i<8;i++) {
            Vector3 p=cam.WorldToScreenPoint(new Vector3((i&1)==0?min.x:max.x,(i&2)==0?min.y:max.y,(i&4)==0?min.z:max.z));
            near=Mathf.Min(near,p.z); far=Mathf.Max(far,p.z);
            lo=Vector2.Min(lo,new Vector2(p.x,p.y)); hi=Vector2.Max(hi,new Vector2(p.x,p.y));
        }
        rect=Rect.MinMaxRect(lo.x,lo.y,hi.x,hi.y);
        return near>=cam.nearClipPlane && far<=cam.farClipPlane && rect.width>=2 && rect.height>=2;
    }
    List<Cover> Covers(Camera cam,Renderer[] renderers) {
        var result=new List<Cover>();
        foreach(Renderer renderer in renderers) {
            if(!Active(renderer) || (cam.cullingMask&(1<<renderer.gameObject.layer))==0) continue;
            Rect rect; float near,far;
            ProjectBounds(cam,renderer.bounds,out rect,out near,out far);
            if(far<cam.nearClipPlane || near>cam.farClipPlane) continue;
            if(renderer is SpriteRenderer) rect=Rect.MinMaxRect(rect.xMin-1,rect.yMin-1,rect.xMax+1,rect.yMax+1);
            if(!rect.Overlaps(new Rect(0,0,Screen.width,Screen.height))) continue;
            result.Add(new Cover { renderer=renderer,rect=rect,near=near,far=far,owner=targets.Owner(renderer) });
        }
        return result;
    }
    static void DumpRenderers(Camera cam,List<Cover> covers) {
        string folder=System.IO.Path.GetDirectoryName(profilePath), marker=System.IO.Path.Combine(folder,"dump-motion-renderers");
        if(!System.IO.File.Exists(marker)) return;
        var rows=new List<string>();
        foreach(var cover in covers) {
            Renderer r=cover.renderer; Material m=r.sharedMaterial;
            var props=new List<string>();
            foreach(string key in new string[] {"_Stencil","_StencilComp","_StencilOp","_StencilReadMask","_StencilWriteMask"})
                if(m!=null && m.HasProperty(key)) props.Add(Q(key)+":"+N(m.GetFloat(key)));
            rows.Add("{\"name\":"+Q(r.name)+",\"shader\":"+Q(m==null || m.shader==null?"":m.shader.name)+
                ",\"layer\":"+r.sortingLayerID+",\"order\":"+r.sortingOrder+",\"queue\":"+(m==null?0:m.renderQueue)+
                ",\"rect\":"+Q(cover.rect.ToString())+",\"near\":"+N(cover.near)+",\"far\":"+N(cover.far)+",\"properties\":{"+String.Join(",",props.ToArray())+"}}");
        }
        System.IO.File.WriteAllText(System.IO.Path.Combine(folder,"motion-renderers.json"),"{\"camera_clear\":"+Q(cam.clearFlags.ToString())+",\"rendering_path\":"+Q(cam.actualRenderingPath.ToString())+",\"renderers\":["+String.Join(",",rows.ToArray())+"]}");
        System.IO.File.Delete(marker);
    }
    static bool CouldCover(Renderer other, Renderer body, float otherNear,float bodyFar) {
        int a=SortingLayer.GetLayerValueFromID(other.sortingLayerID), b=SortingLayer.GetLayerValueFromID(body.sortingLayerID);
        if(a!=b) return a>b;
        if(other.sortingOrder!=body.sortingOrder) return other.sortingOrder>body.sortingOrder;
        // Different queues/shaders may ignore depth: only a proven farther renderer in the same
        // transparent queue can be dismissed. Equal depth is ambiguous and therefore covered.
        var am=other.sharedMaterial; var bm=body.sharedMaterial;
        if(am==null || bm==null) return true;
        if(am.renderQueue!=bm.renderQueue) return am.renderQueue>bm.renderQueue || am.renderQueue>=3000;
        return otherNear<=bodyFar+.001f;
    }
    static string CameraGuard(Camera cam) {
        if(cam==null || !cam.isActiveAndEnabled || !cam.orthographic || cam.targetTexture!=null) return "camera_unverified";
        if(cam.pixelRect!=new Rect(0,0,Screen.width,Screen.height)) return "viewport_unverified";
        // Scope is explicit. Later boss scenes need render-profile validation before enabling motion.
        string s=SceneManager.GetActiveScene().name;
        if(s!="Tutorial" && s!="Tutorial_1" && s!="Tutorial_2" && s!="Tutorial_3") return "scene_unverified";
        List<string> profile=new List<string>();
        foreach(Camera c in Camera.allCameras) foreach(MonoBehaviour effect in c.GetComponents<MonoBehaviour>()) {
            if(effect==null || !effect.isActiveAndEnabled) continue;
            if(effect.GetType().GetMethod("OnRenderImage",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Public)==null) continue;
            if(c!=cam || (!(effect is CameraFilterPack_Colors_RgbClamp) && !(effect is CameraFilterPack_Glow_Glow_Color))) return "render_effect_unverified";
            List<string> fields=new List<string>();
            foreach(var field in effect.GetType().GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.DeclaredOnly)) {
                object value=field.GetValue(effect);
                if(value is float) fields.Add(field.Name+"="+((float)value).ToString("R",CultureInfo.InvariantCulture));
                else if(value is int) fields.Add(field.Name+"="+value);
                else if(value is Color) { Color color=(Color)value; fields.Add(field.Name+"="+color.r.ToString("R",CultureInfo.InvariantCulture)+","+color.g.ToString("R",CultureInfo.InvariantCulture)+","+color.b.ToString("R",CultureInfo.InvariantCulture)+","+color.a.ToString("R",CultureInfo.InvariantCulture)); }
            }
            fields.Sort(); profile.Add(effect.GetType().Name+":"+String.Join(";",fields.ToArray()));
        }
        profile.Sort(); currentProfile=s+"|"+String.Join("|",profile.ToArray());
        if(Time.realtimeSinceStartup-profileRead>1) {
            profileRead=Time.realtimeSinceStartup;
            try { approvedProfile=System.IO.File.ReadAllText(profilePath).Trim(); } catch { approvedProfile=""; }
        }
        return approvedProfile==currentProfile?"":"profile_unverified";
    }
    bool Displayable(Renderer body, Camera cam) {
        Rect rect;
        if(!Active(body)) return Reject("inactive",body);
        if(!body.isVisible || body.shadowCastingMode==UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly ||
            body.GetComponentInParent<LODGroup>()!=null || cam.layerCullDistances[body.gameObject.layer]!=0)
            return Reject("draw_visibility_unverified",body);
        if((cam.cullingMask&(1<<body.gameObject.layer))==0) return Reject("layer_culled",body);
        foreach(Camera other in Camera.allCameras)
            if(other!=cam && other.targetTexture==null) {
                if((other.cullingMask&(1<<body.gameObject.layer))!=0) return Reject("multiple_cameras",body);
                if(other.depth>=cam.depth && (other.clearFlags==CameraClearFlags.Color || other.clearFlags==CameraClearFlags.Skybox))
                    return Reject("later_camera_clear",body);
            }
        var materials=body.sharedMaterials;
        if(materials.Length==0) return Reject("no_material",body);
        var block=new MaterialPropertyBlock(); body.GetPropertyBlock(block);
        if(!block.isEmpty) return Reject("property_block",body);
        foreach(Material m in materials) {
            if(m==null || m.shader==null || m.shader.name!="Spine/Skeleton") return Reject("body_shader",body);
            if(m.HasProperty("_Color") && m.GetColor("_Color").a<.99f) return Reject("material_alpha",body);
        }
        // Vertex alpha is final draw data; skeleton/model visibility flags are not consulted.
        var filter=body.GetComponent<MeshFilter>();
        if(filter==null || filter.sharedMesh==null || filter.sharedMesh.vertexCount==0) return Reject("empty_mesh",body);
        Color32[] colors=filter.sharedMesh.colors32;
        bool opaque=false;
        foreach(Color32 color in colors) if(color.a>=253) { opaque=true; break; }
        if(!opaque) return Reject("vertex_alpha",body);
        float near,far;
        if(!ProjectBounds(cam,body.bounds,out rect,out near,out far)) return Reject("clip_or_empty",body);
        if(rect.xMin<0 || rect.yMin<0 || rect.xMax>Screen.width || rect.yMax>Screen.height) return Reject("outside_screen",body);
        return true;
    }
    static string CoverInfo(Renderer other,Renderer body) {
        var s=other as SpriteRenderer; var p=new MaterialPropertyBlock(); other.GetPropertyBlock(p);
        var m=other.sharedMaterial;
        string stencil=m!=null && m.HasProperty("_StencilComp")?",stencil="+m.GetFloat("_StencilComp")+","+m.GetFloat("_Stencil")+","+m.GetFloat("_StencilOp"):"";
        return "otherQueue="+(m==null?0:m.renderQueue)+",bodyQueue="+(body.sharedMaterial==null?0:body.sharedMaterial.renderQueue)+",bodyOrder="+body.sortingOrder+",block="+!p.isEmpty+",color="+(s==null?"none":s.color.ToString())+",mode="+(s==null?"none":s.drawMode.ToString())+stencil+",transparentFailure="+MotionSurface.LastFailure+":";
    }
    bool Uncovered(Renderer body, Camera cam, List<Cover> all, ConsoleUI ui, Rect rect, Vector3 world) {
        string uiCover=ui.MotionCover(rect,body.transform);
        if(uiCover!="") return Reject("ui_or_pointer_cover:"+uiCover,body);
        float depth=cam.WorldToScreenPoint(world).z;
        float transmission=1;
        UnityEngine.Object owner=targets.Owner(body);
        foreach(Cover cover in all) {
            Renderer other=cover.renderer;
            if(other==body || (owner!=null && owner==cover.owner) || !rect.Overlaps(cover.rect)) continue;
            float on=cover.near;
            if(CouldCover(other,body,on,depth)) {
                if(!MotionStencil.CanDraw(other,rect)) continue;
                transmission*=MotionSurface.Transmission(other,cam,rect);
                if(transmission<.5f)
                    return Reject("world_cover:transmission="+N(transmission)+":alpha="+N(MotionSurface.LastTextureAlphaMaximum)+":"+MotionSurface.LastBoundDescription+":"+CoverInfo(other,body)+other.name+":"+(other.sharedMaterial==null?"null":other.sharedMaterial.shader.name)+":layer="+other.sortingLayerName+":order="+other.sortingOrder+":near="+N(on)+":bodyDepth="+N(depth),body);
            }
        }
        return true;
    }
    bool Surface(List<Renderer> parts,Transform anchor,Track old,Camera cam,List<Cover> all,ConsoleUI ui,out Vector3 world,out Rect region,out bool retained) {
        world=Vector3.zero; region=new Rect(); retained=false;
        foreach(Renderer part in parts) if(!Displayable(part,cam)) return false;
        if(old!=null) {
            world=anchor.TransformPoint(old.local);
            foreach(Renderer part in parts) if(MotionSurface.Contains(part,cam,world,out region) && Uncovered(part,cam,all,ui,region,world)) { retained=true; return true; }
        }
        foreach(Renderer part in parts) {
            Renderer selected=part;
            if(MotionSurface.PickVisible(part,cam,(patch,point)=>Uncovered(selected,cam,all,ui,patch,point),out world,out region)) return true;
        }
        return Reject("no_visible_surface:"+MotionSurface.LastFailure,parts.Count==0?null:parts[0]);
    }
    static List<Renderer> BodyRenderers(Spine.Unity.SkeletonRenderer skeleton) {
        var result=new List<Renderer>();
        var split=skeleton.GetComponent<Spine.Unity.Modules.SkeletonRenderSeparator>();
        if(split!=null && split.isActiveAndEnabled) {
            foreach(var part in split.partsRenderers) if(part!=null && Active(part.MeshRenderer)) {
                var f=part.GetComponent<MeshFilter>();
                if(f!=null && f.sharedMesh!=null && f.sharedMesh.vertexCount>0) result.Add(part.MeshRenderer);
            }
        } else { var r=skeleton.GetComponent<Renderer>(); if(r!=null) result.Add(r); }
        return result;
    }
    public void Capture(ConsoleUI ui, bool diagnostic=false) {
        var timer=System.Diagnostics.Stopwatch.StartNew();
        rejected.Clear(); details.Clear(); candidates=accepted=unsupportedRenderers=0;
        targets=null;
        Camera cam=Camera.main;
        string current=SceneManager.GetActiveScene().name;
        int id=cam==null?0:cam.GetInstanceID();
        if(current!=scene || width!=Screen.width || height!=Screen.height || id!=cameraId) { previous.Clear(); MotionSurface.Reset(); }
        scene=current; width=Screen.width; height=Screen.height; cameraId=id;
        blocked=ProbeActive && !diagnostic?"engineering_probe":CameraGuard(cam);
        List<string> items=new List<string>();
        Dictionary<Transform,Track> next=new Dictionary<Transform,Track>();
        if(blocked=="") {
            // Broad-phase geometry and ownership are shared by all target checks in
            // this frame; never reuse them across frames where masks can change.
            Renderer[] renderers=UnityEngine.Object.FindObjectsOfType<Renderer>();
            targets=new MotionTargets(renderers);
            unsupportedRenderers=targets.UnsupportedRenderers;
            MotionStencil.Prepare(cam,renderers);
            List<Cover> all=Covers(cam,renderers);
            Dictionary<Transform,List<Renderer>> bodies=new Dictionary<Transform,List<Renderer>>();
            foreach(var target in targets.Skeletons) bodies[target.Key]=BodyRenderers(target.Value);
            float now=Time.realtimeSinceStartup;
            if(bodies.Count>0) DumpRenderers(cam,all);
            foreach(var candidate in bodies) {
                Transform anchor=candidate.Key;
                Renderer body=candidate.Value.Count==0?null:candidate.Value[0];
                candidates++;
                Track old; previous.TryGetValue(anchor,out old);
                Rect bounds; Vector3 world; bool retained;
                if(!Surface(candidate.Value,anchor,old,cam,all,ui,out world,out bounds,out retained)) continue;
                Vector2 pixel=Pixel(cam,world);
                if(pixel.x<0 || pixel.y<0 || pixel.x>width || pixel.y>height) { Reject("anchor_outside",body); continue; }
                string state="acquiring", screen="null", obj="null", camera="null"; float dt=0;
                Track track=new Track();
                if(retained && old!=null) {
                    dt=Mathf.Min(60,now-old.time);
                    Vector2 reproject=Pixel(cam,old.world);
                    Vector2 objectDelta=pixel-reproject, cameraDelta=reproject-old.pixel;
                    if(dt>=.01f && dt<=.3f && objectDelta.magnitude<=Mathf.Max(48,Mathf.Min(width,height)*.12f)) {
                        track=old; state="tracking";
                        screen=V((pixel-old.pixel)/dt); obj=V(objectDelta/dt); camera=V(cameraDelta/dt);
                    } else state="discontinuity";
                }
                track.local=anchor.InverseTransformPoint(world); track.world=world; track.pixel=pixel; track.time=now; next[anchor]=track;
                items.Add("{\"track_id\":"+Q(track.token)+",\"state\":"+Q(state)+",\"position\":"+V(pixel)+
                    ",\"bounds\":{\"x\":"+N(bounds.x)+",\"y\":"+N(height-bounds.yMax)+",\"width\":"+N(bounds.width)+",\"height\":"+N(bounds.height)+"}"+
                    ",\"interval_ms\":"+N(dt*1000)+",\"screen_velocity\":"+screen+",\"object_velocity\":"+obj+",\"camera_velocity\":"+camera+"}");
                accepted++;
                if(accepted>=128) break;
            }
        }
        previous.Clear(); foreach(var pair in next) previous[pair.Key]=pair.Value;
        Snapshot="{\"version\":1,\"basis\":\"display_projection_v1\",\"coordinates\":\"top_left_pixels\",\"units\":\"pixels_per_real_second\",\"status\":"+
            Q(blocked==""?"available":"withheld")+",\"tracks\":["+String.Join(",",items.ToArray())+"]}";
        Milliseconds=timer.Elapsed.TotalMilliseconds;
    }
    public string Diagnostics() {
        List<string> reasons=new List<string>(); foreach(var p in rejected) reasons.Add(Q(p.Key)+":"+p.Value);
        return "{\"candidates\":"+candidates+",\"accepted\":"+accepted+",\"unsupported_body_renderers\":"+unsupportedRenderers+",\"blocked\":"+Q(blocked)+",\"profile\":"+Q(currentProfile)+",\"stencil\":"+Q(MotionStencil.LastReason)+",\"stencil_mask\":"+Q(MotionStencil.LastMaskSummary)+",\"canvas_shaders\":"+Q(MotionStencil.LastDepthShaders)+",\"surface_cache_bytes\":"+MotionSurface.CachedTextureBytes+",\"surface_cold_ms\":"+MotionSurface.LastColdMilliseconds.ToString("R",CultureInfo.InvariantCulture)+",\"rejected\":{"+String.Join(",",reasons.ToArray())+"},\"details\":["+String.Join(",",details.ToArray())+"]}";
    }
}
