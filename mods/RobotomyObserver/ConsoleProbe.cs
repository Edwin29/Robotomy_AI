using System;
using System.IO;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

// Explicit engineer-triggered, transient render tests. No save/model mutations.
// Synthetic controls are never included in the player-facing panel adapters.
public sealed class ConsoleProbe : MonoBehaviour
{
    string output;
    GameObject root;
    ConsoleProbeEffect effect;
    AudioClip clip;
    readonly List<string> results=new List<string>();
    public void Begin(string directory) { output=directory; StartCoroutine(Run()); }
    Text Label(Transform parent,string name,Vector2 pos) {
        var go=new GameObject(name,typeof(RectTransform),typeof(CanvasRenderer),typeof(Text));
        go.transform.SetParent(parent,false);
        var text=go.GetComponent<Text>(); text.font=Resources.GetBuiltinResource<Font>("Arial.ttf");
        text.fontSize=18; text.color=Color.white; text.text="VISIBILITY TEST";
        var rect=text.rectTransform; rect.anchorMin=rect.anchorMax=new Vector2(0,0); rect.pivot=Vector2.zero;
        rect.anchoredPosition=pos; rect.sizeDelta=new Vector2(200,35); return text;
    }
    void Check(string name,Text text,bool expected) {
        var reader=new ConsoleUI(); reader.Capture(new List<ViewRect>(),new List<ViewRect>(),new List<string>());
        Rect rect; bool actual=reader.Visible(text,out rect);
        results.Add("{\"case\":"+RobotomyObserver.Quote(name)+",\"expected\":"+(expected?"true":"false")+
            ",\"actual\":"+(actual?"true":"false")+",\"passed\":"+(actual==expected?"true":"false")+"}");
    }
    void AudioCheck(string name,long before,int expected) {
        long actual=ConsoleAudio.EventSequence-before;
        results.Add("{\"case\":"+RobotomyObserver.Quote(name)+",\"expected_events\":"+expected+",\"actual_events\":"+actual+
            ",\"passed\":"+(actual==expected?"true":"false")+"}");
    }
    IEnumerator Run() {
        root=new GameObject("RobotomyVisibilityProbe",typeof(RectTransform),typeof(Canvas));
        var canvas=root.GetComponent<Canvas>(); canvas.renderMode=RenderMode.ScreenSpaceOverlay; canvas.sortingOrder=32760;
        var text=Label(root.transform,"PublicTestLabel",new Vector2(900,150));
        yield return new WaitForEndOfFrame(); Check("uncovered_positive_control",text,true);
        var cover=new GameObject("SyntheticOpaqueCover",typeof(RectTransform),typeof(CanvasRenderer),typeof(Image));
        cover.transform.SetParent(root.transform,false);
        var cr=cover.GetComponent<RectTransform>(); cr.anchorMin=cr.anchorMax=cr.pivot=Vector2.zero; cr.anchoredPosition=new Vector2(900,150); cr.sizeDelta=new Vector2(200,35);
        cover.GetComponent<Image>().color=Color.black;
        yield return new WaitForEndOfFrame(); Check("opaque_cover",text,false);
        cover.GetComponent<Image>().color=new Color(0,0,0,.5f);
        yield return new WaitForEndOfFrame(); Check("partial_alpha_cover",text,false);
        cover.SetActive(false); text.gameObject.AddComponent<CanvasGroup>().alpha=0;
        yield return new WaitForEndOfFrame(); Check("parent_alpha_zero",text,false);
        text.GetComponent<CanvasGroup>().alpha=1;
        var mask=new GameObject("SyntheticViewport",typeof(RectTransform),typeof(RectMask2D)); mask.transform.SetParent(root.transform,false);
        var mr=mask.GetComponent<RectTransform>(); mr.anchorMin=mr.anchorMax=mr.pivot=Vector2.zero; mr.anchoredPosition=new Vector2(900,150); mr.sizeDelta=new Vector2(100,35);
        text.transform.SetParent(mask.transform,false); text.rectTransform.anchoredPosition=Vector2.zero;
        yield return new WaitForEndOfFrame(); Check("partially_clipped_text",text,false);
        text.transform.SetParent(root.transform,false); text.rectTransform.anchoredPosition=new Vector2(900,150);
        yield return new WaitForEndOfFrame(); Check("uncovered_after_cover_removed",text,true);
        if(Camera.main!=null) {
            effect=Camera.main.gameObject.AddComponent<ConsoleProbeEffect>();
            yield return new WaitForEndOfFrame(); Check("unknown_render_effect",text,false);
            effect.enabled=false; Destroy(effect);
        }
        var source=root.AddComponent<AudioSource>(); source.playOnAwake=false; source.loop=true; source.spatialBlend=0;
        clip=AudioClip.Create("Robotomy_generated_test_tone",4410,1,44100,false);
        float[] samples=new float[4410]; for(int i=0;i<samples.Length;i++) samples[i]=.05f*Mathf.Sin(i*2*Mathf.PI*440/44100);
        clip.SetData(samples,0); source.clip=clip; source.mute=true;
        long before=ConsoleAudio.EventSequence; ConsoleAudio.Calls.Play(source); AudioCheck("muted_play_not_published",before,0); source.Stop();
        source.mute=false; source.volume=.1f;
        before=ConsoleAudio.EventSequence; ConsoleAudio.Calls.Play(source); AudioCheck("play_event",before,1);
        before=ConsoleAudio.EventSequence; ConsoleAudio.Calls.Pause(source); AudioCheck("pause_event",before,1);
        before=ConsoleAudio.EventSequence; ConsoleAudio.Calls.UnPause(source); AudioCheck("resume_event",before,1);
        before=ConsoleAudio.EventSequence; ConsoleAudio.Calls.Stop(source); AudioCheck("stop_event",before,1);
        root.SetActive(false); UnityEngine.Object.Destroy(root);
        File.WriteAllText(Path.Combine(output,"visibility-probe.json"),"{\"at_utc\":"+RobotomyObserver.Quote(DateTime.UtcNow.ToString("o"))+
            ",\"basis\":\"synthetic_UI_and_generated_audio_in_actual_runtime\",\"cases\":["+String.Join(",",results.ToArray())+"]}");
        Destroy(this);
    }
    void OnDestroy() { if(root!=null) Destroy(root); if(effect!=null) Destroy(effect); if(clip!=null) Destroy(clip); }
}

public sealed class ConsoleProbeEffect : MonoBehaviour {
    void OnRenderImage(RenderTexture src,RenderTexture dst) { Graphics.Blit(src,dst); }
}
