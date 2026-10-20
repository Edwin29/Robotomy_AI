using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

// Final UI references only. Never reads _nextOrdeal, overload model counters,
// room model timers or creature identities. Units/labels match the visible HUD.
public static class ConsoleHazards {
    static string Q(string s){return RobotomyObserver.Quote(s);}
    static string N(float v){return RobotomyObserver.Number(v);}
    static string Text(ConsoleUI ui,Text t,bool world=false){Rect r;if(t==null || !(world?ui.VisibleWorldLabel(t,out r):ui.Visible(t,out r)) || String.IsNullOrEmpty(t.text) || t.cachedTextGenerator.characterCountVisible<t.text.Length)return null;return t.text;}
    public static string ColorName(Color c){
        Color32 x=c;
        if(Math.Abs(x.r-105)<=2 && Math.Abs(x.g-164)<=2 && Math.Abs(x.b-72)<=2)return "녹빛";
        if(Math.Abs(x.r-159)<=2 && Math.Abs(x.g-104)<=2 && Math.Abs(x.b-234)<=2)return "자색";
        if(Math.Abs(x.r-220)<=2 && Math.Abs(x.g-20)<=2 && Math.Abs(x.b-60)<=2)return "핏빛";
        if(Math.Abs(x.r-254)<=2 && Math.Abs(x.g-150)<=2 && Math.Abs(x.b-11)<=2)return "호박색";
        return "#"+x.r.ToString("X2")+x.g.ToString("X2")+x.b.ToString("X2");
    }
    public static string Capture(ConsoleUI ui){
        string level="null",ordeal="null",gauge="null",rooms="null";
        var status=GameStatusUI.GameStatusUI.Window;
        var e=status==null?null:status.energyContorller;
        if(e!=null){
            string s=Text(ui,e.OverloadLevelText);if(s!=null)level=Q(s);
            s=Text(ui,e.OverLoadIsolateNumText);int count;
            if(s!=null && Int32.TryParse(s,out count) && count>=0)rooms=count.ToString();
            s=Text(ui,e.OverLoadOrdealName);
            if(e.OverLoadOrdealRoot!=null && e.OverLoadOrdealRoot.activeInHierarchy && s!=null){
                Color c=e.OverLoadOrdealName.color*e.OverLoadOrdealName.canvasRenderer.GetColor();
                string color=ColorName(c);
                ordeal="{\"color\":"+Q(color)+",\"stage\":"+Q(s)+",\"label\":"+Q(color+" "+s)+"}";
            }
            // Layout children are the actual displayed slot capacity, including empty slots.
            // Check every slot's projected region. A partially covered bar is unavailable.
            if(e.OverLoadGaugeLayout!=null && e.OverLoadGaugeLayout.activeInHierarchy && level!="null"){
                int total=0,filled=0;bool valid=true;
                foreach(Transform child in e.OverLoadGaugeLayout.transform){
                    var im=child.GetComponent<Image>();Rect r;
                    if(im==null || !ui.VisibleGaugeSlot(im,out r)){valid=false;break;}
                    float a=im.color.a*im.canvasRenderer.GetAlpha();
                    if(a>.99f)filled++;else if(a>.001f){valid=false;break;}
                    total++;
                }
                if(valid && total>0)gauge="{\"filled\":"+filled+",\"max\":"+total+",\"ratio\":"+N((float)filled/total)+",\"label\":"+Q(filled+"/"+total)+"}";
            }
        }
        var timers=new List<string>();
        foreach(var room in UnityEngine.Object.FindObjectsOfType<IsolateRoom>()){
            var t=room.overloadUI;if(t==null)continue;
            var label=t.timerText;int value;Rect rect;
            if(label==null || !ui.VisibleWorldLabel(label,out rect) || String.IsNullOrEmpty(label.text) ||
                label.cachedTextGenerator.characterCountVisible<label.text.Length || !Int32.TryParse(label.text,out value) || value<0)continue;
            string name=Text(ui,room.CreatureName,true);
            timers.Add("{\"room_label\":"+(name==null?"null":Q(name))+",\"seconds\":"+value+",\"x\":"+N(rect.center.x)+",\"y\":"+N(Screen.height-rect.center.y)+"}");
        }
        return "{\"ordeal\":"+ordeal+",\"meltdown_level\":"+level+",\"meltdown_gauge\":"+gauge+",\"target_rooms\":"+rooms+",\"room_timers\":["+String.Join(",",timers.ToArray())+"],\"room_status\":"+ConsoleRoomStatus.Capture(ui)+",\"creature_management\":"+ConsoleRoomStatus.Management(ui)+"}";
    }
}
