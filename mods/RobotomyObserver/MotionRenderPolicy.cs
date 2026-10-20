using System;

// Scene-independent normal display contract. Unknown distortion is not equivalent to normal rendering.
public static class MotionRenderPolicy {
    static bool Near(float a,float b) { return Math.Abs(a-b)<.0001f; }
    public static bool Clamp(float r0,float r1,float g0,float g1,float b0,float b1,float start,float end) {
        return Near(r0,0)&&Near(r1,1)&&Near(g0,0)&&Near(g1,1)&&Near(b0,0)&&Near(b1,1)&&
            start>=0 && start<=.1001f && Near(end,1);
    }
    public static bool Glow(float amount,int filter,float threshold,float intensity,float precision,float r,float g,float b,float a) {
        bool shippedDefault=Near(threshold,.5f)&&Near(intensity,2.25f)&&Near(precision,.56f);
        bool main=Near(threshold,1)&&Near(intensity,3)&&Near(precision,1);
        return Near(intensity,0) || (Near(amount,4)&&filter==4&&(shippedDefault||main)&&
            Near(r,0)&&Near(g,.7f)&&Near(b,1)&&Near(a,1));
    }
}
