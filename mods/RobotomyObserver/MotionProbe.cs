using System;
using System.IO;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

// Transient engineering regression. Does not touch models, paths, progression or saves.
public sealed class MotionProbe : MonoBehaviour {
    string output;
    GameObject cover;
    GameObject worldCover;
    GameObject stencilCover;
    GameObject remoteMask;
    readonly List<UnityEngine.Object> worldAssets=new List<UnityEngine.Object>();
    ConsoleProbeEffect effect;
    Camera cam;
    int mask;
    readonly Dictionary<Renderer,bool> savedRenderers=new Dictionary<Renderer,bool>();
    CameraFilterPack_Colors_RgbClamp clamp;
    float rgbStart;
    readonly ConsoleMotion motion=new ConsoleMotion();
    readonly List<string> results=new List<string>();
    public void Begin(string path) { output=path; ConsoleMotion.ProbeActive=true; StartCoroutine(Run()); }
    string Read() {
        var ui=new ConsoleUI(); ui.Capture(new List<ViewRect>(),new List<ViewRect>(),new List<string>());
        motion.Capture(ui,true); return motion.Snapshot;
    }
    void Check(string name,bool empty) {
        string value=Read(); bool actual=value.Contains("\"tracks\":[]");
        string file="motion-probe-"+name+".png";
        var frame=new Texture2D(Screen.width,Screen.height,TextureFormat.RGB24,false);
        try {
            frame.ReadPixels(new Rect(0,0,Screen.width,Screen.height),0,0,false); frame.Apply(false);
            File.WriteAllBytes(Path.Combine(output,file),frame.EncodeToPNG());
        } finally { Destroy(frame); }
        results.Add("{\"case\":"+RobotomyObserver.Quote(name)+",\"frame\":"+RobotomyObserver.Quote(file)+",\"passed\":"+(actual==empty?"true":"false")+",\"snapshot\":"+value+",\"diagnostics\":"+motion.Diagnostics()+"}");
    }
    void WorldCover(byte alpha) {
        if(worldCover!=null) { worldCover.SetActive(false); Destroy(worldCover); }
        var texture=new Texture2D(16,16,TextureFormat.RGBA32,false);
        var pixels=new Color32[256]; for(int i=0;i<pixels.Length;i++) pixels[i]=new Color32(0,0,0,alpha);
        texture.SetPixels32(pixels); texture.Apply();
        var sprite=Sprite.Create(texture,new Rect(0,0,16,16),new Vector2(.5f,.5f),16);
        var material=new Material(Shader.Find("Sprites/Default"));
        worldAssets.Add(texture); worldAssets.Add(sprite); worldAssets.Add(material);
        worldCover=new GameObject("MotionWorldProbe",typeof(SpriteRenderer));
        var renderer=worldCover.GetComponent<SpriteRenderer>(); renderer.sprite=sprite; renderer.sharedMaterial=material;
        renderer.sortingOrder=32760;
        worldCover.transform.position=cam.ViewportToWorldPoint(new Vector3(.5f,.5f,cam.nearClipPlane+1));
        worldCover.transform.localScale=new Vector3(cam.orthographicSize*cam.aspect*3,cam.orthographicSize*3,1);
    }
    IEnumerator Run() {
        cam=Camera.main; if(cam==null) { Destroy(this); yield break; } mask=cam.cullingMask;
        yield return new WaitForEndOfFrame(); Check("visible_positive",false);
        // Reproduce the shipped UI path: an off-body mask plus a mesh modifier,
        // followed by the mask's pop material. Its writes must stay local even
        // while tutorial-style Canvas sorting changes.
        remoteMask=new GameObject("MotionRemoteMaskCanvas",typeof(RectTransform),typeof(Canvas));
        var remoteCanvas=remoteMask.GetComponent<Canvas>();
        remoteCanvas.renderMode=RenderMode.ScreenSpaceCamera; remoteCanvas.worldCamera=cam;
        remoteCanvas.planeDistance=10; remoteCanvas.sortingOrder=0;
        var remoteImage=new GameObject("MotionRemoteMask",typeof(RectTransform),typeof(CanvasRenderer),typeof(Image),typeof(Mask),typeof(Outline));
        remoteImage.transform.SetParent(remoteMask.transform,false);
        var remoteRect=remoteImage.GetComponent<RectTransform>();
        remoteRect.anchorMin=remoteRect.anchorMax=new Vector2(0,1);
        remoteRect.pivot=new Vector2(0,1); remoteRect.anchoredPosition=new Vector2(8,-8); remoteRect.sizeDelta=new Vector2(64,32);
        yield return new WaitForEndOfFrame(); Check("remote_ui_mask_default_order",false);
        remoteCanvas.sortingLayerName="UI"; remoteCanvas.sortingOrder=4010;
        yield return new WaitForEndOfFrame(); Check("remote_ui_mask_highlight_order",false);
        remoteCanvas.sortingLayerName="Default"; remoteCanvas.sortingOrder=0;
        yield return new WaitForEndOfFrame(); Check("remote_ui_mask_restored_order",false);
        // Shipped UnitMouseEventManager uses Sliced + fillCenter=false. A huge
        // bounding rectangle is not a filled stencil polygon: only border quads
        // exist. Reproduce that topology with borders outside the viewport.
        var borderTexture=new Texture2D(32,32,TextureFormat.RGBA32,false);
        var borderPixels=new Color32[1024]; for(int i=0;i<borderPixels.Length;i++) borderPixels[i]=new Color32(255,255,255,255);
        borderTexture.SetPixels32(borderPixels);borderTexture.Apply();
        var borderSprite=Sprite.Create(borderTexture,new Rect(0,0,32,32),new Vector2(.5f,.5f),100,0,SpriteMeshType.FullRect,new Vector4(4,4,4,4));
        worldAssets.Add(borderTexture);worldAssets.Add(borderSprite);
        var borderImage=remoteImage.GetComponent<Image>();borderImage.sprite=borderSprite;borderImage.type=Image.Type.Sliced;borderImage.fillCenter=false;
        remoteImage.GetComponent<Mask>().showMaskGraphic=false;
        remoteRect.anchorMin=Vector2.zero;remoteRect.anchorMax=Vector2.one;
        remoteRect.offsetMin=new Vector2(-100,-100);remoteRect.offsetMax=new Vector2(100,100);
        yield return new WaitForEndOfFrame(); Check("sliced_ui_mask_empty_center",false);
        remoteMask.SetActive(false); Destroy(remoteMask); remoteMask=null;
        cover=new GameObject("MotionProbeCover",typeof(RectTransform),typeof(Canvas));
        var canvas=cover.GetComponent<Canvas>(); canvas.renderMode=RenderMode.ScreenSpaceOverlay; canvas.sortingOrder=32760;
        var child=new GameObject("MotionOpaqueCover",typeof(RectTransform),typeof(CanvasRenderer),typeof(Image));
        child.transform.SetParent(cover.transform,false);
        var r=child.GetComponent<RectTransform>(); r.anchorMin=Vector2.zero; r.anchorMax=Vector2.one; r.offsetMin=r.offsetMax=Vector2.zero;
        child.GetComponent<Image>().color=Color.black;
        yield return new WaitForEndOfFrame(); Check("opaque_ui_cover",true);
        child.GetComponent<Image>().color=new Color(0,0,0,.25f);
        yield return new WaitForEndOfFrame(); Check("translucent_cover",true);
        cover.SetActive(false);
        yield return new WaitForEndOfFrame(); Check("reappeared_acquiring",false);
        WorldCover(255);
        yield return new WaitForEndOfFrame(); Check("opaque_world_cover",true);
        WorldCover(5);
        yield return new WaitForEndOfFrame(); Check("light_world_shading",false);
        worldCover.SetActive(false); Destroy(worldCover); worldCover=null;
        WorldCover(255);
        var stencilMaterial=new Material(Shader.Find("Custom/SpriteDefaultCustomMask")); worldAssets.Add(stencilMaterial);
        stencilMaterial.SetFloat("_Stencil",231); stencilMaterial.SetFloat("_StencilReadMask",255);
        stencilMaterial.SetFloat("_StencilComp",3); stencilMaterial.SetFloat("_StencilOp",0);
        worldCover.GetComponent<SpriteRenderer>().sharedMaterial=stencilMaterial;
        yield return new WaitForEndOfFrame(); Check("unreachable_stencil_cover",false);
        stencilCover=worldCover; worldCover=null;
        WorldCover(0); // Alpha zero still writes stencil: this shader has no discard.
        var writerMaterial=new Material(Shader.Find("Custom/SpriteDefaultCustomMask")); worldAssets.Add(writerMaterial);
        writerMaterial.SetFloat("_Stencil",231); writerMaterial.SetFloat("_StencilReadMask",255);
        writerMaterial.SetFloat("_StencilComp",8); writerMaterial.SetFloat("_StencilOp",2);
        worldCover.GetComponent<SpriteRenderer>().sharedMaterial=writerMaterial;
        worldCover.GetComponent<SpriteRenderer>().sortingOrder=32759;
        yield return new WaitForEndOfFrame(); Check("transparent_stencil_writer_reveals_cover",true);
        worldCover.SetActive(false); Destroy(worldCover); worldCover=null;
        stencilCover.SetActive(false); Destroy(stencilCover); stencilCover=null;
        cam.cullingMask=0;
        yield return new WaitForEndOfFrame(); Check("camera_culling_mask",true);
        cam.cullingMask=mask;
        foreach(Renderer body in UnityEngine.Object.FindObjectsOfType<Renderer>())
            if(body.GetComponentInParent<WorkerUnit>()!=null || body.GetComponentInParent<CreatureUnit>()!=null) {
                savedRenderers[body]=body.enabled; body.enabled=false;
            }
        yield return new WaitForEndOfFrame(); Check("body_renderers_disabled",true);
        foreach(var saved in savedRenderers) if(saved.Key!=null) saved.Key.enabled=saved.Value;
        savedRenderers.Clear();
        effect=cam.gameObject.AddComponent<ConsoleProbeEffect>();
        yield return new WaitForEndOfFrame(); Check("unknown_postprocess",true);
        effect.enabled=false; Destroy(effect); effect=null;
        clamp=cam.GetComponent<CameraFilterPack_Colors_RgbClamp>();
        if(clamp!=null && clamp.enabled) {
            rgbStart=clamp.RGB_Start; clamp.RGB_Start+=.123f;
            yield return new WaitForEndOfFrame(); Check("known_clamp_changed",true);
            clamp.RGB_Start=rgbStart; clamp=null;
        }
        var glow=cam.GetComponent<CameraFilterPack_Glow_Glow_Color>();
        if(glow!=null && glow.enabled) {
            float original=glow.Threshold; glow.Threshold=original+.123f;
            yield return new WaitForEndOfFrame(); Check("known_filter_changed",true);
            glow.Threshold=original;
        }
        yield return new WaitForEndOfFrame(); Check("restored_positive",false);
        File.WriteAllText(Path.Combine(output,"motion-probe.json"),"{\"basis\":\"transient_render_fixture_in_actual_tutorial\",\"cases\":["+String.Join(",",results.ToArray())+"]}");
        Destroy(this);
    }
    void OnDestroy() {
        if(cam!=null) cam.cullingMask=mask;
        if(cover!=null) Destroy(cover);
        if(worldCover!=null) Destroy(worldCover);
        if(stencilCover!=null) Destroy(stencilCover);
        if(remoteMask!=null) Destroy(remoteMask);
        foreach(var asset in worldAssets) if(asset!=null) Destroy(asset);
        if(effect!=null) Destroy(effect);
        if(clamp!=null) clamp.RGB_Start=rgbStart;
        foreach(var saved in savedRenderers) if(saved.Key!=null) saved.Key.enabled=saved.Value;
        ConsoleMotion.ProbeActive=false;
    }
}
