using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

// Only display objects are read. No model, unlock flag, tooltip backing data or asset names.
public sealed class ConsoleUI
{
    sealed class Panel {
        public GameObject root;
        public Text[] texts = new Text[0];
        public Button[] buttons = new Button[0];
        public float refreshed = -10;
        public void Bind(GameObject next) {
            if (root == next && Time.realtimeSinceStartup - refreshed < 1) return;
            root = next; refreshed = Time.realtimeSinceStartup;
            texts = root == null ? new Text[0] : root.GetComponentsInChildren<Text>(true);
            buttons = root == null ? new Button[0] : root.GetComponentsInChildren<Button>(true);
        }
    }
    readonly Panel energy = new Panel(), agent = new Panel(), creature = new Panel();
    readonly ConsolePanels displayPanels = new ConsolePanels();
    readonly Dictionary<GameObject,Panel> extraPanels = new Dictionary<GameObject,Panel>();
    readonly HashSet<Text> readTexts = new HashSet<Text>();
    readonly Dictionary<string,int> panelCounts = new Dictionary<string,int>();
    InGameUI.AgentUI[] hud = new InGameUI.AgentUI[0];
    float hudRefresh = -10;
    readonly ConsoleCoverAlpha coverAlpha = new ConsoleCoverAlpha();
    PlaySpeedSettingUI speedUI;
    readonly List<Graphic> graphics = new List<Graphic>();
    readonly Dictionary<Graphic, Rect> rectangles = new Dictionary<Graphic, Rect>();
    public readonly Dictionary<string,int> rejected = new Dictionary<string,int>();
    public int candidates, accepted, energyCount, agentCount, creatureCount, hudCount;
    bool unsafeEffects;
    readonly List<string> effects = new List<string>(), rejectionDetails = new List<string>();
    string inspecting = "";

    static bool Active(GameObject go) { return go != null && go.activeInHierarchy; }
    static bool Basic(Graphic g, bool feelingPalette=false) {
        if (g == null || !g.isActiveAndEnabled || g.canvas == null || !g.canvas.isActiveAndEnabled ||
            g.color.a < (feelingPalette ? .78f : .99f) || g.canvasRenderer.GetAlpha() < .99f || g.canvasRenderer.cull || g.depth < 0) return false;
        foreach (CanvasGroup group in g.GetComponentsInParent<CanvasGroup>()) if (group.alpha < .99f) return false;
        return true;
    }
    static bool Drawn(Graphic g) {
        if (g == null || !g.isActiveAndEnabled || g.canvas == null || !g.canvas.isActiveAndEnabled ||
            g.color.a <= .001f || g.canvasRenderer.GetAlpha() <= .001f || g.canvasRenderer.cull || g.depth < 0) return false;
        foreach (CanvasGroup group in g.GetComponentsInParent<CanvasGroup>()) if (group.alpha <= .001f) return false;
        Mask mask = g.GetComponent<Mask>();
        return mask == null || !mask.isActiveAndEnabled || mask.showMaskGraphic;
    }
    public static Camera DisplayCamera(Canvas canvas) {
        if(canvas==null || canvas.renderMode==RenderMode.ScreenSpaceOverlay)return null;
        if(canvas.renderMode==RenderMode.ScreenSpaceCamera)return canvas.worldCamera;
        Camera found=null;foreach(var c in Camera.allCameras)if(c.targetTexture==null && (c.cullingMask&(1<<canvas.gameObject.layer))!=0){if(found!=null)return null;found=c;}return found;
    }
    public static bool ScreenRect(RectTransform rect, Canvas canvas, out Rect result) {
        result = new Rect();
        if (rect == null || canvas == null) return false;
        Camera cam = DisplayCamera(canvas);
        if (canvas.renderMode != RenderMode.ScreenSpaceOverlay &&
            (cam == null || !cam.isActiveAndEnabled || (cam.cullingMask & (1 << canvas.gameObject.layer)) == 0)) return false;
        Vector3[] corners = new Vector3[4]; rect.GetWorldCorners(corners);
        Vector2 min = new Vector2(float.MaxValue,float.MaxValue), max = new Vector2(float.MinValue,float.MinValue);
        foreach (Vector3 corner in corners) {
            if (cam != null && cam.WorldToScreenPoint(corner).z <= 0) return false;
            Vector2 point = RectTransformUtility.WorldToScreenPoint(cam,corner);
            min = Vector2.Min(min,point); max = Vector2.Max(max,point);
        }
        result = Rect.MinMaxRect(min.x,min.y,max.x,max.y);
        return result.width > .1f && result.height > .1f;
    }
    static bool GraphicRect(Graphic graphic,out Rect result) {
        Text text=graphic as Text;
        if(text==null) return ScreenRect(graphic.rectTransform,graphic.canvas,out result);
        result=new Rect();
        Camera cam=DisplayCamera(text.canvas);
        Rect control;
        if(!ScreenRect(text.rectTransform,text.canvas,out control)) return false;
        var verts=text.cachedTextGenerator.verts;
        if(verts.Count<4 || text.pixelsPerUnit<=0) return false;
        Vector2 min=new Vector2(float.MaxValue,float.MaxValue),max=new Vector2(float.MinValue,float.MinValue);
        bool found=false;
        // Unity Text's generated quad vertices, including best-fit sizing. Ignore zero-area terminator/space quads.
        for(int i=0;i+3<verts.Count;i+=4) {
            Vector3 a=verts[i].position,b=verts[i+2].position;
            if(Mathf.Abs(a.x-b.x)<.01f || Mathf.Abs(a.y-b.y)<.01f) continue;
            for(int j=0;j<4;j++) {
                Vector3 world=text.rectTransform.TransformPoint(verts[i+j].position/text.pixelsPerUnit);
                Vector2 p=RectTransformUtility.WorldToScreenPoint(cam,world);
                min=Vector2.Min(min,p); max=Vector2.Max(max,p); found=true;
            }
        }
        if(!found) return false;
        // Display geometry, not a padded click/search rectangle. Padding created
        // false HP/SP overlap in the shipped command-row layout.
        result=Rect.MinMaxRect(min.x,min.y,max.x,max.y); return true;
    }
    static bool Contains(Rect outer, Rect inner) {
        return inner.xMin >= outer.xMin-.25f && inner.yMin >= outer.yMin-.25f &&
            inner.xMax <= outer.xMax+.25f && inner.yMax <= outer.yMax+.25f;
    }
    bool Reject(string reason) {
        if (!rejected.ContainsKey(reason)) rejected[reason]=0; rejected[reason]++;
        if(rejectionDetails.Count<32) rejectionDetails.Add(RobotomyObserver.Quote(inspecting+":"+reason));
        return false;
    }
    static bool PossiblyInFront(Graphic a, Graphic b) {
        Canvas ca=a.canvas, cb=b.canvas;
        if (ca == cb) return a.depth >= b.depth;
        if (ca.rootCanvas == cb.rootCanvas && !ca.overrideSorting && !cb.overrideSorting) return a.depth >= b.depth;
        if (ca.renderMode == RenderMode.ScreenSpaceOverlay && cb.renderMode != RenderMode.ScreenSpaceOverlay) return true;
        if (ca.renderMode != RenderMode.ScreenSpaceOverlay && cb.renderMode == RenderMode.ScreenSpaceOverlay) return false;
        Camera ac=DisplayCamera(ca),bc=DisplayCamera(cb);
        if(ac!=bc){
            if(ac==null || bc==null || ac.depth==bc.depth)return true;
            return ac.depth>bc.depth; // Cameras render in depth order before Canvas sort order.
        }
        int la=SortingLayer.GetLayerValueFromID(ca.sortingLayerID), lb=SortingLayer.GetLayerValueFromID(cb.sortingLayerID);
        if (la != lb) return la > lb;
        if (ca.sortingOrder != cb.sortingOrder) return ca.sortingOrder > cb.sortingOrder;
        return ca.renderOrder >= cb.renderOrder;
    }
    public bool Visible(Graphic g, out Rect rect) { return Visible(g,out rect,false); }
    // Empty overload slots still occupy the displayed bar layout. No model count is read.
    public bool VisibleGaugeSlot(Image g,out Rect rect) { return Visible(g,out rect,false,true); }
    public bool VisibleWorldLabel(Text g,out Rect rect) { return Visible(g,out rect,false,false,true); }
    public bool VisibleResearch(Graphic g,Transform surface,out Rect rect) { return Visible(g,out rect,false,false,false,null,surface,false,true); }
    public bool VisibleStory(Graphic g,out Rect rect) { return Visible(g,out rect,false,false,false,null,null,false,true,true); }
    public bool VisibleWorldGraphic(Graphic g,out Rect rect) { return Visible(g,out rect,false,false,true); }
    public bool VisibleWorldRegion(Graphic g,Rect rect) { Rect unused;return Visible(g,out unused,false,false,true,rect); }
    public bool VisibleTextRegion(Text g,Rect region){Rect r;return Visible(g,out r,false,false,false,region);}
    public bool VisibleReadingRegion(Text g,Rect region,Transform surface){Rect r;return Visible(g,out r,false,false,false,region,surface);}
    // Command window uses intentionally translucent artwork/text. Transparent or
    // culled graphics still disappear; ancestor groups, masks and external covers remain checked.
    public bool VisibleCommandGraphic(Graphic g,Transform surface,out Rect rect) {
        rect=new Rect();
        if(g==null || g.canvasRenderer.cull || g.color.a*g.canvasRenderer.GetAlpha()<=.05f)return false;
        return Visible(g,out rect,false,true,false,null,surface);
    }
    public bool VisibleSurface(Graphic g,Transform surface,out Rect rect){return Visible(g,out rect,false,false,false,null,surface);}
    public bool VisibleHitSurface(Graphic g,Transform surface,out Rect rect){
        rect=new Rect();if(g==null || !GraphicRect(g,out rect))return false;
        Rect ignored;var point=new Rect(rect.center.x-.5f,rect.center.y-.5f,1,1);
        return Visible(g,out ignored,false,false,false,point,surface);
    }
    // Feeling-state palette uses alpha 200/255 in the shipped game. Other fades remain rejected.
    public bool VisibleFeelingLabel(Text g,out Rect rect){return Visible(g,out rect,false,false,false,null,null,true);}
    bool Visible(Graphic g, out Rect rect, bool playbackIcon, bool emptySlot=false, bool worldLabel=false,Rect? region=null,Transform surface=null,bool feelingPalette=false,bool authoredRotation=false,bool storyCanvas=false) {
        rect = new Rect();
        inspecting=g==null?"null":g.name;
        if (emptySlot) {
            if(g==null || !g.isActiveAndEnabled || g.canvas==null || !g.canvas.isActiveAndEnabled || g.depth<0) return Reject("inactive_slot");
            foreach(CanvasGroup group in g.GetComponentsInParent<CanvasGroup>()) if(group.alpha<.99f)return Reject("hidden_slot_group");
        } else if (!Basic(g,feelingPalette)) return Reject("inactive_or_faded");
        string disclosure=ConsoleDisclosure.RejectReason(g.transform);
        if (disclosure!=null) return Reject(disclosure);
        if (unsafeEffects) return Reject("unverified_effect");
        if(!worldLabel && !storyCanvas && (g.canvas.renderMode==RenderMode.WorldSpace || (g.canvas.worldCamera!=null && g.canvas.worldCamera.name=="MainCamera")))
            return Reject("world_render_unverified");
        if (g.material != null && g.material != g.defaultMaterial) return Reject("custom_material");
        if (!(region.HasValue ? ((rect=region.Value).width>0) : GraphicRect(g,out rect)) || !Contains(new Rect(0,0,Screen.width,Screen.height),rect))
            return Reject("outside_screen:"+rect.ToString());
        if (!authoredRotation && Mathf.Abs(Mathf.DeltaAngle(g.rectTransform.eulerAngles.z,0)) > .1f) return Reject("rotated");
        // Our own diagnostic crosshair is not a game occluder for an audited
        // playback icon. Game panels/masks still pass through all checks below.
        // Device-owned pointer is an observation aid, not a game information mask.
        // Match this game's Unity MaskableGraphic: a sorting-override Canvas
        // ends ancestor stencil masks; RectMask2D uses its own selected clip chain.
        var mg=g as MaskableGraphic;
        if(mg!=null && mg.maskable){
            Transform stop=MaskUtilities.FindRootSortOverrideCanvas(g.transform);
            if(g.transform!=stop)for(Transform p=g.transform.parent;p!=null;p=p.parent){
                var mask=p.GetComponent<Mask>();Rect area;
                if(mask!=null && mask.MaskEnabled() && mask.graphic.IsActive() &&
                   (!ScreenRect(mask.rectTransform,mask.graphic.canvas,out area) || !Contains(area,rect)))return Reject("mask_clipped");
                if(p==stop)break;
            }
            var clip=MaskUtilities.GetRectMaskForClippable(mg);
            if(clip!=null){var masks=new List<RectMask2D>();MaskUtilities.GetRectMasksForClip(clip,masks);
                foreach(var mask in masks){Rect area;var canvas=mask.GetComponentInParent<Canvas>();
                    if(!ScreenRect(mask.rectTransform,canvas,out area)||!Contains(area,rect))return Reject("mask_clipped");}
            }
        }
        // Covers are checked even when a covered Text continues updating.
        foreach (Graphic other in graphics) {
            Rect box;
            if (other == g || !rectangles.TryGetValue(other,out box) || !rect.Overlaps(box)) continue;
            // Room HUD decorations belong to the same authored display surface.
            // They are not independent occluders of their own timer/name labels.
            if(worldLabel && other.canvas==g.canvas)continue;
            // Audited composite widgets: portrait pieces/button labels are their
            // own display, not external cover panels. Masks still apply above.
            if(surface!=null && (other.transform==surface || other.transform.IsChildOf(surface)))continue;
            if (PossiblyInFront(other,g)) {
                // Only the game's normal pause decoration is eligible. Other covers stay effective.
                if(ClearPauseCover(other,box,rect)) continue;
                // Normal pause decoration tints the facility; it does not hide its HUD.
                var worldPause=other as Image;
                if(worldLabel && speedUI!=null && worldPause==speedUI.pauseFilter &&
                   (worldPause.sprite==speedUI.pauseDefSprite || worldPause.sprite==speedUI.observeSprite))continue;
                // Normal pause artwork tints this command panel but does not hide its text.
                // Limit the exception to the game's two known pause sprites and this UI root.
                var command=CommandWindow.CommandWindow.CurrentWindow;
                var pause=other as Image;
                var aw=AgentInfoWindow.currentWindow;
                bool knownPanel=surface!=null && ((command!=null && command.RootControl!=null && surface==command.RootControl.transform) || (aw!=null && surface==aw.transform));
                if(knownPanel && speedUI!=null && pause==speedUI.pauseFilter && (pause.sprite==speedUI.pauseDefSprite || pause.sprite==speedUI.observeSprite))continue;
                 inspecting+="<-"+other.name; return Reject("front_graphic"); }
        }
        if(worldLabel && !ConsoleWorldLabels.Clear(g,rect))return Reject("world_label_cover");
        return true;
    }
    static ViewRect Item(Rect r, string text) {
        return new ViewRect { text=text, x=r.x, y=Screen.height-r.yMax, width=r.width, height=r.height };
    }
    void ReadPanel(Panel panel, string source, List<ViewRect> texts, List<ViewRect> buttons) {
        if (!Active(panel.root)) return;
        foreach (Text text in panel.texts) {
            if (text == null || !text.isActiveAndEnabled || !readTexts.Add(text)) continue;
            var record=CreatureInfoWindow.CurrentWindow;
            if(record!=null && record.descList.Contains(text))continue;
            candidates++; Rect rect;
            if (!(source=="command" ? VisibleCommandGraphic(text,panel.root.transform,out rect) : Visible(text,out rect))) continue;
            // Reject truncation and rich-text constructs that can hide characters.
            string value=text.text;
            if (String.IsNullOrEmpty(value) || value.Length>2048) continue;
            string plain=text.supportRichText?System.Text.RegularExpressions.Regex.Replace(value,"<[^>]*>",""):value;
            if (text.cachedTextGenerator.characterCountVisible < plain.Length) {
                Reject("text_overflow"); continue;
            }
            if (text.supportRichText && (value.IndexOf("<size",StringComparison.OrdinalIgnoreCase)>=0 ||
                System.Text.RegularExpressions.Regex.IsMatch(value,@"<color\s*=\s*[^>]*(#[0-9a-fA-F]{8}|clear)[^>]*>",System.Text.RegularExpressions.RegexOptions.IgnoreCase))) {
                Reject("rich_text_visibility"); continue;
            }
            ViewRect item=Item(rect,value); item.panel=source;
            var row=text.GetComponentInParent<CommandWindow.AgentSlot>();
            if(row!=null && source=="command") {
                item.row_id=row.GetInstanceID().ToString();
                var management=row as CommandWindow.ManagementSlot;
                var work=management==null?null:management.workData;
                item.role=text==row.AgentName?"name":text==row.HealthText?"hp":text==row.MentalText?"sp":
                    text==row.FilterText?"status":text==row.WorkFilterText?"action":text==row.WorkFilterSubText?"action_detail":work!=null && text==work.WorkSuccess?"success_rate":work!=null && text==work.WorkSpeed?"work_time":work!=null && text==work.WorkLevel?"work_level":"";
            }
            if(source=="command") CommandWindowReading.Tag(text,item);
            texts.Add(item); accepted++;
            if (!panelCounts.ContainsKey(source)) panelCounts[source]=0; panelCounts[source]++;
            if (source=="energy") energyCount++; else if(source=="agent") agentCount++; else if(source=="creature") creatureCount++;
        }
        foreach (Button button in panel.buttons) {
            if (button == null || !button.isActiveAndEnabled || !button.IsInteractable()) continue;
            // Reuse only an already admitted child label. Never read an occluded button label afresh.
            foreach (Text label in button.GetComponentsInChildren<Text>()) {
                ViewRect admitted=texts.Find(delegate(ViewRect v) { Rect r; return v.panel==source && GraphicRect(label,out r) && v.text==label.text && Mathf.Abs(v.x-r.x)<.1f && Mathf.Abs(v.y-(Screen.height-r.yMax))<.1f; });
                Rect bounds;
                if (admitted != null && ScreenRect(button.transform as RectTransform,label.canvas,out bounds) && Contains(new Rect(0,0,Screen.width,Screen.height),bounds)) {
                    ViewRect item=Item(bounds,admitted.text); item.panel=source; item.interactable=true; buttons.Add(item); break;
                }
            }
        }
    }
    void CaptureCommandTargets(List<ViewRect> texts,List<ViewRect> buttons) {
        var window=CommandWindow.CommandWindow.CurrentWindow;
        var system=UnityEngine.EventSystems.EventSystem.current;
        if(window==null || window.RootControl==null || system==null) return;
        foreach(var row in window.RootControl.GetComponentsInChildren<CommandWindow.AgentSlot>()) {
            string id=row.GetInstanceID().ToString();
            ViewRect anchor=texts.Find(delegate(ViewRect t){return t.row_id==id && (t.role=="name" || t.role=="action");});
            if(anchor==null) continue;
            var point=new Vector2(anchor.x+anchor.width/2,Screen.height-(anchor.y+anchor.height/2));
            var data=new UnityEngine.EventSystems.PointerEventData(system);data.position=point;
            var hits=new List<UnityEngine.EventSystems.RaycastResult>();system.RaycastAll(data,hits);
            if(hits.Count==0) continue;
            var target=UnityEngine.EventSystems.ExecuteEvents.GetEventHandler<UnityEngine.EventSystems.IPointerClickHandler>(hits[0].gameObject);
            var trigger=target==null?null:target.GetComponent<UnityEngine.EventSystems.EventTrigger>();
            bool click=false;
            if(trigger!=null) foreach(var entry in trigger.triggers) {
                if(entry.eventID!=UnityEngine.EventSystems.EventTriggerType.PointerClick) continue;
                for(int i=0;i<entry.callback.GetPersistentEventCount();i++)
                    if(entry.callback.GetPersistentTarget(i)==row && entry.callback.GetPersistentMethodName(i)=="OnClick") click=true;
            }
            if(!click) continue;
            // Identity binding only, after rendered row and click-handler checks.
            // No model vitals/orderability are exported.
            ViewRect item=new ViewRect{text=anchor.text,panel="command",row_id=id,role="click",
                x=anchor.x,y=anchor.y,width=anchor.width,height=anchor.height,
                hit_x=point.x,hit_y=Screen.height-point.y,interactable=true,
                target_id=target.GetInstanceID().ToString(),input_verified=true};
            buttons.Add(item);
            if(row.CurrentAgent!=null && row.CurrentAgent.GetUnit()!=null)
                item.subject_ref="unit:"+ConsoleSignals.Identity(row.CurrentAgent.GetUnit());
        }
    }
    void CapturePlayback(List<ViewRect> texts) {
        if(speedUI==null) return;
        Button[] choices={speedUI.PauseButton,speedUI.NormalSpeed,speedUI.OneHalfSpeed,speedUI.TwiceSpeed};
        string[] labels={"paused","1x","1.5x","2x"};
        ViewRect selected=null;
        for(int i=0;i<choices.Length;i++) {
            var button=choices[i]; Rect rect;
            if(button==null || !button.isActiveAndEnabled || !button.gameObject.activeInHierarchy) continue;
            var display=PlaybackDisplay.Resolve(button);
            if(display==null || !display.Selected || !Visible(display.icon,out rect,true)) continue;
            if(selected!=null) return; // No unique visible selection.
            selected=Item(rect,labels[i]); selected.panel="playback";
        }
        if(selected!=null) texts.Add(selected);
    }
    void CaptureInputTargets(List<ViewRect> buttons) {
        var system=UnityEngine.EventSystems.EventSystem.current;
        if(system==null) return;
        foreach(Button button in UnityEngine.Object.FindObjectsOfType<Button>()) {
            Rect visible, bounds;
            Graphic graphic=button.targetGraphic;
            var playback=PlaybackDisplay.IsPlayback(speedUI,button)?PlaybackDisplay.Resolve(button):null;
            if(playback!=null) graphic=playback.icon;
            if(!button.isActiveAndEnabled || !button.IsInteractable() || graphic==null ||
               !Visible(graphic,out visible,playback!=null) || !ScreenRect(button.transform as RectTransform,graphic.canvas,out bounds)) continue;
            Vector2 point=visible.center;
            if(!bounds.Contains(point)) continue;
            var data=new UnityEngine.EventSystems.PointerEventData(system); data.position=point;
            var hits=new List<UnityEngine.EventSystems.RaycastResult>(); system.RaycastAll(data,hits);
            if(hits.Count==0 || UnityEngine.EventSystems.ExecuteEvents.GetEventHandler<UnityEngine.EventSystems.IPointerClickHandler>(hits[0].gameObject)!=button.gameObject) continue;
            // Opaque runtime identity only. No object names, callbacks or hidden game state.
            ViewRect item=Item(bounds,playback==null?"":PlaybackDisplay.Label(speedUI,button)); item.panel="input_target";
            item.target_id=button.GetInstanceID().ToString(); item.input_verified=true;
            item.interactable=true; item.hit_x=point.x; item.hit_y=Screen.height-point.y;
            buttons.Add(item);
        }
    }
    public void Capture(List<ViewRect> texts, List<ViewRect> buttons, List<string> gauges) {
        if(speedUI==null) speedUI=UnityEngine.Object.FindObjectOfType<PlaySpeedSettingUI>();
        rejected.Clear(); candidates=accepted=energyCount=agentCount=creatureCount=hudCount=0;
        readTexts.Clear(); panelCounts.Clear();
        graphics.Clear(); rectangles.Clear(); effects.Clear(); rejectionDetails.Clear(); unsafeEffects=false;
        foreach(Camera cam in Camera.allCameras) foreach(MonoBehaviour effect in cam.GetComponents<MonoBehaviour>()) {
            if (effect==null || !effect.isActiveAndEnabled) continue;
            var method=effect.GetType().GetMethod("OnRenderImage",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic);
            if (method==null) continue;
            // Normal world-camera filters precede the separate UI camera. World HUD is withheld below.
            string name=effect.GetType().Name;
            effects.Add(RobotomyObserver.Quote(cam.name+":"+effect.GetType().FullName));
            if (cam.name=="MainCamera" && (name=="CameraFilterPack_Glow_Glow_Color" || name=="CameraFilterPack_Colors_RgbClamp")) continue;
            unsafeEffects=true;
        }
        foreach(Canvas canvas in UnityEngine.Object.FindObjectsOfType<Canvas>()) {
            // Facility WorldSpace canvases include room decorations and the enormous
            // UnitMouseEventManager hit surface. They are not screen-covering menus.
            // Audited room labels are read directly; only screen UI enters this registry.
            if(!canvas.isActiveAndEnabled || canvas.renderMode==RenderMode.WorldSpace) continue;
            var registered=GraphicRegistry.GetGraphicsForCanvas(canvas);
            // Unity 2017 IndexedSet implements IList indexing, but its enumerator throws.
            for(int index=0;index<registered.Count;index++) {
                Graphic g=registered[index];
                Rect r;
                if(Drawn(g) && GraphicRect(g,out r)) { graphics.Add(g); rectangles[g]=r; }
            }
        }
        CaptureInputTargets(buttons);
        var status=GameStatusUI.GameStatusUI.Window;
        var aw=AgentInfoWindow.currentWindow;
        var cw=CreatureInfoWindow.CurrentWindow;
        energy.Bind(status==null || status.energyContorller==null ? null : status.energyContorller.ActiveControl);
        agent.Bind(aw==null ? null : aw.gameObject);
        creature.Bind(cw==null ? null : cw.gameObject);
        ReadPanel(energy,"energy",texts,buttons);
        ReadPanel(agent,"agent",texts,buttons);
        ReadPanel(creature,"creature",texts,buttons);
        IList<ConsolePanels.Entry> additional=displayPanels.Capture();
        var retained=new HashSet<GameObject>();
        foreach(var entry in additional) {
            if(entry.root==null) continue;
            retained.Add(entry.root);
            Panel panel;
            if(!extraPanels.TryGetValue(entry.root,out panel)) { panel=new Panel(); extraPanels[entry.root]=panel; }
            panel.Bind(entry.root); ReadPanel(panel,entry.source,texts,buttons);
        }
        ConsoleReading.Capture(this,texts,buttons);
        ConsoleNarrative.Capture(this,texts);
        CaptureCommandTargets(texts,buttons);
        CommandWindowReading.Capture(this,buttons);
        CapturePlayback(texts);
        ConsoleScreen.Capture(this,texts,buttons);
        var expired=new List<GameObject>();
        foreach(var root in extraPanels.Keys) if(root==null || !retained.Contains(root)) expired.Add(root);
        foreach(var root in expired) extraPanels.Remove(root);
        if(status!=null && status.energyContorller!=null) Gauge(status.energyContorller.EnergyFill,"energy",gauges);
        if(Time.realtimeSinceStartup-hudRefresh>=1) { hud=UnityEngine.Object.FindObjectsOfType<InGameUI.AgentUI>(); hudRefresh=Time.realtimeSinceStartup; }
        foreach(var h in hud) if(h!=null && Active(h.ActiveControl)) {
            Gauge(h.HpFill,"agent_hp_bar",gauges); Gauge(h.MentalFill,"agent_mental_bar",gauges);
        }
    }
    void Gauge(Image image,string role,List<string> gauges) {
        Rect r; if(image==null || !Visible(image,out r)) return;
        if(image.canvas.renderMode==RenderMode.WorldSpace || image.canvas.worldCamera==Camera.main) { Reject("world_render_unverified"); return; }
        if(image.type!=Image.Type.Filled || image.fillMethod!=Image.FillMethod.Horizontal) return;
        int pixels=Math.Max(1,(int)Math.Round(r.width));
        int filled=(int)Math.Round(Mathf.Clamp01(image.fillAmount)*pixels);
        gauges.Add("{\"role\":"+RobotomyObserver.Quote(role)+",\"x\":"+RobotomyObserver.Number(r.x)+",\"y\":"+RobotomyObserver.Number(Screen.height-r.yMax)+
            ",\"width\":"+RobotomyObserver.Number(r.width)+",\"height\":"+RobotomyObserver.Number(r.height)+",\"filled_pixels\":"+filled+",\"total_pixels\":"+pixels+"}");
        hudCount++;
    }
    public string Diagnostics() {
        List<string> reasons=new List<string>(); foreach(var pair in rejected) reasons.Add(RobotomyObserver.Quote(pair.Key)+":"+pair.Value);
        List<string> counts=new List<string>(); foreach(var pair in panelCounts) counts.Add(RobotomyObserver.Quote(pair.Key)+":"+pair.Value);
        return "{\"candidates\":"+candidates+",\"accepted\":"+accepted+",\"energy\":"+energyCount+",\"agent\":"+agentCount+",\"creature\":"+creatureCount+",\"panels\":{"+String.Join(",",counts.ToArray())+"},\"gauges\":"+hudCount+",\"rejected\":{"+String.Join(",",reasons.ToArray())+"},\"effects\":["+String.Join(",",effects.ToArray())+"],\"rejection_details\":["+String.Join(",",rejectionDetails.ToArray())+"]}";
    }

    // Reuse this frame's graphics registry; no second UI traversal for motion.
    bool ClearPauseCover(Graphic graphic,Rect box,Rect target) {
        var pause=graphic as Image;
        return speedUI!=null && pause==speedUI.pauseFilter &&
            (pause.sprite==speedUI.pauseDefSprite || pause.sprite==speedUI.observeSprite) &&
            coverAlpha.ClearOver(pause,box,target);
    }
    public string MotionCover(Rect bounds, Transform body) {
        // Device pointer does not hide the game surface it annotates.
        foreach(var pair in rectangles) if(bounds.Overlaps(pair.Value)) {
            if(ClearPauseCover(pair.Key,pair.Value,bounds))continue;
            string path=pair.Key.name; for(Transform p=pair.Key.transform.parent;p!=null;p=p.parent) path=p.name+"/"+path;
            return path+" body="+bounds+" graphic="+pair.Value;
        }
        return "";
    }
}
