using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Web.Script.Serialization;

// Executes the production worker against a temporary folder, no Unity/game input.
public static class HistoryHarness {
    static readonly JavaScriptSerializer json=new JavaScriptSerializer();
    static Dictionary<string,object> Read(string folder) {
        return json.Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(folder,"history/index.json")));
    }
    static object[] Rows(string folder) {
        var rows=(IEnumerable)Read(folder)["records"]; var result=new List<object>();
        foreach(var row in rows) result.Add(row); return result.ToArray();
    }
    static void Assert(bool value,string message) { if(!value) throw new Exception(message); }
    static void Wait(string folder,int sequence) {
        for(int i=0;i<300;i++) {
            try { var rows=Rows(folder); if(rows.Length>0 && Convert.ToInt32(((Dictionary<string,object>)rows[rows.Length-1])["sequence"])==sequence) return; }
            catch(IOException) {} Thread.Sleep(10);
        }
        throw new Exception("Publication timeout "+sequence);
    }
    public static void Main(string[] args) {
        try { Test(args); } catch(Exception ex) { Console.WriteLine(ex.GetType().Name+": "+ex.Message); Environment.Exit(1); }
    }
    static void Test(string[] args) {
        string folder=args[0]; Directory.CreateDirectory(folder);
        using(var history=new ConsoleHistory(folder,new string('a',32),3,2)) {
            for(int i=1;i<=5;i++) { history.Offer(i,i,"{}",new byte[]{(byte)i}); Wait(folder,i); }
            var rows=Rows(folder);
            Assert(rows.Length==3,"count cap");
            Assert(Convert.ToInt32(((Dictionary<string,object>)rows[0])["sequence"])==3,"oldest eviction");
            Assert(!(bool)((Dictionary<string,object>)rows[0])["has_frame"],"independent frame overwrite");
            Assert(Directory.GetFiles(Path.Combine(folder,"history"),"sample-*.json").Length==3,"sample file cap");
            Assert(Directory.GetFiles(Path.Combine(folder,"history"),"frame-*.png").Length==2,"frame file cap");
            string before=File.ReadAllText(Path.Combine(folder,"history/index.json"));
            Thread.Sleep(200); Assert(before==File.ReadAllText(Path.Combine(folder,"history/index.json")),"no age deletion when idle");
            history.Offer(100,100,"{}",null); Wait(folder,100);
            rows=Rows(folder); Assert(rows.Length==3,"pause gap must not collide slots");
            Assert(Convert.ToInt32(((Dictionary<string,object>)rows[0])["sequence"])==4,"accepted counter slots");
            // Force the next sample write to fail after invalidation. The manifest
            // must retain only readable old records even if no later sample arrives.
            string blocked=Path.Combine(folder,"history/sample-0.json");
            using(var locked=new FileStream(blocked,FileMode.Open,FileAccess.Read,FileShare.None)) {
                history.Offer(101,101,"{}",null);
                for(int i=0;i<300 && history.Errors==0;i++) Thread.Sleep(10);
                Assert(history.Errors==1,"forced disk failure");
                foreach(Dictionary<string,object> row in Rows(folder)) Assert(Convert.ToInt32(row["slot"])!=0,"failed slot not advertised");
            }
        }
        using(var restarted=new ConsoleHistory(folder,new string('b',32),1,1)) {
            Assert(Rows(folder).Length==0,"session reset");
            Assert(Directory.GetFiles(Path.Combine(folder,"history"),"sample-*.json").Length==0,"old owned files removed");
            restarted.Offer(1,1,"{}",new byte[]{1}); Wait(folder,1);
        }
        string latest=Path.Combine(folder,"latest.txt");
        using(var publisher=new ConsolePublisher()) {
            for(int i=0;i<200;i++) publisher.Text(latest,i.ToString(),false);
            for(int i=0;i<300;i++) {
                try { if(File.ReadAllText(latest)=="199") break; } catch(IOException) {}
                Thread.Sleep(10);
            }
            Assert(File.ReadAllText(latest)=="199","latest wins under burst");
            Assert(publisher.Coalesced>0,"pending replacements coalesced");
            Assert(publisher.Dropped==0,"latest updates not dropped");
        }
        Console.WriteLine("Production history worker: rollover, frame association, pause gap, idle retention, disk failure, restart passed");
    }
}
