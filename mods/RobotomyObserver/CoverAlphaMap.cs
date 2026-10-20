using System;

// Summed area map: one build per texture, constant-time overlap checks per label.
public sealed class CoverAlphaMap {
    readonly int width, height;
    readonly int[] sums;
    public CoverAlphaMap(byte[] alpha,int width,int height) {
        this.width=width; this.height=height;
        sums=new int[(width+1)*(height+1)];
        for(int y=0;y<height;y++) {
            int row=0;
            for(int x=0;x<width;x++) {
                // Permit only light pause tint, not opaque icons or dense translucent covers.
                row+=alpha[y*width+x]>63?1:0;
                sums[(y+1)*(width+1)+x+1]=sums[y*(width+1)+x+1]+row;
            }
        }
    }
    public bool Clear(int x0,int y0,int x1,int y1) {
        if(x0<0 || y0<0 || x1>width || y1>height || x1<=x0 || y1<=y0) return false;
        int stride=width+1;
        return sums[y1*stride+x1]-sums[y0*stride+x1]-sums[y1*stride+x0]+sums[y0*stride+x0]==0;
    }
}
