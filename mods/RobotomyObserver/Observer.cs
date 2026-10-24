using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Globalization;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.SceneManagement;

// BaseMod's loader convention. Only the isolated copy installs virtual input.
public class Harmony_Patch
{
    public Harmony_Patch()
    {
        if (GameObject.Find("RobotomyReadOnlyObserver") != null) return;
        GameObject go = new GameObject("RobotomyReadOnlyObserver");
        UnityEngine.Object.DontDestroyOnLoad(go);
        go.AddComponent<RobotomyObserver>();
    }
}

[Serializable] public class ViewRect { public string text, panel, target_id, row_id, role, subject_ref; public bool input_verified; public float hit_x, hit_y; public float x, y, width, height; public bool interactable; }
[Serializable] public class ViewSize { public int width, height; }
[Serializable] public class IsolationInfo { public string persistent_data_path, company_name, product_name; }
[Serializable] public class Observation
{
    public int schema_version = 1;
    public string environment = "lobotomy_live";
    public bool read_only = true;
    public string captured_at_utc;
    public int process_id, sequence;
    public string scene;
    public ViewSize screen;
    public IsolationInfo isolation;
    public ViewRect[] ui_texts, buttons;
}

public class RobotomyObserver : MonoBehaviour
{
    private string output;
    private int sequence;
    private Texture2D frame;
    private readonly ConsoleUI ui = new ConsoleUI();
    private readonly ConsoleMotion motion = new ConsoleMotion();
    private readonly ConsoleFacilityMap facility = new ConsoleFacilityMap();
    private float nextFrame;
    private byte[] storyPixels;
    private byte[] storyPng;
    private string storyHash;
    private string previousFrameScene;
    private string storyKey;
    private float storyRefresh;
    private double frameMs;
    private int frameSequence;
    private string frameTimestamp = "";
    private string session;
    private ConsolePublisher publisher;
    private ConsoleHistory history;
    private System.Diagnostics.Stopwatch costs = new System.Diagnostics.Stopwatch();
    private IEnumerator Start()
    {
        output = Environment.GetEnvironmentVariable("ROBOTOMY_OBSERVATION_DIR");
        string expected = Environment.GetEnvironmentVariable("ROBOTOMY_EXPECTED_SAVE_PATH");
        if (Application.companyName != "Robotomy_AI" || Application.productName != "Lobotomy_Observer"
            || String.IsNullOrEmpty(output) || String.IsNullOrEmpty(expected)
            || !String.Equals(Path.GetFullPath(expected).TrimEnd('\\', '/'),
                Path.GetFullPath(Application.persistentDataPath).TrimEnd('\\', '/'), StringComparison.OrdinalIgnoreCase))
        {
            Debug.LogError("Robotomy isolation guard rejected this runtime.");
            Application.Quit();
            yield break;
        }
        Directory.CreateDirectory(output);
        try { RobotomyVirtualInput.Install(output); }
        catch (Exception ex) { Debug.LogError("Robotomy virtual input unavailable: " + ex); Application.Quit(); yield break; }
        gameObject.AddComponent<RobotomyVirtualInput>();
        session = Guid.NewGuid().ToString("N");
        publisher = new ConsolePublisher();
        try { history = new ConsoleHistory(output,session,
            ConsoleHistory.Capacity("ROBOTOMY_HISTORY_SAMPLES",300,600),
            ConsoleHistory.Capacity("ROBOTOMY_HISTORY_FRAMES",30,60)); }
        catch(Exception ex) { Debug.LogError("Robotomy history disabled; latest observation continues: "+ex); }
        ConsoleAudio.Install();
        ConsoleSignals.Install();
        try { ConsoleCombat.Install(); var errorPath=Path.Combine(output,"combat-startup-error.txt");if(File.Exists(errorPath))File.Delete(errorPath); }
        catch(Exception ex) { File.WriteAllText(Path.Combine(output,"combat-startup-error.txt"),ex.ToString()); throw; }
        MotionCanvasGeometry.Install();
        ConsoleMotion.Initialize(output);
        facility.Initialize(output);
        Application.runInBackground = true;
        Debug.Log("Robotomy read-only observer ready: " + Application.persistentDataPath);
        float nextSample=0;
        while (true)
        {
            yield return new WaitForEndOfFrame();
            try { ConsoleCombat.PollFrame(ui); } catch(Exception ex) { Debug.LogError("Combat observation: "+ex); }
            if(Time.realtimeSinceStartup<nextSample) continue;
            nextSample=Time.realtimeSinceStartup+.1f;
            try { Capture(); }
            catch (Exception ex) { Debug.LogError("Robotomy capture: " + ex); }
        }
    }

    public static string Quote(string text)
    {
        StringBuilder result = new StringBuilder("\"");
        foreach (char c in text)
        {
            if (c == '\\' || c == '"') result.Append('\\').Append(c);
            else if (c < 32 || Char.IsSurrogate(c)) result.Append("\\u").Append(((int)c).ToString("x4"));
            else result.Append(c);
        }
        return result.Append('"').ToString();
    }

    public static string Number(float value) { return value.ToString("R", CultureInfo.InvariantCulture); }
    private static string Items(ViewRect[] items, bool buttons)
    {
        List<string> result = new List<string>();
        foreach (ViewRect item in items)
            result.Add("{\"panel\":" + Quote(item.panel ?? "") + ",\"text\":" + Quote(item.text) + ",\"x\":" + Number(item.x) + ",\"y\":" + Number(item.y)
                + ",\"row_id\":" + Quote(item.row_id ?? "") + ",\"role\":" + Quote(item.role ?? "")
                + ",\"subject_ref\":" + Quote(item.subject_ref ?? "")
                + ",\"width\":" + Number(item.width) + ",\"height\":" + Number(item.height)
                + (buttons ? ",\"target_id\":" + Quote(item.target_id ?? "") + ",\"input_verified\":" + (item.input_verified ? "true" : "false") + ",\"hit_x\":" + Number(item.hit_x) + ",\"hit_y\":" + Number(item.hit_y) : "")
                + (buttons ? ",\"interactable\":" + (item.interactable ? "true" : "false") : "") + "}");
        return "[" + String.Join(",", result.ToArray()) + "]";
    }

    private static string Serialize(Observation o)
    {
        // Older Unity JsonUtility omits nested types from this dynamically loaded mod assembly.
        return "{\"schema_version\":1,\"environment\":\"lobotomy_live\",\"read_only\":true,\"captured_at_utc\":"
            + Quote(o.captured_at_utc) + ",\"process_id\":" + o.process_id + ",\"sequence\":" + o.sequence
            + ",\"scene\":" + Quote(o.scene) + ",\"screen\":{\"width\":" + o.screen.width + ",\"height\":" + o.screen.height
            + "},\"isolation\":{\"persistent_data_path\":" + Quote(o.isolation.persistent_data_path)
            + ",\"company_name\":" + Quote(o.isolation.company_name) + ",\"product_name\":" + Quote(o.isolation.product_name)
            + "},\"ui_texts\":" + Items(o.ui_texts, false) + ",\"buttons\":" + Items(o.buttons, true) + "}";
    }

    private void Capture()
    {
        string probe=Path.Combine(output,"run-visibility-probe");
        if(File.Exists(probe) && GetComponent<ConsoleProbe>()==null) {
            File.Delete(probe); gameObject.AddComponent<ConsoleProbe>().Begin(output);
        }
        string motionProbe=Path.Combine(output,"run-motion-probe");
        if(File.Exists(motionProbe) && GetComponent<MotionProbe>()==null) {
            File.Delete(motionProbe); gameObject.AddComponent<MotionProbe>().Begin(output);
        }
        string targetsProbe=Path.Combine(output,"run-motion-targets-probe");
        if(File.Exists(targetsProbe) && !ConsoleMotion.ProbeActive && GetComponent<MotionTargetsProbe>()==null) {
            File.Delete(targetsProbe); gameObject.AddComponent<MotionTargetsProbe>().Begin(output);
        }
        string disclosureProbe=Path.Combine(output,"run-disclosure-probe");
        if(File.Exists(disclosureProbe) && !ConsoleMotion.ProbeActive && GetComponent<ConsoleProbe>()==null && GetComponent<DisclosureProbe>()==null) {
            File.Delete(disclosureProbe); gameObject.AddComponent<DisclosureProbe>().Begin(output);
        }
        costs.Reset(); costs.Start();
        List<ViewRect> texts = new List<ViewRect>(), buttons = new List<ViewRect>();
        List<string> gauges = new List<string>();
        ui.Capture(texts, buttons, gauges);
        double uiMs = costs.Elapsed.TotalMilliseconds;
        ConsoleAudio.Reconcile();
        double audioMs = costs.Elapsed.TotalMilliseconds-uiMs;
        string facilityMap=facility.Capture(ui);
        motion.Capture(ui);
        ConsoleCombat.Sample(ui);
        string hazards=ConsoleHazards.Capture(ui);
        if(facility.PendingSave!=null){publisher.Text(facility.PathName,facility.PendingSave,false);facility.PendingSave=null;}
        double motionMs = motion.Milliseconds;
        Observation observation = new Observation {
            captured_at_utc = DateTime.UtcNow.ToString("o"), process_id = System.Diagnostics.Process.GetCurrentProcess().Id,
            sequence = ++sequence, scene = SceneManager.GetActiveScene().name,
            screen = new ViewSize { width = Screen.width, height = Screen.height },
            isolation = new IsolationInfo { persistent_data_path = Application.persistentDataPath,
                company_name = Application.companyName, product_name = Application.productName },
            ui_texts = texts.ToArray(), buttons = buttons.ToArray()
        };
        int unityFrame = Time.frameCount;
        string body = Serialize(observation);
        body = body.Substring(0,body.Length-1) + ",\"console\":{\"version\":1,\"session\":"+Quote(session)+
            ",\"unity_frame\":"+unityFrame+",\"policy\":\"conservative_display_v1\",\"valid_for_ms\":750,"+
            "\"audio_basis\":\"playback_state_approximation\",\"audio_dropped\":"+ConsoleAudio.Dropped+
            ",\"signal_epoch\":"+ConsoleSignals.Epoch+",\"signals\":"+ConsoleSignals.Capture(ui)+",\"facility_map\":"+facilityMap+",\"hazards\":"+hazards+",\"gauges\":["+String.Join(",",gauges.ToArray())+"],\"audio_events\":"+ConsoleAudio.Snapshot()+",\"dead_employees\":"+ConsoleEmployee.DeadRoster()+",\"motion\":"+motion.Snapshot+"}}";
        body=body.Substring(0,body.Length-2)+",\"combat\":"+ConsoleCombat.Snapshot()+",\"appearance\":"+ConsoleAppearance.Capture(ui)+"}}";
        publisher.Text(Path.Combine(output, "latest.json"), body, false);
        string combat=ConsoleCombat.Drain();
        if(combat.Length>0)publisher.Text(Path.Combine(output,"combat-"+session+".jsonl"),combat,true);
        string audio=ConsoleAudio.Drain();
        if(audio.Length>0) publisher.Text(Path.Combine(output,"audio-"+session+".jsonl"),audio,true);
        double publishMs=costs.Elapsed.TotalMilliseconds-uiMs-audioMs-motionMs;
        bool captured=false;
        byte[] historyPng=null;
        bool storyScene=observation.scene.StartsWith("Story",StringComparison.Ordinal);
        string currentStoryKey=storyScene?ConsoleNarrative.FrameKey(observation.ui_texts):null;
        bool narrativeChange=storyScene && (previousFrameScene!=observation.scene || currentStoryKey!=storyKey);
        string requestPath=Path.Combine(output,"frame-request.txt");
        bool frameRequested=File.Exists(requestPath);
        if(frameRequested)try{File.Delete(requestPath);}catch{}
        if(frameRequested || (Time.realtimeSinceStartup>=nextFrame &&
           (narrativeChange || !storyScene || Time.realtimeSinceStartup>=storyRefresh))) {
            double before=costs.Elapsed.TotalMilliseconds;
            if(frame==null || frame.width!=Screen.width || frame.height!=Screen.height) {
                if(frame!=null) UnityEngine.Object.Destroy(frame);
                frame=new Texture2D(Screen.width,Screen.height,TextureFormat.RGB24,false);
            }
            frame.ReadPixels(new Rect(0,0,Screen.width,Screen.height),0,0,false);
            // CPU EncodeToPNG consumes ReadPixels data; no redundant GPU upload via Apply.
            bool story=observation.scene.StartsWith("Story",StringComparison.Ordinal);
            byte[] pixels=story?frame.GetRawTextureData():null;
            bool same=story && previousFrameScene==observation.scene && SamePixels(storyPixels,pixels);
            byte[] png=same?storyPng:frame.EncodeToPNG();
            historyPng=same || (story && !narrativeChange && !frameRequested)?null:png;
            if(!same) publisher.Put(Path.Combine(output,"frame.png"),png,false);
            frameSequence=unityFrame; frameTimestamp=observation.captured_at_utc;
            string hash;
            if(same) hash=storyHash;
            else using(var sha=System.Security.Cryptography.SHA256.Create()) hash=BitConverter.ToString(sha.ComputeHash(png)).Replace("-","").ToLowerInvariant();
            storyPixels=pixels; storyPng=story?png:null; storyHash=story?hash:null;
            previousFrameScene=observation.scene;
            storyKey=currentStoryKey;
            // Stable dialogue: inspect again within three seconds for effects not
            // represented by UI strings/sprites. Transitions still sample at 1 Hz.
            bool hasDialogue=false;
            foreach(var t in observation.ui_texts)if(t.panel=="story" && (t.role=="dialogue" || t.role=="narration" || t.role=="letter"))hasDialogue=true;
            storyRefresh=Time.realtimeSinceStartup+(hasDialogue?3f:1f);
            publisher.Text(Path.Combine(output,"frame-motion.json"),"{\"session\":"+Quote(session)+",\"unity_frame\":"+unityFrame+",\"sha256\":"+Quote(hash)+",\"snapshot\":"+body+"}",false);
            publisher.Text(Path.Combine(output,"frame-meta.json"),"{\"session\":"+Quote(session)+
                ",\"process_id\":"+observation.process_id+",\"scene\":"+Quote(observation.scene)+",\"unity_frame\":"+unityFrame+
                ",\"captured_at_utc\":"+Quote(frameTimestamp)+",\"sha256\":"+Quote(hash)+"}",false);
            frameMs=costs.Elapsed.TotalMilliseconds-before;
            nextFrame=Time.realtimeSinceStartup+1f; captured=true;
        }
        // TutorialPause can change GameState without changing timeScale. This
        // device-only gate never exports pause callers or hidden boss flags.
        bool historyActive=GameManager.currentGameManager!=null &&
            GameManager.currentGameManager.state==GameState.PLAYING && Time.timeScale>0f;
        bool storyChanged=observation.scene.StartsWith("Story",StringComparison.Ordinal) && historyPng!=null;
        if(history!=null && (storyChanged || (historyActive && !observation.scene.StartsWith("Story",StringComparison.Ordinal))) && !ConsoleMotion.ProbeActive && GetComponent<ConsoleProbe>()==null)
            history.Offer(observation.sequence,unityFrame,body,historyPng);
        string diagnostics="{\"appearance_ms\":"+Number((float)ConsoleAppearance.Milliseconds)+",\"at_utc\":"+Quote(DateTime.UtcNow.ToString("o"))+",\"session\":"+Quote(session)+
            ",\"process_id\":"+observation.process_id+",\"scene\":"+Quote(observation.scene)+",\"unity_frame\":"+unityFrame+
            ",\"ui_ms\":"+uiMs.ToString("R",CultureInfo.InvariantCulture)+",\"audio_ms\":"+audioMs.ToString("R",CultureInfo.InvariantCulture)+
            ",\"motion_ms\":"+motionMs.ToString("R",CultureInfo.InvariantCulture)+",\"motion\":"+motion.Diagnostics()+
            ",\"publish_ms\":"+publishMs.ToString("R",CultureInfo.InvariantCulture)+",\"capture_ms\":"+(captured?frameMs:0).ToString("R",CultureInfo.InvariantCulture)+
            ",\"game_frame_ms\":"+Number(Time.unscaledDeltaTime*1000)+",\"audio_patched\":"+ConsoleAudio.Patched+
            ",\"audio_failures\":"+ConsoleAudio.Failures+",\"publication_dropped\":"+publisher.Dropped+",\"publication_errors\":"+publisher.Errors+",\"publication_coalesced\":"+publisher.Coalesced+
            ",\"history_active\":"+(historyActive?"true":"false")+",\"history_count\":"+(history==null?0:history.Count)+",\"history_frames\":"+(history==null?0:history.FrameCount)+
            ",\"history_dropped\":"+(history==null?0:history.Dropped)+",\"history_errors\":"+(history==null?-1:history.Errors)+
            ",\"last_disk_write_ms\":"+publisher.LastWriteMs.ToString("R",CultureInfo.InvariantCulture)+",\"ui\":"+ui.Diagnostics()+"}";
        publisher.Text(Path.Combine(output,"console-diagnostics.json"),diagnostics,false);
        publisher.Text(Path.Combine(output,"metrics-"+session+".jsonl"),diagnostics+"\n",true);
    }

    private static bool SamePixels(byte[] a,byte[] b) {
        if(a==null || b==null || a.Length!=b.Length)return false;
        for(int i=0;i<a.Length;i++)if(a[i]!=b[i])return false;
        return true;
    }

    // Save identity is shown in the observer page/window title. No banner obscures the energy HUD.
    private void OnDestroy() { if (frame != null) UnityEngine.Object.Destroy(frame); if(history!=null) history.Dispose(); if(publisher!=null) publisher.Dispose(); }
}
