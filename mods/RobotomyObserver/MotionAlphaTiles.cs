using System;

// Exact alpha queries with 8x8 min/max tiles. ~1.03 bytes/texel instead of two
// 32-bit integral images (~8 bytes/texel). Boundary tiles still inspect pixels.
public sealed class MotionAlphaTiles {
 public readonly byte[] alpha,minimum,maximum;public readonly int width,height,stride;
 public MotionAlphaTiles(byte[] values,int w,int h){
  if(w<1||h<1||values==null||values.Length!=w*h)throw new ArgumentException("alpha dimensions");
  alpha=values;width=w;height=h;stride=(w+7)/8;minimum=new byte[stride*((h+7)/8)];maximum=new byte[minimum.Length];
  for(int i=0;i<minimum.Length;i++)minimum[i]=255;
  for(int y=0;y<h;y++)for(int x=0;x<w;x++){int i=(y/8)*stride+x/8;byte a=alpha[y*w+x];if(a<minimum[i])minimum[i]=a;if(a>maximum[i])maximum[i]=a;}
 }
 public bool Any(int x0,int y0,int x1,int y1,bool nonzero){
  if(x0<0||y0<0||x1>width||y1>height||x1<x0||y1<y0)throw new ArgumentOutOfRangeException();
  if(x0==x1||y0==y1)return false;
  for(int ty=y0/8;ty<=(y1-1)/8;ty++)for(int tx=x0/8;tx<=(x1-1)/8;tx++){
   int i=ty*stride+tx;if(nonzero?maximum[i]==0:minimum[i]==255)continue;
   int bx=tx*8,by=ty*8,ex=Math.Min(width,bx+8),ey=Math.Min(height,by+8);
   if(x0<=bx&&y0<=by&&x1>=ex&&y1>=ey)return true;
   for(int y=Math.Max(y0,by);y<Math.Min(y1,ey);y++)for(int x=Math.Max(x0,bx);x<Math.Min(x1,ex);x++)if(nonzero?alpha[y*width+x]!=0:alpha[y*width+x]!=255)return true;
  }return false;
 }
}
