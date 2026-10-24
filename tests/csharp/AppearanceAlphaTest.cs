using System;
class AppearanceAlphaTest {
 static int Main(){var rng=new Random(71);int checkedCount=0;
  foreach(int w in new[]{1,7,8,9,31,64})foreach(int h in new[]{1,8,17,65})foreach(int pattern in new[]{0,1,2}){
   var a=new byte[w*h];for(int i=0;i<a.Length;i++)a[i]=pattern==0?(byte)0:pattern==1?(byte)255:(byte)rng.Next(256);
   var tiles=new MotionAlphaTiles(a,w,h);
   for(int n=0;n<500;n++){int x0=rng.Next(w+1),y0=rng.Next(h+1),x1=rng.Next(x0,w+1),y1=rng.Next(y0,h+1);
    foreach(bool nonzero in new[]{false,true}){bool expected=false;for(int y=y0;y<y1;y++)for(int x=x0;x<x1;x++)if(nonzero?a[y*w+x]!=0:a[y*w+x]!=255)expected=true;
     if(expected!=tiles.Any(x0,y0,x1,y1,nonzero))throw new Exception("Alpha region changed");checkedCount++;
    }
   }
  }Console.WriteLine(checkedCount+" exact rectangle queries passed");return 0;
 }
}
