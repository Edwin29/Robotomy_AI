using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

// Caller restricts this to the game's pauseFilter and its two ordinary decoration sprites.
// Never bypasses progression locks, modal panels, custom materials or postprocessing.
public sealed class ConsoleCoverAlpha {
    readonly Dictionary<Texture2D,CoverAlphaMap> maps=new Dictionary<Texture2D,CoverAlphaMap>();
    public bool ClearOver(Image image,Rect box,Rect label) {
        if(image==null || image.sprite==null || image.type!=Image.Type.Simple || image.preserveAspect ||
            image.material!=image.defaultMaterial || Mathf.Abs(Mathf.DeltaAngle(image.rectTransform.eulerAngles.z,0))>.1f ||
            (image.sprite.packed && image.sprite.packingRotation!=SpritePackingRotation.None)) return false;
        var texture=image.sprite.texture;
        if(texture==null || texture.width>4096 || texture.height>4096) return false;
        CoverAlphaMap map;
        if(!maps.TryGetValue(texture,out map)) {
            // Bounded cache; unsupported/readback failures stay blocked and are not retried every frame.
            if(maps.Count>=2) return false;
            map=Read(texture); maps[texture]=map;
        }
        if(map==null) return false;
        Vector4 uv=UnityEngine.Sprites.DataUtility.GetOuterUV(image.sprite);
        float left=Mathf.Max(box.xMin,label.xMin),right=Mathf.Min(box.xMax,label.xMax);
        float bottom=Mathf.Max(box.yMin,label.yMin),top=Mathf.Min(box.yMax,label.yMax);
        int x0=Mathf.FloorToInt(Mathf.Lerp(uv.x,uv.z,(left-box.xMin)/box.width)*texture.width)-1;
        int x1=Mathf.CeilToInt(Mathf.Lerp(uv.x,uv.z,(right-box.xMin)/box.width)*texture.width)+1;
        int y0=Mathf.FloorToInt(Mathf.Lerp(uv.y,uv.w,(bottom-box.yMin)/box.height)*texture.height)-1;
        int y1=Mathf.CeilToInt(Mathf.Lerp(uv.y,uv.w,(top-box.yMin)/box.height)*texture.height)+1;
        return map.Clear(Mathf.Max(0,x0),Mathf.Max(0,y0),Mathf.Min(texture.width,x1),Mathf.Min(texture.height,y1));
    }
    static CoverAlphaMap Read(Texture2D source) {
        RenderTexture previous=RenderTexture.active,temporary=null; Texture2D copy=null;
        try {
            temporary=RenderTexture.GetTemporary(source.width,source.height,0,RenderTextureFormat.ARGB32);
            Graphics.Blit(source,temporary); RenderTexture.active=temporary;
            copy=new Texture2D(source.width,source.height,TextureFormat.RGBA32,false);
            copy.ReadPixels(new Rect(0,0,source.width,source.height),0,0); copy.Apply();
            Color32[] pixels=copy.GetPixels32(); byte[] alpha=new byte[pixels.Length];
            for(int i=0;i<pixels.Length;i++) alpha[i]=pixels[i].a;
            return new CoverAlphaMap(alpha,source.width,source.height);
        } catch(Exception) { return null; }
        finally {
            RenderTexture.active=previous;
            if(temporary!=null) RenderTexture.ReleaseTemporary(temporary);
            if(copy!=null) UnityEngine.Object.Destroy(copy);
        }
    }
}
