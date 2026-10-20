using System;
using System.Collections.Generic;
using UnityEngine;

// Display geometry only. The caller owns camera-profile and occlusion checks.
// Cache lifetime must be restricted to a verified scene with immutable atlas textures.
public static class MotionSurface
{
    const long CacheLimit = 64L * 1024 * 1024;
    const int TexturePixelLimit = 4 * 1024 * 1024;
    sealed class AlphaMap {
        public Texture2D texture;
        public int width, height, stride;
        public int[] bad, nonzero;
        public byte maximum;
        public int tileStride;
        public byte[] tileMaximum;
    }
    sealed class Geometry {
        public Vector3[] vertices;
        public Vector2[] uv;
        public Color32[] colors;
        public int[][] triangles;
    }
    static readonly Dictionary<Texture2D, AlphaMap> atlases = new Dictionary<Texture2D, AlphaMap>();
    static readonly Dictionary<Texture2D, string> failedAtlases = new Dictionary<Texture2D, string>();
    static readonly Dictionary<Mesh, Geometry> meshes = new Dictionary<Mesh, Geometry>();
    static readonly MaterialPropertyBlock propertyBlock = new MaterialPropertyBlock();
    static int frame = -1;
    public static string LastFailure = "";
    public static long CachedTextureBytes;
    public static double LastColdMilliseconds;
    public static float LastTextureAlphaMaximum, LastTintAlphaUpper, LastTransmission;
    public static float LastLocalAlphaUpper=1, LastGlobalAlphaUpper=1;
    public static string LastBoundDescription="";
    static bool regionMeasured;
    static float regionAlphaUpper=1, patchAlphaUpper=1;
    public static int CachedTextureCount { get { return atlases.Count; } }

    public static void Reset() {
        atlases.Clear(); failedAtlases.Clear(); meshes.Clear(); frame=-1;
        MotionTextureSample.Reset();
        CachedTextureBytes=0; LastColdMilliseconds=0; LastFailure="";
        LastTextureAlphaMaximum=LastTintAlphaUpper=LastTransmission=0;
        LastLocalAlphaUpper=LastGlobalAlphaUpper=regionAlphaUpper=patchAlphaUpper=1;
        LastBoundDescription=""; regionMeasured=false;
    }
    static bool Fail(string reason) { LastFailure=reason; return false; }
    static bool Finite(float value) { return !Single.IsNaN(value) && !Single.IsInfinity(value); }
    static bool Finite(Vector4 value) { return Finite(value.x)&&Finite(value.y)&&Finite(value.z)&&Finite(value.w); }

    static AlphaMap Atlas(Texture2D texture) {
        AlphaMap cached;
        if(atlases.TryGetValue(texture,out cached)) return cached;
        // Color32 readback cannot prove exact zero/one for HDR or float alpha: rounding
        // could erase a small contribution. Admit only ordinary 8-bit-or-less atlases.
        TextureFormat format=texture.format;
        if(format!=TextureFormat.RGBA32 && format!=TextureFormat.ARGB32 && format!=TextureFormat.RGB24 &&
            format!=TextureFormat.Alpha8 && format!=TextureFormat.DXT1 && format!=TextureFormat.DXT5 &&
            format!=TextureFormat.RGBA4444 && format!=TextureFormat.ARGB4444 && format!=TextureFormat.RGB565) {
            Fail("atlas_alpha_precision"); return null;
        }
        string failed;
        if(failedAtlases.TryGetValue(texture,out failed)) { Fail(failed); return null; }
        if(atlases.Count>=256) { Fail("atlas_count_limit"); return null; }
        int w=texture.width, h=texture.height;
        int tileStride=(w+7)/8, tileRows=(h+7)/8;
        long count=(long)w*h, bytes=((long)w+1)*(h+1)*8+(long)tileStride*tileRows;
        if(w<1 || h<1 || count>TexturePixelLimit || CachedTextureBytes+bytes>CacheLimit) {
            Fail("atlas_memory_limit"); return null;
        }
        var timer=System.Diagnostics.Stopwatch.StartNew();
        Color32[] pixels=null;
        Texture2D copy=null;
        RenderTexture temporary=null;
        RenderTexture previous=RenderTexture.active;
        try {
            try { pixels=texture.GetPixels32(0); } catch { pixels=null; }
            if(pixels==null || pixels.Length!=count) {
                // Exact-size readback. Nonzero sampler bias would not represent level zero.
                if(Mathf.Abs(texture.mipMapBias)>.0001f || QualitySettings.masterTextureLimit!=0)
                    { Fail("readback_lod_unverified"); return null; }
                temporary=RenderTexture.GetTemporary(w,h,0,RenderTextureFormat.ARGB32,RenderTextureReadWrite.Linear);
                temporary.filterMode=FilterMode.Point;
                Graphics.Blit(texture,temporary);
                RenderTexture.active=temporary;
                copy=new Texture2D(w,h,TextureFormat.RGBA32,false,true);
                copy.ReadPixels(new Rect(0,0,w,h),0,0,false);
                copy.Apply(false,false);
                pixels=copy.GetPixels32();
            }
            if(pixels==null || pixels.Length!=count) { Fail("atlas_readback_length"); return null; }
            int stride=w+1;
            var sums=new int[(w+1)*(h+1)];
            var nonzero=new int[(w+1)*(h+1)];
            var tileMaximum=new byte[tileStride*tileRows];
            byte maximum=0;
            for(int y=0;y<h;y++) {
                int row=0, present=0;
                for(int x=0;x<w;x++) {
                    if(pixels[y*w+x].a!=255) row++;
                    if(pixels[y*w+x].a!=0) present++;
                    if(pixels[y*w+x].a>maximum) maximum=pixels[y*w+x].a;
                    int tile=(y/8)*tileStride+x/8;
                    if(pixels[y*w+x].a>tileMaximum[tile]) tileMaximum[tile]=pixels[y*w+x].a;
                    sums[(y+1)*stride+x+1]=sums[y*stride+x+1]+row;
                    nonzero[(y+1)*stride+x+1]=nonzero[y*stride+x+1]+present;
                }
            }
            cached=new AlphaMap { texture=texture,width=w,height=h,stride=stride,bad=sums,nonzero=nonzero,maximum=maximum,
                tileStride=tileStride,tileMaximum=tileMaximum };
            atlases.Add(texture,cached); CachedTextureBytes+=bytes;
            return cached;
        } catch { Fail("atlas_readback_failed"); return null; }
        finally {
            RenderTexture.active=previous;
            if(temporary!=null) RenderTexture.ReleaseTemporary(temporary);
            if(copy!=null) UnityEngine.Object.Destroy(copy);
            LastColdMilliseconds=timer.Elapsed.TotalMilliseconds;
            if(!atlases.ContainsKey(texture) && failedAtlases.Count<32) failedAtlases[texture]=LastFailure;
        }
    }
    static bool Prepare(Renderer renderer, Camera camera, out Geometry geometry, out Material[] materials) {
        geometry=null; materials=null;
        if(renderer==null || camera==null || !camera.orthographic || !renderer.enabled || !renderer.gameObject.activeInHierarchy)
            return Fail("surface_inactive");
        propertyBlock.Clear(); renderer.GetPropertyBlock(propertyBlock);
        if(!propertyBlock.isEmpty) return Fail("surface_property_block");
        var filter=renderer.GetComponent<MeshFilter>();
        if(filter==null || filter.sharedMesh==null) return Fail("surface_no_mesh");
        Mesh mesh=filter.sharedMesh;
        if(frame!=Time.frameCount) { meshes.Clear(); frame=Time.frameCount; }
        if(!meshes.TryGetValue(mesh,out geometry)) {
            if(mesh.vertexCount<3 || mesh.vertexCount>65536 || mesh.subMeshCount<1 || mesh.subMeshCount>32)
                return Fail("surface_mesh_limit");
            geometry=new Geometry { vertices=mesh.vertices, uv=mesh.uv, colors=mesh.colors32, triangles=new int[mesh.subMeshCount][] };
            if(geometry.uv.Length!=geometry.vertices.Length || geometry.colors.Length!=geometry.vertices.Length)
                return Fail("surface_vertex_data");
            int total=0;
            for(int i=0;i<mesh.subMeshCount;i++) {
                if(mesh.GetTopology(i)!=MeshTopology.Triangles) return Fail("surface_topology");
                geometry.triangles[i]=mesh.GetTriangles(i); total+=geometry.triangles[i].Length;
            }
            if(total>262144) return Fail("surface_triangle_limit");
            if(meshes.Count<128) meshes.Add(mesh,geometry);
        }
        materials=renderer.sharedMaterials;
        if(materials.Length!=geometry.triangles.Length) return Fail("surface_material_count");
        for(int materialIndex=0;materialIndex<materials.Length;materialIndex++) {
            Material material=materials[materialIndex];
            // This shipped Unity 2017 API exposes renderer-wide property blocks only;
            // the renderer-wide block was checked above.
            if(material==null || material.shader==null || material.shader.name!="Spine/Skeleton") return Fail("surface_shader");
            if(material.HasProperty("_Color") && material.GetColor("_Color").a!=1f) return Fail("surface_material_alpha");
            if(material.mainTextureScale!=Vector2.one || material.mainTextureOffset!=Vector2.zero) return Fail("surface_uv_transform");
            if(!(material.mainTexture is Texture2D)) return Fail("surface_texture_type");
        }
        return true;
    }
    static Vector3 Weights(Vector2 p, Vector3 a, Vector3 b, Vector3 c, float determinant) {
        float x=p.x-a.x,y=p.y-a.y;
        float u=(x*(c.y-a.y)-y*(c.x-a.x))/determinant;
        float v=((b.x-a.x)*y-(b.y-a.y)*x)/determinant;
        return new Vector3(1-u-v,u,v);
    }
    static Vector2 UV(Vector3 weight, Vector2 a, Vector2 b, Vector2 c) { return a*weight.x+b*weight.y+c*weight.z; }

    static bool Patch(Vector2 center, Vector3 a, Vector3 b, Vector3 c, Vector2 ua, Vector2 ub, Vector2 uc,
        Texture2D texture, Camera camera, out Rect region) {
        region=new Rect(center.x-1,center.y-1,2,2);
        if(region.xMin<0 || region.yMin<0 || region.xMax>Screen.width || region.yMax>Screen.height) return Fail("surface_offscreen");
        if(a.z<camera.nearClipPlane || b.z<camera.nearClipPlane || c.z<camera.nearClipPlane ||
            a.z>camera.farClipPlane || b.z>camera.farClipPlane || c.z>camera.farClipPlane) return Fail("surface_depth");
        float determinant=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
        if(!Finite(determinant) || Mathf.Abs(determinant)<.001f) return Fail("surface_degenerate");
        Vector2 lo=new Vector2(float.MaxValue,float.MaxValue),hi=new Vector2(float.MinValue,float.MinValue);
        for(int corner=0;corner<4;corner++) {
            Vector2 p=new Vector2((corner&1)==0?region.xMin:region.xMax,(corner&2)==0?region.yMin:region.yMax);
            Vector3 weight=Weights(p,a,b,c,determinant);
            if(weight.x<0 || weight.y<0 || weight.z<0) return Fail("surface_patch_edge");
            Vector2 uv=UV(weight,ua,ub,uc);
            if(!Finite(uv.x) || !Finite(uv.y)) return Fail("surface_invalid_uv");
            lo=Vector2.Min(lo,uv); hi=Vector2.Max(hi,uv);
        }
        if(lo.x<0 || lo.y<0 || hi.x>1 || hi.y>1) return Fail("surface_wrapped_uv");
        Vector2 uv0=UV(Weights(center,a,b,c,determinant),ua,ub,uc);
        Vector2 dx=UV(Weights(center+Vector2.right,a,b,c,determinant),ua,ub,uc)-uv0;
        Vector2 dy=UV(Weights(center+Vector2.up,a,b,c,determinant),ua,ub,uc)-uv0;
        return MotionTextureSample.Visible(texture,uv0,dx,dy) || TextureRegion(texture,lo,hi,dx,dy,false);
    }
    static bool TextureRegion(Texture2D texture, Vector2 lo, Vector2 hi, Vector2 dx, Vector2 dy, bool empty) {
        regionMeasured=false; regionAlphaUpper=1;
        if(!Finite(lo.x) || !Finite(lo.y) || !Finite(hi.x) || !Finite(hi.y) ||
            lo.x<0 || lo.y<0 || hi.x>1 || hi.y>1) return Fail("surface_wrapped_uv");
        dx=Vector2.Scale(dx,new Vector2(texture.width,texture.height));
        dy=Vector2.Scale(dy,new Vector2(texture.width,texture.height));
        // Frobenius norm bounds the largest singular value of screen->texel mapping,
        // including rotated/sheared triangles (max(column lengths) does not).
        float rho=Mathf.Sqrt(dx.sqrMagnitude+dy.sqrMagnitude);
        if(!Finite(rho)) return Fail("surface_lod_invalid");
        // Cover both trilinear levels and their complete source-level texel blocks.
        // This requires the profile's atlas mips to be normally generated from level zero.
        int level=0;
        if(texture.mipmapCount>1) {
            float lod=Mathf.Log(Mathf.Max(1,rho),2)+Mathf.Max(0,texture.mipMapBias)+QualitySettings.masterTextureLimit;
            // ceil(lod) is already the upper trilinear level. Tiny epsilon only
            // protects rounding at an exact integer, rather than doubling all footprints.
            level=Mathf.Clamp(Mathf.CeilToInt(lod+.0001f),0,texture.mipmapCount-1);
        }
        int block=1<<Mathf.Min(level,20);
        // Normal anisotropic sampling distributes taps along this projected footprint;
        // anisoLevel increases tap count, not its geometric major-axis extent. Expand
        // by a FULL major-axis bound on either side, then by the coarsest mip's
        // bilinear source blocks. This also covers ForceEnable and level-zero taps.
        // We deliberately overbound the usual half-axis support; no sampler settings
        // are changed. As above, only normal generated mip chains are admitted.
        float tapExtent=(texture.anisoLevel>1 || QualitySettings.anisotropicFiltering==AnisotropicFiltering.ForceEnable)?rho:0;
        int x0=Mathf.FloorToInt((lo.x*texture.width-tapExtent)/block-1)*block;
        int y0=Mathf.FloorToInt((lo.y*texture.height-tapExtent)/block-1)*block;
        int x1=(Mathf.FloorToInt((hi.x*texture.width+tapExtent)/block)+2)*block;
        int y1=(Mathf.FloorToInt((hi.y*texture.height+tapExtent)/block)+2)*block;
        if(x0<0 || y0<0 || x1>texture.width || y1>texture.height) return Fail("surface_atlas_edge");
        if((long)(x1-x0)*(y1-y0)>65536) return Fail("surface_footprint_limit");
        AlphaMap alpha=Atlas(texture);
        if(alpha==null) return false;
        int stride=alpha.stride;
        int[] sums=empty?alpha.nonzero:alpha.bad;
        int bad=sums[y1*stride+x1]-sums[y0*stride+x1]-sums[y1*stride+x0]+sums[y0*stride+x0];
        if(empty) {
            int maximum=0;
            for(int ty=y0/8;ty<=(y1-1)/8;ty++)
                for(int tx=x0/8;tx<=(x1-1)/8;tx++)
                    maximum=Math.Max(maximum,alpha.tileMaximum[ty*alpha.tileStride+tx]);
            // Each overlapped tile includes extra texels, so its maximum remains an
            // upper bound for the already mip/aniso-expanded source footprint.
            regionAlphaUpper=bad==0?0:Mathf.Min(255,maximum+1)/255f;
            regionMeasured=true;
        }
        return bad==0 || Fail(empty?"surface_texture_nonzero":"surface_texture_alpha");
    }

    static List<Vector2> Clip(List<Vector2> points, int axis, float edge, bool greater) {
        var result=new List<Vector2>(8);
        if(points.Count==0) return result;
        Vector2 previous=points[points.Count-1];
        float pv=axis==0?previous.x:previous.y;
        bool inside=greater?pv>=edge:pv<=edge;
        foreach(Vector2 current in points) {
            float cv=axis==0?current.x:current.y;
            bool next=greater?cv>=edge:cv<=edge;
            if(next!=inside) {
                float t=(edge-pv)/(cv-pv);
                result.Add(previous+(current-previous)*t);
            }
            if(next) result.Add(current);
            previous=current; pv=cv; inside=next;
        }
        return result;
    }
    // True means no sprite fragment can contribute in this screen rectangle.
    // False is deliberately ambiguous: opaque, unsupported, or failed to establish zero.
    // Shader contract verified against official Unity 2017.4.40f1 source archive:
    // https://download.unity3d.com/download_unity/6e14067f8a9a/builtin_shaders-2017.4.40f1.zip
    // DefaultResourcesExtra/Sprites-Default.shader + CGIncludes/UnitySprites.cginc.
    // Additional shipped profile: Custom/SpriteDefaultCustomMask, resources.assets
    // object5165 SHA256 a29d1d6cf63670a5f42e663e6d7571ca455b84a598efff89acf5d34697134c00.
    // DXBC audit: .robotomy/analysis/custom-sprite-mask.dxbc.txt and .bindings.txt.
    // It samples _MainTex * (vertexColor * _Color), premultiplies RGB, and uses
    // One/OneMinusSrcAlpha, Add, ZWriteOff, LEqual. Its optional stencil test only
    // removes fragments; treating every fragment as passing is conservative here.
    static bool KnownSpriteShader(Material material) {
        if(material==null || material.shader==null) return false;
        string name=material.shader.name;
        return (name=="Sprites/Default" || name=="Custom/SpriteDefaultCustomMask") && material.shader==Shader.Find(name);
    }
    static bool SpriteTexture(SpriteRenderer sprite, Material material, out Texture2D texture) {
        texture=null;
        if(!KnownSpriteShader(material)) return Fail("sprite_shader_identity");
        bool customMask=material.shader.name=="Custom/SpriteDefaultCustomMask";
        if(customMask && (sprite.flipX || sprite.flipY)) return Fail("custom_sprite_flip_unverified");
        propertyBlock.Clear(); sprite.GetPropertyBlock(propertyBlock);
        if(material.mainTextureScale!=Vector2.one || material.mainTextureOffset!=Vector2.zero)
            return Fail("sprite_uv_transform");
        // PixelSnap's float only drives an editor keyword toggle. The actual variant
        // PIXELSNAP_ON is implemented below using UnityPixelSnap's vertex rounding.
        if(!customMask && ((material.HasProperty("_EnableExternalAlpha") && material.GetFloat("_EnableExternalAlpha")!=0) ||
            propertyBlock.GetFloat("_EnableExternalAlpha")!=0 || sprite.sprite.associatedAlphaSplitTexture!=null))
            return Fail("sprite_external_alpha");
        // The built-in renderer supplies a property block, notably _MainTex. Empty
        // GetTexture is ambiguous (absent versus explicit-null) on this Unity API:
        // only a completely empty block can fall back to the native sprite binding.
        Texture binding=propertyBlock.GetTexture("_MainTex");
        if(binding==null && !propertyBlock.isEmpty) return Fail("sprite_texture_binding_missing");
        texture=binding==null?sprite.sprite.texture:binding as Texture2D;
        if(texture==null) return Fail("sprite_texture_binding_type");
        Vector4 flip=propertyBlock.GetVector("_Flip");
        if(flip!=Vector4.zero && (!Finite(flip) || flip.x!=(sprite.flipX?-1f:1f) || flip.y!=(sprite.flipY?-1f:1f)))
            return Fail("sprite_flip_override:value="+flip+",native="+sprite.flipX+","+sprite.flipY);
        // Instancing itself is ordinary SpriteRenderer behavior: Unity supplies the
        // same native Transform, flip and tint per instance. Validate explicit arrays
        // if present, rather than rejecting the material's enableInstancing flag.
        Vector4[] flips=propertyBlock.GetVectorArray("unity_SpriteFlipArray");
        if(flips!=null) foreach(Vector4 value in flips)
            if(!Finite(value) || value.x!=(sprite.flipX?-1f:1f) || value.y!=(sprite.flipY?-1f:1f))
                return Fail("sprite_flip_array_override");
        Vector4[] colors=propertyBlock.GetVectorArray("unity_SpriteRendererColorArray");
        if(colors!=null) foreach(Vector4 value in colors) if(!Finite(value)) return Fail("sprite_nonfinite_tint_array");
        Matrix4x4[] matrices=propertyBlock.GetMatrixArray("unity_ObjectToWorldArray");
        if(matrices!=null && matrices.Length!=0) return Fail("sprite_matrix_array_override");
        // Unknown property names cannot add opacity: this fixed shader consumes only
        // _MainTex, tint, flip and the explicitly rejected alternate paths. Do not
        // infer transparency from a missing/zero tint override; prove texture alpha.
        if(!Finite((Vector4)sprite.color) || !Finite(propertyBlock.GetVector("_Color")) ||
            !Finite(propertyBlock.GetVector("_RendererColor")) ||
            (material.HasProperty("_Color") && !Finite((Vector4)material.GetColor("_Color"))) ||
            (material.HasProperty("_RendererColor") && !Finite((Vector4)material.GetColor("_RendererColor"))))
            return Fail("sprite_nonfinite_tint");
        // Disallow user-supplied transform uniforms; actual camera and transform
        // projection is valid only for the ordinary renderer-managed matrices.
        // Unity 2017 GetMatrix returns IDENTITY for absent properties, not zero.
        foreach(string name in new string[] {"unity_ObjectToWorld","unity_WorldToObject","unity_MatrixVP","glstate_matrix_mvp"})
            if(propertyBlock.GetMatrix(name)!=Matrix4x4.identity) return Fail("sprite_matrix_override:"+name);
        return true;
    }
    static string SpriteDiagnostic(SpriteRenderer sprite, Material material) {
        Texture binding=propertyBlock.GetTexture("_MainTex");
        return "[shaderMatch="+KnownSpriteShader(material)+",profile="+material.shader.name+",instancing="+material.enableInstancing+
            ",keywords="+String.Join("|",material.shaderKeywords)+",binding="+(binding==null?"null":binding.GetType().Name+":"+binding.width+"x"+binding.height)+
            ",flip="+propertyBlock.GetVector("_Flip")+",external="+propertyBlock.GetFloat("_EnableExternalAlpha")+
            ",nativeFlip="+sprite.flipX+","+sprite.flipY+"]";
    }
    public static bool TransparentPatch(Renderer renderer, Camera camera, Rect region) {
        patchAlphaUpper=1;
        try {
            SpriteRenderer sprite=renderer as SpriteRenderer;
            if(sprite==null || camera==null || !camera.orthographic || sprite.sprite==null ||
                sprite.drawMode!=SpriteDrawMode.Simple || region.width<=0 || region.height<=0) return false;
            Material[] materials=renderer.sharedMaterials;
            if(materials.Length!=1) return false;
            Material material=materials[0];
            if(!KnownSpriteShader(material)) return false;
            Texture2D texture;
            if(!SpriteTexture(sprite,material,out texture)) { LastFailure+=SpriteDiagnostic(sprite,material); return false; }
            bool pixelSnap=material.IsKeywordEnabled("PIXELSNAP_ON");
            if(pixelSnap && camera.pixelRect!=new Rect(0,0,Screen.width,Screen.height)) return Fail("sprite_snap_viewport");
            Vector2[] vertices=sprite.sprite.vertices,uv=sprite.sprite.uv;
            ushort[] triangles=sprite.sprite.triangles;
            if(vertices.Length!=uv.Length || vertices.Length>65536 || triangles.Length>262144) return false;
            var projected=new Vector3[vertices.Length];
            float maximumPatchAlpha=0;
            bool allZero=true;
            for(int i=0;i<vertices.Length;i++) {
                Vector2 p=vertices[i];
                if(sprite.flipX) p.x=-p.x;
                if(sprite.flipY) p.y=-p.y;
                projected[i]=camera.WorldToScreenPoint(sprite.transform.TransformPoint(new Vector3(p.x,p.y,0)));
                if(pixelSnap) {
                    // UnityCG.cginc UnityPixelSnap: round(NDC * (_ScreenParams.xy/2)).
                    // Windows uses round-to-even, not floor(x+.5). Retain actual z.
                    Vector3 point=projected[i];
                    point.x=(float)Math.Round(point.x-Screen.width*.5f,MidpointRounding.ToEven)+Screen.width*.5f;
                    point.y=(float)Math.Round(point.y-Screen.height*.5f,MidpointRounding.ToEven)+Screen.height*.5f;
                    projected[i]=point;
                }
            }
            for(int i=0;i+2<triangles.Length;i+=3) {
                int ia=triangles[i],ib=triangles[i+1],ic=triangles[i+2];
                if(ia>=vertices.Length || ib>=vertices.Length || ic>=vertices.Length) return false;
                Vector3 a=projected[ia],b=projected[ib],c=projected[ic];
                if(!Finite(a.x)||!Finite(a.y)||!Finite(b.x)||!Finite(b.y)||!Finite(c.x)||!Finite(c.y)) return false;
                var polygon=new List<Vector2>(3) { new Vector2(a.x,a.y),new Vector2(b.x,b.y),new Vector2(c.x,c.y) };
                // Expand a fraction of a pixel to avoid claiming zero at raster boundaries.
                polygon=Clip(polygon,0,region.xMin-.01f,true);
                polygon=Clip(polygon,0,region.xMax+.01f,false);
                polygon=Clip(polygon,1,region.yMin-.01f,true);
                polygon=Clip(polygon,1,region.yMax+.01f,false);
                if(polygon.Count==0) continue;
                float determinant=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
                if(!Finite(determinant) || Mathf.Abs(determinant)<.001f) return false;
                if(a.z<camera.nearClipPlane || b.z<camera.nearClipPlane || c.z<camera.nearClipPlane ||
                    a.z>camera.farClipPlane || b.z>camera.farClipPlane || c.z>camera.farClipPlane) return false;
                Vector2 lo=new Vector2(float.MaxValue,float.MaxValue),hi=new Vector2(float.MinValue,float.MinValue);
                foreach(Vector2 p in polygon) {
                    Vector2 u=UV(Weights(p,a,b,c,determinant),uv[ia],uv[ib],uv[ic]);
                    lo=Vector2.Min(lo,u); hi=Vector2.Max(hi,u);
                }
                Vector2 origin=polygon[0];
                Vector2 u0=UV(Weights(origin,a,b,c,determinant),uv[ia],uv[ib],uv[ic]);
                Vector2 dx=UV(Weights(origin+Vector2.right,a,b,c,determinant),uv[ia],uv[ib],uv[ic])-u0;
                Vector2 dy=UV(Weights(origin+Vector2.up,a,b,c,determinant),uv[ia],uv[ib],uv[ic])-u0;
                bool zero=TextureRegion(texture,lo,hi,dx,dy,true);
                if(!regionMeasured) { LastFailure+=SpriteDiagnostic(sprite,material); return false; }
                maximumPatchAlpha=Mathf.Max(maximumPatchAlpha,regionAlphaUpper);
                if(!zero) allZero=false;
            }
            // Do not publish a partial bound before every intersecting triangle has
            // been checked. Unsupported later geometry leaves the default upper1.
            patchAlphaUpper=maximumPatchAlpha;
            if(!allZero) LastFailure="surface_local_alpha:"+maximumPatchAlpha.ToString("R",System.Globalization.CultureInfo.InvariantCulture);
            return allZero;
        } catch { return Fail("sprite_surface_exception"); }
    }

    // Lower bound on how much background contrast survives this known alpha blend.
    // This is NOT a claim of zero coverage. The caller composes every possible cover
    // multiplicatively, then applies its explicit minimum-contrast admission policy.
    public static float Transmission(Renderer renderer, Camera camera, Rect region) {
        LastTextureAlphaMaximum=LastTintAlphaUpper=LastTransmission=0;
        LastLocalAlphaUpper=LastGlobalAlphaUpper=1; LastBoundDescription="";
        try {
            if(TransparentPatch(renderer,camera,region)) {
                LastLocalAlphaUpper=0; LastFailure=""; LastTransmission=1; LastBoundDescription="local=0,used=zero"; return 1;
            }
            LastLocalAlphaUpper=patchAlphaUpper;
            SpriteRenderer sprite=renderer as SpriteRenderer;
            if(sprite==null || sprite.sprite==null || sprite.drawMode!=SpriteDrawMode.Simple) return 0;
            Material[] materials=renderer.sharedMaterials;
            if(materials.Length!=1) return 0;
            Material material=materials[0];
            if(!KnownSpriteShader(material)) return 0;
            Texture2D texture;
            if(!SpriteTexture(sprite,material,out texture)) { LastFailure+=SpriteDiagnostic(sprite,material); return 0; }
            AlphaMap alpha=Atlas(texture);
            if(alpha==null) return 0;
            // Use the smaller of two independently conservative bounds. Unknown
            // projected UV geometry retains local1 and falls back to global maximum.
            LastGlobalAlphaUpper=Mathf.Min(255,alpha.maximum+1)/255f;
            LastTextureAlphaMaximum=Mathf.Min(LastGlobalAlphaUpper,LastLocalAlphaUpper);
            float materialTint=material.HasProperty("_Color")?material.GetColor("_Color").a:1;
            Vector4 blockColor=propertyBlock.GetVector("_Color");
            float blockTint=blockColor.w;
            float materialRenderer=material.HasProperty("_RendererColor")?material.GetColor("_RendererColor").a:1;
            Vector4 blockRendererColor=propertyBlock.GetVector("_RendererColor");
            float blockRenderer=blockRendererColor.w;
            if(materialTint<0 || blockTint<0 || materialRenderer<0 || blockRenderer<0 || sprite.color.a<0) {
                Fail("sprite_negative_tint"); return 0;
            }
            // Any nonzero vector unequivocally establishes a block override, even
            // RGB=(1,1,1), alpha0. All-zero remains ambiguous with an absent property.
            float effectiveColor=blockColor!=Vector4.zero?blockTint:Mathf.Max(materialTint,blockTint);
            // SpriteRenderer.color is an actual display tint. Unity supplies it
            // through vertices or native renderer color, depending on batching.
            // Count it ONCE; replacing it with max(1, alpha) made the ordinary
            // 20%-opacity facility Fog behave as a completely opaque cover.
            float effectiveRenderer=blockRendererColor!=Vector4.zero?Mathf.Max(sprite.color.a,blockRenderer):sprite.color.a;
            effectiveRenderer*=Mathf.Max(1,materialRenderer);
            bool customMask=material.shader.name=="Custom/SpriteDefaultCustomMask";
            if(customMask) effectiveRenderer=sprite.color.a; // Native vertex tint; no _RendererColor in this DXBC.
            Vector4[] colors=propertyBlock.GetVectorArray("unity_SpriteRendererColorArray");
            float instanceUpper=0;
            if(colors!=null) foreach(Vector4 color in colors) {
                if(!Finite(color) || color.w<0) { Fail("sprite_instance_tint_invalid"); return 0; }
                instanceUpper=Mathf.Max(instanceUpper,color.w);
            }
            if(material.enableInstancing && !customMask) {
                // A material may select an instanced OR ordinary draw. Cover both.
                effectiveRenderer=Mathf.Max(effectiveRenderer,
                    colors!=null && colors.Length>0?instanceUpper:sprite.color.a);
            }
            // Vertex tint can be white or native tint depending on batching. Never
            // square an alpha below1 when the native value may be applied only once.
            float tint=effectiveColor*effectiveRenderer;
            if(!Finite(tint)) { Fail("sprite_tint_overflow"); return 0; }
            LastTintAlphaUpper=tint;
            LastTransmission=1-Mathf.Clamp01(LastTextureAlphaMaximum*tint);
            LastBoundDescription="local="+LastLocalAlphaUpper.ToString("R",System.Globalization.CultureInfo.InvariantCulture)+
                ",global="+LastGlobalAlphaUpper.ToString("R",System.Globalization.CultureInfo.InvariantCulture)+
                ",used="+(LastLocalAlphaUpper<LastGlobalAlphaUpper?"local":"global")+
                ",tint="+tint.ToString("R",System.Globalization.CultureInfo.InvariantCulture)+
                ",effectiveColor="+effectiveColor+",effectiveRenderer="+effectiveRenderer+
                ",blockColor="+blockColor+",blockRenderer="+blockRendererColor+
                ",materialAlpha="+materialTint+","+materialRenderer+",nativeAlpha="+sprite.color.a;
            LastFailure="";
            return LastTransmission;
        } catch { Fail("sprite_transmission_exception"); return 0; }
    }

    // Existence of a visible body, not proof that an entire anisotropic footprint is opaque.
    // Small zoomed-out creatures previously failed the all-texels-opaque contract.
    public static bool PickPresence(Renderer renderer,Camera camera,Func<Rect,Vector3,bool> visible,out Vector3 world,out Rect region){
        world=Vector3.zero;region=new Rect();Geometry g;Material[] materials;
        if(!Prepare(renderer,camera,out g,out materials))return false;
        for(int sub=0;sub<g.triangles.Length;sub++){
            var tex=materials[sub].mainTexture as Texture2D;if(tex==null)continue;var alpha=Atlas(tex);if(alpha==null)continue;
            var indices=g.triangles[sub];
            for(int i=0;i+2<indices.Length;i+=3){
                int a=indices[i],b=indices[i+1],c=indices[i+2];
                if(a<0 || b<0 || c<0 || a>=g.vertices.Length || b>=g.vertices.Length || c>=g.vertices.Length)continue;
                if(g.colors[a].a<128 || g.colors[b].a<128 || g.colors[c].a<128)continue;
                Vector2 uv=(g.uv[a]+g.uv[b]+g.uv[c])/3;
                int x=Mathf.FloorToInt(uv.x*tex.width),y=Mathf.FloorToInt(uv.y*tex.height);
                if(x<1 || y<1 || x>=tex.width-1 || y>=tex.height-1)continue;
                int x0=x-1,y0=y-1,x1=x+2,y1=y+2,stride=alpha.stride;
                if(alpha.bad[y1*stride+x1]-alpha.bad[y0*stride+x1]-alpha.bad[y1*stride+x0]+alpha.bad[y0*stride+x0]>0)continue;
                var w=renderer.transform.TransformPoint((g.vertices[a]+g.vertices[b]+g.vertices[c])/3);var q=camera.WorldToScreenPoint(w);
                if(q.z<camera.nearClipPlane || q.z>camera.farClipPlane || q.x<1 || q.y<1 || q.x>=Screen.width-1 || q.y>=Screen.height-1)continue;
                var r=new Rect(q.x-1,q.y-1,2,2);if(visible!=null && !visible(r,w))continue;
                world=w;region=r;return true;
            }
        }return false;
    }

    public static bool Contains(Renderer renderer, Camera camera, Vector3 world, out Rect region) {
        Vector3 ignored;
        return Find(renderer,camera,false,world,null,out ignored,out region);
    }
    public static bool Pick(Renderer renderer, Camera camera, out Vector3 world, out Rect region) {
        return Find(renderer,camera,true,Vector3.zero,null,out world,out region);
    }
    public static bool PickVisible(Renderer renderer, Camera camera, Func<Rect,Vector3,bool> visible, out Vector3 world, out Rect region) {
        return Find(renderer,camera,true,Vector3.zero,visible,out world,out region);
    }
    static bool Find(Renderer renderer, Camera camera, bool pick, Vector3 requested, Func<Rect,Vector3,bool> visible, out Vector3 world, out Rect region) {
        world=Vector3.zero; region=new Rect(); LastFailure="surface_no_patch";
        try {
            Geometry geometry; Material[] materials;
            if(!Prepare(renderer,camera,out geometry,out materials)) return false;
            Vector3 fixedPoint=camera.WorldToScreenPoint(requested);
            Vector3 middle=camera.WorldToScreenPoint(renderer.bounds.center);
            float best=Single.MaxValue;
            bool found=false;
            for(int sub=0;sub<geometry.triangles.Length;sub++) {
                Texture2D texture=materials[sub].mainTexture as Texture2D;
                int[] indices=geometry.triangles[sub];
                for(int i=0;i+2<indices.Length;i+=3) {
                    int ia=indices[i], ib=indices[i+1], ic=indices[i+2];
                    if(ia<0 || ib<0 || ic<0 || ia>=geometry.vertices.Length || ib>=geometry.vertices.Length || ic>=geometry.vertices.Length) continue;
                    if(geometry.colors[ia].a!=255 || geometry.colors[ib].a!=255 || geometry.colors[ic].a!=255) continue;
                    Vector3 wa=renderer.transform.TransformPoint(geometry.vertices[ia]);
                    Vector3 wb=renderer.transform.TransformPoint(geometry.vertices[ib]);
                    Vector3 wc=renderer.transform.TransformPoint(geometry.vertices[ic]);
                    Vector3 a=camera.WorldToScreenPoint(wa),b=camera.WorldToScreenPoint(wb),c=camera.WorldToScreenPoint(wc);
                    Vector3 point=pick?(a+b+c)/3:fixedPoint;
                    float score=(point.x-middle.x)*(point.x-middle.x)+(point.y-middle.y)*(point.y-middle.y);
                    if(pick && score>=best) continue;
                    Rect patch;
                    if(!Patch(new Vector2(point.x,point.y),a,b,c,geometry.uv[ia],geometry.uv[ib],geometry.uv[ic],texture,camera,out patch)) {
                        LastFailure+="["+texture.width+"x"+texture.height+",mips="+texture.mipmapCount+",aniso="+texture.anisoLevel+"]";
                        continue;
                    }
                    Vector3 candidate=pick?(wa+wb+wc)/3:requested;
                    if(visible!=null && !visible(patch,candidate)) continue;
                    world=candidate; region=patch; found=true; best=score;
                    if(!pick) { LastFailure=""; return true; }
                }
            }
            if(found) LastFailure="";
            return found;
        } catch { return Fail("surface_exception"); }
    }
}
