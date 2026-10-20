using System;
using System.Collections.Generic;
using UnityEngine;

// Small readable display textures created by WorkerSpriteManager/Spine.
// Sample their ACTUAL mip alpha, rather than requiring an oversized mip footprint
// to be entirely alpha=255. This is a visible-patch estimate, not pixel-perfect
// reconstruction. Geometry, shader, camera and foreground occlusion stay in the caller.
public static class MotionTextureSample {
    sealed class Mips { public byte[][] alpha; public int width,height; }
    static readonly Dictionary<Texture2D,Mips> cache=new Dictionary<Texture2D,Mips>();
    static int bytes;
    const int Limit=8*1024*1024;
    public static void Reset(){cache.Clear();bytes=0;}
    static Mips Read(Texture2D texture) {
        Mips value;if(cache.TryGetValue(texture,out value))return value;
        if(cache.Count>=256 || texture.width>256 || texture.height>256)return null;
        value=null;
        try {
            int count=0;var alpha=new byte[texture.mipmapCount][];
            for(int level=0;level<alpha.Length;level++) {
                var pixels=texture.GetPixels32(level);count+=pixels.Length;
                if(bytes+count>Limit)break;
                alpha[level]=new byte[pixels.Length];
                for(int i=0;i<pixels.Length;i++)alpha[level][i]=pixels[i].a;
            }
            if(bytes+count<=Limit){value=new Mips{alpha=alpha,width=texture.width,height=texture.height};bytes+=count;}
        }catch { /* Unreadable textures continue through the existing atlas path. */ }
        cache[texture]=value;return value;
    }
    static int Index(int value,int size,bool repeat){return repeat?((value%size)+size)%size:Mathf.Clamp(value,0,size-1);}
    static float Alpha(Mips m,Texture2D texture,Vector2 uv,int level) {
        int w=Mathf.Max(1,m.width>>level),h=Mathf.Max(1,m.height>>level);
        float x=uv.x*w-.5f,y=uv.y*h-.5f;int ix=Mathf.FloorToInt(x),iy=Mathf.FloorToInt(y);
        bool repeat=texture.wrapMode==TextureWrapMode.Repeat;
        var a=m.alpha[level];
        float low=Mathf.Lerp(a[Index(iy,h,repeat)*w+Index(ix,w,repeat)],a[Index(iy,h,repeat)*w+Index(ix+1,w,repeat)],x-ix);
        float high=Mathf.Lerp(a[Index(iy+1,h,repeat)*w+Index(ix,w,repeat)],a[Index(iy+1,h,repeat)*w+Index(ix+1,w,repeat)],x-ix);
        return Mathf.Lerp(low,high,y-iy)/255f;
    }
    public static bool Visible(Texture2D texture,Vector2 center,Vector2 dx,Vector2 dy) {
        if(texture.anisoLevel>1 || texture.filterMode==FilterMode.Point ||
           (texture.wrapMode!=TextureWrapMode.Clamp && texture.wrapMode!=TextureWrapMode.Repeat))return false;
        Mips m=Read(texture);if(m==null)return false;
        Vector2 size=new Vector2(texture.width,texture.height);
        float rho=Mathf.Max(Vector2.Scale(dx,size).magnitude,Vector2.Scale(dy,size).magnitude);
        float lod=Mathf.Log(Mathf.Max(1,rho),2)+texture.mipMapBias+QualitySettings.masterTextureLimit;
        int lo=Mathf.Clamp(Mathf.FloorToInt(lod),0,m.alpha.Length-1),hi=Mathf.Clamp(Mathf.CeilToInt(lod),0,m.alpha.Length-1);
        // Solid center and all four corners of the 2px patch, in both sampled mips.
        for(int i=0;i<5;i++) {
            Vector2 uv=i==4?center:center+dx*((i&1)==0?-1:1)+dy*((i&2)==0?-1:1);
            if(Alpha(m,texture,uv,lo)<.75f || Alpha(m,texture,uv,hi)<.75f)return false;
        }
        return true;
    }
}
