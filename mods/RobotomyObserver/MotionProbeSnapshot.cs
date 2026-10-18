using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;

// Engineering fixture decoder for ConsoleMotion's fixed generated JSON schema.
// Does not rely on Unity serialization of classes in a runtime-loaded mod assembly.
// No external/player JSON is accepted here; malformed required fields fail the probe.
public static class MotionProbeSnapshot {
    public sealed class Vector { public float x,y; }
    public sealed class Sample {
        public string track_id,state;public Vector position,object_velocity,camera_velocity,screen_velocity;
        public float interval_ms;
    }
    public sealed class Packet { public string status;public Sample[] tracks; }
    static string Field(string json,string key,string valuePattern) {
        Match match=Regex.Match(json,"\""+key+"\":("+valuePattern+")");
        if(!match.Success) throw new FormatException("Missing motion fixture field: "+key);
        return match.Groups[1].Value;
    }
    static string Text(string json,string key) { return Field(json,key,"\"[a-zA-Z0-9_]+\"").Trim('"'); }
    static float Number(string json,string key) {
        return Single.Parse(Field(json,key,"-?[0-9]+(?:\\.[0-9]+)?"),CultureInfo.InvariantCulture);
    }
    static Vector Point(string json,string key) {
        string value=Field(json,key,"null|\\{[^{}]*\\}");
        return value=="null"?null:new Vector {x=Number(value,"x"),y=Number(value,"y")};
    }
    public static Packet Decode(string json) {
        var tracks=new List<Sample>();
        string[] parts=json.Split(new string[] {"{\"track_id\":"},StringSplitOptions.None);
        for(int i=1;i<parts.Length;i++) {
            string item="{\"track_id\":"+parts[i];
            tracks.Add(new Sample {track_id=Text(item,"track_id"),state=Text(item,"state"),
                position=Point(item,"position"),interval_ms=Number(item,"interval_ms"),
                object_velocity=Point(item,"object_velocity"),camera_velocity=Point(item,"camera_velocity"),
                screen_velocity=Point(item,"screen_velocity")});
        }
        return new Packet {status=Text(parts[0],"status"),tracks=tracks.ToArray()};
    }
}
