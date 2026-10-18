using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Threading;
using System.Runtime.InteropServices;
using System.ComponentModel;

// Bounded disk worker. Unity objects and input are never touched off the main thread.
public sealed class ConsolePublisher : IDisposable
{
    sealed class Write { public string path; public byte[] bytes; public bool append; }
    readonly Queue<Write> queue=new Queue<Write>();
    readonly Dictionary<string,Write> replacements=new Dictionary<string,Write>();
    readonly AutoResetEvent wake=new AutoResetEvent(false);
    readonly Thread thread;
    bool stopping;
    public int Dropped, Errors, Coalesced;
    public double LastWriteMs;
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool MoveFileEx(string existing, string destination, uint flags);
    public static void Replace(string path,byte[] bytes) {
        string temp=path+".tmp";
        File.WriteAllBytes(temp,bytes);
        // Mono File.Replace can expose an absent destination on this runtime.
        // Windows rename-replace preserves the last published file on sharing
        // failure. Only retry the disk operation, never game input or audio append.
        for(int attempt=0;;attempt++) {
            if(MoveFileEx(temp,path,1|8)) return; // REPLACE_EXISTING | WRITE_THROUGH
            int error=Marshal.GetLastWin32Error();
            if(attempt>=4 || (error!=5 && error!=32 && error!=33)) throw new Win32Exception(error);
            Thread.Sleep(10);
        }
    }
    public ConsolePublisher() { thread=new Thread(Run); thread.IsBackground=true; thread.Name="Robotomy publication"; thread.Start(); }
    public void Put(string path,byte[] bytes,bool append) {
        lock(queue) {
            if(stopping) return;
            Write existing;
            if(!append && replacements.TryGetValue(path,out existing)) {
                existing.bytes=bytes; Coalesced++; return;
            }
            if(queue.Count>=64) { Dropped++; return; } // No unbounded memory growth or implicit blocking.
            var item=new Write{path=path,bytes=bytes,append=append};
            queue.Enqueue(item);
            if(!append) replacements[path]=item;
        }
        wake.Set();
    }
    public void Text(string path,string text,bool append) { Put(path,Encoding.UTF8.GetBytes(text),append); }
    void Run() {
        while(true) {
            Write item=null;
            lock(queue) {
                if(queue.Count>0) { item=queue.Dequeue(); if(!item.append) replacements.Remove(item.path); }
                else if(stopping) return;
            }
            if(item==null) { wake.WaitOne(100); continue; }
            var timer=System.Diagnostics.Stopwatch.StartNew();
            try {
                if(item.append) {
                    using(var stream=new FileStream(item.path,FileMode.Append,FileAccess.Write,FileShare.Read)) stream.Write(item.bytes,0,item.bytes.Length);
                } else {
                    Replace(item.path,item.bytes);
                }
            } catch { Interlocked.Increment(ref Errors); }
            LastWriteMs=timer.Elapsed.TotalMilliseconds;
        }
    }
    public void Dispose() { lock(queue) stopping=true; wake.Set(); if(thread.Join(1000)) wake.Close(); }
}
