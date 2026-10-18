using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

// Engineering fixture only. Typed display objects use synthetic strings and never Initialize(),
// buy research, bind a model, register an input handler, or modify save data.
// Decompiled lifecycle audit: CreatureInfoController/KitStat/Open/EquipmentRoot have no
// Unity lifecycle callbacks; KitDataSlot.Start is empty and Update only runs with positionRef.
// All typed components are disabled immediately, with positionRef left null.
public sealed class DisclosureProbe : MonoBehaviour
{
    GameObject root;
    string output;
    bool oldProbe,cleaned,finished;
    readonly List<string> results = new List<string>();
    public void Begin(string directory) {
        output=directory; oldProbe=ConsoleMotion.ProbeActive; ConsoleMotion.ProbeActive=true;
        StartCoroutine(GuardedRun());
    }
    IEnumerator GuardedRun() {
        IEnumerator run=Run();
        while(true) {
            bool next=false; Exception failure=null;
            try { next=run.MoveNext(); } catch(Exception error) { failure=error; }
            if(failure!=null) { Finish(failure.ToString()); yield break; }
            if(!next) yield break;
            yield return run.Current;
        }
    }
    GameObject Group(Transform parent,string name,Vector2 position) {
        var go=new GameObject(name,typeof(RectTransform));go.transform.SetParent(parent,false);
        var rect=go.GetComponent<RectTransform>();rect.anchorMin=rect.anchorMax=rect.pivot=Vector2.zero;
        rect.anchoredPosition=position;rect.sizeDelta=new Vector2(360,150);return go;
    }
    Text Label(Transform parent,string text,Vector2 position) {
        var go=Group(parent,"SyntheticDisclosureLabel",position);go.AddComponent<CanvasRenderer>();
        var label=go.AddComponent<Text>();label.font=Resources.GetBuiltinResource<Font>("Arial.ttf");
        label.text=text;label.fontSize=18;label.color=Color.white;label.raycastTarget=false;
        label.rectTransform.sizeDelta=new Vector2(340,40);return label;
    }
    GameObject Cover(Transform parent) {
        var go=Group(parent,"SyntheticDisclosureCover",Vector2.zero);go.AddComponent<CanvasRenderer>();
        var image=go.AddComponent<Image>();image.color=Color.black;image.raycastTarget=false;return go;
    }
    void Check(string name,Text label,bool expected,bool screenshot) {
        var reader=new ConsoleUI();reader.Capture(new List<ViewRect>(),new List<ViewRect>(),new List<string>());
        Rect bounds;bool actual=reader.Visible(label,out bounds);string imageFile="";
        if(screenshot) {
            imageFile="disclosure-probe-"+name+".png";
            var image=new Texture2D(Screen.width,Screen.height,TextureFormat.RGB24,false);
            try {
                image.ReadPixels(new Rect(0,0,Screen.width,Screen.height),0,0,false);image.Apply(false);
                File.WriteAllBytes(Path.Combine(output,imageFile),image.EncodeToPNG());
            } finally { Destroy(image); }
        }
        results.Add("{\"case\":"+RobotomyObserver.Quote(name)+",\"expected\":"+(expected?"true":"false")+
            ",\"actual\":"+(actual?"true":"false")+",\"passed\":"+(expected==actual?"true":"false")+
            ",\"policy_reason\":"+RobotomyObserver.Quote(ConsoleDisclosure.RejectReason(label.transform)??"")+
            ",\"frame\":"+RobotomyObserver.Quote(imageFile)+",\"diagnostics\":"+reader.Diagnostics()+"}");
    }
    T Slot<T>(Transform parent) where T:CreatureInfo.EquipSlot,new() {
        var slot=new T();slot.ActiveControl=Group(parent,"SyntheticEquipSlot",Vector2.zero);
        slot.BlockControl=Cover(slot.ActiveControl.transform);return slot;
    }
    IEnumerator Run() {
        root=new GameObject("RobotomySyntheticDisclosure",typeof(RectTransform),typeof(Canvas));
        var canvas=root.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceOverlay;canvas.sortingOrder=32760;
        var plain=Label(root.transform,"SYNTHETIC DISPLAY CONTROL",new Vector2(50,350));
        yield return new WaitForEndOfFrame();Check("plain_visible",plain,true,false);plain.gameObject.SetActive(false);

        var group=Group(root.transform,"SyntheticKitIdentity",new Vector2(50,150));
        var kit=group.AddComponent<CreatureInfo.CreatureInfoKitStatRoot>();kit.enabled=false;
        var value=Label(group.transform,"SYNTHETIC HIDDEN IDENTITY",new Vector2(10,20));
        var cover=Cover(group.transform);kit.Open=cover.AddComponent<CreatureInfo.CreatureInfoKitOpenArea>();kit.Open.enabled=false;
        var threshold=Label(cover.transform,"Unlock after 5 uses (fixture)",new Vector2(10,70));kit.Open.costText=threshold;
        yield return new WaitForEndOfFrame();Check("kit_identity_locked",value,false,true);Check("kit_threshold_visible",threshold,true,false);
        cover.SetActive(false);
        yield return new WaitForEndOfFrame();Check("kit_identity_unlocked",value,true,true);
        cover.SetActive(true);
        yield return new WaitForEndOfFrame();Check("kit_identity_relocked",value,false,false);
        cover.SetActive(false);kit.Open=null;
        yield return new WaitForEndOfFrame();Check("kit_missing_cover_withheld",value,false,false);group.SetActive(false);

        group=Group(root.transform,"SyntheticKitRecord",new Vector2(50,150));
        var row=group.AddComponent<CreatureInfo.CreatureInfoKitDataSlot>();row.enabled=false;
        value=Label(group.transform,"SYNTHETIC HIDDEN RECORD",new Vector2(10,20));row.Left_RecordText=value;
        row.disabled=Cover(group.transform);threshold=Label(row.disabled.transform,"Unlock after 10 uses (fixture)",new Vector2(10,70));row.needCostText=threshold;
        yield return new WaitForEndOfFrame();Check("kit_record_locked",value,false,true);Check("kit_record_threshold_visible",threshold,true,false);
        row.disabled.SetActive(false);
        yield return new WaitForEndOfFrame();Check("kit_record_unlocked",value,true,true);group.SetActive(false);

        group=Group(root.transform,"SyntheticEquipment",new Vector2(50,150));
        var equipment=group.AddComponent<CreatureInfo.CreatureInfoEquipmentRoot>();equipment.enabled=false;
        equipment.giftSlot=Slot<CreatureInfo.GiftSlot>(group.transform);equipment.giftSlot.ActiveControl.SetActive(false);
        equipment.armorSlot=Slot<CreatureInfo.ArmorSlot>(group.transform);equipment.armorSlot.ActiveControl.SetActive(false);
        equipment.weaponSlot=Slot<CreatureInfo.WeaponSlot>(group.transform);
        value=Label(equipment.weaponSlot.ActiveControl.transform,"SYNTHETIC HIDDEN WEAPON",new Vector2(10,20));
        // Keep the sibling cover in front of the just-created content label.
        cover=equipment.weaponSlot.BlockControl;cover.transform.SetAsLastSibling();
        threshold=Label(cover.transform,"Observation level 4 (fixture)",new Vector2(10,70));equipment.weaponSlot.BlockText=threshold;
        yield return new WaitForEndOfFrame();Check("equipment_locked",value,false,true);Check("equipment_threshold_visible",threshold,true,false);
        cover.SetActive(false);
        yield return new WaitForEndOfFrame();Check("equipment_unlocked",value,true,true);
        equipment.weaponSlot.BlockControl=null;
        yield return new WaitForEndOfFrame();Check("equipment_missing_cover_withheld",value,false,false);
        equipment.weaponSlot.BlockControl=cover;group.SetActive(false);
        yield return new WaitForEndOfFrame();Check("closed_ancestor_withheld",value,false,false);
        Finish("");
    }
    void Finish(string error) {
        if(finished)return;finished=true;
        try {
            File.WriteAllText(Path.Combine(output,"disclosure-probe.json"),"{\"at_utc\":"+RobotomyObserver.Quote(DateTime.UtcNow.ToString("o"))+
                ",\"basis\":\"synthetic_typed_UI_in_actual_Unity_not_progression_gameplay\",\"error\":"+RobotomyObserver.Quote(error)+
                ",\"not_exercised\":[\"real_research_unlocks\",\"real_tool_usage\",\"command_window_lifecycle\"],\"cases\":["+String.Join(",",results.ToArray())+"]}");
        } finally { Cleanup();StartCoroutine(FinishAfterCleanFrame()); }
    }
    IEnumerator FinishAfterCleanFrame() {
        yield return new WaitForEndOfFrame();ConsoleMotion.ProbeActive=oldProbe;Destroy(this);
    }
    void Cleanup() { if(cleaned)return;cleaned=true;if(root!=null){root.SetActive(false);Destroy(root);} }
    void OnDestroy() { Cleanup();ConsoleMotion.ProbeActive=oldProbe; }
}
