using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

// Count-bounded retrospective cache, independent of latest-state publication.
// Only immutable, already filtered observations/encoded pixels cross this worker boundary.
public sealed class ConsoleHistory : IDisposable
{
    sealed class Sample { public int sequence, frame; public string body; public byte[] png; public long bytes; }
    sealed class Record { public int sequence, frame, slot, frameSlot=-1; public string hash; }
    readonly string directory, session;
    readonly int capacity, frameCapacity;
    readonly Queue<Sample> pending=new Queue<Sample>();
    readonly List<Record> records=new List<Record>();
    readonly AutoResetEvent wake=new AutoResetEvent(false);
    readonly Thread worker;
    long pendingBytes, nextSlot, nextFrameSlot;
    bool stopping;
    public int Dropped, Errors, Count, FrameCount;
    const long MaxPendingBytes=64L*1024*1024;
    const int MaxPending=16;

    public ConsoleHistory(string output,string identity,int samples,int frames) {
        if(samples<1 || samples>600 || frames<1 || frames>60) throw new ArgumentOutOfRangeException();
        directory=Path.Combine(output,"history"); session=identity; capacity=samples; frameCapacity=frames;
        Directory.CreateDirectory(directory);
        // Remove only fixed cache slots owned by this component; never user recordings.
        foreach(string path in Directory.GetFiles(directory)) {
            string name=Path.GetFileName(path), stem=name.EndsWith(".tmp")?name.Substring(0,name.Length-4):name;
            int number; bool owned=false;
            if(stem.StartsWith("sample-") && stem.EndsWith(".json")) owned=Int32.TryParse(stem.Substring(7,stem.Length-12),out number) && number>=0 && number<600;
            if(stem.StartsWith("frame-") && stem.EndsWith(".png")) owned=Int32.TryParse(stem.Substring(6,stem.Length-10),out number) && number>=0 && number<60;
            if(owned) File.Delete(path);
        }
        PublishIndex();
        worker=new Thread(Run); worker.IsBackground=true; worker.Name="Robotomy history"; worker.Start();
    }
    public static int Capacity(string variable,int fallback,int maximum) {
        int value; string raw=Environment.GetEnvironmentVariable(variable);
        return Int32.TryParse(raw,out value) && value>=1 && value<=maximum?value:fallback;
    }
    public void Offer(int sequence,int unityFrame,string snapshot,byte[] png) {
        var item=new Sample{sequence=sequence,frame=unityFrame,body=snapshot,png=png};
        item.bytes=Encoding.UTF8.GetByteCount(snapshot)+(png==null?0:png.Length);
        lock(pending) {
            if(stopping) return;
            if(item.bytes>MaxPendingBytes) { Interlocked.Increment(ref Dropped); return; }
            while(pending.Count>=MaxPending || pendingBytes+item.bytes>MaxPendingBytes) {
                pendingBytes-=pending.Dequeue().bytes; Interlocked.Increment(ref Dropped);
            }
            pending.Enqueue(item); pendingBytes+=item.bytes;
        }
        wake.Set();
    }
    static string Num(long n) { return n.ToString(CultureInfo.InvariantCulture); }
    string SamplePath(int slot) { return Path.Combine(directory,"sample-"+Num(slot)+".json"); }
    string FramePath(int slot) { return Path.Combine(directory,"frame-"+Num(slot)+".png"); }
    void PublishIndex() {
        var rows=new List<string>(); int frames=0;
        foreach(var row in records) {
            if(row.frameSlot>=0) frames++;
            rows.Add("{\"sequence\":"+Num(row.sequence)+",\"unity_frame\":"+Num(row.frame)+",\"slot\":"+Num(row.slot)+
                ",\"has_frame\":"+(row.frameSlot>=0?"true":"false")+",\"frame_slot\":"+(row.frameSlot>=0?Num(row.frameSlot):"null")+
                ",\"sha256\":"+(row.hash==null?"null":"\""+row.hash+"\"")+"}");
        }
        string text="{\"version\":1,\"session\":\""+session+"\",\"capacity\":"+Num(capacity)+",\"frame_capacity\":"+Num(frameCapacity)+
            ",\"dropped\":"+Num(Dropped)+",\"records\":["+String.Join(",",rows.ToArray())+"]}";
        ConsolePublisher.Replace(Path.Combine(directory,"index.json"),Encoding.UTF8.GetBytes(text));
        Count=records.Count; FrameCount=frames;
    }
    void Store(Sample item) {
        int slot=(int)(nextSlot++%capacity);
        int expiredFrame=-1;
        for(int i=records.Count-1;i>=0;i--) if(records[i].slot==slot) {
            expiredFrame=records[i].frameSlot;
            records.RemoveAt(i);
        }
        var record=new Record{sequence=item.sequence,frame=item.frame,slot=slot};
        if(item.png!=null) {
            record.frameSlot=(int)(nextFrameSlot++%frameCapacity);
            foreach(var old in records) if(old.frameSlot==record.frameSlot) { old.frameSlot=-1; old.hash=null; }
        }
        // Commit invalidation BEFORE overwriting any advertised slot. A disk error
        // followed by pause must not leave a manifest advertising broken entries.
        PublishIndex();
        if(expiredFrame>=0 && expiredFrame!=record.frameSlot) File.Delete(FramePath(expiredFrame));
        string envelope="{\"version\":1,\"session\":\""+session+"\",\"sequence\":"+Num(item.sequence)+",\"snapshot\":"+item.body+"}";
        ConsolePublisher.Replace(SamplePath(slot),Encoding.UTF8.GetBytes(envelope));
        if(item.png!=null) {
            using(var hash=SHA256.Create()) record.hash=BitConverter.ToString(hash.ComputeHash(item.png)).Replace("-","").ToLowerInvariant();
            ConsolePublisher.Replace(FramePath(record.frameSlot),item.png);
        }
        records.Add(record);
        try { PublishIndex(); } catch { records.Remove(record); throw; }
    }
    void Run() {
        while(true) {
            Sample item=null;
            lock(pending) {
                if(pending.Count>0) { item=pending.Dequeue(); pendingBytes-=item.bytes; }
                else if(stopping) return;
            }
            if(item==null) { wake.WaitOne(100); continue; }
            try { Store(item); } catch { Interlocked.Increment(ref Errors); }
        }
    }
    public void Dispose() { lock(pending) stopping=true; wake.Set(); if(worker.Join(1000)) wake.Close(); }
}
